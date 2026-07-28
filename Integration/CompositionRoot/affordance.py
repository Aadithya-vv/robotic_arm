"""Composition adapter from ENG-012 public contract to ENG-013 source protocol."""
from taskgraph_knowledge import KnowledgeRequest
class KnowledgeAffordanceSource:
    def __init__(self,knowledge):self._knowledge=knowledge;self._sequence=0
    def get_all(self):
        self._sequence+=1;r=self._knowledge.get_knowledge(KnowledgeRequest(f"affordance-source-{self._sequence}",f"affordance-source-{self._sequence}","composition-root"))
        if r.status.value!="succeeded" or r.graph is None:raise RuntimeError("Knowledge unavailable")
        return tuple(r.graph.records)
