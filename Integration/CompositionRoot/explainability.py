"""Rule-40 adapters exposing read-only public artifact projections to ENG-016."""
from taskgraph_semantic_inventory import SemanticRequest
from taskgraph_knowledge import KnowledgeRequest
from taskgraph_affordance import AffordanceRequest
from taskgraph_planner import PlannerRequest
from taskgraph_taskir import TaskIRRequest

class SemanticPipelineArtifactSource:
    def __init__(self,semantic,knowledge,affordance,planner,taskir):self._semantic,self._knowledge,self._affordance,self._planner,self._taskir=semantic,knowledge,affordance,planner,taskir
    def get_artifacts(self):
        artifacts=[]
        semantic=self._semantic.get_all_objects(SemanticRequest("explain-semantic","explain-rebuild","composition-root"))
        if semantic.status.value!="succeeded":raise RuntimeError("Semantic Inventory unavailable")
        artifacts.extend(("semantic_inventory","ENG-011",x) for x in semantic.inventory.objects)
        knowledge=self._knowledge.get_knowledge(KnowledgeRequest("explain-knowledge","explain-rebuild","composition-root"))
        if knowledge.status.value!="succeeded":raise RuntimeError("Knowledge Graph unavailable")
        artifacts.extend(("knowledge","ENG-012",x) for x in knowledge.graph.records)
        affordance=self._affordance.get_affordance(AffordanceRequest("explain-affordance","explain-rebuild","composition-root"))
        if affordance.status.value!="succeeded":raise RuntimeError("Affordance Graph unavailable")
        artifacts.extend(("affordance","ENG-013",x) for x in affordance.graph.records)
        plans=self._planner.search_plans(PlannerRequest("explain-plans","explain-rebuild","composition-root"))
        if plans.status.value!="succeeded":raise RuntimeError("Semantic Planner unavailable")
        artifacts.extend(("semantic_plan","ENG-015",x) for x in plans.plans)
        taskir=self._taskir.search_task_ir(TaskIRRequest("explain-taskir","explain-rebuild","composition-root"))
        if taskir.status.value!="succeeded":raise RuntimeError("TaskIR Compiler unavailable")
        artifacts.extend(("task_ir","ENG-014",x) for x in taskir.documents)
        return tuple(artifacts)
