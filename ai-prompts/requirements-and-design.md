# AI Prompts — Documentation (lifecycle artifacts)

Factual log of Cursor interactions that produced or revised planning documents.  
**Scope:** `requirements-analysis.md`, `data-model.md`, `data-quality-strategy.md`, `design-notes.md`.  
**Not covered here:** pipeline code, tests executed, Databricks runs (none claimed below).

---

## 1. Requirements analysis vs PRD (review only)

**What you asked**  
Review `requirement-analysis.md` against `prd.md`; find gaps, assumptions vs requirements, ambiguities, and ID/acceptance-criteria fixes. Do **not** rewrite the file yet—findings only. Keep scope practical for a one-day build; do not repeat content that belongs in other artifact docs.

**What Cursor suggested**  
Structured findings: missed deliverables (`tool-workflow.md`, full prompt history, dashboard tiles/filters), items framed as requirements that were design choices (`quality_check_result` encoding, `failed_checks`, four Gold tables, type validation), ambiguities (three vs four Gold aggregations, fourth quality check, segmentation, Gold eligibility, dashboard source layer), and trim guidance so schemas/DQ detail live elsewhere.

**Accepted / changed / rejected**  
- **Accepted (for a later edit):** Add mandatory artifacts, separate PRD vs design, keep defect summary for testing, treat three/four Gold and four checks as clarifications not facts, shorten inline Gold column lists.  
- **Not done in that turn:** No file edits (per your instruction).

**Why**  
You wanted a review gate before committing to an updated requirements doc aligned with the PRD and artifact boundaries.

---

## 2. Update `requirements-analysis.md` from review

**What you asked**  
Apply the review: keep PRD section structure and requirement IDs; add missed PRD deliverables; separate requirements from assumptions/design; keep intentional defect table; leave three/four Gold and four checks as clarifications; point detail to other docs; add high-level acceptance criteria; do not modify other files.

**What Cursor suggested**  
Rewrote the doc: new ART-* / AI-* submission section, SV/GD/DB/TS reshaping, assumptions vs functional reqs, “Clarifications Needed” with open CL-01–CL-06, updated acceptance criteria.

**Accepted / changed / rejected**  
- **Accepted:** Structure, artifact IDs, defect summary, clarifications as open questions, acceptance criteria section.  
- **You later changed direction** on clarifications (see §4)—initial “proposed decisions” inside CL items were superseded.

**Why**  
Turn review into an implementation-driving requirements doc without duplicating data model or DQ strategy.

---

## 3. Naming consistency and exact row counts

**What you asked**  
Explain the note about snake_case in SV-* vs PRD compact names; make naming and volumes consistent across docs; volumes exactly 10,000 / 100,000 / 500.

**What Cursor suggested**  
Explanation: PRD uses names like `customerid` while docs used `customer_id`. Standardize on **snake_case** everywhere; exact counts in DG-02, `data-model.md`, TS-02, acceptance criteria; remove dual “PRD alias” columns; note `prd.md` left unchanged as assessment handout.

**Accepted / changed / rejected**  
- **Accepted:** snake_case as single convention; exact row counts as requirement; cross-links between `requirement-analysis.md` and `data-model.md`.  
- **Rejected / not claimed:** No code generator or CSV headers implemented in repo yet.

**Why**  
One schema vocabulary for generator, Bronze, Silver, and tests; deterministic volume checks.

---

## 4. Resolved clarifications → `requirements-analysis.md` + `data-model.md`

**What you asked**  
Record decisions: CL-01 four Gold incl. `daily_weekly_trends`; CL-02 type + business logic scripts; CL-03 segmentation from sample order value; CL-04 no failed Silver in Gold; CL-05 duplicates flagged and excluded from Gold; CL-06 dashboard Gold-only. Update both docs only.

**What Cursor suggested**  
“Clarifications Needed” → **Resolved Clarifications** table; five Silver script areas; four Gold tables; GD-05 PASS-only; DB-06; data model Gold eligibility, five validation categories, required `gold_daily_weekly_trends`, dashboard Gold-only.

**Accepted / changed / rejected**  
- **Accepted:** All six CL decisions in both files.  
- **Later nuance (design-notes):** Business logic treated as optional/stretch in design doc while requirements still list SV-05 / `05_quality_business_logic.py`—not reconciled in requirements in this conversation.

**Why**  
Close open questions so implementation and data model share one eligibility and layering story.

---

## 5. Create `data-quality-strategy.md`

**What you asked**  
Create DQ strategy from requirements, data model, and PRD: completeness, uniqueness, type/schema, referential integrity; failed-row handling; metrics reporting; intentional defect counts aligned with PRD for future tests; assumptions separate; concise.

**What Cursor suggested**  
New file: shared PASS/FAIL handling, four core checks + supplementary business-logic section (SV-05), PRD defect count table (~700), metrics report shape, assumptions (RI parent set, duplicate handling, etc.).

**Accepted / changed / rejected**  
- **Accepted:** File created as proposed.  
- **Not claimed:** No pytest or Databricks validation runs yet.

**Why**  
Centralize DQ rules and test expectations without bloating requirements or design notes.

---

## 6. Create `design-notes.md`

**What you asked**  
Design notes for Databricks **serverless**: architecture, per-layer design, separation of ingest/validate/aggregate, error handling, rerun, testing (pytest + serverless integration), debugging, trade-offs; PRD-style headings; keep schemas/DQ in other docs.

**What Cursor suggested**  
Full `design-notes.md` with orchestration paths, detailed segmentation (including P90 rule), five Silver checks, error-handling table, TS-06/TS-07 focus, trade-off matrix.

**Accepted / changed / rejected**  
- **Accepted:** Initial file and overall architecture/testing split.  
- **You requested trim next (§7).**

**Why**  
Implementation companion to requirements without replacing data model or DQ strategy.

---

## 7. Trim `design-notes.md`

**What you asked**  
Keep architecture and testing approach; remove detail that belongs in data-model or data-quality-strategy; mark Gold PASS-only as a design decision; trends as stricter PRD interpretation (required); segmentation high-level with High-Value = 90th percentile of customer revenue on generated data (not a long fixed rule block); business-logic validation optional/stretch; align TS-* to `requirements-analysis.md`; simplify error handling.

**What Cursor suggested**  
Shorter design-notes: pointers to other docs, PASS-only as explicit decision, four Gold tables required, Silver 01–04 core / 05 stretch, TS-01–TS-08 mapping table, lighter errors, note that requirements still list SV-05 while design calls business logic stretch.

**Accepted / changed / rejected**  
- **Accepted:** Trimmed `design-notes.md` per list above.  
- **Open inconsistency (flagged by Cursor, not resolved by you):** `requirement-analysis.md` SV-05 vs design-notes “optional stretch” for business logic.

**Why**  
Design doc should guide how to build, not duplicate schemas or DQ tables; assessment-appropriate error handling.

---

## Summary

| Artifact | Outcome in conversation |
|---|---|
| `requirements-analysis.md` | Reviewed vs PRD → updated → naming/volumes → resolved CL-01–CL-06 |
| `data-model.md` | Created/expanded with layers → naming/volumes → Gold/Silver eligibility & four Gold tables |
| `data-quality-strategy.md` | Created (not revised in later turns) |
| `design-notes.md` | Created → trimmed per your constraints |

**Explicitly not done in this thread:** Running pipeline, executing tests, or validating that DQ checks catch the ~700 defects on Databricks.
