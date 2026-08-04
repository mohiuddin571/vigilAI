# VigilAI — Technical Decisions

> Companion documents: [ARCHITECTURE.md](./ARCHITECTURE.md) · [AI_PROJECT_CONTEXT.md](./AI_PROJECT_CONTEXT.md)

Each entry is a lightweight ADR (Architecture Decision Record): **Decision → Context → Alternatives Considered → Tradeoffs → Future Enhancement**. Numbered for reference (e.g. "see TD-06"), not for chronology.

---

## TD-01: Clean Architecture with explicit ports

**Decision**: Domain and Application layers depend on abstract interfaces (`ports`) only; Infrastructure implements them; wiring happens in one composition root.

**Context**: The assignment explicitly penalizes tight coupling between analytics and ONVIF, and requires the analytics pipeline to run unchanged over ONVIF cameras, raw RTSP, and MP4 files.

**Alternatives considered**:
- *Transaction-script / "fat router" FastAPI app* — fastest to write, but analytics code would end up importing camera code directly, which is the exact coupling the assignment warns against.
- *Django-style MVC* — heavier framework assumptions than needed for an API-only backend; FastAPI + Clean Architecture gives the same separation with less ceremony.

**Tradeoffs**: More files and more indirection than a script would need; for a small prototype this can look like over-engineering. Accepted because the assignment is explicitly evaluating architecture, not line count.

**Future enhancement**: Enforce the dependency rule automatically with `import-linter` (contracts forbidding `domain`/`application` from importing `infrastructure`/`interfaces`) as a CI gate rather than a convention.

---

## TD-02: FastAPI as the web framework

**Decision**: FastAPI for REST + WebSocket.

**Context**: Backend is Python; need async I/O for concurrent camera streams, native request validation, and live-view push.

**Alternatives considered**: Flask (no native async/WS story, would need extensions), Django REST Framework (ORM and app-registry assumptions not needed here).

**Tradeoffs**: FastAPI's dependency-injection (`Depends`) is convenient but is *not* used as the project's DI mechanism (see TD-08) — it's reserved for request-scoped concerns (auth, pagination) to avoid two competing DI systems.

**Future enhancement**: None planned; framework choice is expected to hold through production.

---

## TD-03: ONVIF client library — `onvif-zeep-async`

**Decision**: Use `onvif-zeep-async` for device authentication (WS-UsernameToken), device management, and media services.

**Context**: Needed a Python ONVIF client that's async-native (fits the FastAPI/asyncio backend) and still maintained. Older `python-onvif-zeep`/`onvif-zeep` packages are effectively unmaintained.

**Alternatives considered**:
- *Raw SOAP via `zeep` against ONVIF WSDLs directly* — maximum control, no dependency risk, but reimplements what a client library already does; kept as documented fallback.
- *WS-Discovery-first onboarding* (`wsdiscovery` package, broadcast-based) — appealing but many NVR/camera deployments live on routed networks where broadcast discovery doesn't reach; the assignment explicitly asks for IP/username/password auth, so discovery is a "nice to have," not the primary path.

**Tradeoffs**: Dependency on a smaller third-party package (backed by the Home Assistant ONVIF integration user base, which is reassuring but not a guarantee). All ONVIF calls are isolated behind `ICameraGateway` — if the library needs to be replaced, only the infrastructure adapter changes.

**Future enhancement**: Add optional WS-Discovery-based "scan my network" onboarding as a UI convenience once IP/credential onboarding is solid.

---

## TD-04: FFmpeg (subprocess) + OpenCV, not GStreamer

**Decision**: FFmpeg handles RTSP ingestion for recording (stream copy, no re-encode) and browser-preview transcoding; OpenCV `VideoCapture`/`VideoWriter` handles frame-level decode for analytics and MP4 file playback.

**Context**: Assignment mandates FFmpeg for streaming/recording and OpenCV "where appropriate."

**Alternatives considered**: GStreamer (more powerful pipeline graph, but a much heavier dependency to install and reason about on a Mac Mini dev box, and not what the assignment asked for).

**Tradeoffs**: Running FFmpeg as a subprocess means shelling out and parsing stderr for health/diagnostics rather than a native Python pipeline API — more manual process-lifecycle management, but transparent and debuggable (the exact command that runs is always visible in logs).

**Future enhancement**: Wrap the subprocess construction behind a small internal builder if the number of FFmpeg invocation variants grows past a handful; not needed yet.

---

## TD-05: Process-per-stream concurrency model

**Decision**: Each active camera/source's frame-grabbing loop runs in its own OS process (`multiprocessing`), communicating via a bounded, drop-oldest queue. The FastAPI process stays asyncio-only and never blocks on decode.

**Context**: `cv2.VideoCapture.read()` and FFmpeg I/O are blocking calls; YOLO inference is CPU/GPU-bound. Both would stall an asyncio event loop or contend badly under Python's GIL if run as threads in-process.

**Alternatives considered**:
- *Threading* — simpler IPC (shared memory without serialization), but GIL contention between decode and inference threads limits throughput on multi-camera setups; a single misbehaving camera thread is also harder to hard-kill cleanly than a process.
- *asyncio + `run_in_executor`* — fine for I/O-bound work, insufficient isolation for CPU-bound YOLO inference and doesn't protect against a hard camera-driver hang.

**Tradeoffs**: `multiprocessing.Queue` serializes frames (pickling numpy arrays) which costs CPU and memory bandwidth compared to shared memory. Acceptable at the scale of a handful of cameras on a Mac Mini; would need revisiting at high camera counts.

**Future enhancement**: Move to `multiprocessing.shared_memory` ring buffers for frame transport if profiling shows queue serialization is the bottleneck.

---

## TD-06: Object detection — Ultralytics YOLOv8 with built-in ByteTrack

**Decision**: Use Ultralytics' pretrained YOLOv8 (COCO weights) for object detection/classification, and its bundled ByteTrack (`model.track()`) for the identity tracking that loitering detection needs.

**Context**: Assignment mandates Ultralytics YOLO. Loitering detection needs per-object identity across frames, not just per-frame detection.

**Alternatives considered**: DeepSORT (a separate dependency and re-ID model) — rejected because ByteTrack ships inside `ultralytics` already and performs comparably for this use case, avoiding an extra ML dependency.

**Tradeoffs**: COCO pretrained classes are generic (person, car, truck, etc.) — good enough for the required demo scenarios, but won't recognize domain-specific objects (e.g. a specific piece of equipment) without fine-tuning.

**Future enhancement**: Fine-tune or swap in a custom-trained model per deployment; the detector is behind `IObjectDetector`, so this is a model-file/adapter change, not an architecture change.

---

## TD-07: OCR engine for LPR — EasyOCR

**Decision**: EasyOCR for plate text recognition, after a YOLO-based (or classical contour-based, as a lighter fallback) plate-region localizer.

**Context**: License Plate Recognition needs a detect-then-read pipeline: find the plate region, then OCR it.

**Alternatives considered**:
- *PaddleOCR* — strong accuracy, but pulls in PaddlePaddle as a second deep-learning runtime alongside PyTorch (Ultralytics), doubling framework footprint and install complexity on the dev machine.
- *Tesseract* — no extra deep-learning dependency, but materially worse accuracy on angled/low-res plate crops typical of surveillance footage.

**Tradeoffs**: EasyOCR is heavier and slower than Tesseract per-crop; acceptable because LPR only runs on already-cropped, already-detected plate regions, not full frames.

**Future enhancement**: Swap in a purpose-built ALPR model (e.g. a fine-tuned YOLO plate detector + a lightweight CRNN reader) if throughput or accuracy on the evaluation camera's real footage proves insufficient — isolated behind an `ILicensePlateReader` port.

---

## TD-08: Manual composition-root DI, not a DI framework

**Decision**: One `app/core/container.py` module builds every concrete adapter and injects them into use cases via plain constructor arguments. FastAPI's `Depends` is reserved for request-scoped concerns only.

**Context**: Need dependency injection to keep Application decoupled from Infrastructure, without adding a framework the assignment doesn't call for.

**Alternatives considered**: `dependency-injector` library — more features (scopes, providers, wiring decorators) than this project needs; adds a learning-curve dependency for graders reading the code.

**Tradeoffs**: Manual wiring means the composition root grows as adapters grow; for a prototype of this size that's a non-issue and arguably more readable than a framework's provider syntax.

**Future enhancement**: Revisit if the object graph becomes large enough that manual wiring is error-prone (unlikely at this project's scope).

---

## TD-09: Persistence — SQLModel over SQLite, Postgres-ready

**Decision**: SQLModel (SQLAlchemy + Pydantic) models, SQLite file for development, connection string swap to Postgres for anything beyond single-machine use.

**Context**: Need to persist cameras, stream profiles, recording index, and detection events with type-checked schemas that double as API DTOs' source of truth.

**Alternatives considered**: Raw SQLAlchemy + separate Pydantic schemas (more boilerplate, two parallel model definitions); MongoDB (document flexibility not needed — the data is relational: camera → profiles → recordings → events).

**Tradeoffs**: SQLite has no real concurrent-write story; fine for a prototype with one API process, wrong for a multi-instance deployment.

**Future enhancement**: Postgres + Alembic migrations, and a TimescaleDB-style time-series table for `DetectionEvent` if event volume grows large enough that query performance on a plain relational table degrades.

---

## TD-10: Live preview transport — MJPEG first, WebSocket for events, HLS later

**Decision**: Serve the live view as MJPEG-over-HTTP (`multipart/x-mixed-replace`) for the MVP; push analytics events/overlays over a separate WebSocket channel.

**Context**: The browser can't play raw RTSP; something has to bridge camera stream → browser-renderable format.

**Alternatives considered**:
| Option | Latency | Browser support | Multi-viewer efficiency | Complexity |
|---|---|---|---|---|
| MJPEG (chosen) | Low | Universal (`<img>` tag) | Poor (re-encodes per viewer) | Low |
| WebSocket binary frames | Low | Universal, needs client JS | Poor (same issue) | Medium |
| HLS (FFmpeg segmenter) | 2–10s | Universal (`<video>` + hls.js) | Good (segments cacheable/shareable) | Medium-High |
| WebRTC | Very low | Good, needs signaling | Good | High |

**Tradeoffs**: MJPEG doesn't scale to many concurrent viewers per camera and has no built-in adaptive bitrate — acceptable because the assignment's evaluation scenario is one physical camera with a handful of viewers, not a multi-tenant viewing product.

**Future enhancement**: HLS for scale/shareability, or WebRTC if sub-second latency becomes a requirement (e.g. PTZ control feedback).

---

## TD-11: In-process async pub-sub event bus, ports-first

**Decision**: `IEventPublisher`/`IEventSubscriber` ports, implemented in-process (asyncio queue fan-out) for now.

**Context**: Analytics events need to reach both the persistence layer and any live WebSocket subscribers without the orchestrator knowing about either.

**Alternatives considered**: Redis Pub/Sub or Kafka from day one — correct direction for multi-instance deployments, unnecessary operational weight for a single-machine prototype.

**Tradeoffs**: In-process bus doesn't survive an API process restart and can't fan out across multiple backend instances.

**Future enhancement**: Redis Streams (ordering + replay) as a drop-in adapter behind the same port when horizontal scaling is needed.

---

## TD-12: Frontend state — React Query + Zustand, Tailwind

**Decision**: React + TypeScript + Vite; React Query for all server state (cameras, recordings, events); Zustand for local UI state (selected camera, layout); Tailwind CSS for styling; `hls.js`/native `<img>`/`<video>` for media.

**Context**: Frontend needs to poll/subscribe to live-changing server state (camera status, live events) and hold ephemeral UI state, without hand-rolling cache invalidation.

**Alternatives considered**: Redux Toolkit (more ceremony than this app's state complexity warrants); plain `useState`/Context for server state (leads to manual refetch/cache-invalidation bugs, exactly the class of bug React Query exists to prevent).

**Tradeoffs**: Two state libraries (React Query + Zustand) instead of one — accepted because they solve genuinely different problems (server cache vs. local UI state) and mixing them into one tool tends to produce worse code than using each for its purpose.

**Future enhancement**: None anticipated; this stack scales fine through production for an app of this shape.

---

## TD-13: Config via `pydantic-settings`, one `.env`

**Decision**: A single `Settings(BaseSettings)` class is the only place environment variables are read; everything else receives config through constructor injection from the composition root.

**Context**: Multi-process system (API + N stream workers + analytics workers) needs consistent, type-checked configuration without scattered `os.environ.get()` calls that silently return `None` on typos.

**Alternatives considered**: `python-dotenv` + manual parsing — no validation, no type coercion, errors surface at use-time instead of at startup.

**Tradeoffs**: None significant; this is a low-risk, high-value choice.

**Future enhancement**: Layer in a secrets manager (e.g. for camera credentials) before any real deployment — see TD-15.

---

## TD-14: Structured logging via `structlog`

**Decision**: JSON-structured logs in non-dev environments, human-readable console rendering in dev; every log line tagged with `camera_id`/`source_id` and `trace_id` where applicable.

**Context**: With N camera processes + analytics workers + the API process all logging concurrently, unstructured text logs are unreadable and unfilterable.

**Alternatives considered**: Standard-library `logging` with manual formatting — works, but structured context propagation (binding `camera_id` once per worker) is exactly what `structlog`'s context-binding is built for.

**Tradeoffs**: One more dependency; negligible cost.

**Future enhancement**: Ship logs to a central aggregator (e.g. Loki/ELK) once running multi-machine.

---

## TD-15: Camera credentials — plaintext-avoidance now, secrets manager later

**Decision**: Camera passwords are stored encrypted at rest (application-level symmetric encryption using a key from environment config), never logged, never returned in API responses after creation.

**Context**: ONVIF onboarding necessarily handles camera passwords; this is real (if small-scale) sensitive data even in a prototype.

**Alternatives considered**: Plaintext storage (rejected outright — avoidable security smell even in a take-home project); full secrets-manager integration (Vault/AWS Secrets Manager) — correct for production, disproportionate for a local prototype with one evaluator-provided camera.

**Tradeoffs**: Application-level symmetric encryption with a config-supplied key is better than plaintext but is not a substitute for a real secrets manager (the key itself still lives in `.env`).

**Future enhancement**: External secrets manager + per-camera credential rotation before any multi-tenant or production use.

---

## TD-16: Python dependency management — `uv`

**Decision**: `uv` manages the backend's virtual environment and dependencies (`backend/pyproject.toml` + committed `backend/uv.lock`), invoked as `uv sync` / `uv run`.

**Context**: M0 needed a concrete package manager and none was fixed by prior docs — `docs/AI_PROJECT_CONTEXT.md`'s tech table names Python/FastAPI but not a specific dependency tool.

**Alternatives considered**:
- *pip + venv* — zero extra dependency (stdlib-adjacent), but no native lockfile without also adding `pip-tools`, and slower installs.
- *Poetry* — mature and widely known, but a slower dependency resolver and a heavier tool than this project's dependency graph needs.

**Tradeoffs**: One more tool a reviewer needs to know (`uv` instead of plain `pip`), offset by materially faster installs/resolution and a single lockfile that keeps `backend/uv.lock` reproducible across machines.

**Future enhancement**: None anticipated; revisit only if `uv` stops being maintained.

---

## TD-17: Import-linter contract shape + pre-commit/CI enforcement

**Decision**: `import-linter`'s `layers` contract type (configured in `backend/pyproject.toml` under `[tool.importlinter]`) enforces the dependency direction rule from `docs/FOLDER_STRUCTURE.md`: `app.interfaces` and `app.infrastructure` sit at the same (independent) top layer — neither may import the other — both may import `app.application`, which may import `app.domain` only. `app.core` is deliberately left out of the contract's layer list, since its entire job as the composition root is to import across every layer. Enforcement runs in two places: a local `pre-commit` hook (`.pre-commit-config.yaml`, invoking `uv run lint-imports`) and the `import-linter` step in `.github/workflows/ci.yml`.

**Context**: `docs/IMPLEMENTATION_PLAN.md` M0 already named "import-linter (or equivalent)" as the presumptive tool for this gate but never fixed the exact contract shape or where enforcement runs; that's the real decision this entry records.

**Alternatives considered**:
- *A custom AST-walking script* — full control, but reimplements what `import-linter` already does well, and the `layers` contract type happens to map almost one-to-one onto `docs/FOLDER_STRUCTURE.md`'s "Dependency Direction Rule" diagram (including the independent-sibling case for `interfaces`/`infrastructure`).
- *CI-only enforcement (no pre-commit)* — simpler, but lets a violation reach a pushed commit before being caught; pre-commit catches it locally first, CI catches anything committed with `--no-verify`.

**Tradeoffs**: The `layers` contract can't express "core sees everything" as a rule (it can only constrain listed layers) — `core` is simply left out of the contract, which is a correct outcome here but relies on nothing else ever mistakenly relying on the contract to constrain `core`.

**Future enhancement**: Add an explicit "independence" contract for `infrastructure`'s own subfolders (e.g. `analytics/` must not import `streaming/` directly) once those subfolders exist, per `docs/FOLDER_STRUCTURE.md`'s note that infrastructure modules should only talk to each other through ports.

---

## TD-18: M3 ONVIF onboarding — credential storage, port additions, and error classification

**Decision**: Four related implementation-time decisions made while building M3 (ONVIF Camera Onboarding), none of which TD-03/TD-09/TD-15 fixed precisely enough to derive without a real choice:

1. **Credential storage location**: `Camera.password: str` is a plaintext, in-memory-only field (`repr=False`, so it can never leak via an accidental `repr()`/log call) — the same plaintext that arrived in the `POST /cameras` body. `SqlCameraRepository` (`backend/app/infrastructure/persistence/sql_camera_repository.py`) is the *only* code that ever touches ciphertext or the encryption key: it encrypts on `add`/`update`, decrypts on `get`/`list`. `ICameraRepository`'s four-method, `Camera`-only signature (fixed by M1) is unchanged.
2. **Encryption library**: `cryptography`'s `Fernet` (symmetric, authenticated encryption), wrapped in `backend/app/infrastructure/security/credential_cipher.py`. New `Settings` field `camera_credential_encryption_key: str`, required with no default (TD-15 already committed to "a key from environment config"; this entry is what actually names the library and settings field).
3. **Two small, additive port/entity signature extensions**, both discovered only once real ONVIF wiring was attempted:
   - `ICameraGateway.connect()` gained `port: int = 80` — the M1 signature had no way to address a camera at a non-default ONVIF port, and the real `onvif-zeep-async` `ONVIFCamera` constructor requires one.
   - `StreamProfile` gained `onvif_token: str | None = None` — `ICameraGateway.get_video_encoder_configuration`/`get_stream_uri` already type `profile_id` as `str` (the camera's own profile token, not our internal `UUID` id), so M3 has to capture and persist that token now or M4/M5 would have no way to address a persisted profile back on the camera.
   - `ICameraGateway.disconnect()` (new abstract method) — the real `ONVIFCamera` holds an `aiohttp` session that leaks if never closed; discovered live (an "Unclosed client session" warning during manual browser verification), fixed by adding `disconnect()` to the port and having `OnboardCameraUseCase.execute()` call it in a `finally` block regardless of success/failure.
4. **Auth-vs-unreachable classification heuristic**: `onvif-zeep-async`'s own source was read directly (not just its docs) to confirm it does *not* reliably distinguish "wrong credentials" from "other SOAP fault" for the calls M3 makes (`update_xaddrs`, `GetDeviceInformation`, `GetProfiles`) — its `ONVIFAuthError` is only raised from an unrelated HTTP-snapshot code path. `backend/app/infrastructure/onvif/mappers.py::classify_onvif_error` uses `ONVIFAuthError` when present, else a substring match on common WS-Security fault wording (`"notauthorized"`, `"failedauthentication"`, `"unauthorized"`, `"authentication"`, `"password mismatch"`), else falls back to `CameraUnreachableError`. Both map to a clean 4xx (`CameraAuthenticationError` → 401, `CameraUnreachableError` → 400) via `backend/app/core/exception_handlers.py`, so the milestone's acceptance criteria hold either way — only the specific status code is best-effort.
5. **`adjust_time=True` on every connection**: confirmed against two real Matrix `MIDR20FL28CWS` cameras provided for evaluation — without it, `connect()` failed with a SOAP fault reading `"Password Mismatch"` for credentials later confirmed correct. WS-Security digest auth is timestamp-based, so clock skew between this host and the camera (expected for a WAN-reachable camera, not NTP-synced to this dev machine) makes even a *correct* password fail the digest check, and the resulting fault is indistinguishable from an actually-wrong password. `onvif-zeep-async` ships a built-in fix for exactly this (`ONVIFCamera(..., adjust_time=True)`, which measures the offset via `GetSystemDateAndTime` and compensates); `OnvifCameraGateway.connect()` now always passes it. This is unconditional, not conditional/retry-based — there's no reliable way to distinguish "clock skew" from "actually wrong password" from the fault alone, and enabling it unconditionally costs one extra round-trip per connection with no correctness downside for cameras that don't need it.

**Real-hardware finding kept open, not silently worked around**: onboarding both evaluation cameras (`154.210.224.77:7008` and `:7010`) succeeded and persisted correctly, but 2 of each camera's 4 reported profiles were dropped — their `VideoEncoderConfiguration.Encoding` came back as the literal string `"3"` rather than a `tt:VideoEncoding` value (`"JPEG"`/`"MPEG4"`/`"H264"`), which `map_codec` correctly refuses to guess-map (logged as `onvif.unknown_codec`, profile skipped — see the Constraints section's ban on fabricating placeholder values, applied here too). Circumstantial evidence (1920x1080@25fps/4096kbps and 704x576@25fps/1024kbps, alongside two properly-labeled `"JPEG"` profiles at low frame rates) strongly suggests these are the camera's actual H.264 main/sub streams and `"3"` is a vendor firmware bug — but that's inference, not documented vendor behavior, so it is *not* baked into `_ONVIF_ENCODING_TO_CODEC` as a guess: mislabeling a stream's codec would silently corrupt M6's recording pipeline (`-c copy` needs to know the real codec) in a way that's far worse than dropping a profile now. AC #1 ("at least one media profile") is unaffected — both cameras still onboard with 2 usable profiles each. Flagged for whoever picks up M4/M5/M6: confirm with Matrix's ONVIF documentation or `GetVideoEncoderConfigurationOptions` before either mapping `"3"` → `H264` or building anything that assumes these two profiles are unusable.

**Context**: `docs/IMPLEMENTATION_PLAN.md` §M3's "Files" list didn't name persistence, `exception_handlers.py`, or the container/main wiring at all (see the same file's fix in this PR), and its Constraints section flagged the credential-storage question explicitly as undecided. The port/entity extensions, the error-classification heuristic, and the `adjust_time` requirement were not anticipated by any planning document — they surfaced only once the real `onvif-zeep-async` package was installed and inspected, and once real evaluation-camera credentials were tested against it (decisions 1–4 from source/schema inspection; decision 5 and the open finding above from live hardware).

**Alternatives considered**:
- *Separate credential store keyed by camera id* (the other option the M3 prompt named) — rejected because it would require either widening `ICameraRepository`'s signature (a bigger change to an M1-fixed port than adding one field to `Camera`) or bypassing the port entirely from the repository's internals.
- *A protocol-level SOAP/WSDL simulator for offline ONVIF testing* (vs. the fixture-driven fake client actually used, `backend/tests/fixtures/onvif/fake_camera.py`) — a full simulator would exercise the wire format byte-for-byte, but is disproportionate engineering effort for this milestone; the fixture-driven fake (an injectable `client_factory` on `OnvifCameraGateway`, loaded from JSON fixtures shaped like real recorded responses) satisfies T-037's actual DoD ("integration suite runs in CI without a real camera") at a fraction of the cost.
- *Reject unknown WS-Security fault wording as unreachable-only* (no auth heuristic at all) — rejected because it would make every real camera's "wrong password" response surface as 400 instead of 401, a strictly worse default given the AC only requires *some* clean 4xx, but a precise one is more useful when available.

**Tradeoffs**: The auth-classification heuristic is verified only against `onvif-zeep-async`'s own source, not real camera firmware — a vendor phrasing its WS-Security fault unusually could still misclassify as `CameraUnreachableError` (400) instead of `CameraAuthenticationError` (401). Both are still a typed 4xx, so this affects precision, not correctness of the milestone's acceptance criteria. The fixture-driven ONVIF test double is not a substitute for testing against the real `onvif-zeep-async` SOAP/WSDL wire protocol — a subtle bug in how the real library parses a real camera's XML would not be caught by these tests, only by the `@pytest.mark.hardware` suite once a physical camera is available.

**Future enhancement**: If a specific camera vendor's auth-fault wording proves to consistently misclassify, add its fault string to `mappers._AUTH_FAULT_HINTS` rather than reworking the whole classification approach.

---

## TD-19: M4 ONVIF configuration — capability port addition and codec-as-read-only

**Decision**: Two related implementation-time decisions made while building M4 (ONVIF Camera Configuration):

1. **Additive port method**: `ICameraGateway.get_video_encoder_configuration_options(profile_id: str) -> VideoEncoderCapabilities` (new abstract method), backed by a new domain value object `VideoEncoderCapabilities` (`backend/app/domain/value_objects/video_encoder_capabilities.py`: `codec`, `resolutions`, `fps_min`/`fps_max`, optional `bitrate_min_kbps`/`bitrate_max_kbps`). M1's `ICameraGateway.get_video_encoder_configuration`/`set_video_encoder_configuration` (both typed against `StreamProfile`, which only carries *current* values) had no way to express the *range* of values a camera reports as legal, but T-043's DoD ("edit form limited to supported fields") and IMPLEMENTATION_PLAN.md §M4's "edit form limited to supported fields" both require the frontend to know that range, not just discover it by trial-and-error PATCH failures. This mirrors TD-18's precedent for M3: extend `ICameraGateway` additively (no existing method's signature changed) rather than working around a genuine contract gap.
2. **Codec treated as read-only, never offered as editable**: ONVIF's `GetVideoEncoderConfigurationOptions` response reports per-codec ranges (resolutions/framerate/bitrate) but never asserts whether a given video-encoder configuration can be *switched* to a different codec — that's vendor/firmware-dependent behavior the spec doesn't standardize. Rather than guess-map "no explicit prohibition" to "codec changes are allowed" (the same category of guess TD-18 already refused for the `"3"`-encoding finding), `UpdateCameraConfigUseCase`/`encoder_config.validate_requested_configuration` always reject a PATCH that requests a different codec than the profile's current one, via the normal `UnsupportedConfigurationError` → `422` path. This also serves as the concrete "unsupported field" test case required by the Testing Expectations, since it's a deterministic rejection that doesn't depend on fixture-specific bounds.

**Context**: `docs/IMPLEMENTATION_PLAN.md` §M4 named `GetVideoEncoderConfiguration(s)`/`SetVideoEncoderConfiguration`/the config API/the frontend panel as deliverables but, like M3's plan before TD-18, didn't specify the exact port/DTO shape needed to carry capability data from the ONVIF response through to the frontend. `GetVideoEncoderConfiguration`/`SetVideoEncoderConfiguration` on `ICameraGateway` already fit T-040/T-041 as-is (both address by `profile_id` and operate on `StreamProfile`, matching the M3 `onvif_token` convention) — only the capability-exposure gap required a real decision.

**Alternatives considered**:
- *Fold capability data into `StreamProfile` itself* (e.g. optional `available_resolutions` fields) — rejected because `StreamProfile` is a persisted domain entity (round-trips through `SqlCameraRepository`); capability ranges are a live, request-scoped ONVIF fact, not something that belongs in persisted state or that every `StreamProfile` consumer (onboarding, persistence) needs to carry.
- *No dedicated capability port method — validate inside `set_video_encoder_configuration` only, never expose ranges to the API* — this is in fact what `set_video_encoder_configuration` does internally for server-side enforcement (it re-fetches `GetVideoEncoderConfigurationOptions` itself rather than trusting a caller-supplied value, so validation holds even if a client never called GET first). But relying on it exclusively would leave the frontend with no way to build a form "limited to supported fields" except by trial-and-error submission, which doesn't satisfy T-043 as written.
- *Model codec-switch support as a capability field* (e.g. `switchable_codecs: list[Codec]`) — rejected for the same reason TD-18 declined to guess-map the `"3"` encoding: ONVIF's schema gives no field asserting this, so any such list would be this system's own guess, not camera-reported fact.

**Tradeoffs**: The capability fetch (`GetVideoEncoderConfigurationOptions`) is called twice across a GET-then-PATCH cycle — once by `GetCameraConfigUseCase` (to build the response) and again inside `OnvifCameraGateway.set_video_encoder_configuration` (to validate server-side) — rather than threading a single fetched value through both. Accepted because it keeps `set_video_encoder_configuration`'s validation self-contained and safe to call independently (e.g. from a future direct PATCH without a prior GET) rather than trusting a caller-supplied capability snapshot that could be stale. A camera that legitimately supports codec-switching on a given configuration will have that rejected by this system regardless — a real (if currently unencountered) limitation, not a bug in the capability model itself.

**Future enhancement**: If a specific camera vendor's ONVIF extension does assert codec-switch support (e.g. via a documented vendor `Extension` element), add it to `VideoEncoderCapabilities` and loosen the check in `encoder_config.validate_requested_configuration` — don't infer it from silence in the base schema.

---

## Future Enhancements (Consolidated)

| Area | Current (prototype) | Production direction |
|---|---|---|
| Event bus | In-process asyncio | Redis Streams / Kafka |
| Recording storage | Local filesystem | Object storage (S3/MinIO) behind `IRecordingRepository` |
| Database | SQLite | Postgres + Alembic + (optionally) TimescaleDB for events |
| Live preview | MJPEG + WebSocket | HLS and/or WebRTC |
| Auth | None (local dev tool) | OAuth2/OIDC + RBAC |
| Deployment | Single Mac Mini process tree | Docker Compose → k8s if needed |
| Camera discovery | Manual IP entry | WS-Discovery-assisted network scan |
| Detection models | COCO-pretrained YOLO | Fine-tuned per-deployment models |
| Secrets | Encrypted-at-rest, config key | Secrets manager + rotation |
