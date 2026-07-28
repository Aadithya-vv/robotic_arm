from __future__ import annotations
import hashlib,json
from threading import RLock
from .contracts import *
class ExplainabilityEngine:
    def __init__(self,artifact_source,storage,configuration=None,log_sink=None):
        if not isinstance(artifact_source,ArtifactSource):raise TypeError("invalid artifact source")
        if not isinstance(storage,ExplanationStorage):raise TypeError("invalid explanation storage")
        self._source,self._storage=artifact_source,storage;self._configuration=configuration or ExplainabilityConfiguration();self._log=log_sink or NullLogSink();self._records={};self._state=ExplainabilityState.EMPTY;self._lock=RLock()
    @property
    def state(self):return self._state
    def initialize(self,r):
        with self._lock:
            if self._state is not ExplainabilityState.EMPTY:return self._invalid(r,"initialize")
            try:
                payload=self._storage.load() or {"schema_version":SCHEMA_VERSION,"records":[]};self._major(payload.get("schema_version",""));records=tuple(self._decode(x) for x in payload.get("records",[]))
                if any(not self._validate(x)[0] for x in records):raise ValueError("stored explanation integrity failure")
                self._records={x.explanation_id:x for x in records};self._state=ExplainabilityState.AVAILABLE;return self._response(r,ResponseStatus.SUCCEEDED,records=self._all())
            except Exception as e:self._state=ExplainabilityState.INVALID;return self._error(r,"explain.initialize.failed",e)
    def generate_explanation(self,r,artifact_type,source_engine,artifact):
        with self._lock:
            bad=self._ready(r)
            if bad:return bad
            try:
                raw=plain(artifact);record=self._generate(str(artifact_type),str(source_engine),raw,r.correlation_id);valid,errors=self._validate(record)
                if not valid:return self._reject(r,"explain.generated.invalid","; ".join(errors))
                if len(self._records)>=self._configuration.maximum_records and record.explanation_id not in self._records:return self._reject(r,"explain.capacity.exceeded","Explanation capacity exceeded")
                self._records[record.explanation_id]=record;self._persist();return self._response(r,ResponseStatus.SUCCEEDED,record=record,valid=True)
            except Exception as e:return self._error(r,"explain.generate.failed",e)
    GenerateExplanation=generate_explanation
    def get_explanation(self,r,explanation_id):
        bad=self._ready(r);record=self._records.get(explanation_id);return bad or (self._response(r,ResponseStatus.SUCCEEDED,record=record) if record else self._reject(r,"explain.not_found","Explanation not found"))
    GetExplanation=get_explanation
    def search(self,r,query=""):
        bad=self._ready(r);q=str(query).casefold();return bad or self._response(r,ResponseStatus.SUCCEEDED,records=tuple(x for x in self._all() if not q or q in json.dumps(plain(x),sort_keys=True).casefold()))
    Search=search
    def export(self,r,explanation_id=None):
        bad=self._ready(r)
        if bad:return bad
        records=self._all() if explanation_id is None else ((self._records[explanation_id],) if explanation_id in self._records else ())
        if explanation_id and not records:return self._reject(r,"explain.not_found","Explanation not found")
        payload={"schema_version":SCHEMA_VERSION,"engine_version":ENGINE_VERSION,"records":[plain(x) for x in records]};return self._response(r,ResponseStatus.SUCCEEDED,records=records,export=freeze(payload))
    Export=export
    def import_records(self,r,payload):
        with self._lock:
            bad=self._ready(r)
            if bad:return bad
            try:
                values=payload.get("records") if isinstance(payload,Mapping) and "records" in payload else [payload];records=tuple(self._decode(x) for x in values);errors=tuple(e for x in records for e in self._validate(x)[1])
                if errors:return self._reject(r,"explain.import.invalid","; ".join(errors))
                self._records.update((x.explanation_id,x) for x in records);self._persist();return self._response(r,ResponseStatus.SUCCEEDED,records=records)
            except Exception as e:return self._error(r,"explain.import.invalid",e,ResponseStatus.REJECTED)
    Import=import_records
    def validate(self,r,subject):
        bad=self._ready(r)
        if bad:return bad
        try:record=self._records[subject] if isinstance(subject,str) else (subject if isinstance(subject,ExplanationRecord) else self._decode(subject));valid,errors=self._validate(record);return self._response(r,ResponseStatus.SUCCEEDED if valid else ResponseStatus.REJECTED,record=record,valid=valid,errors=tuple(ExplainabilityError("validation","explain.invalid",x,r.request_id,r.correlation_id) for x in errors))
        except Exception as e:return self._error(r,"explain.validate.failed",e,ResponseStatus.REJECTED)
    Validate=validate
    def get_statistics(self,r):
        bad=self._ready(r);types={};engines={}
        for x in self._records.values():types[x.artifact_type]=types.get(x.artifact_type,0)+1;engines[x.source_engine.engine_id]=engines.get(x.source_engine.engine_id,0)+1
        return bad or self._response(r,ResponseStatus.SUCCEEDED,statistics=Statistics(len(self._records),sum(self._validate(x)[0] for x in self._records.values()),types,engines))
    GetStatistics=get_statistics
    def rebuild(self,r):
        with self._lock:
            bad=self._ready(r)
            if bad:return bad
            generated=[]
            try:
                for artifact_type,engine,artifact in self._source.get_artifacts():generated.append(self._generate(artifact_type,engine,plain(artifact),r.correlation_id))
                if len(generated)>self._configuration.maximum_records:return self._reject(r,"explain.capacity.exceeded","Explanation capacity exceeded")
                self._records={x.explanation_id:x for x in generated};self._persist();return self._response(r,ResponseStatus.SUCCEEDED,records=self._all(),valid=True)
            except Exception as e:return self._error(r,"explain.rebuild.failed",e)
    Rebuild=rebuild
    def trace_artifact(self,r,artifact_id):
        matches=tuple(x for x in self._records.values() if x.artifact_id==artifact_id or artifact_id in x.dependency_trace.dependency_chain);return self._trace(r,matches,"artifact")
    TraceArtifact=trace_artifact
    def trace_decision(self,r,explanation_id):
        response=self.get_explanation(r,explanation_id);return response if not response.record else self._response(r,ResponseStatus.SUCCEEDED,record=response.record,trace=response.record.decision_trace)
    TraceDecision=trace_decision
    def trace_dependency(self,r,explanation_id):
        response=self.get_explanation(r,explanation_id);return response if not response.record else self._response(r,ResponseStatus.SUCCEEDED,record=response.record,trace=response.record.dependency_trace)
    TraceDependency=trace_dependency
    def close(self,r):
        with self._lock:
            if self._state is not ExplainabilityState.AVAILABLE:return self._invalid(r,"close")
            self._persist();self._state=ExplainabilityState.CLOSED;return self._response(r,ResponseStatus.SUCCEEDED)
    def _generate(self,artifact_type,source_engine,a,correlation):
        artifact_id=self._id(a);source_version=str(a.get("engine_version",a.get("version","1.0.0")));checksum=str(a.get("checksum",""));schema=str(a.get("schema_version","1.0"));meta=a.get("metadata",{});rule_id=str(meta.get("rule_id",getattr(meta,"rule_id","") if not isinstance(meta,Mapping) else ""));rule_version=str(meta.get("rule_version","")) if isinstance(meta,Mapping) else ""
        plan_id=str(a.get("semantic_plan_id",a.get("plan_id",a.get("compilation",{}).get("source_plan_id","") if isinstance(a.get("compilation"),Mapping) else "")));task_id=str(a.get("task_id",""));knowledge_id=str(a.get("knowledge_id",next((x.get("knowledge_id","") for x in a.get("resources",[]) if isinstance(x,Mapping)),"")));affordance_id=str(a.get("affordance_id",next((x.get("affordance_id","") for x in a.get("resources",[]) if isinstance(x,Mapping)),"")))
        actions=tuple(str(x.get("action","")) for x in a.get("nodes",[]) if isinstance(x,Mapping));provenance=tuple(str(x) for x in (meta.get("provenance",()) if isinstance(meta,Mapping) else ()));chain=tuple(dict.fromkeys(x for x in (knowledge_id,affordance_id,plan_id,task_id,artifact_id) if x));ref=ArtifactReference(artifact_id,artifact_type,EngineReference(source_engine,source_version),checksum,schema);nodes=tuple(ExplanationNode(f"explain-node:{i:03d}",x,ref,chain[:i]) for i,x in enumerate(chain,1));validation=a.get("validation",{});valid=bool(validation.get("valid",True)) if isinstance(validation,Mapping) else True;errors=tuple(validation.get("errors",())) if isinstance(validation,Mapping) else ();warnings=tuple(validation.get("warnings",())) if isinstance(validation,Mapping) else ();comp=a.get("compilation");compilation=CompilationExplanation(str(comp.get("compiler_id","")),str(comp.get("compiler_version","")),str(comp.get("source_plan_id","")),tuple(comp.get("diagnostics",()))) if isinstance(comp,Mapping) else None;checks={artifact_id:checksum};creation=str(a.get("created",a.get("updated","")));base={"explanation_id":"explanation:"+hashlib.sha256((artifact_type+":"+artifact_id+":"+checksum).encode()).hexdigest()[:24],"artifact_id":artifact_id,"artifact_type":artifact_type,"source_engine":EngineReference(source_engine,source_version),"source_version":source_version,"planning_rule_id":rule_id,"semantic_plan_id":plan_id,"task_ir_id":task_id,"knowledge_id":knowledge_id,"affordance_id":affordance_id,"dependency_trace":DependencyTrace(chain,nodes),"decision_trace":DecisionTrace(rule_id,plan_id,actions,tuple(f"declared action: {x}" for x in actions)),"provenance":ProvenanceRecord(artifact_id,provenance,checks),"rule":RuleExplanation(rule_id,rule_version,actions),"validation":ValidationExplanation(valid,errors,warnings),"compilation":compilation,"checksums":checks,"creation_time":creation,"engine_version":ENGINE_VERSION,"schema_version":SCHEMA_VERSION,"metadata":Metadata(correlation,{source_engine:source_version},{"source_schema":schema})};return ExplanationRecord(**base,checksum=self._hash(base))
    @staticmethod
    def _id(a):
        for k in ("task_id","plan_id","affordance_id","knowledge_id","object_id","artifact_id"):
            if a.get(k):return str(a[k])
        raise ValueError("artifact identity missing")
    def _validate(self,x):
        errors=[]
        try:self._major(x.schema_version)
        except Exception as e:errors.append(str(e))
        if not x.artifact_id:errors.append("artifact identity missing")
        if self._without(plain(x),"checksum")!=x.checksum:errors.append("explanation checksum mismatch")
        if not x.validation.valid:errors.append("source validation failed")
        return not errors,tuple(errors)
    def _decode(self,x):
        engine=EngineReference(**x["source_engine"]);d=x["dependency_trace"];nodes=tuple(ExplanationNode(artifact=ArtifactReference(source_engine=EngineReference(**n["artifact"]["source_engine"]),**{k:v for k,v in n["artifact"].items() if k!="source_engine"}),**{k:v for k,v in n.items() if k!="artifact"}) for n in d["nodes"]);dependency=DependencyTrace(d["dependency_chain"],nodes);comp=CompilationExplanation(**x["compilation"]) if x.get("compilation") else None;rest={k:v for k,v in x.items() if k not in {"source_engine","dependency_trace","decision_trace","provenance","rule","validation","compilation","metadata"}};return ExplanationRecord(source_engine=engine,dependency_trace=dependency,decision_trace=DecisionTrace(**x["decision_trace"]),provenance=ProvenanceRecord(**x["provenance"]),rule=RuleExplanation(**x["rule"]),validation=ValidationExplanation(**x["validation"]),compilation=comp,metadata=Metadata(**x["metadata"]),**rest)
    def _trace(self,r,matches,kind):
        bad=self._ready(r)
        if bad:return bad
        if not matches:return self._reject(r,"explain.trace.not_found",f"{kind} trace not found")
        return self._response(r,ResponseStatus.SUCCEEDED,records=matches,trace=tuple(x.dependency_trace for x in matches))
    def _persist(self):self._storage.save({"schema_version":SCHEMA_VERSION,"engine_version":ENGINE_VERSION,"records":[plain(x) for x in self._all()]})
    def _all(self):return tuple(sorted(self._records.values(),key=lambda x:x.explanation_id))
    def _major(self,v):
        if int(str(v).split(".")[0])!=self._configuration.supported_schema_major:raise ValueError("unsupported explanation schema major")
    @staticmethod
    def _hash(v):return hashlib.sha256(json.dumps(plain(v),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    def _without(self,v,k):v=dict(v);v.pop(k,None);return self._hash(v)
    def _ready(self,r):
        if not isinstance(r,ExplainabilityRequest) or not r.request_id or not r.correlation_id:return self._reject(r,"explain.request.invalid","Invalid request")
        if self._state is not ExplainabilityState.AVAILABLE:return self._invalid(r,"operate")
    def _invalid(self,r,op):return self._reject(r,"explain.lifecycle.invalid_state",f"Cannot {op} while {self._state.value}")
    def _reject(self,r,code,message):return self._response(r,ResponseStatus.REJECTED,errors=(ExplainabilityError("validation",code,message,getattr(r,"request_id","unknown"),getattr(r,"correlation_id","unknown")),))
    def _error(self,r,code,e,status=ResponseStatus.FAILED):return self._response(r,status,errors=(ExplainabilityError("processing",code,f"Explainability operation failed: {type(e).__name__}",getattr(r,"request_id","unknown"),getattr(r,"correlation_id","unknown")),))
    def _response(self,r,status,**kw):rid=getattr(r,"request_id","unknown");return ExplainabilityResponse(rid+":explain-response",rid,getattr(r,"correlation_id","unknown"),status,self._state,**kw)
