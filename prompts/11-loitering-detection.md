# Template: Loitering Detection (M11)

> Template — fill in the placeholders (`<...>`) before sending this to Claude Code. See [00-README.md](./00-README.md) for how this folder works.

## Goal

Flag objects/people that remain in a defined zone beyond a configurable duration. Full detail: `docs/IMPLEMENTATION_PLAN.md` §M11.

## Background

Depends on persistent track IDs (see `09-object-tracking.md`) and a configurable `AnalyticsZone`.

## Documents to Read

- `docs/IMPLEMENTATION_PLAN.md` §M11.
- `docs/TASK_BACKLOG.md` — Epic M11 (Loitering Detection), especially T-113 (de-dup requirement).
- `docs/AI_PROJECT_CONTEXT.md` §6 (Glossary — Loitering Detection).

## Scope

<Fill in: which task IDs from Epic M11 in `docs/TASK_BACKLOG.md` are in scope for this PR.>

**Out of scope**: <fill in>

## Acceptance Criteria

<Paste verbatim from `docs/IMPLEMENTATION_PLAN.md` §M11 and the relevant `docs/TASK_BACKLOG.md` rows — do not paraphrase from memory.>

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`).
- No new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR.
- Must emit **one event per qualifying dwell period, not once per frame** — this is an explicit acceptance criterion (T-113), not an implementation detail to skip.
- Zone and threshold must be configurable without a code change.

## Expected Deliverables

<Fill in — reference `docs/IMPLEMENTATION_PLAN.md` §M11 "Files" list rather than restating it.>

## Testing Expectations

Per `AGENTS.md` § Testing Expectations. Specifically: a test (against the MP4 fixture or synthetic track data) with a low threshold confirming exactly one event fires per qualifying dwell period.

## Documentation Updates

- If this milestone's implementation reveals a planning document was wrong, update it in the same PR.
- Update `TASKS.md`: move "Loitering Detection (M11)" from Remaining → In Progress at the start, → Completed once acceptance criteria are met.

## Output Required From Claude

- A brief plan of the files to add/change before writing code.
- The implementation itself, following `AGENTS.md` coding standards.
- Tests per Testing Expectations above.
- Any documentation updates identified above.
- A short summary: what was implemented, which acceptance criteria are satisfied, and any deviations/tradeoffs (with a new `docs/TECHNICAL_DECISIONS.md` entry if a real decision was made).

## Suggested Commit Message

`<Imperative summary> (T-0xx[, T-0yy...])`

## Suggested PR Title

`M11: Loitering Detection`
