# Implementation Prompt: Loitering Detection (M11)

## Context

Loitering Detection flags an object/person that remains inside a defined zone longer than a configurable duration, using the per-object identity ByteTrack tracking already provides (`docs/IMPLEMENTATION_PLAN.md` §M11). It exists now because `docs/IMPLEMENTATION_PLAN.md`'s Milestone Dependency Graph places `M9 --> M11`, M9 (Object Detection & Classification) is complete, and `TASKS.md`'s own "In Progress" line already reads `_Nothing yet. Next up: Loitering Detection._` with M10 (Color Detection) moved to Completed. Persistent track IDs (`docs/IMPLEMENTATION_PLAN.md` §M11's own first deliverable, "Enable YOLO tracking") were **already delivered** as a standalone piece of work ahead of this milestone: `TASKS.md`'s Completed list carries "Object Tracking (ByteTrack, used by M9/M11)" (commit `a3c33b5`, T-110), documented in `docs/TECHNICAL_DECISIONS.md` TD-26. This milestone consumes that existing track-id surface — it does not re-implement tracking.

**Current repo state** (confirm against the working tree at execution time rather than trusting this paragraph — see Required Pre-Implementation Output): `backend/app/domain/entities/analytics_zone.py::AnalyticsZone` already exists from M1 (T-012) — a dataclass with `camera_id: UUID`, `name: str`, `polygon: list[tuple[float, float]]` (validated to have ≥3 points), `id: UUID` — but it has **no persistence port, no SQL adapter, no API route, and no dwell-threshold field**; nothing in `backend/app/application/ports/`, `backend/app/interfaces/api/`, or `backend/app/core/container.py` references it today. `backend/app/domain/value_objects/bounding_box.py::BoundingBox` stores coordinates **normalized to `[0, 1]` relative to the source frame**, not pixel coordinates — `AnalyticsZone.polygon`'s own coordinate space is not fixed by its current definition. `backend/app/infrastructure/analytics/yolo_detector.py::YoloObjectDetector` already writes each frame's own `DetectionEvent`s (each carrying `metadata["track_id"]: int | None` and a `bounding_box: BoundingBox`) into the shared `context` dict under the exported key `EVENTS_BY_SOURCE_CONTEXT_KEY = "yolo_object_detector.events_by_source"`, keyed by `frame.source_id` — this is the same same-frame producer/consumer handoff `ColorDetector` already uses (`docs/TECHNICAL_DECISIONS.md` TD-27). `AnalyticsOrchestrator` (`backend/app/infrastructure/analytics/orchestrator.py`) confirms `context` is "one shared, mutable dict for the lifetime of this orchestrator instance... plugins may store their own cross-frame state in it (namespaced by `plugin_id` if needed)" — this is the mechanism `docs/ARCHITECTURE.md` §6.4 names explicitly for "track history for loitering." No `domain/events/` module exists yet, despite `docs/FOLDER_STRUCTURE.md` listing `LoiteringDetected` as an example domain event; every existing plugin (`NoOpDetectorPlugin`, `YoloObjectDetector`, `ColorDetector`) instead returns plain `DetectionEvent`s with a namespaced `event_type` string (e.g. `f"color_detection.{label.value}"`).

## Documents Consulted

- `AGENTS.md` (full)
- `TASKS.md` (full; current state)
- `docs/IMPLEMENTATION_PLAN.md` §M9 (dependency context, confirmed complete), §M11 (Goal, Deliverables, Files, Acceptance Criteria, Dependencies), Milestone Dependency Graph
- `docs/TASK_BACKLOG.md` Epic M9 (dependency context), Epic M11 (T-110, T-111, T-112, T-113)
- `docs/AI_PROJECT_CONTEXT.md` §2 (Required Capabilities), §6 (Glossary — Loitering Detection), §7 (Non-Goals), §8 (Coding Standards)
- `docs/ARCHITECTURE.md` §6.4 (Analytics Pipeline flow; `IDetectorPlugin.process(frame, context)` shape; `context` as cross-frame state, explicitly naming "track history for loitering"; the one documented same-frame exception for `ColorDetector`)
- `docs/FOLDER_STRUCTURE.md` (Dependency Direction Rule; `infrastructure/analytics/` folder already naming `LoiteringDetector`; `domain/events/` convention naming `LoiteringDetected`; `application/ports/` convention; `core/` as composition root)
- `docs/TECHNICAL_DECISIONS.md` TD-06 (YOLO/ByteTrack, one inference call, no second tracking dependency), TD-24 (`IDetectorPlugin`/`AnalyticsOrchestrator` layering, `context` ownership, per-source `AnalyticsSessionRegistry`), TD-25 (camera-backed analytics sources), TD-26 (Object Tracking as-built: `model.track()` mode change, per-source model/tracker scoping, `metadata["track_id"]` surface — T-110 already complete), TD-27 (Color Detection as-built: the `EVENTS_BY_SOURCE_CONTEXT_KEY` same-frame handoff precedent and its own "Future enhancement" note anticipating reuse by a future plugin), TD-18/TD-19/TD-20/TD-22 (precedent for additive port/entity extensions when a milestone's plan under-specifies a persistence or config shape)
- `docs/PROMPTING_GUIDE.md` §1, §3, §4 (architecture-sensitive-refactor example: confirm interface fit before writing code, or propose the smallest change), §5 (recurring traps), §6 (non-implementation prompting), §7 (keeping docs/code honest)
- `prompts/11-loitering-detection.md` (full)
- `prompts/09-object-tracking.md` (full — confirms T-110 is scoped as a standalone, already-completed unit of work "consumed by M11", not part of this milestone's own deliverables)
- `prompts/runs/10-color-detection-run.md` (full — the immediately preceding milestone's generated run prompt, read for continuity of established conventions: the `context` same-frame handoff, plugin registration in `container.py`, event-correlation-via-`metadata` pattern)
- Current repo state: `backend/app/domain/entities/analytics_zone.py`, `backend/app/domain/entities/detection_event.py`, `backend/app/domain/value_objects/bounding_box.py`, `backend/app/application/ports/{detector_plugin.py, camera_repository.py, recording_repository.py}` (repository-port shape precedent), `backend/app/infrastructure/analytics/{orchestrator.py, yolo_detector.py, color_detector.py}`, `backend/app/interfaces/api/analytics.py`, `backend/app/interfaces/schemas/analytics.py`, `backend/app/core/container.py` (plugin/repository wiring), `backend/tests/unit/domain/test_analytics_zone.py` if present, `backend/tests/integration/analytics/test_yolo_detector_integration.py` (fake-model test pattern), `frontend/src/features/analytics-console/DetectionOverlay.tsx`

## Scope

Maps to Epic M11 in `docs/TASK_BACKLOG.md`:

- T-111 — `AnalyticsZone` polygon CRUD (API) (P0, Complexity M, depends on T-012).
- T-112 — Frontend zone editor (draw polygon on still frame) (P1, Complexity M, depends on T-111).
- T-113 — `LoiteringDetector` plugin with dwell timer + de-dup (P0, Complexity L, depends on T-110, T-111).

**T-110 (Enable YOLO/ByteTrack persistent track IDs) is already complete** (`TASKS.md` Completed list, `docs/TECHNICAL_DECISIONS.md` TD-26) and is explicitly out of scope for this PR — this prompt builds on its existing output (`DetectionEvent.metadata["track_id"]`), it does not modify `YoloObjectDetector`'s tracking behavior.

## Out of Scope

- T-110 / any change to `YoloObjectDetector`'s `model.track()` call, per-source model scoping, or tracker configuration — already delivered; consume its output only.
- Missing Object Detection (M12), License Plate Recognition (M13), Frontend Dashboard Integration (M14), Testing/Hardening (M15), Docker (M16).
- Re-running or modifying M9/M10's own detection/classification/color logic (`YoloObjectDetector`, `ColorDetector`) beyond whatever minimal, explicitly-justified addition the Required Pre-Implementation Output concludes is genuinely required for `LoiteringDetector` to consume the same-frame bounding-box/track-id data those plugins already publish into `context`.
- User authentication, RBAC, multi-tenancy, cloud/object storage, message brokers, GPU cluster inference scaling, mobile applications, and alerting integrations beyond the in-app event feed — explicit non-goals in `docs/AI_PROJECT_CONTEXT.md` §7.

## Acceptance Criteria

Copied verbatim from `docs/IMPLEMENTATION_PLAN.md` §M11:

- "Against the MP4 fixture (or live camera) with a defined zone and a low test threshold (e.g. 5s), a loitering event fires once per qualifying dwell period, not once per frame."
- "Threshold and zone are configurable without a code change."

Copied verbatim from `docs/TASK_BACKLOG.md` Epic M11's Definition of Done column:

- T-111: "Zone persists, retrievable per camera"
- T-112: "Polygon saved matches what was drawn"
- T-113: "One event per qualifying dwell period, not per frame (explicit test)"

## Constraints

From `prompts/11-loitering-detection.md`'s own Constraints:

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`).
- No new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR.
- Must emit **one event per qualifying dwell period, not once per frame** — this is an explicit acceptance criterion (T-113), not an implementation detail to skip.
- Zone and threshold must be configurable without a code change.

Standing rules from `AGENTS.md` that apply to this milestone's kind of work:

- Never let an analytics/detector module import ONVIF or RTSP-specific code directly — it must depend on `IFrameSource`/`Frame` only (§ Things AI Must Never Do); `loitering_detector.py` is an analytics module.
- Never have a use case call an infrastructure adapter directly instead of through a port (§ Things AI Must Never Do) — the new `AnalyticsZone` CRUD use case(s) required by T-111 must depend on a new repository port, not a concrete SQL class.
- Never add a new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry (§ Dependency Rules) — a point-in-polygon containment check needs no new package (pure Python/`numpy`, both already available per TD-04/TD-20/TD-25); only add one (e.g. `shapely`) if the pre-implementation plan concludes it's genuinely necessary, with the TD entry justifying why the already-available primitives don't suffice.
- Never read configuration via `os.environ` outside `backend/app/core/config.py` (§ Things AI Must Never Do) — applies if any dwell-threshold default becomes a `Settings` field.
- Never delete or weaken the source-independence regression test (T-086) to make this change pass (§ Things AI Must Never Do) — confirm it still passes unmodified.
- Verify the `context` mechanism and the `EVENTS_BY_SOURCE_CONTEXT_KEY` handoff actually fit `LoiteringDetector`'s needs before writing code against them, per `docs/PROMPTING_GUIDE.md` §4 and `AGENTS.md` § Rules for AI Coding Assistants — if they don't fit cleanly, stop and propose the smallest interface change, don't work around it with a hack.

## Deliverables

`docs/IMPLEMENTATION_PLAN.md` §M11's Files list names three items: `backend/app/infrastructure/analytics/loitering_detector.py`, `backend/app/domain/entities/analytics_zone.py`, `frontend/src/features/analytics-console/ZoneEditor.tsx`. Resolved against current repo structure and `docs/FOLDER_STRUCTURE.md` (the same category of gap TD-18 through TD-27 each already documented for their own milestone's under-specified Files list):

- `backend/app/infrastructure/analytics/loitering_detector.py` (new) — `LoiteringDetector` implementing `IDetectorPlugin` (`backend/app/application/ports/detector_plugin.py`): for each tracked object inside an enabled zone for its camera/source, accumulates dwell time in `context` (namespaced per `docs/ARCHITECTURE.md` §6.4's own guidance, and per-`source_id` following TD-26/TD-27's precedent against cross-source state bleed in the single shared `AnalyticsOrchestrator`), and emits a `DetectionEvent` once a configured threshold is first crossed for that track — not on every subsequent qualifying frame.
- `backend/app/domain/entities/analytics_zone.py` — already exists (M1/T-012) with `camera_id`/`name`/`polygon`/`id`; whether it needs an additive extension (e.g. a dwell-threshold field, following the additive-extension precedent TD-18/TD-19 already established for this project rather than reopening the entity's existing fields) is a genuine, currently-unresolved question — resolve and state the answer in the Required Pre-Implementation Output before implementing T-111/T-113.
- T-111's CRUD API is not named in §M11's Files list at all (the same gap TD-18 documented for M3's persistence layer). Resolved against `docs/FOLDER_STRUCTURE.md`'s conventions and the existing `ICameraRepository`/`IRecordingRepository` shape (`backend/app/application/ports/`): a new repository port for `AnalyticsZone` (e.g. `add`/`get`/`list`/`update`, plus a per-camera list method to satisfy T-111's "retrievable per camera" DoD), a new SQL adapter under `backend/app/infrastructure/persistence/`, and new API endpoints + Pydantic schemas — following `docs/FOLDER_STRUCTURE.md`'s "one router module per resource" convention (`cameras.py`, `recordings.py`, `analytics.py`, `streams.py` already exist), whether zone routes belong in `backend/app/interfaces/api/analytics.py` or a new `backend/app/interfaces/api/zones.py` is not fixed upstream — state the exact choice in the pre-implementation plan.
- `backend/app/core/container.py` — wire the new `AnalyticsZone` repository/use case(s), and add `LoiteringDetector` to `AnalyticsOrchestrator`'s plugin list, following the existing `YoloObjectDetector`/`ColorDetector` registration precedent (ordering matters, per the existing in-file comment explaining why `ColorDetector` runs after `YoloObjectDetector` — `LoiteringDetector` has the same same-frame dependency on `YoloObjectDetector`'s published context).
- `frontend/src/features/analytics-console/ZoneEditor.tsx` (new, T-112) — draws a polygon on a still frame and persists it via T-111's API. The coordinate space mismatch noted in Context (pixel coordinates drawn in-browser vs. `BoundingBox`'s normalized `[0, 1]` space used by detection/tracking) must be resolved explicitly — state where normalization happens (on save in the frontend, or on read in the backend) in the pre-implementation plan.

## Testing Expectations

Per `AGENTS.md` § Testing Expectations and this template's own instruction: "a test (against the MP4 fixture or synthetic track data) with a low threshold confirming exactly one event fires per qualifying dwell period" — matching T-113's Definition of Done verbatim.

- A test driving `LoiteringDetector.process()` across a sequence of frames/synthetic `context` states representing the same track id remaining inside a zone past a low test threshold (e.g. 5s, per the milestone AC's own suggested value), asserting exactly one `DetectionEvent` is emitted for that dwell period — not one per frame while the threshold remains crossed. Prefer synthetic track data (constructed `DetectionEvent`/`context` fixtures) over a dependency on real footage, consistent with `backend/tests/integration/analytics/test_yolo_detector_integration.py`'s existing precedent of stubbing rather than requiring `@pytest.mark.hardware`, since `backend/tests/fixtures/sample.mp4` is documented (TD-20, TD-25) as a synthetic moving-circle clip with no real loitering scenario in it.
- A unit test for the zone repository/use case(s) (T-111) proving a zone persists and is retrievable per camera, per its DoD, using a fake or the same real-SQLite integration pattern already used for `SqlRecordingRepository`.
- Do not delete or weaken the T-086 source-independence regression test; confirm it still passes unmodified.
- Run the repository's configured formatter, linter, and type checker in addition to the test suite before considering the milestone done (`AGENTS.md` § Definition of Done).

## Documentation Update Requirements

- At the start, replace `TASKS.md`'s current `- [ ] _Nothing yet. Next up: Loitering Detection._` line under `# In Progress` with `- [ ] Loitering Detection (M11)` (moved from `# Remaining`, removing it from that list). Once T-111/T-112/T-113's acceptance criteria are met, move it to `# Completed` in the same PR, and restore the `# In Progress` section's placeholder line naming the next item (Missing Object Detection, M12, per `TASKS.md`'s own ordering).
- If implementation reveals any planning document (`docs/TECHNICAL_DECISIONS.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/ARCHITECTURE.md`, `docs/FOLDER_STRUCTURE.md`) was wrong or incomplete — most likely `docs/FOLDER_STRUCTURE.md`'s `domain/events/` mention of `LoiteringDetected` (currently unbuilt), or `AnalyticsZone`'s field set, given the design gaps identified in Deliverables above — update it in the same PR (`AGENTS.md` § Documentation Update Policy); never duplicate content into a new location, link to it instead.
- `README.md`: only if T-112's zone editor or the new zone CRUD endpoints change a documented setup/usage step (unlikely, per this project's own pattern for prior plugin milestones — see `prompts/runs/10-color-detection-run.md`'s same assessment). Update it only if implementation reveals otherwise.
- Add a `docs/TECHNICAL_DECISIONS.md` entry (see Required Closing Report) for the real implementation-time decisions this milestone makes.

## Milestone Boundary

Implement ONLY this milestone. Do not implement work belonging to any other milestone, even if it seems convenient or clearly needed soon. If, during implementation, you discover that another milestone's work is genuinely required to complete this one, stop and explain why before writing that code — do not silently expand scope.

This applies concretely to `MissingObjectDetector` (M12), `LicensePlateRecognizer` (M13), and any frontend dashboard integration work beyond `ZoneEditor.tsx` itself (M14): do not build any part of them here. It applies equally to M9/M10's already-complete abstractions and to T-110's already-complete tracking: build on `IDetectorPlugin`/`AnalyticsOrchestrator`/`RunAnalyticsPipelineUseCase`/`YoloObjectDetector`/`ColorDetector` as they exist today; the only permitted change to `YoloObjectDetector`, `ColorDetector`, `IDetectorPlugin`, or `AnalyticsOrchestrator` is the minimal one the Required Pre-Implementation Output concludes is genuinely necessary for `LoiteringDetector` to consume the same-frame bounding-box/track-id data those plugins already publish — not a broader restructuring, and never a change to how `model.track()` itself is invoked.

## Required Pre-Implementation Output

Before writing any code, produce:

- **Repo-state precondition check** — confirm, against the working tree at execution time, that `AnalyticsZone`, `IDetectorPlugin`, `AnalyticsOrchestrator`, `YoloObjectDetector`'s `EVENTS_BY_SOURCE_CONTEXT_KEY`/`metadata["track_id"]` surface, and the single-shared-orchestrator wiring in `container.py` still exist as described in Context above.
- **Implementation Plan** — must resolve, explicitly:
  1. How `LoiteringDetector` obtains the current frame's bounding boxes and track ids — confirm reuse of the existing `EVENTS_BY_SOURCE_CONTEXT_KEY` handoff (TD-27's own precedent) fits, before writing code against it; if it doesn't, propose the smallest interface change and flag it for confirmation.
  2. Where the dwell-threshold value lives and how it's configured "without a code change" (AC #2) — an additive field on `AnalyticsZone`, a `Settings` default, or another mechanism — and why.
  3. The polygon-containment check: which point of a tracked object's `BoundingBox` is tested against `AnalyticsZone.polygon` (e.g. center vs. bottom-center/foot point), the algorithm used (no new dependency required unless justified), and the coordinate-space reconciliation between `BoundingBox`'s normalized `[0, 1]` space and whatever space `AnalyticsZone.polygon`/the frontend zone editor produces.
  4. The dwell-timer state machine per track id: when timing starts/resets (zone entry/exit), when the de-dup "already fired" flag resets (if ever), and how state for a track id is evicted so `context` doesn't grow unboundedly for tracks that leave and never return.
  5. Whether `LoiteringDetector` emits a plain `DetectionEvent` (following `YoloObjectDetector`/`ColorDetector`'s established pattern) or introduces a new `domain/events/LoiteringDetected` class (per `docs/FOLDER_STRUCTURE.md`'s example, currently unbuilt) — and why.
  6. The exact shape of T-111's new repository port, SQL adapter, API routes, and schemas, and which existing router file (or new one) the routes live in.
- **Files to Create**
- **Files to Modify**
- **Risks** — address at least: unbounded `context` growth from per-track dwell state across long-running sources; the single-shared-`AnalyticsOrchestrator`-across-sources scoping (TD-26/TD-27's already-documented concern) applied to per-zone, per-track dwell state; and the coordinate-space mismatch between the zone editor's drawn polygon and `BoundingBox`'s normalized space.
- **Assumptions** — state only assumptions confirmed by the consulted documentation and current code; the dwell-threshold configuration mechanism, the polygon-containment point/algorithm, the dwell-timer state machine, and the T-111 port/route shape are genuinely undefined upstream and must be treated as real decisions to make and document, not re-derived from a document that doesn't specify them.

This plan is produced first. Implementation proceeds only after it — and, if this is running interactively, only after the human reviewing it has had the chance to object, unless the human has explicitly asked for autonomous execution without a pause.

## Required Closing Report

On completion, produce:

- **Summary of Implementation**
- **Acceptance Criteria Satisfied** — check each item in the Acceptance Criteria section above.
- **Tradeoffs**
- **New Technical Decisions** — identify each one made (at minimum: how `LoiteringDetector` accesses same-frame bounding-box/track-id data; the dwell-threshold configuration mechanism and any `AnalyticsZone`/`Settings` extension; the polygon-containment point/algorithm and coordinate-space reconciliation; the dwell-timer/de-dup state machine; the T-111 port/persistence/route shape; whether a new domain event class was introduced) and confirm a corresponding `docs/TECHNICAL_DECISIONS.md` entry was added in the same PR (`AGENTS.md` § Dependency Rules and § Documentation Update Policy), not just mentioned in the PR description.
- **Suggested Commit Message** — imperative summary referencing `T-111, T-112, T-113` (e.g. `Add loitering zone CRUD, zone editor, and dwell-time detection plugin (T-111, T-112, T-113)`), per `AGENTS.md` § Commit Message Conventions.
- **Suggested PR Title** — `M11: Loitering Detection`.
