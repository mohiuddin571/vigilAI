# Template: Object Tracking (introduced for M9, consumed by M11)

> Template — fill in the placeholders (`<...>`) before sending this to Claude Code. See [00-README.md](./00-README.md) for how this folder works.

## Goal

Enable persistent per-object track IDs (ByteTrack, bundled with Ultralytics) so downstream plugins — loitering detection, specifically — can reason about dwell time per object rather than per-frame detections in isolation. Full detail: `docs/IMPLEMENTATION_PLAN.md` §M11 (tracking is introduced as part of this milestone in the plan).

## Background

Ultralytics ships ByteTrack; this is a mode change on the existing YOLO call from `08-yolo-integration.md`, not a second detection system (`docs/TECHNICAL_DECISIONS.md` TD-06).

## Documents to Read

- `docs/IMPLEMENTATION_PLAN.md` §M11 (opening deliverable: "Enable YOLO tracking").
- `docs/TASK_BACKLOG.md` — T-110 (Epic M11).
- `docs/TECHNICAL_DECISIONS.md` TD-06.

## Scope

<Fill in: confirm this is being done as the first deliverable of M11, or standalone ahead of the rest of loitering detection — state which.>

**Out of scope**: <fill in — the loitering dwell-timer/zone logic itself belongs in `11-loitering-detection.md`.>

## Acceptance Criteria

<Paste verbatim from `docs/IMPLEMENTATION_PLAN.md` §M11 and task T-110 in `docs/TASK_BACKLOG.md` — do not paraphrase from memory.>

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`).
- No new dependency — ByteTrack ships inside `ultralytics` already; do not add a separate tracking library (TD-06 explicitly rejected DeepSORT for this reason).
- Track IDs must be stable for a given object across consecutive frames in a test clip — this is the acceptance bar, verify with a test, not a visual spot-check alone.

## Expected Deliverables

<Fill in — small, focused change to the M9 detector plugin/orchestrator context to carry track IDs forward.>

## Testing Expectations

Per `AGENTS.md` § Testing Expectations. Specifically: a test clip where the same object retains one ID across consecutive frames.

## Documentation Updates

- If this milestone's implementation reveals a planning document was wrong, update it in the same PR.
- Update `TASKS.md`: move "Object Tracking (ByteTrack, used by M9/M11)" from Remaining → In Progress at the start, → Completed once acceptance criteria are met.

## Output Required From Claude

- A brief plan of the files to add/change before writing code.
- The implementation itself, following `AGENTS.md` coding standards.
- Tests per Testing Expectations above.
- Any documentation updates identified above.
- A short summary: what was implemented, which acceptance criteria are satisfied, and any deviations/tradeoffs (with a new `docs/TECHNICAL_DECISIONS.md` entry if a real decision was made).

## Suggested Commit Message

`<Imperative summary> (T-110)`

## Suggested PR Title

`Object Tracking (ByteTrack)`
