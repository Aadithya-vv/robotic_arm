"""TaskGraph v1.0 Web Edition presentation adapter.

This module exposes the frozen Composition Root through REST and WebSocket
projections. It owns no Engine logic.
"""
from __future__ import annotations

import asyncio
import json
import sys
import shutil
from datetime import datetime
from contextlib import asynccontextmanager
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any
from time import monotonic
from uuid import uuid4

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
from Engines import ActionAssetEngine, CompilerEngine, EngineBus, PackagingEngine


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
                "class_name": class_name,
                "confidence": item.confidence,
                "tracking_id": item.candidate_id,
                "bounding_box": plain(item.region),
                "status": status,
                "annotated_frame": f"/frames/{Path(annotated).name}",
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.runtime = create_runtime({"runtime_mode": "web", "release": "v1.0"}, "web-startup")
    app.state.runtime.video_workspace.web_extraction = {"state": "idle", "current": 0, "total": 0, "eta": 0.0, "frame": None}
    app.state.runtime.video_workspace.web_detection = {"state": "idle", "current": 0, "total": 0, "eta": 0.0, "frames": {}, "metrics": {}}
    app.state.runtime.video_workspace.web_clusters = {"renamed": {}, "ignored": [], "deleted": [], "accepted": []}
    app.state.runtime_subscribers = set()
    app.state.object_subscribers = set()
    app.state.action_assets = ActionAssetEngine(ROOT)
    app.state.compiler = CompilerEngine(app.state.runtime.taskir, app.state.action_assets, taskir_request)
    app.state.packaging = PackagingEngine(ROOT, app.state.action_assets, app.state.compiler)
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
    try: return app.state.packaging.preview(body["robot_id"], body["action_id"], body.get("configuration", {}))
    except KeyError as exc: raise HTTPException(404, f"Resource not found: {exc.args[0]}") from exc

@app.get("/execution/packages")
def execution_packages():
    return {"packages": app.state.packaging.list_packages()}

@app.post("/execution/packages")
async def execution_build_package(request: Request):
    body = await request.json()
    try: return app.state.packaging.build(body["robot_id"], body["action_id"], body.get("configuration", {}))
    except KeyError as exc: raise HTTPException(404, f"Resource not found: {exc.args[0]}") from exc
    except (ValueError, ConnectionError) as exc: raise HTTPException(422, str(exc)) from exc

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


@app.get("/objects/{object_id}/thumbnail")
def get_object_thumbnail(object_id: str):
    item = next((value for value in app.state.runtime.object_library.list() if value["object_id"] == object_id), None)
    if item is None:
        raise HTTPException(404, "Object not found")
    target = Path(item.get("thumbnail", {}).get("path", ""))
    if target.is_file():
        return FileResponse(target)
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


@app.post("/video/import")
async def import_video(request: Request, filename: str, rate: float = 1.0):
    """Thin web adapter over the existing asynchronous VideoWorkspace."""
    runtime = app.state.runtime
    workspace = runtime.video_workspace
    workspace.cancel()
    workspace.frames, workspace.results, workspace.errors = [], {}, []
    workspace.current_object, workspace.current_confidence = None, None
    workspace.web_detection = {"state": "idle", "current": 0, "total": 0, "eta": 0.0, "frames": {}, "metrics": {}}
    workspace.web_clusters = {"renamed": {}, "ignored": [], "deleted": [], "accepted": []}
    upload_dir = ROOT / ".taskgraph-session" / "video"
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / Path(filename).name
    target.write_bytes(await request.body())
    metadata = workspace.inspect(target)
    state = {"state": "extracting", "current": 0, "total": 0, "eta": 0.0, "frame": None}
    workspace.web_extraction = state

    def progress(current, total, eta, frame):
        state.update(state="extracting", current=current, total=total, eta=eta, frame=frame)

    def done(completed, error):
        state.update(state="complete" if completed else "cancelled", current=len(workspace.frames), total=len(workspace.frames), eta=0.0, error=error)

    workspace.extract_async(rate, progress, done)
    return {"accepted": True, "metadata": plain(metadata)}


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
    body = await request.json(); object_id = body.pop("object_id", "")
    try: app.state.runtime.object_library.update(object_id, body)
    except KeyError as exc: raise HTTPException(404, "Object not found") from exc
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    sync_semantic("object-edited"); publish("object", {"objects": plain(app.state.runtime.object_library.list())}); return {"updated": True}


@app.delete("/objects/{object_id}")
def delete_object(object_id: str):
    item = next((value for value in app.state.runtime.object_library.list() if value["object_id"] == object_id), None)
    if item is None: raise HTTPException(404, "Object not found")
    dataset = Path(item.get("thumbnail", {}).get("path", "")).parent.resolve()
    permanent_instances = (ROOT / "Assets" / "ObjectLibrary" / "instances").resolve()
    app.state.runtime.object_library.delete(object_id)
    if dataset.parent == permanent_instances and dataset.is_dir():
        shutil.rmtree(dataset)
    sync_semantic("object-deleted"); publish("object", {"objects": plain(app.state.runtime.object_library.list())}); return {"deleted": True}


def detection_log(message: str):
    folder = ROOT / "Logs"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "detection.log").open("a", encoding="utf-8") as stream:
        stream.write(f"{datetime.now().isoformat(timespec='milliseconds')} {message}\n")


def publish_runtime():
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
    completed=state.get("state")=="complete"
    return {"accepted":completed,"frames":len(workspace.frames),"detection":plain(state),"reason":None if completed else state.get("error") or "Detection failed"}


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
