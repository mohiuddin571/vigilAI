# VigilAI

A Video Management System (VMS) with integrated video analytics: ONVIF camera onboarding, live streaming, recording/playback, and an analytics pipeline (object detection & classification, color detection, loitering detection, missing object detection, and license plate recognition) that runs identically over ONVIF cameras, raw RTSP streams, and local video files.

Built as a production-quality prototype demonstrating Clean Architecture applied to a real-time video/AI system.

> **Status**: 🚧 Planning complete, implementation not yet started. See [Project State](./docs/AI_PROJECT_CONTEXT.md#9-project-state).

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

> Setup instructions will be filled in as milestone M0 (project scaffolding) completes — see [IMPLEMENTATION_PLAN.md](./docs/IMPLEMENTATION_PLAN.md#m0--project-scaffolding--tooling). Placeholders below will become real, tested commands.

### Prerequisites

- Python `<version TBD>`
- Node.js `<version TBD>`
- FFmpeg installed and on `PATH`
- (Optional) an ONVIF-compatible IP camera on the local network — the system also runs fully against local MP4 files without any camera

### Backend

```bash
# TODO: fill in once M0 lands
cd backend
# uv sync / pip install -e . / poetry install — TBD
# uvicorn app.main:app --reload
```

### Frontend

```bash
# TODO: fill in once M0 lands
cd frontend
npm install
npm run dev
```

### Configuration

Copy `.env.example` to `.env` and fill in values — see `.env.example` for the current list of required settings once M0 lands.

### Running Without a Camera

VigilAI is designed to be fully demonstrable without physical hardware: point a source at a local MP4 file and the entire analytics pipeline runs identically to how it would against a live camera. Instructions land with M2 — see [IMPLEMENTATION_PLAN.md](./docs/IMPLEMENTATION_PLAN.md#m2--frame-source-abstraction--mp4-file-adapter).

---

## Project Documentation

This repository is documentation-first: the design was fully specified before implementation began, and the documents below are the source of truth the code is built against.

| Document | What it covers |
|---|---|
| [AGENTS.md](./AGENTS.md) | How to work in this repository — conventions, standards, PR/commit rules, rules for AI assistants |
| [TASKS.md](./TASKS.md) | Living implementation checklist (Completed / In Progress / Remaining) |
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
