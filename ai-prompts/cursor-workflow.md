# AI Prompts — Cursor Workflow Artifacts

Factual log of Cursor interactions for:
`tool-specific/cursor-workflow/project-context.md`, `spec.md`, `task-breakdown.md`, and `.cursor/rules/project.mdc`.

Related planning-doc history: `ai-prompts/requirements-and-design.md` (renamed from `documentation.md`).  
Not covered: pipeline code, executed tests, or Databricks runs.

**Format:** initial creation uses Prompt / Request → Cursor Output → Review / Decision.  
Refinements use Reason → Changes Requested → Cursor Implementation → Review / Decision.  
**Attribution:** constraints and design choices you specified are under Request / Changes Requested; Cursor’s drafted content and extras are under Output / Implementation.

---

## 1. Create `project-context.md`

**Prompt / Request**  
Create common Cursor context covering objective, tech stack, Databricks serverless, Medallion architecture, key decisions, testing, and scope boundaries. Include a Reference Documents section on when to consult each engineering doc. Concise; do not repeat detailed requirements, schemas, DQ rules, or design notes. Suggested sections: Project Goal, Technology Stack, Architecture, Key Decisions, Testing Approach, Scope Boundaries, Reference Documents.

**Cursor Output**  
Drafted `project-context.md` using those sections, summarizing stack/architecture/decisions from existing engineering docs and linking when to open each reference.

**Review / Decision**  
Accepted as initial orientation doc. No further edits to this file except a later link fix after renaming `documentation.md` (see §9).

---

## 2. Create `spec.md`

**Prompt / Request**  
Create implementation spec broken down by data generation, Bronze, Silver, Gold, dashboard, and testing. For each: files/modules, inputs, outputs, key behavior, acceptance criteria; reference requirement IDs. Follow agreed serverless design; keep scope practical for a 1-day implementation; avoid duplicating schemas, DQ rules, or architecture already in other docs.

**Cursor Output**  
Component-wise `spec.md` with IDs, core vs stretch Silver checks, PASS-only Gold, Gold-only dashboard queries, TS mapping, supporting setup, and—**added by Cursor**—a suggested 1-day build order section.

**Review / Decision**  
Accepted structure and component checklists. Cursor’s 1-day build-order section was later removed by your refinement (§3); sequencing deferred to `task-breakdown.md`.

---

## 3. Refine `spec.md`

**Reason for Refinement**  
Spec mixed sequencing with implementation detail; dashboard and artifact bars needed to match assessment intent; `requirement-analysis.md` was under-described as “IDs only.”

**Changes Requested** *(your decisions)*  
- Remove suggested 1-day build order; sequencing belongs in `task-breakdown.md`.  
- Remove 1-day deadline wording from the spec.  
- Reference docs: `requirement-analysis.md` = requirements, acceptance criteria, resolved clarifications (not IDs alone).  
- Dashboard acceptance: actual Databricks SQL Dashboard with 3+ visualizations.  
- Brief reference to AI workflow / submission artifacts.  
- Keep component structure and acceptance criteria.

**Cursor Implementation**  
Applied those edits: Reference documents table, dashboard acceptance wording, new §8 artifacts, removed build-order / deadline language.

**Review / Decision**  
Accepted as implemented.

---

## 4. Create `.cursor/rules/project.mdc`

**Prompt / Request**  
Always-applied rule with sections Architecture, Data, Testing, Documentation, Implementation Discipline. Focus on following project docs, serverless compatibility, Bronze/Silver/Gold boundaries, validating generated code, recording AI decisions/debugging, focused changes / no unnecessary complexity. Short and actionable; no schemas, defect counts, or detailed requirements.

**Cursor Output**  
Created `project.mdc` (`alwaysApply: true`) with those five sections. Cursor chose wording that (a) listed reading all major engineering docs before implementing, and (b) pointed serverless/E2E evidence at `debugging-notes.md`.

**Review / Decision**  
Accepted initial rule. Both of those Cursor choices were later corrected per your refinement (§5).

---

## 5. Refine `project.mdc`

**Reason for Refinement**  
Always loading every engineering doc was heavier than needed; test evidence and debugging notes were conflated.

**Changes Requested** *(your decisions)*  
- Start from `project-context.md` / `spec.md`; consult other docs only as needed.  
- Separate test execution evidence from `debugging-notes.md`; debugging notes = meaningful issues/fixes only.  
- Keep the rest unchanged.

**Cursor Implementation**  
Updated Testing and Documentation bullets only.

**Review / Decision**  
Accepted as implemented.

---

## 6. Create `task-breakdown.md`

**Prompt / Request**  
Dependency-driven tasks for data generation, Bronze, Silver, Gold, dashboard, final validation. Per task: files, dependencies, implementation checklist, validation/tests before advancing, acceptance. Implement → validate → review; separate checkboxes for writing, executing, and reviewing tests; pytest locally + serverless for Spark; do not mark validation complete unless tests ran. Include prompt-history updates and meaningful commits at milestones. Practical; avoid repeating `spec.md` detail.

**Cursor Output**  
T0–T6 plan with implement / write / execute / review gates. Cursor also placed `database/schema.sql` in T0, noted test evidence via tests/README, and added prompt-history and commit columns to tasks and the progress tracker (per your initial request for those milestones).

**Review / Decision**  
Accepted sequence and validation workflow. You later moved schema to T2, separated evidence from README, and removed commit/prompt tracking from this file because you’d manage those yourself (§7–§8).

---

## 7. Refine `task-breakdown.md` (first pass)

**Reason for Refinement**  
T0 was heavier than needed before data gen; validation gates and ownership of commits/prompts needed tightening.

**Changes Requested** *(your decisions)*  
- Keep T0 lightweight; move database/schema setup to T2 if unused by data generation.  
- Keep test execution evidence separate from README and `debugging-notes.md`.  
- Add source schema validation to T1 pytest.  
- Add Bronze vs Silver row-count reconciliation to T3 acceptance.  
- In T6, include remaining AI workflow / submission artifacts from `spec.md`.  
- Remove prompt-history and Git commit tracking from individual tasks and the progress tracker.  
- Keep task sequence and implement → validate → review workflow.

**Cursor Implementation**  
Reworked T0/T2, T1/T3/T6 checklists, and progress tracker; expanded T6 with an inline artifact list.

**Review / Decision**  
Accepted structural changes. Inline T6 artifact list and evidence wording refined again in §8.

---

## 8. Refine `task-breakdown.md` (final adjustments)

**Reason for Refinement**  
Avoid requiring full execution logs; avoid duplicating `spec.md` §8 artifact list inside T6.

**Changes Requested** *(your decisions)*  
- Test evidence = short summary alongside tests; do not require committing full execution logs.  
- Replace repeated T6 submission artifact checklist with a reference to `spec.md` §8.  
- Keep the rest unchanged.

**Cursor Implementation**  
Updated intro evidence line and T6 files/implement/acceptance to match.

**Review / Decision**  
Accepted as implemented.

---

## 9. Create / rename prompt-history files

**Prompt / Request**  
Review Cursor interactions for project-context, spec, project.mdc, and task-breakdown; create `ai-prompts/cursor-workflow.md`. Rename `ai-prompts/documentation.md` → `ai-prompts/requirements-and-design.md` without changing its content.

**Cursor Output**  
Wrote initial `cursor-workflow.md` (older “what you asked / what Cursor suggested” format); renamed documentation file; updated the stale link in `project-context.md`.

**Review / Decision**  
Rename and link fix kept. Prompt-history format/attribution refined in §10.

---

## 10. Refine this document (`cursor-workflow.md`)

**Reason for Refinement**  
Initial history mixed your prescribed decisions into “what Cursor suggested,” and did not clearly separate creation vs refinement.

**Changes Requested** *(your decisions)*  
- Initial creation: Prompt / Request, Cursor Output, Review / Decision.  
- Refinements: Reason for Refinement, Changes Requested, Cursor Implementation, Review / Decision.  
- Correct attribution; keep iterations visible; avoid repetition; don’t invent prompts or decisions.

**Cursor Implementation**  
Rewrote this file to the formats above and fixed attribution on refinement entries.

**Review / Decision**  
Pending your review.

---

## Summary

| Artifact | Iterations |
|---|---|
| `project-context.md` | Created (§1); link updated after rename (§9) |
| `spec.md` | Created (§2) → refined: no 1-day order, dashboard + artifacts (§3) |
| `project.mdc` | Created (§4) → refined: docs-as-needed, evidence vs debugging (§5) |
| `task-breakdown.md` | Created (§6) → refined twice (§7, §8) |
| `documentation.md` | Renamed to `requirements-and-design.md` (§9) |
| `cursor-workflow.md` | Created (§9) → format/attribution refined (§10) |
