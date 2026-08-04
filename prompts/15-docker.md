# Template: Dockerization (M16, Stretch)

> Template — fill in the placeholders (`<...>`) before sending this to Claude Code. See [00-README.md](./00-README.md) for how this folder works.
>
> **Do not start this milestone while any earlier milestone is incomplete.** Per the assignment's own instruction, Docker is explicitly last and only "if time permits" — see `docs/IMPLEMENTATION_PLAN.md` §M16.

## Goal

Containerize backend + frontend for reproducible setup. Full detail: `docs/IMPLEMENTATION_PLAN.md` §M16.

## Background

Only attempted once M15 (testing/hardening/docs polish) is substantially complete.

## Documents to Read

- `docs/IMPLEMENTATION_PLAN.md` §M16.
- `docs/TASK_BACKLOG.md` — Epic M16 (Dockerization).
- `docs/AI_PROJECT_CONTEXT.md` §3 (Environment & Constraints — Docker not required initially).

## Scope

<Fill in: which task IDs from Epic M16 in `docs/TASK_BACKLOG.md` are in scope for this PR.>

**Out of scope**: <fill in — any remaining application feature work; this milestone should not become a vehicle for finishing something else.>

## Acceptance Criteria

<Paste verbatim from `docs/IMPLEMENTATION_PLAN.md` §M16 and the relevant `docs/TASK_BACKLOG.md` rows — do not paraphrase from memory.>

## Constraints

- No new application dependency introduced under cover of "just for Docker" — container tooling choices (base image, compose version) don't need a `docs/TECHNICAL_DECISIONS.md` entry the way an application dependency would, but note the choice in the PR description.
- Backend image must include FFmpeg.
- Document the LAN-camera access approach from within the container (network mode, or explicit port/device mapping) — this is a real gap if left unaddressed.

## Expected Deliverables

<Fill in — reference `docs/IMPLEMENTATION_PLAN.md` §M16 "Files" list rather than restating it.>

## Testing Expectations

Per `AGENTS.md` § Testing Expectations, plus: `docker compose up` brings up a working system reachable at documented ports; camera onboarding works from within the container against the LAN camera.

## Documentation Updates

- Update `README.md`'s "Getting Started" section with the real container-based setup commands, replacing the existing placeholders.
- Update `TASKS.md`: move "Docker (M16, stretch — time-permitting, explicitly last)" from Remaining → In Progress at the start, → Completed once acceptance criteria are met.

## Output Required From Claude

- A brief plan of the files to add before writing code.
- The implementation itself.
- Verification per Testing Expectations above.
- Any documentation updates identified above.
- A short summary: what was implemented and which acceptance criteria are satisfied.

## Suggested Commit Message

`<Imperative summary> (T-0xx[, T-0yy...])`

## Suggested PR Title

`M16: Dockerization`
