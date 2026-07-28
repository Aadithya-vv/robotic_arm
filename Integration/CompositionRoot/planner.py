"""ENG-015 adapters restricted to public ENG-012/013 contracts."""
from taskgraph_knowledge import KnowledgeRequest
from taskgraph_affordance import AffordanceRequest
class KnowledgePlannerSource:
    def __init__(self,engine):self._engine=engine
    def get_all(self):
        response=self._engine.get_knowledge(KnowledgeRequest("planner-knowledge","planner-read","composition-root"))
        if response.status.value!="succeeded":raise RuntimeError("Knowledge source unavailable")
        return response.graph.records
class AffordancePlannerSource:
    def __init__(self,engine):self._engine=engine
    def get_all(self):
        response=self._engine.get_affordance(AffordanceRequest("planner-affordance","planner-read","composition-root"))
        if response.status.value!="succeeded":raise RuntimeError("Affordance source unavailable")
        return response.graph.records

