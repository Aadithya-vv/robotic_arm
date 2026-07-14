"""Thread-safe temporary runtime memory for ENG-006."""
from __future__ import annotations
from threading import RLock
from typing import Any,Mapping
from .contracts import *

_TRANSITIONS={MemoryState.CREATED:{MemoryState.READY,MemoryState.FAILED},MemoryState.READY:{MemoryState.ACTIVE,MemoryState.CLEANING,MemoryState.DISPOSED},MemoryState.ACTIVE:{MemoryState.READY,MemoryState.FAILED},MemoryState.CLEANING:{MemoryState.READY,MemoryState.FAILED},MemoryState.DISPOSED:set(),MemoryState.FAILED:set()}
class MemoryEngine:
    def __init__(self,*,policy:MemoryPolicy|None=None,log_sink:LogSink|None=None):
        self._policy=policy or MemoryPolicy();self._log_sink=log_sink or NullLogSink();self._state=MemoryState.CREATED;self._sessions={};self._owners={};self._session_generations={};self._generation=0;self._sequence=0;self._explanations=[];self._lock=RLock()
    @property
    def state(self):
        with self._lock:return self._state
    @property
    def explanations(self):
        with self._lock:return tuple(self._explanations)
    def initialize(self,r):
        with self._lock:
            if (response:=self._validate_or_state(r,MemoryState.CREATED,"initialize",check_state=False)):return response
            if self._state is not MemoryState.CREATED:return self._invalid(r,"initialize")
            if any(v is not None and v<0 for v in (self._policy.maximum_sessions,self._policy.maximum_entries_per_session)):
                self._state=MemoryState.FAILED;return self._failure(r,"validation","memory.policy.invalid_limit","Memory limits must not be negative")
            error=self._transition(MemoryState.READY,r)
            if error:self._state=MemoryState.FAILED;return self._response(r,ResponseStatus.FAILED,(error,))
            return self._success(r,"Memory lifecycle","Memory is ready")
    def create_session(self,r,session_id,owner_id):
        with self._lock:
            if (response:=self._preflight(r,"create_session")):return response
            if not self._text(session_id) or not self._text(owner_id):return self._rejection(r,"validation","memory.session.invalid_identity","session_id and owner_id must be non-empty")
            if owner_id!=r.source_identity:return self._rejection(r,"authorization","memory.session.owner_mismatch","session owner must match requesting identity")
            if session_id in self._sessions:return self._rejection(r,"conflict","memory.session.duplicate","session already exists")
            if self._policy.maximum_sessions is not None and len(self._sessions)>=self._policy.maximum_sessions:return self._rejection(r,"conflict","memory.session.capacity","session limit reached")
            if (error:=self._begin(r)):return self._response(r,ResponseStatus.FAILED,(error,))
            self._sessions[session_id]={};self._owners[session_id]=owner_id;self._session_generations[session_id]=0;self._generation+=1
            if (error:=self._end(r)):return self._response(r,ResponseStatus.FAILED,(error,))
            session=self._session_snapshot(r,session_id);return self._response(r,ResponseStatus.SUCCEEDED,(),session=session,explanations=(self._explain(r,"Working memory",f"created session {session_id}",(f"owner={owner_id}",),"succeeded"),))
    def put(self,r,session_id,key,value,visibility=Visibility.OWNER,provenance=None):
        with self._lock:
            if (response:=self._preflight(r,"put")):return response
            if (response:=self._session_access(r,session_id,write=True)):return response
            if not self._text(key):return self._rejection(r,"validation","memory.record.invalid_key","memory key must be non-empty")
            if not isinstance(visibility,Visibility):return self._rejection(r,"validation","memory.record.invalid_visibility","visibility must use Memory contract")
            if not self._immutable_value(value):return self._rejection(r,"validation","memory.record.unsupported_value","value cannot be represented as immutable runtime memory")
            entries=self._sessions[session_id];limit=self._policy.maximum_entries_per_session
            if key not in entries and limit is not None and len(entries)>=limit:return self._rejection(r,"conflict","memory.record.capacity","session entry limit reached")
            if (error:=self._begin(r)):return self._response(r,ResponseStatus.FAILED,(error,))
            revision=entries[key].revision+1 if key in entries else 1;record=MemoryRecord(f"{session_id}:{key}:{revision}",session_id,key,self._owners[session_id],value,visibility,revision,r.correlation_id,provenance or {});entries[key]=record;self._mutated(session_id)
            if (error:=self._end(r)):return self._response(r,ResponseStatus.FAILED,(error,))
            return self._response(r,ResponseStatus.SUCCEEDED,(),record=record,explanations=(self._explain(r,"Runtime memory",f"stored {key}",(f"session={session_id}",f"revision={revision}"),"succeeded"),))
    def get(self,r,session_id,key):
        with self._lock:
            if (response:=self._preflight(r,"get")):return response
            if not self._text(key):return self._rejection(r,"validation","memory.record.invalid_key","memory key must be non-empty")
            if session_id not in self._sessions:return self._rejection(r,"dependency_unavailable","memory.session.not_found","session does not exist")
            record=self._sessions[session_id].get(key)
            if record is None:return self._rejection(r,"dependency_unavailable","memory.record.not_found","memory record does not exist")
            if record.owner_id!=r.source_identity and record.visibility is not Visibility.SHARED:return self._rejection(r,"authorization","memory.record.not_accessible","record is owner-only")
            if (error:=self._begin(r)):return self._response(r,ResponseStatus.FAILED,(error,))
            if (error:=self._end(r)):return self._response(r,ResponseStatus.FAILED,(error,))
            return self._response(r,ResponseStatus.SUCCEEDED,(),record=record)
    def delete(self,r,session_id,key):
        with self._lock:
            if (response:=self._preflight(r,"delete")):return response
            if (response:=self._session_access(r,session_id,write=True)):return response
            record=self._sessions[session_id].get(key)
            if record is None:return self._rejection(r,"dependency_unavailable","memory.record.not_found","memory record does not exist")
            if (error:=self._begin(r)):return self._response(r,ResponseStatus.FAILED,(error,))
            del self._sessions[session_id][key];self._mutated(session_id)
            if (error:=self._end(r)):return self._response(r,ResponseStatus.FAILED,(error,))
            return self._response(r,ResponseStatus.SUCCEEDED,(),record=record)
    def cleanup_session(self,r,session_id):
        with self._lock:
            if (response:=self._preflight(r,"cleanup_session")):return response
            if (response:=self._session_access(r,session_id,write=True)):return response
            error=self._transition(MemoryState.CLEANING,r)
            if error:return self._response(r,ResponseStatus.FAILED,(error,))
            self._sessions[session_id].clear();self._mutated(session_id);error=self._transition(MemoryState.READY,r)
            if error:self._state=MemoryState.FAILED;return self._response(r,ResponseStatus.FAILED,(error,))
            return self._success(r,"Memory cleanup",f"cleared session {session_id}")
    def close_session(self,r,session_id):
        with self._lock:
            if (response:=self._preflight(r,"close_session")):return response
            if (response:=self._session_access(r,session_id,write=True)):return response
            error=self._transition(MemoryState.CLEANING,r)
            if error:return self._response(r,ResponseStatus.FAILED,(error,))
            snapshot=self._session_snapshot(r,session_id,SessionState.CLOSED);del self._sessions[session_id];del self._owners[session_id];del self._session_generations[session_id];self._generation+=1;error=self._transition(MemoryState.READY,r)
            if error:self._state=MemoryState.FAILED;return self._response(r,ResponseStatus.FAILED,(error,))
            return self._response(r,ResponseStatus.SUCCEEDED,(),session=snapshot)
    def snapshot(self,r,session_id=None):
        with self._lock:
            if (response:=self._preflight(r,"snapshot")):return response
            if session_id is not None:
                if (response:=self._session_access(r,session_id,write=True)):return response
                return self._response(r,ResponseStatus.SUCCEEDED,(),session=self._session_snapshot(r,session_id))
            visible={sid:self._session_snapshot(r,sid) for sid in sorted(self._sessions) if self._owners[sid]==r.source_identity}
            snap=MemorySnapshot(f"{r.correlation_id}:memory-snapshot:{self._generation}",self._generation,self._state,visible,r.correlation_id);return self._response(r,ResponseStatus.SUCCEEDED,(),snapshot=snap)
    def dispose(self,r):
        with self._lock:
            if (response:=self._preflight(r,"dispose")):return response
            self._sessions.clear();self._owners.clear();self._session_generations.clear();self._generation+=1;error=self._transition(MemoryState.DISPOSED,r)
            if error:return self._response(r,ResponseStatus.FAILED,(error,))
            return self._success(r,"Memory lifecycle","disposed all temporary memory")
    def _preflight(self,r,op):
        errors=self._validate_request(r)
        if errors:return self._response(r,ResponseStatus.REJECTED,errors)
        if self._state is not MemoryState.READY:return self._invalid(r,op)
        return None
    def _validate_or_state(self,r,*args,**kwargs):
        errors=self._validate_request(r);return self._response(r,ResponseStatus.REJECTED,errors) if errors else None
    def _validate_request(self,r):
        errors=[]
        for name in ("request_id","correlation_id","source_identity","target_capability","expectation"):
            if not self._text(getattr(r,name)):errors.append(self._error(r,"validation",f"memory.envelope.{name}",f"{name} must be non-empty"))
        if r.contract_id!=CONTRACT_ID:errors.append(self._error(r,"validation","memory.contract.identity","unsupported Memory contract identity"))
        try:major=int(r.contract_version.split(".",1)[0])
        except (ValueError,TypeError,AttributeError):major=-1
        if major!=1:errors.append(self._error(r,"unsupported_version","memory.contract.version","unsupported Memory contract version"))
        return tuple(errors)
    def _session_access(self,r,sid,write=False):
        if sid not in self._sessions:return self._rejection(r,"dependency_unavailable","memory.session.not_found","session does not exist")
        if write and self._owners[sid]!=r.source_identity:return self._rejection(r,"authorization","memory.session.not_owner","only the session owner may mutate or snapshot it")
        return None
    def _begin(self,r):
        error=self._transition(MemoryState.ACTIVE,r)
        if error:self._state=MemoryState.FAILED
        return error
    def _end(self,r):
        error=self._transition(MemoryState.READY,r)
        if error:self._state=MemoryState.FAILED
        return error
    def _mutated(self,sid):self._session_generations[sid]+=1;self._generation+=1
    def _session_snapshot(self,r,sid,state=SessionState.OPEN):return SessionSnapshot(f"{r.correlation_id}:{sid}:snapshot:{self._session_generations[sid]}",sid,self._owners[sid],state,self._session_generations[sid],self._sessions[sid],r.correlation_id)
    @classmethod
    def _immutable_value(cls,v):
        if v is None or isinstance(v,(str,int,float,bool,bytes)):return True
        if isinstance(v,Mapping):return all(isinstance(k,str) and cls._immutable_value(x) for k,x in v.items())
        if isinstance(v,(list,tuple,set,frozenset)):return all(cls._immutable_value(x) for x in v)
        return False
    @staticmethod
    def _text(v):return isinstance(v,str) and bool(v.strip())
    def _transition(self,target,r):
        source=self._state
        if target not in _TRANSITIONS[source]:return self._error(r,"invalid_state","memory.lifecycle.invalid_transition",f"invalid transition: {source.value} -> {target.value}")
        error=self._log(r,"lifecycle","info",f"Memory transitioning from {source.value} to {target.value}",{"source":source.value,"target":target.value})
        if error:return error
        self._state=target;self._explain(r,"Memory lifecycle",f"transitioned from {source.value} to {target.value}",(f"source={source.value}",f"target={target.value}"),"in_progress");return None
    def _success(self,r,subject,decision):return self._response(r,ResponseStatus.SUCCEEDED,(),explanations=(self._explain(r,subject,decision,(f"state={self._state.value}",),"succeeded"),))
    def _invalid(self,r,op):return self._rejection(r,"invalid_state",f"memory.{op}.invalid_state",f"{op} is invalid while Memory is {self._state.value}")
    def _rejection(self,r,cat,code,msg):return self._response(r,ResponseStatus.REJECTED,(self._error(r,cat,code,msg),),explanations=(self._explain(r,"Memory request",msg,(code,),"rejected"),))
    def _failure(self,r,cat,code,msg):return self._response(r,ResponseStatus.FAILED,(self._error(r,cat,code,msg),))
    def _response(self,r,status,errors,**payload):
        collected=list(errors);log_error=self._log(r,"operation_outcome","info" if status is ResponseStatus.SUCCEEDED else "warning",f"Memory request completed with status {status.value}",{"status":status.value,"state":self._state.value})
        if log_error and not any(e.code==log_error.code for e in collected):collected.append(log_error);status=ResponseStatus.FAILED
        self._sequence+=1;return MemoryResponse(response_id=f"{r.correlation_id}:memory-response:{self._sequence}",request_id=r.request_id,correlation_id=r.correlation_id,status=status,state=self._state,errors=tuple(collected),metadata={"terminal":True},**payload)
    def _explain(self,r,subject,decision,facts,status):
        self._sequence+=1;record=ExplanationRecord(f"{r.correlation_id}:memory-explanation:{self._sequence}",ENGINE_ID,r.correlation_id,subject,decision,tuple(facts),status,{"request_id":r.request_id});self._explanations.append(record);return record
    def _log(self,r,category,severity,message,metadata):
        try:self._log_sink.record(LogRecord(ENGINE_ID,category,severity,r.correlation_id,message,metadata))
        except Exception as exc:return self._error(r,"dependency_unavailable","memory.logging.delivery_failed","logging capability rejected a record",{"exception_type":type(exc).__name__})
        return None
    @staticmethod
    def _error(r,cat,code,msg,context=None):return MemoryError(cat,code,msg,r.request_id,r.correlation_id,False,context or {})
