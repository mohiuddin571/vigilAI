# Implementation Prompt: YOLO Integration — Object Detection & Classification (M9)

## Context

M9 is the first real detector plugin, proving the M8 orchestrator with actual inference instead of the no-op plugin. It implements `IDetectorPlugin` — the M8-established, orchestrator-facing contract (`docs/TECHNICAL_DECISIONS.md` TD-24 deleted the earlier M1 `IObjectDetector` port outright and superseded it with `IDetectorPlugin`; M9's `YoloObjectDetector` implements `IDetectorPlugin` directly, not a separate detector-specific port). Detection and classification come from one YOLO inference call, not two separate systems (`docs/TECHNICAL_DECISIONS.md` TD-06).

**Current repo state** (confirm against the working tree at execution time rather than trusting this paragraph — see Required Pre-Implementation Output): M0–M8 are complete. `backend/app/application/ports/detector_plugin.py::IDetectorPlugin` (`plugin_id`, `process(frame: Frame, context: dict) -> list[DetectionEvent]`), `backend/app/infrastructure/analytics/orchestrator.py::AnalyticsOrchestrator`, `backend/app/application/use_cases/run_analytics_pipeline.py::RunAnalyticsPipelineUseCase`, `backend/app/application/use_cases/analytics_session_registry.py::AnalyticsSessionRegistry`, `backend/app/infrastructure/streaming/supervised_frame_source.py::SupervisedFrameSource`, `backend/app/application/ports/event_repository.py::IEventRepository`, and the `/analytics/*` REST + `/ws/analytics/events` WebSocket surface all exist and work end-to-end today with `backend/app/infrastructure/analytics/noop_plugin.py::NoOpDetectorPlugin` as the only wired plugin. **Only one analytics-enableable source exists today**: `backend/app/core/container.py::_build_analytics_frame_source` hard-rejects any `source_id` other than the literal `"mp4-demo"` fixture — no real onboarded camera can be enabled for analytics yet. No `ultralytics`/`torch` dependency exists in `backend/pyproject.toml`. No `frontend/src/features/analytics-console/` folder exists yet. `docs/TECHNICAL_DECISIONS.md` TD-06's own "Future enhancement" line still says a swapped-in model would be "behind `IObjectDetector`" — stale since TD-24 retired that port (see Documentation Update Requirements).

## Documents Consulted

- `AGENTS.md` (full)
- `TASKS.md` (full; current state)
- `docs/IMPLEMENTATION_PLAN.md` §M8 (dependency context, confirmed complete) and §M9
- `docs/TASK_BACKLOG.md` Epic M8 (T-080/T-081/T-085, dependency context) and Epic M9 (T-090–T-093)
- `docs/TECHNICAL_DECISIONS.md` TD-06 (Ultralytics YOLOv8 + ByteTrack, alternatives considered — full), TD-05 (process-per-stream concurrency: sync/CPU-bound work must not block the asyncio API process), TD-24 (M8's as-built shape: `IDetectorPlugin` superseding `IObjectDetector`, `SupervisedFrameSource`, the single `"mp4-demo"` source, and its own "Future enhancement" note on adding process isolation once a real CPU-bound plugin exists and on per-`source_id` WebSocket filtering once M9+ wires multiple concurrently-enabled sources)
- `docs/ARCHITECTURE.md` §5 (Unified Frame Source) and §6.4 (Analytics Pipeline flow)
- `docs/FOLDER_STRUCTURE.md` (Backend/Frontend folder ownership, `storage/models/`, "Dependency Direction Rule")
- `docs/PROMPTING_GUIDE.md` §5 (Recurring Traps to Name Explicitly)
- `prompts/00-README.md`, `prompts/07-video-source-abstraction.md` (the plugin interface this milestone implements against — its own generated run prompt and TD-24 record what actually got built), `prompts/08-yolo-integration.md` (full)
- `README.md` (status line)
- Current repo state: `backend/app/application/ports/{detector_plugin.py,event_repository.py,frame_source.py}`, `backend/app/infrastructure/analytics/{orchestrator.py,noop_plugin.py}`, `backend/app/application/use_cases/{run_analytics_pipeline.py,analytics_session_registry.py}`, `backend/app/infrastructure/streaming/supervised_frame_source.py`, `backend/app/interfaces/{api/analytics.py,websocket/analytics_events.py,schemas/analytics.py}`, `backend/app/core/container.py` (analytics wiring, `_ANALYTICS_MP4_SOURCE_ID`, `_build_analytics_frame_source`), `backend/app/core/config.py` (confirmed no model-path setting exists), `backend/app/domain/value_objects/bounding_box.py` (normalized `[0,1]` coordinates), `backend/pyproject.toml` (confirmed no `ultralytics`/`torch`), `frontend/src/features/live-view/LiveView.tsx`, `.gitignore` (`storage/models/` already ignored) — confirmed absence of `yolo_detector.py` and `frontend/src/features/analytics-console/`.

## Scope

All of Epic M9 in `docs/TASK_BACKLOG.md`:

- T-090 — Ultralytics integration, model weight caching.
- T-091 — `YoloObjectDetector` plugin (detection + classification).
- T-092 — FPS/perf measurement on the Mac Mini, documented.
- T-093 — Frontend detection overlay (boxes + labels) on live view.

## Out of Scope

- Persistent object tracking (ByteTrack identity across frames) — its own `TASKS.md` line ("Object Tracking (ByteTrack, used by M9/M11)") and `prompts/09-object-tracking.md`; M9's own Acceptance Criteria and Definition of Done require detection + classification only, no track ID.
- Color Detection (M10), Loitering Detection (M11, including `AnalyticsZone`/`ZoneEditor.tsx`), Missing Object Detection (M12), License Plate Recognition (M13).
- Overlay rendering on recorded playback: `docs/IMPLEMENTATION_PLAN.md` §M9's Deliverables text names this as conditional ("if timestamps align with stored events"), not a hard requirement — treat as best-effort, not blocking, and do not let it expand this milestone's scope if the alignment turns out to be nontrivial.
- User authentication, RBAC, multi-tenancy, cloud/object storage, message brokers, mobile applications, and alerting integrations — explicit non-goals in `docs/AI_PROJECT_CONTEXT.md` §7.

## Acceptance Criteria

Copied verbatim from `docs/IMPLEMENTATION_PLAN.md` §M9:

- Running against the MP4 demo fixture produces correct-looking bounding boxes/classes for visible objects (spot-checked manually).
- Runs against the physical camera's live stream at an acceptable frame rate on the Mac Mini (document the achieved FPS — this is a legitimate prototype-stage finding, not a hidden failure).

Matching Definition of Done statements copied verbatim from `docs/TASK_BACKLOG.md` Epic M9:

- T-090: Cold start downloads once, cached thereafter.
- T-091: Bounding boxes + class labels attached to emitted events.
- T-092: Number recorded in TECHNICAL_DECISIONS.md or a perf note.
- T-093: Visually correct overlay during live/MP4 demo.

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`) — this plugin implements `IDetectorPlugin` and depends on `Frame` only; no ONVIF/RTSP imports (`docs/PROMPTING_GUIDE.md` §5).
- No new third-party dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR (`AGENTS.md` § Dependency Rules). `ultralytics`/`torch` itself is already decided and justified by TD-06 — adding the package is not a new decision, but any real implementation-time specifics (exact model variant, confidence/IoU thresholds, the caching/download mechanism, Settings field names) are, and need their own TD-18–TD-24-style entry.
- Model weights are cached under `storage/models/`, not committed to the repo (already gitignored).
- Analytics consumption must remain supervised — reuse `SupervisedFrameSource`/`ReconnectSupervisor` (TD-24 decision 3) rather than reading frames directly; do not bypass it.
- **Genuine gap**: only the `"mp4-demo"` fixture is wired as an analytics-enableable source today (`container.py::_build_analytics_frame_source`). This milestone's own AC #2 ("runs against the physical camera's live stream") requires a real onboarded camera to become analytics-enableable too — no document specifies this mechanism. A reasonable model is the existing `_build_live_stream_worker`/`OnvifRtspFrameSource` camera-resolution pattern (TD-21), wrapped the same way `Mp4FileFrameSource` is today (`SupervisedFrameSource`) — but confirm and document this as a real decision rather than assuming it.
- **Genuine gap**: TD-24 explicitly deferred process isolation for the Analytics Worker "until a real, CPU-bound M9+ plugin exists and profiling shows it stalls the API process" — YOLO inference is exactly that plugin. Decide whether `YoloObjectDetector.process()` runs inline in `RunAnalyticsPipelineUseCase.execute()`'s asyncio loop, via `run_in_executor`, or via a separate process, consistent with TD-05's "sync/process-isolated where CPU-bound" principle, and document the choice.
- **Possible gap**: TD-24 also names per-`source_id` filtering on `/ws/analytics/events` as a natural extension "once M9+ wires multiple concurrently-enabled real camera sources" — if this milestone enables analytics on both `"mp4-demo"` and a real camera concurrently, decide whether the frontend overlay needs that filter now or can manage without it, and document the choice either way.
- Never read configuration (model path, thresholds, etc.) via `os.environ` outside `backend/app/core/config.py`.

## Deliverables

Implement the M9 deliverables from `docs/IMPLEMENTATION_PLAN.md` §M9 at these paths:

- `backend/app/infrastructure/analytics/yolo_detector.py` — `YoloObjectDetector` implementing `IDetectorPlugin`, wired into `AnalyticsOrchestrator`'s plugin list in `backend/app/core/container.py` alongside (or replacing, if the pre-implementation plan concludes the no-op plugin's job is now fully subsumed — resolve this explicitly rather than assuming) `NoOpDetectorPlugin`.
- `frontend/src/features/analytics-console/DetectionOverlay.tsx` — new feature folder (per `docs/FOLDER_STRUCTURE.md`'s named `frontend/src/features/analytics-console/` area), rendering boxes/labels on the live view by subscribing to `/ws/analytics/events`.

Modify `backend/pyproject.toml` (add `ultralytics`), `backend/app/core/config.py` (model path/caching settings, per TD-13's "config only via Settings" rule — resolve exact field names in the pre-implementation plan), `backend/app/core/container.py` (plugin wiring and, per the Constraints gap above, the camera-backed analytics source), and `frontend/src/features/live-view/LiveView.tsx` (to mount the overlay). Resolve the exact additional paths (e.g. a `scripts/` model-download helper, mirroring `scripts/generate_sample_fixture.py`'s existing convention, if the caching mechanism needs one) in the required pre-implementation plan; do not create files for another milestone.

## Testing Expectations

Per `AGENTS.md` § Testing Expectations, and the template's own instruction: results spot-checked against the MP4 demo fixture for correctness (the AC's own wording — "spot-checked manually" — since ML output isn't the kind of thing a deterministic unit assertion should pin exactly); achieved FPS on the Mac Mini documented honestly, not hidden, even if the number is underwhelming.

- Cover `YoloObjectDetector.process()`'s shape mechanically with an automated test: given a frame from the committed `backend/tests/fixtures/sample.mp4` (or a frame with a known detectable object, if the existing synthetic fixture — per `docs/TECHNICAL_DECISIONS.md` TD-20's noted limitation that it contains no real detectable objects — doesn't suffice; flag this explicitly if it blocks meaningful automated coverage rather than silently accepting a no-op test), assert the returned `DetectionEvent`s have a populated `bounding_box` (normalized to `[0,1]` per the existing `BoundingBox` value object) and a class-label-bearing `event_type`/`metadata`.
- Document the manual spot-check (what fixture, what was visually confirmed) alongside the automated test, per the AC's own framing.
- Document achieved FPS per T-092's DoD, in `docs/TECHNICAL_DECISIONS.md` or a dedicated perf note.
- Do not weaken or delete the T-086 source-independence regression test — confirm it still passes unmodified (it exercises the no-op plugin specifically, so should be unaffected, but verify rather than assume).
- Run the repository's configured formatter, linter, type checker, and test suite before considering the milestone done.

## Documentation Update Requirements

- At the start, replace the current `TASKS.md` placeholder line `- [ ] _Nothing yet. Next up: YOLO Integration (M9)._` under `# In Progress` with `- [ ] YOLO Integration — Object Detection & Classification (M9)` (moved from `# Remaining`, removing it from that list). Once every acceptance criterion is met, move it to `# Completed` in the same PR, and restore the `# In Progress` section's placeholder line naming the next milestone (Object Tracking, per `TASKS.md`'s own ordering).
- Update `README.md`'s status line to reflect M9's completion.
- Correct `docs/TECHNICAL_DECISIONS.md` TD-06's "Future enhancement" line, which still says a swapped-in model would sit "behind `IObjectDetector`" — that port no longer exists (TD-24 retired it in favor of `IDetectorPlugin`); update the reference in the same PR per `AGENTS.md` § Documentation Update Policy, since this milestone is exactly the one implementing the concrete detector TD-06 was describing.
- Add a `docs/TECHNICAL_DECISIONS.md` entry for the model caching/download mechanism and its `Settings` fields, the CPU-bound execution strategy chosen for `YoloObjectDetector.process()`, the camera-backed analytics source wiring, and the per-source WS filtering decision — following the TD-18–TD-24 precedent of documenting implementation-time decisions the planning docs didn't fix precisely enough to derive without a real choice.
- If implementation reveals any other planning document was wrong or incomplete, update it in the same PR. Do not duplicate documentation into a new file — link to it.

## Milestone Boundary

Implement ONLY this milestone. Do not implement work belonging to any other milestone, even if it seems convenient or clearly needed soon. If, during implementation, you discover that another milestone's work is genuinely required to complete this one, stop and explain why before writing that code — do not silently expand scope.

This applies concretely to persistent tracking: `model.track()`/ByteTrack identity is a separate, later piece of work (`prompts/09-object-tracking.md`) even though it shares the same Ultralytics model object `YoloObjectDetector` loads here — do not enable tracking mode or persist track IDs as part of this milestone's `DetectionEvent`s. It applies equally to M8's already-complete abstractions: build on `IDetectorPlugin`/`AnalyticsOrchestrator`/`RunAnalyticsPipelineUseCase`/`AnalyticsSessionRegistry`/`SupervisedFrameSource` as they exist today; do not modify their internals to suit this milestone's convenience without first confirming the change is necessary.

## Required Pre-Implementation Output

Before writing any code, produce:

- **M8-precondition check** — confirm, against the working tree at execution time, that `IDetectorPlugin`, `AnalyticsOrchestrator`, `RunAnalyticsPipelineUseCase`, `AnalyticsSessionRegistry`, `SupervisedFrameSource`, and `IEventRepository` still exist as described in Context above, and confirm the current `_build_analytics_frame_source`'s single-source (`"mp4-demo"`) limitation. Expected: yes — but this is a live check against the actual working tree, not an assumption carried over from this prompt.
- **Implementation Plan** — describe: the model loading/caching mechanism and its new `Settings` fields; how YOLO's pixel-space boxes and class labels map onto `DetectionEvent`/the normalized `BoundingBox` value object and `event_type`/`metadata`; the CPU-bound execution strategy for `process()` and why (inline vs. `run_in_executor` vs. a separate process, per TD-05); how a real onboarded camera becomes an analytics-enableable `source_id`; whether per-source WebSocket filtering is added now; and `DetectionOverlay.tsx`'s design (how it subscribes to `/ws/analytics/events`, aligns boxes to the live `<img>`, and its best-effort approach to the conditional playback-overlay text).
- **Files to Create** — list every concrete path, including tests.
- **Files to Modify** — list every concrete path, including `backend/pyproject.toml`, `backend/app/core/container.py`, `backend/app/core/config.py`, `frontend/src/features/live-view/LiveView.tsx`, `TASKS.md`, `README.md`, and `docs/TECHNICAL_DECISIONS.md` (the TD-06 correction).
- **Risks** — address: inference latency stalling the asyncio event loop if run inline; the achieved FPS on the Mac Mini being genuinely low (document honestly per the AC, do not tune the milestone's scope to hide it); first-run model download requiring network access; and the synthetic MP4 fixture's known lack of real detectable objects (TD-20) limiting what "correct-looking bounding boxes" can mean for the automated (vs. manual) test.
- **Assumptions** — state only assumptions confirmed by the consulted documentation and current code. `IDetectorPlugin`/`AnalyticsOrchestrator`/`RunAnalyticsPipelineUseCase`/`AnalyticsSessionRegistry`/`SupervisedFrameSource` are M8-fixed and should be treated as given; the camera-backed analytics source wiring and the CPU-bound execution strategy are genuinely undefined upstream and must be treated as real decisions to make and document, not re-derived from a document that doesn't specify them.

This plan is produced first. Implementation proceeds only after it — and, if this is running interactively, only after the human reviewing it has had the chance to object, unless the human has explicitly asked for autonomous execution without a pause.

## Required Closing Report

On completion, produce:

- **Summary of Implementation**
- **Acceptance Criteria Satisfied** — check each exact item in the Acceptance Criteria section above.
- **Tradeoffs**
- **New Technical Decisions** — identify each one (model caching/Settings, CPU-bound execution strategy, camera-backed analytics source wiring, per-source WS filtering, at minimum) and confirm its corresponding `docs/TECHNICAL_DECISIONS.md` entry was added in the same PR, alongside the TD-06 correction.
- **Suggested Commit Message** — `Implement YOLO object detection and classification plugin (T-090, T-091, T-092, T-093)`.
- **Suggested PR Title** — `M9: YOLO Object Detection & Classification`.
