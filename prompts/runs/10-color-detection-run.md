# Implementation Prompt: Color Detection (M10)

## Context

Color Detection extracts a dominant color label (e.g. "red", "blue", "black") for each object M9's `YoloObjectDetector` already finds, so a `ColorDetector` plugin crops each detected bounding box, computes a dominant color, and surfaces that label alongside the object detection in the live analytics console (`docs/IMPLEMENTATION_PLAN.md` §M10). It exists now because `docs/IMPLEMENTATION_PLAN.md`'s Milestone Dependency Graph places `M9 --> M10`, M9 (Object Detection & Classification, T-090–T-093) and its Object Tracking follow-on (T-110) are both complete (`TASKS.md` Completed list; commit `a3c33b5`), and `TASKS.md`'s own "In Progress" line already reads `_Nothing yet. Next up: Color Detection._`. M10 consumes M9's bounding boxes; it does not run its own object detection.

**Current repo state** (confirm against the working tree at execution time rather than trusting this paragraph — see Required Pre-Implementation Output): `backend/app/domain/value_objects/color_label.py::ColorLabel` (a `StrEnum` with ten members: red/orange/yellow/green/blue/purple/black/white/gray/brown) already exists from M1 but is not referenced by any plugin or use case yet — reuse it, do not redefine color labels elsewhere. `backend/app/domain/entities/detection_event.py::DetectionEvent` has no dedicated color field, only `bounding_box: BoundingBox | None` and a free-form `metadata: dict[str, Any]`. `backend/app/infrastructure/analytics/yolo_detector.py::YoloObjectDetector` is currently the sole plugin wired into the single `AnalyticsOrchestrator` instance built in `Container.__init__` (`backend/app/core/container.py`), which every analytics-enabled source shares. `AnalyticsOrchestrator.process()` (`backend/app/infrastructure/analytics/orchestrator.py`) calls each plugin's `process(frame, context)` in sequence and `.extend()`s the returned `list[DetectionEvent]` onto one local list — **no plugin receives the events another plugin returned for the same frame**; each plugin only sees `frame` and the one shared `context: dict[str, Any]`.

This last point is a genuine, unresolved conflict this prompt must not silently paper over: `prompts/10-color-detection.md`'s own Background section (and `docs/IMPLEMENTATION_PLAN.md` §M10's "consumes bounding boxes" framing) assumes `ColorDetector` reads M9's bounding boxes for the current frame via `context`. But `docs/ARCHITECTURE.md` §6.4, `IDetectorPlugin`'s own docstring, and `docs/TECHNICAL_DECISIONS.md` TD-26 all describe `context` as *per-plugin cross-frame* state ("track history for loitering, the baseline reference for missing-object detection"), explicitly **not** a channel for one plugin to read another plugin's *same-frame* output — `IDetectorPlugin`'s docstring states plugins "must never read another plugin's private key out of it," and TD-26 confirms as of today "no plugin writes to it yet." `docs/PROMPTING_GUIDE.md` §4's own "Good Prompt (architecture-sensitive refactor)" example was written for exactly this situation, naming T-100 directly: confirm whether `ColorDetector` can receive M9's `BoundingBox` results via `context` as currently shaped before writing code against it; if it doesn't fit cleanly, stop and propose the smallest interface change needed rather than working around the gap with a hack (`AGENTS.md` § Rules for AI Coding Assistants: "verify a port/interface actually fits before writing code against it, and raise it rather than working around a bad fit"). This is the central design question the Required Pre-Implementation Output below must resolve before any code is written.

## Documents Consulted

- `AGENTS.md` (full)
- `TASKS.md` (full; current state)
- `docs/IMPLEMENTATION_PLAN.md` §M9 (dependency context, confirmed complete), §M10 (Goal, Deliverables, Files, Acceptance Criteria, Dependencies), Milestone Dependency Graph
- `docs/TASK_BACKLOG.md` Epic M9 (T-090–T-093, dependency context), Epic M10 (T-100, T-101)
- `docs/ARCHITECTURE.md` §6.4 (Analytics Pipeline flow, `IDetectorPlugin.process(frame, context)` shape, per-plugin-not-cross-plugin `context` semantics)
- `docs/FOLDER_STRUCTURE.md` (Dependency Direction Rule; `infrastructure/analytics/` folder contents already naming `ColorDetector`; `core/` as composition root; `backend/tests/` conventions)
- `docs/TECHNICAL_DECISIONS.md` TD-04/TD-20 (`opencv-python-headless` already a dependency — no new image-processing dependency needed for an HSV/k-means approach), TD-06 (YOLO/ByteTrack, one inference call), TD-24 (`IDetectorPlugin`/`AnalyticsOrchestrator` layering, `context` ownership), TD-25 (M9 as-built specifics), TD-26 (Object Tracking as-built; explicitly confirms `context` is unwritten-to by any plugin today)
- `docs/PROMPTING_GUIDE.md` §1, §4 (architecture-sensitive-refactor example named specifically for T-100), §5 (recurring traps), §7 (keeping docs/code honest)
- `docs/AI_PROJECT_CONTEXT.md` §7 (Non-Goals), §8 (Coding Standards)
- `prompts/10-color-detection.md` (full)
- Current repo state: `backend/app/infrastructure/analytics/{orchestrator.py, yolo_detector.py, noop_plugin.py}`, `backend/app/application/ports/detector_plugin.py`, `backend/app/domain/entities/{detection_event.py, frame.py}`, `backend/app/domain/value_objects/color_label.py`, `backend/app/core/container.py` (plugin wiring), `backend/tests/unit/domain/test_color_label.py`, `backend/tests/integration/analytics/test_yolo_detector_integration.py`, `frontend/src/features/analytics-console/DetectionOverlay.tsx`, `backend/pyproject.toml` (confirmed `opencv-python-headless` present, no `scikit-learn`)

## Scope

Maps to Epic M10 in `docs/TASK_BACKLOG.md`:

- T-100 — HSV-histogram dominant-color extraction on bbox crop (P0, Complexity M, depends on T-091).
- T-101 — Color label surfaced in event payload + UI (P0, Complexity S, depends on T-100, T-093).

## Out of Scope

- Loitering Detection (M11: T-110–T-113 — note T-110 is already complete and out of *this* milestone regardless), Missing Object Detection (M12), License Plate Recognition (M13), Frontend Dashboard Integration (M14), Testing/Hardening (M15), Docker (M16).
- Re-running or modifying M9's own detection/classification/tracking logic in `YoloObjectDetector` beyond whatever minimal, explicitly-justified change the Required Pre-Implementation Output concludes is genuinely required to expose its bounding boxes to `ColorDetector` for the same frame (see Context) — do not re-detect objects (this template's own Constraint).
- User authentication, RBAC, multi-tenancy, cloud/object storage, message brokers, GPU cluster inference scaling, mobile applications, and alerting integrations beyond the in-app event feed — explicit non-goals in `docs/AI_PROJECT_CONTEXT.md` §7.

## Acceptance Criteria

Copied verbatim from `docs/IMPLEMENTATION_PLAN.md` §M10:

- "For a small manually-curated set of test crops with known colors, the detector's label matches expectation in a unit test."
- "Color labels appear alongside object detections in the live analytics console."

Copied verbatim from `docs/TASK_BACKLOG.md` Epic M10's Definition of Done column:

- T-100: "Unit test against curated known-color crops passes"
- T-101: "Visible next to each detection in the console"

## Constraints

From `prompts/10-color-detection.md`'s own Constraints:

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`) — this plugin implements `IDetectorPlugin` and depends on `Frame`/context only.
- No new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR.
- Must not duplicate M9's detection work — read bounding boxes from context, don't re-detect.

Standing rules from `AGENTS.md` that apply to this milestone's kind of work:

- Never let an analytics/detector module import ONVIF or RTSP-specific code directly — it must depend on `IFrameSource`/`Frame` only (§ Things AI Must Never Do); `color_detector.py` is an analytics module.
- Never add a new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry (§ Dependency Rules) — `opencv-python-headless` (HSV conversion, histograms, `cv2.kmeans`) and `numpy` are already dependencies (TD-04/TD-20/TD-25); a pure HSV-histogram or `cv2.kmeans`-based approach needs no new package. Only add one (e.g. `scikit-learn`) if the pre-implementation plan concludes it's genuinely necessary, with the TD entry justifying why the already-available `cv2`/`numpy` primitives don't suffice.
- Never read configuration via `os.environ` outside `backend/app/core/config.py` (§ Things AI Must Never Do) — applies if any new color-threshold `Settings` field is introduced.
- Never delete or weaken the source-independence regression test (T-086) to make this change pass (§ Things AI Must Never Do) — confirm it still passes unmodified.
- Verify the `context` mechanism actually fits `IDetectorPlugin`'s existing interface before writing code against it, per `docs/PROMPTING_GUIDE.md` §4's example written specifically for this task, and `AGENTS.md` § Rules for AI Coding Assistants — if it doesn't fit cleanly, stop and propose the smallest interface change, don't work around it with a hack.

## Deliverables

`docs/IMPLEMENTATION_PLAN.md` §M10's Files list names one file: `backend/app/infrastructure/analytics/color_detector.py`. Resolved against current repo structure and `docs/FOLDER_STRUCTURE.md`:

- `backend/app/infrastructure/analytics/color_detector.py` (new) — `ColorDetector` implementing `IDetectorPlugin` (`backend/app/application/ports/detector_plugin.py`): crops each detected bounding box out of `frame.image`, computes a dominant color (HSV histogram or `cv2.kmeans`, per T-100), and maps it to the existing `backend/app/domain/value_objects/color_label.py::ColorLabel` enum — reuse it, do not redefine color buckets elsewhere.
- The mechanism by which `ColorDetector` obtains M9's bounding boxes for the current frame is not fixed by any document read for this prompt (see Context's design gap) — state the chosen mechanism explicitly in the Required Pre-Implementation Output before writing this file, following `docs/PROMPTING_GUIDE.md` §4's instruction to confirm interface fit first.
- `backend/app/core/container.py` — add `ColorDetector` to the `AnalyticsOrchestrator`'s plugin list, following the existing `YoloObjectDetector` wiring precedent at `Container.__init__`. Not named in `docs/IMPLEMENTATION_PLAN.md` §M10's Files list, but unavoidable: `core/` is "the composition root — builds infra adapters, injects into use cases" (`docs/FOLDER_STRUCTURE.md`) and is the only place plugins are assembled into the orchestrator today.
- How a computed color label is attached to "relevant `DetectionEvent`s" (§M10 Deliverables text) is likewise not fixed upstream. Every existing plugin (`NoOpDetectorPlugin`, `YoloObjectDetector`) constructs and returns its own new `DetectionEvent` objects — none mutates an event another plugin returned, and `AnalyticsOrchestrator.process()` provides no channel for that (it only `.extend()`s each plugin's returned list). State explicitly in the pre-implementation plan whether `ColorDetector` follows that same established pattern (its own `DetectionEvent`, correlated to the source detection via `metadata`, e.g. `track_id`/`frame_sequence`, mirroring how `YoloObjectDetector` already keys its own metadata) — this is the constrained default given current code, not a free choice, but confirm it there before implementing.
- Frontend: §M10's Files list names no frontend file, but T-101's Definition of Done ("Visible next to each detection in the console") and §M10's Acceptance Criteria ("Color labels appear alongside object detections in the live analytics console") require a visible change. `frontend/src/features/analytics-console/DetectionOverlay.tsx` (M9's own Files list) is the only existing analytics-console component rendering per-detection data today — modify it, or add a sibling component under the same `frontend/src/features/analytics-console/` feature folder (`docs/FOLDER_STRUCTURE.md`'s `features/` convention) if the pre-implementation plan concludes the overlay itself shouldn't grow. State the exact choice in that plan.

## Testing Expectations

Per `AGENTS.md` § Testing Expectations and this template's own instruction: "a small curated set of test crops with known colors, asserting the detector's label matches expectation" — matching T-100's Definition of Done verbatim. `ColorDetector` needs no real camera/file I/O to test (crops are synthetic in-memory arrays, the same reasoning that already lets `backend/tests/integration/analytics/test_yolo_detector_integration.py` stub a fake Ultralytics-shaped model rather than requiring `@pytest.mark.hardware`) — follow that file's location/pattern precedent for where this test lives, and state the exact choice in the pre-implementation plan since no document fixes it exactly.

- Build a small set of synthetic bounding-box crops (numpy arrays) with known, unambiguous dominant colors (e.g. solid red, solid blue, solid black) and assert `ColorDetector`'s output label matches the expected `ColorLabel` member for each.
- Do not delete or weaken the T-086 source-independence regression test; confirm it still passes unmodified.
- Run the repository's configured formatter, linter, and type checker in addition to the test suite before considering the milestone done (`AGENTS.md` § Definition of Done).

## Documentation Update Requirements

- At the start, replace `TASKS.md`'s current `- [ ] _Nothing yet. Next up: Color Detection._` line under `# In Progress` with `- [ ] Color Detection (M10)` (moved from `# Remaining`, removing it from that list). Once T-100/T-101's acceptance criteria are met, move it to `# Completed` in the same PR, and restore the `# In Progress` section's placeholder line naming the next item (Loitering Detection, M11, per `TASKS.md`'s own ordering).
- If implementation reveals any planning document (`docs/TECHNICAL_DECISIONS.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/ARCHITECTURE.md`, `docs/FOLDER_STRUCTURE.md`) was wrong or incomplete — most likely `docs/ARCHITECTURE.md` §6.4 or `IDetectorPlugin`'s docstring, given the `context` design gap identified in Context above — update it in the same PR (`AGENTS.md` § Documentation Update Policy); never duplicate content into a new location, link to it instead.
- `README.md`: not expected to need an update — this milestone adds no new setup step and no new external dependency (per Constraints). Update it only if implementation reveals otherwise.
- Add a `docs/TECHNICAL_DECISIONS.md` entry (see Required Closing Report) for the real implementation-time decisions this milestone makes.

## Milestone Boundary

Implement ONLY this milestone. Do not implement work belonging to any other milestone, even if it seems convenient or clearly needed soon. If, during implementation, you discover that another milestone's work is genuinely required to complete this one, stop and explain why before writing that code — do not silently expand scope.

This applies concretely to `AnalyticsZone`/the zone editor/`LoiteringDetector` (M11), `MissingObjectDetector` (M12), and `LicensePlateRecognizer` (M13): do not build any part of them here. It applies equally to M8/M9's already-complete abstractions: build on `IDetectorPlugin`/`AnalyticsOrchestrator`/`RunAnalyticsPipelineUseCase`/`YoloObjectDetector` as they exist today; the only permitted change to `YoloObjectDetector` or `IDetectorPlugin`/`AnalyticsOrchestrator` is the minimal one the Required Pre-Implementation Output concludes is genuinely necessary to expose M9's bounding boxes to `ColorDetector` for the same frame — not a broader restructuring.

## Required Pre-Implementation Output

Before writing any code, produce:

- **Repo-state precondition check** — confirm, against the working tree at execution time, that `YoloObjectDetector`, `IDetectorPlugin`, `AnalyticsOrchestrator`, `ColorLabel`, and the single-shared-orchestrator wiring in `container.py` still exist as described in Context above, and that `context` is still unwritten-to by any plugin (TD-26's "no plugin writes to it yet").
- **Implementation Plan** — must resolve, explicitly:
  1. How `ColorDetector` obtains M9's `BoundingBox` results for the current frame, given `context` today carries no same-frame cross-plugin data (the Context section's design gap). Confirm this fits `IDetectorPlugin.process(frame, context)`'s existing signature before proceeding; if not, propose the smallest interface change (e.g. what `YoloObjectDetector` would need to additionally write into `context`, and its shape/key) and flag it for confirmation rather than working around it.
  2. The dominant-color algorithm (HSV histogram vs. `cv2.kmeans`, per T-100's "HSV-histogram" framing) and the concrete mapping from computed color to one of `ColorLabel`'s ten members (hue/saturation/value thresholds or bucket boundaries).
  3. Whether `ColorDetector` emits its own new `DetectionEvent`s (correlated to the source detection via `metadata`) or attaches to an existing one, and the correlation key used (see Deliverables).
  4. The exact frontend file touched to surface the color label per T-101.
- **Files to Create**
- **Files to Modify**
- **Risks** — address at least: the `context` design gap and whatever resolution decision 1 lands on; the single-shared-`AnalyticsOrchestrator`-across-sources scoping already noted as a pre-existing concern in TD-26 for any state introduced into `context`; and the accuracy limits of HSV-histogram/k-means dominant-color extraction on small or partially-occluded crops.
- **Assumptions** — state only assumptions confirmed by the consulted documentation and current code; the `context` cross-plugin mechanism, the event-attachment mechanism, and the exact frontend file are genuinely undefined upstream and must be treated as real decisions to make and document, not re-derived from a document that doesn't specify them.

This plan is produced first. Implementation proceeds only after it — and, if this is running interactively, only after the human reviewing it has had the chance to object, unless the human has explicitly asked for autonomous execution without a pause.

## Required Closing Report

On completion, produce:

- **Summary of Implementation**
- **Acceptance Criteria Satisfied** — check each item in the Acceptance Criteria section above.
- **Tradeoffs**
- **New Technical Decisions** — identify each one made (at minimum: how `ColorDetector` accesses M9's bounding boxes and any resulting interface change; the dominant-color algorithm and color-bucket mapping; how the label attaches to `DetectionEvent`s; the frontend surface touched) and confirm a corresponding `docs/TECHNICAL_DECISIONS.md` entry was added in the same PR (`AGENTS.md` § Dependency Rules and § Documentation Update Policy), not just mentioned in the PR description.
- **Suggested Commit Message** — `Add dominant-color detection for detected objects (T-100, T-101)`.
- **Suggested PR Title** — `M10: Color Detection`.
