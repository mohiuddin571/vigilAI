# Template: Missing Object Detection (M12)

> Template — fill in the placeholders (`<...>`) before sending this to Claude Code. See [00-README.md](./00-README.md) for how this folder works.

## Goal

Flag when an object present in a baseline/reference view disappears for longer than a threshold. Full detail: `docs/IMPLEMENTATION_PLAN.md` §M12.

## Background

Depends on M9's detection and a defined zone (reuses M11's `AnalyticsZone`).

## Documents to Read

- `docs/IMPLEMENTATION_PLAN.md` §M12.
- `docs/TASK_BACKLOG.md` — Epic M12 (Missing Object Detection), especially T-122 (occlusion false-positive guard).
- `docs/AI_PROJECT_CONTEXT.md` §6 (Glossary — Missing Object Detection).

## Scope

<Fill in: which task IDs from Epic M12 in `docs/TASK_BACKLOG.md` are in scope for this PR.>

**Out of scope**: <fill in>

## Acceptance Criteria

<Paste verbatim from `docs/IMPLEMENTATION_PLAN.md` §M12 and the relevant `docs/TASK_BACKLOG.md` rows — do not paraphrase from memory.>

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`).
- No new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR.
- Must guard against brief-occlusion false positives (T-122) — a crafted test clip/synthetic sequence must confirm no event fires under the absence threshold.

## Expected Deliverables

<Fill in — reference `docs/IMPLEMENTATION_PLAN.md` §M12 "Files" list rather than restating it.>

## Testing Expectations

Per `AGENTS.md` § Testing Expectations. Specifically: a prepared clip demonstrating (a) event fires after threshold when object is genuinely removed, and (b) no event fires for a brief under-threshold occlusion.

## Documentation Updates

- If this milestone's implementation reveals a planning document was wrong, update it in the same PR.
- Update `TASKS.md`: move "Missing Object Detection (M12)" from Remaining → In Progress at the start, → Completed once acceptance criteria are met.

## Output Required From Claude

- A brief plan of the files to add/change before writing code.
- The implementation itself, following `AGENTS.md` coding standards.
- Tests per Testing Expectations above.
- Any documentation updates identified above.
- A short summary: what was implemented, which acceptance criteria are satisfied, and any deviations/tradeoffs (with a new `docs/TECHNICAL_DECISIONS.md` entry if a real decision was made).

## Suggested Commit Message

`<Imperative summary> (T-0xx[, T-0yy...])`

## Suggested PR Title

`M12: Missing Object Detection`
