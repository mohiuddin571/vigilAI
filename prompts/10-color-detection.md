# Template: Color Detection (M10)

> Template — fill in the placeholders (`<...>`) before sending this to Claude Code. See [00-README.md](./00-README.md) for how this folder works.

## Goal

Extract a dominant color label for each detected object. Full detail: `docs/IMPLEMENTATION_PLAN.md` §M10.

## Background

Consumes M9's bounding boxes via the orchestrator's per-frame context — does not re-run object detection itself.

## Documents to Read

- `docs/IMPLEMENTATION_PLAN.md` §M10.
- `docs/TASK_BACKLOG.md` — Epic M10 (Color Detection).
- `docs/ARCHITECTURE.md` §6.4 (how plugins share per-frame context without coupling to each other).

## Scope

<Fill in: which task IDs from Epic M10 in `docs/TASK_BACKLOG.md` are in scope for this PR.>

**Out of scope**: <fill in>

## Acceptance Criteria

<Paste verbatim from `docs/IMPLEMENTATION_PLAN.md` §M10 and the relevant `docs/TASK_BACKLOG.md` rows — do not paraphrase from memory.>

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`) — this plugin implements `IDetectorPlugin` and depends on `Frame`/context only.
- No new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR.
- Must not duplicate M9's detection work — read bounding boxes from context, don't re-detect.

## Expected Deliverables

<Fill in — reference `docs/IMPLEMENTATION_PLAN.md` §M10 "Files" list rather than restating it.>

## Testing Expectations

Per `AGENTS.md` § Testing Expectations. Specifically: a small curated set of test crops with known colors, asserting the detector's label matches expectation.

## Documentation Updates

- If this milestone's implementation reveals a planning document was wrong, update it in the same PR.
- Update `TASKS.md`: move "Color Detection (M10)" from Remaining → In Progress at the start, → Completed once acceptance criteria are met.

## Output Required From Claude

- A brief plan of the files to add/change before writing code.
- The implementation itself, following `AGENTS.md` coding standards.
- Tests per Testing Expectations above.
- Any documentation updates identified above.
- A short summary: what was implemented, which acceptance criteria are satisfied, and any deviations/tradeoffs (with a new `docs/TECHNICAL_DECISIONS.md` entry if a real decision was made).

## Suggested Commit Message

`<Imperative summary> (T-0xx[, T-0yy...])`

## Suggested PR Title

`M10: Color Detection`
