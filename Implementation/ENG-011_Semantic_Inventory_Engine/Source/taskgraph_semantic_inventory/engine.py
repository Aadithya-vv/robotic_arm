"""Thread-safe ENG-011 semantic inventory implementation."""
from __future__ import annotations
from datetime import datetime,timezone
from threading import RLock
from typing import Any,Mapping
from .contracts import *

class SemanticInventoryEngine:
    def __init__(self,source:ObjectSource,storage:InventoryStorage,clock=None,log_sink:LogSink|None=None):
        if not isinstance(source,ObjectSource):raise TypeError("source must satisfy ObjectSource")
        if not isinstance(storage,InventoryStorage):raise TypeError("storage must satisfy InventoryStorage")
        self._source,self._storage=source,storage;self._clock=clock or (lambda:datetime.now(timezone.utc).isoformat());self._log=log_sink or NullLogSink()
        if not isinstance(self._log,LogSink):raise TypeError("log_sink must satisfy LogSink")
        self._state=InventoryState.EMPTY;self._inventory=None;self._lock=RLock();self._sequence=0
    @property
    def state(self):return self._state
    def initialize(self,request):
        with self._lock:
            error=self._request_error(request)
            if error:return self._response(request,ResponseStatus.REJECTED,errors=(error,))
            if self._state is not InventoryState.EMPTY:return self._invalid(request,"initialize")
            self._state=InventoryState.BUILDING
            try:return self._build(request,"initialized")
            except Exception as exc:return self._failure(request,"semantic.initialize.failed",exc)
    def refresh(self,request):
        with self._lock:
            if self._state is not InventoryState.AVAILABLE:return self._invalid(request,"refresh")
            self._state=InventoryState.UPDATING
            try:return self._build(request,"refreshed")
            except Exception as exc:return self._failure(request,"semantic.refresh.failed",exc)
    def get_object(self,request,object_id):
        with self._lock:
            rejected=self._ready(request)
            if rejected:return rejected
            item=next((x for x in self._inventory.objects if x.object_id==object_id),None)
            if item is None:return self._response(request,ResponseStatus.REJECTED,errors=(self._error(request,"not_found","semantic.object.not_found","semantic object was not found"),))
            return self._response(request,ResponseStatus.SUCCEEDED,object=item)
    def get_all_objects(self,request):
        with self._lock:
            rejected=self._ready(request)
            return rejected or self._response(request,ResponseStatus.SUCCEEDED,inventory=self._inventory)
    def search(self,request,query="",category="",alias="",tag=""):
        with self._lock:
            rejected=self._ready(request)
            if rejected:return rejected
            q,cat,aka,label=(str(v).strip().casefold() for v in (query,category,alias,tag))
            objects=tuple(item for item in self._inventory.objects if (not q or q in item.object_name.casefold() or q in item.description.casefold()) and (not cat or item.category.casefold()==cat) and (not aka or any(aka in x.casefold() for x in item.aliases)) and (not label or any(label==x.casefold() for x in item.tags)))
            return self._response(request,ResponseStatus.SUCCEEDED,inventory=self._snapshot(objects))
    def get_statistics(self,request):
        with self._lock:
            rejected=self._ready(request);return rejected or self._response(request,ResponseStatus.SUCCEEDED,statistics=self._inventory.statistics)
    def export_inventory(self,request):
        with self._lock:
            rejected=self._ready(request);return rejected or self._response(request,ResponseStatus.SUCCEEDED,export=freeze(plain(self._inventory)))
    def close(self,request):
        with self._lock:
            if self._state in (InventoryState.EMPTY,InventoryState.CLOSED):return self._invalid(request,"close")
            self._state=InventoryState.CLOSED;return self._response(request,ResponseStatus.SUCCEEDED,explanations=(self._explain(request,"inventory","closed",()),))
    def _build(self,request,decision):
        records=tuple(self._normalize(item) for item in self._source.get_all());self._inventory=self._snapshot(records);self._storage.save(plain(self._inventory));self._state=InventoryState.AVAILABLE
        return self._response(request,ResponseStatus.SUCCEEDED,inventory=self._inventory,explanations=(self._explain(request,"inventory",decision,(f"objects={len(records)}",)),))
    def _normalize(self,item:Mapping[str,Any])->SemanticObject:
        object_id=str(item.get("object_id","")).strip();name=str(item.get("name","")).strip()
        if not object_id or not name:raise ValueError("object_id and name are required")
        aliases=self._strings(item.get("aliases",()));tags=self._strings(item.get("tags",()));category=str(item.get("category","")).strip() or "Uncategorized";description=str(item.get("description","")).strip()
        thumbnail=item.get("thumbnail",{}) or {};images=self._strings(thumbnail.get("instance_images",()) or ([thumbnail.get("path")] if thumbnail.get("path") else ()));frames=self._strings(item.get("frames",()))
        confidence=max(0.0,min(1.0,float(item.get("average_confidence",0) or 0)));completeness=sum(bool(v) for v in (name,category,description,aliases,tags,images))/6
        metadata={"user_name":item.get("user_name",name),"ai_name":item.get("ai_name",""),"recognition_statistics":item.get("recognition_statistics",{}),"feature_descriptor_references":[x[0] for x in item.get("descriptors",()) if isinstance(x,(tuple,list)) and x],"times_seen":item.get("times_seen",0)}
        return SemanticObject(object_id,name,category,description,aliases,tuple(item.get("descriptors",())),frames,images,tuple(item.get("recognition_history",())),confidence,str(item.get("created","") or ""),str(item.get("updated",item.get("created","")) or ""),self._strings(item.get("videos",())),frames,tags,tuple(item.get("relationships",())),(),round(completeness*.7+confidence*.3,6),metadata=metadata)
    def _snapshot(self,objects):
        objects=tuple(sorted(objects,key=lambda x:x.object_id));categories={};tags={}
        for item in objects:
            categories[item.category]=categories.get(item.category,0)+1
            for tag in item.tags:tags[tag]=tags.get(tag,0)+1
        score=sum(x.semantic_score for x in objects)/len(objects) if objects else 0.0
        return SemanticInventory(SCHEMA_VERSION,self._clock(),objects,InventoryStatistics(len(objects),categories,tags,score))
    @staticmethod
    def _strings(values):return tuple(dict.fromkeys(str(v).strip() for v in values if v is not None and str(v).strip()))
    def _ready(self,request):
        error=self._request_error(request)
        if error:return self._response(request,ResponseStatus.REJECTED,errors=(error,))
        if self._state is not InventoryState.AVAILABLE:return self._invalid(request,"read")
    def _request_error(self,request):
        if not isinstance(request,SemanticRequest):return self._error(request,"validation","semantic.request.invalid","request must be SemanticRequest")
        if not request.request_id or not request.correlation_id or not request.source_identity:return self._error(request,"validation","semantic.request.missing_identity","request identities are required")
        if request.contract_id!=CONTRACT_ID or request.contract_version.split('.')[0]!=CONTRACT_VERSION.split('.')[0]:return self._error(request,"unsupported_version","semantic.request.unsupported_contract","contract identity or major version is unsupported")
    def _invalid(self,request,operation):return self._response(request,ResponseStatus.REJECTED,errors=(self._error(request,"invalid_state","semantic.lifecycle.invalid_state",f"cannot {operation} while {self._state.value}"),))
    def _failure(self,request,code,exc):self._state=InventoryState.INVALID;return self._response(request,ResponseStatus.FAILED,errors=(self._error(request,"processing",code,f"semantic inventory operation failed: {type(exc).__name__}"),))
    def _error(self,request,category,code,message):return SemanticError(category,code,message,getattr(request,"request_id","unknown"),getattr(request,"correlation_id","unknown"))
    def _explain(self,request,subject,decision,facts):self._sequence+=1;return ExplanationRecord(f"{request.correlation_id}:semantic:{self._sequence}",ENGINE_ID,request.correlation_id,subject,decision,tuple(facts),"succeeded")
    def _response(self,request,status,**values):
        request_id,correlation=getattr(request,"request_id","unknown"),getattr(request,"correlation_id","unknown");response=SemanticResponse(f"{request_id}:semantic-response",request_id,correlation,status,self._state,**values)
        try:self._log.record(LogRecord(ENGINE_ID,"semantic.operation","error" if status is ResponseStatus.FAILED else "warning" if status is ResponseStatus.REJECTED else "info",correlation,status.value,{"state":self._state.value}))
        except Exception:
            if status is not ResponseStatus.FAILED:
                self._state=InventoryState.INVALID;error=self._error(request,"dependency_unavailable","semantic.logging.failed","logging contract failed")
                response=SemanticResponse(f"{request_id}:semantic-response",request_id,correlation,ResponseStatus.FAILED,self._state,errors=tuple(values.get("errors",()))+(error,))
        return response
