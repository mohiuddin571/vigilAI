# Template: ONVIF Camera Configuration (M4)

> Template — fill in the placeholders (`<...>`) before sending this to Claude Code. See [00-README.md](./00-README.md) for how this folder works.

## Goal

Read and, where the camera supports it, update resolution/FPS/bitrate/codec via ONVIF. Full detail: `docs/IMPLEMENTATION_PLAN.md` §M4.

## Background

Depends on M3's camera gateway and the media profile data it discovered.

## Documents to Read

- `docs/IMPLEMENTATION_PLAN.md` §M4.
- `docs/TASK_BACKLOG.md` — Epic M4 (ONVIF Config Read/Update).
- `docs/AI_PROJECT_CONTEXT.md` §6 (Glossary — Codec, Bitrate, ONVIF Media Profile).

## Scope

<Fill in: which task IDs from Epic M4 in `docs/TASK_BACKLOG.md` are in scope for this PR.>

**Out of scope**: <fill in — e.g. live streaming (M5) even though it also touches `GetStreamUri`.>

## Acceptance Criteria

<Paste verbatim from `docs/IMPLEMENTATION_PLAN.md` §M4 and the relevant `docs/TASK_BACKLOG.md` rows — do not paraphrase from memory.>

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`).
- No new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR.
- Only expose fields the camera's own ONVIF profile reports as configurable — never assume a field is writable; an unsupported field/value must return a typed `4xx`, not be silently ignored.

## Expected Deliverables

<Fill in — reference `docs/IMPLEMENTATION_PLAN.md` §M4 "Files" list rather than restating it.>

## Testing Expectations

Per `AGENTS.md` § Testing Expectations. Specifically: a test asserting `PATCH` of a supported field is reflected on the next `GET`, and a test asserting `PATCH` of an unsupported field/value fails cleanly.

## Documentation Updates

- If this milestone's implementation reveals a planning document was wrong, update it in the same PR.
- Update `TASKS.md`: move "Camera Configuration — read/update resolution, FPS, bitrate, codec (M4)" from Remaining → In Progress at the start, → Completed once acceptance criteria are met.

## Output Required From Claude

- A brief plan of the files to add/change before writing code.
- The implementation itself, following `AGENTS.md` coding standards.
- Tests per Testing Expectations above.
- Any documentation updates identified above.
- A short summary: what was implemented, which acceptance criteria are satisfied, and any deviations/tradeoffs (with a new `docs/TECHNICAL_DECISIONS.md` entry if a real decision was made).

## Suggested Commit Message

`<Imperative summary> (T-0xx[, T-0yy...])`

## Suggested PR Title

`M4: ONVIF Camera Configuration`
