# prompts/ — AI Development Workflow

This folder is the operational bridge between the project's planning documents ([`AGENTS.md`](../AGENTS.md), [`TASKS.md`](../TASKS.md), [`docs/`](../docs/)) and an actual Claude Code session. It contains **templates**, not finished prompts — filling one in and using it is a deliberate step, not something to skip.

If anything here ever conflicts with `AGENTS.md`, `TASKS.md`, or `docs/`, those win. This folder is process; they are truth.

---

## Purpose of This Folder

Every milestone in [docs/IMPLEMENTATION_PLAN.md](../docs/IMPLEMENTATION_PLAN.md) eventually needs an actual prompt to hand to Claude Code. Without a template, that prompt gets reinvented ad hoc each time — scope boundaries drift, acceptance criteria get paraphrased from memory instead of copied accurately, and the "don't do X" guardrails from [docs/PROMPTING_GUIDE.md](../docs/PROMPTING_GUIDE.md) get forgotten under deadline pressure. This folder makes the shape of a good prompt repeatable: one file per milestone, same skeleton, only the milestone-specific content changes.

## How Prompts Should Be Used

1. Open the template file for the milestone you're about to start (see the coverage map below).
2. Fill in every placeholder — do not leave `<...>` markers in what you actually paste to Claude Code.
3. Copy the relevant **Acceptance Criteria** and **Files** verbatim from `docs/IMPLEMENTATION_PLAN.md` and the relevant task rows from `docs/TASK_BACKLOG.md` — don't paraphrase them from memory into the prompt; paraphrasing is how a prompt and the plan quietly drift apart.
4. Paste the filled-in template as the actual instruction to Claude Code.
5. Treat the template file itself as reusable — don't leave your filled-in values committed back into it. If a milestone needs to be re-run or redone, the template should still read as a template for the next person.

## Why Only One Milestone Should Be Implemented Per PR

`docs/IMPLEMENTATION_PLAN.md`'s milestones exist in a specific dependency order (see its "Milestone Dependency Graph") precisely so each one is independently reviewable and independently correct before the next depends on it. A PR spanning multiple milestones makes it impossible to tell which acceptance criteria a given diff is supposed to satisfy, and makes `TASKS.md` (which tracks status per milestone) ambiguous the moment the PR is half-merged. This mirrors `AGENTS.md`'s existing PR guideline of one milestone task (or a small tightly related cluster) per PR — this folder just gives that rule a template to enforce it by default.

## Why Prompts Should Remain Small

A prompt that tries to specify an entire milestone's implementation in exhaustive detail stops being a scope boundary and starts being a spec Claude Code either rubber-stamps or silently deviates from. Per `docs/PROMPTING_GUIDE.md`, a good prompt names the scope, the constraints, and the acceptance criteria, and then trusts the acceptance criteria (already written, in `docs/IMPLEMENTATION_PLAN.md`/`docs/TASK_BACKLOG.md`) to define correctness — it doesn't re-derive the design. Small, templated prompts keep that discipline the default instead of something you have to remember under time pressure.

## Why Architecture Documents Should Never Be Duplicated Inside Prompts

Every fact copied out of `docs/ARCHITECTURE.md` or `docs/TECHNICAL_DECISIONS.md` into a prompt file is a second copy that can go stale independently of the first. These templates **link** to the relevant document and section instead of restating it, exactly like `AGENTS.md` links into `docs/` rather than re-explaining it. If a template seems to need architecture detail that isn't a short pointer, that's a signal the relevant `docs/` file is missing something — fix it there, not here.

## How to Update Prompts as the Project Evolves

- If a milestone's scope changes in `docs/IMPLEMENTATION_PLAN.md`, update the corresponding template's **Documents to Read** / **Scope** pointers in the same PR — don't let a template quietly reference an outdated plan.
- If a new recurring "don't do this" trap is discovered during implementation (the kind of thing `docs/PROMPTING_GUIDE.md` §5 tracks), add it there first, then reference it from the relevant template's **Constraints** section rather than inlining it in multiple templates.
- If a milestone is added, removed, or split in `docs/IMPLEMENTATION_PLAN.md`, add/remove/split its template file here to match, and update the coverage map below and `TASKS.md`.
- Never fill in a template with real content and leave it committed that way — templates stay templates.

---

## Milestone Coverage Map

Every file below is a **template**, referencing the milestone(s) it covers by ID from `docs/IMPLEMENTATION_PLAN.md`. Numbering here is for navigation only — it is **not** the required implementation order. The authoritative build order is `docs/IMPLEMENTATION_PLAN.md`'s Milestone Dependency Graph and `TASKS.md`; consult those before picking the next milestone, don't just work through this list top to bottom.

| File | Milestone(s) | Note |
|---|---|---|
| `01-project-foundation.md` | M0, M1 | Scaffolding and the domain/application core are grouped as one "foundation" template — both are prerequisite groundwork with no feature-specific content of their own. |
| `02-onvif-camera-discovery.md` | M3 | Named per this task's required file list. Per `docs/TECHNICAL_DECISIONS.md` TD-03, the actual M3 scope is **IP + credential onboarding**, not network discovery — WS-Discovery is an explicit future enhancement, not this milestone. Treat the filename as a folder-navigation label, not a scope statement; the template body reflects the real scope. |
| `03-camera-configuration.md` | M4 | |
| `04-stream-manager.md` | M5 | Covers both live streaming and automatic reconnection — one milestone in `docs/IMPLEMENTATION_PLAN.md`. |
| `05-recording.md` | M6 | |
| `06-playback.md` | M7 | |
| `07-video-source-abstraction.md` | M2, M8 | Frame source abstraction (M2) and the analytics pipeline foundation it enables (M8, including the permanent source-independence regression test) are grouped — both are plumbing that every capability template from `08` onward depends on. **Build-order note**: despite its position in this list, M2 is built early (see IMPLEMENTATION_PLAN.md — it precedes M3/M4/M5), M8 comes after M1/M2 and before M9–M13. |
| `08-yolo-integration.md` | M9 | Object detection *and* classification — one YOLO inference call per `docs/TECHNICAL_DECISIONS.md` TD-06. |
| `09-object-tracking.md` | M9 / M11 | ByteTrack identity tracking; introduced for M9, consumed by M11 (loitering). |
| `10-color-detection.md` | M10 | |
| `11-loitering-detection.md` | M11 | |
| `12-missing-object.md` | M12 | |
| `13-license-plate-recognition.md` | M13 | |
| `14-frontend-integration.md` | M14 | |
| `15-docker.md` | M16 | Stretch, explicitly last — see `docs/IMPLEMENTATION_PLAN.md` M16. |
| `99-pr-review-checklist.md` | — | Cross-cutting; use before opening any milestone's PR. |

**Not separately templated, by design**: M15 (Testing, Hardening, Documentation Polish) is an end-of-project pass across everything already built, not a new capability — when you reach it, it's `99-pr-review-checklist.md` applied project-wide plus the specific audits `docs/IMPLEMENTATION_PLAN.md` M15 lists, not a new template. "Demo Preparation" in `TASKS.md` is explicitly noted there as evaluation logistics, not a system-design milestone — same reasoning applies.

---

## Development Workflow

1. Pull latest changes.
2. Read `AGENTS.md`.
3. Read `TASKS.md`.
4. Read the relevant architecture documents in `docs/` for the milestone you're about to start.
5. Select the next milestone (per `TASKS.md` status and `docs/IMPLEMENTATION_PLAN.md`'s dependency graph — not just the next number in this folder).
6. Open the corresponding prompt template in `prompts/`.
7. Fill in the milestone-specific requirements (scope, acceptance criteria copied from the docs, any extra constraints).
8. Ask Claude Code to implement only that milestone.
9. Review Claude's proposed changes.
10. Run formatting.
11. Run linting.
12. Run static analysis (type-checking).
13. Run tests.
14. Manually verify the feature.
15. Update `README.md` if needed.
16. Update `TASKS.md` (move the item to Completed, or update its status).
17. Commit following `AGENTS.md`'s commit message conventions (imperative summary, referencing the relevant `TASK_BACKLOG.md` ID).
18. Push the branch.
19. Open a Pull Request.
20. Complete `99-pr-review-checklist.md`.
21. Request review.
22. Address review feedback.
23. Merge only after approval.
24. Repeat the process for the next milestone.

```
Choose Milestone
        ↓
Read Docs
        ↓
Run Claude Prompt
        ↓
Review Generated Code
        ↓
Run Tests
        ↓
Manual Verification
        ↓
Update Docs
        ↓
Commit
        ↓
Push
        ↓
Create PR
        ↓
Review
        ↓
Merge
        ↓
Next Milestone
```
