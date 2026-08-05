# Implementation Prompt: Object Tracking (ByteTrack) (M9/M11, T-110)

## Context

Object Tracking enables persistent per-object track IDs by switching `YoloObjectDetector`'s existing YOLO inference call from `model()` to Ultralytics' bundled `model.track()` (ByteTrack) — a mode change on the M9 call, not a second detection/tracking system (`docs/TECHNICAL_DECISIONS.md` TD-06). `docs/IMPLEMENTATION_PLAN.md` lists "Enable YOLO tracking" as §M11's opening deliverable, but `docs/TASK_BACKLOG.md` T-110's own Dependencies column names only T-091 (`YoloObjectDetector`, already complete) — not T-111 (`AnalyticsZone` CRUD) — and `TASKS.md` already tracks it as its own standalone Remaining line ("Object Tracking (ByteTrack, used by M9/M11)"), separate from "Loitering Detection (M11)". This milestone exists now, ahead of the rest of M11, so T-113's `LoiteringDetector` plugin (dwell time per zone, a later milestone) has stable per-object identity to measure dwell time against once it's built.

**Current repo state** (confirm against the working tree at execution time rather than trusting this paragraph — see Required Pre-Implementation Output): M0–M9 are complete (`TASKS.md`). `backend/app/infrastructure/analytics/yolo_detector.py::YoloObjectDetector` is the sole plugin wired into a single `AnalyticsOrchestrator` instance, built once in `Container.__init__` (`backend/app/core/container.py`) and **shared across every analytics-enabled source** — `_build_analytics_use_case` injects the same `self._analytics_orchestrator.process` into every `RunAnalyticsPipelineUseCase` it builds, regardless of `source_id`. `process()` currently calls `model(frame.image, conf=..., iou=..., device=..., verbose=False)` — a plain, non-tracking inference call — and maps each result box to a `DetectionEvent` via `_clamped_bounding_box`, attaching `class_id`/`class_label`/`frame_sequence`/`source_id` in `metadata`; no track id exists anywhere in this path today. `ultralytics>=8.4.115` is already a `backend/pyproject.toml` dependency (added for M9); ByteTrack ships inside it, so no new dependency is needed (TD-06). `backend/app/domain/entities/tracked_object.py::TrackedObject` (`camera_id`, `track_id`, `object_class`, `first_seen_at`, `last_seen_at`, `last_bounding_box`) already exists from M1 (T-012) but is unused by any code path. `backend/app/application/ports/detector_plugin.py::IDetectorPlugin.process(frame, context)`'s own docstring already anticipates this: "`context` carries cross-frame state a plugin needs (e.g. track history for loitering...)". `backend/tests/integration/analytics/test_yolo_detector_integration.py` covers `YoloObjectDetector.process()`'s current (non-tracking) mapping against a real decoded frame from `backend/tests/fixtures/sample.mp4`, using a stubbed Ultralytics-shaped model (`_StubModel`/`_StubResult`/`_StubBoxes`/`_StubTensor`) rather than real inference, because that fixture is a synthetic clip with no real COCO objects (`docs/TECHNICAL_DECISIONS.md` TD-20).

## Documents Consulted

- `AGENTS.md` (full)
- `TASKS.md` (full; current state)
- `docs/IMPLEMENTATION_PLAN.md` §M9 (dependency context, confirmed complete), §M11 (opening deliverable, "Enable YOLO tracking"), Milestone Dependency Graph
- `docs/TASK_BACKLOG.md` Epic M9 (T-090–T-093, dependency context) and Epic M11 (T-110–T-113)
- `docs/TECHNICAL_DECISIONS.md` TD-06 (full — decision, DeepSORT rejection, tradeoffs), TD-20 (`sample.mp4` synthetic-fixture limitation), TD-24 (`IDetectorPlugin`/`context` shape, `AnalyticsOrchestrator` layering), TD-25 (M9 as-built: execution strategy, camera-backed source, model/`Settings` fields)
- `docs/FOLDER_STRUCTURE.md` (Dependency Direction Rule, `backend/tests/` conventions, `storage/models/`)
- `prompts/09-object-tracking.md` (full)
- Current repo state: `backend/app/infrastructure/analytics/yolo_detector.py`, `backend/app/application/ports/detector_plugin.py`, `backend/app/infrastructure/analytics/orchestrator.py`, `backend/app/application/use_cases/run_analytics_pipeline.py`, `backend/app/domain/entities/detection_event.py`, `backend/app/domain/entities/tracked_object.py`, `backend/app/core/container.py` (plugin wiring, `_build_analytics_use_case`), `backend/app/core/config.py` (existing `yolo_*` `Settings` fields), `backend/pyproject.toml` (confirmed `ultralytics` already present), `backend/tests/integration/analytics/test_yolo_detector_integration.py`

## Scope

Standalone, ahead of the rest of M11 — not bundled with M11's zone/dwell-timer work. Basis: `docs/TASK_BACKLOG.md` T-110's Dependencies column names only T-091 (already complete), not T-111 (`AnalyticsZone` CRUD); `TASKS.md` already carries "Object Tracking (ByteTrack, used by M9/M11)" as its own Remaining line, distinct from "Loitering Detection (M11)"; and this template (`prompts/09-object-tracking.md`) is itself a separate file from `prompts/11-loitering-detection.md`. Maps to exactly one `docs/TASK_BACKLOG.md` row:

- T-110 — Enable YOLO/ByteTrack persistent track IDs (Epic M11, P0, Complexity M).

## Out of Scope

- T-111 (`AnalyticsZone` polygon CRUD API), T-112 (frontend zone editor), T-113 (`LoiteringDetector` plugin with dwell timer + de-dup) — all belong to `prompts/11-loitering-detection.md`, per this template's own Background/Scope framing.
- Color Detection (M10), Missing Object Detection (M12), License Plate Recognition (M13), Frontend Dashboard Integration (M14), Testing/Hardening (M15), Docker (M16).
- Persisting `TrackedObject` domain entities to a repository/database — no acceptance criterion for T-110 requires persistence; `TrackedObject` exists (M1/T-012) but is unused today, and whether/how it is touched here is addressed under Deliverables below rather than assumed in or out.
- User authentication, RBAC, multi-tenancy, cloud/object storage, message brokers, mobile applications, and alerting integrations — explicit non-goals in `docs/AI_PROJECT_CONTEXT.md` §7.

## Acceptance Criteria

Copied verbatim from `docs/TASK_BACKLOG.md` T-110's Definition of Done — the only backlog row this milestone maps to:

- Same object retains one ID across consecutive frames in a test clip.

`docs/IMPLEMENTATION_PLAN.md` §M11's own Acceptance Criteria ("a loitering event fires once per qualifying dwell period, not once per frame"; "Threshold and zone are configurable without a code change") describe the whole M11 milestone (zone + dwell timer + tracking together) and are not decomposed per-deliverable in that document — both criteria there test T-111/T-113's out-of-scope work, not tracking specifically, so they are not restated here. This is a genuine gap in how the plan document breaks down M11, not an omission by this prompt.

## Constraints

From `prompts/09-object-tracking.md`'s own Constraints:

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`).
- No new dependency — ByteTrack ships inside `ultralytics` already; do not add a separate tracking library (TD-06 explicitly rejected DeepSORT for this reason).
- Track IDs must be stable for a given object across consecutive frames in a test clip — this is the acceptance bar, verify with a test, not a visual spot-check alone.

Standing rules from `AGENTS.md` that apply to this milestone's kind of work:

- Never let an analytics/detector module import ONVIF or RTSP-specific code directly — it must depend on `IFrameSource`/`Frame` only (§ Things AI Must Never Do); this milestone touches `yolo_detector.py`, an analytics module.
- Never add a new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry (§ Dependency Rules) — reinforces the "no new dependency" constraint above; relevant only if the pre-implementation plan concludes a genuinely new package is needed, which TD-06 already says it should not be.
- Never delete or weaken the source-independence regression test (T-086) to make this change pass (§ Things AI Must Never Do) — confirm it still passes unmodified.
- Never read configuration via `os.environ` outside `backend/app/core/config.py` (§ Things AI Must Never Do) — applies if any new tracker-related setting is introduced.

## Deliverables

Neither `docs/IMPLEMENTATION_PLAN.md` §M11's Files list (`loitering_detector.py`, `analytics_zone.py`, `ZoneEditor.tsx` — all out of scope per above) nor this template's own Expected Deliverables placeholder name an exact file list for tracking; the template describes it only in prose as "a small, focused change to the M9 detector plugin/orchestrator context to carry track IDs forward." This is a genuine gap resolved as follows, using that description plus the current code read above:

- Modify `backend/app/infrastructure/analytics/yolo_detector.py` — the M9 YOLO call this template's Background identifies as what changes mode (`model()` → `model.track(..., persist=True)`, Ultralytics' documented tracking entry point that TD-06 already committed to using) — and its downstream mapping to `DetectionEvent`.
- How the resulting track id is surfaced on `DetectionEvent` is not fixed by any document read for this prompt: the existing `metadata` pattern already attaches `class_id`/`class_label` per box, the closest established precedent. State the chosen mechanism explicitly in the Required Pre-Implementation Output below rather than assuming it silently.
- Modify `backend/app/core/config.py` only if the pre-implementation plan concludes a new `Settings` field is genuinely needed — do not add one speculatively.
- Extend `backend/tests/integration/analytics/test_yolo_detector_integration.py` (or add a new test module alongside it, if the pre-implementation plan concludes the existing file's scope shouldn't grow) with the track-id-stability coverage described under Testing Expectations below.

## Testing Expectations

Per `AGENTS.md` § Testing Expectations, and this template's own instruction: "a test clip where the same object retains one ID across consecutive frames." `backend/tests/fixtures/sample.mp4` is a synthetic clip with no real COCO objects (`docs/TECHNICAL_DECISIONS.md` TD-20) — real inference against it produces no detections, which is exactly why `test_yolo_detector_integration.py` already stubs a fake Ultralytics-shaped model (`_StubModel`/`_StubResult`/`_StubBoxes`/`_StubTensor`) instead of loading real weights. Follow that same established pattern for the track-id test rather than attempting real inference against the fixture:

- Extend the stub shapes to carry a per-box track id (mirroring `xyxyn`/`cls`/`conf`'s existing tensor-like `.tolist()` shape) alongside the existing fields.
- Simulate at least two consecutive frames/inference calls through the same detector instance, with the stub model returning the same track id for what represents the same object across both, and assert `YoloObjectDetector` surfaces that same id both times — this is the acceptance bar from the Acceptance Criteria above, verified with a test, not a visual spot-check.
- Do not delete or weaken the T-086 source-independence regression test; confirm it still passes unmodified.
- Run the repository's configured formatter, linter, and type checker in addition to the test suite before considering the milestone done (`AGENTS.md` § Definition of Done).

## Documentation Update Requirements

- At the start, replace the current `TASKS.md` placeholder line `- [ ] _Nothing yet. Next up: Object Tracking._` under `# In Progress` with `- [ ] Object Tracking (ByteTrack, used by M9/M11)` (moved from `# Remaining`, removing it from that list). Once T-110's acceptance criterion is met, move it to `# Completed` in the same PR, and restore the `# In Progress` section's placeholder line naming the next item (Color Detection, per `TASKS.md`'s own ordering).
- If implementation reveals any planning document (`docs/TECHNICAL_DECISIONS.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/FOLDER_STRUCTURE.md`) was wrong or incomplete, update it in the same PR (`AGENTS.md` § Documentation Update Policy) — do not duplicate content into a new location, link to it instead.
- `README.md`: not expected to need an update — this is a backend-internal mode-change on an existing inference call, with no new setup step, no new dependency, and no user-visible change to onboarding/setup instructions; update it only if implementation reveals otherwise.
- Add a `docs/TECHNICAL_DECISIONS.md` entry (see Required Closing Report) for the real implementation-time decisions this milestone makes — at minimum, how the track id is carried on `DetectionEvent`, and how tracker state (`persist=True`) is scoped given that a single `AnalyticsOrchestrator`/`YoloObjectDetector` instance is shared across every analytics-enabled source today (see Context and Required Pre-Implementation Output).

## Milestone Boundary

Implement ONLY this milestone. Do not implement work belonging to any other milestone, even if it seems convenient or clearly needed soon. If, during implementation, you discover that another milestone's work is genuinely required to complete this one, stop and explain why before writing that code — do not silently expand scope.

This applies concretely to `AnalyticsZone`/zone CRUD/the zone editor/`LoiteringDetector` (T-111–T-113): do not build any part of them here, even though `docs/IMPLEMENTATION_PLAN.md` groups them under the same §M11 heading as tracking — they depend on this milestone's output, not the reverse, and are a separate prompt (`prompts/11-loitering-detection.md`). It applies equally to M8/M9's already-complete abstractions: build on `IDetectorPlugin`/`AnalyticsOrchestrator`/`RunAnalyticsPipelineUseCase`/`AnalyticsSessionRegistry`/`YoloObjectDetector`'s existing detection+classification mapping as they exist today; do not restructure them beyond what enabling tracking requires without first confirming the change is necessary.

## Required Pre-Implementation Output

Before writing any code, produce:

- **M9-precondition check** — confirm, against the working tree at execution time, that `YoloObjectDetector`, `IDetectorPlugin`, `AnalyticsOrchestrator`, and the single-shared-orchestrator wiring in `container.py` still exist as described in Context above. Expected: yes — but this is a live check against the actual working tree, not an assumption carried over from this prompt.
- **Implementation Plan** — describe: exactly how `model.track()` is invoked from `process()` (parameters, `persist=True` semantics); how the returned track id is carried onto `DetectionEvent` (the `metadata` key chosen, following or deliberately diverging from the existing `class_id`/`class_label` pattern); whether/how it interacts with the `IDetectorPlugin` `context` dict already earmarked in its own docstring for "track history"; and whether `TrackedObject` (M1/T-012, currently unused) is constructed here or left for a later milestone to adopt.
- **Files to Create**
- **Files to Modify**
- **Risks** — address at least: `AnalyticsOrchestrator` is instantiated once in `Container.__init__` and shared across every concurrently-enabled analytics source (confirmed in Context above) — a single `YoloObjectDetector`, and therefore a single underlying Ultralytics tracker, would receive interleaved frames from every enabled source if more than one is active at once; confirm whether `persist=True` tracker state is safe under that sharing or whether track ids need to be scoped per `source_id`, and treat this as a real risk to resolve or explicitly document as a known limitation, not a hypothetical. Also address: the synthetic `sample.mp4` fixture's lack of real objects (TD-20), constraining what an automated test can assert beyond the stubbed-model approach already used in `test_yolo_detector_integration.py`.
- **Assumptions** — state only assumptions confirmed by the consulted documentation and current code. `IDetectorPlugin`/`AnalyticsOrchestrator`/`RunAnalyticsPipelineUseCase`/`YoloObjectDetector`'s detection+classification mapping are M8/M9-fixed and should be treated as given; the exact `DetectionEvent` metadata surface for the track id, whether `TrackedObject` is constructed, and the per-source tracker-state scoping are genuinely undefined upstream and must be treated as real decisions to make and document, not re-derived from a document that doesn't specify them.

This plan is produced first. Implementation proceeds only after it — and, if this is running interactively, only after the human reviewing it has had the chance to object, unless the human has explicitly asked for autonomous execution without a pause.

## Required Closing Report

On completion, produce:

- **Summary of Implementation**
- **Acceptance Criteria Satisfied** — check the exact item in the Acceptance Criteria section above.
- **Tradeoffs**
- **New Technical Decisions** — identify each one made (at minimum: the `DetectionEvent` track-id surface, the `persist=True`/tracker-scoping resolution, and whether `TrackedObject` is adopted) and confirm a corresponding `docs/TECHNICAL_DECISIONS.md` entry was added in the same PR (`AGENTS.md` § Dependency Rules and § Documentation Update Policy), not just mentioned in the PR description.
- **Suggested Commit Message** — `Enable YOLO/ByteTrack persistent track IDs (T-110)`.
- **Suggested PR Title** — `Object Tracking (ByteTrack)`.
