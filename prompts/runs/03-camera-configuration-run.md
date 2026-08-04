# Implementation Prompt: ONVIF Camera Configuration (M4; T-040–T-043)

## Context

Implement M4: read the live video-encoder configuration of an already onboarded ONVIF camera and update only camera-supported resolution, FPS, bitrate, and codec values. M4 depends on M3, which is present in the current working tree: camera credentials and ONVIF profile tokens are persisted, `OnvifCameraGateway` has M4 method stubs, and the camera onboarding UI/API already exist. This work is the ONVIF configuration/control plane only; live RTSP streaming is M5.

## Documents Consulted

- `AGENTS.md` (full)
- `TASKS.md` (full; current state)
- `docs/AI_PROJECT_CONTEXT.md` (full; especially §§2, 5–8)
- `docs/ARCHITECTURE.md` (full; especially §§5, 6.1, and 7)
- `docs/FOLDER_STRUCTURE.md` (full; especially the layer ownership and Dependency Direction Rule)
- `docs/IMPLEMENTATION_PLAN.md` (full; especially §M4)
- `docs/PROMPTING_GUIDE.md` (full)
- `docs/TASK_BACKLOG.md` (full; especially Epic M4)
- `docs/TECHNICAL_DECISIONS.md` (full; especially TD-01, TD-03, TD-08, TD-09, TD-13, TD-15, and TD-18)
- `prompts/00-README.md` (full)
- `prompts/03-camera-configuration.md` (full)
- Current M3 implementation relevant to this milestone: `backend/app/application/ports/camera_gateway.py`, `backend/app/application/ports/camera_repository.py`, `backend/app/application/use_cases/update_camera_config.py`, `backend/app/infrastructure/onvif/onvif_camera_gateway.py`, `backend/app/infrastructure/onvif/mappers.py`, `backend/app/infrastructure/persistence/sql_camera_repository.py`, `backend/app/interfaces/api/cameras.py`, `backend/app/interfaces/schemas/camera.py`, `backend/app/core/container.py`, `frontend/src/features/camera-onboarding/`, `frontend/src/services/camerasApi.ts`, and `frontend/src/types/camera.ts`.

## Scope

Implement all Epic M4 tasks in `docs/TASK_BACKLOG.md`:

- T-040 — `GetVideoEncoderConfiguration(s)` mapping.
- T-041 — `SetVideoEncoderConfiguration` with capability-aware field filtering.
- T-042 — `GET /cameras/{id}/config` and `PATCH /cameras/{id}/config`.
- T-043 — frontend config panel that views and edits only capability-supported fields.

Use the current `ICameraGateway`, `ICameraRepository`, `Camera`, and `StreamProfile` contracts as the starting point. Verify that the existing contracts fit before coding. If a necessary change to one of those contracts is not cleanly supported by the documented design, stop and propose the smallest documented change instead of working around it.

## Out of Scope

- M2 frame-source abstraction and MP4 source work.
- M5 work, including `GetStreamUri`, RTSP frame sources, browser live view, and reconnect/backoff.
- M6 onward: recording, playback, analytics, Docker, or demo preparation.
- WS-Discovery/network-scan onboarding; TD-03 identifies it as a future enhancement.
- Changes to camera onboarding other than the minimal integration needed to read/update a persisted onboarded camera's encoder configuration.
- User authentication, RBAC, multi-tenancy, cloud storage, message brokers, mobile applications, and alerting integrations, which are explicit non-goals in `docs/AI_PROJECT_CONTEXT.md` §7.

## Acceptance Criteria

Copied verbatim from `docs/IMPLEMENTATION_PLAN.md` §M4:

- `GET /cameras/{id}/config` returns resolution, FPS, bitrate, and codec sourced live from the camera (not cached stale data, unless explicitly requested via a query param).
- `PATCH` with a supported change is reflected on a subsequent `GET`.
- `PATCH` with an unsupported field/value returns a typed `4xx`, never silently ignored.

Matching Definition of Done statements copied verbatim from `docs/TASK_BACKLOG.md` Epic M4:

- Resolution/FPS/bitrate/codec read correctly.
- Attempting an unsupported field returns typed 4xx, not a raw SOAP fault.
- PATCH result reflected on next GET.
- Editing a real supported field updates the physical camera.

## Constraints

- Follow the Dependency Direction Rule in `docs/FOLDER_STRUCTURE.md`. `UpdateCameraConfigUseCase` must depend on `ICameraGateway` and `ICameraRepository`, never a concrete ONVIF gateway, repository, FastAPI router, or frontend type. `interfaces/` calls application use cases only; `core/` remains the sole composition root.
- Use `onvif-zeep-async` as decided by TD-03. Do not add a dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR. Do not replace an already decided technology without an updated decision entry.
- All configuration remains in the single `Settings` object; do not read `os.environ` outside `backend/app/core/config.py`. Use structured logging and do not log camera passwords.
- Only expose fields the camera's own ONVIF profile reports as configurable. Never assume a field is writable. An unsupported field or value must surface as `UnsupportedConfigurationError` through the existing typed-exception HTTP mapping, not be silently discarded or passed through as a raw SOAP fault.
- `GET /cameras/{id}/config` must perform the live ONVIF read required by the first acceptance criterion. Do not satisfy it from `Camera.stream_profiles` or other persisted configuration state.
- Preserve M3's credential-at-rest behavior from TD-15 and TD-18. Reuse the persisted camera's encrypted credentials through the repository boundary; do not introduce plaintext persistence, response fields, or logging.
- TD-18 records an evaluator-camera finding where the ONVIF encoder value was the literal string `"3"`. Do not guess-map that value to `H264`; first confirm it through the camera/vendor documentation or `GetVideoEncoderConfigurationOptions`, as TD-18 requires.
- Keep ONVIF as configuration/control-plane work. Do not implement pixel decoding, RTSP handling, or analytics imports in this milestone.
- Use Pydantic validation at the HTTP boundary and keep API schemas separate from application DTOs and domain entities, per `docs/FOLDER_STRUCTURE.md` and `docs/PROMPTING_GUIDE.md` §5.

## Deliverables

Implement the M4 deliverables from `docs/IMPLEMENTATION_PLAN.md` §M4 at these paths:

- `backend/app/infrastructure/onvif/encoder_config.py` — ONVIF video-encoder configuration read/update and capability mapping used by `OnvifCameraGateway`.
- `backend/app/application/use_cases/update_camera_config.py` — the completed `UpdateCameraConfigUseCase`.
- `backend/app/interfaces/api/cameras.py` — `GET /cameras/{id}/config` and `PATCH /cameras/{id}/config` routes integrated with the existing camera router.
- `frontend/src/features/camera-onboarding/ConfigPanel.tsx` — current configuration display and edit form limited to supported fields.

Modify the existing gateway, composition root, schemas, frontend API client/types, camera feature composition, persistence implementation, and test fixtures only where required to wire these deliverables and make the acceptance criteria pass. Resolve the exact additional paths in the required pre-implementation plan; do not create files for another milestone.

## Testing Expectations

- Add a test that asserts `PATCH` of a supported field is reflected on the next `GET`.
- Add a test that asserts `PATCH` of an unsupported field/value fails cleanly with the typed `4xx` required by the acceptance criteria.
- Unit-test application behavior using fakes for every port, with no real I/O.
- Test the ONVIF adapter and API integration using the committed M3 ONVIF fixture-driven fake (`backend/tests/fixtures/onvif/fake_camera.py`) or an equivalent recorded-fixture extension, so the default suite does not require the physical camera.
- Any test requiring the evaluator-provided physical camera must be marked `@pytest.mark.hardware` and skipped in CI. The hardware test must verify T-043 by editing a real supported field and confirming the camera reflects it.
- Run the repository's configured formatter, linter, type checker, and test suite. Preserve the M0 import-linter guarantee and do not weaken any existing test.

## Documentation Update Requirements

- At the start, move the exact current `TASKS.md` line `- [ ] Camera Configuration — read/update resolution, FPS, bitrate, codec (M4)` from `# Remaining` to `# In Progress`. Once every acceptance criterion is met, move that same line to `# Completed` in the same PR.
- Update `README.md` only if the implementation changes user-visible setup or usage.
- If implementation reveals a planning or architecture document is wrong or incomplete, update the relevant document in `docs/` in the same PR, as required by `AGENTS.md` § Documentation Update Policy. Do not duplicate documentation into a new file.
- If implementation requires a new third-party dependency or a decision not already covered by the technical decisions, add the corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR.

## Milestone Boundary

Implement ONLY this milestone. Do not implement work belonging to any other milestone, even if it seems convenient or clearly needed soon. If, during implementation, you discover that another milestone's work is genuinely required to complete this one, stop and explain why before writing that code — do not silently expand scope.

## Required Pre-Implementation Output

Before writing any code, produce:

- **Implementation Plan** — describe how a request obtains the persisted camera credentials, performs the live ONVIF configuration read, obtains the camera-reported configuration capabilities, validates the PATCH request, applies a supported update, and ensures the following GET is live rather than stale.
- **Files to Create** — list every concrete path, including tests and any fixture changes.
- **Files to Modify** — list every concrete path, including the gateway, use case, router, schemas, composition root, persistence/fixture/frontend integration as applicable, `TASKS.md`, and any documentation required above.
- **Risks** — address the unavailable-hardware path, vendor-specific ONVIF capability/update behavior, and the risk of reporting persisted configuration as a live read.
- **Assumptions** — state only assumptions confirmed by the consulted documentation and current code. If a required capability representation or port/API contract is undefined upstream, identify it as an explicit decision requiring confirmation before implementation rather than inventing it.

This plan is produced first. Implementation proceeds only after it — and, if this is running interactively, only after the human reviewing it has had the chance to object, unless the human has explicitly asked for autonomous execution without a pause.

## Required Closing Report

On completion, produce:

- **Summary of Implementation**
- **Acceptance Criteria Satisfied** — check each exact item in the Acceptance Criteria section above.
- **Tradeoffs**
- **New Technical Decisions** — identify each one and confirm its corresponding `docs/TECHNICAL_DECISIONS.md` entry was added in the same PR, if applicable.
- **Suggested Commit Message** — `Implement ONVIF camera configuration (T-040, T-041, T-042, T-043)`.
- **Suggested PR Title** — `M4: ONVIF Camera Configuration`.
