"""Composition adapter from ENG-011 public contract to ENG-012 source protocol."""
from __future__ import annotations
from taskgraph_semantic_inventory import SemanticRequest

class SemanticInventoryKnowledgeSource:
    def __init__(self,semantic_inventory):self._semantic_inventory=semantic_inventory;self._sequence=0
    def get_all(self):
        self._sequence+=1;response=self._semantic_inventory.get_all_objects(SemanticRequest(f"knowledge-source-{self._sequence}",f"knowledge-source-{self._sequence}","composition-root"))
        if response.status.value!="succeeded" or response.inventory is None:raise RuntimeError("Semantic Inventory unavailable")
        return tuple(response.inventory.objects)
