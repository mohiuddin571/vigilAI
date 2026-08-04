# PR Review Checklist

Complete this before opening any milestone PR (per `prompts/00-README.md`'s Development Workflow, step 20). This checklist operationalizes `AGENTS.md`'s Definition of Done and Testing Expectations — it doesn't replace them, so check those sections if an item here is unclear.

## Architecture

- [ ] No layer-boundary violation: `domain/` imports nothing project-internal; `application/` imports `domain/` only; `infrastructure/`/`interfaces/` depend on `application/` (and `domain/` for entities) only — see `docs/FOLDER_STRUCTURE.md` "Dependency Direction Rule."
- [ ] Analytics code (if touched) depends on `IFrameSource`/`Frame` only — no ONVIF/RTSP import (`docs/PROMPTING_GUIDE.md` §5).
- [ ] Use cases call ports, never concrete infrastructure adapters directly.
- [ ] Any new dependency has a corresponding `docs/TECHNICAL_DECISIONS.md` entry in this PR.

## Code Quality

- [ ] No opportunistic refactor or cleanup mixed into a feature PR (`AGENTS.md` § PR Guidelines).
- [ ] No dead code, no commented-out blocks left behind.
- [ ] Naming matches the vocabulary already established in `docs/AI_PROJECT_CONTEXT.md` §6 (Glossary) and existing entities/ports — no parallel terminology for the same concept.

## Testing

- [ ] Domain/Application changes: unit tests requiring no real I/O, using fakes for every port.
- [ ] Infrastructure changes: integration tests against the MP4 fixture by default; hardware-only tests marked and skipped in CI.
- [ ] The source-independence regression test (T-086) still exists and still passes, unmodified in a way that weakens it.
- [ ] New acceptance criteria from `docs/IMPLEMENTATION_PLAN.md`/`docs/TASK_BACKLOG.md` for this milestone each have a corresponding test or an explicit manual-verification note.

## Logging

- [ ] Structured logging (`structlog`) used, not bare `print()`.
- [ ] Log lines touching a camera/source carry `camera_id`/`source_id` context.
- [ ] No secrets (camera passwords, tokens) logged.

## Error Handling

- [ ] Domain/Application failure modes raise typed exceptions, not bare `Exception`/`ValueError` with no semantic meaning.
- [ ] The `interfaces/` layer maps each relevant typed exception to a correct, specific HTTP status — no unhandled exception surfacing as a raw 500 with a stack trace.

## Documentation

- [ ] If implementation revealed a planning document was wrong, it was updated in this PR, not left to drift (`AGENTS.md` § Documentation Update Policy).
- [ ] No content duplicated from `docs/` into a prompt, code comment, or elsewhere — link instead.

## Performance

- [ ] For streaming/analytics changes: no unbounded queue growth under sustained load (bounded, drop-oldest per `docs/TECHNICAL_DECISIONS.md` TD-05).
- [ ] For inference-heavy plugins (YOLO, OCR): rough throughput/latency noted in the PR description, even if informally.

## Security

- [ ] Camera credentials never logged, never returned in an API response after creation (`docs/TECHNICAL_DECISIONS.md` TD-15).
- [ ] No secret or credential committed to the repository.
- [ ] User-supplied input (IP, port, form fields) validated at the API boundary, not assumed well-formed downstream.

## Linting

- [ ] `ruff check` (or configured linter) passes with no new warnings.

## Formatting

- [ ] `black` (or configured formatter) applied; no unrelated formatting churn outside the PR's actual change.

## Type Hints

- [ ] All new/changed functions and methods are fully type-hinted.
- [ ] `mypy` (or configured type-checker) passes.

## README Updates

- [ ] `README.md` updated if this PR changes setup/usage instructions (most milestones through M15 leave the placeholders as-is; check `docs/IMPLEMENTATION_PLAN.md` for which milestone owns which placeholder).

## TASKS.md Updates

- [ ] The relevant line(s) in `TASKS.md` moved to the correct section (Completed / In Progress / Remaining) to match the actual state after this PR merges.
