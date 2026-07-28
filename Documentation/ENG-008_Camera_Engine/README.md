# ENG-008 — Camera Engine

## Public Behavior

ENG-008 discovers camera devices, initializes one selected provider, acquires immutable frame observations, reports diagnostics, and shuts the camera down. Every operation returns a structured `CameraResponse` containing status, runtime state, explanation records, and a structured error when the operation fails.

The public surface is defined by `CameraContract`. Consumers interact with the Engine through that contract and the immutable request, response, configuration, observation, diagnostic, error, and explanation records in `contracts.py`.

## Provider Architecture

Hardware access is isolated behind `CameraProvider`. The Engine contains no direct OpenCV dependency.

- `MockCameraProvider` is the deterministic default. It supports discovery and acquisition without camera hardware and is suitable for tests, simulation, and integration development.
- `OpenCVCameraProvider` is optional. It imports OpenCV only when used and reports an explicit provider-unavailable error when the package is absent.
- `CameraProviderCatalog` validates provider contracts, rejects duplicate identifiers, and performs deterministic selection.

The default catalog is intentionally hardware-independent. Applications that require OpenCV must opt in by composing `CameraProviderCatalog.default(include_opencv=True)` or supplying an approved provider.

## Lifecycle

The controlled lifecycle is:

`Closed -> Opening -> Ready -> Capturing -> Ready -> Closing -> Closed`

An opening, acquisition, provider, or logging failure moves the Engine to `Failed`. Shutdown from `Failed` performs best-effort provider cleanup and returns the Engine to `Closed`. Invalid operations are rejected without silently changing state.

## Configuration

`CameraConfiguration` supplies the provider identifier, device identifier, width, height, frame rate, and pixel format. Values are validated before the provider is opened. Validated configuration is immutable for the active lifecycle; changing it requires shutdown and reinitialization.

No filesystem location or configuration file format is assumed. A caller may obtain values from ENG-003 through its public contract and construct the configuration record at the composition boundary.

## Observations and Diagnostics

Each acquired `CameraObservation` contains immutable frame bytes, dimensions, pixel format, provider and device identity, a monotonically increasing sequence, and a provider timestamp. The Camera Engine performs acquisition only; it does not detect, track, label, interpret, or transform scene content.

Diagnostics expose lifecycle state, provider/device identity, acquired-frame count, provider details, and the most recent structured error. Responses also carry immutable explanation records for significant decisions and state transitions.

## Logging and Concurrency

Logging occurs exclusively through the injected `LogSink` public contract. `NullLogSink` is available when no logging provider has been composed. Logging failures are explicit Engine failures rather than hidden side effects.

Lifecycle and acquisition operations are guarded by a reentrant lock. Concurrent acquisitions are serialized, producing unique, ordered observation sequences and deterministic state transitions.

## Error Handling

Failures use stable structured codes, including invalid request/configuration/state, unknown or unavailable provider, connection failure, acquisition failure, malformed provider output, logging failure, and provider exception. Provider exceptions are translated at the boundary and are not exposed directly to consumers.

## Responsibilities and Boundaries

ENG-008 owns camera discovery, connection lifecycle, configuration application, frame acquisition, diagnostics, runtime state, and camera-specific error reporting. It does not own object detection, scene tracking, semantic identity, demonstration interpretation, persistent event delivery, or logging storage.

## Limitations

- The OpenCV adapter is optional and was contract-tested without requiring the OpenCV package or physical hardware.
- Frames are exposed in the pixel format supplied by the provider; image conversion and perception are outside ENG-008.
- Provider-specific capabilities beyond the approved camera contract require a future provider extension and architectural review.

## Locations

- Specification: `Specifications/ENG-008_Camera_Engine/Specification.md`
- Framework Prompt: `Prompts/ENG-008_Camera_Engine/FrameworkPrompt.md`
- Source: `Implementation/ENG-008_Camera_Engine/Source/taskgraph_camera/`
- Tests: `Tests/ENG-008_Camera_Engine/`
- Reports: `Reports/ENG-008_Camera_Engine/`
