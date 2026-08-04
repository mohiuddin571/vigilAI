# Template: Playback (M7)

> Template — fill in the placeholders (`<...>`) before sending this to Claude Code. See [00-README.md](./00-README.md) for how this folder works.

## Goal

Browse and play back recorded footage from the frontend, with working seek. Full detail: `docs/IMPLEMENTATION_PLAN.md` §M7.

## Background

Depends on M6's recording index and stored segments.

## Documents to Read

- `docs/IMPLEMENTATION_PLAN.md` §M7.
- `docs/TASK_BACKLOG.md` — Epic M7 (Playback).

## Scope

<Fill in: which task IDs from Epic M7 in `docs/TASK_BACKLOG.md` are in scope for this PR.>

**Out of scope**: <fill in>

## Acceptance Criteria

<Paste verbatim from `docs/IMPLEMENTATION_PLAN.md` §M7 and the relevant `docs/TASK_BACKLOG.md` rows — do not paraphrase from memory.>

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`).
- No new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR.
- Playback endpoint must serve via HTTP range requests so the browser's native `<video>` seek works without a custom protocol.

## Expected Deliverables

<Fill in — reference `docs/IMPLEMENTATION_PLAN.md` §M7 "Files" list rather than restating it.>

## Testing Expectations

Per `AGENTS.md` § Testing Expectations. Specifically: a partial-content (`206`) range request must be verified, not just a full-file `GET`.

## Documentation Updates

- If this milestone's implementation reveals a planning document was wrong, update it in the same PR.
- Update `TASKS.md`: move "Playback (M7)" from Remaining → In Progress at the start, → Completed once acceptance criteria are met.

## Output Required From Claude

- A brief plan of the files to add/change before writing code.
- The implementation itself, following `AGENTS.md` coding standards.
- Tests per Testing Expectations above.
- Any documentation updates identified above.
- A short summary: what was implemented, which acceptance criteria are satisfied, and any deviations/tradeoffs (with a new `docs/TECHNICAL_DECISIONS.md` entry if a real decision was made).

## Suggested Commit Message

`<Imperative summary> (T-0xx[, T-0yy...])`

## Suggested PR Title

`M7: Playback`
