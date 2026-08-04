# Template: ONVIF Camera Onboarding (M3)

> Template — fill in the placeholders (`<...>`) before sending this to Claude Code. See [00-README.md](./00-README.md) for how this folder works.
>
> **Naming note**: this file is named per the required `prompts/` file list. The actual milestone scope, per `docs/TECHNICAL_DECISIONS.md` TD-03, is **IP + credential onboarding** — WS-Discovery-based network scanning is an explicit future enhancement, not part of M3. Don't let the filename imply broader scope than the docs commit to.

## Goal

Authenticate to an ONVIF camera using IP + username + password and read its identity/media-profile information. Full detail: `docs/IMPLEMENTATION_PLAN.md` §M3.

## Background

First milestone touching real hardware/infrastructure. Independent of M2 (frame source abstraction) — ONVIF here is a configuration/control-plane concern only, never a pixel-decoding one (`docs/ARCHITECTURE.md` §5).

## Documents to Read

- `docs/IMPLEMENTATION_PLAN.md` §M3.
- `docs/TASK_BACKLOG.md` — Epic M3 (ONVIF Onboarding).
- `docs/TECHNICAL_DECISIONS.md` TD-03 (ONVIF client library choice, alternatives considered), TD-15 (credential handling).
- `docs/ARCHITECTURE.md` §6.1 (Camera Onboarding & Configuration sequence diagram).

## Scope

<Fill in: which task IDs from Epic M3 in `docs/TASK_BACKLOG.md` are in scope for this PR.>

**Out of scope**: <fill in — e.g. encoder config read/update (M4), WS-Discovery network scanning (future enhancement, not this milestone).>

## Acceptance Criteria

<Paste verbatim from `docs/IMPLEMENTATION_PLAN.md` §M3 and the relevant `docs/TASK_BACKLOG.md` rows — do not paraphrase from memory.>

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`) — the `OnboardCameraUseCase` depends on `ICameraGateway` only, never on `onvif-zeep-async` directly.
- No new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR.
- Camera passwords must never be logged or returned in an API response after creation (TD-15).
- Invalid credentials / unreachable host must produce a typed exception → clear `4xx`, never a raw SOAP fault or stack trace leaking to the client.

## Expected Deliverables

<Fill in — reference `docs/IMPLEMENTATION_PLAN.md` §M3 "Files" list rather than restating it.>

## Testing Expectations

Per `AGENTS.md` § Testing Expectations: integration tests against a mock SOAP server or recorded ONVIF fixtures by default (so CI doesn't require the physical camera); anything requiring the real evaluator-provided camera is marked (e.g. `@pytest.mark.hardware`) and skipped in CI.

## Documentation Updates

- If this milestone's implementation reveals a planning document was wrong (e.g. the evaluator's camera has quirks not anticipated in TD-03), update it in the same PR.
- Update `TASKS.md`: move "ONVIF Camera Onboarding — IP + credential authentication (M3)" from Remaining → In Progress at the start, → Completed once acceptance criteria are met.

## Output Required From Claude

- A brief plan of the files to add/change before writing code.
- The implementation itself, following `AGENTS.md` coding standards.
- Tests per Testing Expectations above.
- Any documentation updates identified above.
- A short summary: what was implemented, which acceptance criteria are satisfied, and any deviations/tradeoffs (with a new `docs/TECHNICAL_DECISIONS.md` entry if a real decision was made).

## Suggested Commit Message

`<Imperative summary> (T-0xx[, T-0yy...])`

## Suggested PR Title

`M3: ONVIF Camera Onboarding`
