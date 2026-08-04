# Implementation Prompt: Project Foundation (M0, M1)

## Context

Stand up the running-but-empty FastAPI + React skeleton with quality tooling in place (M0), and the framework-free domain entities/value objects plus every application-layer port and use-case skeleton (M1). Every later milestone depends on this one: M0 supplies the tooling and composition root every adapter is wired through, and M1 supplies the entities and ports every future adapter and use case implements against. Nothing in this milestone is camera-, stream-, or analytics-specific — no concrete `infrastructure/` adapter exists yet, and use cases here are signatures only, not real logic.

## Documents Consulted

- `AGENTS.md` (full)
- `TASKS.md` (full)
- `docs/AI_PROJECT_CONTEXT.md` (full)
- `docs/IMPLEMENTATION_PLAN.md` §M0 (Project Scaffolding & Tooling), §M1 (Domain & Application Core)
- `docs/TASK_BACKLOG.md` — Epic M0 — Scaffolding (T-001–T-009), Epic M1 — Domain & Application Core (T-010–T-017)
- `docs/FOLDER_STRUCTURE.md` (full)
- `docs/TECHNICAL_DECISIONS.md` TD-01 (Clean Architecture with explicit ports), TD-08 (manual composition-root DI), TD-13 (config via `pydantic-settings`)
- `README.md` § Getting Started (to resolve whether/how it needs updating — it does; see Documentation Update Requirements)

## Scope

All tasks under Epic M0 and Epic M1 in `docs/TASK_BACKLOG.md`:

- **Epic M0**: T-001 (backend package skeleton), T-002 (`pyproject.toml` + ruff/black/mypy/pytest config), T-003 (`Settings` + `.env.example`), T-004 (`structlog` setup), T-005 (composition root stub + `main.py` + `/health`), T-006 (import-linter contract, P1), T-007 (React+Vite+TS+Tailwind skeleton), T-008 (frontend hits `/health`), T-009 (pre-commit/CI workflow, P1).
- **Epic M1**: T-010 (`Camera`, `StreamProfile` entities), T-011 (`Recording`, `DetectionEvent` entities), T-012 (`AnalyticsZone`, `TrackedObject` entities, P1), T-013 (value objects), T-014 (domain exception hierarchy), T-015 (ports: `ICameraGateway`, `IFrameSource`, `ICameraRepository`, `IRecordingRepository`), T-016 (ports: `IObjectDetector`, `ILicensePlateReader`, `IEventPublisher`), T-017 (6 use case skeletons).

Full Definition of Done for each task ID is in `docs/TASK_BACKLOG.md` — do not re-derive it from this prompt; look it up there. T-006 and T-009 are P1 ("required by the assignment but can slip briefly" per `docs/TASK_BACKLOG.md`'s priority key) — within this same PR, they may be sequenced last, but they are still in this milestone's scope and this PR, not deferred to a separate one (`AGENTS.md` § Pull Request Guidelines: one milestone per PR).

## Out of Scope

- Any concrete `infrastructure/` adapter (ONVIF client, FFmpeg/OpenCV frame source, YOLO/EasyOCR detector, SQL repository implementation) — those start at M2/M3.
- Any real use-case logic — the six M1 use cases (`OnboardCameraUseCase`, `UpdateCameraConfigUseCase`, `StartLiveStreamUseCase`, `StartRecordingUseCase`, `ListRecordingsUseCase`, `RunAnalyticsPipelineUseCase`) are signatures with docstring-level intent only, per `docs/IMPLEMENTATION_PLAN.md` M1.
- `domain/events/` — `docs/FOLDER_STRUCTURE.md` describes this subfolder as part of `domain/`'s eventual contents, but `docs/IMPLEMENTATION_PLAN.md` M1's deliverables list does not include domain events as an M1 deliverable. Leave this folder absent; it is not this milestone's scope, and creating it now would be scope not asked for by the milestone plan.
- `application/dto/` — same reasoning: named in `docs/FOLDER_STRUCTURE.md`'s general description of `application/`, but not in M1's deliverables list. Out of scope here.
- `ConfigureAnalyticsRuleUseCase` — listed in `docs/FOLDER_STRUCTURE.md`'s general `use_cases/` description but not among the six use cases `docs/IMPLEMENTATION_PLAN.md` M1 actually specifies. Out of scope for this milestone.
- `backend/app/core/exception_handlers.py` — named in `docs/FOLDER_STRUCTURE.md`'s general description of `core/`, but not in M0's "Files" list, and there is no real exception-raising logic yet for it to map (that arrives with M3's typed exceptions). Out of scope here.
- Anything from M2 onward.

## Acceptance Criteria

Copied verbatim from `docs/IMPLEMENTATION_PLAN.md`:

**M0**:
- `uvicorn app.main:app` starts cleanly; `GET /health` returns `200`.
- `npm run dev` serves a page that displays the backend health status.
- `ruff`/`mypy`/`pytest` all run and pass (pytest with zero tests is fine — it must at least run).
- Import-linter contract fails intentionally if a test import violates layering, then is reverted (proves the gate works).

**M1**:
- 100% of domain/value-object code covered by unit tests that require zero mocking (pure functions/objects).
- No file under `domain/` or `application/` imports `fastapi`, `cv2`, `onvif_zeep_async`, `sqlalchemy`, or anything from `infrastructure/`/`interfaces/` — enforced by the M0 import-linter gate.

## Constraints

From the milestone template:
- Follow the Dependency Direction Rule (`docs/FOLDER_STRUCTURE.md`) — `domain/` imports nothing from this project; `application/` imports `domain/` only.
- No new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry in the same PR.
- Use cases in this milestone are signatures only — do not implement real logic that belongs to a later milestone.
- Do not create any concrete `infrastructure/` adapter yet.

Standing rules from `AGENTS.md` that apply to this kind of work:
- Never have a use case call an infrastructure adapter directly instead of through a port (§ Things AI Must Never Do) — enforced here even though no adapters exist yet: use-case signatures must depend on the M1 port interfaces, never presuppose a concrete implementation.
- Never read configuration via `os.environ` outside `app/core/config.py` (§ Things AI Must Never Do, § Coding Standards) — the single `Settings(BaseSettings)` class (TD-13) is the only place environment variables are read.
- `core/container.py` is the composition root and the only module allowed to import across all layers (`docs/FOLDER_STRUCTURE.md` § `backend/app/core/`) — it stays a stub in this milestone (no adapters to wire yet) but must not become a place where `domain/`/`application/` code reaches into a concrete implementation.
- FastAPI's `Depends` is not this project's DI mechanism (TD-08) — reserve it for request-scoped concerns only if/when it's used; the composition root is manual.

## Deliverables

**M0** (from `docs/IMPLEMENTATION_PLAN.md` §M0 "Files", resolved against `docs/FOLDER_STRUCTURE.md`):
- `backend/pyproject.toml`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/core/logging.py`
- `backend/app/core/container.py`
- `frontend/package.json`
- `frontend/src/App.tsx`
- `.env.example`
- `.gitignore`
- Backend/frontend tooling config needed to satisfy the acceptance criteria (ruff/black/mypy config, an import-linter contract, and whatever Vite/TypeScript/Tailwind config `npm run dev` and Tailwind require) — exact file names/locations for these are not specified in `docs/IMPLEMENTATION_PLAN.md` beyond "ruff/black/mypy config" and "Tailwind configured"; decide and list them explicitly in the Required Pre-Implementation Output below rather than guessing here.
- Pre-commit hook configuration, or a documented equivalent CI step, enforcing lint/format/type-check (T-009) — explicitly listed as an M0 deliverable in `docs/IMPLEMENTATION_PLAN.md` §M0, but not given a file name there either; decide and list the concrete file(s) (e.g. `.pre-commit-config.yaml`, or a CI workflow file) in the Required Pre-Implementation Output below. Note: `docs/IMPLEMENTATION_PLAN.md` gives this deliverable no corresponding acceptance criterion of its own — its completion is verified by it existing and functioning as documented (blocks a lint violation from being committed/merged, per T-009's Definition of Done in `docs/TASK_BACKLOG.md`), not by one of the Acceptance Criteria bullets above.
- A minimal `backend/tests/` scaffold sufficient for `pytest` to run with zero tests (required by M0's acceptance criteria; distinct from M1's `backend/tests/unit/domain/`).

**M1** (from `docs/IMPLEMENTATION_PLAN.md` §M1 "Files", resolved against `docs/FOLDER_STRUCTURE.md`):
- `backend/app/domain/entities/` — `Camera`, `StreamProfile`, `Recording`, `DetectionEvent`, `AnalyticsZone`, `TrackedObject`.
- `backend/app/domain/value_objects/` — `Resolution`, `Codec`, `BitrateKbps`, `BoundingBox`, `ColorLabel`, `PlateNumber`.
- `backend/app/domain/exceptions.py` — the domain exception hierarchy (at minimum `CameraUnreachableError`, `UnsupportedConfigurationError`, per `docs/FOLDER_STRUCTURE.md`).
- `backend/app/application/ports/` — `ICameraGateway`, `IFrameSource`, `ICameraRepository`, `IRecordingRepository`, `IObjectDetector`, `ILicensePlateReader`, `IEventPublisher`.
- `backend/app/application/use_cases/` — `OnboardCameraUseCase`, `UpdateCameraConfigUseCase`, `StartLiveStreamUseCase`, `StartRecordingUseCase`, `ListRecordingsUseCase`, `RunAnalyticsPipelineUseCase` (signatures + docstring intent only).
- `backend/tests/unit/domain/` — unit tests for every entity/value-object validation rule.

## Testing Expectations

- Domain and value-object unit tests require zero mocking (pure functions/objects) and must reach 100% coverage of that code, per the M1 acceptance criteria above.
- The import-linter (or equivalent) dependency-rule gate from M0 must be proven, not just configured: deliberately introduce a violating import (e.g. `domain/` importing from `infrastructure/`), confirm the check fails, then revert it and confirm the check passes. This is an explicit M0 acceptance criterion, not optional polish.
- No MP4 fixture, hardware marker, or integration test infrastructure is needed at this milestone — those begin at M2 and M3 respectively (`AGENTS.md` § Testing Expectations); do not add them here.

## Documentation Update Requirements

- **`TASKS.md`**: at the start of this work, replace the line `- [ ] _Nothing yet — no application code exists. Next up: Backend & Frontend Foundation (M0)._` under `# In Progress` with `- [ ] Backend & Frontend Foundation (M0)` and `- [ ] Domain & Application Core (M1)` (moved from `# Remaining`, removing those two exact lines from there). Once all acceptance criteria above are met, move both lines to `# Completed`.
- **`README.md`**: this milestone is one of the cases where README genuinely needs updating — its § Getting Started currently reads `# TODO: fill in once M0 lands` in the Backend and Frontend code blocks, and `Python <version TBD>` / `Node.js <version TBD>` under Prerequisites. Replace these placeholders with the real, tested commands and versions this milestone establishes (the actual `pip`/`uv`/`poetry` install command chosen, the real `uvicorn`/`npm run dev` invocations, and the concrete Python/Node versions pinned in `backend/pyproject.toml`/`frontend/package.json`).
- **`docs/` architecture documents**: update only if implementation reveals one of them was wrong (per `AGENTS.md` § Documentation Update Policy) — e.g. if a tooling choice forces a deviation from TD-01/TD-08/TD-13, add a new `docs/TECHNICAL_DECISIONS.md` entry explaining why in the same PR. No update is anticipated by default for a scaffolding milestone.

## Milestone Boundary

Implement ONLY this milestone. Do not implement work belonging to any other milestone, even if it seems convenient or clearly needed soon. If, during implementation, you discover that another milestone's work is genuinely required to complete this one, stop and explain why before writing that code — do not silently expand scope.

## Required Pre-Implementation Output

Before writing any code, produce:

- **Implementation Plan** — the approach, in enough detail to review, including how the ambiguous items flagged in Deliverables above (exact linter/formatter config file locations, import-linter contract location, frontend tooling config) will be resolved.
- **Files to Create** — the complete concrete file list, replacing every folder-level reference above with actual file paths and names.
- **Files to Modify** — expected to be `README.md` and `TASKS.md` per Documentation Update Requirements; list anything else here explicitly if identified.
- **Risks**
- **Assumptions** — explicitly include the four Out-of-Scope resolutions above (`domain/events/`, `application/dto/`, `ConfigureAnalyticsRuleUseCase`, `exception_handlers.py`) so they're visible as deliberate scope decisions, not oversights.

This plan is produced first. Implementation proceeds only after it — and, if this is running interactively, only after the human reviewing it has had the chance to object, unless the human has explicitly asked for autonomous execution without a pause.

## Required Closing Report

On completion, produce:

- **Summary of Implementation**
- **Acceptance Criteria Satisfied** — checked off against the exact list in the Acceptance Criteria section above.
- **Tradeoffs**
- **New Technical Decisions** — if any real decision was made (e.g. a specific import-linter tool, a specific frontend tooling choice not already fixed by `docs/TECHNICAL_DECISIONS.md`), add a corresponding `docs/TECHNICAL_DECISIONS.md` entry in this same PR, not just a mention in the closing report.
- **Suggested Commit Message** — imperative mood, referencing the relevant `docs/TASK_BACKLOG.md` task ID(s) from Scope above, per `AGENTS.md` § Commit Message Conventions.
- **Suggested PR Title** — `M0/M1: Project Foundation`, per `prompts/01-project-foundation.md`.
