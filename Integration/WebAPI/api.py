"""TaskGraph v1.0 Web Edition presentation adapter.

This module exposes the frozen Composition Root through REST and WebSocket
projections. It owns no Engine logic.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import shutil
from datetime import datetime
from contextlib import asynccontextmanager
from dataclasses import fields, is_dataclass
from pathlib import Path
from threading import RLock
from typing import Any
from time import monotonic
from uuid import uuid4
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parents[2]
COMPOSITION = ROOT / "Integration" / "CompositionRoot"
INTEGRATION = ROOT / "Integration"
for source in sorted((ROOT / "Implementation").glob("ENG-*_Engine/Source")):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
if str(COMPOSITION) not in sys.path:
    sys.path.insert(0, str(COMPOSITION))
if str(INTEGRATION) not in sys.path:
    sys.path.insert(0, str(INTEGRATION))

from gpu_runtime import accelerator_diagnostics
from health import collect_health
from shutdown import shutdown_runtime
from startup import create_runtime
from validation import validate_runtime
from taskgraph_semantic_inventory import SemanticRequest
from taskgraph_knowledge import KnowledgeRequest
from taskgraph_affordance import AffordanceRequest
from taskgraph_planner import PlannerRequest
from taskgraph_taskir import TaskIRRequest
from taskgraph_explainability import ExplainabilityRequest
from frame_processing import FrameProcessingService
from cluster_engine import ClusterEngine
from object_library_service import ObjectLibraryService
from action_builder_store import ActionBuilderStore, ActionLibraryStore
from Engines import ActionAssetEngine, CompilerEngine, EngineBus, ExecutionTaskStore, PackagingEngine, RobotProfileStore


def plain(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: plain(getattr(value, field.name)) for field in fields(value)}
    if hasattr(value, "items"):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [plain(item) for item in value]
    if isinstance(value, bytes):
        return None
    if hasattr(value, "value"):
        return value.value
    return value


FRAME_MANIFEST_PATH = ROOT / "Workspace" / "frame_manifest.json"
FRAME_REVIEW_PATH = ROOT / "Workspace" / "frame_review_state.json"
FRAME_STATE_LOCK = RLock()


def _read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else fallback
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return fallback


def _write_json(path: Path, value: dict[str, Any]):
    with FRAME_STATE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(plain(value), indent=2), encoding="utf-8")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def _frame_sort_key(path: Path):
    match = re.search(r"(\d+)$", path.stem)
    return (int(match.group(1)) if match else sys.maxsize, path.name.lower())


def _frame_file_available(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size <= 8:
            return False
        with path.open("rb") as stream:
            return stream.read(8) == b"\x89PNG\r\n\x1a\n"
    except OSError:
        return False


def ensure_frame_manifest(runtime) -> dict[str, Any]:
    """Return the persisted extraction manifest, reconciling legacy frame files once."""
    workspace = runtime.video_workspace
    stored = _read_json(FRAME_MANIFEST_PATH, {})
    session_id = str(stored.get("session_id") or uuid4().hex)
    records = [item for item in stored.get("frames", []) if isinstance(item, dict) and item.get("filename")]
    known = {str(item["filename"]): item for item in records}
    changed = not stored.get("session_id")
    for position, path in enumerate(sorted(workspace.frames, key=_frame_sort_key), 1):
        if path.name in known:
            continue
        width = height = 0
        try:
            import cv2
            image = cv2.imread(str(path))
            if image is not None:
                height, width = image.shape[:2]
        except Exception:
            pass
        fps = float(getattr(workspace.metadata, "fps", 0) or 0)
        record = {
            "frame_id": f"{session_id}:{uuid4().hex}",
            "filename": path.name,
            "source_frame_number": position,
            "timestamp": (position - 1) / fps if fps > 0 else 0.0,
            "width": width,
            "height": height,
        }
        records.append(record)
        known[path.name] = record
        changed = True
    records.sort(key=lambda item: _frame_sort_key(Path(str(item["filename"]))))
    manifest = {"version": 1, "session_id": session_id, "frames": records}
    if changed:
        _write_json(FRAME_MANIFEST_PATH, manifest)
    return manifest


def persist_frame_review(runtime):
    workspace = runtime.video_workspace
    review = getattr(workspace, "web_frame_review", {"current_frame_id": None, "selected_frame_ids": []})
    _write_json(FRAME_REVIEW_PATH, {
        "version": 1,
        "current_frame_id": review.get("current_frame_id"),
        "selected_frame_ids": list(dict.fromkeys(review.get("selected_frame_ids", []))),
        "detection": getattr(workspace, "web_detection", {}),
        "clusters": getattr(workspace, "web_clusters", {}),
    })


def restore_frame_review(runtime):
    workspace = runtime.video_workspace
    stored = _read_json(FRAME_REVIEW_PATH, {})
    detection = stored.get("detection") if isinstance(stored.get("detection"), dict) else {}
    if detection.get("state") == "running":
        detection.update(state="cancelled", error="Detection was interrupted by application shutdown.")
    workspace.web_detection = detection or {"state": "idle", "current": 0, "total": 0, "eta": 0.0, "frames": {}, "metrics": {}}
    workspace.web_clusters = stored.get("clusters") if isinstance(stored.get("clusters"), dict) else {"renamed": {}, "ignored": [], "deleted": [], "accepted": [], "generated": []}
    for key, fallback in {"renamed": {}, "ignored": [], "deleted": [], "accepted": [], "selected": [], "expanded": [], "generated": [], "clustering": {"state": "idle", "progress": 0, "error": None}}.items():
        workspace.web_clusters.setdefault(key, fallback)
    workspace.web_frame_review = {
        "current_frame_id": stored.get("current_frame_id"),
        "selected_frame_ids": list(dict.fromkeys(stored.get("selected_frame_ids", []))),
    }


def frame_workspace_payload(runtime) -> dict[str, Any]:
    workspace = runtime.video_workspace
    manifest = ensure_frame_manifest(runtime)
    detection = getattr(workspace, "web_detection", {})
    detection_frames = detection.get("frames", {})
    frames = []
    for position, item in enumerate(manifest["frames"], 1):
        path = workspace.frames_dir / str(item["filename"])
        detected = detection_frames.get(str(position), {})
        available = _frame_file_available(path)
        frames.append({
            **item,
            "ordinal": position,
            "availability": "available" if available else "missing",
            "available": available,
            "detection_status": detected.get("status", "waiting"),
            "detections": detected.get("labels", []),
            "image_url": f"/frame-workspace/frames/{item['frame_id']}?variant=raw",
        })
    valid_ids = {item["frame_id"] for item in frames}
    review = getattr(workspace, "web_frame_review", {"current_frame_id": None, "selected_frame_ids": []})
    selected = [item for item in review.get("selected_frame_ids", []) if item in valid_ids]
    current = review.get("current_frame_id") if review.get("current_frame_id") in valid_ids else (frames[0]["frame_id"] if frames else None)
    return {
        "session_id": manifest["session_id"],
        "frames": frames,
        "review": {"current_frame_id": current, "selected_frame_ids": selected},
        "detection": plain(detection),
    }


def runtime_payload(runtime) -> dict[str, Any]:
    detector = runtime.perception.detector_status()
    metrics = runtime.monitor.rolling_averages()
    workers = runtime.perception.worker_diagnostics()
    video = runtime.video_workspace
    return {
        "version": "v1.0",
        "milestone": "M2 FINAL",
        "status": "operational",
        "detector": plain(detector),
        "accelerator": plain(accelerator_diagnostics()),
        "metrics": plain(metrics),
        "workers": plain(workers),
        "workspace": {
            "frames": len(video.frames),
            "processed": len(video.results),
            "errors": len(video.errors),
            "current_object": video.current_object,
            "current_confidence": video.current_confidence,
            "extraction": plain(getattr(video, "web_extraction", {"state": "idle", "current": 0, "total": 0, "eta": 0.0, "frame": None})),
            "video": {
                "metadata": plain(video.metadata),
                "source_url": (
                    f"/video/source?v={video.source_path.stat().st_mtime_ns}"
                    if video.source_path and video.source_path.is_file()
                    else None
                ),
            },
            "detection": plain(getattr(video, "web_detection", {"state": "idle", "current": 0, "total": 0, "eta": 0.0, "frames": {}, "metrics": {}})),
        },
        "timeline": plain(runtime.monitor.snapshot()[-120:]),
    }


def scene_payload(runtime) -> dict[str, Any]:
    results = runtime.video_workspace.results
    snapshot = results[max(results)][2] if results else None
    if snapshot is None:
        return {"scene_id": None, "objects": [], "relationships": []}
    return plain(snapshot)


def detection_payload(runtime) -> dict[str, Any]:
    rows = []
    manifest_frames = ensure_frame_manifest(runtime).get("frames", [])
    deleted = set(getattr(runtime.video_workspace, "web_clusters", {}).get("deleted", ()))
    for index, value in sorted(runtime.video_workspace.results.items()):
        _, vision, _, annotated, status = value
        for item in vision.objects:
            class_name = item.properties.get("ai_class") or "Object"
            cluster_id = f"cluster-{str(class_name).strip().lower().replace(' ', '-')}"
            if cluster_id in deleted:
                continue
            rows.append({
                "frame": index + 1,
                "frame_id": manifest_frames[index]["frame_id"] if index < len(manifest_frames) else f"video-frame-{index + 1}",
                "class_name": class_name,
                "confidence": item.confidence,
                "tracking_id": item.candidate_id,
                "bounding_box": plain(item.region),
                "embedding": [number for feature in item.features for number in feature.values],
                "status": status,
                "annotated_frame": f"/frames/{Path(annotated).name}",
            })
    if not rows:
        state = getattr(runtime.video_workspace, "web_detection", {})
        for frame_number, frame_state in state.get("frames", {}).items():
            index = max(0, int(frame_number) - 1)
            for item in frame_state.get("labels", []):
                rows.append({
                    "frame": index + 1,
                    "frame_id": manifest_frames[index]["frame_id"] if index < len(manifest_frames) else f"video-frame-{index + 1}",
                    "class_name": item.get("class_name") or item.get("label") or "Object",
                    "confidence": float(item.get("confidence", 0.0)),
                    "tracking_id": item.get("object_id") or f"frame-{index + 1}-object",
                    "bounding_box": {key: int(item.get(key, 0)) for key in ("x", "y", "width", "height")},
                    "embedding": item.get("embedding", []),
                    "status": frame_state.get("status", "detected"),
                    "annotated_frame": f"/frames/{manifest_frames[index]['filename']}" if index < len(manifest_frames) else None,
                })
    return {"detections": rows, "errors": plain(runtime.video_workspace.errors)}


HUMAN_CLASSES = {"person", "hand", "arm", "face", "body"}


def cluster_payload(runtime) -> dict[str, Any]:
    review = getattr(runtime.video_workspace, "web_clusters", {"renamed": {}, "ignored": [], "deleted": [], "accepted": []})
    if review.get("generated"):
        clusters=[]
        for stored in review["generated"]:
            if stored["id"] in review["deleted"] or stored["id"] in review["ignored"] or stored["id"] in review["accepted"]:continue
            item={**stored,"name":review["renamed"].get(stored["id"],stored["name"])};clusters.append(item)
        return {"clusters":plain(clusters),"review":plain(review)}
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in detection_payload(runtime)["detections"]:
        if row["class_name"].strip().lower() in HUMAN_CLASSES:
            continue
        cluster_id = f"cluster-{row['class_name'].strip().lower().replace(' ', '-')}"
        groups.setdefault(cluster_id, []).append(row)
    clusters = []
    for cluster_id, instances in sorted(groups.items()):
        if cluster_id in review["deleted"] or cluster_id in review["ignored"] or cluster_id in review["accepted"]:
            continue
        name = review["renamed"].get(cluster_id) or instances[0]["class_name"].title()
        clusters.append({"id": cluster_id, "name": name, "instances": instances, "frame_count": len({item["frame"] for item in instances}), "confidence": sum(item["confidence"] for item in instances) / len(instances), "status": "ready"})
    return {"clusters": clusters, "review": plain(review)}


def frame_cluster_payload(runtime) -> dict[str, Any]:
    review = runtime.video_workspace.web_clusters
    selected = set(review.get("selected", []))
    expanded = set(review.get("expanded", []))
    deleted = set(review.get("deleted", []))
    frames = {item["ordinal"]: item for item in frame_workspace_payload(runtime)["frames"]}
    clusters = []
    for stored in review.get("generated", []):
        if stored["id"] in deleted:
            continue
        representatives = []
        for number in stored.get("representative_frames", []):
            frame = frames.get(int(number))
            if frame:
                representatives.append({
                    "frame_id": frame["frame_id"],
                    "ordinal": frame["ordinal"],
                    "filename": frame["filename"],
                    "image_url": frame["image_url"],
                    "available": frame["available"],
                })
        instances = []
        for instance in stored.get("instances", []):
            number = int(instance["frame"])
            frame = frames.get(number)
            instances.append({
                **instance,
                "frame_id": frame["frame_id"] if frame else instance.get("frame_id") or f"video-frame-{number}",
                "image_url": frame["image_url"] if frame else None,
            })
        clusters.append({
            **stored,
            "name": review.get("renamed", {}).get(stored["id"], stored["name"]),
            "instances": instances,
            "member_frames": sorted({item["frame_id"] for item in instances}),
            "representatives": representatives,
            "representative_frame": representatives[0] if representatives else None,
            "object_count": len(instances),
            "selected": stored["id"] in selected,
            "expanded": stored["id"] in expanded,
            "review_state": "accepted" if stored["id"] in review.get("accepted", []) else "rejected" if stored["id"] in review.get("ignored", []) else stored.get("review_state", "pending"),
            "created_at": stored.get("created_at") or datetime.now().isoformat(timespec="seconds"),
        })
    return {
        "clusters": plain(clusters),
        "selected_cluster_ids": [item["id"] for item in clusters if item["selected"]],
        "clustering": plain(review.get("clustering", {"state": "idle", "progress": 0, "error": None})),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.runtime = create_runtime({"runtime_mode": "web", "release": "v1.0"}, "web-startup")
    restore_frame_review(app.state.runtime)
    app.state.runtime_subscribers = set()
    app.state.object_subscribers = set()
    app.state.action_assets = ActionAssetEngine(ROOT)
    app.state.execution_tasks = ExecutionTaskStore(ROOT)
    app.state.robot_profiles = RobotProfileStore(ROOT)
    app.state.compiler = CompilerEngine(ROOT, app.state.runtime.taskir, app.state.action_assets, app.state.execution_tasks, taskir_request)
    app.state.packaging = PackagingEngine(ROOT, app.state.execution_tasks, app.state.robot_profiles)
    app.state.engine_bus = EngineBus()
    app.state.engine_bus.start()
    app.state.cluster_subscribers = set()
    app.state.loop = asyncio.get_running_loop()
    app.state.validation = validate_runtime(app.state.runtime, "web-validation")
    yield
    app.state.engine_bus.stop()
    shutdown_runtime(app.state.runtime, "web-shutdown")


app = FastAPI(title="TaskGraph v1.0 Web API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/runtime")
def get_runtime():
    return runtime_payload(app.state.runtime)


@app.get("/objects")
def get_objects():
    return {"objects": plain(app.state.runtime.object_library.list())}


def object_dependency_payload(object_id: str) -> dict[str, Any]:
    references: list[dict[str, str]] = []
    try:
        state = app.state.action_assets.load_workspace()
        if any(item.get("objectId") == object_id for item in state.get("scene_objects", ()) + state.get("timeline", ())):
            references.append({"kind": "action_builder", "id": "workspace", "name": "Action Builder workspace"})
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    try:
        for action in app.state.action_assets.list_assets():
            if object_id in action.get("referencedObjects", ()) or any(item.get("objectId") == object_id for item in action.get("scene_objects", ()) + action.get("keyframes", ())):
                references.append({"kind": "action", "id": action["id"], "name": action.get("name") or action["id"]})
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    locations = (
        ("taskir", ROOT / "Assets" / "TaskIR"),
        ("execution_task", ROOT / "Assets" / "Execution Tasks"),
        ("execution_package", ROOT / "Assets" / "ExecutionPackages"),
    )
    for kind, directory in locations:
        if not directory.is_dir(): continue
        for path in directory.rglob("*.json"):
            try:
                if object_id in path.read_text(encoding="utf-8"):
                    references.append({"kind": kind, "id": path.stem, "name": path.name})
            except OSError:
                continue
    unique = {(item["kind"], item["id"]): item for item in references}
    return {"object_id": object_id, "count": len(unique), "references": list(unique.values())}


def object_manifest_payload() -> dict[str, Any]:
    library = app.state.runtime.object_library
    objects = []
    for item in library.list():
        value = plain(item)
        object_id = value["object_id"]
        thumbnail = value.get("thumbnail", {})
        metadata = value.get("metadata", {})
        frame_ids = list(metadata.get("frame_ids") or thumbnail.get("source_frames") or value.get("frames") or ())
        detections = list(metadata.get("detections") or ())
        target = Path(thumbnail.get("path", ""))
        dependencies = object_dependency_payload(object_id)
        objects.append({
            "object_id": object_id,
            "name": value.get("name", ""),
            "category": value.get("category", ""),
            "type": value.get("type", ""),
            "description": value.get("description", ""),
            "tags": list(value.get("tags") or ()),
            "aliases": list(value.get("aliases") or ()),
            "properties": value.get("properties") or {},
            "metadata": metadata,
            "color": value.get("color", ""),
            "material": value.get("material", ""),
            "created": value.get("created", ""),
            "updated": value.get("updated", ""),
            "version": int(value.get("version", 1) or 1),
            "review_status": metadata.get("review_state", ""),
            "availability": "available" if target.is_file() else "missing",
            "thumbnail_url": f"/objects/{quote(object_id, safe='')}/thumbnail" if target.is_file() else "",
            "representative_image_url": f"/objects/{quote(object_id, safe='')}/thumbnail" if target.is_file() else "",
            "representative_frame_id": thumbnail.get("frame_id", ""),
            "source_cluster": metadata.get("cluster_id", ""),
            "source_cluster_name": metadata.get("cluster_name", ""),
            "source_frames": frame_ids,
            "frame_count": len(frame_ids),
            "bounding_boxes": [entry.get("bounding_box") for entry in detections if entry.get("bounding_box")],
            "detection_confidence": thumbnail.get("confidence"),
            "average_confidence": value.get("average_confidence"),
            "usage_count": dependencies["count"],
            "dependencies": dependencies["references"],
        })
    return {"version": "TaskGraph Object Manifest v1", "objects": objects, "categories": plain(library.categories())}


@app.get("/object-library/manifest")
def get_object_manifest():
    return object_manifest_payload()


@app.get("/object-library/objects/{object_id}/dependencies")
def get_object_dependencies(object_id: str):
    if not any(item["object_id"] == object_id for item in app.state.runtime.object_library.list()):
        raise HTTPException(404, "Object not found")
    return object_dependency_payload(object_id)

@app.get("/action-builder/state")
def get_action_builder_state(): return app.state.action_assets.load_workspace()

@app.put("/action-builder/state")
async def put_action_builder_state(request: Request):
    try: return app.state.action_assets.save_workspace(await request.json())
    except (ValueError, TypeError, json.JSONDecodeError) as exc: raise HTTPException(422, str(exc)) from exc

@app.get("/actions")
def get_actions(): return {"actions": app.state.action_assets.list_assets()}

@app.get("/actions/{action_id}")
def get_action(action_id: str):
    try: return {"action": app.state.action_assets.get_asset(action_id)}
    except KeyError as exc: raise HTTPException(404, "Action not found") from exc

@app.post("/actions")
async def create_action(request: Request):
    try:
        envelope = await request.body()
        if len(envelope) < 5:
            raise ValueError("Action Asset payload is incomplete")
        metadata_size = int.from_bytes(envelope[:4], "big")
        if metadata_size <= 0 or metadata_size > 10_000_000 or len(envelope) <= 4 + metadata_size:
            raise ValueError("Action Asset payload is invalid")
        body = json.loads(envelope[4:4 + metadata_size].decode("utf-8"))
        preview = envelope[4 + metadata_size:]
        return {"action": app.state.action_assets.create_asset(body, preview, ".webm")}
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(422, str(exc)) from exc

@app.api_route("/action-assets/{action_id}/{filename}", methods=["GET", "HEAD"])
def get_action_preview(action_id: str, filename: str):
    try:
        path = app.state.action_assets.preview_path(action_id)
    except KeyError as exc:
        raise HTTPException(404, "Action preview not found") from exc
    if filename != path.name:
        raise HTTPException(404, "Action preview not found")
    return FileResponse(path)

@app.patch("/actions/{action_id}")
async def update_action(action_id: str, request: Request):
    try: return {"action": app.state.action_assets.update_asset(action_id, await request.json())}
    except KeyError as exc: raise HTTPException(404, "Action not found") from exc
    except (ValueError, TypeError) as exc: raise HTTPException(422, str(exc)) from exc

@app.delete("/actions/{action_id}")
def delete_action(action_id: str):
    try: app.state.action_assets.delete_asset(action_id); return {"deleted": True}
    except KeyError as exc: raise HTTPException(404, "Action not found") from exc

def semantic_request(operation: str): return SemanticRequest(f"web-semantic-{operation}", f"web-semantic-{operation}", "web-api")
def sync_semantic(operation: str):
    semantic=app.state.runtime.semantic_inventory.refresh(semantic_request(operation))
    if semantic.status.value=="succeeded":
        knowledge=app.state.runtime.knowledge.rebuild(KnowledgeRequest(f"web-knowledge-{operation}",f"web-knowledge-{operation}","web-api"))
        if knowledge.status.value=="succeeded":
            affordance=app.state.runtime.affordance.rebuild(AffordanceRequest(f"web-affordance-{operation}",f"web-affordance-{operation}","web-api"))
            if affordance.status.value=="succeeded":app.state.runtime.planner.rebuild(PlannerRequest(f"web-planner-{operation}",f"web-planner-{operation}","web-api"))
    return semantic

@app.get("/semantic")
def get_semantic_inventory(): return plain(app.state.runtime.semantic_inventory.get_all_objects(semantic_request("all")).inventory)

@app.get("/semantic/statistics")
def get_semantic_statistics(): return plain(app.state.runtime.semantic_inventory.get_statistics(semantic_request("statistics")).statistics)

@app.get("/semantic/search")
def search_semantic_inventory(q: str = "", category: str = "", alias: str = "", tag: str = ""): return plain(app.state.runtime.semantic_inventory.search(semantic_request("search"), q, category, alias, tag).inventory)

@app.get("/semantic/{object_id}")
def get_semantic_object(object_id: str):
    item=app.state.runtime.semantic_inventory.get_object(semantic_request("object"), object_id).object
    if item is None: raise HTTPException(404, "Semantic object not found")
    return plain(item)

def knowledge_request(operation: str): return KnowledgeRequest(f"web-knowledge-{operation}",f"web-knowledge-{operation}","web-api")

@app.get("/knowledge")
def get_knowledge_graph(): return plain(app.state.runtime.knowledge.export_knowledge(knowledge_request("all")).export)

@app.get("/knowledge/statistics")
def get_knowledge_statistics(): return plain(app.state.runtime.knowledge.get_statistics(knowledge_request("statistics")).statistics)

@app.get("/knowledge/search")
def search_knowledge(q: str="", property: str="", fact: str="", category: str="", relationship: str=""): return plain(app.state.runtime.knowledge.search(knowledge_request("search"),q,property,fact,category,relationship).graph)

@app.get("/knowledge/categories")
def knowledge_categories(): return {"categories":plain(app.state.runtime.knowledge.get_statistics(knowledge_request("categories")).statistics.categories)}

@app.get("/knowledge/properties")
def knowledge_properties(): return {"properties":plain(app.state.runtime.knowledge.get_statistics(knowledge_request("properties")).statistics.properties)}

@app.get("/knowledge/relationships")
def knowledge_relationships():
    graph=app.state.runtime.knowledge.export_knowledge(knowledge_request("relationships")).export
    return {"relationships":[item for record in plain(graph).get("records",[]) for item in record.get("relationships",[])]}

@app.get("/knowledge/{knowledge_id:path}")
def get_knowledge_record(knowledge_id: str):
    item=app.state.runtime.knowledge.get_knowledge(knowledge_request("record"),knowledge_id).record
    if item is None:raise HTTPException(404,"Knowledge record not found")
    return plain(item)

def affordance_request(operation:str):return AffordanceRequest(f"web-affordance-{operation}",f"web-affordance-{operation}","web-api")
@app.get("/affordances")
def get_affordances():return plain(app.state.runtime.affordance.export_affordances(affordance_request("all")).export)
@app.get("/affordances/statistics")
def get_affordance_statistics():return plain(app.state.runtime.affordance.get_statistics(affordance_request("statistics")).statistics)
@app.get("/affordances/search")
def search_affordances(q:str="",capability:str="",action:str=""):return plain(app.state.runtime.affordance.search(affordance_request("search"),q,capability,action).graph)
@app.get("/affordances/actions")
def get_affordance_actions():return {"actions":plain(app.state.runtime.affordance.get_statistics(affordance_request("actions")).statistics.actions)}
@app.get("/affordances/{affordance_id:path}")
def get_affordance(affordance_id:str):
    item=app.state.runtime.affordance.get_affordance(affordance_request("record"),affordance_id).record
    if item is None:raise HTTPException(404,"Affordance Record not found")
    return plain(item)

def planner_request(operation:str):return PlannerRequest(f"web-planner-{operation}",f"web-planner-{operation}","web-api")
@app.get("/planner/plans")
def planner_plans(q:str=""):return {"plans":plain(app.state.runtime.planner.search_plans(planner_request("plans"),q).plans)}
@app.post("/planner/plans")
async def planner_create(request:Request):
    body=await request.json();response=app.state.runtime.planner.create_plan(planner_request("create"),body.get("goal",""),tuple(body.get("constraints",())))
    if response.status.value!="succeeded":raise HTTPException(422,plain(response.errors))
    return plain(response.plan)
@app.get("/planner/plans/{plan_id:path}")
def planner_plan(plan_id:str):
    response=app.state.runtime.planner.get_plan(planner_request("detail"),plan_id)
    if response.plan is None:raise HTTPException(404,"Semantic Plan not found")
    return plain(response.plan)
@app.get("/planner/statistics")
def planner_statistics():return plain(app.state.runtime.planner.get_statistics(planner_request("statistics")).statistics)
@app.get("/planner/goals")
def planner_goals(q:str=""):return {"goals":[plain(x.goal) for x in app.state.runtime.planner.search_goals(planner_request("goals"),q).plans]}
@app.post("/planner/validate/{plan_id:path}")
def planner_validate(plan_id:str):return plain(app.state.runtime.planner.validate_plan(planner_request("validate"),plan_id))
@app.post("/planner/import")
async def planner_import(request:Request):
    response=app.state.runtime.planner.import_plan(planner_request("import"),await request.json())
    if response.status.value!="succeeded":raise HTTPException(422,plain(response.errors))
    return plain(response.plan)
@app.get("/planner/export/{plan_id:path}")
def planner_export(plan_id:str):
    response=app.state.runtime.planner.export_plan(planner_request("export"),plan_id)
    if response.export is None:raise HTTPException(404,"Semantic Plan not found")
    return plain(response.export)

def taskir_request(operation: str): return TaskIRRequest(f"web-taskir-{operation}", f"web-taskir-{operation}", "web-api")

@app.get("/taskir")
def taskir_all(q: str = ""):
    return {"documents": plain(app.state.runtime.taskir.search_task_ir(taskir_request("all"), q).documents)}

@app.get("/taskir/statistics")
def taskir_statistics():
    return plain(app.state.runtime.taskir.get_statistics(taskir_request("statistics")).statistics)

@app.get("/taskir/actions")
def taskir_action_documents():
    return {"documents": plain(app.state.compiler.list_compiled())}

@app.post("/taskir/actions/{action_id}/validate")
def taskir_validate_action(action_id: str):
    try: return plain(app.state.compiler.validate(action_id))
    except KeyError as exc: raise HTTPException(404, "Action not found") from exc

@app.post("/taskir/actions/{action_id}/compile")
def taskir_compile_action(action_id: str):
    try: return {"task_ir": plain(app.state.compiler.compile(action_id))}
    except KeyError as exc: raise HTTPException(404, "Action not found") from exc
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc

@app.get("/taskir/actions/{action_id}")
def taskir_action_document(action_id: str):
    try: return {"task_ir": plain(app.state.compiler.get(action_id))}
    except KeyError as exc: raise HTTPException(404, "Compiled Action TaskIR not found") from exc

@app.post("/taskir/actions/{action_id}/move-to-execution")
def taskir_move_to_execution(action_id: str):
    try: return {"execution_task": plain(app.state.compiler.create_execution_task(action_id))}
    except KeyError as exc: raise HTTPException(404, "Compile the Action before moving it to Execution") from exc

@app.get("/execution/tasks")
def execution_tasks():
    return {"tasks": plain(app.state.packaging.list_execution_tasks())}

@app.get("/execution/tasks/{execution_task_id}")
def execution_task(execution_task_id: str):
    try: return plain(app.state.packaging.get_execution_task(execution_task_id))
    except KeyError as exc: raise HTTPException(404, "Execution Task not found") from exc

@app.api_route("/execution/tasks/{execution_task_id}/{filename}", methods=["GET", "HEAD"])
def execution_task_asset(execution_task_id: str, filename: str):
    try: return FileResponse(app.state.packaging.execution_task_asset(execution_task_id, filename))
    except KeyError as exc: raise HTTPException(404, "Execution Task asset not found") from exc

@app.post("/taskir/compile")
async def taskir_compile(request: Request):
    body = await request.json()
    source = body.get("semantic_plan")
    if source is None and body.get("plan_id"):
        source = app.state.runtime.planner.get_plan(planner_request("taskir-source"), body["plan_id"]).plan
    if source is None:
        raise HTTPException(422, "A validated semantic_plan or plan_id is required")
    response = app.state.runtime.taskir.compile(taskir_request("compile"), source)
    if response.status.value != "succeeded": raise HTTPException(422, plain(response.errors))
    return plain(response.result)

@app.post("/taskir/validate")
async def taskir_validate(request: Request):
    body = await request.json(); subject = body.get("task_id", body.get("task_ir", body))
    response = app.state.runtime.taskir.validate(taskir_request("validate"), subject)
    if response.status.value != "succeeded": raise HTTPException(422, plain(response))
    return plain(response)

@app.post("/taskir/import")
async def taskir_import(request: Request):
    response = app.state.runtime.taskir.import_task_ir(taskir_request("import"), await request.json())
    if response.status.value != "succeeded": raise HTTPException(422, plain(response.errors))
    return plain(response)

@app.get("/taskir/export")
def taskir_export(task_id: str | None = None):
    response = app.state.runtime.taskir.export_task_ir(taskir_request("export"), task_id)
    if response.status.value != "succeeded": raise HTTPException(404, plain(response.errors))
    return plain(response.export)

@app.get("/taskir/{task_id:path}")
def taskir_detail(task_id: str):
    response = app.state.runtime.taskir.get_task_ir(taskir_request("detail"), task_id)
    if response.task_ir is None: raise HTTPException(404, "TaskIR document not found")
    return plain(response.task_ir)

@app.get("/execution/robots")
def execution_robots():
    return {"robots": app.state.packaging.list_robots(), "connected": app.state.packaging.connection.connected}

@app.post("/execution/connection/connect")
def execution_connect():
    discovered = app.state.packaging.connection.discover()
    profile = app.state.packaging.store_robot(app.state.packaging.connection.connect())
    return {"connected": True, "discovered": discovered, "robot": profile}

@app.post("/execution/connection/disconnect")
def execution_disconnect():
    app.state.packaging.connection.disconnect()
    return {"connected": False}

@app.post("/execution/connection/refresh")
def execution_refresh():
    return {"connected": app.state.packaging.connection.connected, "discovered": app.state.packaging.connection.discover(), "robots": app.state.packaging.list_robots()}

@app.post("/execution/packages/preview")
async def execution_package_preview(request: Request):
    body = await request.json()
    try: return app.state.packaging.preview(body["robot_id"], body["execution_task_id"], body.get("configuration", {}))
    except KeyError as exc: raise HTTPException(404, f"Resource not found: {exc.args[0]}") from exc

@app.get("/execution/packages")
def execution_packages():
    return {"packages": app.state.packaging.list_packages()}

@app.post("/execution/packages")
async def execution_build_package(request: Request):
    body = await request.json()
    try: return app.state.packaging.build(body["robot_id"], body["execution_task_id"], body.get("configuration", {}))
    except KeyError as exc: raise HTTPException(404, f"Resource not found: {exc.args[0]}") from exc
    except (ValueError, ConnectionError) as exc: raise HTTPException(422, str(exc)) from exc

@app.post("/execution/packages/{package_id}/send")
def execution_send_package(package_id: str):
    try: return app.state.packaging.send_execution_package(package_id)
    except KeyError as exc: raise HTTPException(404, "Execution Package not found") from exc
    except ConnectionError as exc: raise HTTPException(409, str(exc)) from exc

@app.get("/execution/packages/{package_id}")
def execution_package(package_id: str):
    try: return app.state.packaging.get_package(package_id)
    except KeyError as exc: raise HTTPException(404, "Execution Package not found") from exc

def explain_request(operation: str): return ExplainabilityRequest(f"web-explain-{operation}", f"web-explain-{operation}", "web-api")

@app.get("/explain")
def explain_all(q: str = ""):
    return {"records": plain(app.state.runtime.explainability.search(explain_request("all"), q).records)}

@app.get("/explain/statistics")
def explain_statistics(): return plain(app.state.runtime.explainability.get_statistics(explain_request("statistics")).statistics)

@app.get("/explain/trace")
def explain_trace(artifact_id: str):
    response=app.state.runtime.explainability.trace_artifact(explain_request("trace"),artifact_id)
    if response.status.value!="succeeded":raise HTTPException(404,plain(response.errors))
    return plain(response)

@app.get("/explain/dependencies")
def explain_dependencies(explanation_id: str):
    response=app.state.runtime.explainability.trace_dependency(explain_request("dependencies"),explanation_id)
    if response.status.value!="succeeded":raise HTTPException(404,plain(response.errors))
    return plain(response)

@app.post("/explain/validate")
async def explain_validate(request:Request):
    body=await request.json();subject=body.get("explanation_id",body.get("explanation",body));response=app.state.runtime.explainability.validate(explain_request("validate"),subject)
    if response.status.value!="succeeded":raise HTTPException(422,plain(response))
    return plain(response)

@app.post("/explain/import")
async def explain_import(request:Request):
    response=app.state.runtime.explainability.import_records(explain_request("import"),await request.json())
    if response.status.value!="succeeded":raise HTTPException(422,plain(response.errors))
    return plain(response)

@app.get("/explain/export")
def explain_export(explanation_id:str|None=None):
    response=app.state.runtime.explainability.export(explain_request("export"),explanation_id)
    if response.status.value!="succeeded":raise HTTPException(404,plain(response.errors))
    return plain(response.export)

@app.get("/explain/{explanation_id:path}")
def explain_detail(explanation_id:str):
    response=app.state.runtime.explainability.get_explanation(explain_request("detail"),explanation_id)
    if response.record is None:raise HTTPException(404,"Explanation not found")
    return plain(response.record)


@app.api_route("/objects/{object_id}/thumbnail", methods=["GET", "HEAD"])
def get_object_thumbnail(object_id: str):
    item = next((value for value in app.state.runtime.object_library.list() if value["object_id"] == object_id), None)
    if item is None:
        raise HTTPException(404, "Object not found")
    target = Path(item.get("thumbnail", {}).get("path", "")).resolve()
    root = (ROOT / "Assets" / "ObjectLibrary" / "instances").resolve()
    if target.is_file() and target.is_relative_to(root):
        return FileResponse(target, headers={"Cache-Control": "private, max-age=300"})
    raise HTTPException(404, "Object thumbnail not found")


@app.get("/clusters")
def get_clusters():
    return cluster_payload(app.state.runtime)


@app.get("/scene")
def get_scene():
    return scene_payload(app.state.runtime)


@app.get("/health")
def get_health():
    values = collect_health(app.state.runtime)
    return {"healthy": all(item.healthy for item in values.values()), "engines": plain(values)}


@app.get("/validation")
def get_validation():
    checks = app.state.validation
    return {"passed": all(item.passed for item in checks), "checks": plain(checks)}


@app.get("/reports")
def get_reports():
    report = ROOT / "Assets" / "TaskGraph_Runtime_Report.json"
    return {
        "available": report.is_file(),
        "runtime": json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {},
        "formats": ["json", "pdf", "markdown"],
    }


@app.get("/detections")
def get_detections():
    return detection_payload(app.state.runtime)


VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
MAX_VIDEO_BYTES = 2 * 1024 * 1024 * 1024

@app.post("/video/validate")
async def validate_video(request: Request, filename: str):
    workspace = app.state.runtime.video_workspace
    if workspace.web_extraction.get("state") == "extracting":
        raise HTTPException(409, "Cancel the current extraction before importing another video.")
    suffix = Path(filename).suffix.lower()
    if suffix not in VIDEO_EXTENSIONS: raise HTTPException(415, "Unsupported video format. Use MP4, AVI, MOV, MKV, or WebM.")
    upload_dir = ROOT / ".taskgraph-session" / "video"
    upload_dir.mkdir(parents=True, exist_ok=True)
    staging = upload_dir / f"uploading{suffix}"
    size = 0
    try:
        with staging.open("wb") as stream:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_VIDEO_BYTES: raise HTTPException(413, "Video exceeds the 2 GB project limit.")
                stream.write(chunk)
        if size == 0: raise HTTPException(422, "The selected video is empty.")
        try: workspace.inspect(staging)
        except ValueError as exc: raise HTTPException(422, str(exc)) from exc
        if not workspace.cancel(wait=True): raise HTTPException(409, "The previous extraction worker did not stop safely.")
        target = upload_dir / f"source-{uuid4().hex}{suffix}"
        old_source = workspace.source_path
        staging.replace(target)
        metadata = workspace.accept_source(target, Path(filename).name)
        if old_source and old_source != target: old_source.unlink(missing_ok=True)
        publish_runtime()
        return {"validated": True, "metadata": plain(metadata), "source_url": f"/video/source?v={target.stat().st_mtime_ns}"}
    finally:
        if staging.is_file(): staging.unlink()

@app.post("/video/extract")
def extract_video(interval: float = 1.0):
    if not (0.01 <= interval <= 3600): raise HTTPException(422, "Frame interval must be between 0.01 and 3600 seconds.")
    workspace = app.state.runtime.video_workspace
    if workspace.web_extraction.get("state") == "extracting": raise HTTPException(409, "Frame extraction is already running.")
    state = {"state": "extracting", "current": 0, "total": 0, "eta": 0.0, "frame": None, "extraction_duration": 0.0, "error": None}
    workspace.web_extraction = state
    workspace.persist_state()

    def progress(current, total, eta, frame):
        state.update(state="extracting", current=min(current, total), total=total, eta=max(0.0, eta), frame=frame)
        workspace.persist_state()
        publish_runtime()

    def done(completed, error, elapsed):
        final_state = "complete" if completed else "error" if error else "cancelled"
        count = len(workspace.frames)
        state.update(state=final_state, current=count if completed else state["current"], total=count if completed else state["total"], eta=0.0, error=error, extraction_duration=elapsed)
        if completed:
            workspace.results, workspace.errors = {}, []
            workspace.current_object, workspace.current_confidence = None, None
            workspace.web_detection = {"state": "idle", "current": 0, "total": 0, "eta": 0.0, "frames": {}, "metrics": {}}
            workspace.web_clusters = {"renamed": {}, "ignored": [], "deleted": [], "accepted": [], "selected": [], "expanded": [], "generated": [], "clustering": {"state": "idle", "progress": 0, "error": None}}
            manifest = ensure_frame_manifest(app.state.runtime)
            first_id = manifest["frames"][0]["frame_id"] if manifest["frames"] else None
            workspace.web_frame_review = {"current_frame_id": first_id, "selected_frame_ids": [first_id] if first_id else []}
        workspace.persist_state()
        publish_runtime()
    try: workspace.extract_async(1.0 / interval, progress, done)
    except (ValueError, RuntimeError) as exc:
        state.update(state="error", error=str(exc))
        workspace.persist_state()
        raise HTTPException(409 if isinstance(exc, RuntimeError) else 422, str(exc)) from exc
    return {"accepted": True, "state": state}

@app.post("/video/cancel")
def cancel_video_extraction():
    workspace = app.state.runtime.video_workspace
    if workspace.web_extraction.get("state") != "extracting": return {"cancelled": False, "state": workspace.web_extraction.get("state", "ready")}
    stopped = workspace.cancel(wait=True)
    if not stopped: raise HTTPException(409, "Extraction worker did not stop within the safety timeout.")
    return {"cancelled": True, "state": workspace.web_extraction.get("state", "cancelled")}

@app.api_route("/video/source", methods=["GET", "HEAD"])
def video_source():
    source = app.state.runtime.video_workspace.source_path
    if not source or not source.is_file(): raise HTTPException(404, "No validated video is available.")
    return FileResponse(source)

@app.delete("/video/source")
def remove_video_source():
    workspace = app.state.runtime.video_workspace
    if workspace.web_extraction.get("state") == "extracting": raise HTTPException(409, "Cancel extraction before removing the video.")
    source = workspace.source_path
    if source and source.is_file(): source.unlink()
    workspace.source_path, workspace.metadata = None, None
    workspace.web_extraction = {"state": "idle", "current": 0, "total": 0, "eta": 0.0, "frame": None}
    workspace.persist_state()
    publish_runtime()
    return {"removed": True}


@app.get("/frame-workspace")
def get_frame_workspace():
    return frame_workspace_payload(app.state.runtime)


@app.patch("/frame-workspace/review")
async def update_frame_review(request: Request):
    try:
        body = await request.json()
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(400, "Review state must be valid JSON.") from exc
    if not isinstance(body, dict):
        raise HTTPException(422, "Review state must be a JSON object.")
    payload = frame_workspace_payload(app.state.runtime)
    valid_ids = {item["frame_id"] for item in payload["frames"]}
    current = body.get("current_frame_id")
    selected = body.get("selected_frame_ids", [])
    if current is not None and current not in valid_ids:
        raise HTTPException(422, "Current frame is not present in the active frame manifest.")
    if not isinstance(selected, list) or any(item not in valid_ids for item in selected):
        raise HTTPException(422, "Selection contains a frame outside the active frame manifest.")
    app.state.runtime.video_workspace.web_frame_review = {
        "current_frame_id": current,
        "selected_frame_ids": list(dict.fromkeys(selected)),
    }
    persist_frame_review(app.state.runtime)
    return {"saved": True, "review": app.state.runtime.video_workspace.web_frame_review}


@app.get("/frame-workspace/frames/{frame_id}")
def get_workspace_frame(frame_id: str, variant: str = "raw"):
    payload = frame_workspace_payload(app.state.runtime)
    frame = next((item for item in payload["frames"] if item["frame_id"] == frame_id), None)
    if frame is None:
        raise HTTPException(404, "Frame is not present in the active frame manifest.")
    raw = ROOT / "Workspace" / "Frames" / Path(frame["filename"]).name
    detected = ROOT / "Workspace" / "Frames" / "Detected" / Path(frame["filename"]).name
    if variant not in {"raw", "annotated"}:
        raise HTTPException(422, "Frame variant must be raw or annotated.")
    target = detected if variant == "annotated" and detected.is_file() else raw
    if not _frame_file_available(target):
        raise HTTPException(422 if target.is_file() else 404, "Frame image is missing, corrupt, or unavailable.")
    return FileResponse(target, headers={"Cache-Control": "no-cache"})


def publish(channel: str, payload: dict[str, Any]):
    for queue in tuple(getattr(app.state, f"{channel}_subscribers")):
        app.state.loop.call_soon_threadsafe(queue.put_nowait, payload)


def require_cluster(cluster_id: str) -> dict[str, Any]:
    cluster = next((item for item in cluster_payload(app.state.runtime)["clusters"] if item["id"] == cluster_id), None)
    if cluster is None:
        raise HTTPException(404, "Cluster not found in current session")
    return cluster


@app.patch("/clusters/rename")
async def rename_cluster(request: Request):
    body = await request.json(); cluster = require_cluster(body.get("cluster_id", "")); name = str(body.get("name", "")).strip()
    if not name: raise HTTPException(422, "Cluster name is required")
    app.state.runtime.video_workspace.web_clusters["renamed"][cluster["id"]] = name
    publish("cluster", cluster_payload(app.state.runtime)); return {"updated": True}


@app.post("/clusters/ignore")
async def ignore_cluster(request: Request):
    body = await request.json(); cluster = require_cluster(body.get("cluster_id", "")); app.state.runtime.video_workspace.web_clusters["ignored"].append(cluster["id"])
    publish("cluster", cluster_payload(app.state.runtime)); return {"ignored": True}


@app.post("/clusters/delete")
async def delete_cluster(request: Request):
    body = await request.json(); cluster = require_cluster(body.get("cluster_id", "")); app.state.runtime.video_workspace.web_clusters["deleted"].append(cluster["id"])
    publish("cluster", cluster_payload(app.state.runtime)); publish("runtime", runtime_payload(app.state.runtime)); return {"deleted": True}


@app.post("/objects/create")
async def create_object(request: Request):
    body = await request.json(); cluster = require_cluster(body.get("cluster_id", "")); dataset_id = uuid4().hex
    dataset = ROOT / "Assets" / "ObjectLibrary" / "instances" / dataset_id; dataset.mkdir(parents=True, exist_ok=True)
    saved = []
    for instance in cluster["instances"]:
        source = ROOT / "Workspace" / "Frames" / "Detected" / f"frame{instance['frame']:04d}.png"
        if not source.is_file(): source = ROOT / "Workspace" / "Frames" / f"frame{instance['frame']:04d}.png"
        if source.is_file():
            target = dataset / source.name; shutil.copy2(source, target); saved.append(str(target))
    if not saved: raise HTTPException(422, "Cluster has no valid instance images")
    representative = cluster["instances"][0]
    result = app.state.runtime.video_workspace.results.get(representative["frame"] - 1)
    visual = next((item for item in result[1].objects if item.candidate_id == representative["tracking_id"]), None) if result else None
    descriptors = tuple((item.name, tuple(item.values)) for item in visual.features) if visual else ()
    region = representative["bounding_box"]
    crop = {"path": saved[0], "frame_id": f"video-frame-{representative['frame']}", "x": region["x"], "y": region["y"], "width": region["width"], "height": region["height"], "instance_images": saved}
    fields = {"name": str(body.get("name", "")).strip(), "description": str(body.get("description", "")).strip(), "category": str(body.get("category", "")).strip(), "notes": str(body.get("notes", "")).strip(), "tags": str(body.get("tags", "")).strip(), "confidence": cluster["confidence"]}
    if not fields["name"]: raise HTTPException(422, "Object name is required")
    before = {item["object_id"] for item in app.state.runtime.object_library.list()}
    try: app.state.runtime.object_library.create(fields, crop, descriptors)
    except ValueError as exc: shutil.rmtree(dataset, ignore_errors=True); raise HTTPException(409, str(exc)) from exc
    created = next(item for item in app.state.runtime.object_library.list() if item["object_id"] not in before)
    app.state.runtime.video_workspace.web_clusters["accepted"].append(cluster["id"])
    sync_semantic("object-created")
    publish("object", {"objects": plain(app.state.runtime.object_library.list())}); publish("cluster", cluster_payload(app.state.runtime))
    return {"created": plain(created)}


@app.post("/objects/from-cluster")
async def create_semantic_object(request: Request):
    body=await request.json();cluster=require_cluster(body.get("cluster_id",""))
    try:created=ObjectLibraryService(app.state.runtime.object_library).create_from_cluster(cluster,body)
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc
    app.state.runtime.video_workspace.web_clusters["accepted"].append(cluster["id"]);sync_semantic("object-created")
    publish("object",{"objects":plain(app.state.runtime.object_library.list())});publish("cluster",cluster_payload(app.state.runtime))
    return {"created":plain(created)}


@app.patch("/objects/edit")
async def edit_object(request: Request):
    try:
        body = await request.json()
        if not isinstance(body, dict): raise ValueError("Object edit payload must be an object")
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(422, "Object edit payload is invalid") from exc
    object_id = str(body.pop("object_id", ""))
    try:
        response = app.state.runtime.object_library.update(object_id, body)
        if getattr(response.status, "value", response.status) != "succeeded": raise RuntimeError("Object persistence failed")
    except KeyError as exc: raise HTTPException(404, "Object not found") from exc
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc: raise HTTPException(503, str(exc)) from exc
    sync_semantic("object-edited")
    payload = object_manifest_payload()
    publish("object", {"objects": plain(app.state.runtime.object_library.list())})
    return {"object": next(item for item in payload["objects"] if item["object_id"] == object_id), "manifest": payload}


def replace_object_references(object_id: str, replacement_id: str):
    def replace(value):
        if isinstance(value, dict): return {key: replace(item) for key, item in value.items()}
        if isinstance(value, list): return [replace(item) for item in value]
        return replacement_id if value == object_id else value
    paths = [ROOT / "Assets" / "Actions" / "builder_state.json"]
    for directory, pattern in (
        (ROOT / "Assets" / "Actions", "*.action"),
        (ROOT / "Assets" / "TaskIR", "*.json"),
        (ROOT / "Assets" / "Execution Tasks", "*.json"),
        (ROOT / "Assets" / "ExecutionPackages", "*.json"),
    ):
        if directory.is_dir(): paths.extend(directory.rglob(pattern))
    for path in dict.fromkeys(paths):
        if not path.is_file(): continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        replaced = replace(value)
        if replaced == value: continue
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(replaced, indent=2), encoding="utf-8")
        temporary.replace(path)


def delete_object_record(object_id: str):
    item = next((value for value in app.state.runtime.object_library.list() if value["object_id"] == object_id), None)
    if item is None: raise HTTPException(404, "Object not found")
    dataset = Path(item.get("thumbnail", {}).get("path", "")).parent.resolve()
    permanent_instances = (ROOT / "Assets" / "ObjectLibrary" / "instances").resolve()
    response = app.state.runtime.object_library.delete(object_id)
    if getattr(response.status, "value", response.status) != "succeeded":
        raise HTTPException(503, "Object persistence failed; no assets were removed")
    if dataset.parent == permanent_instances and dataset.is_dir():
        try: shutil.rmtree(dataset)
        except OSError as exc: raise HTTPException(503, f"Object record deleted but dataset cleanup failed: {exc}") from exc


@app.delete("/objects/{object_id}")
def delete_object(object_id: str, force: bool = False, replacement_id: str = ""):
    dependencies = object_dependency_payload(object_id)
    if replacement_id:
        if replacement_id == object_id or not any(item["object_id"] == replacement_id for item in app.state.runtime.object_library.list()):
            raise HTTPException(422, "Replacement object is invalid")
        replace_object_references(object_id, replacement_id)
    elif dependencies["count"] and not force:
        raise HTTPException(409, {"message": "Object is referenced by downstream assets", **dependencies})
    delete_object_record(object_id)
    sync_semantic("object-deleted")
    publish("object", {"objects": plain(app.state.runtime.object_library.list())})
    return {"deleted": True, "manifest": object_manifest_payload()}


@app.post("/object-library/objects/{object_id}/duplicate")
def duplicate_object(object_id: str):
    library = app.state.runtime.object_library
    source = next((plain(item) for item in library.list() if item["object_id"] == object_id), None)
    if source is None: raise HTTPException(404, "Object not found")
    name_root = f"{source['name']} Copy"
    names = {str(item["name"]).casefold() for item in library.list()}
    name = name_root
    suffix = 2
    while name.casefold() in names:
        name = f"{name_root} {suffix}"; suffix += 1
    crop = dict(source.get("thumbnail") or {})
    original = Path(crop.get("path", "")).parent
    target = ROOT / "Assets" / "ObjectLibrary" / "instances" / uuid4().hex
    if original.is_dir():
        shutil.copytree(original, target)
        def remap(value):
            if isinstance(value, str):
                try:
                    relative = Path(value).relative_to(original)
                    return str(target / relative)
                except ValueError:
                    return value
            if isinstance(value, list): return [remap(item) for item in value]
            return value
        crop = {key: remap(value) for key, value in crop.items()}
    fields = {key: source.get(key, "") for key in ("category", "type", "material", "color", "weight", "description", "tags", "notes", "aliases", "properties", "metadata")}
    fields["name"] = name
    fields["confidence"] = source.get("average_confidence", 0)
    try:
        before = {item["object_id"] for item in library.list()}
        response = library.create(fields, crop, ())
        if getattr(response.status, "value", response.status) != "succeeded": raise RuntimeError("Object persistence failed")
        created = next(item["object_id"] for item in library.list() if item["object_id"] not in before)
    except Exception:
        if target.is_dir(): shutil.rmtree(target, ignore_errors=True)
        raise
    sync_semantic("object-duplicated")
    publish("object", {"objects": plain(library.list())})
    payload = object_manifest_payload()
    return {"object": next(item for item in payload["objects"] if item["object_id"] == created), "manifest": payload}


@app.post("/object-library/objects/bulk-delete")
async def bulk_delete_objects(request: Request):
    try:
        body = await request.json()
        object_ids = list(dict.fromkeys(str(item) for item in body.get("object_ids", ()) if str(item)))
        force = bool(body.get("force", False))
    except (ValueError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        raise HTTPException(422, "Bulk delete payload is invalid") from exc
    blocked = [object_dependency_payload(item) for item in object_ids]
    blocked = [item for item in blocked if item["count"]]
    if blocked and not force: raise HTTPException(409, {"message": "Objects are referenced by downstream assets", "blocked": blocked})
    for object_id in object_ids: delete_object_record(object_id)
    sync_semantic("objects-bulk-deleted")
    publish("object", {"objects": plain(app.state.runtime.object_library.list())})
    return {"deleted": object_ids, "manifest": object_manifest_payload()}


@app.post("/object-library/categories")
async def create_object_category(request: Request):
    try: category = app.state.runtime.object_library.create_category((await request.json()).get("name"))
    except (ValueError, TypeError, AttributeError, json.JSONDecodeError) as exc: raise HTTPException(422, str(exc)) from exc
    return {"category": plain(category), "manifest": object_manifest_payload()}


@app.patch("/object-library/categories/{category_id}")
async def rename_object_category(category_id: str, request: Request):
    try: category = app.state.runtime.object_library.rename_category(category_id, (await request.json()).get("name"))
    except KeyError as exc: raise HTTPException(404, "Category not found") from exc
    except (ValueError, TypeError, AttributeError, json.JSONDecodeError) as exc: raise HTTPException(422, str(exc)) from exc
    publish("object", {"objects": plain(app.state.runtime.object_library.list())})
    return {"category": plain(category), "manifest": object_manifest_payload()}


@app.delete("/object-library/categories/{category_id}")
def delete_object_category(category_id: str, replacement: str = ""):
    try: app.state.runtime.object_library.delete_category(category_id, replacement)
    except KeyError as exc: raise HTTPException(404, "Category not found") from exc
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    publish("object", {"objects": plain(app.state.runtime.object_library.list())})
    return {"deleted": True, "manifest": object_manifest_payload()}


def detection_log(message: str):
    folder = ROOT / "Logs"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "detection.log").open("a", encoding="utf-8") as stream:
        stream.write(f"{datetime.now().isoformat(timespec='milliseconds')} {message}\n")


def publish_runtime():
    persist_frame_review(app.state.runtime)
    payload = runtime_payload(app.state.runtime)
    for queue in tuple(app.state.runtime_subscribers):
        app.state.loop.call_soon_threadsafe(queue.put_nowait, payload)


@app.post("/detection/run-legacy", include_in_schema=False)
def run_detection_legacy():
    runtime = app.state.runtime
    workspace = runtime.video_workspace
    if getattr(workspace, "web_detection", {}).get("state") == "running":
        return {"accepted": False, "reason": "Detection is already running"}
    if not workspace.frames:
        return {"accepted": False, "reason": "No extracted frames"}
    total = len(workspace.frames)
    started = monotonic()
    state = {"state": "running", "phase": "warming_up", "current": 0, "current_label": "Loading YOLO model", "total": total, "eta": 0.0, "frame": 0, "frames": {str(index): {"status": "waiting", "labels": [], "overlay_ready": False} for index in range(1, total + 1)}, "metrics": {"processed": 0, "failed": 0, "skipped": 0, "detected_objects": 0, "average_inference_ms": 0.0, "inference_ms": 0.0, "fps": 0.0}, "inference_samples": []}
    workspace.web_detection = state
    detection_log(f"BATCH START model={runtime.perception.detector_status().get('current')} device={runtime.perception.detector_status().get('device')} frames={total}")

    def progress(current, count, eta, frame_name):
        state.update(current=current, total=count, eta=eta, frame=current, frame_name=frame_name)
        publish_runtime()

    def frame_started(number, frame_name):
        state.update(phase="detecting", current=number, frame=number, frame_name=frame_name, current_label="Scanning")
        state["frames"][str(number)] = {"status": "processing", "labels": [], "overlay_ready": False}
        detection_log(f"FRAME {number} STARTED")
        publish_runtime()

    def frame_done(index, elapsed_ms):
        number = index + 1
        failed = next((error for error in workspace.errors if error.get("frame") == number), None)
        result = workspace.results.get(index)
        labels = [{"class_name": item.properties.get("ai_class") or "Object", "confidence": item.confidence, "object_id": item.candidate_id, "x": item.region.x, "y": item.region.y, "width": item.region.width, "height": item.region.height} for item in result[1].objects] if result else []
        status = "error" if failed else "detected" if labels else "no_detection"
        state["frames"][str(number)] = {"status": status, "labels": labels, "overlay_ready": bool(result and Path(result[3]).is_file()), "overlay": f"/frames/{Path(result[3]).name}" if result else None}
        elapsed = max(0.001, monotonic() - started)
        processed = sum(value["status"] in {"detected", "no_detection", "error"} for value in state["frames"].values())
        failures = sum(value["status"] == "error" for value in state["frames"].values())
        inference_ms = float(elapsed_ms)
        state["inference_samples"].append(inference_ms)
        average_inference = sum(state["inference_samples"]) / max(1, len(state["inference_samples"]))
        detected_objects = sum(len(value.get("labels", [])) for value in state["frames"].values())
        state["metrics"].update(processed=processed, failed=failures, skipped=0, detected_objects=detected_objects, average_inference_ms=average_inference, inference_ms=inference_ms, fps=processed / elapsed)
        state.update(current=number, frame=number, current_label=labels[0]["class_name"] if labels else "No object")
        objects = len(result[1].objects) if result else 0
        overlay = str(result[3]) if result else "none"
        if failed:
            detection_log(f"FRAME {number} ERROR inference_ms={inference_ms:.1f} exception={failed.get('message')}")
        else:
            summary = ", ".join(f"{item['class_name']}:{item['confidence']:.3f}" for item in labels) or "none"
            detection_log(f"FRAME {number} FINISHED inference_ms={inference_ms:.1f} objects={objects} labels={summary} overlay={overlay} websocket=published")
        publish_runtime()

    def done(completed, error):
        elapsed = max(0.001, monotonic() - started)
        state.update(state="complete" if completed else "error" if error else "cancelled", phase="complete" if completed else "stopped", current=total if completed else state["current"], frame=total if completed else state["frame"], eta=0.0)
        state["metrics"].update(total_runtime_seconds=elapsed, gpu=plain(accelerator_diagnostics()))
        detection_log(f"BATCH {'COMPLETE' if completed else 'CANCELLED'} processed={state['metrics']['processed']} failed={state['metrics']['failed']} fps={state['metrics']['fps']:.3f} error={error}")
        publish_runtime()

    workspace.detect_async(frame_started, progress, frame_done, done)
    publish_runtime()
    return {"accepted": True, "frames": total}


@app.post("/detection/run")
def run_detection():
    workspace=app.state.runtime.video_workspace
    if getattr(workspace,"web_detection",{}).get("state")=="running":return {"accepted":False,"reason":"Detection is already running"}
    try:state=FrameProcessingService(app.state.runtime,detection_log,publish_runtime).run()
    except ValueError as exc:return {"accepted":False,"reason":str(exc)}
    completed=state.get("state") in {"complete","partial"}
    return {"accepted":completed,"frames":len(workspace.frames),"detection":plain(state),"reason":None if completed else state.get("error") or f"Detection {state.get('state', 'failed')}"}


@app.post("/detection/cancel")
def cancel_detection():
    workspace = app.state.runtime.video_workspace
    if getattr(workspace, "web_detection", {}).get("state") != "running":
        return {"cancelled": False, "state": getattr(workspace, "web_detection", {}).get("state", "idle")}
    workspace.cancel(wait=False)
    return {"cancelled": True, "state": "cancelling"}


@app.get("/frame-workspace/clusters")
def get_frame_clusters():
    return frame_cluster_payload(app.state.runtime)


@app.post("/frame-workspace/clusters/generate")
def generate_frame_clusters():
    workspace = app.state.runtime.video_workspace
    review = workspace.web_clusters
    if review.get("clustering", {}).get("state") == "running":
        raise HTTPException(409, "Cluster generation is already running.")
    detections = detection_payload(app.state.runtime)["detections"]
    if not workspace.frames:
        raise HTTPException(422, "No extracted frames are available for clustering.")
    if not detections:
        raise HTTPException(422, "No object detections are available. Run YOLO before generating clusters.")
    review["clustering"] = {"state": "running", "progress": 10, "error": None}
    persist_frame_review(app.state.runtime)
    try:
        generated = ClusterEngine().build(detections)
        created = datetime.now().isoformat(timespec="seconds")
        for cluster in generated:
            cluster.update(
                created_at=created,
                review_state="pending",
                embedding_dimensions=max((len(item.get("embedding", [])) for item in cluster.get("instances", [])), default=0),
            )
        review.update(
            generated=generated,
            renamed={},
            ignored=[],
            deleted=[],
            accepted=[],
            selected=[],
            expanded=[generated[0]["id"]] if generated else [],
            clustering={"state": "complete", "progress": 100, "error": None},
        )
        persist_frame_review(app.state.runtime)
        payload = frame_cluster_payload(app.state.runtime)
        publish("cluster", payload)
        return payload
    except Exception as exc:
        review["clustering"] = {"state": "failed", "progress": 0, "error": str(exc)}
        persist_frame_review(app.state.runtime)
        raise HTTPException(500, f"Cluster generation failed: {exc}") from exc


@app.patch("/frame-workspace/clusters/review")
async def update_frame_cluster_review(request: Request):
    body = await request.json()
    review = app.state.runtime.video_workspace.web_clusters
    valid_ids = {item["id"] for item in review.get("generated", []) if item["id"] not in review.get("deleted", [])}
    selected = body.get("selected_cluster_ids", review.get("selected", []))
    expanded = body.get("expanded_cluster_ids", review.get("expanded", []))
    if not isinstance(selected, list) or any(item not in valid_ids for item in selected):
        raise HTTPException(422, "Cluster selection contains an unknown cluster.")
    if not isinstance(expanded, list) or any(item not in valid_ids for item in expanded):
        raise HTTPException(422, "Expanded cluster state contains an unknown cluster.")
    review["selected"] = list(dict.fromkeys(selected))
    review["expanded"] = list(dict.fromkeys(expanded))
    persist_frame_review(app.state.runtime)
    return frame_cluster_payload(app.state.runtime)


@app.patch("/frame-workspace/clusters/{cluster_id}")
async def rename_frame_cluster(cluster_id: str, request: Request):
    body = await request.json()
    review = app.state.runtime.video_workspace.web_clusters
    cluster = next((item for item in review.get("generated", []) if item["id"] == cluster_id and cluster_id not in review.get("deleted", [])), None)
    if cluster is None:
        raise HTTPException(404, "Cluster not found.")
    name = str(body.get("name", "")).strip()
    if not name:
        raise HTTPException(422, "Cluster name is required.")
    review["renamed"][cluster_id] = name
    persist_frame_review(app.state.runtime)
    return frame_cluster_payload(app.state.runtime)


@app.post("/frame-workspace/clusters/merge")
async def merge_frame_clusters(request: Request):
    body = await request.json()
    ids = list(dict.fromkeys(body.get("cluster_ids", [])))
    review = app.state.runtime.video_workspace.web_clusters
    sources = [item for item in review.get("generated", []) if item["id"] in ids and item["id"] not in review.get("deleted", [])]
    if len(ids) < 2 or len(sources) != len(ids):
        raise HTTPException(422, "Select at least two valid clusters to merge.")
    instances = [instance for source in sources for instance in source.get("instances", [])]
    merged_id = f"cluster-merged-{uuid4().hex[:10]}"
    confidence = sum(float(item.get("confidence", 0.0)) for item in instances) / max(1, len(instances))
    representatives = list(dict.fromkeys(item["frame"] for item in sorted(instances, key=lambda item: float(item.get("confidence", 0.0)), reverse=True)))[:4]
    merged = {
        "id": merged_id,
        "name": str(body.get("name") or " + ".join(review["renamed"].get(item["id"], item["name"]) for item in sources)),
        "instances": instances,
        "frame_count": len({item["frame"] for item in instances}),
        "confidence": confidence,
        "representative_frames": representatives,
        "bounding_box_statistics": {
            "average_width": sum(item["bounding_box"]["width"] for item in instances) / max(1, len(instances)),
            "average_height": sum(item["bounding_box"]["height"] for item in instances) / max(1, len(instances)),
        },
        "status": "pending",
        "review_state": "pending",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "embedding_dimensions": max((len(item.get("embedding", [])) for item in instances), default=0),
    }
    review["generated"] = [item for item in review["generated"] if item["id"] not in ids] + [merged]
    review["selected"] = [merged_id]
    review["expanded"] = [merged_id]
    persist_frame_review(app.state.runtime)
    return frame_cluster_payload(app.state.runtime)


@app.post("/frame-workspace/clusters/{cluster_id}/split")
def split_frame_cluster(cluster_id: str):
    review = app.state.runtime.video_workspace.web_clusters
    source = next((item for item in review.get("generated", []) if item["id"] == cluster_id and cluster_id not in review.get("deleted", [])), None)
    if source is None:
        raise HTTPException(404, "Cluster not found.")
    instances = source.get("instances", [])
    if len(instances) < 2:
        raise HTTPException(422, "Cluster needs at least two detected objects to split.")
    partitions = (instances[::2], instances[1::2])
    children = []
    for position, group in enumerate(partitions, 1):
        child_id = f"{cluster_id}-split-{uuid4().hex[:8]}"
        children.append({
            **source,
            "id": child_id,
            "name": f"{review['renamed'].get(cluster_id, source['name'])} {position}",
            "instances": group,
            "frame_count": len({item["frame"] for item in group}),
            "confidence": sum(float(item.get("confidence", 0.0)) for item in group) / len(group),
            "representative_frames": list(dict.fromkeys(item["frame"] for item in sorted(group, key=lambda item: float(item.get("confidence", 0.0)), reverse=True)))[:4],
            "created_at": datetime.now().isoformat(timespec="seconds"),
        })
    review["generated"] = [item for item in review["generated"] if item["id"] != cluster_id] + children
    review["selected"] = [item["id"] for item in children]
    review["expanded"] = [children[0]["id"]]
    persist_frame_review(app.state.runtime)
    return frame_cluster_payload(app.state.runtime)


@app.delete("/frame-workspace/clusters/{cluster_id}")
def delete_frame_cluster(cluster_id: str):
    review = app.state.runtime.video_workspace.web_clusters
    if not any(item["id"] == cluster_id for item in review.get("generated", [])):
        raise HTTPException(404, "Cluster not found.")
    if cluster_id not in review["deleted"]:
        review["deleted"].append(cluster_id)
    review["selected"] = [item for item in review.get("selected", []) if item != cluster_id]
    review["expanded"] = [item for item in review.get("expanded", []) if item != cluster_id]
    persist_frame_review(app.state.runtime)
    return frame_cluster_payload(app.state.runtime)


@app.post("/frame-workspace/clusters/handoff")
async def handoff_frame_clusters(request: Request):
    body = await request.json()
    ids = list(dict.fromkeys(body.get("cluster_ids", [])))
    review = app.state.runtime.video_workspace.web_clusters
    clusters = [item for item in review.get("generated", []) if item["id"] in ids and item["id"] not in review.get("deleted", [])]
    if not ids or len(clusters) != len(ids):
        raise HTTPException(422, "Select one or more valid clusters to send to Object Library.")
    manifest = {item["ordinal"]: item for item in frame_workspace_payload(app.state.runtime)["frames"]}
    service = ObjectLibraryService(app.state.runtime.object_library)
    created, errors = [], []
    for cluster in clusters:
        name = review["renamed"].get(cluster["id"], cluster["name"])
        enriched_instances = []
        for instance in cluster.get("instances", []):
            frame = manifest.get(int(instance["frame"]))
            enriched_instances.append({**instance, "frame_id": frame["frame_id"] if frame else f"video-frame-{instance['frame']}"})
        enriched = {**cluster, "name": name, "instances": enriched_instances}
        metadata = {
            "cluster_id": cluster["id"],
            "cluster_name": name,
            "frame_ids": [item["frame_id"] for item in enriched_instances],
            "detections": plain(enriched_instances),
            "review_state": "accepted",
        }
        try:
            created.append(service.create_from_cluster(enriched, {"name": name, "metadata": metadata}))
            if cluster["id"] not in review["accepted"]:
                review["accepted"].append(cluster["id"])
        except Exception as exc:
            errors.append({"cluster_id": cluster["id"], "message": str(exc)})
    review["selected"] = [item for item in review.get("selected", []) if item not in {cluster["id"] for cluster in clusters if cluster["id"] in review["accepted"]}]
    persist_frame_review(app.state.runtime)
    if not created:
        raise HTTPException(422, {"message": "No selected clusters could be imported.", "errors": errors})
    sync_semantic("cluster-handoff")
    publish("object", {"objects": plain(app.state.runtime.object_library.list())})
    publish("cluster", frame_cluster_payload(app.state.runtime))
    return {"created": plain(created), "errors": errors, "clusters": frame_cluster_payload(app.state.runtime)}


@app.post("/clusters/build")
def build_clusters():
    review=app.state.runtime.video_workspace.web_clusters
    review["generated"]=ClusterEngine().build(detection_payload(app.state.runtime)["detections"])
    payload=cluster_payload(app.state.runtime);publish("cluster",payload);return payload


@app.post("/clusters/merge")
async def merge_clusters(request:Request):
    body=await request.json();review=app.state.runtime.video_workspace.web_clusters;generated=review.get("generated",[]);source=next((x for x in generated if x["id"]==body.get("cluster_id")),None)
    target=next((x for x in generated if source and x["id"]!=source["id"]),None)
    if source is None or target is None:raise HTTPException(422,"Two clusters are required to merge")
    instances=source["instances"]+target["instances"];source.update(name=body.get("name") or source["name"],instances=instances,frame_count=len({x["frame"] for x in instances}),confidence=sum(x["confidence"] for x in instances)/len(instances),representative_frames=list(dict.fromkeys(x["frame"] for x in instances))[:4]);generated.remove(target)
    payload=cluster_payload(app.state.runtime);publish("cluster",payload);return payload


@app.post("/clusters/split")
async def split_cluster(request:Request):
    body=await request.json();review=app.state.runtime.video_workspace.web_clusters;generated=review.get("generated",[]);source=next((x for x in generated if x["id"]==body.get("cluster_id")),None)
    if source is None or len(source["instances"])<2:raise HTTPException(422,"Cluster needs at least two detections to split")
    left,right=source["instances"][::2],source["instances"][1::2];source["instances"]=left;source["frame_count"]=len({x["frame"] for x in left});source["confidence"]=sum(x["confidence"] for x in left)/len(left);copy={**source,"id":f"{source['id']}-split","name":f"{source['name']} Split","instances":right,"frame_count":len({x['frame'] for x in right}),"confidence":sum(x["confidence"] for x in right)/len(right),"representative_frames":list(dict.fromkeys(x["frame"] for x in right))[:4]};generated.append(copy)
    payload=cluster_payload(app.state.runtime);publish("cluster",payload);return payload


@app.get("/frames/{name}")
def get_frame(name: str):
    detected = (ROOT / "Workspace" / "Frames" / "Detected" / Path(name).name).resolve()
    raw = (ROOT / "Workspace" / "Frames" / Path(name).name).resolve()
    target = detected if detected.is_file() else raw
    if target.is_file():
        return FileResponse(target)
    return FileResponse(ROOT / "Assets" / "Screenshots" / "README.md", media_type="text/plain", status_code=404)


async def stream(websocket: WebSocket, projection, interval: float = 1.0):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(projection(app.state.runtime))
            await asyncio.sleep(interval)
    except (WebSocketDisconnect, RuntimeError):
        return


@app.websocket("/ws/runtime")
async def ws_runtime(websocket: WebSocket):
    await websocket.accept()
    queue = asyncio.Queue()
    app.state.runtime_subscribers.add(queue)
    try:
        await websocket.send_json(runtime_payload(app.state.runtime))
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                payload = runtime_payload(app.state.runtime)
            await websocket.send_json(payload)
    except (WebSocketDisconnect, RuntimeError):
        return
    finally:
        app.state.runtime_subscribers.discard(queue)


@app.websocket("/ws/scene")
async def ws_scene(websocket: WebSocket):
    await stream(websocket, scene_payload)


@app.websocket("/ws/detections")
async def ws_detections(websocket: WebSocket):
    await stream(websocket, detection_payload, 0.5)


async def subscription_stream(websocket: WebSocket, channel: str, projection):
    await websocket.accept()
    queue = asyncio.Queue()
    subscribers = getattr(app.state, f"{channel}_subscribers")
    subscribers.add(queue)
    try:
        await websocket.send_json(projection(app.state.runtime))
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                payload = projection(app.state.runtime)
            await websocket.send_json(payload)
    except (WebSocketDisconnect, RuntimeError):
        return
    finally:
        subscribers.discard(queue)


@app.websocket("/ws/objects")
async def ws_objects(websocket: WebSocket):
    await subscription_stream(websocket, "object", lambda runtime: {"objects": plain(runtime.object_library.list())})


@app.websocket("/ws/clusters")
async def ws_clusters(websocket: WebSocket):
    await subscription_stream(websocket, "cluster", cluster_payload)
