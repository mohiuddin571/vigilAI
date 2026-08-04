# Template: Recording (M6)

> Template — fill in the placeholders (`<...>`) before sending this to Claude Code. See [00-README.md](./00-README.md) for how this folder works.

## Goal

Record a camera's stream to disk as MP4 segments with metadata. Full detail: `docs/IMPLEMENTATION_PLAN.md` §M6.

## Background

Depends on M5's resolved RTSP source. Runs independently of the analytics decode path so enabling/disabling analytics never affects recording fidelity.

## Documents to Read

- `docs/IMPLEMENTATION_PLAN.md` §M6.
- `docs/TASK_BACKLOG.md` — Epic M6 (Recording).
- `docs/TECHNICAL_DECISIONS.md` TD-04 (FFmpeg subprocess, stream-copy recording).

## Scope

<Fill in: which task IDs from Epic M6 in `docs/TASK_BACKLOG.md` are in scope for this PR.>

**Out of scope**: <fill in — e.g. playback (M7), even though it consumes this milestone's output.>

## Acceptance Criteria

<Paste verbatim from `docs/IMPLEMENTATION_PLAN.md` §M6 and the relevant `docs/TASK_BACKLOG.md` rows — do not paraphrase from memory.>

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`).
- No new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR.
- Recording must use FFmpeg stream-copy (`-c copy`, no re-encode) per TD-04, reading directly from the RTSP source — not from decoded analytics frames.
- Must not interfere with, or be interfered by, the live-view MJPEG path running concurrently (verify both running at once).

## Expected Deliverables

<Fill in — reference `docs/IMPLEMENTATION_PLAN.md` §M6 "Files" list rather than restating it.>

## Testing Expectations

Per `AGENTS.md` § Testing Expectations. Specifically: produced segments must be valid, verifiable with `ffprobe`; recording metadata must be queryable immediately after stopping.

## Documentation Updates

- If this milestone's implementation reveals a planning document was wrong, update it in the same PR.
- Update `TASKS.md`: move "Recording (M6)" from Remaining → In Progress at the start, → Completed once acceptance criteria are met.

## Output Required From Claude

- A brief plan of the files to add/change before writing code.
- The implementation itself, following `AGENTS.md` coding standards.
- Tests per Testing Expectations above.
- Any documentation updates identified above.
- A short summary: what was implemented, which acceptance criteria are satisfied, and any deviations/tradeoffs (with a new `docs/TECHNICAL_DECISIONS.md` entry if a real decision was made).

## Suggested Commit Message

`<Imperative summary> (T-0xx[, T-0yy...])`

## Suggested PR Title

`M6: Recording`
