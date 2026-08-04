# Implementation Prompt: Analytics Pipeline Foundation (M8)

## Context

The source template bundles two milestones — M2 (Frame Source Abstraction) and M8 (Analytics Pipeline Foundation) — because M8's orchestrator is built directly on M2's `IFrameSource` abstraction and is the mechanism that satisfies the assignment's non-negotiable requirement that analytics not be coupled to ONVIF (`docs/AI_PROJECT_CONTEXT.md` §2). **M2 is already complete** per `TASKS.md`'s Completed list, built early and ahead of M3–M7 exactly as `docs/IMPLEMENTATION_PLAN.md`'s "How to Read This Plan" section describes ("the analytics pipeline foundation... is built and demoed against local MP4 files before ONVIF work starts"). This generated prompt's actual scope is therefore **M8 only** — Epic M2's tasks (T-020–T-025) are prerequisite context this milestone builds on, not work to redo.

**Current repo state** (confirm against the working tree at execution time rather than trusting this paragraph — see Required Pre-Implementation Output): M0–M7 are complete. `backend/app/application/ports/frame_source.py::IFrameSource` yields `Frame` (finalized at M2); `Mp4FileFrameSource`, `ReconnectSupervisor`, and `StreamWorker`/`IStreamWorker` all exist and are exercised by M5's live-view and M6's recording paths. No `backend/app/infrastructure/analytics/`, `backend/app/infrastructure/messaging/`, or `backend/app/domain/events/` folder exists yet. `backend/app/application/use_cases/run_analytics_pipeline.py` is still the M1 stub (`NotImplementedError`), constructed against `IObjectDetector` (M1 port: `detect(frame: Any) -> list[DetectionEvent]` — never tightened from `Any` to `Frame` the way `IFrameSource` was at M2) and `IEventPublisher` (M1 port: `publish`/`subscribe`, unimplemented). No `IDetectorPlugin` port exists — `docs/ARCHITECTURE.md` §6.4 names it (`IDetectorPlugin.process(frame, context) -> list[DetectionEvent]`) as what every plugin implements and the orchestrator iterates, but no M1 port of that name was ever defined, and how it relates to the existing `IObjectDetector` is not resolved by any document (see Constraints).

## Documents Consulted

- `AGENTS.md` (full)
- `TASKS.md` (full; current state)
- `docs/ARCHITECTURE.md` §5 (The Core Abstraction: Unified Frame Source, full) and §6.4 (Analytics Pipeline flow, full)
- `docs/IMPLEMENTATION_PLAN.md` §M2 (dependency context, confirmed complete) and §M8, plus "How to Read This Plan" and the Milestone Dependency Graph (M8's explicit "does not depend on M3–M7")
- `docs/TASK_BACKLOG.md` Epic M2 (T-020–T-025, dependency context) and Epic M8 (T-080–T-086, especially T-086)
- `docs/TECHNICAL_DECISIONS.md` TD-05 (process-per-stream concurrency), TD-11 (in-process async pub-sub event bus, ports-first), TD-20 (M2's as-built port/process shape — `IStreamWorker`, `ReconnectSupervisor`/`StreamWorker` split — that this milestone must not disturb)
- `docs/FOLDER_STRUCTURE.md` (Backend folder ownership — `infrastructure/analytics/`, `infrastructure/messaging/`, `interfaces/api/analytics.py`, `persistence/` naming `SqlEventRepository` — and the "Dependency Direction Rule")
- `docs/PROMPTING_GUIDE.md` §5 (Recurring Traps to Name Explicitly, especially "Analytics importing ONVIF/RTSP directly" and "Treating MP4-source testing as optional")
- `prompts/00-README.md`, `prompts/07-video-source-abstraction.md` (full)
- `README.md` (status line: "...M6 (Recording), and M7 (Playback) complete. Next up: M8.")
- Current repo state: `backend/app/application/ports/{frame_source.py,object_detector.py,event_publisher.py}`, `backend/app/domain/entities/{frame.py,detection_event.py}`, `backend/app/application/use_cases/run_analytics_pipeline.py`, `backend/app/infrastructure/streaming/{stream_worker.py,reconnect_supervisor.py,mp4_frame_source.py}` (confirmed complete, unmodified by this milestone), `backend/app/application/use_cases/{start_live_stream.py,recording_session_registry.py}` (the established per-camera stateful-singleton pattern this milestone's analytics enable/disable state should follow), `backend/app/interfaces/websocket/stream_status.py` (whose own docstring names "M8's `IEventPublisher`" as the next real pub-sub mechanism), `backend/app/core/container.py`, `backend/app/main.py` — confirmed absence of `infrastructure/analytics/`, `infrastructure/messaging/`, `interfaces/api/analytics.py`, and any `IDetectorPlugin` port or detection-event repository/port.

## Scope

All of Epic M8 in `docs/TASK_BACKLOG.md` (all P0):

- T-080 — `IDetectorPlugin` interface.
- T-081 — `AnalyticsOrchestrator` (plugin iteration per frame).
- T-082 — In-process `EventBus` implementing `IEventPublisher`.
- T-083 — `DetectionEvent` persistence.
- T-084 — WebSocket analytics-events channel.
- T-085 — Analytics enable/disable API per source.
- T-086 — Source-independence regression test.

Epic M2 (T-020–T-025) is already complete — out of scope for this PR (see Out of Scope), included above only as the dependency this milestone builds on.

## Out of Scope

- Epic M2 (T-020–T-025) — already complete; build on `IFrameSource`/`Mp4FileFrameSource`/`IStreamWorker`/`ReconnectSupervisor` as they exist today, do not re-implement or modify without a stated, justified reason.
- Any real detector plugin (M9+) — M8 uses a no-op/passthrough plugin only, per `docs/IMPLEMENTATION_PLAN.md` §M8's own Deliverables text ("a trivial 'no-op'/passthrough plugin used purely to prove the orchestrator wiring end-to-end").
- Frontend analytics-console UI — `docs/IMPLEMENTATION_PLAN.md` §M8's Files list names backend files only; M8's acceptance criteria are satisfied via WebSocket delivery and a persisted, queryable event table, not a UI. `frontend/src/features/analytics-console/` (M9's `DetectionOverlay.tsx`, M11's `ZoneEditor.tsx`) is not this milestone's job.
- M9–M13 (individual analytics capabilities: YOLO, color, loitering, missing-object, LPR) and M14 (frontend dashboard integration).
- User authentication, RBAC, multi-tenancy, cloud/object storage, message brokers (Redis/Kafka — TD-11 already decides in-process for now), mobile applications, and alerting integrations — explicit non-goals in `docs/AI_PROJECT_CONTEXT.md` §7.

## Acceptance Criteria

Copied verbatim from `docs/IMPLEMENTATION_PLAN.md` §M8:

- Analytics can be toggled on for the MP4 demo source and events (even from the no-op plugin) appear over WebSocket and in the event table.
- The source-independence test from the deliverables passes and is kept permanently in the suite as a regression guard for the assignment's core architectural requirement.

Matching Definition of Done statements copied verbatim from `docs/TASK_BACKLOG.md` Epic M8:

- T-081: No-op plugin invoked once per frame, provably.
- T-082: Multiple subscribers all receive published events.
- T-083: Events queryable after publish.
- T-084: Browser client receives events in real time during a live/MP4 run.
- T-085: Toggling off stops new events without restarting the stream.
- T-086: Test asserts identical plugin-invocation behavior across sources; kept permanently as a regression guard — this is the assignment's core architectural claim made verifiable.

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`): the orchestrator and every detector plugin depend on `Frame`/`IFrameSource` only, never on `onvif-zeep-async`, `cv2.VideoCapture` internals, or RTSP specifics directly. This is also a standing rule, not specific to this PR — `AGENTS.md` § Engineering Principles and § Things AI Must Never Do state it explicitly: "Never let an analytics/detector module import ONVIF or RTSP-specific code directly."
- No new third-party dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR (`AGENTS.md` § Dependency Rules). None is expected for M8's own scope — TD-11 already decides an in-process asyncio event bus, and no ML/detection library is introduced before M9.
- **T-086 (source-independence regression test) must be added in this PR and is permanent** — `AGENTS.md` § Testing Expectations and § Things AI Must Never Do both state it must never be deleted or weakened by any later milestone to make an unrelated change pass.
- Reconnect/backoff remains source-agnostic and already exists (M2, TD-20: `ReconnectSupervisor`/`StreamWorker`) — this milestone consumes frames through that same supervised path (the way M5's live-view and M6's recording already do), and must not modify or bypass it for analytics-specific behavior.
- **Genuine design gap to resolve, not invent silently**: `IDetectorPlugin` (T-080) and the existing M1 `IObjectDetector` port are not reconciled by any document. Decide how they relate — for example, `IDetectorPlugin` supersedes `IObjectDetector` as the orchestrator-facing contract every plugin implements, with `IObjectDetector` retired or narrowed to an internal M9 (YOLO-specific) concern — and record the decision in `docs/TECHNICAL_DECISIONS.md` (see Documentation Update Requirements). Do not leave both existing with silently overlapping responsibility.
- **Genuine gap**: T-083 (`DetectionEvent` persistence) needs a repository, but no M1 port of that shape was ever named — only `docs/FOLDER_STRUCTURE.md`'s `persistence/` folder description names a concrete `SqlEventRepository` class with no abstract port to match. Add the additive port this needs, mirroring the precedent already established in this codebase (`docs/TECHNICAL_DECISIONS.md` TD-18–TD-22) for every prior milestone that hit an undocumented port gap, and document it the same way.

## Deliverables

Implement the M8 deliverables from `docs/IMPLEMENTATION_PLAN.md` §M8 at these paths:

- `backend/app/application/use_cases/run_analytics_pipeline.py` — replace the current `NotImplementedError` body. Its present constructor takes a single `object_detector: IObjectDetector`; resolve in the pre-implementation plan whether/how this changes to accept the plugin collection the orchestrator iterates, consistent with the `IDetectorPlugin`/`IObjectDetector` decision above.
- `backend/app/infrastructure/analytics/orchestrator.py` — `AnalyticsOrchestrator`, a plain iterator over enabled plugins per frame (`docs/ARCHITECTURE.md` §6.4), with no plugin-to-plugin coupling.
- `backend/app/infrastructure/messaging/event_bus.py` — in-process `EventBus` implementing `IEventPublisher` (TD-11).
- `backend/app/interfaces/websocket/analytics_events.py` — WebSocket channel pushing published events to subscribed browser clients.

Paths implied by the Deliverables text but not named in `docs/IMPLEMENTATION_PLAN.md` §M8's Files list — resolve the exact paths in the required pre-implementation plan, following the folder conventions `docs/FOLDER_STRUCTURE.md` already establishes:

- The new `IDetectorPlugin` port, under `backend/app/application/ports/`.
- The no-op/passthrough plugin proving orchestrator wiring end-to-end, under `backend/app/infrastructure/analytics/`.
- The `DetectionEvent` persistence port and its `SqlEventRepository` implementation (the class name `docs/FOLDER_STRUCTURE.md`'s `persistence/` section already specifies), under `backend/app/application/ports/` and `backend/app/infrastructure/persistence/` respectively.
- The analytics enable/disable API, at `backend/app/interfaces/api/analytics.py` — the file `docs/FOLDER_STRUCTURE.md`'s `interfaces/api/` list already names alongside `cameras.py`/`recordings.py`/`streams.py`.

Modify `backend/app/core/container.py` and `backend/app/main.py` for composition-root wiring. Do not create any frontend files (see Out of Scope).

## Testing Expectations

Per `AGENTS.md` § Testing Expectations, and the template's own instruction:

- **T-086 is the test that proves the assignment's core architectural requirement, not a nice-to-have**: run the same orchestrator and the same (no-op) plugin once against `Mp4FileFrameSource` (the committed `backend/tests/fixtures/sample.mp4`) and once against a fake `IFrameSource` double, asserting identical plugin-invocation behavior. It must be added in this PR and live permanently in the suite.
- Domain/Application layers (`RunAnalyticsPipelineUseCase`): unit tests with no real I/O, using fakes for `IFrameSource`, `IDetectorPlugin`, and `IEventPublisher`.
- `EventBus` (T-082): unit test asserting multiple subscribers all receive a published event.
- `DetectionEvent` persistence (T-083): integration test asserting an event is queryable immediately after being published.
- WebSocket analytics-events channel (T-084): a test connecting during a live/MP4 run and asserting events arrive in real time, following the same pattern established for the existing `stream_status.py` WebSocket channel.
- Analytics enable/disable (T-085): test that disabling analytics for a camera/source stops new events without stopping or restarting the underlying stream.
- Do not weaken or delete the M2 fake-flaky-`IFrameSource` reconnect/backoff unit test — unaffected by this milestone, but permanent per `AGENTS.md`.
- Run the repository's configured formatter, linter, type checker, and test suite before considering the milestone done.

## Documentation Update Requirements

- At the start, replace the current `TASKS.md` placeholder line `- [ ] _Nothing yet. Next up: Analytics Pipeline Foundation (M8)._` under `# In Progress` with `- [ ] Analytics Pipeline Foundation — orchestrator, source-independence regression test (M8)` (moved from `# Remaining`, removing it from that list). Once every acceptance criterion is met, move it to `# Completed` in the same PR, and restore the `# In Progress` section's placeholder line naming the next milestone (YOLO Integration, M9).
- Update `README.md`'s status line (currently "...M6 (Recording), and M7 (Playback) complete. Next up: M8.") to reflect M8's completion and M9 as next.
- Add a `docs/TECHNICAL_DECISIONS.md` entry documenting the `IDetectorPlugin`/`IObjectDetector` relationship decision and the new `DetectionEvent` persistence port, following the TD-18–TD-22 precedent of documenting implementation-time decisions the planning docs didn't fix precisely enough to derive without a real choice.
- If implementation reveals any other planning document was wrong or incomplete (e.g. `docs/ARCHITECTURE.md` §6.4's plugin interface naming, once the `IDetectorPlugin`/`IObjectDetector` decision is made), update it in the same PR per `AGENTS.md` § Documentation Update Policy. Do not duplicate documentation into a new file — link to it.

## Milestone Boundary

Implement ONLY this milestone. Do not implement work belonging to any other milestone, even if it seems convenient or clearly needed soon. If, during implementation, you discover that another milestone's work is genuinely required to complete this one, stop and explain why before writing that code — do not silently expand scope.

This applies concretely to M2's already-complete abstractions: build on `IFrameSource`/`Mp4FileFrameSource`/`IStreamWorker`/`ReconnectSupervisor` as they exist today; do not modify M2's internals to suit M8's convenience without first confirming the change here. It applies equally to M9: implementing a real detector plugin (YOLO or otherwise) beyond the no-op/passthrough plugin this milestone requires is out of scope, however tempting it may be once the orchestrator exists.

## Required Pre-Implementation Output

Before writing any code, produce:

- **M1/M2-precondition check** — confirm, against the working tree at execution time, that `IFrameSource`/`Mp4FileFrameSource`/`IStreamWorker`/`ReconnectSupervisor` (M2) and `DetectionEvent`/`IObjectDetector`/`IEventPublisher` (M1) still exist as described in Context above. Expected: yes — but this is a live check against the actual working tree, not an assumption carried over from this prompt.
- **Implementation Plan** — describe: the resolved relationship between `IDetectorPlugin` and `IObjectDetector` and its consequences for `RunAnalyticsPipelineUseCase`'s constructor; the orchestrator's per-frame plugin-iteration and cross-frame `context` design (`docs/ARCHITECTURE.md` §6.4); the new `DetectionEvent` persistence port's shape; how analytics enable/disable state per camera/source is held (the established per-camera stateful-singleton pattern `StartLiveStreamUseCase`/`RecordingSessionRegistry` already set is a reasonable model to follow, but confirm rather than assume); and T-086's exact test design and file location.
- **Files to Create** — list every concrete path, including tests and the new ports.
- **Files to Modify** — list every concrete path, including `backend/app/core/container.py`, `backend/app/main.py`, `TASKS.md`, and `README.md`.
- **Risks** — address: reconciling `IDetectorPlugin`/`IObjectDetector` without leaving orphaned or contradictory port definitions; WebSocket multi-client fan-out design (an analogous problem to TD-21's MJPEG multi-viewer fan-out, worth checking for a reusable pattern); and T-086 test reliability given `Mp4FileFrameSource`/`StreamWorker`'s process-isolated machinery.
- **Assumptions** — state only assumptions confirmed by the consulted documentation and current code. M2's `IFrameSource`/`Mp4FileFrameSource`/`IStreamWorker` shape is fixed and should be treated as given; the `IDetectorPlugin`/`IObjectDetector` relationship and the `DetectionEvent` persistence port shape are genuinely undefined upstream and must be treated as real decisions to make and document, not re-derived from a document that doesn't specify them.

This plan is produced first. Implementation proceeds only after it — and, if this is running interactively, only after the human reviewing it has had the chance to object, unless the human has explicitly asked for autonomous execution without a pause.

## Required Closing Report

On completion, produce:

- **Summary of Implementation**
- **Acceptance Criteria Satisfied** — check each exact item in the Acceptance Criteria section above.
- **Tradeoffs**
- **New Technical Decisions** — identify each one (the `IDetectorPlugin`/`IObjectDetector` relationship and the `DetectionEvent` persistence port, at minimum) and confirm its corresponding `docs/TECHNICAL_DECISIONS.md` entry was added in the same PR.
- **Suggested Commit Message** — `Implement analytics pipeline orchestrator and source-independence regression test (T-080, T-081, T-082, T-083, T-084, T-085, T-086)`.
- **Suggested PR Title** — `M8: Analytics Pipeline Foundation`.
