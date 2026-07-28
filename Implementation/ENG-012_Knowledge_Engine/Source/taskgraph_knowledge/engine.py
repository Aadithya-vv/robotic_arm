"""Thread-safe, non-reasoning ENG-012 Knowledge Engine."""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from threading import RLock
from typing import Any
from .contracts import *

class KnowledgeEngine:
    def __init__(self,source:SemanticInventorySource,storage:KnowledgeStorage,configuration:KnowledgeConfiguration|None=None,clock=None,log_sink:LogSink|None=None):
        if not isinstance(source,SemanticInventorySource):raise TypeError("source must satisfy SemanticInventorySource")
        if not isinstance(storage,KnowledgeStorage):raise TypeError("storage must satisfy KnowledgeStorage")
        self._source,self._storage=source,storage;self._configuration=configuration or KnowledgeConfiguration();self._clock=clock or (lambda:datetime.now(timezone.utc).isoformat());self._log=log_sink or NullLogSink()
        if not self._configuration.schema_version or self._configuration.maximum_records<1:raise ValueError("invalid Knowledge configuration")
        if not isinstance(self._log,LogSink):raise TypeError("log_sink must satisfy LogSink")
        self._state=KnowledgeState.EMPTY;self._graph=None;self._lock=RLock();self._sequence=0;self._by_id={};self._by_object={}
    @property
    def state(self):return self._state
    def initialize(self,request):
        with self._lock:
            if self._state is not KnowledgeState.EMPTY:return self._invalid(request,"initialize")
            error=self._request_error(request)
            if error:return self._response(request,ResponseStatus.REJECTED,errors=(error,))
            self._state=KnowledgeState.BUILDING
            try:return self._build(request,"initialized")
            except Exception as exc:return self._failure(request,"knowledge.initialize.failed",exc)
    def rebuild(self,request):
        with self._lock:
            if self._state is not KnowledgeState.AVAILABLE:return self._invalid(request,"rebuild")
            self._state=KnowledgeState.UPDATING
            try:return self._build(request,"rebuilt")
            except Exception as exc:return self._failure(request,"knowledge.rebuild.failed",exc)
    def get_knowledge(self,request,knowledge_id=None):
        if knowledge_id is None:
            with self._lock:
                rejected=self._ready(request);return rejected or self._response(request,ResponseStatus.SUCCEEDED,graph=self._graph)
        return self._lookup(request,self._by_id,knowledge_id,"knowledge")
    def get_knowledge_by_object(self,request,object_id):return self._lookup(request,self._by_object,object_id,"object")
    def _lookup(self,request,index,key,kind):
        with self._lock:
            rejected=self._ready(request)
            if rejected:return rejected
            item=index.get(str(key))
            if item is None:return self._response(request,ResponseStatus.REJECTED,errors=(self._error(request,"not_found",f"knowledge.{kind}.not_found",f"{kind} knowledge was not found"),))
            return self._response(request,ResponseStatus.SUCCEEDED,record=item)
    def search(self,request,query="",property_name="",fact="",category="",relationship=""):
        with self._lock:
            rejected=self._ready(request)
            if rejected:return rejected
            q,prop,known,cat,rel=(str(v).strip().casefold() for v in (query,property_name,fact,category,relationship))
            records=tuple(r for r in self._graph.records if (not q or q in r.object_name.casefold() or q in json.dumps(plain(r),sort_keys=True).casefold()) and (not prop or any(prop==k.casefold() for k in r.properties)) and (not known or any(known in json.dumps(plain(x),sort_keys=True).casefold() for x in r.facts)) and (not cat or r.category.casefold()==cat) and (not rel or any(rel in json.dumps(plain(x),sort_keys=True).casefold() for x in r.relationships)))
            return self._response(request,ResponseStatus.SUCCEEDED,graph=self._snapshot(records))
    def get_statistics(self,request):
        with self._lock:
            rejected=self._ready(request);return rejected or self._response(request,ResponseStatus.SUCCEEDED,statistics=self._graph.statistics)
    def export_knowledge(self,request):
        with self._lock:
            rejected=self._ready(request);return rejected or self._response(request,ResponseStatus.SUCCEEDED,export=freeze(plain(self._graph)))
    def validate_knowledge(self,request):
        with self._lock:
            rejected=self._ready(request)
            if rejected:return rejected
            valid=all(self._checksum(r)==r.checksum and r.object_id and r.knowledge_id for r in self._graph.records)
            return self._response(request,ResponseStatus.SUCCEEDED if valid else ResponseStatus.FAILED,valid=valid,errors=() if valid else (self._error(request,"internal_invariant","knowledge.integrity.failed","knowledge checksum validation failed"),))
    def close(self,request):
        with self._lock:
            if self._state in (KnowledgeState.EMPTY,KnowledgeState.CLOSED):return self._invalid(request,"close")
            self._state=KnowledgeState.CLOSED;return self._response(request,ResponseStatus.SUCCEEDED,explanations=(self._explain(request,"knowledge graph","closed",()),))
    def _build(self,request,decision):
        source=self._source.get_all()
        if len(source)>self._configuration.maximum_records:raise ValueError("semantic inventory exceeds configured capacity")
        records=tuple(self._record(item) for item in source);self._graph=self._snapshot(records);self._by_id={r.knowledge_id:r for r in records};self._by_object={r.object_id:r for r in records};self._storage.save(plain(self._graph));self._state=KnowledgeState.AVAILABLE
        return self._response(request,ResponseStatus.SUCCEEDED,graph=self._graph,explanations=(self._explain(request,"knowledge graph",decision,(f"records={len(records)}",)),))
    def _record(self,item):
        if not isinstance(item,SemanticObjectContract) or not item.object_id or not item.object_name:raise ValueError("invalid semantic object contract")
        metadata=plain(item.metadata);properties={"category":item.category,"semantic_version":item.version,"tags":list(item.tags)};facts=[]
        if item.description:facts.append({"predicate":"description","value":item.description,"source":"semantic_inventory"})
        if item.aliases:facts.append({"predicate":"aliases","value":list(item.aliases),"source":"semantic_inventory"})
        attributes={k:metadata[k] for k in ("user_name","ai_name","times_seen","recognition_statistics") if k in metadata};materials=self._strings(metadata.get("materials",()) or ([metadata.get("material")] if metadata.get("material") else ()));uses=self._strings(metadata.get("typical_uses",()));environment=plain(metadata.get("environment",{}))
        summary=f"{item.object_name} — {item.category}."+(f" {item.description}" if item.description else "")
        base={"knowledge_id":f"knowledge:{item.object_id}","object_id":item.object_id,"object_name":item.object_name,"category":item.category,"summary":summary,"properties":properties,"facts":facts,"attributes":attributes,"typical_uses":uses,"materials":materials,"environment":environment,"confidence":max(0.0,min(1.0,float(item.average_confidence))),"knowledge_sources":("semantic_inventory",item.object_id),"relationships":tuple(item.relationships),"metadata":{"semantic_score":getattr(item,"semantic_score",0.0),"semantic_record_version":item.version},"version":CONTRACT_VERSION,"schema_version":SCHEMA_VERSION,"engine_version":ENGINE_VERSION,"created":item.learning_date or self._clock(),"updated":item.last_updated or self._clock()}
        checksum=self._checksum_values(base);return KnowledgeRecord(**base,checksum=checksum)
    def _snapshot(self,records):
        records=tuple(sorted(records,key=lambda r:r.knowledge_id));categories={};properties={};facts=relationships=0
        for record in records:
            categories[record.category]=categories.get(record.category,0)+1;facts+=len(record.facts);relationships+=len(record.relationships)
            for key in record.properties:properties[key]=properties.get(key,0)+1
        average=sum(r.confidence for r in records)/len(records) if records else 0.0
        return KnowledgeGraph(CONTRACT_VERSION,SCHEMA_VERSION,self._clock(),records,KnowledgeStatistics(len(records),categories,properties,facts,relationships,average))
    @staticmethod
    def _strings(values):return tuple(dict.fromkeys(str(v).strip() for v in values if v is not None and str(v).strip()))
    @staticmethod
    def _checksum_values(values):return hashlib.sha256(json.dumps(plain(values),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    def _checksum(self,record):values=plain(record);values.pop("checksum",None);return self._checksum_values(values)
    def _ready(self,request):
        error=self._request_error(request)
        if error:return self._response(request,ResponseStatus.REJECTED,errors=(error,))
        if self._state is not KnowledgeState.AVAILABLE:return self._invalid(request,"read")
    def _request_error(self,request):
        if not isinstance(request,KnowledgeRequest):return self._error(request,"validation","knowledge.request.invalid","request must be KnowledgeRequest")
        if not request.request_id or not request.correlation_id or not request.source_identity:return self._error(request,"validation","knowledge.request.missing_identity","request identities are required")
        if request.contract_id!=CONTRACT_ID or request.contract_version.split('.')[0]!=CONTRACT_VERSION.split('.')[0]:return self._error(request,"unsupported_version","knowledge.request.unsupported_contract","contract identity or major version is unsupported")
    def _invalid(self,request,operation):return self._response(request,ResponseStatus.REJECTED,errors=(self._error(request,"invalid_state","knowledge.lifecycle.invalid_state",f"cannot {operation} while {self._state.value}"),))
    def _failure(self,request,code,exc):self._state=KnowledgeState.INVALID;return self._response(request,ResponseStatus.FAILED,errors=(self._error(request,"processing",code,f"knowledge operation failed: {type(exc).__name__}"),))
    def _error(self,request,category,code,message):return KnowledgeError(category,code,message,getattr(request,"request_id","unknown"),getattr(request,"correlation_id","unknown"))
    def _explain(self,request,subject,decision,facts):self._sequence+=1;return ExplanationRecord(f"{request.correlation_id}:knowledge:{self._sequence}",ENGINE_ID,request.correlation_id,subject,decision,tuple(facts),"succeeded")
    def _response(self,request,status,**values):
        rid,corr=getattr(request,"request_id","unknown"),getattr(request,"correlation_id","unknown");response=KnowledgeResponse(f"{rid}:knowledge-response",rid,corr,status,self._state,**values)
        try:self._log.record(LogRecord(ENGINE_ID,"knowledge.operation","error" if status is ResponseStatus.FAILED else "warning" if status is ResponseStatus.REJECTED else "info",corr,status.value,{"state":self._state.value}))
        except Exception:
            if status is not ResponseStatus.FAILED:self._state=KnowledgeState.INVALID;response=KnowledgeResponse(f"{rid}:knowledge-response",rid,corr,ResponseStatus.FAILED,self._state,errors=tuple(values.get("errors",()))+(self._error(request,"dependency_unavailable","knowledge.logging.failed","logging contract failed"),))
        return response
