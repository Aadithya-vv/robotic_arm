# TaskGraph v1.1.4 Object Review and Object Library Report

## 1. Root cause of every non-working button

The Detected Objects page built clusters from the detections projection and stored accepted, ignored, and rejected states only in component-local React state. Create Object merely changed that local status, Rename Cluster had no handler, and Ignore/Delete only hid cards until the component remounted. The Object Library View, Edit, and Delete controls had no handlers. No mutation endpoints or object/cluster WebSocket projections existed.

## 2. Buttons that were UI-only

| Button | Previous behavior | v1.1.4 behavior |
|---|---|---|
| Create Object | Local `Accepted` label only | Opens the required form and calls `POST /objects/create` |
| Rename Cluster | No handler | Calls `PATCH /clusters/rename` |
| Ignore Cluster | Local hide only | Calls `POST /clusters/ignore` |
| Delete Cluster | Local hide only | Confirms and calls `POST /clusters/delete` |
| View Object | No handler | Opens a read-only backend-projected detail dialog |
| Edit Object | No handler | Opens a form and calls `PATCH /objects/edit` |
| Delete Object | No handler | Confirms and calls `DELETE /objects/{id}` |

React no longer mutates authoritative object or review state.

## 3. Backend APIs added

- `GET /clusters`
- `PATCH /clusters/rename`
- `POST /clusters/ignore`
- `POST /clusters/delete`
- `POST /objects/create`
- `PATCH /objects/edit`
- `DELETE /objects/{object_id}`
- `GET /objects/{object_id}/thumbnail`
- `WS /ws/clusters`
- `WS /ws/objects`

## 4. Backend object creation flow

The API validates the current-session cluster, copies every available instance frame into a unique permanent `Assets/ObjectLibrary/instances/<dataset-id>` directory, records the representative thumbnail and all instance paths, carries across the cluster confidence and available feature descriptors, and invokes the existing `ObjectLibrary.create` responsibility. That responsibility generates the Object ID and atomically persists `Assets/ObjectLibrary/objects.json`. The accepted cluster is removed from the session review projection and both object and cluster updates are broadcast immediately.

The create dialog contains Object Name, Description, Category, optional Notes, thumbnail preview, read-only frame count and confidence, Cancel, and the create submission control.

## 5. Backend cluster deletion flow

Deleted cluster IDs are stored in the backend's session-only review state. Cluster and detection projections filter those IDs, then cluster and runtime updates are published. Page navigation cannot restore a deleted cluster. Importing another video resets the review state, as required. Ignore uses a separate session-only set and does not create or delete permanent knowledge. Rename is also held in backend session state.

## 6. Backend object deletion flow

The delete endpoint resolves the object from the Object Library, invokes the existing `ObjectLibrary.delete` responsibility, updates `objects.json`, removes the v1.1.4-owned permanent instance directory when applicable, and broadcasts the new Object Library projection. Legacy object image locations are never broadly removed.

## 7. Runtime synchronization verification

`GET /clusters` and the cluster mutation handlers use backend review state as the single source of truth. A new video resets renamed, ignored, deleted, and accepted sets without touching the Object Library. Object mutations exclusively use the existing Object Library create/update/delete methods.

## 8. WebSocket synchronization verification

`/ws/objects` and `/ws/clusters` send an initial authoritative projection, receive mutation broadcasts through per-channel queues, and send a periodic authoritative heartbeat. React Query consumes both channels with the existing reconnecting WebSocket hook. No reload, refresh, or page transition is required.

## 9. Validation table

| Validation | Result | Evidence |
|---|---|---|
| Python syntax | Pass | `python -m py_compile Integration/WebAPI/api.py` |
| TypeScript project check | Pass | local `tsc -b WebApp/tsconfig.json` |
| Frontend lint | Pass with one pre-existing warning | 0 errors; existing Fast Refresh warning in `components.tsx` |
| API route registration | Pass | All six required mutation routes plus both WebSocket routes registered |
| API startup/read projections | Pass | TestClient returned HTTP 200 for `/objects` and `/clusters` |
| Session lifecycle regression | Pass | `Tests.test_session_lifecycle` |
| Existing Composition Root v0.2.4 test | Environment-limited | Runtime selected Classical CV because the YOLO model was unavailable; expected YOLO11M assertion failed before this workflow executes |
| Production bundle | Sandbox-limited | TypeScript passed; Vite/esbuild could not traverse the sandbox boundary while resolving its config |
| Persistence mechanism | Pass by inspection | All mutations invoke existing Object Library responsibilities and its atomic JSON writer |
| Session deletion persistence | Pass by inspection | Backend session state, not React state, filters both cluster and detection projections |

## 10. Architecture verification

No ABP, GBP, Rule 40, Engine, Composition Root, Launcher, session lifecycle, or detection-pipeline files were modified for v1.1.4. Changes are limited to the WebAPI adapter, React presentation/synchronization, Vite proxy mapping, styling for existing workflow dialogs, and this report. The Object Library remains the only permanent source of application knowledge; cluster review state remains temporary.

## Files modified

- `Integration/WebAPI/api.py`
- `WebApp/src/App.tsx`
- `WebApp/src/lib.ts`
- `WebApp/src/pages.tsx`
- `WebApp/src/styles.css`
- `WebApp/vite.config.ts`

## Files added

- `TaskGraph_v1.1.4_Object_Review_and_Object_Library_Report.md`

## Remaining limitations

- Automated browser interaction was not available in the workspace, so dialog clicks and visual WebSocket updates were validated through compilation, route/projection smoke tests, and code-path inspection rather than a browser automation suite.
- Existing legacy objects whose thumbnail files no longer exist return a deliberate 404 placeholder condition; v1.1.4-created object images are copied into permanent storage and served by object ID.
