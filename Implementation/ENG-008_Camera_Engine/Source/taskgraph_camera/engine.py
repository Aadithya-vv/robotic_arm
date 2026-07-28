"""Thread-safe provider-driven ENG-008 Camera Engine."""
from __future__ import annotations
from threading import RLock
from typing import Mapping,Any
from .contracts import *
from .providers import CameraProviderCatalog
_TRANSITIONS={CameraState.CLOSED:{CameraState.OPENING},CameraState.OPENING:{CameraState.READY,CameraState.FAILED},CameraState.READY:{CameraState.CAPTURING,CameraState.CLOSING,CameraState.FAILED},CameraState.CAPTURING:{CameraState.READY,CameraState.FAILED},CameraState.FAILED:{CameraState.CLOSING},CameraState.CLOSING:{CameraState.CLOSED,CameraState.FAILED}}
class CameraEngine:
    def __init__(self,providers=None,*,log_sink=None):self._catalog=providers if isinstance(providers,CameraProviderCatalog) else (CameraProviderCatalog.default() if providers is None else CameraProviderCatalog(providers));self._log=log_sink or NullLogSink();self._state=CameraState.CLOSED;self._provider=None;self._configuration=None;self._frames=0;self._sequence=0;self._last_error=None;self._explanations=[];self._lock=RLock()
    @property
    def state(self):
        with self._lock:return self._state
    @property
    def explanations(self):
        with self._lock:return tuple(self._explanations)
    def discover(self,r):
        with self._lock:
            errors=self._validate_request(r)
            if errors:return self._response(r,ResponseStatus.REJECTED,errors)
            if self._state is not CameraState.CLOSED:return self._invalid(r,"discover")
            if self._catalog.errors:return self._failure(r,"validation","camera.provider.catalog_invalid","; ".join(self._catalog.errors))
            devices=[];provider_errors=[]
            for provider_id in self._catalog.provider_ids:
                provider=self._catalog.get(provider_id)
                try:result=provider.discover()
                except Exception as exc:provider_errors.append(self._error(r,"dependency_unavailable","camera.discovery.provider_exception",f"provider discovery raised: {provider_id}",{"exception_type":type(exc).__name__}));continue
                if not isinstance(result,ProviderDiscovery):provider_errors.append(self._error(r,"validation","camera.discovery.invalid_result",f"provider returned invalid discovery: {provider_id}"))
                elif result.succeeded:devices.extend(result.devices)
                else:provider_errors.append(self._error(r,"dependency_unavailable",result.error_code or "camera.discovery.failed",result.error_summary or "provider discovery failed",{"provider_id":provider_id}))
            if not devices and provider_errors:return self._response(r,ResponseStatus.FAILED,provider_errors)
            explanation=self._explain(r,"Camera discovery",f"discovered {len(devices)} camera devices",tuple(x.device_id for x in devices),"succeeded")
            return self._response(r,ResponseStatus.SUCCEEDED,(),devices=tuple(devices),explanations=(explanation,),metadata={"provider_warnings":tuple(e.code for e in provider_errors)})
    def initialize(self,r,configuration):
        with self._lock:
            errors=list(self._validate_request(r))+list(self._validate_configuration(r,configuration))
            if errors:return self._response(r,ResponseStatus.REJECTED,errors)
            if self._state is not CameraState.CLOSED:return self._invalid(r,"initialize")
            if self._catalog.errors:return self._failure(r,"validation","camera.provider.catalog_invalid","; ".join(self._catalog.errors))
            provider=self._catalog.get(configuration.provider_id)
            if provider is None:return self._rejection(r,"dependency_unavailable","camera.provider.not_found",f"camera provider unavailable: {configuration.provider_id}")
            error=self._transition(CameraState.OPENING,r)
            if error:return self._failed(r,error)
            try:result=provider.open(configuration)
            except Exception as exc:return self._failed(r,self._error(r,"dependency_unavailable","camera.provider.open_exception","camera provider raised during open",{"exception_type":type(exc).__name__}))
            if not isinstance(result,ProviderResult):return self._failed(r,self._error(r,"validation","camera.provider.open_invalid_result","camera provider returned invalid open result"))
            if not result.succeeded:return self._failed(r,self._error(r,"dependency_unavailable",result.error_code or "camera.connection.failed",result.error_summary or "camera connection failed"))
            self._provider=provider;self._configuration=configuration;self._frames=0;error=self._transition(CameraState.READY,r)
            if error:return self._failed(r,error)
            return self._success(r,"Camera initialization",f"connected {configuration.device_id}")
    def acquire(self,r):
        with self._lock:
            errors=self._validate_request(r)
            if errors:return self._response(r,ResponseStatus.REJECTED,errors)
            if self._state is not CameraState.READY:return self._invalid(r,"acquire")
            error=self._transition(CameraState.CAPTURING,r)
            if error:return self._failed(r,error)
            try:result=self._provider.acquire()
            except Exception as exc:return self._failed(r,self._error(r,"processing_failure","camera.capture.provider_exception","camera provider raised during acquisition",{"exception_type":type(exc).__name__}))
            if not isinstance(result,ProviderFrame):return self._failed(r,self._error(r,"validation","camera.capture.invalid_result","camera provider returned invalid frame result"))
            if not result.succeeded:return self._failed(r,self._error(r,"processing_failure",result.error_code or "camera.capture.failed",result.error_summary or "frame acquisition failed"))
            if not result.data or result.width<=0 or result.height<=0 or result.channels<=0:return self._failed(r,self._error(r,"validation","camera.capture.invalid_frame","provider frame dimensions and data must be valid"))
            self._frames+=1;observation=CameraObservation(f"{r.correlation_id}:camera-observation:{self._frames}",self._frames,self._configuration.device_id,self._provider.provider_id,r.correlation_id,result.data,result.width,result.height,result.channels,result.pixel_format,result.timestamp_context,result.metadata)
            error=self._transition(CameraState.READY,r)
            if error:return self._failed(r,error)
            explanation=self._explain(r,"Frame acquisition",f"captured observation {observation.observation_id}",(f"sequence={observation.sequence}",f"dimensions={observation.width}x{observation.height}"),"succeeded")
            return self._response(r,ResponseStatus.SUCCEEDED,(),observation=observation,explanations=(explanation,))
    def diagnostics(self,r):
        with self._lock:
            errors=self._validate_request(r)
            if errors:return self._response(r,ResponseStatus.REJECTED,errors)
            provider_data={}
            if self._provider is not None:
                try:provider_data=dict(self._provider.diagnostics())
                except Exception as exc:return self._failure(r,"dependency_unavailable","camera.diagnostics.provider_exception","provider diagnostics raised",{"exception_type":type(exc).__name__})
            value=CameraDiagnostics(self._state,None if self._provider is None else self._provider.provider_id,None if self._configuration is None else self._configuration.device_id,self._frames,provider_data,self._last_error)
            return self._response(r,ResponseStatus.SUCCEEDED,(),diagnostics=value)
    def shutdown(self,r):
        with self._lock:
            errors=self._validate_request(r)
            if errors:return self._response(r,ResponseStatus.REJECTED,errors)
            if self._state not in {CameraState.READY,CameraState.FAILED}:return self._invalid(r,"shutdown")
            error=self._transition(CameraState.CLOSING,r)
            if error:return self._response(r,ResponseStatus.FAILED,(error,))
            if self._provider is not None:
                try:result=self._provider.close()
                except Exception as exc:self._state=CameraState.FAILED;return self._failure(r,"dependency_unavailable","camera.provider.close_exception","provider close raised",{"exception_type":type(exc).__name__})
                if not isinstance(result,ProviderResult) or not result.succeeded:self._state=CameraState.FAILED;return self._failure(r,"dependency_unavailable","camera.provider.close_failed","provider close failed")
            self._provider=None;self._configuration=None;error=self._transition(CameraState.CLOSED,r)
            if error:self._state=CameraState.FAILED;return self._response(r,ResponseStatus.FAILED,(error,))
            return self._success(r,"Camera shutdown","camera resources released")
    def _validate_request(self,r):
        errors=[]
        for n in ("request_id","correlation_id","source_identity","target_capability","expectation"):
            if not isinstance(getattr(r,n),str) or not getattr(r,n).strip():errors.append(self._error(r,"validation",f"camera.envelope.{n}",f"{n} must be non-empty"))
        if r.contract_id!=CONTRACT_ID:errors.append(self._error(r,"validation","camera.contract.identity","unsupported Camera contract identity"))
        try:major=int(r.contract_version.split(".",1)[0])
        except (ValueError,TypeError,AttributeError):major=-1
        if major!=1:errors.append(self._error(r,"unsupported_version","camera.contract.version","unsupported Camera contract version"))
        return tuple(errors)
    def _validate_configuration(self,r,c):
        if not isinstance(c,CameraConfiguration):return (self._error(r,"validation","camera.configuration.invalid_contract","configuration must use Camera contract"),)
        errors=[]
        for n in ("provider_id","device_id","pixel_format"):
            if not isinstance(getattr(c,n),str) or not getattr(c,n).strip():errors.append(self._error(r,"validation",f"camera.configuration.{n}",f"{n} must be non-empty"))
        for n in ("width","height","frames_per_second"):
            if not isinstance(getattr(c,n),int) or isinstance(getattr(c,n),bool) or getattr(c,n)<=0:errors.append(self._error(r,"validation",f"camera.configuration.{n}",f"{n} must be a positive integer"))
        return tuple(errors)
    def _transition(self,target,r):
        source=self._state
        if target not in _TRANSITIONS[source]:return self._error(r,"invalid_state","camera.lifecycle.invalid_transition",f"invalid transition: {source.value} -> {target.value}")
        log_error=self._write_log(r,"lifecycle","info",f"Camera transitioning from {source.value} to {target.value}",{"source":source.value,"target":target.value})
        if log_error:return log_error
        self._state=target;self._explain(r,"Camera lifecycle",f"transitioned from {source.value} to {target.value}",(f"source={source.value}",f"target={target.value}"),"in_progress");return None
    def _failed(self,r,error):self._last_error=error.code;self._state=CameraState.FAILED;return self._response(r,ResponseStatus.FAILED,(error,),explanations=(self._explain(r,"Camera operation","camera entered failed state",(error.code,),"failed"),))
    def _success(self,r,subject,decision):return self._response(r,ResponseStatus.SUCCEEDED,(),explanations=(self._explain(r,subject,decision,(f"state={self._state.value}",),"succeeded"),))
    def _invalid(self,r,op):return self._rejection(r,"invalid_state",f"camera.{op}.invalid_state",f"{op} is invalid while Camera is {self._state.value}")
    def _rejection(self,r,cat,code,msg):return self._response(r,ResponseStatus.REJECTED,(self._error(r,cat,code,msg),),explanations=(self._explain(r,"Camera request",msg,(code,),"rejected"),))
    def _failure(self,r,cat,code,msg,context=None):return self._response(r,ResponseStatus.FAILED,(self._error(r,cat,code,msg,context),))
    def _response(self,r,status,errors,**payload):
        metadata={"terminal":True};metadata.update(payload.pop("metadata",{}));log_error=self._write_log(r,"operation_outcome","info" if status is ResponseStatus.SUCCEEDED else "warning",f"Camera request completed with status {status.value}",{"status":status.value,"state":self._state.value});collected=list(errors)
        if log_error and not any(x.code==log_error.code for x in collected):collected.append(log_error);status=ResponseStatus.FAILED
        self._sequence+=1;return CameraResponse(response_id=f"{r.correlation_id}:camera-response:{self._sequence}",request_id=r.request_id,correlation_id=r.correlation_id,status=status,state=self._state,errors=tuple(collected),metadata=metadata,**payload)
    def _explain(self,r,subject,decision,facts,status):self._sequence+=1;value=ExplanationRecord(f"{r.correlation_id}:camera-explanation:{self._sequence}",ENGINE_ID,r.correlation_id,subject,decision,tuple(facts),status,{"request_id":r.request_id});self._explanations.append(value);return value
    def _write_log(self,r,category,severity,message,metadata):
        try:self._log.record(LogRecord(ENGINE_ID,category,severity,r.correlation_id,message,metadata))
        except Exception as exc:return self._error(r,"dependency_unavailable","camera.logging.delivery_failed","logging capability rejected Camera record",{"exception_type":type(exc).__name__})
        return None
    @staticmethod
    def _error(r,cat,code,msg,context=None):return CameraError(cat,code,msg,r.request_id,r.correlation_id,False,context or {})
