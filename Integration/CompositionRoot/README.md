# TaskGraph v0.1 Composition Root

This non-Engine layer is the sole concrete assembly point for the seven frozen Core Platform Engines. It owns provider construction, dependency injection, startup/shutdown ordering, health projection, runtime validation, and the executable entry point—never Engine behavior.

## Files

- `main.py`: executable entry point and structured startup-error boundary.
- `runtime.py`: immutable composed runtime container.
- `providers.py`: static configuration, Bootstrap readiness/capability, deferred logging, and unavailable-future adapters.
- `startup.py`: deterministic seven-Engine construction and startup.
- `shutdown.py`: reverse-order public-contract shutdown.
- `health.py`: read-only lifecycle health projection.
- `validation.py`: M1 public-contract validation checks.

## Startup Order

Bootstrap establishes the initial lifecycle while its diagnostics are held by `DeferredLogSink`. Logging initializes next and receives the buffered records. Configuration, Registry, Event Bus, and Memory then initialize; Registry receives metadata for all seven Engines; Registry becomes ready; Kernel starts last from Bootstrap readiness.

## Running

From the repository root:

```powershell
python Integration\CompositionRoot\main.py
```

From this directory, the equivalent short command is `python main.py`. Use `--validate-only` for non-GUI release validation.

Future Engines may be added only after approval: import their public package, construct them here, publish Registry metadata, extend health/validation, and add public shutdown—without modifying frozen Engine internals.
