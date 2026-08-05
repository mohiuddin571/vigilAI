# Implementation Prompt: Missing Object Detection (M12)

## Context

M12 adds `MissingObjectDetector`, a detector plugin that flags when an object present in a baseline/reference view disappears from a defined zone for longer than a configurable threshold (`docs/AI_PROJECT_CONTEXT.md` §6 glossary). It depends on M9's YOLO detection/tracking output and reuses M11's `AnalyticsZone` for the region definition (`docs/IMPLEMENTATION_PLAN.md`'s Milestone Dependency Graph: `M9 --> M12`). Per `TASKS.md`, M0–M11 are complete and M12 is next in the build order — no other milestone work is a prerequisite beyond what M9/M11 already delivered.

## Documents Consulted

- `AGENTS.md` (full)
- `TASKS.md` (full)
- `docs/IMPLEMENTATION_PLAN.md` §M12 (Missing Object Detection), plus §M11 and the Milestone Dependency Graph for context
- `docs/TASK_BACKLOG.md` Epic M12 (T-120, T-121, T-122), plus Epic M11 rows (T-110–T-113) for precedent
- `docs/AI_PROJECT_CONTEXT.md` §6 (Glossary — Missing Object Detection), §7 (Non-Goals), §8 (Coding Standards), §9 (Project State)
- `docs/FOLDER_STRUCTURE.md` — Backend folder-by-folder (`domain/`, `application/`, `infrastructure/`, `interfaces/`, `backend/tests/`) and the Dependency Direction Rule
- `docs/TECHNICAL_DECISIONS.md` TD-24 (M8 — `IDetectorPlugin`, `DetectionEvent` event-shape convention), TD-26 (tracking/track-id surface), TD-27 (M10 — same-frame `context` handoff), TD-28 (M11 — zone persistence, containment algorithm, dwell state machine, event shape; its Future Enhancement note explicitly anticipates M12 reusing the containment primitive)
- `docs/PROMPTING_GUIDE.md` §5 (Recurring Traps to Name Explicitly)

## Scope

All three tasks in `docs/TASK_BACKLOG.md` Epic M12 — a single tightly-coupled cluster (baseline capture is a prerequisite for the detector; the occlusion guard is part of the same detector's logic), matching the precedent M11 set by covering T-111/T-112/T-113 in one PR (`docs/TECHNICAL_DECISIONS.md` TD-28):

- **T-120** — Baseline capture mechanism (reference frame/zone state).
- **T-121** — `MissingObjectDetector` plugin with absence timer.
- **T-122** — Occlusion false-positive guard.

### Out of Scope

- M13 (License Plate Recognition/OCR) and any plate-localization or OCR work.
- M14 (Frontend Dashboard Integration) beyond what M11 already built — no new frontend deliverable is named in `docs/IMPLEMENTATION_PLAN.md` §M12's Files list; the existing analytics-console event feed (built for M9/M10 events) is the display surface for `missing_object_detection.*` events, same as it already is for other event types.
- M15 (Testing/Hardening/Documentation Polish) and M16 (Docker) — explicitly later milestones.
- Any change to `LoiteringDetector`, `ZoneEditor.tsx`, or `AnalyticsZone`'s existing fields beyond an additive field if the baseline-storage design genuinely requires one (see Deliverables).
- WS-Discovery, ONVIF network discovery, or any camera-onboarding change — unrelated to this milestone.

## Acceptance Criteria

Copied verbatim from `docs/IMPLEMENTATION_PLAN.md` §M12:

- "Demonstrable against a prepared MP4 clip: object present at baseline capture, later removed from frame, event fires after the configured threshold and not before."
- "False-positive guard: brief occlusion (a person walking in front of the object for under the threshold) does not fire an event — verified with a crafted test clip or unit test using synthetic detection sequences."

Copied verbatim from `docs/TASK_BACKLOG.md` Epic M12 (Definition of Done column):

- T-120: "Baseline stored and retrievable"
- T-121: "Event fires only after threshold crossed on a prepared test clip"
- T-122: "Crafted test: brief occlusion under threshold produces no event"

## Constraints

From the M12 template itself:

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md` § "Dependency Direction Rule (Enforced, Not Just Documented)"): `domain/` imports nothing project-local; `application/` imports `domain/` only; `infrastructure/`/`interfaces/` import `application/` (and `domain/` for entities) and never each other directly.
- No new third-party dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry (what it replaces, why, tradeoffs) in the same PR — per `AGENTS.md` § Dependency Rules. Note the M11 precedent (TD-28): a pure-Python point-in-polygon/region check was written rather than adding `shapely`; prefer the same approach here unless a real, documented reason requires otherwise.
- Must guard against brief-occlusion false positives (T-122): a crafted test clip or synthetic detection-sequence unit test must confirm no event fires under the absence threshold.

Standing rules from `AGENTS.md` § Things AI Must Never Do that apply to this analytics-touching milestone (also named as recurring traps in `docs/PROMPTING_GUIDE.md` §5 — do not let any of these slip in while building a detector plugin):

- Never let `MissingObjectDetector` or any analytics code import ONVIF/RTSP-specific code — it depends on `IFrameSource`/`Frame` only.
- Never have a use case call an infrastructure adapter directly instead of through a port.
- Never read configuration via `os.environ` outside `app/core/config.py` — any new absence-threshold or baseline-related setting goes through the single `Settings` object (`pydantic-settings`).
- Never duplicate or rewrite existing content from `docs/` into a new file or location — link to it.
- Never implement work beyond this milestone's scope, or change documented architecture, without stopping to confirm first.
- Never delete or weaken the source-independence regression test (T-086) — it must keep passing unmodified.

## Deliverables

- `backend/app/infrastructure/analytics/missing_object_detector.py` — the `MissingObjectDetector` plugin, per `docs/IMPLEMENTATION_PLAN.md` §M12's Files list and `docs/FOLDER_STRUCTURE.md`'s `infrastructure/analytics/` section (which already lists `MissingObjectDetector` alongside `YoloObjectDetector`/`ColorDetector`/`LoiteringDetector` as a plugin implementing `IDetectorPlugin`).
- The baseline capture mechanism (T-120). Neither `docs/IMPLEMENTATION_PLAN.md` §M12 nor `docs/TASK_BACKLOG.md` fixes its exact storage shape (e.g., an additive field/table keyed off `AnalyticsZone`, a new port + repository mirroring `IAnalyticsZoneRepository`'s shape, or in-memory `context` state analogous to `LoiteringDetector`'s per-`(source_id, zone_id, track_id)` dwell state — TD-28 decision 5). This is a genuine implementation-time decision, same as every prior milestone's undocumented gaps (TD-18 through TD-28) — decide it, document it in a new `docs/TECHNICAL_DECISIONS.md` entry per the Required Closing Report below, and note that TD-28's own Future Enhancement section already anticipated M12 reusing the region-containment primitive `LoiteringDetector` established, so prefer reuse over reinventing it.
- Tests, per Testing Expectations below.

## Testing Expectations

Per `AGENTS.md` § Testing Expectations, expanded with this milestone's own required mechanism:

- Domain/Application layer additions (if the baseline-storage design introduces any): unit tests with no real I/O, using fakes for every port.
- Infrastructure: `MissingObjectDetector` gets integration test coverage against the committed local MP4 fixture (`backend/tests/fixtures/sample.mp4`, per `docs/FOLDER_STRUCTURE.md`), demonstrating AC #1 — event fires after the configured threshold once an object is genuinely removed, and not before. Note `docs/TECHNICAL_DECISIONS.md` TD-25's still-open flag that `sample.mp4` is a synthetic clip (a moving circle) without real COCO objects; if this limits a literal "object removed from frame" demonstration, use a synthetic detection-sequence unit test instead — AC #2 (T-122) explicitly permits "a crafted test clip **or** unit test using synthetic detection sequences," and the same allowance is reasonable for AC #1 if the fixture's limitation makes a real clip impractical. Document whichever approach is used.
- The occlusion false-positive guard (T-122) must be verified by a crafted test clip or synthetic detection-sequence unit test confirming a brief under-threshold occlusion produces no event.
- The source-independence regression test (T-086) is permanent and must keep passing unmodified — do not delete or weaken it to make this milestone's tests pass.

## Documentation Update Requirements

- Update `TASKS.md`: move the line `- [ ] Missing Object Detection (M12)` from the Remaining section to the In Progress section (replacing the current placeholder line `- [ ] _Nothing yet. Next up: Missing Object Detection (M12)._`) at the start of implementation, then to the Completed section once all acceptance criteria above are met.
- If implementation reveals a planning document (`docs/IMPLEMENTATION_PLAN.md`, `docs/TASK_BACKLOG.md`, `docs/FOLDER_STRUCTURE.md`, etc.) was wrong, update it in the same PR per `AGENTS.md` § Documentation Update Policy — do not defer it to a follow-up.

## Milestone Boundary

Implement ONLY this milestone. Do not implement work belonging to any other milestone, even if it seems convenient or clearly needed soon. If, during implementation, you discover that another milestone's work is genuinely required to complete this one, stop and explain why before writing that code — do not silently expand scope.

## Required Pre-Implementation Output

Before writing any code, produce:

- **Implementation Plan** — the approach, in enough detail to review, including how the baseline-capture mechanism (T-120) will be stored/retrieved and how it integrates with `MissingObjectDetector`'s per-frame absence timer.
- **Files to Create**
- **Files to Modify**
- **Risks**
- **Assumptions**

This plan is produced first; implementation proceeds only after it, and — if running interactively — only after the human reviewing it has had the chance to object, unless the human has explicitly asked for autonomous execution without a pause.

## Required Closing Report

On completion, provide:

- **Summary of Implementation**
- **Acceptance Criteria Satisfied** — checked off against the six items listed under Acceptance Criteria above (the two `docs/IMPLEMENTATION_PLAN.md` §M12 criteria and the three `docs/TASK_BACKLOG.md` T-120/T-121/T-122 Definition-of-Done rows).
- **Tradeoffs**
- **New Technical Decisions** — if the baseline-storage design (or any other real, undocumented-upstream choice) was made during implementation, add a corresponding `docs/TECHNICAL_DECISIONS.md` entry (decision, context, alternatives considered, tradeoffs, future enhancement) in the same PR, not just a mention in the PR description.
- **Suggested Commit Message** — imperative mood, referencing the relevant task ID(s) (`T-120`, `T-121`, `T-122` as applicable), per `AGENTS.md` § Commit Message Conventions.
- **Suggested PR Title**
