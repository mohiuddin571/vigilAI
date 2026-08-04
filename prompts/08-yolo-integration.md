# Template: YOLO Integration — Object Detection & Classification (M9)

> Template — fill in the placeholders (`<...>`) before sending this to Claude Code. See [00-README.md](./00-README.md) for how this folder works.

## Goal

Real object detection and classification via Ultralytics YOLO, wired in as a detector plugin on the M8 orchestrator. Full detail: `docs/IMPLEMENTATION_PLAN.md` §M9.

## Background

First real detector plugin — proves the M8 orchestrator with actual inference instead of the no-op plugin. Detection and classification come from one YOLO inference call, not two separate systems.

## Documents to Read

- `docs/IMPLEMENTATION_PLAN.md` §M9.
- `docs/TASK_BACKLOG.md` — Epic M9 (Object Detection & Classification).
- `docs/TECHNICAL_DECISIONS.md` TD-06 (Ultralytics YOLOv8 + ByteTrack, alternatives considered).
- `prompts/07-video-source-abstraction.md` — the plugin interface this milestone implements against.

## Scope

<Fill in: which task IDs from Epic M9 in `docs/TASK_BACKLOG.md` are in scope for this PR.>

**Out of scope**: <fill in — e.g. persistent tracking (see `09-object-tracking.md`), color detection (M10).>

## Acceptance Criteria

<Paste verbatim from `docs/IMPLEMENTATION_PLAN.md` §M9 and the relevant `docs/TASK_BACKLOG.md` rows — do not paraphrase from memory.>

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`) — this plugin implements `IDetectorPlugin` and depends on `Frame` only; no ONVIF/RTSP imports (`docs/PROMPTING_GUIDE.md` §5).
- No new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR.
- Model weights are cached under `storage/models/`, not committed to the repo.

## Expected Deliverables

<Fill in — reference `docs/IMPLEMENTATION_PLAN.md` §M9 "Files" list rather than restating it.>

## Testing Expectations

Per `AGENTS.md` § Testing Expectations. Specifically: results spot-checked against the MP4 demo fixture for correctness; achieved FPS on the Mac Mini documented honestly, not hidden.

## Documentation Updates

- If this milestone's implementation reveals a planning document was wrong, update it in the same PR.
- Update `TASKS.md`: move "YOLO Integration — Object Detection & Classification (M9)" from Remaining → In Progress at the start, → Completed once acceptance criteria are met.

## Output Required From Claude

- A brief plan of the files to add/change before writing code.
- The implementation itself, following `AGENTS.md` coding standards.
- Tests per Testing Expectations above.
- Any documentation updates identified above.
- A short summary: what was implemented, which acceptance criteria are satisfied, and any deviations/tradeoffs (with a new `docs/TECHNICAL_DECISIONS.md` entry if a real decision was made).

## Suggested Commit Message

`<Imperative summary> (T-0xx[, T-0yy...])`

## Suggested PR Title

`M9: YOLO Object Detection & Classification`
