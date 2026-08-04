# Implementation Prompt: Playback (M7)

## Context

M7 lets a user browse and play back recorded footage from the frontend, serving stored MP4 segments over HTTP range requests so the browser's native `<video>` element can seek without a custom protocol. It follows M6 (Recording), complete per `TASKS.md`/`README.md`'s status line and `docs/AI_PROJECT_CONTEXT.md` §9, which produced real ffprobe-valid MP4 segments under `storage/recordings/{camera_id}/`, persisted one row per physical segment file via `SqlRecordingRepository` (`docs/TECHNICAL_DECISIONS.md` TD-22).

**Current repo state** (confirm against the working tree at execution time rather than trusting this paragraph — see Required Pre-Implementation Output): M0–M6 are complete. `backend/app/application/use_cases/list_recordings.py` (`ListRecordingsUseCase`) is **already implemented**, not a stub — TD-22 explicitly built it ahead of its formal T-071 assignment because M6's own AC #2 ("Recording metadata is queryable via `GET /recordings`") needed it; its docstring says so and names "richer filtering/pagination beyond what `IRecordingRepository.list()` already supports" as this milestone's remaining job. `backend/app/interfaces/api/recordings.py` already exists with `POST /cameras/{id}/recording/start`, `/stop`, and `GET /recordings` (camera/time-range filterable). No playback/range-request endpoint exists yet. `backend/app/domain/exceptions.py` has no `RecordingNotFoundError` (confirmed absent). `frontend/src/features/recordings/RecordingControl.tsx` exists from M6 with an in-code comment stating it is "deliberately minimal... no player/seek, which is M7's (Playback) job" — it renders start/stop control and a plain list only. `frontend/src/services/recordingsApi.ts` already has `listRecordings`/`startRecording`/`stopRecording`; no playback-URL helper exists yet.

## Documents Consulted

- `AGENTS.md` (full)
- `TASKS.md` (full; current state)
- `docs/IMPLEMENTATION_PLAN.md` §M6 (dependency context) and §M7
- `docs/TASK_BACKLOG.md` Epic M6 (T-061, dependency context) and Epic M7 (T-070–T-072)
- `docs/TECHNICAL_DECISIONS.md` TD-04 (FFmpeg stream-copy, no re-encode), TD-09 (SQLModel/SQLite persistence), TD-22 (M6's as-built shape — specifically decision 2's one-row-per-segment persistence model this milestone serves, and its explicit note that `ListRecordingsUseCase`'s core logic already exists)
- `docs/ARCHITECTURE.md` §6.3 (Recording & Playback flow: "playback is served via HTTP range requests so the browser's native `<video>` seek works without a custom protocol")
- `docs/FOLDER_STRUCTURE.md` (Backend/Frontend folder ownership, "Dependency Direction Rule", `storage/recordings/`)
- `docs/PROMPTING_GUIDE.md` §5 (Recurring Traps to Name Explicitly)
- `prompts/00-README.md`, `prompts/06-playback.md` (full)
- `README.md` (status line: "...M6 (Recording) complete. Next up: M7 (Playback).")
- Current repo state: `backend/app/interfaces/api/recordings.py`, `backend/app/application/use_cases/list_recordings.py`, `backend/app/application/ports/recording_repository.py`, `backend/app/domain/entities/recording.py`, `backend/app/domain/exceptions.py` (confirmed no `RecordingNotFoundError`), `backend/app/core/exception_handlers.py`, `backend/app/core/container.py`, `backend/app/core/config.py` (`recording_output_dir`), `backend/tests/unit/application/test_list_recordings.py` (confirmed single-recording fixture only, not yet "multiple cameras/days"), `frontend/src/features/recordings/RecordingControl.tsx`, `frontend/src/services/recordingsApi.ts`, `frontend/src/types/recording.ts`, `frontend/src/App.tsx`.

## Scope

From Epic M7 in `docs/TASK_BACKLOG.md`:

- T-070 — HTTP range-request playback endpoint.
- T-071 — `ListRecordingsUseCase` with camera/date filters. The pass-through implementation already exists (M6, TD-22); this milestone's remaining work is bringing its test coverage up to T-071's own Definition of Done ("filters verified by test data spanning multiple cameras/days"), and extending the use case itself only if a genuine gap surfaces against that DoD — not re-implementing what already works.
- T-072 — Frontend recordings list + `<video>` player.

## Out of Scope

- M6 (Recording)'s own remaining known limitations — no reconnect/backoff for the Recording Worker, no live segment-rollover tracking — both explicitly named as TD-22 Future Enhancements, not this milestone's job.
- M8+ (Analytics Pipeline Foundation and every capability milestone after it).
- WS-Discovery/network-scan onboarding, HLS/WebRTC transport, object storage for recordings, and other items `docs/TECHNICAL_DECISIONS.md` names as future enhancements rather than in-scope now.
- User authentication, RBAC, multi-tenancy, cloud/object storage, message brokers, mobile applications, and alerting integrations — explicit non-goals in `docs/AI_PROJECT_CONTEXT.md` §7.

## Acceptance Criteria

Copied verbatim from `docs/IMPLEMENTATION_PLAN.md` §M7:

- A recorded segment plays back in-browser with working seek/scrub, confirming range-request support.
- Recordings list is filterable by camera and time range.

Matching Definition of Done statements copied verbatim from `docs/TASK_BACKLOG.md` Epic M7:

- T-070: `curl -r` partial requests return correct `206` responses.
- T-071: Filters verified by test data spanning multiple cameras/days.
- T-072: Seek/scrub works smoothly in-browser.

## Constraints

- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`): `interfaces/api/recordings.py` calls use cases/repositories only through their existing ports, never touches the filesystem or `infrastructure/persistence/` internals directly beyond what the existing router-factory pattern (`create_recordings_router`, per `backend/app/interfaces/api/cameras.py`'s equivalent) already establishes.
- No new third-party dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR (`AGENTS.md` § Dependency Rules).
- The playback endpoint must serve via HTTP range requests so the browser's native `<video>` seek works without a custom protocol (template constraint, matching `docs/ARCHITECTURE.md` §6.3).
- Resolve the served file path via `IRecordingRepository`'s stored `file_path` only, keyed by the recording's UUID from the URL — never construct or accept a filesystem path directly from client input, to avoid a path-traversal vulnerability in a file-serving endpoint.
- A request for a recording id that doesn't exist must return a typed 4xx, not a raw filesystem error or unhandled exception — `RecordingNotFoundError` does not exist yet (confirmed absent from `backend/app/domain/exceptions.py`); add it additively, mirroring `CameraNotFoundError`, and map it in `backend/app/core/exception_handlers.py` the same way `RecordingNotInProgressError` → `409` was added at M6 (TD-22).
- Never read configuration (any new playback-related setting, if needed) via `os.environ` outside `backend/app/core/config.py`.
- Never have a use case or router call an infrastructure adapter directly instead of through a port.

## Deliverables

Implement the M7 deliverables from `docs/IMPLEMENTATION_PLAN.md` §M7 at these paths:

- `backend/app/interfaces/api/recordings.py` (extended) — a new playback route serving a recording's MP4 file via HTTP range requests. `docs/IMPLEMENTATION_PLAN.md`/`docs/TASK_BACKLOG.md` do not fix the exact route path or the range-request serving mechanism (e.g. a framework-provided range-aware file response vs. hand-rolled `Range` header parsing) — decide and document this in the required pre-implementation plan below, choosing the smallest addition consistent with the existing `/recordings`/`/cameras/{id}/recording/*` routes already in this file.
- `backend/app/domain/exceptions.py` (extended) — `RecordingNotFoundError`, per the Constraints section above.
- `backend/app/core/exception_handlers.py` (extended) — the corresponding 4xx mapping.
- `frontend/src/features/recordings/**` (extended) — a recordings browser: camera/time-range filter controls plus a native `<video>` player with working seek/scrub, extending (not replacing) `RecordingControl.tsx`'s existing start/stop control and list.

Modify `backend/app/application/use_cases/list_recordings.py` only if the pre-implementation plan identifies a genuine gap against T-071's DoD that the existing pass-through implementation doesn't already satisfy — do not rewrite working M6 code without a stated reason. Modify the frontend API client/hooks/types (`frontend/src/services/recordingsApi.ts`, `frontend/src/hooks/`, `frontend/src/types/recording.ts`) and `frontend/src/App.tsx` as needed to reach the new deliverables from the browser. Resolve the exact additional paths in the required pre-implementation plan; do not create files for another milestone.

## Testing Expectations

Per `AGENTS.md` § Testing Expectations, and the template's own Testing Expectations:

- A partial-content (`206`) range request must be verified, not just a full-file `GET` (template's explicit instruction) — cover both a `curl -r`-equivalent partial request (correct `206` status, `Content-Range` header, and byte-range body) and a full, non-ranged request (still `200`) against a real MP4 segment file. Use `backend/tests/fixtures/sample.mp4` (or a fixture-produced `Recording` row pointing at it) as the test's underlying file, consistent with how M2/M6 use the same fixture.
- Extend `backend/tests/unit/application/test_list_recordings.py` (or an equivalent integration test) to satisfy T-071's own DoD literally — "filters verified by test data spanning multiple cameras/days" — which the current single-recording fixture does not yet exercise.
- A request for a nonexistent recording id must be verified to return the new typed 4xx, not a raw error.
- Domain/Application layers: unit tests with no real I/O, using fakes for `IRecordingRepository`, for any new or modified use-case logic.
- Do not weaken or delete the M2 fake-flaky-`IFrameSource` reconnect/backoff unit test or the T-086 source-independence regression test — neither is touched by this milestone, but both are permanent per `AGENTS.md`.
- Run the repository's configured formatter, linter, type checker, and test suite before considering the milestone done.

## Documentation Update Requirements

- At the start, replace the current `TASKS.md` placeholder line `- [ ] _Nothing yet. Next up: Playback (M7)._` under `# In Progress` with `- [ ] Playback (M7)` (moved from `# Remaining`, removing it from that list). Once every acceptance criterion is met, move it to `# Completed` in the same PR, and restore the `# In Progress` section's placeholder line naming the next milestone (Analytics Pipeline Foundation, M8).
- Update `README.md`'s status line (currently "...M5 (Live Streaming + Auto-Reconnect), and M6 (Recording) complete. Next up: M7 (Playback).") to reflect M7's completion and M8 as next.
- Add a `docs/TECHNICAL_DECISIONS.md` entry for the playback endpoint's route shape and range-request serving mechanism, and for `RecordingNotFoundError`'s addition, following the TD-18–TD-22 precedent of documenting implementation-time decisions the planning docs didn't fix precisely enough to derive without a real choice.
- If implementation reveals any other planning document was wrong or incomplete, update it in the same PR per `AGENTS.md` § Documentation Update Policy. Do not duplicate documentation into a new file — link to it.

## Milestone Boundary

Implement ONLY this milestone. Do not implement work belonging to any other milestone, even if it seems convenient or clearly needed soon. If, during implementation, you discover that another milestone's work is genuinely required to complete this one, stop and explain why before writing that code — do not silently expand scope.

This applies concretely to M6's already-implemented `ListRecordingsUseCase`: build on it as it exists today (extending only if T-071's DoD genuinely requires it); do not modify M6's recording start/stop/worker code to suit this milestone's convenience without first confirming the change is necessary.

## Required Pre-Implementation Output

Before writing any code, produce:

- **M6-precondition check** — confirm, against the working tree at execution time, that `SqlRecordingRepository`, `Recording`, `ListRecordingsUseCase`, and `backend/app/interfaces/api/recordings.py`'s existing routes still exist as described in Context above. Expected: yes — but this is a live check against the actual working tree, not an assumption carried over from this prompt.
- **Implementation Plan** — describe: the exact playback route path and how it serves range requests (the specific mechanism chosen and why); how the recording id in the URL is resolved to a stored `file_path` via `IRecordingRepository` only; the `RecordingNotFoundError` addition and its exception-handler mapping; what, if anything, T-071's DoD requires beyond the existing pass-through `ListRecordingsUseCase`; and the frontend player/filter component design (what's added to `frontend/src/features/recordings/` and how it composes with the existing `RecordingControl.tsx`).
- **Files to Create** — list every concrete path, including tests.
- **Files to Modify** — list every concrete path, including `TASKS.md` and `README.md`.
- **Risks** — address: performance/correctness of range-serving a large MP4 file; a `Recording` row whose underlying file is missing/deleted from disk (DB row present, file absent); and playback of a camera's recordings while that camera is actively recording or live-streaming (concurrent read access to files/state introduced by M5/M6).
- **Assumptions** — state only assumptions confirmed by the consulted documentation and current code. `IRecordingRepository`/`Recording`'s M1-fixed shape and `ListRecordingsUseCase`'s M6-built pass-through logic should be treated as given unless the plan identifies and justifies a specific extension need; the playback route's exact shape is genuinely undefined upstream and must be treated as a real decision to make and document, not re-derived from a document that doesn't specify it.

This plan is produced first. Implementation proceeds only after it — and, if this is running interactively, only after the human reviewing it has had the chance to object, unless the human has explicitly asked for autonomous execution without a pause.

## Required Closing Report

On completion, produce:

- **Summary of Implementation**
- **Acceptance Criteria Satisfied** — check each exact item in the Acceptance Criteria section above.
- **Tradeoffs**
- **New Technical Decisions** — identify each one (the playback route shape/range-serving mechanism and `RecordingNotFoundError`, at minimum) and confirm its corresponding `docs/TECHNICAL_DECISIONS.md` entry was added in the same PR.
- **Suggested Commit Message** — `Implement recording playback with HTTP range requests (T-070, T-071, T-072)`.
- **Suggested PR Title** — `M7: Playback`.
