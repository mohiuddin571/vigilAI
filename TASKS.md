# TASKS.md — Living Implementation Checklist

Quick-glance status only. This is an index into [docs/IMPLEMENTATION_PLAN.md](./docs/IMPLEMENTATION_PLAN.md) (milestone detail: goals, deliverables, acceptance criteria) and [docs/TASK_BACKLOG.md](./docs/TASK_BACKLOG.md) (task-level detail: priority, complexity, dependencies, Definition of Done) — it doesn't replace either. Milestone IDs (`M0`–`M16`) in parentheses are how a line here maps back to that detail.

**How to maintain this file**: when a task starts, move its line from Remaining to In Progress; when it meets its acceptance criteria per TASK_BACKLOG.md, move it to Completed. Update in the same PR as the work, per [AGENTS.md](./AGENTS.md) § Pull Request Guidelines.

---

# Completed

- [x] Initial architecture & technical decisions (`docs/ARCHITECTURE.md`, `docs/TECHNICAL_DECISIONS.md`)
- [x] Implementation plan & task backlog (`docs/IMPLEMENTATION_PLAN.md`, `docs/TASK_BACKLOG.md`)
- [x] Documentation organized into `docs/`, README kept at root
- [x] AI agent workflow docs (`AGENTS.md`, `TASKS.md`)
- [x] AI prompt workflow templates (`prompts/`)
- [x] Backend & Frontend Foundation (M0)
- [x] Domain & Application Core (M1)
- [x] ONVIF Camera Onboarding — IP + credential authentication (M3)
- [x] Camera Configuration — read/update resolution, FPS, bitrate, codec (M4)
- [x] Video Source Abstraction — MP4 file source (M2)
- [x] RTSP Stream Manager / Browser Live Streaming (M5)
- [x] Automatic Reconnection (M5)
- [x] Recording (M6)
- [x] Playback (M7)
- [x] Analytics Pipeline Foundation — orchestrator, source-independence regression test (M8)
- [x] YOLO Integration — Object Detection & Classification (M9)
- [x] Object Tracking (ByteTrack, used by M9/M11)
- [x] Color Detection (M10)
- [x] Loitering Detection (M11)
- [x] Missing Object Detection (M12). Post-M12 fix: `MissingObjectDetector` now re-identifies a baseline track across a tracker (ByteTrack) track_id relabel via class-label + IoU matching against its last-known bounding box — previously a relabel (e.g. one triggered by deleting and recreating a zone, which forces a fresh baseline capture on the next in-zone frame) was indistinguishable from the object actually leaving, firing a false `missing_object_detection.object_missing` event even though the object never moved. See `backend/app/infrastructure/analytics/missing_object_detector.py` and `geometry.py::iou`.
- [x] License Plate Recognition / OCR (M13)
- [x] Frontend Integration — unified dashboard (M14)
- [x] Camera & Event Lifecycle Management — edit/delete camera (cascade), delete recording, clear events, per-camera analytics visibility (post-M14 addendum, T-170–T-176). Backend unit-tested (`backend/tests/unit/application/test_{update_camera,delete_camera,delete_recording,clear_detection_events}.py`); manual end-to-end verification against the running system was not completed this session (dev backend became unresponsive mid-session) — do this before considering it demo-ready.

# In Progress

- [ ] _Nothing yet. Next up: Testing, Hardening & Final Documentation Polish (M15)._

# Remaining

- [ ] Testing, Hardening & Final Documentation Polish (M15)
- [ ] Docker (M16, stretch — time-permitting, explicitly last)
- [ ] Demo Preparation (not a formal milestone — see note below)

---

**Note on "Demo Preparation"**: not tracked as a milestone in `docs/IMPLEMENTATION_PLAN.md` since it's evaluation logistics rather than system design. When it's time to plan it, either add detail here directly or promote it to an `M17` entry in IMPLEMENTATION_PLAN.md — don't let scope accumulate silently under this one line.

**Note on ordering**: this list follows `docs/IMPLEMENTATION_PLAN.md`'s actual build order, not a flat feature list — most notably, Video Source Abstraction (M2) comes before ONVIF work (M3/M4) because the analytics pipeline is proven against local MP4 files before any camera dependency exists, and Analytics Pipeline Foundation (M8) comes before individual analytics capabilities (M9–M13) because it's what makes those capabilities source-agnostic rather than ONVIF-specific. See IMPLEMENTATION_PLAN.md's "Milestone Dependency Graph" for the full picture. M3 landing before M2 in the Completed list above is not a deviation from this: `docs/IMPLEMENTATION_PLAN.md` §M3's own Dependencies line states M3 depends only on M1 and is explicitly "Independent of M2 — can be built in parallel if needed."
