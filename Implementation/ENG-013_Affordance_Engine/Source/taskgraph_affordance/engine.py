from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from threading import RLock
from .contracts import *
from .rules import ACTION_CATEGORIES,matching_rules
class AffordanceEngine:
    def __init__(self,source:KnowledgeSource,storage:AffordanceStorage,configuration=None,clock=None,log_sink=None):
        if not isinstance(source,KnowledgeSource):raise TypeError("source must satisfy KnowledgeSource")
        if not isinstance(storage,AffordanceStorage):raise TypeError("storage must satisfy AffordanceStorage")
        self._source,self._storage=source,storage;self._configuration=configuration or AffordanceConfiguration();self._clock=clock or (lambda:datetime.now(timezone.utc).isoformat());self._log=log_sink or NullLogSink()
        if self._configuration.maximum_records<1 or self._configuration.rule_version!=RULE_VERSION:raise ValueError("invalid Affordance configuration")
        self._state=AffordanceState.EMPTY;self._graph=None;self._by_id={};self._by_object={};self._lock=RLock();self._sequence=0
    @property
    def state(self):return self._state
    def initialize(self,r):
        with self._lock:
            if self._state is not AffordanceState.EMPTY:return self._invalid(r,"initialize")
            self._state=AffordanceState.BUILDING
            try:return self._build(r,"initialized")
            except Exception as e:return self._failure(r,"affordance.initialize.failed",e)
    def rebuild(self,r):
        with self._lock:
            if self._state is not AffordanceState.AVAILABLE:return self._invalid(r,"rebuild")
            self._state=AffordanceState.UPDATING
            try:return self._build(r,"rebuilt")
            except Exception as e:return self._failure(r,"affordance.rebuild.failed",e)
    def get_affordance(self,r,affordance_id=None):
        with self._lock:
            bad=self._ready(r)
            if bad:return bad
            if affordance_id is None:return self._response(r,ResponseStatus.SUCCEEDED,graph=self._graph)
            return self._found(r,self._by_id.get(affordance_id))
    def get_affordance_by_object(self,r,object_id):
        with self._lock:
            bad=self._ready(r);return bad or self._found(r,self._by_object.get(object_id))
    def _found(self,r,item):return self._response(r,ResponseStatus.SUCCEEDED,record=item) if item else self._response(r,ResponseStatus.REJECTED,errors=(self._error(r,"not_found","affordance.not_found","Affordance Record not found"),))
    def search(self,r,query="",capability="",action=""):
        with self._lock:
            bad=self._ready(r)
            if bad:return bad
            q,cap,act=(str(x).strip().casefold() for x in (query,capability,action));items=tuple(x for x in self._graph.records if (not q or q in x.object_name.casefold() or q in x.summary.casefold()) and (not cap or cap in (a.casefold() for a in x.affordances)) and (not act or act in (a.casefold() for a in x.affordances)))
            return self._response(r,ResponseStatus.SUCCEEDED,graph=self._snapshot(items))
    def export_affordances(self,r):
        with self._lock:
            bad=self._ready(r);return bad or self._response(r,ResponseStatus.SUCCEEDED,export=freeze(plain(self._graph)))
    def validate_affordances(self,r):
        with self._lock:
            bad=self._ready(r)
            if bad:return bad
            valid=all(self._checksum(x)==x.checksum and tuple(sorted(set(x.affordances)))==x.affordances for x in self._graph.records)
            return self._response(r,ResponseStatus.SUCCEEDED if valid else ResponseStatus.FAILED,valid=valid,errors=() if valid else (self._error(r,"invariant","affordance.integrity.failed","Affordance integrity failed"),))
    def get_statistics(self,r):
        with self._lock:
            bad=self._ready(r);return bad or self._response(r,ResponseStatus.SUCCEEDED,statistics=self._graph.statistics)
    def close(self,r):
        with self._lock:
            if self._state in (AffordanceState.EMPTY,AffordanceState.CLOSED):return self._invalid(r,"close")
            self._state=AffordanceState.CLOSED;return self._response(r,ResponseStatus.SUCCEEDED)
    def _build(self,r,decision):
        source=self._source.get_all()
        if len(source)>self._configuration.maximum_records:raise ValueError("capacity exceeded")
        records=tuple(self._record(x) for x in source);self._graph=self._snapshot(records);self._by_id={x.affordance_id:x for x in records};self._by_object={x.object_id:x for x in records};self._storage.save(plain(self._graph));self._state=AffordanceState.AVAILABLE
        return self._response(r,ResponseStatus.SUCCEEDED,graph=self._graph,explanations=(self._explain(r,decision,(f"records={len(records)}",)),))
    def _record(self,k):
        if not isinstance(k,KnowledgeRecordContract) or not k.knowledge_id or not k.object_id:raise ValueError("invalid Knowledge contract")
        rules=matching_rules(k.object_name,k.category);actions=tuple(sorted({a for rule in rules for a in rule.actions}));ids=tuple(rule.rule_id+"@"+rule.version for rule in rules);pre={a:("object available",) for a in actions};post={a:("capability applied",) for a in actions};constraints={a:("context validation required",) for a in actions};safety={a:("execution safety belongs downstream",) for a in actions};base={"affordance_id":f"affordance:{k.object_id}","object_id":k.object_id,"knowledge_id":k.knowledge_id,"object_name":k.object_name,"summary":f"{k.object_name}: {', '.join(actions) if actions else 'no catalogued capabilities'}.","affordances":actions,"preconditions":pre,"postconditions":post,"constraints":constraints,"safety_notes":safety,"confidence":k.confidence if actions else 0.0,"knowledge_sources":tuple(k.knowledge_sources)+(k.knowledge_id,),"generation_rule":ids,"metadata":{"category":k.category,"action_categories":{a:ACTION_CATEGORIES.get(a,"uncategorized") for a in actions}},"schema_version":SCHEMA_VERSION,"engine_version":ENGINE_VERSION,"created":k.created or self._clock(),"updated":k.updated or self._clock()};return AffordanceRecord(**base,checksum=self._hash(base))
    def _snapshot(self,records):
        records=tuple(sorted(records,key=lambda x:x.affordance_id));actions={};cats={}
        for x in records:
            for a in x.affordances:actions[a]=actions.get(a,0)+1;cat=ACTION_CATEGORIES.get(a,"uncategorized");cats[cat]=cats.get(cat,0)+1
        total=sum(actions.values());avg=sum(x.confidence for x in records)/len(records) if records else 0
        return AffordanceGraph(CONTRACT_VERSION,SCHEMA_VERSION,RULE_VERSION,self._clock(),records,AffordanceStatistics(len(records),total,actions,cats,avg))
    @staticmethod
    def _hash(v):return hashlib.sha256(json.dumps(plain(v),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    def _checksum(self,x):v=plain(x);v.pop("checksum",None);return self._hash(v)
    def _ready(self,r):
        if not isinstance(r,AffordanceRequest) or not r.request_id or not r.correlation_id:return self._response(r,ResponseStatus.REJECTED,errors=(self._error(r,"validation","affordance.request.invalid","Invalid request"),))
        if self._state is not AffordanceState.AVAILABLE:return self._invalid(r,"read")
    def _invalid(self,r,op):return self._response(r,ResponseStatus.REJECTED,errors=(self._error(r,"invalid_state","affordance.lifecycle.invalid_state",f"Cannot {op} while {self._state.value}"),))
    def _failure(self,r,code,e):self._state=AffordanceState.INVALID;return self._response(r,ResponseStatus.FAILED,errors=(self._error(r,"processing",code,f"Affordance operation failed: {type(e).__name__}"),))
    def _error(self,r,cat,code,msg):return AffordanceError(cat,code,msg,getattr(r,"request_id","unknown"),getattr(r,"correlation_id","unknown"))
    def _explain(self,r,decision,facts):self._sequence+=1;return ExplanationRecord(f"{r.correlation_id}:affordance:{self._sequence}",ENGINE_ID,r.correlation_id,"affordance graph",decision,tuple(facts),"succeeded")
    def _response(self,r,status,**kw):
        rid,corr=getattr(r,"request_id","unknown"),getattr(r,"correlation_id","unknown");response=AffordanceResponse(f"{rid}:affordance-response",rid,corr,status,self._state,**kw)
        try:self._log.record(LogRecord(ENGINE_ID,"affordance.operation","error" if status is ResponseStatus.FAILED else "info",corr,status.value,{"state":self._state.value}))
        except Exception:
            if status is not ResponseStatus.FAILED:self._state=AffordanceState.INVALID;response=AffordanceResponse(f"{rid}:affordance-response",rid,corr,ResponseStatus.FAILED,self._state,errors=(self._error(r,"dependency","affordance.logging.failed","Logging failed"),))
        return response
