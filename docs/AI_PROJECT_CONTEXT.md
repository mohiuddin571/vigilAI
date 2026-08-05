# AI_PROJECT_CONTEXT.md

**Purpose of this file**: this is the single document a future AI assistant (Claude Code or otherwise) should read first, before touching any code. It is the durable context that survives across sessions — everything else (architecture, folder structure, plan, backlog) is downstream of what's summarized here. If something in another doc ever contradicts this file, treat it as a signal the docs have drifted and flag it rather than silently picking one.

---

## 1. What This Project Is

**VigilAI** is a prototype Video Management System (VMS) with integrated video analytics, built as a take-home technical evaluation for a video surveillance/analytics company. It is not a toy CLI script and not a production SaaS — it's a **production-quality prototype**: real architecture, real engineering discipline, intentionally scoped down on ops concerns (auth, scaling, multi-tenancy) that a real deployment would need but a prototype doesn't need to prove competence.

**What is being evaluated** (keep this in mind for every decision): ability to learn an unfamiliar domain (ONVIF, VMS internals) independently, research and apply industry standards correctly, design a scalable/maintainable architecture, follow engineering best practices, ship a working prototype, make and justify sound technical tradeoffs, and write clean, well-documented code. Architecture quality and reasoning are being graded at least as heavily as raw feature completeness.

---

## 2. Required Capabilities (the contract)

**Core VMS**:
- ONVIF camera onboarding — authenticate via IP + username + password.
- Read camera configuration: resolution, FPS, bitrate, codec.
- Update supported camera configuration.
- Live video streaming.
- Automatic reconnection on stream/connection loss.
- Video recording.
- Playback of recorded video.

**Video Analytics** (must work identically regardless of frame source):
- Object Detection
- Object Classification
- Color Detection
- Loitering Detection
- Missing Object Detection
- License Plate Recognition (OCR)

**Non-negotiable architectural constraint**: analytics must not be coupled to ONVIF. The pipeline must run over ONVIF cameras, raw RTSP streams, and local MP4 files without any change to analytics code. See [ARCHITECTURE.md](./ARCHITECTURE.md) §5 for the mechanism (`IFrameSource` port).

---

## 3. Environment & Constraints

- **Dev machine**: Mac Mini (Apple Silicon assumed — matters for OCR/inference backend choices, e.g. PyTorch MPS).
- **Backend**: Python, FastAPI.
- **Frontend**: React.
- **Detection framework**: Ultralytics YOLO (required).
- **Also required**: OpenCV where appropriate, FFmpeg for streaming/recording.
- **Hardware**: evaluators provide exactly **one physical ONVIF camera**. The architecture must support multiple cameras even though only one will be tested live.
- **Demo without hardware**: the system must be able to run analytics against prerecorded local MP4 files — this is the primary development/demo path, not a fallback bolted on later.
- **Docker**: not required initially; added at the end only if time permits. Do not let Docker block core feature work.

---

## 4. Architectural Summary (see ARCHITECTURE.md for full detail)

Clean Architecture, four layers, strict inward dependency direction:

1. **Domain** — pure business entities/rules, no framework imports.
2. **Application** — use cases + **ports** (abstract interfaces like `IFrameSource`, `ICameraGateway`, `IDetectorPlugin`, `IRecordingRepository`).
3. **Infrastructure** — concrete adapters implementing ports: ONVIF client, FFmpeg/OpenCV frame sources, YOLO/EasyOCR detectors, SQL persistence.
4. **Interfaces** — FastAPI routers + WebSocket hub translating HTTP/WS to use-case calls.

The load-bearing abstraction is `IFrameSource`: `OnvifRtspFrameSource`, `RawRtspFrameSource`, and `Mp4FileFrameSource` all yield the same `Frame` domain object, so the `AnalyticsOrchestrator` and every detector plugin depend on that interface only — never on ONVIF or RTSP specifics.

Concurrency: one OS process per active stream (`multiprocessing`), FastAPI stays asyncio-only. See [TECHNICAL_DECISIONS.md](./TECHNICAL_DECISIONS.md) TD-05.

---

## 5. Technology Choices (already decided — do not re-litigate without reason)

| Concern | Choice |
|---|---|
| ONVIF client | `onvif-zeep-async` |
| Video ingestion | FFmpeg (subprocess) for RTSP/recording, OpenCV for frame decode |
| Object detection/classification/tracking | Ultralytics YOLOv8 + built-in ByteTrack |
| OCR (LPR) | EasyOCR |
| Persistence | SQLModel over SQLite (dev), Postgres-ready |
| Live preview | MJPEG-over-HTTP (MVP) + WebSocket for events |
| DI | Manual composition root (`app/core/container.py`), not a DI framework |
| Config | `pydantic-settings` + `.env`, one `Settings` object |
| Logging | `structlog`, JSON, correlated by `camera_id`/`trace_id` |
| Frontend state | React Query (server state) + Zustand (UI state) |
| Frontend styling | Tailwind CSS |

Full reasoning, alternatives considered, and tradeoffs for each: [TECHNICAL_DECISIONS.md](./TECHNICAL_DECISIONS.md). **Do not silently swap a technology choice** — if a choice turns out to be wrong, update TECHNICAL_DECISIONS.md with a new entry explaining why, don't just change the code.

---

## 6. Glossary (domain terms a newcomer to VMS/ONVIF won't know)

- **ONVIF** — Open Network Video Interface Forum; an industry standard (SOAP/WSDL-based) for IP camera interoperability, covering device discovery, media configuration, and streaming.
- **WS-Discovery** — the ONVIF/UPnP mechanism for auto-discovering devices on a local network via multicast; not the primary onboarding path here (IP/credentials are), but a documented future enhancement.
- **WS-UsernameToken** — the SOAP authentication scheme ONVIF uses (digest-based, not plain HTTP basic auth).
- **ONVIF Media Profile** — a named bundle of video source + encoder configuration a camera exposes (e.g. "MainStream", "SubStream"); `GetProfiles` lists them, `GetStreamUri` resolves one to an RTSP URL.
- **RTSP** — Real Time Streaming Protocol; the control protocol cameras use to negotiate a media stream (actual video typically rides over RTP).
- **Codec** — video compression format (e.g. H.264/H.265) reported/configured via ONVIF's video encoder configuration.
- **Bitrate** — encoded stream data rate (kbps), one of the configurable encoder parameters.
- **Loitering Detection** — flagging an object/person that remains within a defined zone longer than a threshold duration; requires per-object identity tracking across frames, not just per-frame detection.
- **Missing Object Detection** — flagging when an object present in a baseline/reference view disappears (e.g. a monitored asset removed from frame) for longer than a threshold.
- **LPR / ALPR** — (Automatic) License Plate Recognition: detect a plate region, then OCR the plate text.
- **MJPEG** — Motion JPEG; a simple "multipart HTTP" streaming format any browser can render via an `<img>` tag, used here for the live-view MVP.
- **HLS** — HTTP Live Streaming; segment-based adaptive streaming, noted as a future upgrade over MJPEG.
- **Frame Source** — this project's abstraction (`IFrameSource`) unifying ONVIF cameras, raw RTSP, and MP4 files behind one interface for the analytics pipeline.

---

## 7. Non-Goals (explicitly out of scope — do not implement unless asked)

- Authentication/authorization (RBAC, login) for the VMS itself.
- Multi-tenant support.
- Horizontal scaling / multi-node deployment.
- Cloud object storage for recordings (filesystem is fine).
- A message broker (Redis/Kafka) — in-process event bus is sufficient.
- GPU cluster inference scaling.
- Mobile apps.
- Alerting integrations (email/SMS/webhooks) beyond the in-app event feed, unless explicitly requested later.

If a future prompt seems to ask for one of these, confirm scope before building it — it's more likely a misunderstanding than a real requirement change.

---

## 8. Coding Standards (apply to every file, every milestone)

- Type hints everywhere; no bare `Any` without justification.
- Pydantic (v2) for all data validation at boundaries — API schemas, config, value objects where useful.
- Structured logging (`structlog`) — no bare `print()`.
- All configuration through `pydantic-settings`; no direct `os.environ` reads outside `app/core/config.py`.
- Async where I/O-bound (API handlers, DB calls, WebSocket); sync/process-isolated where CPU-bound (decode, inference) — see TD-05.
- Every use case and domain object must be unit-testable without a running server, a real camera, or real FFmpeg — that's the entire point of the port boundary. If a test needs to mock `cv2` or `onvif_zeep_async` directly, the abstraction has leaked and needs fixing before the test is written.
- Docstrings only where the *why* isn't obvious from the name/types; no restating the signature in prose.

---

## 9. Project State

> Update this section as work progresses. Future AI sessions should read this before assuming anything about what exists.

- **Current milestone**: M0–M13 complete (scaffolding, domain/application core, frame source abstraction, ONVIF onboarding/config, live streaming + auto-reconnect, recording, playback, analytics pipeline foundation, YOLO object detection & classification + tracking, color detection, loitering detection, missing object detection, license plate recognition). See [TASKS.md](../TASKS.md) for the live checklist — this section is a coarser summary and can lag it briefly.
- **What exists**: The full documentation set, plus a working backend (`backend/app/`) and frontend (`frontend/src/`) implementing M0–M13's deliverables — camera onboarding/config over ONVIF, the `IFrameSource`/`IStreamWorker` abstractions, MP4 and RTSP frame sources, browser live view (MJPEG + WS status) with automatic reconnect, FFmpeg stream-copy recording to MP4 segments (`IRecordingWorker`, `SqlRecordingRepository`, start/stop/list API), HTTP range-request playback of recorded segments with a filterable recordings browser + native `<video>` player in the frontend, the `IDetectorPlugin`/`AnalyticsOrchestrator`/`EventBus`/`SqlEventRepository`/analytics WebSocket channel/per-source enable-disable API proving analytics runs identically regardless of frame source (the permanent T-086 regression test), a real `YoloObjectDetector` plugin (detection + classification + ByteTrack tracking in one inference call) analytics-enableable on both the MP4 demo fixture and real onboarded cameras, a `ColorDetector` plugin surfacing a dominant color label alongside each detection, `AnalyticsZone` polygon CRUD (`/zones`) + a frontend `ZoneEditor` + a `LoiteringDetector` plugin emitting one event per qualifying dwell period per zone/track, a `MissingObjectDetector` plugin flagging a baseline-registered object's absence past a per-zone threshold, and now a `LicensePlateRecognizer` plugin (classical-CV `PlateLocalizer` + `EasyOcrReader`, non-blocking queued OCR execution) emitting recognized plate text + confidence — see TECHNICAL_DECISIONS.md TD-22 through TD-30.
- **What's next**: Frontend Dashboard Integration (M14) per [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) and [TASKS.md](../TASKS.md).
- **Known open questions**: exact make/model of the evaluator-provided ONVIF camera is unknown until evaluation day — onboarding/config-read/config-update code should be validated against ONVIF's spec plus a mock/test camera or camera simulator, not assumptions about one vendor's quirks.

---

## 10. How to Use the Other Documents

| Document | Read it when you need to... |
|---|---|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Understand component responsibilities, data flow, diagrams |
| [FOLDER_STRUCTURE.md](./FOLDER_STRUCTURE.md) | Know where a new file belongs and what it's allowed to import |
| [TECHNICAL_DECISIONS.md](./TECHNICAL_DECISIONS.md) | Understand *why* a technology/pattern was chosen, and its tradeoffs |
| [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) | Know what milestone comes next and its acceptance criteria |
| [TASK_BACKLOG.md](./TASK_BACKLOG.md) | Find a specific prioritized task with its Definition of Done |
| [PROMPTING_GUIDE.md](./PROMPTING_GUIDE.md) | Write a well-scoped Claude Code prompt for the next chunk of work |
| [README.md](../README.md) | Get the outward-facing project overview |
