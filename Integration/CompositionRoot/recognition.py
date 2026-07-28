"""Descriptor matching against user-created application objects."""
from math import sqrt


class ObjectRecognizer:
    def __init__(self, object_library, threshold=0.82): self.library = object_library; self.threshold = threshold

    def recognize(self, descriptors):
        source = self._vector(descriptors); best = None
        for item in self.library.list():
            candidate = self._stored_vector(item.get("descriptors", ())); score = self._similarity(source, candidate)
            if best is None or score > best[0]: best = (score, item)
        if best and best[0] >= self.threshold:
            self.library.record_recognition(best[1]["object_id"], best[0])
            return {"known": True, "user_name": best[1]["name"], "object_id": best[1]["object_id"], "recognition_confidence": best[0], "library_match": best[1]["object_id"]}
        return {"known": False, "user_name": None, "object_id": None, "recognition_confidence": 0.0 if best is None else best[0]}

    @staticmethod
    def _vector(descriptors):
        for item in descriptors:
            if item.name == "color_histogram": return tuple(item.values)
        return ()

    @staticmethod
    def _stored_vector(descriptors):
        for name, values in descriptors:
            if name == "color_histogram": return tuple(values)
        return ()

    @staticmethod
    def _similarity(first, second):
        if not first or len(first) != len(second): return 0.0
        distance = sqrt(sum((a-b)**2 for a,b in zip(first, second)))
        return 1.0 / (1.0 + distance)
