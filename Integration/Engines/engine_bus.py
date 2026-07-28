"""Generic reusable engine communication infrastructure.

This module intentionally contains no TaskGraph business rules.
"""
from __future__ import annotations

from collections import defaultdict
from threading import RLock


class EngineBus:
    def __init__(self):
        self._engines = {}
        self._subscribers = defaultdict(list)
        self._lock = RLock()
        self._started = False

    def start(self): self._started = True
    def stop(self): self._started = False

    def register(self, name, engine):
        with self._lock:
            if name in self._engines: raise ValueError(f"Engine already registered: {name}")
            self._engines[name] = engine

    def unregister(self, name):
        with self._lock: return self._engines.pop(name, None)

    def discover(self): return tuple(sorted(self._engines))

    def request(self, engine_name, operation, *args, **kwargs):
        if not self._started: raise RuntimeError("Engine Bus is not started")
        engine = self._engines.get(engine_name)
        if engine is None: raise KeyError(engine_name)
        handler = getattr(engine, operation, None)
        if handler is None or operation.startswith("_"): raise AttributeError(operation)
        return handler(*args, **kwargs)

    def subscribe(self, event_name, callback):
        with self._lock: self._subscribers[event_name].append(callback)
        return lambda: self.unsubscribe(event_name, callback)

    def unsubscribe(self, event_name, callback):
        with self._lock:
            if callback in self._subscribers[event_name]: self._subscribers[event_name].remove(callback)

    def publish(self, event_name, payload):
        for callback in tuple(self._subscribers[event_name]): callback(payload)
