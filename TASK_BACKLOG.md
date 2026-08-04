# VigilAI — Task Backlog

> Companion documents: [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) (milestone-level) · [ARCHITECTURE.md](./ARCHITECTURE.md)

This backlog is the fine-grained, trackable breakdown of [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md). Each milestone maps to one epic below. Work top to bottom within **P0**, then **P1**, etc.; within a priority, respect the Dependencies column.

**Priority**: P0 = required for a functioning core demo · P1 = required by the assignment but can slip briefly · P2 = quality/robustness, do if time allows · P3 = stretch/nice-to-have.
**Complexity**: S (< 2h) · M (half day) · L (1–2 days) · XL (2+ days, consider splitting further before starting).

---

## Epic: M0 — Scaffolding

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-001 | Backend package skeleton per FOLDER_STRUCTURE.md | P0 | S | — | Empty layered packages exist; `python -c "import app"` works |
| T-002 | `pyproject.toml` with ruff/black/mypy/pytest config | P0 | S | T-001 | `ruff check`, `mypy`, `pytest` all runnable from repo root |
| T-003 | `Settings` (pydantic-settings) + `.env.example` | P0 | S | T-001 | Missing required env var fails fast at startup with a clear error |
| T-004 | `structlog` setup (JSON prod / pretty dev) | P0 | S | T-003 | Log line includes level, timestamp, and bound context keys |
| T-005 | Composition root stub + FastAPI `main.py` + `/health` | P0 | S | T-001 | `GET /health` returns 200 |
| T-006 | Import-linter contract for layer dependency rule | P1 | M | T-001 | CI fails on a deliberately-introduced violating import; passes after revert |
| T-007 | React + Vite + TS + Tailwind skeleton | P0 | S | — | `npm run dev` renders a page |
| T-008 | Frontend hits `/health`, displays status | P0 | S | T-005, T-007 | Page shows live backend health |
| T-009 | Pre-commit hooks / CI workflow for lint+type+test | P1 | M | T-002 | Hook or CI step blocks a lint violation from being committed/merged |

## Epic: M1 — Domain & Application Core

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-010 | `Camera`, `StreamProfile` entities | P0 | S | T-001 | Unit tests cover invalid-state construction (e.g. negative bitrate rejected) |
| T-011 | `Recording`, `DetectionEvent` entities | P0 | S | T-001 | Same as above |
| T-012 | `AnalyticsZone`, `TrackedObject` entities | P1 | S | T-001 | Same as above |
| T-013 | Value objects: `Resolution`, `Codec`, `BitrateKbps`, `BoundingBox`, `ColorLabel`, `PlateNumber` | P0 | M | T-001 | Each has validation tests (e.g. `Resolution` rejects 0×0) |
| T-014 | Domain exception hierarchy | P0 | S | T-010–T-013 | `CameraUnreachableError`, `UnsupportedConfigurationError` etc. defined and raised from stub use cases |
| T-015 | Ports: `ICameraGateway`, `IFrameSource`, `ICameraRepository`, `IRecordingRepository` | P0 | S | T-010, T-011 | Abstract methods only, no implementation leakage |
| T-016 | Ports: `IObjectDetector`, `ILicensePlateReader`, `IEventPublisher` | P0 | S | T-011 | Same |
| T-017 | Use case skeletons (6 use cases, signatures only) | P0 | M | T-015, T-016 | Each has a docstring stating pre/post-conditions and a failing `NotImplementedError` body |

## Epic: M2 — Frame Source Abstraction (MP4)

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-020 | Finalize `Frame` object shape | P0 | S | T-013 | Includes source_id, sequence, timestamp, image, metadata |
| T-021 | `Mp4FileFrameSource` (OpenCV-based) | P0 | M | T-020 | Yields frames from fixture MP4 at correct throttled rate |
| T-022 | Commit sample MP4 fixture(s) | P0 | S | — | At least one clip with visible people/objects/vehicle+plate for later analytics milestones |
| T-023 | Stream Worker: process-isolated loop + bounded drop-oldest queue | P0 | L | T-021 | Under sustained overload, memory stays bounded (queue never grows unbounded) |
| T-024 | Reconnect/backoff supervisor, source-agnostic | P0 | M | T-023 | Unit test with a fake flaky `IFrameSource` proves backoff sequence (e.g. 1s,2s,4s,capped) |
| T-025 | Debug endpoint to observe live frame flow from a started source | P1 | S | T-023 | Returns latest frame metadata or an MJPEG snippet |

## Epic: M3 — ONVIF Onboarding

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-030 | Integrate `onvif-zeep-async`, connect + auth | P0 | M | T-015 | Successful auth against real/simulated camera; wrong password yields typed error |
| T-031 | `GetDeviceInformation` mapping to domain `Camera` | P0 | S | T-030 | Manufacturer/model/firmware captured |
| T-032 | `GetProfiles` mapping to `StreamProfile`(s) | P0 | M | T-030 | All camera-reported profiles persisted |
| T-033 | `OnboardCameraUseCase` full implementation | P0 | M | T-031, T-032, T-017 | Integration test onboards fixture/simulated camera end-to-end |
| T-034 | `POST /cameras`, `GET /cameras`, `GET /cameras/{id}` endpoints + schemas | P0 | M | T-033 | OpenAPI docs render correctly; manual curl test passes |
| T-035 | Credential-at-rest encryption | P1 | M | T-033 | Password never appears in logs or API responses; stored ciphertext in DB |
| T-036 | Frontend "Add Camera" form | P0 | M | T-034 | Submitting valid IP/user/pass onboards and lists the camera |
| T-037 | ONVIF SOAP fixture capture for offline/CI testing | P1 | M | T-030 | Integration suite runs in CI without a real camera present |

## Epic: M4 — ONVIF Config Read/Update

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-040 | `GetVideoEncoderConfiguration(s)` mapping | P0 | M | T-032 | Resolution/FPS/bitrate/codec read correctly |
| T-041 | `SetVideoEncoderConfiguration` with capability-aware field filtering | P0 | L | T-040 | Attempting an unsupported field returns typed 4xx, not a raw SOAP fault |
| T-042 | `GET /cameras/{id}/config`, `PATCH /cameras/{id}/config` | P0 | M | T-041 | PATCH result reflected on next GET |
| T-043 | Frontend config panel (view + edit, field-limited by capability) | P0 | M | T-042 | Editing a real supported field updates the physical camera |

## Epic: M5 — Live Streaming + Reconnect

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-050 | `OnvifRtspFrameSource` (resolves `GetStreamUri`, delegates decode) | P0 | M | T-021, T-040 | Same `Frame` shape as `Mp4FileFrameSource` |
| T-051 | `RawRtspFrameSource` | P1 | M | T-021 | Works against a generic RTSP URL with no ONVIF involved |
| T-052 | MJPEG live-view HTTP endpoint | P0 | M | T-050 | Renders in a plain `<img>` tag in a browser |
| T-053 | WebSocket stream-status/health channel | P1 | M | T-024 | UI reflects connected/reconnecting/failed states in real time |
| T-054 | Real-world reconnect validation against physical camera | P0 | M | T-052, T-024 | Documented test: network interrupted → auto-recovers within N seconds |
| T-055 | Frontend live-view component with status indicator | P0 | M | T-052, T-053 | Visually confirms stream + shows reconnect state during induced failure |

## Epic: M6 — Recording

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-060 | FFmpeg segment-muxer recording worker (stream copy) | P0 | L | T-050 | Produces valid MP4 segments verifiable with `ffprobe` |
| T-061 | `SqlRecordingRepository` + recording metadata schema | P0 | M | T-011 | Segment rows queryable with correct duration/size |
| T-062 | `StartRecordingUseCase` / `StopRecordingUseCase` | P0 | M | T-060, T-061 | Start→stop cycle produces exactly one consistent metadata row per segment set |
| T-063 | `POST /cameras/{id}/recording/start`/`stop`, `GET /recordings` | P0 | M | T-062 | Manual test: start, wait, stop, list shows entry |
| T-064 | Recording/live-view concurrency verification | P1 | M | T-063, T-055 | Both running simultaneously without frame drops/corruption in either |
| T-065 | Storage path/quota configuration | P2 | S | T-060 | Configurable via `Settings`; documented disk-usage behavior |

## Epic: M7 — Playback

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-070 | HTTP range-request playback endpoint | P0 | M | T-061 | `curl -r` partial requests return correct `206` responses |
| T-071 | `ListRecordingsUseCase` with camera/date filters | P0 | S | T-061 | Filters verified by test data spanning multiple cameras/days |
| T-072 | Frontend recordings list + `<video>` player | P0 | M | T-070, T-071 | Seek/scrub works smoothly in-browser |

## Epic: M8 — Analytics Pipeline Foundation

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-080 | `IDetectorPlugin` interface | P0 | S | T-016 | — |
| T-081 | `AnalyticsOrchestrator` (plugin iteration per frame) | P0 | M | T-080, T-023 | No-op plugin invoked once per frame, provably |
| T-082 | In-process `EventBus` implementing `IEventPublisher` | P0 | M | T-016 | Multiple subscribers all receive published events |
| T-083 | `DetectionEvent` persistence | P0 | S | T-011, T-082 | Events queryable after publish |
| T-084 | WebSocket analytics-events channel | P0 | M | T-082 | Browser client receives events in real time during a live/MP4 run |
| T-085 | Analytics enable/disable API per source | P0 | S | T-081 | Toggling off stops new events without restarting the stream |
| **T-086** | **Source-independence regression test** (same plugin, orchestrator run against `Mp4FileFrameSource` and a fake `IFrameSource`) | **P0** | M | T-081, T-021 | Test asserts identical plugin-invocation behavior across sources; kept permanently as a regression guard — this is the assignment's core architectural claim made verifiable |

## Epic: M9 — Object Detection & Classification

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-090 | Ultralytics integration, model weight caching | P0 | M | T-080 | Cold start downloads once, cached thereafter |
| T-091 | `YoloObjectDetector` plugin (detection + classification) | P0 | L | T-090, T-081 | Bounding boxes + class labels attached to emitted events |
| T-092 | FPS/perf measurement on Mac Mini, documented | P1 | S | T-091 | Number recorded in TECHNICAL_DECISIONS.md or a perf note |
| T-093 | Frontend detection overlay (boxes + labels) on live view | P0 | M | T-091, T-055 | Visually correct overlay during live/MP4 demo |

## Epic: M10 — Color Detection

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-100 | HSV-histogram dominant-color extraction on bbox crop | P0 | M | T-091 | Unit test against curated known-color crops passes |
| T-101 | Color label surfaced in event payload + UI | P0 | S | T-100, T-093 | Visible next to each detection in the console |

## Epic: M11 — Loitering Detection

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-110 | Enable YOLO/ByteTrack persistent track IDs | P0 | M | T-091 | Same object retains one ID across consecutive frames in a test clip |
| T-111 | `AnalyticsZone` polygon CRUD (API) | P0 | M | T-012 | Zone persists, retrievable per camera |
| T-112 | Frontend zone editor (draw polygon on still frame) | P1 | M | T-111 | Polygon saved matches what was drawn |
| T-113 | `LoiteringDetector` plugin with dwell timer + de-dup | P0 | L | T-110, T-111 | One event per qualifying dwell period, not per frame (explicit test) |

## Epic: M12 — Missing Object Detection

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-120 | Baseline capture mechanism (reference frame/zone state) | P0 | M | T-111 | Baseline stored and retrievable |
| T-121 | `MissingObjectDetector` plugin with absence timer | P0 | L | T-120, T-091 | Event fires only after threshold crossed on a prepared test clip |
| T-122 | Occlusion false-positive guard | P1 | M | T-121 | Crafted test: brief occlusion under threshold produces no event |

## Epic: M13 — License Plate Recognition

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-130 | Plate region localizer (YOLO or classical CV fallback) | P0 | L | T-091 | Correctly boxes plate region on test clip in majority of sampled frames |
| T-131 | `EasyOcrReader` implementing `ILicensePlateReader` | P0 | M | T-016 | Given a clean plate crop, returns correct text in isolated test |
| T-132 | `LicensePlateRecognizer` plugin composing localizer + OCR | P0 | M | T-130, T-131 | End-to-end event with plate text emitted from a live/MP4 run |
| T-133 | Non-blocking OCR execution (async/queued) | P1 | M | T-132 | Orchestrator frame loop latency unaffected by OCR runtime (measured) |
| T-134 | Accuracy note documented honestly | P1 | S | T-132 | TECHNICAL_DECISIONS.md or perf note states observed accuracy/limits |

## Epic: M14 — Frontend Dashboard Integration

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-140 | App routing/navigation shell tying all features together | P0 | M | M3–M13 features | All feature routes reachable from nav |
| T-141 | End-to-end manual walkthrough script (onboard → live → record → play → analytics) | P0 | S | T-140 | Walkthrough completes with no dead ends or console errors |
| T-142 | Responsive/layout pass | P2 | M | T-140 | Usable at common laptop resolutions |

## Epic: M15 — Testing, Hardening, Docs Polish

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-150 | Coverage audit, domain/application | P0 | M | all prior | Meaningful gaps identified and either closed or explicitly noted |
| T-151 | Error-path review across all use cases | P0 | M | all prior | Every use case failure mode maps to a typed exception → correct HTTP status |
| T-152 | Logging audit across worker processes | P1 | M | all prior | A synthetic field failure is diagnosable from logs alone |
| T-153 | README real setup commands (replace placeholders) | P0 | S | all prior | Fresh clone + documented steps → running system |
| T-154 | Update AI_PROJECT_CONTEXT.md "Project State" | P0 | S | all prior | Reflects actual end-state, not planning-time assumptions |

## Epic: M16 — Dockerization (Stretch)

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-160 | Backend Dockerfile (incl. FFmpeg) | P3 | M | T-153 | Image builds, container serves `/health` |
| T-161 | Frontend Dockerfile | P3 | S | T-153 | Image builds, serves the app |
| T-162 | `docker-compose.yml` incl. storage volume | P3 | M | T-160, T-161 | `docker compose up` yields a working system reachable on documented ports |
| T-163 | Document LAN camera access from container | P3 | S | T-162 | Onboarding the physical camera works from inside the container |

---

## Cross-Cutting / Quality Backlog (not tied to one milestone)

| ID | Task | Priority | Complexity | Dependencies | Definition of Done |
|---|---|---|---|---|---|
| T-200 | OpenAPI-generated TypeScript types (replace hand-mirrored `types/`) | P2 | M | M3+ endpoints stable | Frontend types generated by a script, no manual drift |
| T-201 | API-level input validation edge cases (malformed IP, out-of-range port) | P1 | S | M3 | Rejected with clear 422s, tested |
| T-202 | Graceful shutdown of all worker processes on API stop | P1 | M | M2 | `SIGTERM` to API process cleanly stops all child stream/recording workers, no orphaned FFmpeg processes |
| T-203 | Basic rate/resource guard (max concurrent streams) | P2 | S | M5 | Exceeding a configured max returns a clear error instead of degrading silently |
| T-204 | Structured perf note: frame-drop rate under N concurrent analytics-enabled streams | P2 | M | M9 | Documented, informs future scaling discussion |

## Explicit Non-Backlog (do not schedule unless requirements change)

Auth/RBAC · multi-tenant support · horizontal scaling · cloud object storage · Redis/Kafka event bus · mobile apps · alerting integrations beyond in-app feed. See [AI_PROJECT_CONTEXT.md](./AI_PROJECT_CONTEXT.md) §7 for rationale.
