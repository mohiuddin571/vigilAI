# VigilAI — Prompting Guide for Claude Code

> Companion documents: [AI_PROJECT_CONTEXT.md](./AI_PROJECT_CONTEXT.md) · [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) · [TASK_BACKLOG.md](./TASK_BACKLOG.md)

This guide is for whoever (human or AI) is about to write the next Claude Code prompt for this project. Good prompts here produce code that respects the architecture without babysitting; bad prompts produce working-but-wrong code that quietly violates the layering this whole documentation set exists to protect.

---

## 1. The One Rule

**Every implementation prompt should point at a specific backlog ID or milestone, not a vague feature name.** "Implement ONVIF onboarding" is worse than "Implement T-033 (`OnboardCameraUseCase`) per TASK_BACKLOG.md, milestone M3 in IMPLEMENTATION_PLAN.md." The backlog and plan already encode scope, dependencies, and Definition of Done — repeating that context in prose invites drift between the docs and what actually gets built.

---

## 2. Session Startup Ritual

At the start of any session doing real implementation work, the prompt (or the first message) should establish:

1. **Read `AI_PROJECT_CONTEXT.md` first.** It's the anchor; everything else is detail.
2. **State which milestone/task is in scope**, by ID.
3. **State what already exists** — don't make Claude Code re-discover the codebase state from scratch if you already know it (e.g. "M0–M2 are done; you're starting M3").

If you don't know what already exists, ask Claude Code to check (`git log`, read `AI_PROJECT_CONTEXT.md` §9 "Project State") *before* proposing changes, rather than assuming.

---

## 3. Anatomy of a Good Implementation Prompt

A well-formed prompt for this project has four parts:

1. **Scope** — the specific task ID(s)/milestone, and explicitly what's *out* of scope for this prompt (prevents scope creep into the next milestone).
2. **Architectural constraints that apply** — cite the specific port(s)/layer(s) involved, referencing ARCHITECTURE.md/FOLDER_STRUCTURE.md sections by name.
3. **Acceptance criteria** — copy them from TASK_BACKLOG.md/IMPLEMENTATION_PLAN.md rather than re-deriving new ones ad hoc.
4. **What NOT to do** — call out the specific coupling or shortcut that's tempting but wrong for this task (see §5 for the recurring ones).

---

## 4. Examples

### Example: Good Prompt (feature work)

> Implement T-021 and T-022 from TASK_BACKLOG.md (Epic M2 — Frame Source Abstraction).
>
> Scope: `Mp4FileFrameSource` implementing the `IFrameSource` port defined in `application/ports/`, plus a committed sample MP4 fixture under `backend/tests/fixtures/`. Use OpenCV `VideoCapture`. Support looping and FPS-throttling per ARCHITECTURE.md §5.
>
> Out of scope: the Stream Worker process/queue (that's T-023, separate task) — for this task, a synchronous generator/async iterator satisfying `IFrameSource` is enough.
>
> Constraint: this file lives in `infrastructure/streaming/` and must only depend on `domain/` (for the `Frame` type) and `application/ports/` (to implement `IFrameSource`) — it must not import anything from `interfaces/`.
>
> Acceptance criteria: per TASK_BACKLOG.md T-021 — yields frames from the fixture at the expected throttled rate; per T-022 — fixture is committed and referenced by an integration test.
>
> Don't: don't add ONVIF or RTSP handling here — this task is deliberately camera-independent so it can be built and tested before any camera integration exists.

**Why this works**: it's traceable to a backlog ID, states the port being implemented, states the layer boundary explicitly, and preempts the most likely scope-creep mistake (reaching for RTSP/ONVIF code that doesn't belong here yet).

### Example: Bad Prompt (feature work)

> Add video file support to the analytics system.

**Why this fails**: no scope boundary (does "analytics system" mean the orchestrator too? the UI?), no port/layer named (Claude Code has to guess where files go and may put decode logic inside the orchestrator instead of behind `IFrameSource`, defeating the entire architecture), no acceptance criteria to check against, no guardrail against scope creep into adjacent milestones.

### Example: Good Prompt (architecture-sensitive refactor)

> The `YoloObjectDetector` plugin (T-091) currently works. Before starting T-100 (Color Detection), review whether `ColorDetector` can be implemented as a second, independent `IDetectorPlugin` that receives the same `Frame` and the *previous* plugin's `BoundingBox` results via the orchestrator's per-frame `context`, per ARCHITECTURE.md §6.4 — rather than color detection re-running its own object detection. Confirm this fits `IDetectorPlugin`'s existing interface before writing code; if it doesn't fit cleanly, stop and propose the smallest interface change needed, don't work around it with a hack.

**Why this works**: it asks Claude Code to verify architectural fit *before* writing code, and explicitly permits raising an interface change rather than silently working around a bad fit — which is exactly the judgment call that produces either clean or messy plugin systems.

### Example: Good Prompt (research/decision task)

> We need a plate-region localizer for T-130. Research whether a pretrained YOLO license-plate model is realistically available and usable within Ultralytics' standard loading path, versus a classical-CV (contour/edge-based) fallback. Don't implement yet — report back: which approach, expected accuracy tradeoffs, and whether it changes any TECHNICAL_DECISIONS.md entry (it would extend TD-06/TD-07). I'll confirm before you implement.

**Why this works**: research and implementation are separated. This matters more here than in most projects, because LPR (M13) is explicitly the highest-uncertainty analytic — committing to an implementation before confirming feasibility risks a wasted milestone.

---

## 5. Recurring Traps to Name Explicitly

These are the specific ways a well-intentioned prompt can produce architecture-violating code for *this* project. Naming them in a prompt when relevant saves a review cycle:

- **Analytics importing ONVIF/RTSP directly.** Any detector plugin or the orchestrator reaching for `onvif_zeep_async` or an RTSP URL string is an automatic architecture violation — it should only ever see `Frame` objects from `IFrameSource`. Call this out explicitly whenever prompting analytics work.
- **Use cases calling infrastructure directly instead of through ports.** Easy mistake when an adapter and a use case are built in the same session — the use case should only ever hold a port-typed constructor argument.
- **Config values read via `os.environ` outside `core/config.py`.** Any adapter reading env vars directly instead of receiving config through its constructor breaks the single-source-of-config guarantee in TD-13.
- **Skipping the reconnect/backoff supervisor for a "just this once" direct connection.** Every `IFrameSource` should go through the Stream Worker's supervised lifecycle (T-023/T-024) — a prompt that says "just connect directly for now, we'll add reconnect later" tends to produce two divergent connection-handling code paths that never get unified.
- **Building UI against `application/dto` instead of `interfaces/schemas`.** The API-facing Pydantic schemas are a distinct layer from use-case DTOs on purpose (TD-01/FOLDER_STRUCTURE.md); collapsing them couples the wire format to internal orchestration shape.
- **Treating MP4-source testing as optional.** Given M8's explicit acceptance criterion (T-086, the source-independence regression test), any analytics prompt that only tests against the physical camera is incomplete by this project's own definition of done.

---

## 6. Prompting for Non-Implementation Work

Not every prompt should produce code:

- **"Research only, report back, don't implement"** — use for anything with real technical uncertainty (LPR approach, ONVIF library quirks against the actual evaluator camera, FFmpeg flag choices). Forcing a report-first step here is cheaper than reviewing and unwinding a wrong implementation.
- **"Update TECHNICAL_DECISIONS.md with a new entry, don't change code yet"** — use when a decision made earlier turns out to be wrong mid-implementation. The fix belongs in the decision log, then the code, in that order, so the paper trail stays honest.
- **"Just fix the bug, minimal diff, no refactor"** — use for anything in TASK_BACKLOG.md's cross-cutting/hardening section (T-200+); these are explicitly not the place for opportunistic redesign.

---

## 7. Keeping the Docs and the Code Honest

When implementation reveals that a doc was wrong (a milestone's scope was off, a technology choice didn't pan out, a folder needs to move), the prompt for that work should say so explicitly: *"update FOLDER_STRUCTURE.md/TECHNICAL_DECISIONS.md/IMPLEMENTATION_PLAN.md to reflect this before/alongside the code change."* Treat the documentation set as a living contract, not a one-time artifact — a future session (or the evaluator) reading these docs should be able to trust that they describe the system as it actually is, not as it was planned to be on day one.
