"""Deterministic synchronous ENG-005 Event Bus."""
from __future__ import annotations
from threading import RLock
from typing import Any, Mapping
from .contracts import *

_TRANSITIONS = {
    EventBusState.CREATED:{EventBusState.STARTING}, EventBusState.STARTING:{EventBusState.ACCEPTING_EVENTS,EventBusState.FAILED},
    EventBusState.ACCEPTING_EVENTS:{EventBusState.DRAINING,EventBusState.DEGRADED,EventBusState.FAILED},
    EventBusState.DEGRADED:{EventBusState.DRAINING}, EventBusState.DRAINING:{EventBusState.STOPPED,EventBusState.FAILED},
    EventBusState.STOPPED:set(), EventBusState.FAILED:set(),
}

class EventBusEngine:
    def __init__(self, *, policy: EventBusPolicy|None=None, log_sink: LogSink|None=None):
        self._policy=policy or EventBusPolicy(); self._log_sink=log_sink or NullLogSink(); self._state=EventBusState.CREATED
        self._publishers={}; self._subscriptions={}; self._handlers={}; self._generation=0; self._delivery_count=0; self._sequence=0; self._explanations=[]; self._lock=RLock()
    @property
    def state(self):
        with self._lock: return self._state
    @property
    def explanations(self):
        with self._lock: return tuple(self._explanations)
    def start(self, request):
        with self._lock:
            errors=self._validate_request(request)
            if errors:return self._response(request,ResponseStatus.REJECTED,errors)
            if self._state is not EventBusState.CREATED:return self._invalid(request,"start")
            if any(v is not None and v<0 for v in (self._policy.maximum_publishers,self._policy.maximum_subscriptions)):
                self._state=EventBusState.FAILED; return self._failure(request,"validation","event_bus.policy.invalid_limit","Event Bus limits must not be negative")
            error=self._transition(EventBusState.STARTING,request) or self._transition(EventBusState.ACCEPTING_EVENTS,request)
            if error:self._state=EventBusState.FAILED; return self._response(request,ResponseStatus.FAILED,(error,))
            return self._success(request,"Event Bus lifecycle","Event Bus accepts events")
    def register_publisher(self,request,publisher):
        with self._lock:
            errors=list(self._validate_request(request))+list(self._validate_publisher(request,publisher))
            if errors:return self._response(request,ResponseStatus.REJECTED,errors)
            if self._state is not EventBusState.ACCEPTING_EVENTS:return self._invalid(request,"register_publisher")
            if publisher.publisher_id in self._publishers:return self._rejection(request,"conflict","event_bus.publisher.duplicate","publisher already registered")
            if self._policy.maximum_publishers is not None and len(self._publishers)>=self._policy.maximum_publishers:return self._rejection(request,"conflict","event_bus.publisher.capacity","publisher limit reached")
            self._publishers[publisher.publisher_id]=publisher; self._generation+=1
            return self._response(request,ResponseStatus.SUCCEEDED,(),publisher=publisher,explanations=(self._explain(request,"Publisher registration",f"registered {publisher.publisher_id}",(f"topics={len(publisher.topics)}",),"succeeded"),))
    def unregister_publisher(self,request,publisher_id):
        with self._lock:
            if (response:=self._preflight(request,"unregister_publisher")):return response
            publisher=self._publishers.get(publisher_id)
            if publisher is None:return self._rejection(request,"dependency_unavailable","event_bus.publisher.not_found","publisher is not registered")
            del self._publishers[publisher_id]; self._generation+=1
            return self._response(request,ResponseStatus.SUCCEEDED,(),publisher=publisher)
    def subscribe(self,request,subscription,handler):
        with self._lock:
            errors=list(self._validate_request(request))+list(self._validate_subscription(request,subscription))
            if not isinstance(handler,EventHandler):errors.append(self._error(request,"validation","event_bus.subscription.invalid_handler","handler must implement EventHandler"))
            if errors:return self._response(request,ResponseStatus.REJECTED,errors)
            if self._state is not EventBusState.ACCEPTING_EVENTS:return self._invalid(request,"subscribe")
            if subscription.subscription_id in self._subscriptions:return self._rejection(request,"conflict","event_bus.subscription.duplicate","subscription already exists")
            if self._policy.maximum_subscriptions is not None and len(self._subscriptions)>=self._policy.maximum_subscriptions:return self._rejection(request,"conflict","event_bus.subscription.capacity","subscription limit reached")
            self._subscriptions[subscription.subscription_id]=subscription; self._handlers[subscription.subscription_id]=handler; self._generation+=1
            return self._response(request,ResponseStatus.SUCCEEDED,(),subscription=subscription,explanations=(self._explain(request,"Subscription",f"subscribed {subscription.subscriber_id}",(f"topic={subscription.topic}",),"succeeded"),))
    def unsubscribe(self,request,subscription_id):
        with self._lock:
            if (response:=self._preflight(request,"unsubscribe")):return response
            subscription=self._subscriptions.get(subscription_id)
            if subscription is None:return self._rejection(request,"dependency_unavailable","event_bus.subscription.not_found","subscription does not exist")
            del self._subscriptions[subscription_id]; del self._handlers[subscription_id]; self._generation+=1
            return self._response(request,ResponseStatus.SUCCEEDED,(),subscription=subscription)
    def publish(self,request,event):
        with self._lock:
            errors=list(self._validate_request(request))+list(self._validate_event(request,event))
            if errors:return self._response(request,ResponseStatus.REJECTED,errors)
            if self._state is not EventBusState.ACCEPTING_EVENTS:return self._invalid(request,"publish")
            publisher=self._publishers.get(event.publisher_id)
            if publisher is None:return self._rejection(request,"dependency_unavailable","event_bus.publish.publisher_unknown","event publisher is not registered")
            if event.topic not in publisher.topics:return self._rejection(request,"authorization","event_bus.publish.topic_not_authorized","publisher is not registered for this topic")
            matches=[(sid,sub) for sid,sub in sorted(self._subscriptions.items()) if sub.topic==event.topic]
            outcomes=[]; errors=[]
            for sid,sub in matches:
                try: result=self._handlers[sid].deliver(event)
                except Exception as exc:
                    outcomes.append(DeliveryOutcome(sid,sub.subscriber_id,False,"handler raised")); errors.append(self._error(request,"dependency_unavailable","event_bus.delivery.handler_exception","subscriber handler raised",{"subscription_id":sid,"exception_type":type(exc).__name__})); continue
                if not isinstance(result,DeliveryResult):
                    outcomes.append(DeliveryOutcome(sid,sub.subscriber_id,False,"invalid result")); errors.append(self._error(request,"validation","event_bus.delivery.invalid_result","subscriber returned a non-contract result",{"subscription_id":sid}))
                elif result.succeeded: outcomes.append(DeliveryOutcome(sid,sub.subscriber_id,True))
                else:
                    outcomes.append(DeliveryOutcome(sid,sub.subscriber_id,False,result.error_summary)); errors.append(self._error(request,"processing_failure","event_bus.delivery.rejected",result.error_summary or "subscriber rejected delivery",{"subscription_id":sid}))
            self._delivery_count+=1
            delivery=EventDelivery(f"{event.event_id}:delivery:{self._delivery_count}",event.event_id,event.topic,tuple(outcomes),event.correlation_id)
            status=ResponseStatus.SUCCEEDED if not errors else (ResponseStatus.PARTIAL if any(o.succeeded for o in outcomes) else ResponseStatus.FAILED)
            explanation=self._explain(request,"Event delivery",f"routed event {event.event_id}",(f"topic={event.topic}",f"deliveries={len(outcomes)}",f"failures={len(errors)}"),status.value)
            return self._response(request,status,errors,delivery=delivery,explanations=(explanation,))
    def snapshot(self,request):
        with self._lock:
            if (response:=self._preflight(request,"snapshot")):return response
            snapshot=EventBusSnapshot(f"{request.correlation_id}:event-bus-snapshot:{self._generation}",self._generation,self._state,self._publishers,self._subscriptions,self._delivery_count,request.correlation_id)
            return self._response(request,ResponseStatus.SUCCEEDED,(),snapshot=snapshot)
    def stop(self,request):
        with self._lock:
            errors=self._validate_request(request)
            if errors:return self._response(request,ResponseStatus.REJECTED,errors)
            if self._state not in {EventBusState.ACCEPTING_EVENTS,EventBusState.DEGRADED}:return self._invalid(request,"stop")
            error=self._transition(EventBusState.DRAINING,request)
            if error:return self._response(request,ResponseStatus.FAILED,(error,))
            self._subscriptions.clear(); self._handlers.clear(); self._publishers.clear(); self._generation+=1
            error=self._transition(EventBusState.STOPPED,request)
            if error:self._state=EventBusState.FAILED; return self._response(request,ResponseStatus.FAILED,(error,))
            return self._success(request,"Event Bus lifecycle","Event Bus drained and stopped")
    def _preflight(self,request,operation):
        errors=self._validate_request(request)
        if errors:return self._response(request,ResponseStatus.REJECTED,errors)
        if self._state is not EventBusState.ACCEPTING_EVENTS:return self._invalid(request,operation)
        return None
    def _validate_request(self,r):
        errors=[]
        for name in ("request_id","correlation_id","source_identity","target_capability","expectation"):
            if not isinstance(getattr(r,name),str) or not getattr(r,name).strip():errors.append(self._error(r,"validation",f"event_bus.envelope.{name}",f"{name} must be non-empty"))
        if r.contract_id!=CONTRACT_ID:errors.append(self._error(r,"validation","event_bus.contract.identity","unsupported contract identity"))
        try:major=int(r.contract_version.split(".",1)[0])
        except (ValueError,TypeError,AttributeError):major=-1
        if major!=1:errors.append(self._error(r,"unsupported_version","event_bus.contract.version","unsupported contract version"))
        return tuple(errors)
    def _validate_publisher(self,r,p):
        if not isinstance(p,PublisherRegistration):return (self._error(r,"validation","event_bus.publisher.invalid_contract","publisher must use public contract"),)
        errors=[]
        if not p.publisher_id.strip():errors.append(self._error(r,"validation","event_bus.publisher.identity","publisher_id must be non-empty"))
        if not p.topics or any(not isinstance(t,str) or not t.strip() for t in p.topics):errors.append(self._error(r,"validation","event_bus.publisher.topics","publisher requires non-empty topics"))
        if len(p.topics)!=len(set(p.topics)):errors.append(self._error(r,"validation","event_bus.publisher.duplicate_topic","publisher topics must be unique"))
        return tuple(errors)
    def _validate_subscription(self,r,s):
        if not isinstance(s,Subscription):return (self._error(r,"validation","event_bus.subscription.invalid_contract","subscription must use public contract"),)
        return tuple(self._error(r,"validation",f"event_bus.subscription.{n}",f"{n} must be non-empty") for n in ("subscription_id","subscriber_id","topic") if not isinstance(getattr(s,n),str) or not getattr(s,n).strip())
    def _validate_event(self,r,e):
        if not isinstance(e,PlatformEvent):return (self._error(r,"validation","event_bus.event.invalid_contract","event must use public contract"),)
        errors=[]
        for n in ("event_id","topic","publisher_id","correlation_id"):
            if not isinstance(getattr(e,n),str) or not getattr(e,n).strip():errors.append(self._error(r,"validation",f"event_bus.event.{n}",f"{n} must be non-empty"))
        if e.correlation_id!=r.correlation_id:errors.append(self._error(r,"validation","event_bus.event.correlation_mismatch","event correlation must match request"))
        try:major=int(e.event_version.split(".",1)[0])
        except (ValueError,TypeError,AttributeError):major=-1
        if major!=1:errors.append(self._error(r,"unsupported_version","event_bus.event.version","unsupported event version"))
        return tuple(errors)
    def _transition(self,target,r):
        source=self._state
        if target not in _TRANSITIONS[source]:return self._error(r,"invalid_state","event_bus.lifecycle.invalid_transition",f"invalid transition: {source.value} -> {target.value}")
        error=self._log(r,"lifecycle","info",f"Event Bus transitioning from {source.value} to {target.value}",{"source":source.value,"target":target.value})
        if error:return error
        self._state=target; self._explain(r,"Event Bus lifecycle",f"transitioned from {source.value} to {target.value}",(f"source={source.value}",f"target={target.value}"),"in_progress"); return None
    def _success(self,r,subject,decision):return self._response(r,ResponseStatus.SUCCEEDED,(),explanations=(self._explain(r,subject,decision,(f"state={self._state.value}",),"succeeded"),))
    def _invalid(self,r,op):return self._rejection(r,"invalid_state",f"event_bus.{op}.invalid_state",f"{op} is invalid while Event Bus is {self._state.value}")
    def _rejection(self,r,cat,code,msg):return self._response(r,ResponseStatus.REJECTED,(self._error(r,cat,code,msg),),explanations=(self._explain(r,"Event Bus request",msg,(code,),"rejected"),))
    def _failure(self,r,cat,code,msg):return self._response(r,ResponseStatus.FAILED,(self._error(r,cat,code,msg),))
    def _response(self,r,status,errors,**payload):
        collected=list(errors); log_error=self._log(r,"operation_outcome","info" if status is ResponseStatus.SUCCEEDED else "warning",f"Event Bus request completed with status {status.value}",{"status":status.value,"state":self._state.value})
        if log_error and not any(e.code==log_error.code for e in collected):collected.append(log_error);status=ResponseStatus.FAILED
        self._sequence+=1; return EventBusResponse(response_id=f"{r.correlation_id}:event-bus-response:{self._sequence}",request_id=r.request_id,correlation_id=r.correlation_id,status=status,state=self._state,errors=tuple(collected),metadata={"terminal":True},**payload)
    def _explain(self,r,subject,decision,facts,status):
        self._sequence+=1; record=ExplanationRecord(f"{r.correlation_id}:event-bus-explanation:{self._sequence}",ENGINE_ID,r.correlation_id,subject,decision,tuple(facts),status,{"request_id":r.request_id});self._explanations.append(record);return record
    def _log(self,r,category,severity,message,metadata):
        try:self._log_sink.record(LogRecord(ENGINE_ID,category,severity,r.correlation_id,message,metadata))
        except Exception as exc:return self._error(r,"dependency_unavailable","event_bus.logging.delivery_failed","logging capability rejected a record",{"exception_type":type(exc).__name__})
        return None
    @staticmethod
    def _error(r,cat,code,msg,context=None):return EventBusError(cat,code,msg,r.request_id,r.correlation_id,False,context or {})
