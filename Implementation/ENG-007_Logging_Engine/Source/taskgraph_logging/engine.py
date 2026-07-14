"""Central structured Logging Engine for ENG-007."""
from __future__ import annotations
from threading import RLock
from typing import Any,Mapping
from .contracts import *
_TRANSITIONS={LoggingState.CREATED:{LoggingState.CONFIGURING},LoggingState.CONFIGURING:{LoggingState.READY,LoggingState.DEGRADED},LoggingState.READY:{LoggingState.RECORDING,LoggingState.FLUSHING,LoggingState.DEGRADED},LoggingState.RECORDING:{LoggingState.READY,LoggingState.DEGRADED},LoggingState.DEGRADED:{LoggingState.FLUSHING},LoggingState.FLUSHING:{LoggingState.STOPPED,LoggingState.DEGRADED},LoggingState.STOPPED:set()}
class LoggingEngine:
    """Normalize, filter, retain, format, and forward runtime log records."""
    def __init__(self,*,policy:LoggingPolicy|None=None,sink:RuntimeLogSink|None=None):
        self._policy=policy or LoggingPolicy();self._sink=sink or NullRuntimeLogSink();self._state=LoggingState.CREATED;self._records=[];self._accepted=0;self._filtered=0;self._rejected=0;self._generation=0;self._sequence=0;self._explanations=[];self._lock=RLock()
    @property
    def state(self):
        with self._lock:return self._state
    @property
    def explanations(self):
        with self._lock:return tuple(self._explanations)
    def initialize(self,r):
        with self._lock:
            errors=self._validate_request(r)
            if errors:return self._response(r,ResponseStatus.REJECTED,errors)
            if self._state is not LoggingState.CREATED:return self._invalid(r,"initialize")
            error=self._transition(LoggingState.CONFIGURING,r)
            if error:return self._response(r,ResponseStatus.FAILED,(error,))
            policy_errors=self._validate_policy(r)
            if policy_errors:self._state=LoggingState.DEGRADED;return self._response(r,ResponseStatus.FAILED,policy_errors)
            error=self._transition(LoggingState.READY,r)
            if error:self._state=LoggingState.DEGRADED;return self._response(r,ResponseStatus.FAILED,(error,))
            return self._success(r,"Logging lifecycle","Logging is ready")
    def record(self,record)->None:
        """Structural sink boundary used by all existing Engine LogSink protocols."""
        try:
            entry=LogInput(source_identity=record.engine_id,category=record.category,severity=record.severity,correlation_id=record.correlation_id,message=record.message,timestamp_context=getattr(record,"timestamp_context",None),metadata=record.metadata)
        except Exception as exc:raise LoggingDeliveryError("invalid structural log record") from exc
        response=self.record_log(LoggingRequest(f"sink-{self._sequence+1}",entry.correlation_id,entry.source_identity),entry)
        if response.status is not ResponseStatus.SUCCEEDED:raise LoggingDeliveryError(response.errors[0].message if response.errors else "logging rejected record")
    def record_log(self,r,entry):
        with self._lock:
            errors=list(self._validate_request(r))+list(self._validate_entry(r,entry))
            if errors:self._rejected+=1;return self._response(r,ResponseStatus.REJECTED,errors)
            if self._state is not LoggingState.READY:return self._invalid(r,"record")
            severity=self._severity(entry.severity)
            if SEVERITY_RANK[severity]<SEVERITY_RANK[self._policy.minimum_severity] or (self._policy.allowed_categories and entry.category not in self._policy.allowed_categories):
                self._filtered+=1;explanation=self._explain(r,"Log filtering","record excluded by configured filter",(f"severity={severity.value}",f"category={entry.category}"),"succeeded");return self._response(r,ResponseStatus.SUCCEEDED,(),explanations=(explanation,),metadata={"recorded":False,"filtered":True})
            if len(self._records)>=self._policy.maximum_records:self._rejected+=1;return self._rejection(r,"conflict","logging.records.capacity","runtime log capacity reached")
            error=self._transition(LoggingState.RECORDING,r)
            if error:return self._response(r,ResponseStatus.FAILED,(error,))
            sequence=self._accepted+1;canonical=StructuredLogRecord(f"{entry.correlation_id}:log:{sequence}",sequence,entry.source_identity,entry.category,severity,entry.correlation_id,entry.message,entry.timestamp_context,entry.metadata)
            try:result=self._sink.write(canonical)
            except Exception as exc:return self._sink_failure(r,"logging.sink.write_exception","local log sink raised",type(exc).__name__)
            if not isinstance(result,SinkResult):return self._sink_failure(r,"logging.sink.invalid_result","local log sink returned a non-contract result")
            if not result.succeeded:return self._sink_failure(r,"logging.sink.write_failed",result.error_summary or "local log sink rejected record")
            self._records.append(canonical);self._accepted+=1;self._generation+=1
            error=self._transition(LoggingState.READY,r)
            if error:self._state=LoggingState.DEGRADED;return self._response(r,ResponseStatus.FAILED,(error,))
            explanation=self._explain(r,"Structured logging",f"recorded {canonical.record_id}",(f"category={canonical.category}",f"severity={canonical.severity.value}"),"succeeded")
            return self._response(r,ResponseStatus.SUCCEEDED,(),record=canonical,explanations=(explanation,),metadata={"recorded":True,"filtered":False})
    def query(self,r,filter=None):
        with self._lock:
            errors=self._validate_request(r)
            if errors:return self._response(r,ResponseStatus.REJECTED,errors)
            if self._state not in {LoggingState.READY,LoggingState.DEGRADED,LoggingState.STOPPED}:return self._invalid(r,"query")
            if filter is not None and not isinstance(filter,LogFilter):return self._rejection(r,"validation","logging.filter.invalid_contract","filter must use Logging contract")
            records=tuple(x for x in self._records if self._matches(x,filter or LogFilter()))
            snapshot=LoggingSnapshot(f"{r.correlation_id}:logging-snapshot:{self._generation}",self._generation,self._state,records,self._accepted,self._filtered,self._rejected,r.correlation_id)
            return self._response(r,ResponseStatus.SUCCEEDED,(),snapshot=snapshot)
    def format(self,r,filter=None):
        with self._lock:
            response=self.query(r,filter)
            if response.status is not ResponseStatus.SUCCEEDED:return response
            formatted=tuple(f"{x.sequence}|{x.severity.value}|{x.category}|{x.source_identity}|{x.correlation_id}|{x.message}" for x in response.snapshot.records)
            return self._response(r,ResponseStatus.SUCCEEDED,(),snapshot=response.snapshot,formatted_records=formatted)
    def stop(self,r):
        with self._lock:
            errors=self._validate_request(r)
            if errors:return self._response(r,ResponseStatus.REJECTED,errors)
            if self._state not in {LoggingState.READY,LoggingState.DEGRADED}:return self._invalid(r,"stop")
            error=self._transition(LoggingState.FLUSHING,r)
            if error:return self._response(r,ResponseStatus.FAILED,(error,))
            try:result=self._sink.flush()
            except Exception as exc:return self._sink_failure(r,"logging.sink.flush_exception","local log sink flush raised",type(exc).__name__)
            if not isinstance(result,SinkResult) or not result.succeeded:return self._sink_failure(r,"logging.sink.flush_failed",result.error_summary if isinstance(result,SinkResult) and result.error_summary else "local log sink flush failed")
            error=self._transition(LoggingState.STOPPED,r)
            if error:self._state=LoggingState.DEGRADED;return self._response(r,ResponseStatus.FAILED,(error,))
            return self._success(r,"Logging lifecycle","Logging flushed and stopped")
    def _matches(self,x,f):
        return (f.minimum_severity is None or SEVERITY_RANK[x.severity]>=SEVERITY_RANK[f.minimum_severity]) and (not f.categories or x.category in f.categories) and (not f.source_identities or x.source_identity in f.source_identities) and (f.correlation_id is None or x.correlation_id==f.correlation_id)
    def _validate_request(self,r):
        errors=[]
        for n in ("request_id","correlation_id","source_identity","target_capability","expectation"):
            if not self._text(getattr(r,n)):errors.append(self._error(r,"validation",f"logging.envelope.{n}",f"{n} must be non-empty"))
        if r.contract_id!=CONTRACT_ID:errors.append(self._error(r,"validation","logging.contract.identity","unsupported Logging contract identity"))
        try:major=int(r.contract_version.split(".",1)[0])
        except (ValueError,TypeError,AttributeError):major=-1
        if major!=1:errors.append(self._error(r,"unsupported_version","logging.contract.version","unsupported Logging contract version"))
        return tuple(errors)
    def _validate_policy(self,r):
        errors=[]
        if not isinstance(self._policy.minimum_severity,Severity):errors.append(self._error(r,"validation","logging.policy.severity","minimum severity must use Logging contract"))
        if self._policy.maximum_records<=0:errors.append(self._error(r,"validation","logging.policy.capacity","maximum_records must be positive"))
        if any(not self._text(x) for x in self._policy.allowed_categories) or len(set(self._policy.allowed_categories))!=len(self._policy.allowed_categories):errors.append(self._error(r,"validation","logging.policy.categories","allowed categories must be unique non-empty strings"))
        return tuple(errors)
    def _validate_entry(self,r,e):
        if not isinstance(e,LogInput):return (self._error(r,"validation","logging.record.invalid_contract","record must use Logging contract"),)
        errors=[]
        for n in ("source_identity","category","correlation_id","message"):
            if not self._text(getattr(e,n)):errors.append(self._error(r,"validation",f"logging.record.{n}",f"{n} must be non-empty"))
        try:self._severity(e.severity)
        except ValueError:errors.append(self._error(r,"validation","logging.record.severity","unsupported log severity"))
        if e.correlation_id!=r.correlation_id:errors.append(self._error(r,"validation","logging.record.correlation","record correlation must match request"))
        return tuple(errors)
    @staticmethod
    def _severity(v):
        if isinstance(v,Severity):return v
        normalized=str(v).strip().lower()
        if normalized=="warn":normalized="warning"
        return Severity(normalized)
    def _sink_failure(self,r,code,msg,exception_type=None):
        self._state=LoggingState.DEGRADED;context={} if exception_type is None else {"exception_type":exception_type};return self._response(r,ResponseStatus.FAILED,(self._error(r,"dependency_unavailable",code,msg,context),))
    def _transition(self,target,r):
        source=self._state
        if target not in _TRANSITIONS[source]:return self._error(r,"invalid_state","logging.lifecycle.invalid_transition",f"invalid transition: {source.value} -> {target.value}")
        self._state=target;self._explain(r,"Logging lifecycle",f"transitioned from {source.value} to {target.value}",(f"source={source.value}",f"target={target.value}"),"in_progress");return None
    def _success(self,r,subject,decision):return self._response(r,ResponseStatus.SUCCEEDED,(),explanations=(self._explain(r,subject,decision,(f"state={self._state.value}",),"succeeded"),))
    def _invalid(self,r,op):return self._rejection(r,"invalid_state",f"logging.{op}.invalid_state",f"{op} is invalid while Logging is {self._state.value}")
    def _rejection(self,r,cat,code,msg):self._rejected+=1;return self._response(r,ResponseStatus.REJECTED,(self._error(r,cat,code,msg),),explanations=(self._explain(r,"Logging request",msg,(code,),"rejected"),))
    def _response(self,r,status,errors,**payload):
        metadata={"terminal":True};metadata.update(payload.pop("metadata",{}));self._sequence+=1
        return LoggingResponse(response_id=f"{r.correlation_id}:logging-response:{self._sequence}",request_id=r.request_id,correlation_id=r.correlation_id,status=status,state=self._state,errors=tuple(errors),metadata=metadata,**payload)
    def _explain(self,r,subject,decision,facts,status):self._sequence+=1;record=ExplanationRecord(f"{r.correlation_id}:logging-explanation:{self._sequence}",ENGINE_ID,r.correlation_id,subject,decision,tuple(facts),status,{"request_id":r.request_id});self._explanations.append(record);return record
    @staticmethod
    def _text(v):return isinstance(v,str) and bool(v.strip())
    @staticmethod
    def _error(r,cat,code,msg,context=None):return LoggingError(cat,code,msg,r.request_id,r.correlation_id,False,context or {})
