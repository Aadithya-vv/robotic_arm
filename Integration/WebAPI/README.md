# TaskGraph v1.0 Web API

Thin presentation adapter over the unchanged TaskGraph Composition Root.

```powershell
.\.venv\Scripts\pip.exe install -r Integration\WebAPI\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn api:app --app-dir Integration\WebAPI --host 127.0.0.1 --port 8000
```

REST: `/runtime`, `/objects`, `/scene`, `/health`, `/reports`, `/validation`, `/detections`.

WebSocket: `/ws/runtime`, `/ws/scene`, `/ws/detections`.

The adapter is intentionally read-only and contains no perception, recognition, Scene, CUDA, YOLO, validation, reporting, or worker logic.
