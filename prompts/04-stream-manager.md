# Template: Live Stream Manager + Auto-Reconnect (M5)

> Template — fill in the placeholders (`<...>`) before sending this to Claude Code. See [00-README.md](./00-README.md) for how this folder works.

## Goal

View a camera's live stream in the browser, with automatic recovery from disconnects. Full detail: `docs/IMPLEMENTATION_PLAN.md` §M5.

## Background

Depends on M2's shared FFmpeg/OpenCV decode path (`OnvifRtspFrameSource`/`RawRtspFrameSource` reuse it) and M3/M4's `GetStreamUri` resolution.

## Documents to Read

- `docs/IMPLEMENTATION_PLAN.md` §M5.
- `docs/TASK_BACKLOG.md` — Epic M5 (Live Streaming + Reconnect).
- `docs/ARCHITECTURE.md` §6.2 (Live Streaming + Auto-Reconnect sequence diagram).
- `docs/TECHNICAL_DECISIONS.md` TD-05 (process-per-stream concurrency), TD-10 (MJPEG + WebSocket transport, alternatives considered).

## Scope

<Fill in: which task IDs from Epic M5 in `docs/TASK_BACKLOG.md` are in scope for this PR.>

**Out of scope**: <fill in — e.g. recording (M6), even though it will reuse this milestone's resolved stream.>

## Acceptance Criteria

<Paste verbatim from `docs/IMPLEMENTATION_PLAN.md` §M5 and the relevant `docs/TASK_BACKLOG.md` rows — do not paraphrase from memory.>

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`).
- No new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR.
- Reconnect/backoff must go through the same supervised Stream Worker lifecycle built in M2 — no bespoke "just connect directly for now, add reconnect later" path (`docs/PROMPTING_GUIDE.md` §5 names this trap explicitly).
- Live view must remain unaffected by analytics being enabled/disabled once M8+ exists.

## Expected Deliverables

<Fill in — reference `docs/IMPLEMENTATION_PLAN.md` §M5 "Files" list rather than restating it.>

## Testing Expectations

Per `AGENTS.md` § Testing Expectations. Specifically: a real-world or simulated disconnect (network interruption / RTSP source killed) must trigger automatic reconnection without manual intervention, observable in logs and reflected in the UI's connection-status indicator.

## Documentation Updates

- If this milestone's implementation reveals a planning document was wrong, update it in the same PR.
- Update `TASKS.md`: move "RTSP Stream Manager / Browser Live Streaming (M5)" and "Automatic Reconnection (M5)" from Remaining → In Progress at the start, → Completed once acceptance criteria are met.

## Output Required From Claude

- A brief plan of the files to add/change before writing code.
- The implementation itself, following `AGENTS.md` coding standards.
- Tests per Testing Expectations above.
- Any documentation updates identified above.
- A short summary: what was implemented, which acceptance criteria are satisfied, and any deviations/tradeoffs (with a new `docs/TECHNICAL_DECISIONS.md` entry if a real decision was made).

## Suggested Commit Message

`<Imperative summary> (T-0xx[, T-0yy...])`

## Suggested PR Title

`M5: Live Streaming + Auto-Reconnect`
