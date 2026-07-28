"""Composition adapters for ENG-011 public provider contracts."""
from __future__ import annotations

class ObjectLibrarySemanticSource:
    """Expose permanent object records without coupling ENG-011 to their implementation."""
    def __init__(self,object_library):self._object_library=object_library
    def get_all(self):return tuple(self._object_library.list())
