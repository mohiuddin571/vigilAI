# Template: Frontend Dashboard Integration (M14)

> Template — fill in the placeholders (`<...>`) before sending this to Claude Code. See [00-README.md](./00-README.md) for how this folder works.

## Goal

Tie every backend capability built so far (M3–M13) into one coherent, navigable UI. Full detail: `docs/IMPLEMENTATION_PLAN.md` §M14.

## Background

Depends on M3 through M13 all being functional at the API level — this milestone is integration, not new backend capability.

## Documents to Read

- `docs/IMPLEMENTATION_PLAN.md` §M14.
- `docs/TASK_BACKLOG.md` — Epic M14 (Frontend Dashboard Integration).
- `docs/FOLDER_STRUCTURE.md` — "Frontend — Folder by Folder" section.
- `docs/TECHNICAL_DECISIONS.md` TD-12 (React Query + Zustand + Tailwind).

## Scope

<Fill in: which task IDs from Epic M14 in `docs/TASK_BACKLOG.md` are in scope for this PR — this milestone may reasonably span more than one PR; say which slice this one covers.>

**Out of scope**: <fill in>

## Acceptance Criteria

<Paste verbatim from `docs/IMPLEMENTATION_PLAN.md` §M14 and the relevant `docs/TASK_BACKLOG.md` rows — do not paraphrase from memory.>

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`) — `frontend/src/features/` folders must not import each other directly; shared logic goes through `components/`/`hooks/`/`services/`.
- No new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR.
- Server state goes through React Query hooks; local UI state through Zustand — don't hand-roll a third pattern (TD-12).

## Expected Deliverables

<Fill in — reference `docs/IMPLEMENTATION_PLAN.md` §M14 "Files" list rather than restating it.>

## Testing Expectations

Per `AGENTS.md` § Testing Expectations, plus a manual walkthrough per acceptance criteria: onboard → live view → configure → record → play back → enable analytics → define zone → see live events, all through the UI without touching the API directly.

## Documentation Updates

- If this milestone's implementation reveals a planning document was wrong, update it in the same PR.
- Update `TASKS.md`: move "Frontend Integration — unified dashboard (M14)" from Remaining → In Progress at the start, → Completed once acceptance criteria are met.

## Output Required From Claude

- A brief plan of the files to add/change before writing code.
- The implementation itself, following `AGENTS.md` coding standards.
- Tests per Testing Expectations above.
- Any documentation updates identified above.
- A short summary: what was implemented, which acceptance criteria are satisfied, and any deviations/tradeoffs (with a new `docs/TECHNICAL_DECISIONS.md` entry if a real decision was made).

## Suggested Commit Message

`<Imperative summary> (T-0xx[, T-0yy...])`

## Suggested PR Title

`M14: Frontend Dashboard Integration`
