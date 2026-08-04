# Template: Project Foundation (M0, M1)

> Template — fill in the placeholders (`<...>`) before sending this to Claude Code. See [00-README.md](./00-README.md) for how this folder works.

## Goal

Stand up the empty-but-running FastAPI + React skeleton with quality tooling in place (M0), and the framework-free domain entities/value objects plus every application-layer port (M1) — so every later milestone adds features instead of fighting setup or missing abstractions. Full detail: `docs/IMPLEMENTATION_PLAN.md` §M0, §M1.

## Background

Every other milestone depends on this one — M0 for tooling and the composition root, M1 for the entities and ports every adapter and use case will implement against. Nothing in this milestone is camera- or analytics-specific.

## Documents to Read

- `docs/AI_PROJECT_CONTEXT.md` — read first if this is a fresh session.
- `docs/IMPLEMENTATION_PLAN.md` §M0, §M1 — goals, deliverables, acceptance criteria.
- `docs/TASK_BACKLOG.md` — Epic M0 (Scaffolding), Epic M1 (Domain & Application Core).
- `docs/FOLDER_STRUCTURE.md` — the full target layered layout this milestone establishes.
- `docs/TECHNICAL_DECISIONS.md` TD-01 (Clean Architecture with explicit ports), TD-08 (manual composition-root DI), TD-13 (config via `pydantic-settings`).

## Scope

<Fill in: which task IDs from Epic M0 and/or Epic M1 in `docs/TASK_BACKLOG.md` are in scope for this PR.>

**Out of scope**: <fill in — e.g. any concrete infrastructure adapter; those start at M2/M3.>

## Acceptance Criteria

<Paste verbatim from `docs/IMPLEMENTATION_PLAN.md` §M0 and §M1, and the relevant `docs/TASK_BACKLOG.md` rows — do not paraphrase from memory.>

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`) — `domain/` imports nothing from this project; `application/` imports `domain/` only.
- No new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR.
- Use cases in this milestone are signatures only (per `docs/IMPLEMENTATION_PLAN.md` M1 deliverables) — do not implement real logic that belongs to a later milestone.
- Do not create any concrete `infrastructure/` adapter yet.

## Expected Deliverables

<Fill in — reference `docs/IMPLEMENTATION_PLAN.md` §M0/§M1 "Files" lists rather than restating them.>

## Testing Expectations

Per `AGENTS.md` § Testing Expectations: domain/value-object validation rules need unit tests requiring no mocking; the import-linter (or equivalent) dependency-rule gate from M0 must actually fail on a deliberately introduced violation and pass after reverting it.

## Documentation Updates

- If this milestone's implementation reveals a planning document was wrong, update it in the same PR (`AGENTS.md` § Documentation Update Policy).
- Update `TASKS.md`: move "Backend & Frontend Foundation (M0)" and "Domain & Application Core (M1)" from Remaining → In Progress at the start, → Completed once acceptance criteria are met.

## Output Required From Claude

- A brief plan of the files to add before writing code.
- The implementation itself, following `AGENTS.md` coding standards.
- Tests per Testing Expectations above.
- Any documentation updates identified above.
- A short summary: what was implemented, which acceptance criteria are satisfied, and any deviations/tradeoffs (with a new `docs/TECHNICAL_DECISIONS.md` entry if a real decision was made).

## Suggested Commit Message

`<Imperative summary> (T-0xx[, T-0yy...])`

## Suggested PR Title

`M0/M1: Project Foundation`
