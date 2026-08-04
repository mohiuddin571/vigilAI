# Implementation Prompt: Recording (M6)

## Context

M6 records an onboarded camera's live RTSP stream to disk as MP4 segments via an FFmpeg stream-copy muxer, independent of the analytics decode path — so recording fidelity never depends on whether analytics is enabled and vice versa (`docs/TECHNICAL_DECISIONS.md` TD-04). It follows M5 (Live Streaming + Auto-Reconnect), complete per `TASKS.md`, which is where the ONVIF `GetStreamUri` resolution pattern this milestone reuses (`StartLiveStreamUseCase`, `backend/app/application/use_cases/start_live_stream.py`) was established.

**Current repo state** (confirm against the working tree at execution time rather than trusting this paragraph — see Required Pre-Implementation Output): M0–M5 are complete. `backend/app/application/use_cases/start_recording.py` and `list_recordings.py` are M1-era stubs (`NotImplementedError` bodies) already typed against `ICameraRepository`/`IRecordingRepository`; `backend/app/application/ports/recording_repository.py::IRecordingRepository` (`add`/`get`/`list`) and `backend/app/domain/entities/recording.py::Recording` (`camera_id`, `file_path`, `started_at`, `ended_at`, `size_bytes`, `duration_seconds`) already exist from M1. No `StopRecordingUseCase`, no `SqlRecordingRepository`, no `backend/app/interfaces/api/recordings.py`, and no Recording Worker exist yet. `storage/recordings/` is already gitignored (`.gitignore`) and named in `docs/FOLDER_STRUCTURE.md` as the Recording Worker's default output path.

## Documents Consulted

- `AGENTS.md` (full)
- `TASKS.md` (full; current state)
- `docs/IMPLEMENTATION_PLAN.md` §M6, and §M5/§M7 for adjacent-milestone boundaries
- `docs/TASK_BACKLOG.md` Epic M6 (T-060–T-065) and Epic M5 (T-050 dependency context)
- `docs/TECHNICAL_DECISIONS.md` TD-04 (FFmpeg subprocess, stream-copy recording), TD-05 (process-per-stream concurrency), TD-10 (MJPEG live-view concurrency), TD-15 (credential logging ban), TD-18/TD-19/TD-20/TD-21 (the precedent pattern of additive ports/entities discovered only once real implementation is attempted, and TD-21's specific finding that `ffmpeg` was not installed in the M5 implementation environment)
- `docs/ARCHITECTURE.md` §5 (Unified Frame Source), §6.2 (Live Streaming sequence), §6.3 (Recording & Playback)
- `docs/FOLDER_STRUCTURE.md` (Backend/Frontend folder ownership, "Dependency Direction Rule", `storage/recordings/`)
- `docs/PROMPTING_GUIDE.md` §5 (Recurring Traps to Name Explicitly)
- `prompts/00-README.md`, `prompts/05-recording.md` (full)
- `README.md` (status line; FFmpeg prerequisite row, currently framed as a dev/test-only tool "required from M5 onward")
- Current repo state: `backend/app/application/use_cases/start_recording.py`, `list_recordings.py`, `backend/app/application/ports/recording_repository.py`, `backend/app/domain/entities/recording.py`, `backend/app/application/use_cases/start_live_stream.py` (RTSP-URI resolution pattern to reuse), `backend/app/application/ports/camera_gateway.py` (`get_stream_uri`), `backend/app/core/container.py`, `backend/app/main.py`, `backend/app/core/config.py` (`Settings`), `backend/app/interfaces/api/{cameras.py,streams.py}` (router-factory pattern), `.gitignore` (`storage/recordings/`) — confirmed absence of `StopRecordingUseCase`, `SqlRecordingRepository`, `backend/app/infrastructure/streaming/recording_worker.py`, `backend/app/interfaces/api/recordings.py`, and any `frontend/src/features/recordings/`.

## Scope

From Epic M6 in `docs/TASK_BACKLOG.md`:

- T-060 — FFmpeg segment-muxer recording worker (stream copy).
- T-061 — `SqlRecordingRepository` + recording metadata schema.
- T-062 — `StartRecordingUseCase` / `StopRecordingUseCase`.
- T-063 — `POST /cameras/{id}/recording/start`/`stop`, `GET /recordings` endpoints.
- T-064 — Recording/live-view concurrency verification.

Use the existing `IRecordingRepository` port (`backend/app/application/ports/recording_repository.py`) and `Recording` entity (`backend/app/domain/entities/recording.py`) as the starting point for T-061/T-062 — both are M1-fixed and should be treated as given unless implementation reveals a genuine gap (e.g. `Recording` currently models one `file_path`, not a set of segments; if FFmpeg's segment muxer produces multiple files per start/stop cycle, resolve this by either extending `Recording` or persisting one row per segment file — decide and document this as a real technical decision, don't silently pick one without noting it). Verify `IRecordingRepository`/`Recording` still fit before coding against them, per `docs/PROMPTING_GUIDE.md` §4's "architecture-sensitive refactor" pattern; if they don't cleanly fit, stop and propose the smallest documented change instead of working around it.

## Out of Scope

- T-065 (Storage path/quota configuration) — P2, "do if time allows" per `docs/TASK_BACKLOG.md`'s priority key, and not required by any Acceptance Criterion below. A sensible default output path under `storage/recordings/` is in scope (the deliverable itself requires segments to land there); making that path and a disk-usage/quota policy configurable via `Settings` beyond that default is T-065's job, not this milestone's.
- M7 (Playback), including the HTTP range-request playback endpoint, even though it consumes this milestone's output and the frontend `recordings/` feature folder created here.
- M8+ (Analytics Pipeline Foundation and every capability milestone after it) — this milestone only has to remain unaffected by analytics being toggled (mirroring M5's equivalent constraint), not build any analytics integration.
- WS-Discovery/network-scan onboarding, HLS/WebRTC transport, and other items `docs/TECHNICAL_DECISIONS.md` names as future enhancements rather than in-scope now.
- User authentication, RBAC, multi-tenancy, cloud/object storage, message brokers, mobile applications, and alerting integrations — explicit non-goals in `docs/AI_PROJECT_CONTEXT.md` §7.

## Acceptance Criteria

Copied verbatim from `docs/IMPLEMENTATION_PLAN.md` §M6:

- Starting a recording produces valid, playable MP4 segment(s) on disk under `storage/recordings/`.
- Recording metadata is queryable via `GET /recordings` immediately after stopping.
- Recording continues correctly across the live-view MJPEG stream being opened/closed (the two paths don't interfere).

Matching Definition of Done statements copied verbatim from `docs/TASK_BACKLOG.md` Epic M6:

- T-060: Produces valid MP4 segments verifiable with `ffprobe`.
- T-061: Segment rows queryable with correct duration/size.
- T-062: Start→stop cycle produces exactly one consistent metadata row per segment set.
- T-063: Manual test: start, wait, stop, list shows entry.
- T-064: Both running simultaneously without frame drops/corruption in either.

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`): `StartRecordingUseCase`/`StopRecordingUseCase` depend on ports only, never a concrete FFmpeg/subprocess class directly. No abstraction currently exists for "the Recording Worker" the way `IStreamWorker` exists for the Stream Worker (`docs/TECHNICAL_DECISIONS.md` TD-20) — no planning document specifies this port's shape, so this is a genuine gap, not an oversight to reproduce; add the smallest additive port needed (mirroring the precedent in TD-18/TD-19/TD-20/TD-21, each of which added a port/method once real implementation revealed a contract gap) and record the decision per the Documentation Update Requirements below. `interfaces/api/recordings.py` must call use cases only, never `infrastructure/streaming/` or `infrastructure/persistence/` directly. `infrastructure/streaming/` must not import `infrastructure/analytics/` or vice versa.
- No new third-party dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR (`AGENTS.md` § Dependency Rules). TD-04 already decides FFmpeg as a subprocess for recording — implement within that decision (invoke the `ffmpeg` binary via `subprocess`/`asyncio.create_subprocess_exec`, per TD-04's "transparent and debuggable" rationale) rather than introducing a Python FFmpeg-wrapper library.
- Recording must use FFmpeg stream-copy (`-c copy`, no re-encode) per TD-04, reading directly from the RTSP source resolved via `ICameraGateway.get_stream_uri` — not from `IFrameSource`/Stream Worker decoded frames. Reuse `StartLiveStreamUseCase`'s existing pattern for resolving a camera's stream URI through `ICameraGateway` (connect → `get_stream_uri` → disconnect) as the model for how the Recording Worker obtains its input URL; do not decode frames to produce the recording.
- Must not interfere with, or be interfered by, the live-view MJPEG path running concurrently — verify both running at once (T-064). Recording and live-view are two independent consumers of the same underlying RTSP source; neither may hold an exclusive lock on it that blocks the other.
- Never read configuration (output directory, segment duration, FFmpeg binary path, etc.) via `os.environ` outside `backend/app/core/config.py` (`AGENTS.md` § Things AI Must Never Do).
- Never have a use case call an infrastructure adapter directly instead of through a port.
- Never log a resolved RTSP stream URI or camera credential verbatim — the same URI resolved by `get_stream_uri` can embed credentials, and TD-15/`AGENTS.md` forbid camera passwords appearing in logs; this applies equally to the Recording Worker's FFmpeg command-line construction (do not log the full invoked command if it contains the URI unredacted).

## Deliverables

Implement the M6 deliverables from `docs/IMPLEMENTATION_PLAN.md` §M6 at these paths:

- `backend/app/infrastructure/streaming/recording_worker.py` — FFmpeg segment-muxer recording worker (stream copy), reading directly from the RTSP source.
- `backend/app/infrastructure/persistence/recording_repository.py` — `SqlRecordingRepository` implementing `IRecordingRepository`, persisting segment metadata (camera, start/end time, duration, file path, size). Follow the existing `SqlCameraRepository` (`backend/app/infrastructure/persistence/sql_camera_repository.py`) as the naming/structure precedent for this repository implementation and its SQLModel table (`backend/app/infrastructure/persistence/models.py`).
- `backend/app/application/use_cases/start_recording.py` — replace the current `NotImplementedError` body of `StartRecordingUseCase` with real logic.
- `backend/app/application/use_cases/stop_recording.py` — new `StopRecordingUseCase` (does not exist yet).
- `backend/app/interfaces/api/recordings.py` — new router: `POST /cameras/{id}/recording/start`, `POST /cameras/{id}/recording/stop`, `GET /recordings`.
- `frontend/src/features/recordings/**` — new feature folder (per `docs/FOLDER_STRUCTURE.md`'s named `frontend/src/features/recordings/` area, which M7 will later extend with the playback list/player) containing the start/stop recording control with visible status.

Modify the composition root (`backend/app/core/container.py`), app wiring (`backend/app/main.py`), and any frontend API client/types/routing needed to reach these deliverables from the browser. Resolve the exact additional paths (e.g. the new Recording Worker port's file under `backend/app/application/ports/`, a `recordings` API client, a `useRecording` hook per `docs/FOLDER_STRUCTURE.md`'s `frontend/src/hooks/` convention) in the required pre-implementation plan; do not create files for another milestone.

## Testing Expectations

Per `AGENTS.md` § Testing Expectations, and the template's own Testing Expectations:

- Domain and Application layers (`StartRecordingUseCase`, `StopRecordingUseCase`): unit tests with no real I/O, using fakes for `ICameraRepository`, `IRecordingRepository`, and the new Recording Worker port.
- Infrastructure adapters (`SqlRecordingRepository`, the FFmpeg recording worker): integration tests against the committed local fixture (`backend/tests/fixtures/sample.mp4`, from M2) by default.
- Produced segments must be valid MP4, verifiable with `ffprobe` (T-060's explicit DoD) — the test suite must actually invoke `ffprobe` (or an equivalent programmatic check) against a segment produced by a real `ffmpeg` subprocess run, not merely assert a file was written.
- Recording metadata must be queryable via the repository/`GET /recordings` immediately after stopping (AC #2 / T-063's DoD) — cover this with an integration test that starts, waits, stops, and lists in sequence.
- T-064's concurrency requirement (recording and live-view MJPEG running simultaneously without frame drops/corruption in either) needs a documented test or reproduction steps, following the same pattern TD-21 used for T-054 (Live Streaming's real-world reconnect check) when the required hardware/binary wasn't available in the implementation environment: TD-21 recorded that `ffmpeg -version` was not found in that environment. Confirm whether `ffmpeg` is now installed before implementation; if it still is not, do not silently skip T-064 — document the gap the same way TD-21 did (what was verified instead, and the exact reproduction steps for whoever has `ffmpeg`/a camera available), rather than claiming the acceptance criterion is met.
- Do not weaken or delete the M2 fake-flaky-`IFrameSource` reconnect/backoff unit test or the T-086 source-independence regression test (neither is touched by this milestone, but both are permanent per `AGENTS.md`).
- Run the repository's configured formatter, linter, type checker, and test suite before considering the milestone done.

## Documentation Update Requirements

- At the start, replace the current `TASKS.md` placeholder line `- [ ] _Nothing yet. Next up: Recording (M6)._` under `# In Progress` with `- [ ] Recording (M6)` (moved from `# Remaining`, removing it from that list). Once every acceptance criterion is met, move it to `# Completed` in the same PR, and restore the `# In Progress` section's placeholder line naming the next milestone (Playback, M7).
- Update `README.md`'s status line (currently "...M4 (ONVIF Configuration), and M5 (Live Streaming + Auto-Reconnect) complete. Next up: M6 (Recording).") to reflect M6's completion and M7 as next, since recording start/stop is a new user-visible capability.
- Update `README.md`'s FFmpeg prerequisite row: it currently frames `ffmpeg` as needed only "as a dev/test tool to serve a local test RTSP stream" (M5-era wording). From this milestone on, `ffmpeg` is a genuine runtime dependency — the Recording Worker invokes it directly as a subprocess (TD-04) — so this row's justification is now stronger than "dev/test tool" and should say so.
- Add a `docs/TECHNICAL_DECISIONS.md` entry for the Recording Worker's port shape (the new abstraction `StartRecordingUseCase`/`StopRecordingUseCase` depend on instead of the concrete FFmpeg worker class) and the concrete FFmpeg subprocess invocation approach (flags, segment naming/rotation scheme, how the process is supervised/stopped cleanly), following the TD-18/TD-19/TD-20/TD-21 precedent of documenting implementation-time decisions the planning docs didn't fix precisely enough to derive without a real choice. If `Recording`'s single-`file_path` shape needed to change to support multiple segments per start/stop cycle, document that decision here too.
- If implementation reveals any other planning document was wrong or incomplete, update it in the same PR per `AGENTS.md` § Documentation Update Policy. Do not duplicate documentation into a new file — link to it.

## Milestone Boundary

Implement ONLY this milestone. Do not implement work belonging to any other milestone, even if it seems convenient or clearly needed soon. If, during implementation, you discover that another milestone's work is genuinely required to complete this one, stop and explain why before writing that code — do not silently expand scope.

This applies concretely to M7 (Playback): the `frontend/src/features/recordings/` folder and `GET /recordings` endpoint created here are deliberately minimal — start/stop control and a list sufficient to satisfy AC #2, not a player or seek UI, which is M7's job.

## Required Pre-Implementation Output

Before writing any code, produce:

- **M5-precondition check** — confirm, against the working tree at execution time, that `StartLiveStreamUseCase`, `ICameraGateway.get_stream_uri`, `IRecordingRepository`, and `Recording` still exist as described in Context above, and confirm whether the `ffmpeg` binary is present in the current environment (`ffmpeg -version`). Report the result of this check explicitly; if `ffmpeg` is absent, say so before proceeding rather than assuming it exists.
- **Implementation Plan** — describe: how the Recording Worker resolves a camera's RTSP URI (reusing `ICameraGateway.get_stream_uri`, mirroring `StartLiveStreamUseCase`'s connect → resolve → disconnect pattern); the exact `ffmpeg` command line and segment-naming/rotation scheme used for stream-copy muxing; the shape of the new port `StartRecordingUseCase`/`StopRecordingUseCase` will depend on instead of the concrete worker class; how segment metadata reaches `SqlRecordingRepository` (including how `Recording`'s current single-`file_path` shape is or isn't extended for multiple segments); and how concurrent recording + live-view MJPEG access to the same camera's RTSP source is verified not to interfere (T-064).
- **Files to Create** — list every concrete path, including tests and the new port file.
- **Files to Modify** — list every concrete path, including `backend/app/core/container.py`, `backend/app/main.py`, `backend/app/infrastructure/persistence/models.py`, any frontend routing/services files, `TASKS.md`, and `README.md`.
- **Risks** — address: `ffmpeg` binary availability in the implementation environment (per the precondition check above and TD-21's prior finding); cleanly stopping a running `ffmpeg` subprocess without corrupting the final segment; concurrent recording/live-view access to one camera's RTSP source (T-064); and file/storage-path collisions across overlapping or restarted recording sessions.
- **Assumptions** — state only assumptions confirmed by the consulted documentation and current code. `IRecordingRepository`/`Recording`'s existing M1 shape should be treated as given unless the plan identifies and justifies a specific extension need; the Recording Worker's port shape is genuinely undefined upstream and must be treated as a real decision to make and document, not re-derived from a document that doesn't specify it.

This plan is produced first. Implementation proceeds only after it — and, if this is running interactively, only after the human reviewing it has had the chance to object, unless the human has explicitly asked for autonomous execution without a pause.

## Required Closing Report

On completion, produce:

- **Summary of Implementation**
- **Acceptance Criteria Satisfied** — check each exact item in the Acceptance Criteria section above.
- **Tradeoffs**
- **New Technical Decisions** — identify each one (the Recording Worker port shape, the FFmpeg invocation/segment scheme, and any `Recording` entity change, at minimum) and confirm its corresponding `docs/TECHNICAL_DECISIONS.md` entry was added in the same PR.
- **Suggested Commit Message** — `Implement recording to disk with FFmpeg stream-copy (T-060, T-061, T-062, T-063, T-064)`.
- **Suggested PR Title** — `M6: Recording`.
