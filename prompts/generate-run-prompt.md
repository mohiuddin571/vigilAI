# Generate Run Prompt — Milestone Template → Executable Implementation Prompt

This is a **meta-prompt**: a prompt whose job is to produce another prompt. Feed it, together with one milestone template from this folder, to Claude Code. Its only output is a single, fully resolved, ready-to-paste implementation prompt for that milestone — it does not write code, and it does not touch any file in this repository.

This file is reused for every milestone. It never changes per milestone; only the template you pair it with does.

---

## How to Use This File

Invoke it with the milestone template you want to turn into a runnable prompt, e.g.:

> Using `prompts/generate-run-prompt.md`, generate the executable implementation prompt for `prompts/08-yolo-integration.md`.

The response is a single markdown document: the executable prompt. Copy it into a **new** Claude Code session to actually implement the milestone — do not treat this generation step and the implementation step as the same session, and do not let this step start implementing.

## Required Input

- The path to exactly one milestone template under `prompts/` (e.g. `prompts/01-project-foundation.md`, `prompts/02-onvif-camera-discovery.md`, `prompts/08-yolo-integration.md`). If none is given, stop and ask which one — do not guess.

## Hard Boundary

- Output **one markdown document** — the executable implementation prompt — presented in the response as a markdown code block.
- Do not write it to a file in the repository unless the user explicitly asks you to save it; templates in `prompts/` stay reusable and unfilled (see `prompts/00-README.md` § How Prompts Should Be Used, point 5).
- Do not generate application code, scaffold project files, or modify any existing file. This step produces documentation about what to do next — nothing else.

---

## Workflow

### Step 1 — Read and Understand

Read, in full, not skimmed:

- `AGENTS.md`
- `TASKS.md`
- Every document listed under the milestone template's own **Documents to Read** section — all of them, not a representative sample. If a listed document references a specific section (e.g. `docs/IMPLEMENTATION_PLAN.md` §M9, `docs/TECHNICAL_DECISIONS.md` TD-06), read that section specifically, not just the file's introduction.

Do not proceed to Step 2 on partial reading. If a referenced document or section cannot be found, stop and report exactly what's missing rather than guessing its content.

### Step 2 — Read the Milestone Template

Read the supplied milestone template (e.g. `01-project-foundation.md`, `02-onvif-camera-discovery.md`, `08-yolo-integration.md`) in full: Goal, Background, Documents to Read, Scope, Acceptance Criteria, Constraints, Expected Deliverables, Testing Expectations, Documentation Updates, Output Required From Claude, Suggested Commit Message, Suggested PR Title.

### Step 3 — Resolve Every Placeholder

Replace every `<...>` placeholder (`<Fill in>`, `<TODO>`, `<fill in>`, or any bracketed instruction text) with real content resolved from the documents read in Step 1. No placeholder markers may remain anywhere in the output. If a placeholder cannot be resolved because the source documents genuinely don't specify it, do not invent a value — state explicitly in that section that the detail is undefined upstream and should be confirmed with the project owner before implementation starts. An honest gap is acceptable; a fabricated requirement is not.

### Step 4 — Expand the Content Sections

Using only what Steps 1–2 actually read, expand:

- **Scope** — the specific `docs/TASK_BACKLOG.md` task IDs this milestone's template scope maps to, and an explicit out-of-scope list (typically: the next milestone's work, and anything the template's Constraints section already names as forbidden).
- **Acceptance Criteria** — copied verbatim from `docs/IMPLEMENTATION_PLAN.md` and the matching `docs/TASK_BACKLOG.md` rows. Verbatim means verbatim: do not summarize or reword criteria that already exist in writing.
- **Deliverables** — the concrete file paths implied by the milestone's "Files" list in `docs/IMPLEMENTATION_PLAN.md`, resolved against the layout in `docs/FOLDER_STRUCTURE.md` (so a deliverable reads as an actual path, not a vague description).
- **Constraints** — the template's own Constraints section in full, plus any standing rule from `AGENTS.md` § Dependency Rules and § Things AI Must Never Do that applies to this milestone's kind of work (e.g. the ONVIF/analytics decoupling rule only applies to analytics-touching milestones).
- **Testing Expectations** — the template's own Testing Expectations, expanded with the specific fixture/mechanism named there (e.g. the MP4 fixture, a specific fake, `@pytest.mark.hardware`), not a generic "write tests" instruction.
- **Documentation Updates** — the specific `TASKS.md` line(s) to move (quoted exactly as they appear in `TASKS.md` today), plus the template's own Documentation Updates content.

Do not invent requirements anywhere in this step. Every sentence added here must trace back to something actually read in Step 1 or Step 2.

### Step 5 — Improve for Execution

Revise the draft so it is:

- **Deterministic** — two different readers should implement the same thing from it; remove any wording that leaves the scope boundary open to interpretation.
- **Unambiguous** — no contradictory instructions between sections (e.g. Scope and Constraints must agree on what's excluded).
- **Non-duplicative** — a fact stated once should not be restated elsewhere in the prompt; if two sections need the same fact, one states it and the other references that section.
- **Reference-based, not copied** — architecture/design detail lives in `docs/`; the generated prompt points at it (`docs/ARCHITECTURE.md` §5, etc.) rather than reproducing paragraphs from it. Only acceptance criteria are ever copied verbatim (Step 4) — everything else is a pointer.

### Step 6 — Require a Pre-Implementation Plan

The generated prompt must instruct its eventual executor (the future Claude Code implementation session) to produce, before writing any code:

- **Implementation Plan** — the approach, in enough detail to review.
- **Files to Create**
- **Files to Modify**
- **Risks**
- **Assumptions**

The generated prompt must state that this plan is produced first, and that implementation only proceeds after it — and, if running interactively, only after the human reviewing it has had the chance to object, unless the human has explicitly asked for autonomous execution without a pause.

### Step 7 — State the Milestone Boundary

The generated prompt must state, close to verbatim:

> Implement ONLY this milestone. Do not implement work belonging to any other milestone, even if it seems convenient or clearly needed soon. If, during implementation, you discover that another milestone's work is genuinely required to complete this one, stop and explain why before writing that code — do not silently expand scope.

### Step 8 — Require Documentation Updates

The generated prompt must require its executor to:

- Update `TASKS.md` — move this milestone's line(s) from Remaining → In Progress at the start, → Completed once acceptance criteria are met.
- Update `README.md` **only if** this milestone's acceptance criteria or deliverables actually change what's user-visible in setup/usage (most milestones don't; check the template's own Documentation Updates section for whether this one does).
- Update the relevant `docs/` architecture document **only if** implementation reveals that document was wrong or incomplete — per `AGENTS.md` § Documentation Update Policy, in the same PR, not as a follow-up.

### Step 9 — Require a Closing Report

The generated prompt must require its executor to finish with:

- **Summary of Implementation**
- **Acceptance Criteria Satisfied** (checked off against the list from Step 4)
- **Tradeoffs**
- **New Technical Decisions** (if any — with the instruction to add a corresponding `docs/TECHNICAL_DECISIONS.md` entry, not just mention it in the PR)
- **Suggested Commit Message** (imperative, referencing the relevant `TASK_BACKLOG.md` task ID(s), per `AGENTS.md` § Commit Message Conventions)
- **Suggested PR Title**

---

## Required Structure of the Generated Implementation Prompt

Produce the generated prompt with these sections, in this order, every time — this is what makes output from different milestone templates consistent and comparable:

1. **Title** — `Implementation Prompt: <Milestone Name> (<Milestone ID(s)>)`
2. **Context** — 2–4 resolved sentences: what this milestone is, why it exists now, what it depends on. No placeholders, no restated architecture paragraphs.
3. **Documents Consulted** — the exact list of documents/sections actually read to build this prompt (Step 1's real result, not a generic list).
4. **Scope** — resolved (Step 4).
5. **Out of Scope** — resolved (Step 4).
6. **Acceptance Criteria** — verbatim (Step 4).
7. **Constraints** — resolved (Step 4).
8. **Deliverables** — resolved (Step 4).
9. **Testing Expectations** — resolved (Step 4).
10. **Documentation Update Requirements** — resolved (Step 4 + Step 8).
11. **Milestone Boundary** — the Step 7 statement, verbatim.
12. **Required Pre-Implementation Output** — the Step 6 requirement, spelled out.
13. **Required Closing Report** — the Step 9 list, spelled out.

Target length for the generated prompt: **approximately 150–250 lines**. If resolving every section faithfully produces something shorter, that's fine — do not pad it to hit the range. If it runs longer, look for duplication (Step 5) before accepting the length as necessary.

---

## Quality Bar Before Returning the Output

- [ ] No `<...>`, `<TODO>`, or bracketed placeholder text remains anywhere.
- [ ] Every Acceptance Criterion is copied verbatim from a source document, with that document named.
- [ ] No fact is stated in more than one section.
- [ ] No architecture/design detail is reproduced from `docs/` beyond a pointer — except Acceptance Criteria, which are the one deliberate exception.
- [ ] Nothing in the prompt was invented — every requirement traces to `AGENTS.md`, `TASKS.md`, or a document the milestone template pointed at.
- [ ] The Milestone Boundary statement (Step 7) is present, close to verbatim.
- [ ] The Required Pre-Implementation Output and Required Closing Report sections are both present and complete.
- [ ] The output is a single markdown document — no application code, no other files.
