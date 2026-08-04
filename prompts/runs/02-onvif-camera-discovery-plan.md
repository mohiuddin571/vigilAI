# Implementation Plan: ONVIF Camera Onboarding (M3)

> Companion to [`02-onvif-camera-discovery-run.md`](./02-onvif-camera-discovery-run.md) (the executed prompt). This is the Required Pre-Implementation Output it demands, produced and reviewed before any code was written.

## Implementation Plan

**Flow**: `POST /cameras {ip, port, username, password}` → `OnboardCameraUseCase` → `OnvifCameraGateway.connect()` (WS-Security auth) → `get_device_info()` (`GetDeviceInformation`) → `get_profiles()` (`GetProfiles`, extracting `VideoEncoderConfiguration` per profile) → persist via `SqlCameraRepository` (SQLite, password encrypted at rest) → `201` with `CameraResponse` (no password).

Before writing this plan, the actual `onvif-zeep-async` package was installed in a scratch venv and inspected directly (constructor signature, exception hierarchy, bundled WSDL/XSD schemas) rather than relying on documentation guesses, since correctness here matters for both implementation and mypy.

### Resolved gaps

**1. `ICameraGateway.connect()` needs a `port` parameter.** The M1 signature is `connect(ip_address, username, password)` with no port. ONVIF devices are addressed by `ip:port` (`ONVIFCamera(host, port, user, passwd, ...)` — confirmed from the actual installed package signature). Adding `port: int = 80` to the port method — a minimal, additive fix to a port that was never exercised until now, not a redesign.

**2. `StreamProfile` needs to carry the camera's own profile token.** `ICameraGateway.get_video_encoder_configuration(profile_id: str)`/`get_stream_uri(profile_id: str)` already type `profile_id` as `str` — confirming the intended design is that the *camera's* token (e.g. `"Profile_1"`), not our internal `StreamProfile.id: UUID`, is what M4/M5 will pass back to the gateway. Without capturing it now, M3's own persisted profiles would be permanently unusable by M4/M5. Adding `onvif_token: str | None = None` to `StreamProfile` (optional, so existing tests/construction sites are unaffected).

**3. Credential storage design** (the flagged Deliverables gap): a `password: str = field(default="", repr=False)` field on `Camera` (plaintext in memory only — the same plaintext that arrived in the POST body; `repr=False` so it can never leak via accidental `repr()`/log of a `Camera` object). `ICameraRepository.add`/`update` keep their existing `Camera`-only signature unchanged. **`SqlCameraRepository` is the only place that ever touches ciphertext or the encryption key** — it encrypts on write into its own SQL column, decrypts on read. The API response schema never includes `password`. This is the "field on `Camera`, excluded from API responses at the schema layer" option from the prompt, chosen over a separate credential store because it requires no port-signature change beyond what #1 already does, and keeps the four-method `ICameraRepository` contract exactly as M1 defined it.

Encryption: `cryptography`'s `Fernet` (new dependency — not pre-approved by name in TD-15, which only committed to "a key from environment config," so this gets its own `docs/TECHNICAL_DECISIONS.md` entry), wrapped in `infrastructure/security/CredentialCipher`. New `Settings` field: `camera_credential_encryption_key: str` (required, no default — a baked-in default would defeat TD-15's "key lives only in `.env`" point). `.env.example` documents how to generate one.

**4. Persistence schema.** One `camera` SQLite table (SQLModel), minimal per the prompt's "not a general-purpose persistence layer" instruction: `id, name, ip_address, port, username, encrypted_password, manufacturer, model, firmware_version, is_online, stream_profiles_json`. Stream profiles are stored as a JSON blob column, not a normalized child table — this milestone never queries profiles independently of their camera, so normalizing would be speculative.

**5. Auth-vs-unreachable exception mapping.** Inspecting the actual library source showed its `safe_func` decorator only wraps *synchronous* request construction, not the awaited call — its own code comments confirm operation calls can raise a raw `zeep.exceptions.Fault` directly, and the library's own `ONVIFAuthError` is only raised from its HTTP-snapshot path (401), not from WS-Security SOAP faults. There's no clean library-provided way to distinguish "wrong password" from "other SOAP fault" — different camera vendors phrase WS-Security auth faults differently. New domain exception `CameraAuthenticationError`, classified as: `ONVIFAuthError` → always auth; a `zeep.exceptions.Fault` whose message contains an auth-hint substring (`"notauthorized"`, `"failedauthentication"`, `"unauthorized"`, `"authentication"`) → auth; everything else (`ONVIFError`, `ONVIFTimeoutError`, transport/`OSError`/timeout) → `CameraUnreachableError`. Best-effort heuristic, documented as a tradeoff, not a guarantee for every camera firmware.

**6. `GetProfiles` edge case.** Per the actual ONVIF XSD, both `Profile.VideoEncoderConfiguration` and its nested `RateControl` are optional (`minOccurs="0"`). Since `StreamProfile` requires resolution/codec/bitrate/fps with no defaults, `get_profiles()` skips (with a `structlog` warning) any profile missing either — it cannot fabricate placeholder values, and the Constraints section explicitly forbids that.

**7. Frontend.** `frontend/package.json` doesn't have React Query yet even though TD-12 already committed to it — adding `@tanstack/react-query` now is implementing an already-decided stack piece, not a new decision. Layout:
```
frontend/src/types/camera.ts               — TS types mirroring CameraResponse
frontend/src/services/camerasApi.ts        — fetch wrappers (only fetch/WebSocket call site, per FOLDER_STRUCTURE.md)
frontend/src/features/camera-onboarding/
    AddCameraForm.tsx
    CameraList.tsx
    CameraOnboardingPage.tsx                — composes the two
```
`vite.config.ts` gets a `/cameras` proxy entry alongside the existing `/health` one. `App.tsx` renders `CameraOnboardingPage` below the existing health card (no router needed yet — this is the only feature until M14's nav integration).

**8. T-037 testing strategy.** A full byte-level SOAP/WSDL simulator server is disproportionate for this milestone. Instead: `OnvifCameraGateway` takes an injectable client factory (defaults to the real `ONVIFCamera` constructor); tests inject a fake camera object built from recorded-shape fixture data (`backend/tests/fixtures/onvif/*.json`, mirroring real `GetDeviceInformation`/`GetProfiles` response shapes confirmed against the actual WSDL/XSD). Satisfies T-037's actual DoD ("integration suite runs in CI without a real camera") and the AC's explicit "recorded SOAP fixtures" option, while staying maintainable. Documented as a tradeoff vs. a protocol-level simulator.

**9. CI needs real `Settings`.** No test currently touches `app.core.config`, so CI never needed `ENVIRONMENT` set. Once integration tests build the container, they will. Adding `ENVIRONMENT`/`CAMERA_CREDENTIAL_ENCRYPTION_KEY` env vars to the `Pytest` step of `.github/workflows/ci.yml`, and `-m "not hardware"` to `pytest`'s `addopts` (registering a `hardware` marker) so hardware-gated tests are skipped by default without a CI-side change.

## Files to Create

**Backend**
- `backend/app/application/use_cases/list_cameras.py` — `ListCamerasUseCase`
- `backend/app/application/use_cases/get_camera.py` — `GetCameraUseCase`
- `backend/app/infrastructure/onvif/__init__.py`
- `backend/app/infrastructure/onvif/onvif_camera_gateway.py` — `OnvifCameraGateway`
- `backend/app/infrastructure/onvif/mappers.py` — pure device-info/profile/codec mapping helpers (unit-testable without a live client)
- `backend/app/infrastructure/security/__init__.py`
- `backend/app/infrastructure/security/credential_cipher.py` — `CredentialCipher`
- `backend/app/infrastructure/persistence/__init__.py`
- `backend/app/infrastructure/persistence/database.py` — async engine/session factory, `init_db()`
- `backend/app/infrastructure/persistence/models.py` — `CameraRow` (SQLModel table)
- `backend/app/infrastructure/persistence/sql_camera_repository.py` — `SqlCameraRepository`
- `backend/app/interfaces/schemas/__init__.py`
- `backend/app/interfaces/schemas/camera.py` — request/response Pydantic models
- `backend/app/interfaces/api/__init__.py`
- `backend/app/interfaces/api/cameras.py` — router
- `backend/app/core/exception_handlers.py`
- `backend/tests/unit/application/__init__.py`, `test_onboard_camera.py`, `test_camera_queries.py` — fakes only, no I/O
- `backend/tests/unit/core/__init__.py`, `test_exception_handlers.py` — exception→status mapping, no camera needed
- `backend/tests/unit/infrastructure/__init__.py`, `test_onvif_mappers.py` — pure mapping-function tests incl. the missing-`RateControl` skip case
- `backend/tests/integration/__init__.py`, `backend/tests/integration/onvif/__init__.py`
- `backend/tests/integration/onvif/test_onboard_camera_integration.py` — fixture-driven gateway + **real** `SqlCameraRepository` against a temp SQLite file; proves AC #3 by re-opening a second repository instance against the same file
- `backend/tests/integration/onvif/test_onboard_camera_hardware.py` — `@pytest.mark.hardware`, skipped unless real camera env vars are set
- `backend/tests/fixtures/onvif/device_information.json`, `profiles.json`

**Frontend**: the 6 files listed under "7. Frontend" above.

**Docs**: `docs/TECHNICAL_DECISIONS.md` gets a new `TD-18` entry (credential storage/encryption library choice, the two port/entity signature additions, the auth-vs-unreachable heuristic, the fixture-testing strategy).

## Files to Modify

- `backend/app/domain/exceptions.py` — add `CameraAuthenticationError`, `CameraNotFoundError`
- `backend/app/domain/entities/camera.py` — add `port`, `password` fields
- `backend/app/domain/entities/stream_profile.py` — add `onvif_token`
- `backend/app/application/ports/camera_gateway.py` — add `port` param to `connect()`
- `backend/app/application/use_cases/onboard_camera.py` — implement `execute()`
- `backend/app/core/config.py` — add `camera_credential_encryption_key`, `database_url`
- `backend/app/core/container.py` — wire everything; update stale docstring
- `backend/app/main.py` — lifespan `init_db()`, register router + exception handlers
- `backend/pyproject.toml` — add `onvif-zeep-async`, `sqlmodel`, `aiosqlite`, `cryptography`; `hardware` marker + `-m "not hardware"`; mypy overrides for untyped libs
- `backend/tests/unit/domain/test_exceptions.py`, `test_camera.py`, `test_stream_profile.py` — cover new fields/exceptions (keeps the domain 100%-coverage gate green)
- `.env.example`, local `.env` (untracked convenience) — new encryption key
- `.github/workflows/ci.yml` — env vars for the `Pytest` step
- `frontend/package.json`, `vite.config.ts`, `src/main.tsx` (QueryClientProvider), `src/App.tsx`
- `TASKS.md` — per the Documentation Update Requirements
- `README.md` — Configuration section, status banner
- `docs/IMPLEMENTATION_PLAN.md` §M3 — fix the incomplete "Files" list

## Risks

- **No physical camera available**: all development/testing is fixture-driven (per #8 above); the `@pytest.mark.hardware` test exists but will be unexercised until a real camera is available — it's a thin scaffold, not proof the real adapter works end-to-end against actual hardware.
- **ONVIF vendor quirks TD-03 didn't anticipate**: the auth-vs-unreachable classification (#5) is a message-sniffing heuristic verified only against the library's own source, not against real camera firmware fault strings — a vendor phrasing its auth fault unusually could misclassify as `CameraUnreachableError` (400) instead of `CameraAuthenticationError` (401). Both are still a clean 4xx, so the AC is met either way, but the status code could be imprecise for a given camera.
- **`GetProfiles` returning profiles with no usable encoder config** (spec-legal per the XSD) means some cameras could onboard with zero usable `StreamProfile`s, which would fail AC #1 ("at least one media profile") for that specific device — not something code can fix, only surface clearly.
- **mypy strict + SQLModel**: `table=True` models sometimes need the `sqlmodel.mypy_plugin` or targeted ignores; the plugin is added up front and adjusted if needed during implementation.

## Assumptions

- Credential-storage design: plaintext `Camera.password` field (in-memory only, `repr=False`), ciphertext only ever exists inside `SqlCameraRepository`'s SQL column — see gap #3.
- `ICameraGateway` ABC completeness: `set_video_encoder_configuration` and `get_stream_uri` get `raise NotImplementedError` bodies (M4/M5 territory); `get_video_encoder_configuration` also stubs `NotImplementedError` per the prompt's clarification, while `get_profiles()` does the *real* per-profile encoder-config extraction itself.
- Camera `name` is not part of the request body (AC only specifies IP/username/password); it's derived as `f"{manufacturer} {model}"` when device info provides both, else falls back to the IP address.
- No frontend routing library added — this is the only feature screen until M14.
