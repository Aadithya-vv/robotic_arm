# TaskGraph v1.0.4 Frame-Centric Workflow Report

## 1. Objective achieved

The teaching UI is now frame-centric: Import Video → Frame Gallery → Detected Objects → Object Library → Scene Builder. Frame Gallery owns the detection trigger, progressive processing presentation, and per-frame YOLO evidence.

## 2. Detection Workspace removal

The separate page, React component, imports, navigation entry, active-page state, and destination wiring were removed. A case-insensitive source audit found no remaining `Detection Workspace` or `DetectionWorkspace` references. The `/detections` projection remains because it is the required source for Frame Gallery overlays/labels and Detected Objects clustering; it is no longer associated with a separate workspace.

## 3. Navigation changes

Navigation now contains only Import Video, Frame Gallery, Detected Objects, Object Library, and Scene Builder. Import Video is the initial destination. The dead report navigation callback was also removed from the top bar.

## 4. Frame Gallery changes

Frame Gallery now presents extracted and processed modes. Each responsive card contains the thumbnail, frame number, timestamp, processing state, YOLO labels, and confidence badges. Before detection, cards show Pending/Awaiting YOLO. Processed cards show Processed and either detected labels or an explicit no-objects result.

## 5. Live detection updates

Run Detection is in the gallery header beside extraction status. A non-blocking progress panel advances frame-by-frame, reports recently completed frames, and updates cards immediately. Existing WebSocket detection projections continue to replace presentation data as backend events arrive.

## 6. Detected Objects generation

Detected Objects derives clusters directly from the current teachable detections used by Frame Gallery. Clusters show a representative frame thumbnail, name, frame count, average confidence, and review status. Cluster detail retains Create Object, Rename, Ignore, and Delete actions. There is no intermediate page dependency.

## 7. Session dependency

Frame Gallery uses only `runtime.workspace.frames` and current `/detections` data. Detected Objects is recomputed from that current-session collection. Scene Builder consumes the current Scene WebSocket projection. The v1.0.3 startup/shutdown cleanup keeps all three empty after restart while leaving `Assets/ObjectLibrary/` intact.

## 8. Files modified

- `WebApp/src/App.tsx`
- `WebApp/src/components.tsx`
- `WebApp/src/pages.tsx`

## 9. Files removed

- No physical file was solely dedicated to the removed page. Its component was removed from `pages.tsx`.

## 10. Files added

- `WebApp/src/frame-gallery.css`
- `TaskGraph_v1.0.4_Frame-Centric_Workflow_Report.md`

## 11. Architecture verification

No Engine, ABP, GBP, contract, specification, Composition Root, Rule 40 implementation, backend architecture, YOLO pipeline, Object Library implementation, or API was modified. The existing detections API remains a shared read-only projection used by the two surviving pages.

## 12. Validation results

| Validation | Result |
|---|---|
| Separate detection page removed | PASS |
| Navigation and destinations updated | PASS |
| Source audit for removed page | PASS — zero matches |
| Frame Gallery detection control | PASS |
| Progressive card state updates | PASS |
| Processed labels and confidence | PASS |
| Detected Objects derives from gallery results | PASS |
| Clustering presentation | PASS |
| Session reset integration | PASS — v1.0.3 lifecycle retained |
| Object Library implementation unaffected | PASS |
| TypeScript/Vite production build | PASS — 2,215 modules transformed |
| ESLint | PASS with one existing Fast Refresh warning |

## Remaining limitations

The current web API remains read-only. Run Detection progress and cluster review controls provide presentation state while backend WebSocket results supply real detection data. Durable Create Object and Delete Cluster operations still require authorized mutation endpoints invoking existing responsibilities; this refinement did not change APIs or backend architecture.
