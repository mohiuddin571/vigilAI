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

**Future enhancement**: Fine-tune or swap in a custom-trained model per deployment; the detector is behind `IDetectorPlugin` (M8, supersedes the M1 `IObjectDetector` — see TD-24), so this is a model-file/adapter change, not an architecture change.

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

## TD-20: M2 Frame Source Abstraction — port shape, process model, and a known fixture limitation

**Decision**: Five related implementation-time decisions made while building M2 (Frame Source Abstraction + MP4 File Adapter), none of which `docs/IMPLEMENTATION_PLAN.md`/`docs/ARCHITECTURE.md` fixed precisely enough to derive without a real choice:

1. **New port: `IStreamWorker`** (`backend/app/application/ports/stream_worker.py`) — `start`/`stop`/`frames()`/`health()`. Neither `docs/ARCHITECTURE.md` §6.2 nor `docs/FOLDER_STRUCTURE.md` names an exact interface for "the Stream Worker abstraction," but the M5 template (`prompts/04-stream-manager.md`'s generated run prompt) already presupposes `StartLiveStreamUseCase` depends on "`IFrameSource` and the M2 Stream Worker abstraction it wraps." Since `application/` may only import `domain/` (Dependency Direction Rule, `docs/FOLDER_STRUCTURE.md`), a use case cannot hold the concrete `StreamWorker` class directly — it needs a port, so this is additive in the same spirit as TD-18/TD-19's port extensions, not a new architectural direction.
2. **Split reconnect logic from process isolation**: `ReconnectSupervisor` (`infrastructure/streaming/reconnect_supervisor.py`) is a pure-asyncio class owning the open→consume→backoff→retry loop against any `IFrameSource`, with no knowledge of `multiprocessing`. `StreamWorker` (`infrastructure/streaming/stream_worker.py`, implements `IStreamWorker`) runs a `ReconnectSupervisor` inside a child `multiprocessing.Process` (TD-05) and bridges frames/health back via two bounded, drop-oldest `multiprocessing.Queue`s. This split exists specifically so T-024's required test ("unit test with a fake flaky `IFrameSource` proves backoff sequence") can run with no real I/O and no process-spawn overhead, while T-023's "in a separate process" acceptance criterion is still met by the outer class. `ReconnectSupervisor` retries indefinitely with a capped backoff — `StreamState.FAILED` is defined (for M5's WebSocket status channel, T-053) but never emitted by M2's code, since no acceptance criterion in this milestone calls for a give-up-after-N-attempts policy.
3. **OpenCV package**: `opencv-python-headless` (not `opencv-python`) — TD-04 already decided OpenCV for MP4/analytics decode but never named the installable package; headless avoids pulling in Qt/GUI bindings this server-side project never uses. `numpy` arrives as its transitive dependency and is used directly in `domain/entities/frame.py`'s `image` field — the domain layer's existing "never import `cv2`/`fastapi`/`sqlalchemy`" rule (`docs/FOLDER_STRUCTURE.md`) doesn't cover `numpy`, and `IMPLEMENTATION_PLAN.md` §M2 itself specifies the `Frame` object must carry an "image array."
4. **New domain exception**: `FrameSourceUnavailableError` (`domain/exceptions.py`) — `CameraUnreachableError` is ONVIF-connection-specific naming that would be misleading for an MP4 file that fails to open, so a source-agnostic sibling was added rather than reusing or renaming the existing one.
5. **Configuration additions**: `Settings.stream_worker_reconnect_backoff_seconds` (`[1, 2, 4, 8, 16, 30]`) and `Settings.stream_worker_frame_queue_max_size` (`10`) — TD-13 requires all config through `Settings`, and T-024/T-023 need concrete default values neither `IMPLEMENTATION_PLAN.md` nor `TASK_BACKLOG.md` pin down beyond "e.g. 1s,2s,4s,capped."

**Known limitation, kept open rather than silently worked around** (mirrors TD-18's precedent for its own real-hardware finding): `backend/tests/fixtures/sample.mp4` (T-022) is a **synthetic** clip generated by `scripts/generate_sample_fixture.py` (a colored circle moving across a plain background) — there was no way to source real footage in the environment this milestone was implemented in. It fully satisfies M2's own acceptance criteria (frames flow at the correct throttled rate; reconnect/backoff works against it) but does **not** satisfy T-022's Definition of Done wish for "visible people/objects/vehicle+plate," which M9 (object detection), M10 (color), and M13 (LPR) will need. Flagged for whoever picks up M9: replace `backend/tests/fixtures/sample.mp4` with a real short clip containing detectable objects (and, for M13, a legible plate) before building detector plugins against it — the synthetic clip will produce no meaningful detections.

**Observed operational risk, not fixed in this milestone**: manual smoke-testing under `uvicorn --reload` showed that when the API process is replaced by a reload cycle (or killed non-gracefully) while a `StreamWorker` child process is running, the child (a `multiprocessing.Process(daemon=True)`) can be orphaned — `daemon=True` cleanup relies on the *parent* interpreter's normal `atexit` handling, which doesn't run if the parent is terminated abruptly rather than exiting normally. `StreamWorker.stop()` itself joins/terminates its child cleanly when called, so this only manifests when `stop()` is never called at all before the parent dies. This is exactly the class of problem `docs/TASK_BACKLOG.md` T-202 ("Graceful shutdown of all worker processes on API stop," cross-cutting, depends on M2) is scoped to fix — not addressed here since it's explicitly a separate backlog item, not part of M2's acceptance criteria.

**Context**: `docs/IMPLEMENTATION_PLAN.md` §M2's own Deliverables/Files lists named `Frame`, `Mp4FileFrameSource`, and "Stream Worker" but not the port shape connecting them to a future use case, the exact process-isolation mechanics, or the debug endpoint's request/response contract — all four surfaced only once real implementation was attempted, the same category of gap TD-18/TD-19 document for M3/M4.

**Alternatives considered**:
- *Fold reconnect/backoff directly into `StreamWorker`, no separate `ReconnectSupervisor` class* — rejected because it would make T-024's required unit test either spawn a real OS process (slow, and reintroduces the exact process-vs-logic coupling T-023/T-024 being separate backlog items already implies should be separable) or force the fake flaky source through the multiprocessing boundary (fakes generally aren't picklable-by-design, e.g. closures/mocks).
- *Give `IFrameSource` its own `health()` method* (matching `docs/ARCHITECTURE.md` §5's class diagram literally) — rejected because a source only knows open/closed, not "reconnecting"; that's the supervising Stream Worker's concern. The diagram is corrected in the same PR (see below) rather than matched as-is.
- *Real footage sourced from a stock/sample-video site* — not attempted: fetching arbitrary external video content isn't something to do unprompted, and no such source was provided for this milestone.

**Tradeoffs**: The synthetic fixture is the biggest one — it fully proves M2's plumbing but is a known dead end for M9+ as documented above. The `IStreamWorker`/`ReconnectSupervisor`/`StreamWorker` three-way split adds a layer of indirection a simpler (single-class) design wouldn't need, accepted for the testability reason given above.

**Future enhancement**: Add a bounded-retry/give-up policy (transitioning to `StreamState.FAILED`) if a future milestone's acceptance criteria require distinguishing "still trying" from "given up" in the UI, rather than retrying forever. Fix T-202 to guarantee child-process cleanup even on ungraceful parent termination (e.g. `atexit`/signal handlers registered by the composition root, or an OS-level process-group kill).

---

## TD-21: M5 Live Streaming — RTSP decode path, use-case shape, and per-camera gateway lifecycle

**Decision**: Four related implementation-time decisions made while building M5 (Live Streaming + Auto-Reconnect), none of which `docs/IMPLEMENTATION_PLAN.md`/`docs/ARCHITECTURE.md` fixed precisely enough to derive without a real choice:

1. **RTSP decode reuses `cv2.VideoCapture`, not a subprocess `ffmpeg`, and defaults to TCP transport**: `OnvifRtspFrameSource`/`RawRtspFrameSource` (`backend/app/infrastructure/streaming/rtsp_frame_source.py`) open RTSP URLs via `cv2.VideoCapture(url, cv2.CAP_FFMPEG, [...timeouts])` — the exact `Mp4FileFrameSource` decode call shape (TD-04/TD-20), just pointed at a network URL. `opencv-python-headless` ships FFmpeg's decode libraries statically linked, so no new Python dependency or subprocess-management code was needed. The Deliverables text in `docs/IMPLEMENTATION_PLAN.md`/the M5 run prompt calling this "the shared FFmpeg/OpenCV decode path introduced by M2" is read literally: M2 only introduced `cv2.VideoCapture`-based decode, so that's what's shared. Public RTSP port-forwards commonly expose TCP but not RTP's dynamic UDP ports, so the injected `rtsp_transport` setting defaults to TCP; it is passed to FFmpeg through OpenCV's documented capture-options mechanism. A subprocess `ffmpeg` muxer remains M6's (`recording_worker.py`, `-c copy`) deliverable, not M5's.
2. **`OnvifRtspFrameSource` re-resolves `GetStreamUri` on every `start()`** (i.e. every reconnect attempt), building a short-lived `ICameraGateway` internally via a required (no-default) `camera_gateway_factory: Callable[[], ICameraGateway]` constructor argument — not a live gateway instance, since `OnvifRtspFrameSource`'s constructor args must stay picklable to cross the `multiprocessing` "spawn" boundary `StreamWorker` uses (TD-20). The concrete `OnvifCameraGateway` is supplied only by `core/container.py` (the composition root), so `infrastructure/streaming/` never imports `infrastructure/onvif/` directly — consistent with `docs/FOLDER_STRUCTURE.md`'s "infrastructure subfolders only talk to each other through ports." Re-resolving per attempt (rather than resolving once and reusing a cached URL) tolerates a camera that changes its RTSP URL (e.g. after a reboot) without the source getting stuck retrying a stale one; the cost is one extra ONVIF round-trip per reconnect attempt, accepted as cheap relative to the RTSP connection itself.
3. **`StartLiveStreamUseCase` is a stateful singleton holding a per-`camera_id` registry**, not a per-request use case — the composition root builds and returns the same instance every call (`Container.build_start_live_stream_use_case`), mirroring M2's `DebugStreamUseCase` (T-025) generalized from one global worker to one worker per camera. This was necessary because MJPEG viewers, the WebSocket status channel, and start/stop calls must all observe the *same* running Stream Worker across separate HTTP/WS requests. A consequence: its `ICameraGateway` dependency had to become a **factory** (`camera_gateway_factory: Callable[[], ICameraGateway]`), not a fixed instance — reusing one `OnvifCameraGateway` (which holds per-connection mutable state, the same reason `interfaces/api/cameras.py` uses per-request use-case factories, TD-08) across the singleton's lifetime would let concurrent `execute()` calls for different cameras corrupt each other's ONVIF session. `execute()` still does one upfront `connect()` → `get_stream_uri()` → `disconnect()` cycle through this factory purely as a fail-fast reachability/credential check (so a currently-unreachable camera or bad password surfaces as a synchronous typed 4xx from `POST /streams/{id}/start`), separate from and in addition to `OnvifRtspFrameSource`'s own independent resolution inside the supervised worker (decision 2) — the URI/credentials resolved by this check are never logged or persisted (TD-15), and are deliberately not threaded into the worker (which re-resolves itself) to keep the two concerns decoupled.

4. **Enable the ONVIF client's `nat_override` on every camera connection and support an optional public RTSP URL override.** Some cameras reached through a public port-forward advertise private-LAN ONVIF service XAddrs (for example, `10.x.x.x:80`) in `GetServices`/`GetCapabilities`. Following those addresses makes onboarding or stream start fail even though the configured public host/port is reachable. `nat_override=True` rewrites advertised ONVIF service URLs to the configured camera host/port while preserving their paths; it is harmless for direct LAN connections. It deliberately applies only to ONVIF control-plane service URLs. A persisted optional RTSP URL override addresses cameras whose `GetStreamUri` result is also private or whose public RTSP endpoint differs from the ONVIF forwarding endpoint; when supplied, the stream worker uses it directly and leaves ONVIF to the synchronous reachability check.
5. **In-process broadcast fan-out for multi-viewer MJPEG**: `IStreamWorker.frames()` drains a single `multiprocessing.Queue` (TD-20) — two concurrent callers would race for items rather than each seeing the full stream, which matters here because multiple browser tabs/`<img>` requests can legitimately view the same camera concurrently (TD-10's documented multi-viewer tradeoff). `StartLiveStreamUseCase`'s internal `_StreamHandle` runs exactly one task draining `worker.frames()`, and republishes each frame via an `asyncio.Condition` that every viewer's own `frames()` async generator waits on — a slow viewer misses frames rather than blocking the worker or other viewers, which is the accepted MVP tradeoff TD-10 already named. This also keeps process count at one-per-camera regardless of viewer count, addressing part of TD-10's "poor multi-viewer efficiency" note (re-encode-per-viewer is still true — JPEG-encoding happens per MJPEG HTTP connection in `interfaces/api/streams.py` — but at least decode/process spawning is not per-viewer).

**Known limitation, kept open rather than silently worked around** (mirrors TD-18/TD-20's precedent): neither a physical ONVIF camera nor the `ffmpeg`/an RTSP-server binary was available in the environment this milestone was implemented in (verified: `ffmpeg -version` → not found), so T-054 ("real-world reconnect validation against physical camera") could not be executed live. What was verified instead: `RawRtspFrameSource`/`OnvifRtspFrameSource` pointed at the local MP4 fixture path (exercising the identical `cv2.VideoCapture` decode call `cv2.VideoCapture` makes for a real `rtsp://` URL, just without a real network source) in `backend/tests/integration/streaming/test_rtsp_frame_source_integration.py`; and that reconnect/backoff itself needs no new testing, since `OnvifRtspFrameSource`/`RawRtspFrameSource` are supervised by the exact same `ReconnectSupervisor` already proven against a fake flaky `IFrameSource` in T-024's permanent test (`backend/tests/unit/infrastructure/test_reconnect_supervisor.py`, unmodified). A real-camera or local-RTSP-server run of the induced-disconnect scenario remains an open, `@pytest.mark.hardware`-shaped manual step for whoever has access to the evaluator's camera or can install `ffmpeg` — reproduction steps: start a live stream against the camera/test RTSP source, confirm `GET /streams/{id}/status` (or the WS channel) shows `"connected"`, interrupt the network path or kill the RTSP source process, confirm `status` moves to `"reconnecting"` with `consecutive_failures` increasing, restore the source, confirm `status` returns to `"connected"` within the configured backoff schedule's cumulative worst case (`stream_worker_reconnect_backoff_seconds`, capped at 30s per attempt).

**Context**: `docs/IMPLEMENTATION_PLAN.md` §M5 and `docs/TASK_BACKLOG.md` Epic M5 named `OnvifRtspFrameSource`/`RawRtspFrameSource`, `StartLiveStreamUseCase`, the MJPEG endpoint, and the WebSocket channel as deliverables but, like M2/M3/M4 before it (TD-18/TD-19/TD-20), didn't specify the exact decode mechanism, the use case's statefulness, or the multi-viewer fan-out mechanics — all four surfaced only once real implementation was attempted.

**Alternatives considered**:
- *Subprocess `ffmpeg` piping raw video frames* — rejected for M5 as disproportionate scope: it would duplicate `cv2.VideoCapture`'s already-working RTSP handling, and M6's recording worker is the milestone that actually needs `ffmpeg`'s `-c copy` stream-copy behavior (no frame decode at all, just remuxing), which `cv2.VideoCapture` cannot do.
- *Pre-resolve the RTSP URI once in `StartLiveStreamUseCase` and hand a plain URL to a `RawRtspFrameSource`-shaped worker, with no `OnvifRtspFrameSource` class at all* — rejected because it would make `OnvifRtspFrameSource` and `RawRtspFrameSource` behaviorally identical (contradicting T-050/T-051's distinct DoDs) and would leave the supervised worker retrying a URL that could go stale after a camera reboot, with no way to refresh it short of restarting the whole live-view session from the API layer.
- *Per-request `StartLiveStreamUseCase` (matching `OnboardCameraUseCase`'s shape) with a separately-injected shared worker registry* — considered, but splitting "the use case" from "the state it owns" into two objects didn't reduce complexity over the single-singleton `DebugStreamUseCase` precedent already established and blessed by TD-20; would also have needed the same registry object threaded through both the API router and the WS router regardless.
- *One `multiprocessing.Queue` per viewer, with the child process itself fanning out* — rejected as unnecessary complexity: fan-out is a pure in-process concern once frames reach the API process, and doing it there (asyncio, not multiprocessing) avoids adding a second IPC layer.

**Tradeoffs**: MJPEG is still re-encoded (JPEG) per viewer, per TD-10's already-accepted tradeoff — this milestone only avoids re-*decoding*/re-*spawning* per viewer, not re-encoding. The upfront `get_stream_uri` reachability check in `StartLiveStreamUseCase.execute()` costs a redundant ONVIF round-trip beyond what `OnvifRtspFrameSource` itself needs (mirroring TD-19's precedent of accepting a redundant capability-fetch for validation-safety reasons) — accepted because it turns "camera unreachable" from a UI-only-observable-via-WS-polling failure into an immediate typed 4xx from the start endpoint. The reconnect-validation known limitation above is the most significant one: automated coverage proves the decode path and the (unmodified, already-permanent) reconnect/backoff logic, not the specific combination of "real RTSP protocol timing + real network interruption," which needs hardware or `ffmpeg` this environment didn't have.

**Future enhancement**: Once a physical camera or local RTSP test server is available, run and document the manual T-054 reproduction above, converting it into a `@pytest.mark.hardware` test if practical. If MJPEG's re-encode-per-viewer cost becomes a real bottleneck (TD-10's "Future enhancement" already names HLS/WebRTC as the production direction), the JPEG encode step in `interfaces/api/streams.py` is the one place that would need to change, not the frame-production/fan-out path added here.

---

## TD-22: M6 Recording — worker port shape, segment/persistence model, and session-sharing across two use cases

**Decision**: Five related implementation-time decisions made while building M6 (Recording), none of which `docs/IMPLEMENTATION_PLAN.md`/`docs/TASK_BACKLOG.md` fixed precisely enough to derive without a real choice:

1. **`IRecordingWorker` port**: `start() -> Recording` / `stop() -> list[Recording]` (`backend/app/application/ports/recording_worker.py`), mirroring `IStreamWorker`'s role for live streaming — `StartRecordingUseCase`/`StopRecordingUseCase` depend on this, never on the concrete FFmpeg subprocess class directly. Both methods return domain `Recording` entities directly rather than a new DTO type — sanctioned by `docs/FOLDER_STRUCTURE.md` ("infrastructure... depends on... domain... to construct/return entities"), the same precedent `IStreamWorker.frames()` already sets by yielding `Frame`.
2. **`Recording` kept as-is (one row per physical segment file), not extended to hold multiple file paths.** `docs/IMPLEMENTATION_PLAN.md` §M6's own prompt flagged this as a genuine open question (`Recording` currently models one `file_path`, ffmpeg's segment muxer can produce several files per session). Reconciled with the M1-era `start_recording.py` stub's own docstring ("a Recording row exists... for the in-progress segment") as follows: `StartRecordingUseCase` persists **one** in-progress row (`ended_at=None`) the moment `IRecordingWorker.start()` returns; at `stop()`, the first finalized segment **updates** that same row (`IRecordingRepository` gained a new `update()` method, mirroring `ICameraRepository.update()` — additive, same pattern as TD-18/19/20's port extensions) and any further rollover segments are `add()`ed fresh. In the common case (one recording session, one segment — segment duration longer than the session), this satisfies T-062's DoD ("exactly one consistent metadata row per segment set") literally: one row, created at start, finalized at stop, same id throughout.
3. **Deterministic segment naming (`{session_id}_%03d.mp4`, `session_id = uuid4()` chosen once per `start()`), not ffmpeg's `-strftime`.** The exact path of the first segment must be knowable *before* ffmpeg is even spawned (so `start()` can return an accurate in-progress `Recording.file_path`) — a `%03d` numeric pattern makes this exact; guessing ffmpeg's wall-clock write time to the second to match a `-strftime` pattern would not be reliably exact. Segment duration/size metadata itself is extracted via `ffprobe` (subprocess) **after** ffmpeg exits in `stop()`, not tracked live during the recording (e.g. via polling the output directory or tailing ffmpeg's `-segment_list` manifest) — no acceptance criterion requires in-progress segment metadata to be more precise than "a row exists, `ended_at=None`," so the added complexity of live rollover-tracking wasn't justified for this milestone.
4. **The RTSP/media URI is resolved once, synchronously, inside `StartRecordingUseCase` itself** (the same `camera_gateway.connect()` → `get_stream_uri()` → `disconnect()` pattern `StartLiveStreamUseCase` uses as its fail-fast reachability check — TD-21), and passed **directly** into `FfmpegRecordingWorker`'s constructor — unlike `OnvifRtspFrameSource`, which re-resolves the URI itself on every reconnect attempt inside a `multiprocessing` child process. This is a deliberate divergence from the live-streaming pattern: `FfmpegRecordingWorker` is not a `multiprocessing` child (ffmpeg itself is already the isolated OS process handling I/O — TD-05's rationale for process isolation doesn't apply to a Python object that only supervises a subprocess handle), so there's no picklability constraint requiring re-resolution inside a spawned process. A consequence: recording has **no reconnect/backoff supervisor** in this milestone — a bad *media* connection (as opposed to bad ONVIF credentials/unreachable host, caught synchronously by the upfront check) surfaces only at `stop()` time, as an empty segment list (`StopRecordingUseCase` raises `FrameSourceUnavailableError` in that case). No acceptance criterion requires recording to auto-reconnect; this is accepted as a known limitation, not silently worked around.
5. **`RecordingSessionRegistry`** (`backend/app/application/use_cases/recording_session_registry.py`): a small shared-state class holding `{camera_id: (IRecordingWorker, first_recording_id)}` + per-camera `asyncio.Lock`s, built once in the composition root and injected into both `StartRecordingUseCase` and `StopRecordingUseCase`. Necessary because — unlike `StartLiveStreamUseCase`, which owns both `execute()` and `stop()` as methods on one stateful singleton (TD-21) — `docs/TASK_BACKLOG.md` T-062's Deliverables explicitly split start/stop into two separate use case classes, both of which need the same live worker handle across separate HTTP requests. `StartRecordingUseCase.execute()` is idempotent (already-recording → returns the existing in-progress row via a repository read) like `StartLiveStreamUseCase.execute()`; `StopRecordingUseCase.execute()` on a camera with nothing running raises a new `RecordingNotInProgressError` → `409 Conflict` (new mapping in `exception_handlers.py` — the first use of 409 in this codebase, chosen over 404 since the camera itself is not missing, only the session).

**Additional small decision**: `StartRecordingUseCase` also honors `camera.rtsp_url_override` (added at M5/TD-21) exactly as `OnvifRtspFrameSource._resolve_stream_uri` does — skipping the ONVIF gateway call entirely and using the override URL (with stored credentials injected if absent) when set. This wasn't explicitly named in the M6 prompt but was a small, direct consequence of reusing the M5 pattern; recording would otherwise silently behave inconsistently with live view for any camera relying on that override. The credential-injection helper (`_add_rtsp_credentials`) is duplicated locally in `start_recording.py` rather than imported from `infrastructure/streaming/rtsp_frame_source.py`, since application code cannot import infrastructure code (Dependency Direction Rule).

**`ListRecordingsUseCase` implemented now, ahead of its formal T-071/M7 assignment**: `docs/TASK_BACKLOG.md` assigns "`ListRecordingsUseCase` with camera/date filters" to T-071 (Epic M7), but M6's own copied-verbatim acceptance criterion #2 ("Recording metadata is queryable via `GET /recordings` immediately after stopping") cannot be demonstrated through the API without it, and the M1-era stub's signature (`camera_id`/`start`/`end` filters, already matching `IRecordingRepository.list()`) was already fixed. Treated as the minimal slice of an already-specified M1 stub needed to satisfy M6's own AC, not a duplication of T-071's fuller scope — flagged here rather than done silently, per `docs/PROMPTING_GUIDE.md`'s guidance on stopping and explaining rather than expanding scope quietly.

**Known limitation, kept open rather than silently worked around** (mirrors TD-18/20/21's precedent): neither a physical camera nor `ffmpeg`/`ffprobe` themselves are installed in the environment this milestone was implemented in (verified: `ffmpeg -version`/`ffprobe -version` → not found — the same gap TD-21 recorded for T-054, unchanged since). `backend/tests/integration/streaming/test_recording_worker_integration.py` and `test_recordings_api_integration.py` (the latter covering both T-063's start/wait/stop/list cycle and T-064's recording+live-view concurrency, against the local MP4 fixture exactly as `test_streams_api_integration.py` does for live view) are skip-guarded on `shutil.which("ffmpeg")`/`shutil.which("ffprobe")` and were not executed in this environment. What *was* verified instead: `backend/tests/unit/application/test_recording_concurrency.py` proves, with fakes, that `StartLiveStreamUseCase`'s internal registry and `RecordingSessionRegistry` share no lock or object, so nothing in the code *can* serialize the two paths against each other; all repository/use-case logic (segment persistence, idempotency, the update-vs-add split, error paths) is covered by real-SQLite integration tests and fakes-based unit tests, which do run and pass here. Reproduction steps for whoever has `ffmpeg`/`ffprobe`/a camera available: run the two skip-guarded test files directly (they'll execute instead of skip); for a live-camera check beyond the fixture, start a live stream (`POST /streams/{id}/start`), open `GET /streams/{id}/mjpeg` in a browser tab, then `POST /cameras/{id}/recording/start`, wait, `POST .../recording/stop`, and confirm both the MJPEG preview kept rendering throughout and `ffprobe` validates the resulting segment.

**Context**: `docs/IMPLEMENTATION_PLAN.md` §M6 and `docs/TASK_BACKLOG.md` Epic M6 named the Recording Worker, `StartRecordingUseCase`/`StopRecordingUseCase`, `SqlRecordingRepository`, and the recording endpoints as deliverables but — like M2/M3/M4/M5 before it (TD-18/19/20/21) — didn't specify the worker's port shape, the segment/persistence model, or how two separate use case classes would share one running worker; the M6 prompt itself explicitly named the `Recording`-shape question as open. All five surfaced only once real implementation was attempted.

**Alternatives considered**:
- *Extend `Recording` with a list of segment file paths, one row per session* — rejected: `IRecordingRepository`/`Recording` were both explicitly named as M1-fixed and "to be treated as given unless the plan identifies and justifies a specific extension need" in the M6 prompt; one-row-per-segment-file satisfies every stated acceptance criterion without touching either, and keeps `Recording` a single physical artifact per row, matching how `SqlCameraRepository`'s equivalent decisions were made incrementally rather than up front.
- *Live segment-rollover tracking (polling the output directory, or tailing ffmpeg's `-segment_list` manifest) to persist each segment the moment it completes* — rejected as disproportionate for this milestone: no acceptance criterion requires in-progress segment-by-segment visibility, and it can't be verified in an environment without `ffmpeg` anyway. Left as a natural extension point (see Future Enhancement below) rather than built and left unverified.
- *A reconnect/backoff supervisor for the Recording Worker, matching `ReconnectSupervisor`'s role for live streaming* — rejected for the same disproportionate-scope reason; no AC requires it, and TD-04's framing of the Recording Worker never mentions reconnect behavior the way TD-20's `IStreamWorker`/`ReconnectSupervisor` split does for live streaming.
- *One combined `RecordingUseCase` class with both `execute()`/`stop()` methods, matching `StartLiveStreamUseCase`'s shape* — not available here: `docs/TASK_BACKLOG.md` T-062's Deliverables explicitly name `StartRecordingUseCase`/`StopRecordingUseCase` as separate files/classes, which is what necessitated the `RecordingSessionRegistry` extraction in the first place.

**Tradeoffs**: The "resolve once, no reconnect" design (decision 4) is a real capability gap versus live streaming — a recording session that outlives a transient RTSP hiccup will simply end early rather than recover, and a slow-to-fail media connection surfaces only at `stop()` rather than `start()`. The post-hoc ffprobe-based metadata extraction (decision 3) means segment metadata is unavailable until the *entire* recording session ends, not per-segment as rollovers happen — acceptable given no AC requires otherwise, but a real limitation for any future long-running-session UI that wants live segment visibility. The ffmpeg/ffprobe-dependent tests are unverified by execution in this environment, the same category of gap TD-21 already accepted for T-054.

**Future enhancement**: Add reconnect/backoff to `FfmpegRecordingWorker` (e.g. detect subprocess exit while still expected to be running, restart with a fresh segment session) if recording sessions are expected to run long enough for transient RTSP drops to matter in practice. Add live segment-rollover persistence (polling or `-segment_list`-manifest-tailing) if a future milestone's UI needs to show completed segments before a session ends. Run the skip-guarded tests and the manual reproduction above once `ffmpeg`/`ffprobe`/a physical camera are available, converting the manual step into an automated `@pytest.mark.hardware` check if practical.

---

## TD-23: M7 Playback — range-request mechanism, route shape, and `RecordingNotFoundError`

**Decision**: Three related implementation-time decisions made while building M7 (Playback), none of which `docs/IMPLEMENTATION_PLAN.md`/`docs/TASK_BACKLOG.md` fixed precisely enough to derive without a real choice:

1. **Route shape**: `GET /recordings/{recording_id}/media`, added to the existing `create_recordings_router` (`backend/app/interfaces/api/recordings.py`) alongside `GET /recordings`, rather than a separate router file or a path nested under `/cameras/{id}/...`. `recording_id` (not `camera_id`) is the natural key here — a recording segment is independently addressable once listed — and every other recording-scoped operation already lives in this same router, so a new file would split one resource's endpoints across two modules for no benefit.
2. **Range-request mechanism: Starlette's `FileResponse`, not hand-rolled `Range` header parsing.** Reading `starlette/responses.py` directly (the installed version in `backend/.venv`) confirmed `FileResponse` already parses `Range`/`If-Range`, returns `206` with a correct `Content-Range` for a satisfiable single range, `200` for a plain `GET`, `416` for an unsatisfiable range, and sets `Accept-Ranges: bytes` by default — exactly T-070's DoD, already shipped by a dependency this project already has (Starlette, via FastAPI). Hand-rolling this would duplicate well-tested framework code for no correctness or architectural benefit. The one gap `FileResponse` doesn't cover: a missing file raises a raw `RuntimeError` at ASGI send time rather than a clean 4xx, so the route stats the file itself (`Path.is_file()`) before constructing the response — see decision 3.
3. **`RecordingNotFoundError`** (`domain/exceptions.py`), mirroring `CameraNotFoundError`, mapped to `404` in `exception_handlers.py` (same additive-mapping pattern `RecordingNotInProgressError` → `409` established at M6/TD-22). Raised from two places for a deliberately unified 404: `GetRecordingUseCase` (new, mirrors `GetCameraUseCase`) when no `Recording` row exists for the id, and inline in the playback route itself when the row exists but `Path(recording.file_path).is_file()` is false (DB row present, file missing/deleted from disk). Both failure modes mean the same thing to a client — "this recording isn't playable" — so one exception type and one status code was chosen over inventing a second, more granular error for a distinction no acceptance criterion asks for.

**File-existence check placed in the router, not the use case**: `GetRecordingUseCase` stays a pure `IRecordingRepository.get()` wrapper with no I/O beyond the repository call, keeping it unit-testable with a fake and no real filesystem access (`AGENTS.md` § Testing Expectations — domain/application layers need no real I/O). The `Path.is_file()` check instead lives in `interfaces/api/recordings.py`'s route handler, immediately before constructing `FileResponse` — consistent with `streams.py`'s MJPEG route already doing response-shaping work (JPEG encoding) directly at the interfaces layer rather than pushing it into a use case.

**Context**: `docs/IMPLEMENTATION_PLAN.md` §M7 and `docs/TASK_BACKLOG.md` Epic M7 named "a playback endpoint serving MP4 via HTTP range requests" as the deliverable but, like every milestone before it (TD-18 through TD-22), didn't fix the exact route path, the serving mechanism, or how a not-found recording should be classified — all three surfaced only once real implementation was attempted. T-071 (`ListRecordingsUseCase` filters) needed no code change — its M6-built pass-through implementation, checked against T-071's DoD, already satisfies it; `SqlRecordingRepository`'s existing filtering behavior was already proven with multi-camera/multi-day test data (`test_recording_repository_integration.py`), and the only real gap was `test_list_recordings.py`'s single-recording fixture, extended in this PR with a fake that actually filters (not just records calls) plus multi-camera/multi-day test data, per T-071's DoD literally.

**Alternatives considered**:
- *Hand-rolled `Range` header parsing in the route handler* — rejected per decision 2: it would duplicate what `FileResponse` already does correctly, adding surface area for range-parsing bugs (off-by-one byte offsets, multi-range requests, malformed headers) with no upside.
- *A distinct `RecordingFileMissingError` for the DB-row-present-but-file-absent case* — rejected: no acceptance criterion or DoD distinguishes this from "recording not found" at the HTTP layer, and a second exception type would be unused precision.
- *Resolving the file path inside the router by reading `IRecordingRepository` directly, no `GetRecordingUseCase`* — rejected for consistency with every other single-resource lookup in this codebase (`GetCameraUseCase`), and because a use case is what stays independently unit-testable with a fake, per this project's established pattern.

**Tradeoffs**: A recording actively being written to by ffmpeg (M6/TD-22's in-progress segment) is, in principle, playable through this same endpoint mid-write — `FileResponse` has no special handling for a growing file, and no acceptance criterion requires guarding against this, so it isn't. Reusing one `RecordingNotFoundError` for both "no such id" and "file missing from disk" means a log line's `exception_type` alone can't distinguish the two without reading `detail`.

**Future enhancement**: If concurrent playback-during-recording of the same in-progress segment proves visibly broken in practice (rather than just theoretically possible), either exclude in-progress (`ended_at is None`) recordings from being playable, or document the specific corruption mode observed.

---

## TD-24: M8 Analytics Pipeline Foundation — port reconciliation, orchestrator layering, event persistence, and enable/disable shape

**Decision**: Five related implementation-time decisions made while building M8 (Analytics Pipeline Foundation), none of which `docs/IMPLEMENTATION_PLAN.md`/`docs/TASK_BACKLOG.md`/`docs/ARCHITECTURE.md` fixed precisely enough to derive without a real choice:

1. **`IDetectorPlugin` supersedes and replaces `IObjectDetector`**, rather than the two coexisting. The M1 `IObjectDetector` (`detect(frame: Any) -> list[DetectionEvent]`) was never tightened from `Any` to `Frame` and had no `context` parameter, so it couldn't express `docs/ARCHITECTURE.md` §6.4's `IDetectorPlugin.process(frame, context)` shape without becoming a second, overlapping port. `backend/app/application/ports/object_detector.py` is deleted outright — nothing depended on it besides the M1 stub of `RunAnalyticsPipelineUseCase`, which this milestone rewrites anyway, and M9's `YoloObjectDetector` will implement `IDetectorPlugin` directly, so there is no remaining internal concern to narrow `IObjectDetector` to.
2. **`AnalyticsOrchestrator` stays at `infrastructure/analytics/orchestrator.py` (per `docs/FOLDER_STRUCTURE.md`), but `RunAnalyticsPipelineUseCase` never imports it.** `docs/ARCHITECTURE.md` §5's prose calls the orchestrator "(Application layer)," but its own concrete file path (both there and in `docs/IMPLEMENTATION_PLAN.md` §M8's Files list) is `infrastructure/analytics/`, and `application/` may only import `domain/` — the import-linter `layers` contract (TD-17) forbids `application` importing `infrastructure` regardless of how few real infrastructure dependencies a given infrastructure-layer module happens to have. Rather than move the orchestrator to `application/` (contradicting the explicit Deliverables path), `RunAnalyticsPipelineUseCase` takes a plain `process_frame: Callable[[Frame], Awaitable[list[DetectionEvent]]]` constructor argument; the composition root passes `AnalyticsOrchestrator.process` (a bound method). This mirrors the existing `build_stream_worker`/`build_recording_worker` callable-injection precedent (TD-21/TD-22) for exactly the same reason — a use case needing behavior from a concrete infrastructure class it isn't allowed to import directly. `docs/ARCHITECTURE.md` §5 is corrected in this PR to describe the orchestrator as Infrastructure layer and name this callable-injection mechanism.
3. **`SupervisedFrameSource`** (`infrastructure/streaming/supervised_frame_source.py`) — a new `IFrameSource` adapter wrapping any `IFrameSource` in `ReconnectSupervisor` and re-exposing it as `IFrameSource`. `docs/IMPLEMENTATION_PLAN.md` §M8's Constraints require analytics to "consume frames through that same supervised path" M5's live-view/M6's recording already use, without modifying or bypassing `ReconnectSupervisor`/`StreamWorker` — but T-086's own Testing Expectations require the regression test to run directly against a raw `Mp4FileFrameSource` and a fake `IFrameSource`, which only works if `RunAnalyticsPipelineUseCase` depends on the `IFrameSource` port, not `IStreamWorker` (a different, incompatible port shape) or a concrete `StreamWorker`. `ReconnectSupervisor` (TD-20) was deliberately split out from `StreamWorker`'s `multiprocessing` wrapper specifically so it could be reused directly, in-process — this adapter is that reuse. No process isolation was added for analytics in this milestone: no M8 acceptance criterion requires it, and the only plugin that exists is a no-op — `docs/ARCHITECTURE.md`'s Component Responsibilities table is annotated to note this until a real, CPU-bound M9+ plugin actually needs it.
4. **`IEventRepository`** (`application/ports/event_repository.py`) — additive port for T-083, mirroring `IRecordingRepository`'s `add`/`list` shape (the same precedent TD-18–TD-22 established for every prior milestone's undocumented persistence gap). `SqlEventRepository` + new `DetectionEventRow` table (`bounding_box_json`/`metadata_json` as JSON columns, mirroring `CameraRow.stream_profiles_json`). `DetectionEvent.camera_id: UUID` (M1-fixed, required, no default) has no real onboarded `Camera` to point at for M8's bare `source_id="mp4-demo"` string — `NoOpDetectorPlugin` derives it via `uuid5(NAMESPACE_DNS, frame.source_id)` (deterministic, so the same source always maps to the same id) rather than a random one, and preserves the literal `source_id` in `metadata` for exact traceability. This is a documented derivation for a demo/non-camera source, not a guess about real-world camera behavior (distinct from TD-18's fabrication ban, which was about guessing unknowable vendor firmware behavior).
5. **Enable/disable per source (T-085)**: `RunAnalyticsPipelineUseCase` is bound to one `frame_source` at construction and owns that source's full `start()`/`frames()`/`stop()` lifecycle itself inside `execute()` (the M1 stub's "frame_source is already started" precondition didn't survive real implementation — a self-contained lifecycle is simpler and is what T-086's test needs). It carries its own `enabled` flag (default `True`, toggled by `enable()`/`disable()`): frames are always drained from `frame_source.frames()`, but only processed/published while enabled, so disabling never stops or restarts the source. A new `AnalyticsSessionRegistry` (`application/use_cases/analytics_session_registry.py`) holds one such use case + its background `asyncio.Task` per `source_id`, mirroring `StartLiveStreamUseCase`'s internal per-camera registry (TD-21) rather than `RecordingSessionRegistry`'s separate-registry-plus-two-use-case-classes shape (TD-22) — T-085, unlike T-062, names only one use case file. Keyed by `source_id: str`, not a `Camera` UUID, since M8 has no ONVIF camera dependency (`docs/IMPLEMENTATION_PLAN.md`'s Milestone Dependency Graph: M8 depends only on M1/M2). Only one source is wired in this milestone: `"mp4-demo"`, the committed fixture.

**Context**: `docs/IMPLEMENTATION_PLAN.md` §M8 and `docs/TASK_BACKLOG.md` Epic M8 named the orchestrator, event bus, event persistence, WebSocket channel, and enable/disable API as deliverables but — like every milestone before it (TD-18 through TD-23) — didn't fix the exact port relationships, layering mechanics, persistence shape, or enable/disable state-holding pattern; the M8 run prompt itself flagged the `IDetectorPlugin`/`IObjectDetector` relationship and the event persistence port as open, real decisions to make. The orchestrator-layering conflict (decision 2) and the supervised-path constraint (decision 3) were not anticipated by any planning document — they surfaced only once the import-linter contract and T-086's literal test design were checked against each other.

**Alternatives considered**:
- *Keep `IObjectDetector` alongside `IDetectorPlugin`, narrowed to an internal M9 YOLO-only concern* — rejected: nothing in this milestone or the documented M9 plan actually needs two separate detector-facing ports: M9's `YoloObjectDetector` is named as implementing "the detector plugin interface" directly in `docs/IMPLEMENTATION_PLAN.md` §M9, so keeping `IObjectDetector` around would be dead, overlapping scaffolding, not a real narrowing.
- *Move `AnalyticsOrchestrator` to `application/`* — rejected as a bigger deviation from this milestone's explicit Deliverables path than the callable-injection fix, and it would leave `docs/FOLDER_STRUCTURE.md`'s `infrastructure/analytics/` folder description (which already lists the orchestrator) wrong instead of right.
- *Give `RunAnalyticsPipelineUseCase` an `IStreamWorker` parameter instead of `IFrameSource`* — rejected because it directly contradicts T-086's Testing Expectations text, which names `Mp4FileFrameSource` (an `IFrameSource`) and a fake `IFrameSource` double as what the regression test must run against.
- *Full `multiprocessing` process isolation for the Analytics Worker now, matching `docs/ARCHITECTURE.md`'s Component Map* — rejected as speculative generality for a no-op plugin; revisit at M9 once a real, CPU-bound detector exists and an acceptance criterion actually needs it.
- *A random UUID for the no-op plugin's `DetectionEvent.camera_id`* — rejected in favor of a deterministic `uuid5` derivation so the same `source_id` always maps to the same id, making events from repeated runs of the same demo source correlatable.

**Tradeoffs**: The `process_frame: Callable[...]` indirection (decision 2) is one more layer between `RunAnalyticsPipelineUseCase` and what it actually calls, compared to holding the orchestrator directly — accepted because the alternative is either violating the Dependency Direction Rule or moving a file `docs/FOLDER_STRUCTURE.md` already places elsewhere. In-process (non-isolated) analytics consumption (decision 3) means a future real CPU-bound plugin (M9+) will need a design revisit — flagged, not silently deferred. The `uuid5`-derived `camera_id` (decision 4) means the no-op plugin's events cannot be joined against a real `camera` table row (there isn't one for `"mp4-demo"`) — acceptable since no M8 acceptance criterion requires that join, only that events are queryable.

**Future enhancement**: Add process isolation to the Analytics Worker (matching `docs/ARCHITECTURE.md`'s original Component Map) once a real, CPU-bound detector plugin (M9's YOLO) exists and profiling shows it stalls the API process or contends with Stream Worker decode. Add per-`source_id` filtering to the `/ws/analytics/events` channel once M9+ wires multiple concurrently-enabled real camera sources (M8 only ever has one).

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
