# TaskGraph v1.1.2 Branding & Frame Gallery Synchronization Report

## 1. Objective achieved

Frame Gallery synchronization is complete and validated end-to-end. Official branding installation is prepared through existing launcher icon hooks but remains blocked because the referenced supplied robotic-arm logo was not present in the user attachment, Codex attachment store, repository assets, or WebApp source.

## 2. Branding integration

The launcher already resolves `Assets/Branding/taskgraph.ico` for its native window icon. The displayed product version was updated to v1.1.2 in the launcher and WebApp. No substitute graphic was generated or labeled “official,” preserving brand integrity.

## 3. Assets added

No branding binaries were added because no source logo was supplied. Required final targets remain:

- `Assets/Branding/taskgraph.png`
- `Assets/Branding/taskgraph.ico`

## 4. Icon generation

Not performed. ICO generation requires the missing official PNG source. Once attached, the PNG can be copied losslessly and converted to a multi-resolution Windows ICO.

## 5. Launcher branding

Launcher version is v1.1.2. Splash/window icon loading is already wired to `Assets/Branding/taskgraph.ico`. Desktop `.cmd` files cannot carry a custom Windows icon; the existing launcher can additionally generate an icon-bearing `.lnk` after the ICO exists.

## 6. Web branding

The WebApp retains TaskGraph product naming and now displays v1.1.2. Header-logo and favicon replacement require `taskgraph.png`/`taskgraph.ico`; broken references were intentionally not introduced.

## 7. Frame synchronization root cause

The Import Video page simulated extraction with a browser timer and never sent the selected video to the backend. Consequently, the existing runtime WebSocket correctly continued publishing `workspace.frames = 0`. Frame Gallery derived its count from that value and remained empty. The stale display was not a React Query rendering defect; it was disconnected duplicate frontend state.

## 8. Synchronization fix

- Added a thin `POST /video/import` WebAPI adapter over the existing `VideoWorkspace.inspect` and `extract_async` responsibilities.
- The selected file is stored only under `.taskgraph-session/video`.
- New import clears prior temporary frames/results/errors but never touches Object Library data.
- Extraction callbacks update a presentation-only status projection on `VideoWorkspace`.
- `/runtime` now publishes extraction state, current frame, total, ETA, and live `len(video.frames)`.
- The existing `/ws/runtime` stream pushes those values every second into the React Query cache.
- Import Video renders progress exclusively from that backend projection and navigates after backend completion.
- Frame Gallery derives cards exclusively from the live runtime frame count.
- API requests use browser `cache: no-store`.
- `/frames/{name}` serves the raw extracted frame before detection and the detected overlay afterward.
- The Vite development proxy now includes `/video`.

No frame-list state or polling cache was duplicated in React.

## 9. Files modified

- `Integration/WebAPI/api.py`
- `WebApp/vite.config.ts`
- `WebApp/src/App.tsx`
- `WebApp/src/components.tsx`
- `WebApp/src/lib.ts`
- `WebApp/src/pages.tsx`
- `Launcher/runtime_state.py`

## 10. Validation results

| Check | Result |
|---|---|
| Synthetic video accepted by backend | PASS |
| Existing asynchronous extraction completed | PASS |
| Workspace frames written | PASS — 6 |
| Runtime reported matching live frame count | PASS — 6 |
| Runtime extraction state reached complete | PASS |
| React receives runtime updates through existing WebSocket | PASS by data-flow audit |
| Browser frame-list caching disabled | PASS |
| Raw frame endpoint available before YOLO | PASS by endpoint audit |
| Frontend TypeScript/Vite build | PASS — 2,215 modules |
| ESLint | PASS with one existing Fast Refresh warning |
| WebAPI syntax/import | PASS |
| Session test artifacts removed | PASS |
| Object Library unchanged | PASS — before/after hash matched |
| Restart cleanup retained | PASS |
| Official PNG installed | BLOCKED — asset absent |
| ICO generated/applied | BLOCKED — asset absent |
| Header/favicon official logo | BLOCKED — asset absent |

## 11. Remaining limitations

The official logo must be attached before branding can be completed. Supported source formats are PNG, SVG, WEBP, JPEG, or ICO; a transparent high-resolution PNG is preferred. After receipt, remaining work is mechanical: install PNG, generate ICO sizes, update splash artwork/window icon, create an icon-bearing `.lnk`, replace the header mark, and add the favicon.
