# M4 — ONVIF Camera Configuration: Implementation Plan & Report

> Companion to [`03-camera-configuration-run.md`](./03-camera-configuration-run.md) (the prompt that was executed). This file records the pre-implementation plan that was produced and reviewed before coding, and the closing report produced after implementation and verification. Scope: Epic M4 in `docs/TASK_BACKLOG.md` — T-040 (`GetVideoEncoderConfiguration(s)` mapping), T-041 (`SetVideoEncoderConfiguration` with capability-aware field filtering), T-042 (`GET`/`PATCH /cameras/{id}/config`), T-043 (frontend config panel).

---

## Part 1 — Implementation Plan (pre-code)

### How a request flows end-to-end

1. **`GET /cameras/{id}/config?profile_id=...`** — router calls `GetCameraConfigUseCase`, which loads the persisted `Camera` (404 via `CameraNotFoundError` if missing, likewise if `profile_id` doesn't match any persisted profile's `onvif_token`), connects `ICameraGateway` with the camera's decrypted stored credentials, and calls two live ONVIF reads: `get_video_encoder_configuration` (T-040, resolution/fps/bitrate/codec) and `get_video_encoder_configuration_options` (camera-reported capability ranges), disconnecting in a `finally`. No data comes from `Camera.stream_profiles`.
2. **`PATCH /cameras/{id}/config?profile_id=...`** — router builds a partial `CameraConfigUpdate` DTO from the request body and calls `UpdateCameraConfigUseCase`, which loads the camera, connects, reads the *current* live config, merges requested fields onto it into a full `StreamProfile` (ONVIF's `SetVideoEncoderConfiguration` requires a full config object, not a delta), and calls `set_video_encoder_configuration`. That gateway method internally re-fetches the raw config + capability options, validates the requested values against them (rejecting a codec change or an out-of-range value as `UnsupportedConfigurationError`, never silently ignoring), mutates only the changed fields on the *raw* ONVIF object (preserving `Multicast`/`SessionTimeout`/etc. it doesn't understand, so nothing camera-required gets clobbered), and calls the SOAP `SetVideoEncoderConfiguration`. Any camera-side rejection is also mapped to `UnsupportedConfigurationError`, never a raw SOAP fault.
3. The use case then re-reads the profile live, updates the persisted `Camera.stream_profiles` entry, and persists via `ICameraRepository.update`. Because GET is always live, the next GET naturally reflects the change — no cache to invalidate.

### Key design decision

`ICameraGateway`'s four listed contracts fit almost entirely as-is (`get_video_encoder_configuration`/`set_video_encoder_configuration` already take/return `StreamProfile` and address by `profile_id`, matching the persisted `onvif_token`). The one gap: T-043 requires the frontend edit form to be *limited to supported fields*, which needs capability data (supported resolutions, fps range, bitrate range) surfaced through the API — data no existing port method returns.

Rather than working around this, one small **additive** port method was added: `ICameraGateway.get_video_encoder_configuration_options(profile_id) -> VideoEncoderCapabilities` (new domain value object), following the same additive-extension precedent TD-18 set for M3. Recorded as `docs/TECHNICAL_DECISIONS.md` TD-19. Codec itself is treated as **read-only** (not offered as editable) — ONVIF's `VideoEncoderConfigurationOptions` doesn't cleanly assert "can this config be switched to codec X," and per TD-18's own precedent this system doesn't guess-map that. A PATCH attempting to change codec is exactly the "unsupported field" test case.

### Files to Create

- `backend/app/domain/value_objects/video_encoder_capabilities.py` — `VideoEncoderCapabilities` (codec, resolutions, fps range, optional bitrate range)
- `backend/tests/unit/domain/test_video_encoder_capabilities.py`
- `backend/app/application/dto/__init__.py`, `backend/app/application/dto/camera_config.py` — `CameraConfigUpdate` (partial patch), `CameraConfigDTO` (profile + capabilities)
- `backend/app/application/use_cases/get_camera_config.py` — `GetCameraConfigUseCase`
- `backend/app/infrastructure/onvif/encoder_config.py` — mapping (`GetVideoEncoderConfiguration(s)` → `StreamProfile`, `Options` → `VideoEncoderCapabilities`), validation, raw-config mutation, profile→config-token resolution
- `backend/tests/unit/infrastructure/test_encoder_config.py`
- `backend/tests/unit/application/test_get_camera_config.py`, `test_update_camera_config.py`
- `backend/tests/integration/onvif/test_camera_config_integration.py` (use-case level, real gateway+fixture+SQL repo)
- `backend/tests/integration/onvif/test_camera_config_api_integration.py` — the two required AC tests, through the real FastAPI router via `httpx.AsyncClient`
- `backend/tests/integration/onvif/test_camera_config_hardware.py` — `@pytest.mark.hardware`, edits a real supported field, confirms reflected (T-043's hardware DoD)
- `backend/tests/fixtures/onvif/video_encoder_configurations.json`, `video_encoder_configuration_options.json`
- `frontend/src/features/camera-onboarding/ConfigPanel.tsx`

### Files to Modify

- `backend/app/application/ports/camera_gateway.py` — add `get_video_encoder_configuration_options`
- `backend/app/infrastructure/onvif/onvif_camera_gateway.py` — implement all three encoder-config methods
- `backend/app/application/use_cases/update_camera_config.py` — complete `execute()`, change third param to `CameraConfigUpdate`
- `backend/app/interfaces/api/cameras.py` — add `GET`/`PATCH /cameras/{id}/config`
- `backend/app/interfaces/schemas/camera.py` — add config request/response schemas; add `onvif_token` to `StreamProfileResponse` (frontend needs it to address a profile)
- `backend/app/core/container.py`, `backend/app/main.py` — wire the two new use cases
- `backend/tests/fixtures/onvif/fake_camera.py`, `profiles.json` — extend fake to be stateful (`GetVideoEncoderConfiguration(s)`, `GetVideoEncoderConfigurationOptions`, `SetVideoEncoderConfiguration` that actually mutates); add config tokens
- `backend/tests/unit/application/test_onboard_camera.py` — its hand-written `FakeCameraGateway` must implement the new abstract port method or it'll fail to instantiate
- `frontend/src/services/camerasApi.ts`, `frontend/src/types/camera.ts` — config GET/PATCH client + types
- `frontend/src/features/camera-onboarding/CameraList.tsx` — wire in `ConfigPanel`
- `docs/TECHNICAL_DECISIONS.md` — new TD-19 entry for the port addition
- `TASKS.md` — move M4 line to In Progress now, Completed at the end

### Risks

- **No physical camera available this session** — all non-hardware tests run against the fixture-driven fake, same approach TD-18 established for M3; the `@pytest.mark.hardware` test is written but skipped.
- **Vendor-specific ONVIF quirks** — `H264Options`'s `BitrateRange` only exists in the v1.2 `Extension` block; some cameras won't report it. Handled by treating a missing bitrate range as "no pre-validation bound, defer to the camera's own Set-time rejection" rather than guessing a bound.
- **Reporting persisted data as live** — mitigated structurally: `GetCameraConfigUseCase` never reads `Camera.stream_profiles` for the returned values, only for validating that `profile_id` belongs to this camera before doing the live ONVIF calls.
- **TD-18's `"3"`-codec finding** — if `GetVideoEncoderConfiguration` reports an unrecognized encoding, `UnsupportedConfigurationError` is raised rather than guess-mapping it, consistent with TD-18.

### Assumptions

- `profile_id` is a required query parameter (not a path segment), matching the AC's literal `GET/PATCH /cameras/{id}/config` shape.
- No cached-read query param is being added — the AC phrases it as a permitted exception ("unless explicitly requested via a query param"), not a requirement, and no backlog task asks for it.
- Persistence and domain-entity/repository schemas need no changes — `StreamProfile`'s existing fields already round-trip through `SqlCameraRepository` unchanged.

---

## Part 2 — Closing Report (post-implementation)

### Summary of Implementation

`GetVideoEncoderConfiguration(s)` and `SetVideoEncoderConfiguration` are wired into `OnvifCameraGateway` via a new `backend/app/infrastructure/onvif/encoder_config.py` module that resolves a profile's own ONVIF token to its video-encoder-configuration token, maps live SOAP responses to/from `StreamProfile`, and validates PATCH requests against camera-reported capability ranges (`GetVideoEncoderConfigurationOptions`). `GetCameraConfigUseCase` (new) and `UpdateCameraConfigUseCase` (completed) sit behind `GET`/`PATCH /cameras/{id}/config`, and a `ConfigPanel.tsx` frontend component displays current values and edits only camera-supported fields.

### Acceptance Criteria Satisfied

- **`GET /cameras/{id}/config` returns resolution/FPS/bitrate/codec sourced live from the camera** — `GetCameraConfigUseCase` never reads `Camera.stream_profiles`; every field comes from a fresh `get_video_encoder_configuration` ONVIF call. Verified in `test_camera_config_integration.py` and `test_camera_config_api_integration.py`.
- **`PATCH` with a supported change is reflected on a subsequent `GET`** — verified end-to-end through the real FastAPI router in `test_patch_supported_field_reflected_on_next_get`, and at the use-case/persistence level in `test_patch_supported_bitrate_is_reflected_on_next_get_and_persists`.
- **`PATCH` with an unsupported field/value returns a typed 4xx, never silently ignored** — verified via `test_patch_unsupported_field_returns_typed_4xx_not_silently_ignored` (HTTP layer, codec change → 422) plus resolution/bitrate-out-of-range cases at the integration level; camera-side SOAP rejections are also mapped, never left as a raw fault.

Matching Task Backlog DoDs (resolution/FPS/bitrate/codec read correctly; unsupported field → typed 4xx not raw SOAP fault; PATCH reflected on next GET; hardware test edits a real supported field) are all met — the last one via `test_camera_config_hardware.py`, `@pytest.mark.hardware`-gated and skipped in CI pending the physical camera.

### Tradeoffs

- **Codec is read-only** — ONVIF's options response never asserts whether a config can switch codecs, so a codec-change PATCH is always rejected rather than guessed at (see TD-19). This also serves as the deterministic "unsupported field" test case.
- **No cached-read query param** — the AC phrases it as a permitted exception, not a requirement; no backlog task asked for it, so GET is always live.
- **`GetVideoEncoderConfigurationOptions` is fetched twice across a GET→PATCH cycle** (once for the GET response, once inside `set_video_encoder_configuration`'s own server-side validation) rather than threading a single value through — keeps the Set path safe to call independently and never trusting a possibly-stale caller-supplied capability snapshot.
- **Full browser verification of `ConfigPanel` wasn't possible** — no physical or fixture-backed camera is reachable from the dev server in this session (same constraint M3 documented). Confirmed the app boots cleanly with no console errors; the GET/PATCH flow itself is covered by the API-level integration tests instead.

### New Technical Decisions

**TD-19** (`docs/TECHNICAL_DECISIONS.md`): the additive `ICameraGateway.get_video_encoder_configuration_options` port method + `VideoEncoderCapabilities` value object, and the codec-as-read-only policy.

### Files Changed

**Created**:
- `backend/app/domain/value_objects/video_encoder_capabilities.py`
- `backend/app/application/dto/__init__.py`, `backend/app/application/dto/camera_config.py`
- `backend/app/application/use_cases/get_camera_config.py`
- `backend/app/infrastructure/onvif/encoder_config.py`
- `backend/tests/unit/domain/test_video_encoder_capabilities.py`
- `backend/tests/unit/infrastructure/test_encoder_config.py`
- `backend/tests/unit/application/test_get_camera_config.py`
- `backend/tests/unit/application/test_update_camera_config.py`
- `backend/tests/integration/onvif/test_camera_config_integration.py`
- `backend/tests/integration/onvif/test_camera_config_api_integration.py`
- `backend/tests/integration/onvif/test_camera_config_hardware.py`
- `backend/tests/fixtures/onvif/video_encoder_configurations.json`
- `backend/tests/fixtures/onvif/video_encoder_configuration_options.json`
- `frontend/src/features/camera-onboarding/ConfigPanel.tsx`

**Modified**:
- `backend/app/application/ports/camera_gateway.py`
- `backend/app/application/use_cases/update_camera_config.py`
- `backend/app/infrastructure/onvif/onvif_camera_gateway.py`
- `backend/app/interfaces/api/cameras.py`
- `backend/app/interfaces/schemas/camera.py`
- `backend/app/core/container.py`
- `backend/app/main.py`
- `backend/tests/fixtures/onvif/fake_camera.py`
- `backend/tests/fixtures/onvif/profiles.json`
- `backend/tests/unit/application/test_onboard_camera.py`
- `frontend/src/services/camerasApi.ts`
- `frontend/src/types/camera.ts`
- `frontend/src/features/camera-onboarding/CameraList.tsx`
- `docs/TECHNICAL_DECISIONS.md`
- `TASKS.md`

### Tests Executed

`ruff check`, `black --check`, `mypy --strict`, `lint-imports` (layering contract kept), `pytest` — 133 passed / 2 hardware-gated deselected, 100% domain-layer coverage maintained. Frontend: `tsc -b` (clean) and `oxlint` (clean). Backend + frontend dev servers smoke-tested; no console errors on load.

**Note**: `frontend/src/App.tsx` was already modified (uncommitted) and `storage/` already present (untracked) before this session started — neither was touched by this work and neither is staged.

### Suggested Commit Message

`Implement ONVIF camera configuration (T-040, T-041, T-042, T-043)`

### Suggested PR Title

`M4: ONVIF Camera Configuration`
