from __future__ import annotations

import hashlib
import json
from threading import RLock
from typing import Any, Mapping

from .contracts import *


class TaskIRCompilerEngine:
    """Pure deterministic compiler from validated Semantic Plans to canonical TaskIR."""

    def __init__(self, storage, configuration=None, log_sink=None):
        if not isinstance(storage, TaskIRStorage):
            raise TypeError("invalid TaskIR storage")
        self._storage = storage
        self._configuration = configuration or TaskIRConfiguration()
        self._log = log_sink or NullLogSink()
        self._state = CompilerState.EMPTY
        self._documents: dict[str, TaskIR] = {}
        self._action_documents: dict[str, dict[str, Any]] = {}
        self._plan_index: dict[str, str] = {}
        self._lock = RLock()

    @property
    def state(self):
        return self._state

    def initialize(self, request):
        with self._lock:
            if self._state is not CompilerState.EMPTY:
                return self._invalid(request, "initialize")
            try:
                payload = self._storage.load() or {"schema_version": SCHEMA_VERSION, "documents": []}
                self._check_major(payload.get("schema_version", ""))
                documents = tuple(self._decode(item) for item in payload.get("documents", []))
                invalid = [doc.task_id for doc in documents if not self._validate(doc).valid]
                if invalid:
                    raise ValueError("stored TaskIR failed integrity validation")
                self._documents = {doc.task_id: doc for doc in documents}
                self._action_documents = {str(item["action_id"]): dict(item) for item in payload.get("action_documents", [])}
                self._reindex()
                self._state = CompilerState.AVAILABLE
                return self._response(request, ResponseStatus.SUCCEEDED, documents=self._all())
            except Exception as error:
                self._state = CompilerState.INVALID
                return self._error(request, "taskir.initialize.failed", error)

    def compile(self, request, semantic_plan):
        with self._lock:
            bad = self._ready(request)
            if bad:
                return bad
            plan = plain(semantic_plan)
            source_validation = self._validate_plan(plan)
            if not source_validation.valid:
                return self._reject(request, "taskir.semantic_plan.invalid", "; ".join(source_validation.errors))
            try:
                task_ir = self._compile(plan, plan.get("correlation_id", plan["plan_id"]))
                validation = self._validate(task_ir)
                if not validation.valid:
                    return self._reject(request, "taskir.compilation.invalid", "; ".join(validation.errors))
                if len(self._documents) >= self._configuration.maximum_documents and task_ir.task_id not in self._documents:
                    return self._reject(request, "taskir.capacity.exceeded", "TaskIR storage capacity exceeded")
                self._documents[task_ir.task_id] = task_ir
                self._reindex()
                self._persist()
                result = TaskCompilationResult(task_ir, validation, task_ir.compilation.diagnostics)
                return self._response(request, ResponseStatus.SUCCEEDED, result=result, task_ir=task_ir, validation=validation)
            except Exception as error:
                return self._error(request, "taskir.compile.failed", error)

    Compile = compile

    def validate_action(self, request, action):
        bad = self._ready(request)
        if bad:
            return {"valid": False, "errors": [plain(error) for error in bad.errors], "warnings": []}
        value = plain(action)
        errors = []
        if not str(value.get("id", "")).strip(): errors.append("Action ID is required")
        if not str(value.get("name", "")).strip(): errors.append("Action name is required")
        if not isinstance(value.get("keyframes", []), list): errors.append("Action timeline must be an array")
        if not isinstance(value.get("scene_objects", []), list): errors.append("Action scene objects must be an array")
        warnings = [] if value.get("keyframes") else ["Action has no keyframes; an IDLE operation will be generated"]
        return {"valid": not errors, "errors": errors, "warnings": warnings}

    def compile_action(self, request, action):
        """Compile an authored Action without discarding its original coordinate timeline."""
        with self._lock:
            validation = self.validate_action(request, action)
            if not validation["valid"]: raise ValueError("; ".join(validation["errors"]))
            document = self._compile_action(plain(action), validation["warnings"])
            self._action_documents[document["action_id"]] = document
            self._persist()
            return document

    def get_action_task_ir(self, request, action_id):
        bad = self._ready(request)
        if bad: raise RuntimeError("TaskIR compiler is unavailable")
        if action_id not in self._action_documents: raise KeyError(action_id)
        return self._action_documents[action_id]

    def list_action_task_ir(self, request):
        bad = self._ready(request)
        if bad: raise RuntimeError("TaskIR compiler is unavailable")
        return tuple(sorted(self._action_documents.values(), key=lambda item: item["metadata"]["compiled_at"], reverse=True))

    def validate(self, request, subject):
        bad = self._ready(request)
        if bad:
            return bad
        try:
            task_ir = self._resolve(subject)
            validation = self._validate(task_ir)
            return self._response(request, ResponseStatus.SUCCEEDED if validation.valid else ResponseStatus.REJECTED,
                                  task_ir=task_ir, validation=validation)
        except Exception as error:
            return self._error(request, "taskir.validate.failed", error, ResponseStatus.REJECTED)

    Validate = validate

    def get_task_ir(self, request, task_id):
        bad = self._ready(request)
        document = self._documents.get(task_id)
        return bad or (self._response(request, ResponseStatus.SUCCEEDED, task_ir=document) if document else
                       self._reject(request, "taskir.not_found", "TaskIR document not found"))

    GetTaskIR = get_task_ir

    def search_task_ir(self, request, query=""):
        bad = self._ready(request)
        needle = str(query).casefold()
        documents = tuple(doc for doc in self._all() if not needle or needle in json.dumps(plain(doc), sort_keys=True).casefold())
        return bad or self._response(request, ResponseStatus.SUCCEEDED, documents=documents)

    SearchTaskIR = search_task_ir

    def export_task_ir(self, request, task_id=None):
        bad = self._ready(request)
        if bad:
            return bad
        documents = self._all() if task_id is None else (self._documents.get(task_id),)
        if any(item is None for item in documents):
            return self._reject(request, "taskir.not_found", "TaskIR document not found")
        payload = {"schema_version": SCHEMA_VERSION, "engine_version": ENGINE_VERSION,
                   "documents": [plain(item) for item in documents]}
        return self._response(request, ResponseStatus.SUCCEEDED, export=freeze(payload), documents=documents)

    ExportTaskIR = export_task_ir

    def import_task_ir(self, request, payload):
        with self._lock:
            bad = self._ready(request)
            if bad:
                return bad
            try:
                raw_documents = payload.get("documents") if isinstance(payload, Mapping) and "documents" in payload else [payload]
                documents = tuple(self._decode(item) for item in raw_documents)
                validations = tuple(self._validate(item) for item in documents)
                errors = tuple(error for validation in validations for error in validation.errors)
                if errors:
                    return self._reject(request, "taskir.import.invalid", "; ".join(errors))
                if len(set(self._documents) | {item.task_id for item in documents}) > self._configuration.maximum_documents:
                    return self._reject(request, "taskir.capacity.exceeded", "TaskIR storage capacity exceeded")
                self._documents.update((item.task_id, item) for item in documents)
                self._reindex()
                self._persist()
                return self._response(request, ResponseStatus.SUCCEEDED, documents=documents)
            except Exception as error:
                return self._error(request, "taskir.import.invalid", error, ResponseStatus.REJECTED)

    ImportTaskIR = import_task_ir

    def get_statistics(self, request):
        bad = self._ready(request)
        actions: dict[str, int] = {}
        for document in self._documents.values():
            for node in document.nodes:
                actions[node.action] = actions.get(node.action, 0) + 1
        stats = TaskStatistics(len(self._documents), sum(self._validate(item).valid for item in self._documents.values()),
                               sum(len(item.nodes) for item in self._documents.values()),
                               sum(len(item.edges) for item in self._documents.values()), actions)
        return bad or self._response(request, ResponseStatus.SUCCEEDED, statistics=stats)

    GetStatistics = get_statistics

    def rebuild(self, request):
        with self._lock:
            bad = self._ready(request)
            if bad:
                return bad
            invalid = tuple(key for key, value in self._documents.items() if not self._validate(value).valid)
            for key in invalid:
                self._documents.pop(key)
            self._reindex()
            if invalid:
                self._persist()
            return self._response(request, ResponseStatus.SUCCEEDED, documents=self._all(),
                                  validation=TaskValidation(not invalid, tuple(f"removed invalid document: {key}" for key in invalid)))

    Rebuild = rebuild

    def close(self, request):
        with self._lock:
            if self._state is not CompilerState.AVAILABLE:
                return self._invalid(request, "close")
            self._persist()
            self._state = CompilerState.CLOSED
            return self._response(request, ResponseStatus.SUCCEEDED)

    def _compile(self, plan, correlation_id):
        plan_id = plan["plan_id"]
        task_id = "taskir:" + hashlib.sha256(plan["checksum"].encode()).hexdigest()[:24]
        rule_id = plan["metadata"]["rule_id"]
        nodes = []
        for source in plan["nodes"]:
            pre = tuple(TaskCondition(f'{source["node_id"]}:pre:{index:03d}', "precondition", value)
                        for index, value in enumerate(source.get("preconditions", []), 1))
            post = tuple(TaskCondition(f'{source["node_id"]}:post:{index:03d}', "postcondition", value)
                         for index, value in enumerate(source.get("postconditions", []), 1))
            constraints = tuple(TaskConstraint(f'{source["node_id"]}:constraint:{index:03d}', "semantic", value)
                                for index, value in enumerate(source.get("constraints", []), 1))
            base = {"task_id": task_id, "node_id": source["node_id"], "semantic_plan_id": plan_id,
                    "planning_rule_id": source.get("metadata", {}).get("rule_id", rule_id), "action": source["action"],
                    "object_id": source["object_id"], "knowledge_id": source["knowledge_id"],
                    "affordance_id": source["affordance_id"], "parameters": (),
                    "inputs": tuple(source.get("inputs", [])), "outputs": tuple(source.get("outputs", [])),
                    "preconditions": pre, "postconditions": post, "constraints": constraints,
                    "priority": source["priority"], "metadata": source.get("metadata", {}),
                    "schema_version": SCHEMA_VERSION, "engine_version": ENGINE_VERSION,
                    "created": source["created"], "updated": source["updated"]}
            nodes.append(TaskNode(**base, checksum=self._hash(base)))
        edges = tuple(TaskEdge(item["source_node_id"], item["target_node_id"], item.get("relation", "precedes"))
                      for item in plan.get("edges", []))
        constraints = tuple(TaskConstraint(item["constraint_id"], item["kind"], item["description"], item.get("required", True))
                            for item in plan.get("constraints", []))
        provenance = tuple(plan["metadata"].get("provenance", ())) + (plan_id,)
        metadata = TaskMetadata(correlation_id, plan["schema_version"], rule_id, plan["metadata"]["rule_version"], provenance,
                                tuple(plan.get("explanation_references", ())))
        compilation = TaskCompilation(plan_id, ENGINE_ID, ENGINE_VERSION, ("source validated", "structure preserved", "TaskIR validated"))
        base = {"task_id": task_id, "semantic_plan_id": plan_id, "correlation_id": correlation_id,
                "goal": plan["goal"], "resources": tuple(plan.get("resources", ())), "nodes": tuple(nodes), "edges": edges,
                "constraints": constraints, "failure_semantics": tuple(plan.get("failure_semantics", ())),
                "metadata": metadata, "validation": TaskValidation(True), "compilation": compilation,
                "schema_version": SCHEMA_VERSION, "engine_version": ENGINE_VERSION,
                "created": plan["created"], "updated": plan["updated"]}
        return TaskIR(**base, checksum=self._hash(base))

    def _compile_action(self, action, warnings):
        from datetime import datetime
        from math import hypot
        started = datetime.now()
        timeline = sorted((dict(item) for item in action.get("keyframes", [])), key=lambda item: float(item.get("timestamp", 0)))
        referenced = list(dict.fromkeys(str(item) for item in action.get("referencedObjects", []) if item))
        operations = []
        for object_id in referenced or [""]:
            frames = [(index, item) for index, item in enumerate(timeline) if not object_id or str(item.get("objectId", "")) == object_id]
            if not frames:
                operations.append({"operation_id": f"op-{len(operations)+1:03d}", "type": "IDLE", "object_id": object_id,
                                   "frames": [0, 0], "timestamps": [0.0, 0.0], "coordinates": [], "inference": "No coordinate changes observed", "metadata": {}})
                continue
            first_index, first = frames[0]
            operations.append(self._action_operation(len(operations), "PICK", object_id, first_index, first_index, first, first, 0.0,
                                                     "First observed object state establishes acquisition"))
            for (left_index, left), (right_index, right) in zip(frames, frames[1:]):
                distance = hypot(float(right.get("positionX", 0))-float(left.get("positionX", 0)),
                                 float(right.get("positionY", 0))-float(left.get("positionY", 0)))
                kind = "TRANSPORT" if distance > 0.01 else "IDLE"
                inference = "Coordinate displacement indicates transport" if kind == "TRANSPORT" else "No significant coordinate displacement"
                operations.append(self._action_operation(len(operations), kind, object_id, left_index, right_index, left, right, distance, inference))
            last_index, last = frames[-1]
            operations.append(self._action_operation(len(operations), "PLACE", object_id, last_index, last_index, last, last, 0.0,
                                                     "Final observed object state establishes placement"))
        segments = [{"segment_id": f"segment-{index+1:03d}", **item} for index, item in enumerate(operations)]
        duration = max([float(action.get("estimatedDuration", 0) or 0), *(float(item.get("timestamp", 0)) for item in timeline)], default=0)
        completed = datetime.now()
        stages = ["Action", "Load Timeline", "Analyze Coordinates", "Infer Motion", "Detect Semantic Segments", "Generate Operations", "Validate", "Generate TaskIR"]
        document = {"task_ir_id": f'taskir-action:{action["id"]}', "action_id": action["id"], "schema_version": "1.0",
                    "vocabulary": ["IDLE", "PICK", "TRANSPORT", "PLACE"],
                    "objects": referenced, "original_coordinates": [dict(item) for item in timeline], "timeline": [dict(item) for item in timeline],
                    "semantic_segments": segments, "operations": operations,
                    "metadata": {"action_name": action["name"], "description": action.get("description", ""), "category": action.get("category", ""),
                                 "tags": list(action.get("tags", [])), "preview_video": action.get("previewVideo"), "duration": duration,
                                 "source_created_at": action.get("createdAt"), "source_updated_at": action.get("updatedAt"),
                                 "compiled_at": completed.isoformat(timespec="seconds"), "compiler": ENGINE_ID, "compiler_version": ENGINE_VERSION},
                    "validation": {"valid": True, "errors": [], "warnings": list(warnings)},
                    "pipeline": [{"name": name, "status": "complete", "details": self._stage_detail(name, action, timeline, operations)} for name in stages],
                    "console": ["Loading Action...", "Loading Timeline...", "Analyzing Coordinates...", "Inferring Motion...",
                                "Generating Operations...", "Generating TaskIR...", "Completed."],
                    "metrics": {"objects": len(referenced), "keyframes": len(timeline), "operations": len(operations),
                                "semantic_segments": len(segments), "warnings": len(warnings), "errors": 0,
                                "build_time_ms": max(1, int((completed-started).total_seconds()*1000))}}
        document["checksum"] = self._hash(document)
        return document

    @staticmethod
    def _action_operation(index, kind, object_id, left_index, right_index, left, right, distance, inference):
        return {"operation_id": f"op-{index+1:03d}", "type": kind, "object_id": object_id,
                "frames": [left_index, right_index], "timestamps": [float(left.get("timestamp", 0)), float(right.get("timestamp", 0))],
                "coordinates": [{"x": float(left.get("positionX", 0)), "y": float(left.get("positionY", 0)), "rotation": float(left.get("rotationAngle", 0))},
                                {"x": float(right.get("positionX", 0)), "y": float(right.get("positionY", 0)), "rotation": float(right.get("rotationAngle", 0))}],
                "inference": inference, "metadata": {"distance": round(distance, 6)}}

    @staticmethod
    def _stage_detail(name, action, timeline, operations):
        details = {"Action": f'Loaded {action.get("name", "Action")}', "Load Timeline": f"{len(timeline)} keyframes loaded",
                   "Analyze Coordinates": f"{len(timeline)} coordinate states preserved", "Infer Motion": f"{sum(x['type']=='TRANSPORT' for x in operations)} movements detected",
                   "Detect Semantic Segments": f"{len(operations)} semantic segments detected", "Generate Operations": f"{len(operations)} operations generated",
                   "Validate": "V1 vocabulary and coordinate preservation valid", "Generate TaskIR": "Robot-independent TaskIR generated"}
        return details[name]

    def _validate_plan(self, plan):
        errors = []
        required = ("plan_id", "goal", "nodes", "validation", "metadata", "schema_version", "checksum", "created", "updated")
        errors.extend(f"Semantic Plan missing {name}" for name in required if name not in plan)
        if errors:
            return TaskValidation(False, tuple(errors))
        try:
            self._check_major(plan["schema_version"])
        except ValueError as error:
            errors.append(str(error))
        validation = plan.get("validation", {})
        if not validation.get("valid") or validation.get("errors"):
            errors.append("Semantic Plan is not validated")
        nodes = plan.get("nodes", [])
        ids = [item.get("node_id") for item in nodes]
        if not ids:
            errors.append("Semantic Plan has no nodes")
        if len(ids) != len(set(ids)):
            errors.append("Semantic Plan contains duplicate node IDs")
        if any(edge.get("source_node_id") not in ids or edge.get("target_node_id") not in ids for edge in plan.get("edges", [])):
            errors.append("Semantic Plan edge references unknown node")
        if self._checksum_without(plan, "checksum") != plan.get("checksum"):
            errors.append("Semantic Plan checksum mismatch")
        if any(self._checksum_without(node, "checksum") != node.get("checksum") for node in nodes):
            errors.append("Semantic Plan node checksum mismatch")
        return TaskValidation(not errors, tuple(errors))

    def _validate(self, document):
        errors = []
        try:
            self._check_major(document.schema_version)
        except ValueError as error:
            errors.append(str(error))
        ids = [node.node_id for node in document.nodes]
        if not ids:
            errors.append("TaskIR has no nodes")
        if len(ids) != len(set(ids)):
            errors.append("duplicate TaskIR node IDs")
        if any(edge.source_node_id not in ids or edge.target_node_id not in ids for edge in document.edges):
            errors.append("TaskIR edge references unknown node")
        if any(self._checksum_without(plain(node), "checksum") != node.checksum for node in document.nodes):
            errors.append("TaskIR node checksum mismatch")
        if self._checksum_without(plain(document), "checksum") != document.checksum:
            errors.append("TaskIR checksum mismatch")
        if document.semantic_plan_id != document.compilation.source_plan_id:
            errors.append("TaskIR provenance mismatch")
        return TaskValidation(not errors, tuple(errors))

    def _decode(self, raw):
        nodes = tuple(TaskNode(parameters=tuple(TaskParameter(**x) for x in item.get("parameters", [])),
                               preconditions=tuple(TaskCondition(**x) for x in item.get("preconditions", [])),
                               postconditions=tuple(TaskCondition(**x) for x in item.get("postconditions", [])),
                               constraints=tuple(TaskConstraint(**x) for x in item.get("constraints", [])),
                               **{key: value for key, value in item.items() if key not in {"parameters", "preconditions", "postconditions", "constraints"}})
                      for item in raw["nodes"])
        return TaskIR(nodes=nodes, edges=tuple(TaskEdge(**x) for x in raw.get("edges", [])),
                      constraints=tuple(TaskConstraint(**x) for x in raw.get("constraints", [])),
                      metadata=TaskMetadata(**raw["metadata"]), validation=TaskValidation(**raw["validation"]),
                      compilation=TaskCompilation(**raw["compilation"]),
                      **{key: value for key, value in raw.items() if key not in {"nodes", "edges", "constraints", "metadata", "validation", "compilation"}})

    def _resolve(self, subject):
        if isinstance(subject, TaskIR):
            return subject
        if isinstance(subject, str):
            if subject not in self._documents:
                raise ValueError("TaskIR document not found")
            return self._documents[subject]
        return self._decode(subject)

    def _persist(self):
        self._storage.save({"schema_version": SCHEMA_VERSION, "engine_version": ENGINE_VERSION,
                            "documents": [plain(item) for item in self._all()],
                            "action_documents": list(self._action_documents.values())})

    def _reindex(self):
        self._plan_index = {item.semantic_plan_id: item.task_id for item in self._documents.values()}

    def _all(self):
        return tuple(sorted(self._documents.values(), key=lambda item: item.task_id))

    def _check_major(self, version):
        if int(str(version).split(".")[0]) != self._configuration.supported_schema_major:
            raise ValueError("unsupported schema major version")

    @staticmethod
    def _hash(value):
        return hashlib.sha256(json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

    def _checksum_without(self, value, key):
        value = dict(plain(value))
        value.pop(key, None)
        return self._hash(value)

    def _ready(self, request):
        if not isinstance(request, TaskIRRequest) or not request.request_id or not request.correlation_id:
            return self._reject(request, "taskir.request.invalid", "Invalid compiler request")
        if self._state is not CompilerState.AVAILABLE:
            return self._invalid(request, "operate")

    def _invalid(self, request, operation):
        return self._reject(request, "taskir.lifecycle.invalid_state", f"Cannot {operation} while {self._state.value}")

    def _reject(self, request, code, message):
        error = TaskIRError("validation", code, message, getattr(request, "request_id", "unknown"),
                            getattr(request, "correlation_id", "unknown"))
        return self._response(request, ResponseStatus.REJECTED, errors=(error,))

    def _error(self, request, code, error, status=ResponseStatus.FAILED):
        detail = TaskIRError("processing", code, f"TaskIR operation failed: {type(error).__name__}",
                             getattr(request, "request_id", "unknown"), getattr(request, "correlation_id", "unknown"))
        return self._response(request, status, errors=(detail,))

    def _response(self, request, status, **values):
        request_id = getattr(request, "request_id", "unknown")
        return TaskIRResponse(f"{request_id}:taskir-response", request_id, getattr(request, "correlation_id", "unknown"),
                              status, self._state, **values)
