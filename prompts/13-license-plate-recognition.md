# Template: License Plate Recognition / OCR (M13)

> Template — fill in the placeholders (`<...>`) before sending this to Claude Code. See [00-README.md](./00-README.md) for how this folder works.

## Goal

Detect and read license plates: localize the plate region, then OCR it. Full detail: `docs/IMPLEMENTATION_PLAN.md` §M13.

## Background

Highest-uncertainty analytic in the set — per `docs/PROMPTING_GUIDE.md` §4 ("Good Prompt: research/decision task"), consider a research-only pass on the plate-localizer approach before implementing, if that hasn't already happened.

## Documents to Read

- `docs/IMPLEMENTATION_PLAN.md` §M13.
- `docs/TASK_BACKLOG.md` — Epic M13 (License Plate Recognition), especially T-133 (non-blocking OCR) and T-134 (honest accuracy note).
- `docs/TECHNICAL_DECISIONS.md` TD-07 (EasyOCR, alternatives considered).

## Scope

<Fill in: which task IDs from Epic M13 in `docs/TASK_BACKLOG.md` are in scope for this PR.>

**Out of scope**: <fill in>

## Acceptance Criteria

<Paste verbatim from `docs/IMPLEMENTATION_PLAN.md` §M13 and the relevant `docs/TASK_BACKLOG.md` rows — do not paraphrase from memory.>

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`) — implement `ILicensePlateReader`/the plugin interface; no ONVIF/RTSP imports.
- No new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR (especially if the plate localizer approach changes from what TD-07 assumed).
- OCR must not block the orchestrator's per-frame loop for other plugins (T-133) — document the isolation approach used (async/queued execution).

## Expected Deliverables

<Fill in — reference `docs/IMPLEMENTATION_PLAN.md` §M13 "Files" list rather than restating it.>

## Testing Expectations

Per `AGENTS.md` § Testing Expectations. Specifically: recognized text checked against an MP4 clip with a clearly visible plate; observed accuracy documented honestly (T-134), not overstated.

## Documentation Updates

- If this milestone's implementation reveals a planning document was wrong (e.g. the localizer approach deviates from TD-07's assumption), update `docs/TECHNICAL_DECISIONS.md` in the same PR.
- Update `TASKS.md`: move "License Plate Recognition / OCR (M13)" from Remaining → In Progress at the start, → Completed once acceptance criteria are met.

## Output Required From Claude

- A brief plan of the files to add/change before writing code.
- The implementation itself, following `AGENTS.md` coding standards.
- Tests per Testing Expectations above.
- Any documentation updates identified above.
- A short summary: what was implemented, which acceptance criteria are satisfied, and any deviations/tradeoffs (with a new `docs/TECHNICAL_DECISIONS.md` entry if a real decision was made).

## Suggested Commit Message

`<Imperative summary> (T-0xx[, T-0yy...])`

## Suggested PR Title

`M13: License Plate Recognition (OCR)`
