# Template: Video Source Abstraction + Analytics Pipeline Foundation (M2, M8)

> Template — fill in the placeholders (`<...>`) before sending this to Claude Code. See [00-README.md](./00-README.md) for how this folder works.
>
> **This is the architectural centerpiece of the project.** M2 proves the `IFrameSource` abstraction against local MP4 files; M8 builds the analytics orchestrator on top of it and adds the permanent regression test that proves analytics is source-agnostic. Per `docs/IMPLEMENTATION_PLAN.md`'s ordering, M2 is built early — before M3/M4/M5 depend on its shared decode path — despite this file's position in the `prompts/` list.

## Goal

M2: yield a uniform `Frame` object from local MP4 files via `IFrameSource`, with a process-isolated Stream Worker and supervised reconnect/backoff. M8: build the `AnalyticsOrchestrator` and event infrastructure on top of `IFrameSource`, and add the source-independence regression test (T-086). Full detail: `docs/IMPLEMENTATION_PLAN.md` §M2, §M8.

## Background

This is the mechanism satisfying the assignment's non-negotiable requirement that analytics not be coupled to ONVIF (`docs/AI_PROJECT_CONTEXT.md` §2). Every detector milestone (`08`–`13`) depends on M8's orchestrator existing and being provably source-agnostic first.

## Documents to Read

- `docs/ARCHITECTURE.md` §5 (The Core Abstraction: Unified Frame Source) and §6.4 (Analytics Pipeline flow) — read these in full, not just skimmed.
- `docs/IMPLEMENTATION_PLAN.md` §M2, §M8.
- `docs/TASK_BACKLOG.md` — Epic M2 (Frame Source Abstraction), Epic M8 (Analytics Pipeline Foundation), especially **T-086**.
- `docs/TECHNICAL_DECISIONS.md` TD-05 (process-per-stream concurrency), TD-11 (in-process event bus).

## Scope

<Fill in: which task IDs from Epic M2 and Epic M8 in `docs/TASK_BACKLOG.md` are in scope for this PR.>

**Out of scope**: <fill in — e.g. any real detector plugin (M9+); M8 uses a no-op/passthrough plugin only, per the plan.>

## Acceptance Criteria

<Paste verbatim from `docs/IMPLEMENTATION_PLAN.md` §M2, §M8 and the relevant `docs/TASK_BACKLOG.md` rows — do not paraphrase from memory.>

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`) — the orchestrator and every detector plugin depend on `Frame`/`IFrameSource` only, never on `onvif-zeep-async`, `cv2.VideoCapture` internals, or RTSP specifics directly.
- No new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR.
- **T-086 (source-independence regression test) must be added in this PR and is permanent** — it must never be deleted or weakened by any later milestone to make an unrelated change pass.
- Reconnect/backoff logic must be source-agnostic (the same supervisor wraps MP4 looping and, later, camera reconnection).

## Expected Deliverables

<Fill in — reference `docs/IMPLEMENTATION_PLAN.md` §M2/§M8 "Files" lists rather than restating them.>

## Testing Expectations

Per `AGENTS.md` § Testing Expectations. Specifically: the source-independence test asserts identical plugin-invocation behavior between `Mp4FileFrameSource` and a fake `IFrameSource` double — this is the test that proves the assignment's core architectural requirement, not just a nice-to-have.

## Documentation Updates

- If this milestone's implementation reveals a planning document was wrong, update it in the same PR.
- Update `TASKS.md`: move "Video Source Abstraction — MP4 file source (M2)" and "Analytics Pipeline Foundation — orchestrator, source-independence regression test (M8)" from Remaining → In Progress at the start, → Completed once acceptance criteria are met.

## Output Required From Claude

- A brief plan of the files to add/change before writing code.
- The implementation itself, following `AGENTS.md` coding standards.
- Tests per Testing Expectations above, including T-086.
- Any documentation updates identified above.
- A short summary: what was implemented, which acceptance criteria are satisfied, and any deviations/tradeoffs (with a new `docs/TECHNICAL_DECISIONS.md` entry if a real decision was made).

## Suggested Commit Message

`<Imperative summary> (T-0xx[, T-0yy...])`

## Suggested PR Title

`M2/M8: Video Source Abstraction & Analytics Pipeline Foundation`
