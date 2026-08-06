# VigilAI — Folder Structure

> Companion documents: [ARCHITECTURE.md](./ARCHITECTURE.md) · [AI_PROJECT_CONTEXT.md](./AI_PROJECT_CONTEXT.md)

This tree is the target layout the [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) milestones build out incrementally — not everything exists on day one. Folders are created when the milestone that needs them starts, not preemptively.

```
vigilAI/
├── README.md
├── docs/
│   ├── AI_PROJECT_CONTEXT.md
│   ├── ARCHITECTURE.md
│   ├── FOLDER_STRUCTURE.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── PROMPTING_GUIDE.md
│   ├── TECHNICAL_DECISIONS.md
│   └── TASK_BACKLOG.md
├── .env.example
├── .gitignore
│
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── domain/
│   │   │   ├── entities/
│   │   │   ├── value_objects/
│   │   │   ├── events/
│   │   │   └── exceptions.py
│   │   ├── application/
│   │   │   ├── ports/
│   │   │   ├── use_cases/
│   │   │   └── dto/
│   │   ├── infrastructure/
│   │   │   ├── onvif/
│   │   │   ├── streaming/
│   │   │   ├── analytics/
│   │   │   ├── persistence/
│   │   │   └── messaging/
│   │   ├── interfaces/
│   │   │   ├── api/
│   │   │   ├── websocket/
│   │   │   └── schemas/
│   │   └── core/
│   │       ├── config.py
│   │       ├── container.py
│   │       ├── logging.py
│   │       └── exception_handlers.py
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── fixtures/
│
├── frontend/
│   ├── package.json
│   └── src/
│       ├── features/
│       ├── components/
│       ├── services/
│       ├── hooks/
│       ├── store/
│       └── types/
│
├── storage/
│   ├── recordings/
│   ├── models/
│   └── demo_videos/
│
└── scripts/
```

---

## Backend — Folder by Folder

### `backend/app/domain/`
**Owns**: business entities and rules with zero framework knowledge.
**Contains**:
- `entities/` — `Camera`, `StreamProfile`, `Recording`, `DetectionEvent`, `AnalyticsZone`, `TrackedObject`, `Frame` (M2 — the `IFrameSource`/`IStreamWorker` payload type).
- `value_objects/` — `Resolution`, `Codec`, `BitrateKbps`, `PlateNumber`, `ColorLabel`, `BoundingBox`, `StreamHealth`/`StreamState` (M2 — a Stream Worker's point-in-time health snapshot).
- No dedicated `events/` submodule: TD-24 (M8) settled the actual convention as a single `DetectionEvent` entity with a namespaced `event_type` string (e.g. `object_detection.person`, `color_detection.red`, `loitering_detection.dwell_exceeded`) rather than one class per finding — confirmed again at M11/TD-28 rather than introducing the `LoiteringDetected` class this line originally (pre-M8) anticipated. `CameraWentOffline`/`RecordingCompleted` were likewise never built as separate classes for the same reason.
- `exceptions.py` — domain-level exception types (`CameraUnreachableError`, `UnsupportedConfigurationError`).
**Dependencies**: none within the project. May use Python stdlib and `pydantic` (for validation-rich value objects) but never `fastapi`, `cv2`, `onvif_zeep_async`, `sqlalchemy`.
**Who touches this**: anyone adding a new business concept. Changes here should be rare and deliberate — this is the layer everything else is built to protect.

### `backend/app/application/`
**Owns**: orchestration of domain objects to fulfill a use case, and the contracts (ports) infrastructure must satisfy.
**Contains**:
- `ports/` — abstract base classes: `ICameraGateway`, `IFrameSource`, `IStreamWorker` (M2 — the Stream Worker abstraction a use case depends on instead of a concrete `StreamWorker` class), `IRecordingRepository`, `IDetectorPlugin` (M8 — supersedes the M1 `IObjectDetector`, retired; see `docs/TECHNICAL_DECISIONS.md` TD-24), `IEventRepository` (M8), `ILicensePlateReader`, `IEventPublisher`, `ICameraRepository`.
- `use_cases/` — one class per business operation: `OnboardCameraUseCase`, `UpdateCameraConfigUseCase`, `StartLiveStreamUseCase`, `StartRecordingUseCase`, `ListRecordingsUseCase`, `RunAnalyticsPipelineUseCase`, `ConfigureAnalyticsRuleUseCase`. Plus `DebugStreamUseCase` (M2, T-025) — dev/demo tooling proving the Stream Worker end-to-end, not a persisted business operation like the others.
- `dto/` — plain dataclasses/Pydantic models passed between interfaces and use cases (not the same as domain entities, and not the same as API schemas — this is the use-case-facing shape).
**Dependencies**: `domain/` only.
**Who touches this**: anyone adding or changing a business operation. A new use case is the right place to start most feature work.

### `backend/app/infrastructure/`
**Owns**: every concrete integration with the outside world.
**Contains**:
- `onvif/` — `OnvifCameraGateway` (implements `ICameraGateway`) wrapping `onvif-zeep-async`: auth, `GetDeviceInformation`, `GetProfiles`, encoder config read/update, `GetStreamUri`.
- `streaming/` — `OnvifRtspFrameSource`, `RawRtspFrameSource`, `Mp4FileFrameSource` (all implement `IFrameSource`); FFmpeg process wrappers for recording and preview transcoding; `ReconnectSupervisor` (source-agnostic reconnect/backoff loop, M2) and `StreamWorker` (implements `IStreamWorker`, runs a `ReconnectSupervisor` in an isolated process — see `docs/TECHNICAL_DECISIONS.md` TD-20 for why these are two classes).
- `analytics/` — detector plugins implementing `IDetectorPlugin`: `NoOpDetectorPlugin` (M8, proves orchestrator wiring), `YoloObjectDetector`, `ColorDetector`, `LoiteringDetector`, `MissingObjectDetector`, `LicensePlateRecognizer` (composes a plate localizer + `EasyOcrReader`); the `AnalyticsOrchestrator`.
- `persistence/` — SQLModel table models, repository implementations (`SqlCameraRepository`, `SqlRecordingRepository`, `SqlEventRepository`), migrations.
- `messaging/` — in-process asyncio `EventBus` implementing `IEventPublisher` (M8, TD-11/TD-24)/subscriber-side fan-out to WebSocket connections.
**Dependencies**: `application/` (to implement its ports) and `domain/` (to construct/return entities). Infrastructure modules never import each other across subfolders except through ports (e.g. `analytics/` must not import `streaming/` directly — it receives `Frame` objects, it doesn't know how they were produced).
**Who touches this**: anyone integrating a new library, protocol, or storage backend.

### `backend/app/interfaces/`
**Owns**: translation between the outside world's wire formats (HTTP, WebSocket) and use cases.
**Contains**:
- `api/` — FastAPI routers, one module per resource: `cameras.py`, `recordings.py`, `analytics.py`, `streams.py`.
- `websocket/` — connection management and message framing for live frames and live analytics events.
- `schemas/` — Pydantic request/response models (API-facing shape; converted to/from `application/dto`).
**Dependencies**: `application/` only (calls use cases; never reaches into `infrastructure/` or `domain/` directly).
**Who touches this**: anyone adding or changing an HTTP/WS endpoint.

### `backend/app/core/`
**Owns**: process-wide plumbing that doesn't belong to any single layer.
**Contains**: `config.py` (the one `Settings` class), `container.py` (composition root — builds infra adapters, injects into use cases), `logging.py` (structlog setup), `exception_handlers.py` (domain exception → HTTP status mapping).
**Dependencies**: everything (this is the wiring layer — the one place allowed to import across all other layers).
**Who touches this**: rarely, and carefully — this is the file most likely to create accidental coupling if edited casually.

### `backend/tests/`
- `unit/` — mirrors `domain/` and `application/`; uses fakes for every port, no real I/O, no real FastAPI app.
- `integration/` — exercises real infrastructure adapters against the local MP4 fixture (`tests/fixtures/sample.mp4`) and, for ONVIF, against a mock SOAP server or `@pytest.mark.hardware`-gated real camera.
- `fixtures/` — sample MP4 clips, recorded ONVIF SOAP responses for offline testing.

---

## Frontend — Folder by Folder

### `frontend/src/pages/`
**Owns**: route-level composition (added M14, `docs/UI_UX_DESIGN.md` §12/TD-31) — one file per routed screen (`DashboardPage`, `CameraListPage`, `CameraDetailPage`, `LiveViewPage`, `RecordingsPage`, `EventsPage`), wired up in `App.tsx`'s `react-router-dom` route tree. This is the layer allowed to import from more than one `features/` folder in the same file (e.g. `CameraDetailPage`'s Zones tab renders `analytics-console/ZoneEditor` while its Configuration tab renders `camera-onboarding/ConfigPanel`) — the same role `core/` plays on the backend as the one place allowed to see across layers. A page should stay a thin composition: real UI/logic lives in `features/`, `pages/` just decides what's on screen for a given route and passes data between features that can't import each other directly.
**Dependencies**: `features/`, `components/`, `hooks/`, `store/`, `services/`, `types/`, `lib/`.

### `frontend/src/features/`
**Owns**: feature-scoped UI + logic, one subfolder per feature area (`camera-onboarding/`, `recordings/`, `analytics-console/`, `dashboard/`, `event-center/` — the latter two added M14). Each feature folder may contain its own components, hooks, and API-call wrappers. (`live-view/` existed through M5–M14 but held only `LiveView.tsx`; once the Dashboard needed the same component, it moved to `components/` — see below — leaving no feature-specific content behind, so the folder was removed rather than left empty.)
**Dependencies**: `services/`, `components/`, `hooks/`, `store/`, `types/`, `lib/`. Features do not import from each other — shared logic moves to `components/`/`hooks/`/`services/`/`lib/` instead, or composition moves up to `pages/`.

### `frontend/src/components/`
**Owns**: shared, feature-agnostic UI primitives (buttons, modals, layout shell, video player wrapper) — e.g. `AppShell` (nav + routed `<Outlet/>`), `Panel`, `Dialog`, `CameraPicker`, `AnalyticsToggle`, `LiveView` (the latter two started in `features/`, moved here once a second caller needed them — `features/` may not import each other).
**Dependencies**: none within `src/` besides `types/`.

### `frontend/src/services/`
**Owns**: typed API clients (REST fetch wrappers, WebSocket connection manager). This is the only place `fetch`/`WebSocket` is called directly.
**Dependencies**: `types/`.

### `frontend/src/hooks/`
**Owns**: React Query hooks built on top of `services/` (`useCameras`, `useLiveStream`, `useRecordings`, `useAnalyticsEvents`).

### `frontend/src/store/`
**Owns**: Zustand stores for local UI state (selected camera, layout preferences, active analytics filters) — `uiStore` (added M14): last-viewed camera, the Event Center nav badge's unread count.

### `frontend/src/lib/`
**Owns**: small, pure, feature-agnostic helper functions that are neither a component, a hook, nor an API client — e.g. `eventCategory.ts` (added M14: derives an analytics event's category/human-readable detail from its `event_type`/`metadata`, shared by the Dashboard and Event Center, both of which need it but may not import each other).
**Dependencies**: `types/`.

### `frontend/src/types/`
**Owns**: TypeScript types mirroring backend Pydantic schemas (kept in sync manually initially; candidate for OpenAPI-generated types later — see backlog).

---

## Top-Level Non-Code Folders

- **`docs/`** — all architecture, planning, design, and AI-context documentation (everything except `README.md`, which stays at the repo root as the entry point). No code; nothing under `app/` or `frontend/src/` imports from it.
- **`storage/recordings/`** — MP4 segments written by the Recording Worker. Gitignored; the filesystem implementation of `IRecordingRepository` points here by default (configurable path).
- **`storage/models/`** — downloaded/cached model weights (YOLO `.pt` files, EasyOCR model cache). Gitignored.
- **`storage/demo_videos/`** — operator-provided pre-recorded clips for the demo video library (M17). Gitignored, same as `storage/recordings/`; `LocalDemoVideoRepository` scans this directory directly (no DB table).
- **`scripts/`** — one-off operational scripts (e.g. seed a demo camera record, download model weights, generate a sample MP4 fixture). Not part of the application; never imported by `app/`.

---

## Dependency Direction Rule (Enforced, Not Just Documented)

```mermaid
flowchart LR
    Interfaces --> Application
    Infrastructure --> Application
    Application --> Domain
    Core -.wires everything, allowed to see all layers.-> Interfaces
    Core -.-> Infrastructure
    Core -.-> Application
```

Plain-language version, used as the actual review checklist:

1. `domain/` imports nothing from this project.
2. `application/` imports only `domain/`.
3. `infrastructure/` and `interfaces/` import `application/` (and `domain/` for entity construction) — never each other.
4. `core/` is the only module allowed to import across all layers, because its entire job is wiring them together.
5. Frontend `features/` never import each other directly.

Milestone M0 sets up `import-linter` (or an equivalent lightweight check) to fail CI if rule 1–3 is violated, so this stays a guarantee rather than a convention that quietly rots.
