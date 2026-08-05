# VigilAI

A Video Management System (VMS) with integrated video analytics: ONVIF camera onboarding, live streaming, recording/playback, and an analytics pipeline (object detection & classification, color detection, loitering detection, missing object detection, and license plate recognition) that runs identically over ONVIF cameras, raw RTSP streams, and local video files.

Built as a production-quality prototype demonstrating Clean Architecture applied to a real-time video/AI system.

> **Status**: 🚧 M0 (Project Scaffolding & Tooling), M1 (Domain & Application Core), M2 (Frame Source Abstraction), M3 (ONVIF Camera Onboarding), M4 (ONVIF Configuration), M5 (Live Streaming + Auto-Reconnect), M6 (Recording), M7 (Playback), M8 (Analytics Pipeline Foundation), and M9 (YOLO Integration — Object Detection & Classification) complete. Next up: Object Tracking. See [Project State](./docs/AI_PROJECT_CONTEXT.md#9-project-state).

---

## Overview

VigilAI onboards IP cameras over [ONVIF](https://www.onvif.org/), reads and updates their encoder configuration, streams and records video, and runs a pluggable analytics pipeline over the resulting frames. The analytics pipeline is built around a single abstraction — a **frame source** — that makes an ONVIF camera, a raw RTSP stream, and a prerecorded MP4 file indistinguishable to every detector downstream. That decoupling is the architectural centerpiece of this project; see [ARCHITECTURE.md](./docs/ARCHITECTURE.md) §5 for how it's enforced.

### Core Capabilities

**Video Management**
- ONVIF camera onboarding via IP + username + password
- Read camera configuration (resolution, FPS, bitrate, codec)
- Update supported camera configuration
- Live video streaming with automatic reconnection
- Video recording
- Playback of recorded video

**Video Analytics**
- Object Detection
- Object Classification
- Color Detection
- Loitering Detection
- Missing Object Detection
- License Plate Recognition (OCR)

---

## Architecture at a Glance

Clean Architecture, four layers, dependencies point inward only:

```
Interfaces (FastAPI + WebSocket)
    → Infrastructure (ONVIF, FFmpeg/OpenCV, YOLO, EasyOCR, SQL)
        → Application (use cases + ports)
            → Domain (entities, value objects — zero framework dependencies)
```

The full picture, including diagrams and key flows, is in [ARCHITECTURE.md](./docs/ARCHITECTURE.md).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Object detection / classification / tracking | Ultralytics YOLOv8 (ByteTrack) |
| OCR (license plates) | EasyOCR |
| Video ingestion / recording | FFmpeg, OpenCV |
| ONVIF client | `onvif-zeep-async` |
| Persistence | SQLModel (SQLite in dev, Postgres-ready) |
| Config | `pydantic-settings` |
| Logging | `structlog` (structured/JSON) |

Full reasoning for every choice, including tradeoffs and rejected alternatives: [TECHNICAL_DECISIONS.md](./docs/TECHNICAL_DECISIONS.md).

---

## Getting Started

These steps get the backend and frontend running. Camera onboarding/configuration (M3/M4) needs a real or simulated ONVIF camera to do anything beyond what's below; the local MP4 debug stream (M2, Step 6) needs no camera at all.

### Step 1 — One-time machine setup

Skip anything you already have installed.

| Tool | Check if installed | Install (macOS) |
|---|---|---|
| Git | `git --version` | `brew install git` |
| [`uv`](https://docs.astral.sh/uv/) (Python 3.12 + backend deps) | `uv --version` | `brew install uv` |
| Node.js 22.12+ (frontend) | `node --version` | `brew install nvm` then `nvm install --lts && nvm use --lts` |
| FFmpeg | `ffmpeg -version` | `brew install ffmpeg` — a genuine runtime dependency from **M6 onward**: the Recording Worker invokes the `ffmpeg` CLI directly as a subprocess for stream-copy segment muxing, and `ffprobe` to verify/measure finalized segments (TD-04, TD-22). Before M6, it was needed only as a dev/test tool to serve a local test RTSP stream when validating live view/reconnect without the physical camera (`OnvifRtspFrameSource`/`RawRtspFrameSource` decode RTSP via OpenCV's bundled FFmpeg backend, a separate code path — TD-21) |

`uv` and `nvm` manage their own tool versions per-project, so you don't need to separately install Python or pin a global Node version.

### Step 2 — Get the code

```bash
git clone https://github.com/mohiuddin571/vigilAI.git
cd vigilAI
```

(If you already have the repo, just `git pull` instead.)

### Step 3 — Configure

Every time you set up the repo on a machine for the first time, copy the example env file:

```bash
cp .env.example .env
```

`ENVIRONMENT` and `CAMERA_CREDENTIAL_ENCRYPTION_KEY` are required — the backend fails fast at startup if `.env` is missing or either is unset. `ENVIRONMENT` defaults to `development` in the example file; `CAMERA_CREDENTIAL_ENCRYPTION_KEY` has no default (it's the key camera passwords are encrypted with at rest — TD-15, TD-18) and must be generated per machine:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste the output into `.env` as `CAMERA_CREDENTIAL_ENCRYPTION_KEY=...`. See `.env.example` for the full list of settings.

### Step 4 — Run the backend

Open a terminal at the repo root:

```bash
cd backend
uv sync                              # installs dependencies (only needed once, or after pulling new changes)
uv run uvicorn app.main:app --reload
```

Leave this terminal running. You should see `Uvicorn running on http://127.0.0.1:8000`. Verify it in a second terminal:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### Step 5 — Run the frontend

Open a **new, separate terminal** at the repo root (keep the backend terminal running):

```bash
cd frontend
npm install    # only needed once, or after pulling new changes
npm run dev
```

Leave this terminal running too. Open **http://localhost:5173** in your browser — you should see a "VigilAI" card reading "Backend: ok". The frontend proxies `/health` to the backend on port 8000, so the backend must already be running (Step 4) for this to show `ok` instead of an error.

### Step 6 — Run the local MP4 debug stream (no camera needed)

With the backend running (Step 4), this exercises the M2 Stream Worker end to end against the committed sample fixture (`backend/tests/fixtures/sample.mp4`) — no ONVIF camera involved:

```bash
curl -X POST http://localhost:8000/debug/streams/mp4/start
curl http://localhost:8000/debug/streams/mp4/status   # state, and the latest frame's metadata
curl -X POST http://localhost:8000/debug/streams/mp4/stop
```

`status` should move from `"connecting"` to `"connected"`, with `latest_frame.sequence` increasing on repeated calls at roughly the fixture's frame rate. This is dev/demo tooling proving the frame source + reconnect-supervised Stream Worker work (T-025) — it's not the real browser live-view (Step 7 below), which goes over MJPEG-over-HTTP against a resolved camera stream.

Note: `backend/tests/fixtures/sample.mp4` is a synthetically generated clip (`scripts/generate_sample_fixture.py`), not real footage — see [TECHNICAL_DECISIONS.md](./docs/TECHNICAL_DECISIONS.md) TD-20 for why, and for the known limitation this leaves for later analytics milestones (M9+).

### Step 7 — Live view of an onboarded camera (M5, needs a real or ONVIF-simulator camera)

With a camera onboarded (via the frontend's "Add Camera" form, or `POST /cameras` directly — see M3 above), open the frontend (Step 5) — the "Live View" card lists onboarded cameras and shows an `<img>`-based MJPEG preview with a connected/reconnecting/failed indicator once you click **Connect**. Equivalently, from the API directly:

```bash
curl -X POST http://localhost:8000/streams/{camera_id}/start
curl http://localhost:8000/streams/{camera_id}/status
# open http://localhost:8000/streams/{camera_id}/mjpeg directly in a browser tab
curl -X POST http://localhost:8000/streams/{camera_id}/stop
```

The status WebSocket (`ws://localhost:8000/ws/streams/{camera_id}/status`) pushes the same status roughly once a second — this is what the frontend's connection indicator subscribes to. To see the reconnect behavior described in [TECHNICAL_DECISIONS.md](./docs/TECHNICAL_DECISIONS.md) TD-21, interrupt the camera's network path (or kill a local test RTSP stream) while connected and watch `status`/the WS channel move to `"reconnecting"` and back to `"connected"`.

### Step 8 — Object detection overlay (M9, works on the MP4 demo or a real camera)

Once a stream is connected (Step 7, or the MP4 debug stream's `source_id="mp4-demo"`), the frontend's Live View automatically enables analytics for that source and overlays live YOLO detection boxes/labels. The very first detection anywhere on a machine downloads `yolov8n.pt` (~6MB) into `storage/models/` (gitignored, cached thereafter) — this needs network access once. Equivalently, from the API directly:

```bash
curl -X POST http://localhost:8000/analytics/{source_id}/enable   # source_id: "mp4-demo" or a camera's id
curl http://localhost:8000/analytics/{source_id}/status
curl http://localhost:8000/analytics/events                       # persisted detections, filterable
# ws://localhost:8000/ws/analytics/events pushes each detection live
```

See [TECHNICAL_DECISIONS.md](./docs/TECHNICAL_DECISIONS.md) TD-25 for the model/execution-strategy choices, the achieved FPS on the Mac Mini, and `scripts/benchmark_yolo_fps.py` for reproducing that measurement.

### Stopping the app

Press `Ctrl+C` in each terminal (backend and frontend) to stop them. If you started them in the background instead and lost track of them:

```bash
lsof -i :8000   # find the backend process
lsof -i :5173   # find the frontend process
kill <PID>      # PID is in the second column of the lsof output
```

---

## Project Documentation

This repository is documentation-first: the design was fully specified before implementation began, and the documents below are the source of truth the code is built against.

| Document | What it covers |
|---|---|
| [AGENTS.md](./AGENTS.md) | How to work in this repository — conventions, standards, PR/commit rules, rules for AI assistants |
| [TASKS.md](./TASKS.md) | Living implementation checklist (Completed / In Progress / Remaining) |
| [prompts/00-README.md](./prompts/00-README.md) | Reusable Claude Code prompt templates per milestone, plus the full AI development workflow |
| [AI_PROJECT_CONTEXT.md](./docs/AI_PROJECT_CONTEXT.md) | Full project context — start here if you're new (human or AI) |
| [ARCHITECTURE.md](./docs/ARCHITECTURE.md) | Component responsibilities, diagrams, key flows, technology rationale |
| [FOLDER_STRUCTURE.md](./docs/FOLDER_STRUCTURE.md) | Repo layout, folder ownership, dependency direction rules |
| [IMPLEMENTATION_PLAN.md](./docs/IMPLEMENTATION_PLAN.md) | Milestones — goals, deliverables, acceptance criteria, dependencies |
| [TASK_BACKLOG.md](./docs/TASK_BACKLOG.md) | Fine-grained prioritized backlog with Definition of Done per task |
| [TECHNICAL_DECISIONS.md](./docs/TECHNICAL_DECISIONS.md) | Every significant technical decision, alternatives considered, tradeoffs |
| [PROMPTING_GUIDE.md](./docs/PROMPTING_GUIDE.md) | How implementation prompts for this project should be written |

---

## Design Principles

- **Clean Architecture** — business logic has zero dependency on frameworks or I/O; everything swappable sits behind an interface (a "port").
- **SOLID** — most visibly Dependency Inversion (use cases depend on abstractions, not concrete ONVIF/FFmpeg/YOLO code) and Interface Segregation (narrow, single-purpose ports rather than one god-interface).
- **Source-agnostic analytics** — the same pipeline runs over ONVIF cameras, raw RTSP, and local MP4 files, enforced by a permanent regression test (see [IMPLEMENTATION_PLAN.md](./docs/IMPLEMENTATION_PLAN.md#m8--analytics-pipeline-foundation), T-086 in the backlog).
- **Explicit tradeoffs over silent shortcuts** — every deliberate scope cut or "good enough for now" choice is written down in [TECHNICAL_DECISIONS.md](./docs/TECHNICAL_DECISIONS.md) rather than left implicit in the code.

---

## Roadmap

See [IMPLEMENTATION_PLAN.md](./docs/IMPLEMENTATION_PLAN.md) for the full milestone sequence (M0–M16). High-level shape: scaffolding → domain/application core → frame-source abstraction proven on local video → ONVIF onboarding/config → live streaming/reconnect → recording/playback → analytics pipeline foundation → the six required analytics capabilities → integrated frontend → hardening → Docker (time-permitting, explicitly last).

---

## License

`<TBD>`
