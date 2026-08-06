# Implementation Prompt: License Plate Recognition / OCR (M13)

## Context

M13 adds License Plate Recognition (LPR/ALPR): localize the plate region in a frame, then OCR the crop — a detect-then-read pipeline (`docs/IMPLEMENTATION_PLAN.md` §M13; `docs/AI_PROJECT_CONTEXT.md` §6 glossary). It depends on M9's detection infrastructure patterns, though plate detection is a separate model from `YoloObjectDetector` (Milestone Dependency Graph: `M9 --> M13`). Per `TASKS.md`, M0–M12 are complete and M13 is next in the build order. This is explicitly the highest-uncertainty analytic in the set — `docs/PROMPTING_GUIDE.md` §4's worked "research/decision task" example is written specifically about M13's plate-localizer question, and this milestone's own template Background section directs a research-only pass on that question before implementing, if one hasn't already happened. This prompt folds that research question into the Required Pre-Implementation Output below (rather than a separate session) because a reviewable implementation plan cannot be produced without resolving it first.

## Documents Consulted

- `AGENTS.md` (full)
- `TASKS.md` (full)
- `docs/IMPLEMENTATION_PLAN.md` §M13 (License Plate Recognition (OCR)), plus the Milestone Dependency Graph
- `docs/TASK_BACKLOG.md` Epic M13 (T-130–T-134)
- `docs/TECHNICAL_DECISIONS.md` TD-06 (object detection — YOLOv8 + ByteTrack, alternatives considered), TD-07 (OCR engine — EasyOCR, alternatives considered), TD-20 (M2 — `sample.mp4` fixture is a synthetic clip with no real detectable objects, still-open action item), TD-24 (`IDetectorPlugin`/`DetectionEvent` event-shape convention), TD-25 (M9 — `asyncio.to_thread` execution strategy for a CPU-bound plugin, model-caching pattern, the `opencv-python`/`opencv-python-headless` dependency-conflict precedent), TD-27 (same-frame `context` handoff pattern between two named plugins)
- `docs/ARCHITECTURE.md` §5 (Unified Frame Source) and §6.4 (Analytics Pipeline flow, the `context` contract, and the one documented `YoloObjectDetector`/`ColorDetector` `context` exception)
- `docs/FOLDER_STRUCTURE.md` — Backend folder-by-folder (`domain/`, `application/`, `infrastructure/`, `interfaces/`, `backend/tests/`) and the Dependency Direction Rule
- `docs/PROMPTING_GUIDE.md` §4 (Example: Good Prompt, research/decision task — the T-130 worked example) and §5 (Recurring Traps to Name Explicitly)
- `docs/AI_PROJECT_CONTEXT.md` §6 (Glossary — LPR/ALPR), §7 (Non-Goals), §8 (Coding Standards), §9 (Project State)

## Scope

All five tasks in `docs/TASK_BACKLOG.md` Epic M13 — a single tightly-coupled cluster (the plugin cannot exist without both the localizer and the reader; T-133/T-134 are explicit Constraints/Testing Expectations of this same milestone's template, not separable follow-up work), matching the precedent M8–M12 set of bundling one epic per PR (`docs/TECHNICAL_DECISIONS.md` TD-24 through TD-29):

- **T-130** — Plate region localizer (YOLO or classical CV fallback).
- **T-131** — `EasyOcrReader` implementing `ILicensePlateReader`.
- **T-132** — `LicensePlateRecognizer` plugin composing localizer + OCR.
- **T-133** — Non-blocking OCR execution (async/queued).
- **T-134** — Accuracy note documented honestly.

### Out of Scope

- M14 (Frontend Dashboard Integration) — `docs/IMPLEMENTATION_PLAN.md` §M13's Files list names only backend files (`plate_localizer.py`, `easyocr_reader.py`, `license_plate_recognizer.py`); no frontend deliverable is named for M13, unlike M9/M10/M11. The existing analytics-console event feed becomes the display surface for `license_plate_recognition.*` events once M14 wires it in, the same way it already works for other event types.
- M15 (Testing, Hardening & Final Documentation Polish) and M16 (Docker) — explicitly later milestones.
- Replacing `backend/tests/fixtures/sample.mp4` for M9/M10/M11/M12's own still-open needs (`docs/TECHNICAL_DECISIONS.md` TD-20/TD-25's flagged action item covering objects in general). This PR only needs to add a plate-visible fixture for this milestone's own acceptance criteria (see Deliverables) — do not attempt to also fix the general synthetic-fixture limitation for object/color detection.
- Any change to `YoloObjectDetector`, `ColorDetector`, `LoiteringDetector`, or `MissingObjectDetector` beyond what's needed to wire `LicensePlateRecognizer` into the existing plugin list in `container.py`.
- WS-Discovery, ONVIF network discovery, or any camera-onboarding change — unrelated to this milestone.

## Acceptance Criteria

Copied verbatim from `docs/IMPLEMENTATION_PLAN.md` §M13:

- "Against an MP4 clip containing a clearly visible plate, recognized text matches the actual plate in at least a majority of sampled frames (document actual accuracy honestly — this is the highest-difficulty, highest-variance analytic in the set)."
- "Plugin never blocks the orchestrator loop for other plugins — OCR latency is isolated (documented approach: async/queued execution rather than inline per-frame blocking if inference time requires it)."

Copied verbatim from `docs/TASK_BACKLOG.md` Epic M13 (Definition of Done column):

- T-130: "Correctly boxes plate region on test clip in majority of sampled frames"
- T-131: "Given a clean plate crop, returns correct text in isolated test"
- T-132: "End-to-end event with plate text emitted from a live/MP4 run"
- T-133: "Orchestrator frame loop latency unaffected by OCR runtime (measured)"
- T-134: "TECHNICAL_DECISIONS.md or perf note states observed accuracy/limits"

## Constraints

From the M13 template itself:

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md` § "Dependency Direction Rule (Enforced, Not Just Documented)") — implement `ILicensePlateReader` (`backend/app/application/ports/license_plate_reader.py`, already exists from M1) and the `IDetectorPlugin` interface (`backend/app/application/ports/detector_plugin.py`, already exists from M8); no ONVIF/RTSP imports anywhere in this milestone's code.
- No new third-party dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry (what it replaces, why, tradeoffs) in the same PR — per `AGENTS.md` § Dependency Rules, especially if the plate-localizer approach changes from what TD-07 assumed. TD-07 already names both a YOLO-based and a classical-CV plate localizer as options; whichever is chosen, and EasyOCR's own actual `pyproject.toml` addition, needs a documented entry (see Documentation Update Requirements). Check for a TD-25-style dependency conflict (EasyOCR pulling in its own OpenCV/PyTorch requirement that could collide with `opencv-python-headless`) before assuming a clean install.
- OCR must not block the orchestrator's per-frame loop for other plugins (T-133) — document the isolation approach used (async/queued execution). TD-25 decision 2 already established `asyncio.to_thread` as this codebase's pattern for a CPU-bound, blocking inference call (`YoloObjectDetector.process()`); use the same pattern unless EasyOCR's actual measured latency genuinely requires a queued/background-task approach instead — if so, document why `to_thread` alone was insufficient.

Standing rules from `AGENTS.md` § Things AI Must Never Do that apply to this analytics-touching milestone (also named as recurring traps in `docs/PROMPTING_GUIDE.md` §5):

- Never let `LicensePlateRecognizer`, `EasyOcrReader`, `plate_localizer.py`, or any analytics code import ONVIF/RTSP-specific code — depends on `IFrameSource`/`Frame` only.
- Never have a use case call an infrastructure adapter directly instead of through a port.
- Never read configuration via `os.environ` outside `app/core/config.py` — any new confidence threshold, model path, or queue-size setting goes through the single `Settings` object.
- Never duplicate or rewrite existing content from `docs/` into a new file or location — link to it.
- Never implement work beyond this milestone's scope, or change documented architecture, without stopping to confirm first.
- Never delete or weaken the source-independence regression test (T-086) — it must keep passing unmodified.

## Deliverables

- `backend/app/infrastructure/analytics/plate_localizer.py` (T-130) — per `docs/IMPLEMENTATION_PLAN.md` §M13's Files list and `docs/FOLDER_STRUCTURE.md`'s `infrastructure/analytics/` section (which already lists `LicensePlateRecognizer` as composing "a plate localizer + `EasyOcrReader`"). Neither doc fixes whether this is a YOLO-based detector or a classical-CV (contour/edge) fallback — resolve this as the central research question in the Required Pre-Implementation Output below, per this milestone's Background section and the `docs/PROMPTING_GUIDE.md` §4 worked example written for exactly this task.
- `backend/app/infrastructure/analytics/easyocr_reader.py` (T-131) — `EasyOcrReader` implementing the existing `ILicensePlateReader` port (`backend/app/application/ports/license_plate_reader.py`) and returning the existing `PlateNumber` value object (`backend/app/domain/value_objects/plate_number.py`) — both already exist from M1 and are not to be recreated or have their signatures changed without stopping to confirm first; the port's `read(plate_crop) -> tuple[PlateNumber, float] | None` shape is the contract to implement against.
- `backend/app/infrastructure/analytics/license_plate_recognizer.py` (T-132) — `LicensePlateRecognizer` implementing the existing `IDetectorPlugin` port (`backend/app/application/ports/detector_plugin.py`), composing the localizer and `EasyOcrReader`, emitting `DetectionEvent`s with recognized plate text + confidence, following the `event_type` naming convention every existing plugin uses (`f"license_plate_recognition.{...}"`, mirroring `object_detection.*`/`color_detection.*`/`loitering_detection.*`/`missing_object_detection.*`, per `docs/TECHNICAL_DECISIONS.md` TD-24's settled convention).
- `backend/app/core/container.py` — wire `LicensePlateRecognizer` into `AnalyticsOrchestrator`'s existing plugin list (the composition root is the only module allowed to import across layers, per `docs/FOLDER_STRUCTURE.md`'s `core/` section); update the ordering comment there if `LicensePlateRecognizer` also needs same-frame `context` from `YoloObjectDetector`'s bounding boxes (`docs/ARCHITECTURE.md` §6.4's one documented exception) — decide during planning whether LPR needs this or runs its own independent plate localization over the full frame instead.
- `backend/pyproject.toml` — add EasyOCR (and, if the chosen localizer approach needs one, a plate-detection model dependency), with a corresponding `docs/TECHNICAL_DECISIONS.md` entry per Constraints above.
- A committed MP4 fixture (or documented equivalent) containing a clearly visible license plate — this milestone's own acceptance criteria require testing against one and none currently exists (`backend/tests/fixtures/sample.mp4` is a synthetic moving-circle clip with no real objects or plates, per `docs/TECHNICAL_DECISIONS.md` TD-20's still-open flag). Resolve how this is sourced (e.g. a generated synthetic clip rendering plate-like text, similar in spirit to `scripts/generate_sample_fixture.py`'s existing approach, or a documented alternative) as part of the Required Pre-Implementation Output; `docs/IMPLEMENTATION_PLAN.md`/`docs/TASK_BACKLOG.md` do not specify a mechanism, so this is a genuine implementation-time decision, not an invented requirement.
- Tests, per Testing Expectations below.

## Testing Expectations

Per `AGENTS.md` § Testing Expectations, expanded with this milestone's own required mechanism:

- Domain/Application layer additions (if any): unit tests with no real I/O, using fakes for every port.
- `EasyOcrReader` (T-131): an isolated test against a clean, cropped plate image confirms it returns the correct text — following the existing `tests/integration/analytics/test_<plugin>_integration.py` naming pattern (e.g. `backend/tests/integration/analytics/test_easyocr_reader_integration.py`), since it exercises the real EasyOCR model, matching how `test_color_detector_integration.py`/`test_yolo_detector_integration.py` already test real inference rather than faking it.
- Plate localizer (T-130): integration test confirming it correctly boxes the plate region on the plate-visible test clip (see Deliverables) in a majority of sampled frames — `backend/tests/integration/analytics/test_plate_localizer_integration.py`.
- `LicensePlateRecognizer` (T-132): end-to-end integration test against the same fixture, asserting a `DetectionEvent` with recognized plate text is emitted from a live/MP4 run — `backend/tests/integration/analytics/test_license_plate_recognizer_integration.py`.
- Non-blocking execution (T-133): a measured test confirming orchestrator frame-loop latency is unaffected by OCR runtime — the exact mechanism depends on the isolation approach chosen under Constraints (e.g. timing the orchestrator's per-frame call with and without `LicensePlateRecognizer` enabled, or asserting the call returns before OCR completes).
- Accuracy (T-134 / `docs/IMPLEMENTATION_PLAN.md` §M13 AC #1): sample multiple frames from the plate-visible fixture, compare recognized text to the actual plate, and record the observed match rate honestly, including if it's well under 100% — this is named as the highest-difficulty, highest-variance analytic in the set; an honestly-reported partial result satisfies this AC, an inflated one does not.
- The source-independence regression test (T-086) is permanent and must keep passing unmodified — do not delete or weaken it to make this milestone's tests pass.

## Documentation Update Requirements

- Update `TASKS.md`: move the line `- [ ] License Plate Recognition / OCR (M13)` from the Remaining section to the In Progress section (replacing the current placeholder line `- [ ] _Nothing yet. Next up: License Plate Recognition / OCR (M13)._`) at the start of implementation, then to the Completed section once all acceptance criteria above are met.
- Add a new `docs/TECHNICAL_DECISIONS.md` entry (TD-30, the next available number after TD-29) documenting: the plate-localizer approach chosen and why (extending TD-07's already-named alternatives, per this milestone's Constraints), the non-blocking execution mechanism chosen (T-133), the fixture-sourcing decision, and the honestly-observed accuracy result (T-134) — following the TD-18 through TD-29 pattern of one consolidated entry per milestone's real implementation-time decisions, not scattered across only the PR description.
- If implementation reveals another planning document (`docs/IMPLEMENTATION_PLAN.md`, `docs/TASK_BACKLOG.md`, `docs/FOLDER_STRUCTURE.md`, etc.) was wrong, update it in the same PR per `AGENTS.md` § Documentation Update Policy — do not defer it to a follow-up.

## Milestone Boundary

Implement ONLY this milestone. Do not implement work belonging to any other milestone, even if it seems convenient or clearly needed soon. If, during implementation, you discover that another milestone's work is genuinely required to complete this one, stop and explain why before writing that code — do not silently expand scope.

## Required Pre-Implementation Output

Before writing any code, produce:

- **Implementation Plan** — the approach, in enough detail to review, and must explicitly resolve, with reasoning: (1) the plate-localizer approach — per this milestone's Background section and the `docs/PROMPTING_GUIDE.md` §4 worked example, research whether a pretrained YOLO license-plate model is realistically available and usable within Ultralytics' standard loading path versus a classical-CV (contour/edge-based) fallback, before committing to one; (2) how the plate-visible test fixture will be sourced; (3) the non-blocking OCR execution mechanism (T-133); (4) whether `LicensePlateRecognizer` needs same-frame `context` from `YoloObjectDetector` (`docs/ARCHITECTURE.md` §6.4) or runs independently.
- **Files to Create**
- **Files to Modify**
- **Risks**
- **Assumptions**

This plan is produced first; implementation proceeds only after it, and — if running interactively — only after the human reviewing it has had the chance to object, unless the human has explicitly asked for autonomous execution without a pause.

## Required Closing Report

On completion, provide:

- **Summary of Implementation**
- **Acceptance Criteria Satisfied** — checked off against the seven items listed under Acceptance Criteria above (the two `docs/IMPLEMENTATION_PLAN.md` §M13 criteria and the five `docs/TASK_BACKLOG.md` T-130–T-134 Definition-of-Done rows).
- **Tradeoffs**
- **New Technical Decisions** — the TD-30 entry described in Documentation Update Requirements above, added in the same PR, not just mentioned in the PR description.
- **Suggested Commit Message** — imperative mood, referencing the relevant task ID(s) (`T-130` through `T-134` as applicable), per `AGENTS.md` § Commit Message Conventions.
- **Suggested PR Title**
