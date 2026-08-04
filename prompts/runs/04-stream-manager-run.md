# Implementation Prompt: Live Stream Manager + Auto-Reconnect (M5)

## Context

M5 delivers browser-viewable live video for an already-onboarded ONVIF camera, with automatic recovery from network/RTSP disconnects — the first milestone where a camera's video, not just its metadata, reaches the frontend. It follows M3/M4 (ONVIF onboarding and `GetVideoEncoderConfiguration`) and M2 (Frame Source Abstraction), all complete per `TASKS.md`. Its Stream Worker/reconnect path is what M6 (Recording) will reuse rather than reimplement.

**M2 precondition now satisfied** (this prompt was originally generated before M2 existed; that gap is resolved). `backend/app/infrastructure/streaming/` now contains `mp4_frame_source.py` (`Mp4FileFrameSource`), `reconnect_supervisor.py` (`ReconnectSupervisor` — the source-agnostic open→consume→backoff→retry loop, T-024), and `stream_worker.py` (`StreamWorker`, process-isolated per TD-05, T-023). `backend/app/domain/entities/frame.py` finalizes `Frame` (source_id, sequence, timestamp, image, metadata); `backend/app/application/ports/frame_source.py` is tightened to yield `Frame` (no longer `Any`) and now declares a `source_id` property. A new port, `backend/app/application/ports/stream_worker.py::IStreamWorker` (`start`/`stop`/`frames()`/`health()`), is what M5 depends on instead of the concrete `StreamWorker` class — this is "the M2 Stream Worker abstraction" referenced throughout this prompt. Full rationale for these shapes, including why reconnect logic and process isolation are two separate classes, is in `docs/TECHNICAL_DECISIONS.md` TD-20 — read it before designing `StartLiveStreamUseCase`'s dependencies. Still confirm this against the working tree at execution time (Required Pre-Implementation Output, below) rather than trusting this paragraph blindly — it describes the state as of M2's PR (#10) merging to `main`.

## Documents Consulted

- `AGENTS.md` (full)
- `TASKS.md` (full; current state)
- `docs/IMPLEMENTATION_PLAN.md` §M2 (dependency context), §M5, and "Milestone Dependency Graph"
- `docs/TASK_BACKLOG.md` Epic M2 (T-020–T-025, dependency context) and Epic M5 (T-050–T-055)
- `docs/ARCHITECTURE.md` §5 (Unified Frame Source, including `IStreamWorker`) and §6.2 (Live Streaming + Auto-Reconnect sequence diagram)
- `docs/TECHNICAL_DECISIONS.md` TD-05 (process-per-stream concurrency), TD-10 (MJPEG + WebSocket transport, alternatives considered), TD-20 (M2's port shape, the `ReconnectSupervisor`/`StreamWorker` split, and its noted open items — synthetic fixture, daemon-cleanup risk)
- `docs/FOLDER_STRUCTURE.md` (Backend folder ownership, "Dependency Direction Rule", now naming `IStreamWorker`/`DebugStreamUseCase`/`Frame`/`StreamHealth`)
- `docs/PROMPTING_GUIDE.md` §5 (Recurring Traps to Name Explicitly)
- `prompts/00-README.md` (full)
- `prompts/04-stream-manager.md` (full)
- `README.md` (Step 6, the M2 debug-stream demo; FFmpeg install note now reads "not needed yet, only from M5 onward")
- Current repo state relevant to this milestone: `backend/app/application/ports/frame_source.py` (tightened to `Frame`, now declares `source_id`), `backend/app/application/ports/stream_worker.py` (`IStreamWorker`, new in M2), `backend/app/infrastructure/streaming/**` (`Mp4FileFrameSource`, `ReconnectSupervisor`, `StreamWorker` — all exist now), `backend/app/application/use_cases/start_live_stream.py` (still the M1 stub — `NotImplementedError` body, unchanged by M2), `backend/app/application/ports/camera_gateway.py`, `backend/app/core/container.py`, `backend/app/main.py`, `backend/app/interfaces/api/{cameras.py,stream_debug.py}` — confirmed absence of `backend/app/interfaces/websocket/`, `backend/app/interfaces/api/streams.py`, and `frontend/src/features/live-view/` (all still M5's to create).

## Scope

All of Epic M5 in `docs/TASK_BACKLOG.md`:

- T-050 — `OnvifRtspFrameSource` (resolves `GetStreamUri`, delegates decode).
- T-051 — `RawRtspFrameSource` (generic RTSP URL, no ONVIF involved).
- T-052 — MJPEG live-view HTTP endpoint.
- T-053 — WebSocket stream-status/health channel.
- T-054 — Real-world reconnect validation against the physical camera.
- T-055 — Frontend live-view component with status indicator.

Use the existing `IFrameSource` port (`backend/app/application/ports/frame_source.py`), the new `IStreamWorker` port (`backend/app/application/ports/stream_worker.py`), and the existing `StartLiveStreamUseCase` stub (`backend/app/application/use_cases/start_live_stream.py`, whose docstring already names T-050 as where its real logic lands) as the starting point. Verify all three still fit before coding against them; if a documented contract doesn't cleanly support what M5 needs, stop and propose the smallest documented change instead of working around it.

## Out of Scope

- M2 (Frame Source Abstraction + MP4 File Adapter) — already complete (see Context above); nothing further to build there.
- M6 (Recording), including the FFmpeg segment-muxer and recording/live-view concurrency, even though it will reuse this milestone's resolved stream.
- M7 (Playback).
- M8+ (Analytics Pipeline Foundation and every capability milestone after it) — this milestone only has to remain unaffected by analytics being toggled once M8+ exists (see Acceptance Criteria), not build any analytics integration itself.
- WS-Discovery/network-scan onboarding, HLS/WebRTC transport, and other items `docs/TECHNICAL_DECISIONS.md` TD-03/TD-10 list as future enhancements rather than in-scope now.
- User authentication, RBAC, multi-tenancy, cloud storage, message brokers, mobile applications, and alerting integrations — explicit non-goals in `docs/AI_PROJECT_CONTEXT.md` §7.

## Acceptance Criteria

Copied verbatim from `docs/IMPLEMENTATION_PLAN.md` §M5:

- Live view renders in-browser for the physical camera (or an RTSP test stream) within a few seconds of starting.
- Simulated disconnect (e.g. camera network cable pulled, or test RTSP server killed) results in automatic reconnection without manual intervention, visible in logs and reflected in the UI's connection-status indicator.
- Analytics-independent: turning analytics on/off (once it exists, M8+) does not change live-view behavior.

Matching Definition of Done statements copied verbatim from `docs/TASK_BACKLOG.md` Epic M5:

- T-050: Same `Frame` shape as `Mp4FileFrameSource`.
- T-051: Works against a generic RTSP URL with no ONVIF involved.
- T-052: Renders in a plain `<img>` tag in a browser.
- T-053: UI reflects connected/reconnecting/failed states in real time.
- T-054: Documented test: network interrupted → auto-recovers within N seconds.
- T-055: Visually confirms stream + shows reconnect state during induced failure.

## Constraints

- Follow the Dependency Direction Rule in `docs/FOLDER_STRUCTURE.md`: `StartLiveStreamUseCase` depends on `IFrameSource` and `IStreamWorker` only, never a concrete FFmpeg/OpenCV/RTSP class nor the concrete `StreamWorker`/`ReconnectSupervisor` classes; `interfaces/api/streams.py` and `interfaces/websocket/stream_status.py` call the use case only, never `infrastructure/streaming/` directly; `infrastructure/streaming/` never imports `infrastructure/analytics/` or vice versa.
- No new third-party dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR (`AGENTS.md` § Dependency Rules). TD-04 already decides FFmpeg (subprocess) + OpenCV for decode and TD-10 already decides MJPEG-over-HTTP + a separate WebSocket channel for status — implement within those decisions rather than introducing an alternative transport or decode library.
- Reconnect/backoff must go through the same supervised `StreamWorker`/`ReconnectSupervisor` lifecycle built in M2 (T-023/T-024, TD-20) — `docs/PROMPTING_GUIDE.md` §5 names "skipping the reconnect/backoff supervisor for a 'just this once' direct connection" as a recurring trap that produces two divergent connection-handling code paths that never get unified. `OnvifRtspFrameSource` and `RawRtspFrameSource` must be `IFrameSource`s the Stream Worker supervises (same pattern as `Mp4FileFrameSource`), not self-managing connections with their own retry logic.
- Never read configuration (RTSP timeouts, backoff parameters, MJPEG boundary, etc.) via `os.environ` outside `backend/app/core/config.py` (`AGENTS.md` § Things AI Must Never Do).
- Never have `StartLiveStreamUseCase` call an infrastructure adapter directly instead of through a port.
- Never log a resolved RTSP stream URI or camera credential verbatim — `GetStreamUri` results and RTSP connection strings can embed camera credentials, and TD-15/`AGENTS.md` forbid camera passwords appearing in logs.
- Live view must remain unaffected by analytics being enabled/disabled once M8+ exists — this is Acceptance Criterion 3 above; do not build any coupling to an analytics on/off flag in this milestone.

## Deliverables

Implement the M5 deliverables from `docs/IMPLEMENTATION_PLAN.md` §M5 at these paths:

- `backend/app/infrastructure/streaming/rtsp_frame_source.py` — `OnvifRtspFrameSource` and `RawRtspFrameSource`, both implementing `IFrameSource`, sharing the FFmpeg/OpenCV decode path introduced by M2.
- `backend/app/application/use_cases/start_live_stream.py` — complete `StartLiveStreamUseCase`, wiring a Stream Worker to a real RTSP source resolved via `GetStreamUri` (replace the current `NotImplementedError` body; keep or extend its existing `ICameraGateway`/`ICameraRepository` constructor dependencies as needed).
- `backend/app/interfaces/api/streams.py` — MJPEG-over-HTTP live-view endpoint (new file; new router, wired into `backend/app/main.py` and `backend/app/core/container.py` the same way `cameras.py` is today).
- `backend/app/interfaces/websocket/stream_status.py` — WebSocket channel for stream health/status (new file; new package, since `backend/app/interfaces/websocket/` does not exist yet).
- `frontend/src/features/live-view/**` — `<img>`-based MJPEG viewer component with a connection-status indicator (new feature folder, since `frontend/src/features/` currently only has `camera-onboarding/`).

Modify the composition root (`backend/app/core/container.py`), app wiring (`backend/app/main.py`), and any frontend API client/types/routing needed to reach these deliverables from the browser. Resolve the exact additional paths (e.g. a `streams` API client, a `useLiveStream` hook per `docs/FOLDER_STRUCTURE.md`'s `frontend/src/hooks/` convention) in the required pre-implementation plan; do not create files for another milestone.

## Testing Expectations

Per `AGENTS.md` § Testing Expectations:

- Domain and Application layers (`StartLiveStreamUseCase`): unit tests with no real I/O, using fakes for `ICameraGateway`/`ICameraRepository` and the M2 `IFrameSource`/Stream Worker abstractions.
- Infrastructure adapters (`OnvifRtspFrameSource`, `RawRtspFrameSource`): integration tests against the committed local MP4 fixture (`backend/tests/fixtures/sample.mp4`, from M2) by default; anything requiring the physical camera is marked `@pytest.mark.hardware` and skipped in CI.
- A real-world or simulated disconnect (network interruption / RTSP source killed) must trigger automatic reconnection without manual intervention, observable in logs and reflected in the UI's connection-status indicator — this is T-054's explicit "documented test" requirement; document the reproduction steps (how the disconnect was induced, expected recovery time) alongside the test, not only assert on backoff timing.
- Do not weaken or delete the M2 fake-flaky-`IFrameSource` reconnect/backoff unit test while extending it for RTSP sources.
- Run the repository's configured formatter, linter, type checker, and test suite before considering the milestone done.

## Documentation Update Requirements

- At the start, move these exact current `TASKS.md` lines from `# Remaining` to `# In Progress`: `- [ ] RTSP Stream Manager / Browser Live Streaming (M5)` and `- [ ] Automatic Reconnection (M5)`. Once every acceptance criterion is met, move both to `# Completed` in the same PR.
- Update `README.md`'s FFmpeg install-prerequisites row (currently "not needed yet, only from M5 onward") to reflect that FFmpeg is now required.
- If implementation reveals a planning or architecture document was wrong or incomplete (e.g. `docs/ARCHITECTURE.md` §6.2's sequence diagram, or M5's Dependencies line once M2's actual shape is known), update it in the same PR per `AGENTS.md` § Documentation Update Policy. Do not duplicate documentation into a new file.
- If implementation requires a new third-party dependency or makes a real technical decision not already covered, add the corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR.

## Milestone Boundary

Implement ONLY this milestone. Do not implement work belonging to any other milestone, even if it seems convenient or clearly needed soon. If, during implementation, you discover that another milestone's work is genuinely required to complete this one, stop and explain why before writing that code — do not silently expand scope.

This applies concretely to M2's abstractions: build on `IFrameSource`/`IStreamWorker`/`StreamWorker`/`ReconnectSupervisor` as they exist today; do not modify M2's internals to suit M5's convenience without first confirming the change here (per the Scope section's "verify the port fits" instruction) — a genuinely needed change to an M2 file should be flagged and justified, not made silently.

## Required Pre-Implementation Output

Before writing any code, produce:

- **M2-precondition check** — confirm, against the working tree at execution time, that `docs/TASK_BACKLOG.md` T-020–T-024 (finalized `Frame`, `Mp4FileFrameSource`, `IStreamWorker`, `StreamWorker`, `ReconnectSupervisor`) still exist as described in Context above. Expected: yes (M2 merged in PR #10) — but this is a live check against the actual working tree, not an assumption carried over from this prompt. If the precondition somehow does not hold, stop here per Milestone Boundary above instead of producing the rest of this plan.
- **Implementation Plan** — describe how `StartLiveStreamUseCase` resolves a camera's stream URI via the existing `ICameraGateway`, hands it to an `IStreamWorker` (built by the composition root, wrapping an `OnvifRtspFrameSource`/`RawRtspFrameSource`), how the MJPEG endpoint and WebSocket status channel each consume that worker's `frames()`/`health()`, and how the frontend live-view component reflects connected/reconnecting/failed state during an induced disconnect.
- **Files to Create** — list every concrete path, including tests.
- **Files to Modify** — list every concrete path, including `backend/app/core/container.py`, `backend/app/main.py`, any frontend routing/services files, `TASKS.md`, and `README.md`.
- **Risks** — address the unavailable-hardware path (falling back to a test RTSP stream or the M2 MP4 fixture), multi-viewer MJPEG resource usage (TD-10's documented tradeoff), and correctly distinguishing a genuine disconnect from a transient frame stall.
- **Assumptions** — state only assumptions confirmed by the consulted documentation and current code. `IStreamWorker`'s shape is now fixed by M2 (TD-20) and should be treated as given, not re-derived; if some other required contract is still undefined upstream at execution time, identify it as an explicit decision requiring confirmation before implementation rather than inventing it.

This plan is produced first. Implementation proceeds only after it — and, if this is running interactively, only after the human reviewing it has had the chance to object, unless the human has explicitly asked for autonomous execution without a pause.

## Required Closing Report

On completion, produce:

- **Summary of Implementation**
- **Acceptance Criteria Satisfied** — check each exact item in the Acceptance Criteria section above.
- **Tradeoffs**
- **New Technical Decisions** — identify each one and confirm its corresponding `docs/TECHNICAL_DECISIONS.md` entry was added in the same PR, if applicable.
- **Suggested Commit Message** — `Implement live streaming and auto-reconnect (T-050, T-051, T-052, T-053, T-054, T-055)`.
- **Suggested PR Title** — `M5: Live Streaming + Auto-Reconnect`.
