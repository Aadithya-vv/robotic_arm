from __future__ import annotations
import hashlib,json,re
from datetime import datetime,timezone
from threading import RLock
from .contracts import *
from .rules import rule_for
class SemanticPlannerEngine:
    def __init__(self,knowledge_source,affordance_source,storage,configuration=None,clock=None,log_sink=None):
        if not isinstance(knowledge_source,KnowledgeSource) or not isinstance(affordance_source,AffordanceSource):raise TypeError("invalid planner source")
        if not isinstance(storage,SemanticPlanStorage):raise TypeError("invalid planner storage")
        self._knowledge,self._affordances,self._storage=knowledge_source,affordance_source,storage;self._configuration=configuration or PlannerConfiguration();self._clock=clock or (lambda:datetime.now(timezone.utc).isoformat());self._state=PlannerState.EMPTY;self._plans={};self._lock=RLock()
    @property
    def state(self):return self._state
    def initialize(self,r):
        with self._lock:
            if self._state is not PlannerState.EMPTY:return self._invalid(r,"initialize")
            try:
                payload=self._storage.load() or {"schema_version":SCHEMA_VERSION,"plans":[]}
                if payload.get("schema_version")!=SCHEMA_VERSION:raise ValueError("unsupported planner schema")
                self._plans={p.plan_id:p for p in (self._decode(x) for x in payload.get("plans",[]))};self._state=PlannerState.AVAILABLE
                return self._response(r,ResponseStatus.SUCCEEDED,plans=self._all())
            except Exception as e:self._state=PlannerState.INVALID;return self._error_response(r,"planner.initialize.failed",e)
    def create_plan(self,r,goal,constraints=()):
        with self._lock:
            bad=self._ready(r)
            if bad:return bad
            rule=rule_for(goal)
            if not rule:return self._reject(r,"planner.goal.unsupported","No deterministic planning rule exists for this goal")
            records=sorted(self._affordances.get_all(),key=lambda x:x.affordance_id)
            candidate=next((x for x in records if any(t in x.object_name.casefold() for t in rule.object_terms) and all(a in x.affordances for a in rule.actions)),None)
            if not candidate:return self._reject(r,"planner.affordance.unavailable","No object exposes every affordance required by the planning rule")
            knowledge=next((x for x in self._knowledge.get_all() if x.knowledge_id==candidate.knowledge_id and x.object_id==candidate.object_id),None)
            if knowledge is None:return self._reject(r,"planner.knowledge.unavailable","Affordance does not resolve to current Knowledge")
            now=self._clock();slug=re.sub(r"[^a-z0-9]+","-",rule.goal).strip("-");pid=f"plan:{slug}:{candidate.object_id}";nodes=[]
            for i,action in enumerate(rule.actions,1):
                base={"plan_id":pid,"node_id":f"{pid}:node:{i:03d}","action":action,"object_id":candidate.object_id,"knowledge_id":candidate.knowledge_id,"affordance_id":candidate.affordance_id,"goal":rule.goal,"preconditions":tuple(candidate.preconditions.get(action,("object available",))),"postconditions":tuple(candidate.postconditions.get(action,("capability applied",))),"constraints":tuple(candidate.constraints.get(action,())),"participants":(candidate.object_id,),"inputs":() if i==1 else (f"step:{i-1}:complete",),"outputs":(f"step:{i}:complete",),"duration":"semantic-only","priority":i,"metadata":{"rule_id":rule.rule_id},"schema_version":SCHEMA_VERSION,"engine_version":ENGINE_VERSION,"created":now,"updated":now};nodes.append(SemanticPlanNode(**base,checksum=self._hash(base)))
            edges=tuple(SemanticPlanEdge(nodes[i].node_id,nodes[i+1].node_id) for i in range(len(nodes)-1));cons=tuple(SemanticConstraint(f"constraint:{i+1}","semantic",str(x)) for i,x in enumerate(constraints));resource=SemanticResource(f"resource:{candidate.object_id}",candidate.object_id,candidate.knowledge_id,candidate.affordance_id,"primary")
            meta=PlanMetadata(rule.rule_id,RULE_VERSION,{"knowledge":getattr(knowledge,"schema_version",SCHEMA_VERSION),"affordance":getattr(candidate,"schema_version",SCHEMA_VERSION)},(candidate.knowledge_id,candidate.affordance_id));validation=PlanValidation(True,())
            base={"plan_id":pid,"goal":SemanticGoal(f"goal:{slug}",rule.goal,str(goal),rule.success),"nodes":tuple(nodes),"edges":edges,"constraints":cons,"resources":(resource,),"validation":validation,"metadata":meta,"schema_version":SCHEMA_VERSION,"engine_version":ENGINE_VERSION,"created":now,"updated":now};plan=SemanticPlan(**base,checksum=self._hash(base));valid,errors=self._validate(plan)
            if not valid:return self._reject(r,"planner.plan.invalid","; ".join(errors))
            if len(self._plans)>=self._configuration.maximum_plans and pid not in self._plans:return self._reject(r,"planner.capacity.exceeded","Planner capacity exceeded")
            self._plans[pid]=plan;self._persist();return self._response(r,ResponseStatus.SUCCEEDED,plan=plan,valid=True)
    def validate_plan(self,r,plan_id):
        plan=self._plans.get(plan_id);bad=self._ready(r)
        if bad:return bad
        if not plan:return self._reject(r,"planner.plan.not_found","Semantic Plan not found")
        valid,errors=self._validate(plan);return self._response(r,ResponseStatus.SUCCEEDED if valid else ResponseStatus.FAILED,plan=plan,valid=valid,errors=tuple(PlannerError("validation","planner.plan.invalid",x,r.request_id,r.correlation_id) for x in errors))
    def get_plan(self,r,plan_id):
        bad=self._ready(r);plan=self._plans.get(plan_id)
        return bad or (self._response(r,ResponseStatus.SUCCEEDED,plan=plan) if plan else self._reject(r,"planner.plan.not_found","Semantic Plan not found"))
    def search_plans(self,r,query=""):
        bad=self._ready(r);q=str(query).casefold();return bad or self._response(r,ResponseStatus.SUCCEEDED,plans=tuple(p for p in self._all() if not q or q in p.plan_id.casefold() or q in p.goal.name.casefold()))
    def search_goals(self,r,query=""):
        return self.search_plans(r,query)
    def export_plan(self,r,plan_id):
        response=self.get_plan(r,plan_id);return response if not response.plan else self._response(r,ResponseStatus.SUCCEEDED,plan=response.plan,export=freeze(plain(response.plan)))
    def import_plan(self,r,payload):
        bad=self._ready(r)
        if bad:return bad
        try:plan=self._decode(payload);valid,errors=self._validate(plan)
        except Exception as e:return self._error_response(r,"planner.import.invalid",e,ResponseStatus.REJECTED)
        if not valid:return self._reject(r,"planner.import.invalid","; ".join(errors))
        self._plans[plan.plan_id]=plan;self._persist();return self._response(r,ResponseStatus.SUCCEEDED,plan=plan,valid=True)
    def get_statistics(self,r):
        bad=self._ready(r);goals={}
        for p in self._plans.values():goals[p.goal.name]=goals.get(p.goal.name,0)+1
        return bad or self._response(r,ResponseStatus.SUCCEEDED,statistics=PlannerStatistics(len(self._plans),sum(self._validate(p)[0] for p in self._plans.values()),sum(len(p.nodes) for p in self._plans.values()),freeze(goals)))
    def rebuild(self,r):
        bad=self._ready(r)
        if bad:return bad
        invalid=tuple(pid for pid,p in self._plans.items() if not self._validate(p)[0])
        for pid in invalid:self._plans.pop(pid)
        if invalid:self._persist()
        return self._response(r,ResponseStatus.SUCCEEDED,plans=self._all(),valid=not invalid)
    def close(self,r):
        if self._state is not PlannerState.AVAILABLE:return self._invalid(r,"close")
        self._persist();self._state=PlannerState.CLOSED;return self._response(r,ResponseStatus.SUCCEEDED)
    def _validate(self,p):
        errors=[];ids=[n.node_id for n in p.nodes]
        if not ids:errors.append("plan has no nodes")
        if len(ids)!=len(set(ids)):errors.append("duplicate node IDs")
        if any(e.source_node_id not in ids or e.target_node_id not in ids for e in p.edges):errors.append("edge references unknown node")
        if any(self._node_hash(n)!=n.checksum for n in p.nodes):errors.append("node checksum mismatch")
        affordances={x.affordance_id:x for x in self._affordances.get_all()}
        if any(n.affordance_id not in affordances or n.action not in affordances[n.affordance_id].affordances for n in p.nodes):errors.append("action is not supported by current affordance")
        if self._plan_hash(p)!=p.checksum:errors.append("plan checksum mismatch")
        return not errors,tuple(errors)
    def _decode(self,x):
        goal=SemanticGoal(**x["goal"]);nodes=tuple(SemanticPlanNode(**n) for n in x["nodes"]);edges=tuple(SemanticPlanEdge(**e) for e in x.get("edges",[]));cons=tuple(SemanticConstraint(**c) for c in x.get("constraints",[]));resources=tuple(SemanticResource(**a) for a in x.get("resources",[]));validation=PlanValidation(**x["validation"]);meta=PlanMetadata(**x["metadata"]);rest={k:v for k,v in x.items() if k not in {"goal","nodes","edges","constraints","resources","validation","metadata"}};return SemanticPlan(goal=goal,nodes=nodes,edges=edges,constraints=cons,resources=resources,validation=validation,metadata=meta,**rest)
    def _persist(self):self._storage.save({"schema_version":SCHEMA_VERSION,"engine_version":ENGINE_VERSION,"plans":[plain(x) for x in self._all()]})
    def _all(self):return tuple(sorted(self._plans.values(),key=lambda x:x.plan_id))
    @staticmethod
    def _hash(v):return hashlib.sha256(json.dumps(plain(v),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    def _node_hash(self,n):v=plain(n);v.pop("checksum");return self._hash(v)
    def _plan_hash(self,p):v=plain(p);v.pop("checksum");return self._hash(v)
    def _ready(self,r):
        if not isinstance(r,PlannerRequest) or not r.request_id or not r.correlation_id:return self._reject(r,"planner.request.invalid","Invalid request")
        if self._state is not PlannerState.AVAILABLE:return self._invalid(r,"operate")
    def _invalid(self,r,op):return self._reject(r,"planner.lifecycle.invalid_state",f"Cannot {op} while {self._state.value}")
    def _reject(self,r,code,message):return self._response(r,ResponseStatus.REJECTED,errors=(PlannerError("validation",code,message,getattr(r,"request_id","unknown"),getattr(r,"correlation_id","unknown")),))
    def _error_response(self,r,code,e,status=ResponseStatus.FAILED):return self._response(r,status,errors=(PlannerError("processing",code,f"Planner operation failed: {type(e).__name__}",getattr(r,"request_id","unknown"),getattr(r,"correlation_id","unknown")),))
    def _response(self,r,status,**kw):return PlannerResponse(f"{getattr(r,'request_id','unknown')}:planner-response",getattr(r,"request_id","unknown"),getattr(r,"correlation_id","unknown"),status,self._state,**kw)
