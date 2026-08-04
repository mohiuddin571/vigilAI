# Implementation Prompt: ONVIF Camera Onboarding (M3)

## Context

Authenticate to an ONVIF camera using IP + username + password, read its device identity and media profiles, and persist the onboarded camera so it survives an API restart. This is the first milestone to touch real infrastructure — it depends only on M1 (the domain entities and ports already exist and are unchanged) and is explicitly independent of M2 (`docs/IMPLEMENTATION_PLAN.md` §M3 "Dependencies: M1... Independent of M2 — can be built in parallel if needed"). ONVIF here is strictly a configuration/control-plane concern: it never touches pixels or streaming (`docs/ARCHITECTURE.md` §5).

## Documents Consulted

- `AGENTS.md` (full)
- `TASKS.md` (full, current state)
- `docs/IMPLEMENTATION_PLAN.md` §M3
- `docs/TASK_BACKLOG.md` — Epic M3 — ONVIF Onboarding (T-030–T-037)
- `docs/TECHNICAL_DECISIONS.md` TD-03 (ONVIF client library), TD-15 (credential handling), TD-09 (persistence — consulted because M3's own acceptance criteria requires persistence though `docs/IMPLEMENTATION_PLAN.md`'s M3 "Files" list doesn't name it), TD-08 (composition-root DI, for wiring the new adapter)
- `docs/ARCHITECTURE.md` §6.1 (Camera Onboarding & Configuration flow), §7 (Error Handling — typed exceptions map to HTTP status in the FastAPI exception-handler layer)
- **Current repository state**, inspected directly since it's more authoritative than planning docs for "what already exists": `backend/app/application/ports/camera_gateway.py`, `camera_repository.py`, `backend/app/application/use_cases/onboard_camera.py`, `backend/app/domain/entities/camera.py`, `stream_profile.py`, `backend/app/domain/exceptions.py`, `backend/app/core/config.py`, `container.py`, `main.py`, `backend/pyproject.toml`, and the current (near-empty) `backend/app/interfaces/`, `backend/app/infrastructure/`, and `frontend/src/` trees.

## Scope

All tasks under Epic M3 in `docs/TASK_BACKLOG.md`: T-030 (integrate `onvif-zeep-async`, connect + auth), T-031 (`GetDeviceInformation` → `Camera`), T-032 (`GetProfiles` → `StreamProfile`s), T-033 (`OnboardCameraUseCase` full implementation), T-034 (`POST /cameras`, `GET /cameras`, `GET /cameras/{id}` endpoints + schemas), T-035 (credential-at-rest encryption, P1), T-036 (frontend "Add Camera" form), T-037 (ONVIF SOAP fixture capture for offline/CI testing, P1).

Full Definition of Done for each task ID is in `docs/TASK_BACKLOG.md` — do not re-derive it from this prompt; look it up there. T-035 and T-037 are P1 ("can slip briefly" per the priority key) — within this same PR they may be sequenced last, but they stay in this PR, not a separate one (`AGENTS.md` § Pull Request Guidelines: one milestone per PR). T-035 being P1 governs *sequencing*, not whether plaintext passwords are ever acceptable even temporarily — they are not (TD-15 explicitly rejects plaintext storage outright, "even in a take-home project"); do not persist a camera's password unencrypted at any point, even as a to-be-fixed-later shortcut.

## Out of Scope

- Encoder configuration read/update (`GetVideoEncoderConfiguration`, `SetVideoEncoderConfiguration`, `PATCH /cameras/{id}/config`) — that is M4.
- Resolving `GetStreamUri` for actual RTSP playback — that is M5 (`OnvifRtspFrameSource`; per `docs/IMPLEMENTATION_PLAN.md` §M5's own Dependencies line: "M2 (shared decode path), M3/M4 (for `GetStreamUri`)").
- WS-Discovery / network-scan onboarding — TD-03 explicitly names this a future enhancement, not part of this milestone, regardless of what this template's filename (`02-onvif-camera-discovery.md`) suggests (see the naming note at the top of `prompts/02-onvif-camera-discovery.md`).
- Anything from M2 (frame source abstraction) — independent of this milestone, not a prerequisite, not to be pulled forward.
- Anything from M5 onward (live streaming, recording, playback, analytics).

## Acceptance Criteria

Copied verbatim from `docs/IMPLEMENTATION_PLAN.md` §M3:

- Against the evaluator's physical camera (or, until it's available, an ONVIF camera simulator / recorded SOAP fixtures), `POST /cameras` with valid IP/username/password returns `201` with device info and at least one media profile.
- Invalid credentials return a clear `4xx` with a typed error, not a stack trace.
- Onboarding is persisted and survives an API restart (`GET /cameras` lists it).

## Constraints

From the milestone template:
- Follow the Dependency Direction Rule — `OnboardCameraUseCase` (already exists at `backend/app/application/use_cases/onboard_camera.py`) depends on `ICameraGateway` and `ICameraRepository` only, never on `onvif-zeep-async` or a concrete repository directly.
- Camera passwords must never be logged or returned in an API response after creation (TD-15; also `AGENTS.md` § Things AI Must Never Do).
- Invalid credentials / unreachable host must produce a typed exception → clear `4xx`, never a raw SOAP fault or stack trace leaking to the client. `docs/ARCHITECTURE.md` §7 places this translation in the FastAPI exception-handler layer — `backend/app/core/exception_handlers.py` does not exist in the repository yet, and neither M0 nor M1's "Files" lists in `docs/IMPLEMENTATION_PLAN.md` included it (there was nothing to map yet, since M1's use cases are stub-only); this is the milestone that creates it.

Dependency additions, both already pre-approved — adding them does **not** require a new `docs/TECHNICAL_DECISIONS.md` entry, only implementing what's already decided:
- `onvif-zeep-async` — pre-approved by TD-03.
- SQLModel + a SQLite driver — pre-approved by TD-09. A new entry *is* required only if implementation has to deviate from what TD-03 or TD-09 already committed to (e.g. a different ONVIF library, a different persistence approach).

Architectural mechanic this milestone must handle correctly: `ICameraGateway` (`backend/app/application/ports/camera_gateway.py`) is an ABC with six abstract methods. `OnvifCameraGateway` must implement all six to be instantiable — Python will not allow a partially-implemented ABC subclass to be constructed. Only `connect`, `get_device_info`, and `get_profiles` have real logic in this milestone (per `docs/IMPLEMENTATION_PLAN.md` §M3's own Deliverables). Give `set_video_encoder_configuration` (real logic belongs to M4) and `get_stream_uri` (real logic belongs to M5) `raise NotImplementedError` stub bodies, mirroring the pattern M1 already established for use-case skeletons — do not implement their real logic now, and do not leave `OnvifCameraGateway` abstract/uninstantiable.

**Clarification — `get_video_encoder_configuration` is a narrower case than the other two stubs**: `StreamProfile`'s `resolution`, `codec`, `bitrate`, and `fps` fields (`backend/app/domain/entities/stream_profile.py`) have no defaults — `get_profiles()` cannot construct a valid `StreamProfile` without real encoder values, and `docs/ARCHITECTURE.md` §6.1's sequence diagram confirms this: it shows the onboarding flow's `GetProfiles` call returning "profiles, resolution, fps, bitrate, codec" together. So `get_profiles()`'s M3 implementation must extract encoder configuration from the ONVIF `GetProfiles` response itself and populate `StreamProfile` fully — that is real M3 logic, not deferred. What stays a stub is only the *separate* `get_video_encoder_configuration(profile_id)` method — the on-demand, single-profile re-query `docs/IMPLEMENTATION_PLAN.md` §M4 adds for `GET /cameras/{id}/config`'s "not cached stale data" requirement. Do not leave `StreamProfile` objects with placeholder/default encoder values after `get_profiles()` — that would fail M3's own acceptance criteria (a `StreamProfile` can't even be constructed that way).

## Deliverables

From `docs/IMPLEMENTATION_PLAN.md` §M3 "Files", resolved against the current repository:

- `backend/app/infrastructure/onvif/` (new) — `OnvifCameraGateway` implementing `ICameraGateway`, per the Constraints note above.
- `backend/app/interfaces/api/cameras.py` (new) — `POST /cameras`, `GET /cameras`, `GET /cameras/{id}`.
- `backend/app/interfaces/schemas/camera.py` (new) — Pydantic request/response models; the response schema must not include the password field.
- `frontend/src/features/camera-onboarding/` (new) — "Add Camera" form. `frontend/src/` currently has no subfolders beyond the M0 skeleton (`App.tsx`, `main.tsx`, `index.css`); this milestone is the first to populate `features/`, and any supporting `services/`/`types/` files it needs. Decide the exact internal file layout in the Required Pre-Implementation Output below.

Required but **not named** in `docs/IMPLEMENTATION_PLAN.md` §M3's "Files" list — each is a genuine gap between that list and M3's own Acceptance Criteria or Constraints, flagged rather than silently added or silently skipped:

- **Persistence** — AC #3 ("Onboarding is persisted and survives an API restart") cannot be met without a concrete `ICameraRepository` implementation and real storage; no `backend/app/infrastructure/persistence/` exists yet, and no SQL dependency is in `backend/pyproject.toml` yet. Build the minimal `SqlCameraRepository` (SQLModel/SQLite, per TD-09) needed to satisfy AC #3 — not a general-purpose persistence layer for entities this milestone doesn't need.
- **Credential storage** — `Camera` (`backend/app/domain/entities/camera.py`) currently has no password field, and `ICameraRepository`'s four methods (`add`/`get`/`list`/`update`) only take `Camera`. Where the encrypted password actually lives (a field on `Camera` excluded from API responses at the schema layer, vs. a separate credential store keyed by camera ID) is not decided by any existing code or document. Decide this in the Required Pre-Implementation Output below — do not guess silently.
- **Encryption key config** — TD-15 says the encryption key comes from environment config; `Settings` (`backend/app/core/config.py`) has no such field today. Add one.
- **`backend/app/core/exception_handlers.py`** — see Constraints above; new in this milestone.
- **`backend/app/main.py`** (modify) — register the cameras router and the new exception handlers; currently has neither.
- **`backend/app/core/container.py`** (modify) — currently an empty stub whose docstring says "there are no concrete infrastructure adapters yet (those start at M2/M3)." Add the `build_*` wiring for `OnvifCameraGateway`, the new repository, and `OnboardCameraUseCase`, and update that docstring — it goes stale the moment this milestone lands.
- **`backend/pyproject.toml`** (modify) — add `onvif-zeep-async` and the SQLModel/SQLite dependencies.
- **`.env.example`** (modify) — document the new encryption-key setting. (`.env` itself is gitignored — a local, untracked file, not a repository deliverable; each developer sets their own value there.)

## Testing Expectations

Per the milestone template and `AGENTS.md` § Testing Expectations:
- Integration tests run by default against a mock SOAP server or recorded ONVIF fixtures (T-037) — CI must not require the physical camera.
- Anything requiring the real evaluator-provided camera is marked `@pytest.mark.hardware` and skipped in CI.
- T-033's Definition of Done requires an integration test that onboards a fixture/simulated camera end-to-end — this is the test that also proves AC #3 (persists across restart), so it should exercise the real repository, not a fake.
- Unit-test the new exception-handler mapping (invalid credentials → typed exception → `4xx`) without needing a real or simulated camera.

## Documentation Update Requirements

- **`TASKS.md`**: the current `# In Progress` line reads `- [ ] _Nothing yet — no application code beyond M0/M1 exists. Next up: Video Source Abstraction (M2)._` — this is stale the moment work starts here, since M3 is being started instead of/alongside M2. Replace it with `- [ ] ONVIF Camera Onboarding — IP + credential authentication (M3)` (moved from `# Remaining`), and note in the commit or PR description that this is legitimate per `docs/IMPLEMENTATION_PLAN.md` §M3's explicit "Independent of M2" dependency note, not a deviation from plan. Once all acceptance criteria above are met, move the line to `# Completed`.
- **`README.md`**: update only if this milestone changes user-visible setup — likely yes, since a new environment variable (the encryption key) becomes required; add it to `.env.example`'s documented settings and to README's Configuration section if that section enumerates required variables.
- **`docs/` architecture documents**: update only if implementation reveals one was wrong (`AGENTS.md` § Documentation Update Policy). Two likely candidates given the gaps identified above: `docs/IMPLEMENTATION_PLAN.md` §M3's "Files" list is incomplete (missing persistence, exception handlers, container/main wiring) — consider fixing it in this PR so the next reader doesn't hit the same gap; and if the credential-storage design decision (above) is non-obvious, it may warrant its own `docs/TECHNICAL_DECISIONS.md` entry.

## Milestone Boundary

Implement ONLY this milestone. Do not implement work belonging to any other milestone, even if it seems convenient or clearly needed soon. If, during implementation, you discover that another milestone's work is genuinely required to complete this one, stop and explain why before writing that code — do not silently expand scope.

## Required Pre-Implementation Output

Before writing any code, produce:

- **Implementation Plan** — the approach, including how the flagged gaps above are resolved: exact persistence approach (`SqlCameraRepository` schema), exact credential-storage design (where the encrypted password lives), the new `Settings` field name/type for the encryption key, and the internal layout of `frontend/src/features/camera-onboarding/`.
- **Files to Create** — the complete concrete file list, replacing every folder-level reference above with actual file paths and names.
- **Files to Modify** — expected to include `backend/app/main.py`, `backend/app/core/container.py`, `backend/pyproject.toml`, `.env.example`, `TASKS.md`, and possibly `README.md` and `docs/IMPLEMENTATION_PLAN.md` per Documentation Update Requirements; list anything else identified.
- **Risks** — explicitly address: what happens if the evaluator's physical camera isn't available during this work (mock/fixture-based development per T-037); what happens if the camera's ONVIF version has quirks TD-03 didn't anticipate.
- **Assumptions** — explicitly include the credential-storage design decision (from Deliverables above) and the `ICameraGateway` ABC-completeness handling (stub bodies for M4/M5 methods, from Constraints above), so they're visible as deliberate calls, not oversights.

This plan is produced first. Implementation proceeds only after it — and, if this is running interactively, only after the human reviewing it has had the chance to object, unless the human has explicitly asked for autonomous execution without a pause.

## Required Closing Report

On completion, produce:

- **Summary of Implementation**
- **Acceptance Criteria Satisfied** — checked off against the exact list in the Acceptance Criteria section above.
- **Tradeoffs**
- **New Technical Decisions** — if the credential-storage design or any other real decision was made beyond what TD-03/TD-09/TD-15 already specify, add a corresponding `docs/TECHNICAL_DECISIONS.md` entry in this same PR, not just a mention in the closing report.
- **Suggested Commit Message** — imperative mood, referencing the relevant `docs/TASK_BACKLOG.md` task ID(s) from Scope above, per `AGENTS.md` § Commit Message Conventions.
- **Suggested PR Title** — `M3: ONVIF Camera Onboarding`, per `prompts/02-onvif-camera-discovery.md`.
