# TaskGraph v0.2 Composition Root

This non-Engine layer is the sole concrete assembly point for ENG-001 through ENG-010. It owns provider construction, dependency injection, startup/shutdown, health projection, Camera→Vision→Scene orchestration, validation, and the executable boundary—never Engine behavior.

## Files

- `main.py`: executable and startup-error boundary.
- `runtime.py`: immutable ten-Engine runtime container.
- `providers.py`: configuration, Bootstrap capability, and deferred logging adapters.
- `perception.py`: public-contract-only Camera→Vision→Scene orchestration.
- `startup.py`: approved ten-Engine construction and startup.
- `shutdown.py`: exact reverse-order public-contract shutdown.
- `health.py`: ten-Engine lifecycle health projection.
- `validation.py`: M2 public-contract validation.

## Lifecycle Order

Startup:

`Bootstrap → Kernel → Configuration → Registry → Event Bus → Memory → Logging → Camera → Vision → Scene`

Shutdown executes the reverse sequence. The logging bridge buffers diagnostics before Logging starts and after Logging stops, preventing concrete lifecycle coupling.

## Running

```powershell
.\.venv\Scripts\python.exe Integration\CompositionRoot\main.py
.\.venv\Scripts\python.exe Integration\CompositionRoot\main.py --validate-only
```

Only this layer constructs concrete Engines. Interactions use exported public contracts and structural provider boundaries under Rule 40.
