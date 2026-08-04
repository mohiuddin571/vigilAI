# VigilAI

A Video Management System (VMS) with integrated video analytics: ONVIF camera onboarding, live streaming, recording/playback, and an analytics pipeline (object detection & classification, color detection, loitering detection, missing object detection, and license plate recognition) that runs identically over ONVIF cameras, raw RTSP streams, and local video files.

Built as a production-quality prototype demonstrating Clean Architecture applied to a real-time video/AI system.

> **Status**: 🚧 M0 (Project Scaffolding & Tooling), M1 (Domain & Application Core), and M3 (ONVIF Camera Onboarding) complete — M3 landed ahead of M2 since it's independent of it (see `docs/IMPLEMENTATION_PLAN.md` §M3 "Dependencies"). Next up: M2 (Frame Source Abstraction). See [Project State](./docs/AI_PROJECT_CONTEXT.md#9-project-state).

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

The current milestone (M0/M1) is a backend health check and a frontend page that displays it — there's no camera/video functionality to run yet (that starts at M2). These steps get that running.

### Step 1 — One-time machine setup

Skip anything you already have installed.

| Tool | Check if installed | Install (macOS) |
|---|---|---|
| Git | `git --version` | `brew install git` |
| [`uv`](https://docs.astral.sh/uv/) (Python 3.12 + backend deps) | `uv --version` | `brew install uv` |
| Node.js 22.12+ (frontend) | `node --version` | `brew install nvm` then `nvm install --lts && nvm use --lts` |
| FFmpeg | `ffmpeg -version` | `brew install ffmpeg` — **not needed yet**, only from M2/M5 onward |

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

### Stopping the app

Press `Ctrl+C` in each terminal (backend and frontend) to stop them. If you started them in the background instead and lost track of them:

```bash
lsof -i :8000   # find the backend process
lsof -i :5173   # find the frontend process
kill <PID>      # PID is in the second column of the lsof output
```

### Running Without a Camera

VigilAI is designed to be fully demonstrable without physical hardware: point a source at a local MP4 file and the entire analytics pipeline runs identically to how it would against a live camera. Instructions land with M2 — see [IMPLEMENTATION_PLAN.md](./docs/IMPLEMENTATION_PLAN.md#m2--frame-source-abstraction--mp4-file-adapter).

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
