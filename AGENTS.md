# AGENTS.md — Working in This Repository

This file explains **how** to work in this repository — human or AI. It is not architecture documentation; for *what* is being built and *why*, see [`docs/`](./docs/), starting with [docs/AI_PROJECT_CONTEXT.md](./docs/AI_PROJECT_CONTEXT.md). If anything here appears to conflict with `docs/`, the documents in `docs/` win — open an issue/PR to fix this file rather than acting on the conflict.

---

## Purpose of This Repository

VigilAI is a prototype Video Management System with integrated video analytics (ONVIF onboarding, live streaming, recording/playback, and a pluggable analytics pipeline), built as a technical evaluation demonstrating Clean Architecture applied to a real-time video/AI system. Full context: [docs/AI_PROJECT_CONTEXT.md](./docs/AI_PROJECT_CONTEXT.md).

## Development Philosophy

Documentation precedes and governs implementation here, not the other way around. [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md), [docs/TECHNICAL_DECISIONS.md](./docs/TECHNICAL_DECISIONS.md), and [docs/IMPLEMENTATION_PLAN.md](./docs/IMPLEMENTATION_PLAN.md) are the source of truth for design and sequencing — code should conform to them, and if reality diverges, the docs get updated deliberately (see Documentation Update Policy below), not silently outrun.

## Engineering Principles

- Clean Architecture with explicit ports (`domain` → `application` → `infrastructure`/`interfaces`), SOLID, and constructor-based dependency injection — see [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) and [docs/TECHNICAL_DECISIONS.md](./docs/TECHNICAL_DECISIONS.md) TD-01/TD-08.
- Analytics must stay decoupled from ONVIF/RTSP specifics — every detector depends on `IFrameSource`/`Frame` only. This is enforced by a permanent regression test, not a convention (see IMPLEMENTATION_PLAN.md M8, backlog T-086).
- Prefer the smallest change that satisfies a task's acceptance criteria over speculative generality.

## Repository Conventions

- `README.md` — project entry point, stays at the repository root.
- `AGENTS.md`, `TASKS.md` — repository operations (this file, and the living checklist), also at the root, since they're about *working in* the repo rather than the system it describes.
- `docs/` — all architecture, planning, design, and AI-context documentation. See [docs/FOLDER_STRUCTURE.md](./docs/FOLDER_STRUCTURE.md) for the full repo layout, including the backend/frontend structure that gets built out milestone by milestone.
- `prompts/` — reusable Claude Code prompt templates, one per milestone, plus the full AI development workflow. See [prompts/00-README.md](./prompts/00-README.md). Operational, like this file — not architecture documentation, so it also lives at the root rather than under `docs/`.
- Don't create new root-level documents. If it's project documentation, it belongs in `docs/`; if it's operational (like this file), it belongs at the root alongside `README.md`.

## Coding Standards

Type hints throughout, Pydantic for validation at boundaries, structured logging (`structlog`, no bare `print`), config only via the single `Settings` object, async for I/O-bound work, and every domain/application-layer class unit-testable without real I/O. Full list: [docs/AI_PROJECT_CONTEXT.md](./docs/AI_PROJECT_CONTEXT.md) §8.

## Dependency Rules

Source-code dependencies point inward only: `domain` depends on nothing in this project; `application` depends on `domain` only; `infrastructure`/`interfaces` depend on `application` (and `domain` for entities); `core` is the sole layer allowed to see everything, because it's the composition root. Full rule and rationale: [docs/FOLDER_STRUCTURE.md](./docs/FOLDER_STRUCTURE.md) "Dependency Direction Rule."

New third-party dependencies are not free — adding one means adding or updating the relevant entry in [docs/TECHNICAL_DECISIONS.md](./docs/TECHNICAL_DECISIONS.md) (what it replaces, why, tradeoffs) in the same PR. No dependency should show up in `pyproject.toml`/`package.json` without a paper trail explaining why it's there.

## Pull Request Guidelines

- One milestone task (or a small cluster of tightly related tasks) per PR — reference the backlog ID(s) from [docs/TASK_BACKLOG.md](./docs/TASK_BACKLOG.md) (e.g. `T-021`) in the title or description.
- PR description states what changed and which acceptance criteria (from TASK_BACKLOG.md / IMPLEMENTATION_PLAN.md) it satisfies.
- Keep diffs reviewable: implementation and unrelated cleanup/refactors go in separate PRs.
- Update `TASKS.md` in the same PR when a milestone or checklist item moves between Completed / In Progress / Remaining.
- Complete [prompts/99-pr-review-checklist.md](./prompts/99-pr-review-checklist.md) before opening the PR.

## Commit Message Conventions

- Imperative mood ("Add", "Fix", "Move" — not "Added"/"Fixes").
- Reference the backlog task ID where applicable (e.g. `Implement OnboardCameraUseCase (T-033)`).
- One logical change per commit; don't mix documentation reorganization with feature code, or unrelated fixes with the task at hand (this mirrors how the docs/ reorganization and the initial documentation were kept as separate commits in this repo's own history).

## Documentation Update Policy

If implementation reveals a planning document was wrong — a milestone's scope was off, a technology choice didn't pan out, a folder needs to move — update the relevant document (`docs/TECHNICAL_DECISIONS.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/FOLDER_STRUCTURE.md`, etc.) **in the same change**, not as a follow-up. See [docs/PROMPTING_GUIDE.md](./docs/PROMPTING_GUIDE.md) §7. Never duplicate content that already exists in `docs/` into a new location — link to it.

## Testing Expectations

- Domain and Application layers: unit tests with no real I/O, using fakes for every port.
- Infrastructure adapters: integration tests against the committed local MP4 fixture by default; anything requiring the physical ONVIF camera is marked (e.g. `@pytest.mark.hardware`) and skipped in CI.
- The source-independence regression test (backlog T-086 — same analytics pipeline behaves identically over `Mp4FileFrameSource` and a fake `IFrameSource`) is permanent and must never be deleted or weakened to make a change pass.
- Full milestone-level testing bar: [docs/IMPLEMENTATION_PLAN.md](./docs/IMPLEMENTATION_PLAN.md) M15.

## Definition of Done

A task is done when: its acceptance criteria in [docs/TASK_BACKLOG.md](./docs/TASK_BACKLOG.md) / [docs/IMPLEMENTATION_PLAN.md](./docs/IMPLEMENTATION_PLAN.md) are met; tests (per Testing Expectations above) pass; lint/type-check are clean; no dependency-rule violation was introduced (§ Dependency Rules); any documentation that became stale as a result was updated in the same change; and `TASKS.md` reflects the new state.

## Rules for AI Coding Assistants

[docs/PROMPTING_GUIDE.md](./docs/PROMPTING_GUIDE.md) is the authoritative guide for how prompts and sessions in this repo should be structured — read it before starting implementation work. In short: start a session by reading `docs/AI_PROJECT_CONTEXT.md`; scope every implementation task to a specific ID in `docs/TASK_BACKLOG.md` or milestone in `docs/IMPLEMENTATION_PLAN.md`; separate research/decision work ("report back, don't implement yet") from implementation work; verify a port/interface actually fits before writing code against it, and raise it rather than working around a bad fit.

## Things AI Must Never Do

- Never let an analytics/detector module import ONVIF or RTSP-specific code directly — it must depend on `IFrameSource`/`Frame` only (see PROMPTING_GUIDE.md §5).
- Never have a use case call an infrastructure adapter directly instead of through a port.
- Never read configuration via `os.environ` outside `app/core/config.py`.
- Never add a new dependency without a corresponding `docs/TECHNICAL_DECISIONS.md` entry.
- Never duplicate or rewrite existing content from `docs/` into a new file or location — link to it instead.
- Never implement application code, change the documented architecture, or expand scope beyond what was asked — confirm first.
- Never delete or weaken the source-independence regression test (T-086) to make an unrelated change pass.
- Never commit camera credentials, API keys, or other secrets; never log camera passwords (see TECHNICAL_DECISIONS.md TD-15).
- Never take an irreversible or shared-state action (force-push, history rewrite, deleting branches/data, merging PRs) without explicit confirmation for that specific action.
