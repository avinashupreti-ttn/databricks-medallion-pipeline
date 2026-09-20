# Tool Workflow — AI Workflow Foundation (Part A)

## Primary AI tool

**Cursor** (Composer / agent chat) with an always-applied project rule
(`.cursor/rules/project.mdc`) and Cursor workflow docs under
`tool-specific/cursor-workflow/`.

## How project context is provided

- Persistent context: `project-context.md`, `spec.md`, `task-breakdown.md`,
  and engineering contracts (`requirement-analysis.md`, `data-model.md`,
  `data-quality-strategy.md`, `design-notes.md`).
- Tasks attach only the docs needed for that stage instead of reloading
  every file every time.
- Rules enforce Medallion boundaries, snake_case, synthetic data only,
  and “do not claim green without executed evidence.”

## Requirement analysis

- AI reviewed `prd.md` vs an existing analysis draft; gaps and clarifications
  (CL-01–CL-06) were recorded in `requirement-analysis.md` and companion docs.
- Prompt history: `ai-prompts/requirements-and-design.md`.

## Pipeline design (Bronze / Silver / Gold)

- Design choices (PASS-only Gold, segmentation P90, overwrite reruns,
  pytest + serverless testing) live in `design-notes.md`.
- Sequencing and gates live in `task-breakdown.md`; component contracts in
  `spec.md`.

## Code generation (Python / PySpark / SQL)

- Layer scripts under `src/bronze`, `src/silver`, `src/gold` were generated
  against the contracts, then reviewed and adjusted.
- Digit-prefixed quality modules use `importlib`; entry points resolve
  `__file__` carefully for Databricks serverless.
- Prompt history: `ai-prompts/data-generation.md`, `bronze-implementation.md`,
  `silver-implementation.md`, `databricks-bronze-silver-implementation.md`,
  `gold-aggregates.md`, `dashboard.md`.

## Validating AI-generated code

- Local pytest for generator and pure helpers (`tests/summary/final-execution.md`).
- Databricks job run for E2E Bronze → Silver → Gold (`ts-07-execution.md`).
- Serverless Spark notebook for TS-02–TS-05 table contracts
  (`ts_02_05_serverless_validation.py` + per-TS summaries).
- Rejected or corrected suggestions when they violated contracts (e.g.
  schema apply before Bronze existence check).

## Testing and validation with AI

- Tests written alongside implementation; HTML reports under `tests/reports/`.
- Databricks markers skip locally; skips are never treated as passes.
- Final local suite re-run recorded for TS-06 / TS-08.

## Debugging with AI

Meaningful issues and fixes are in `debugging-notes.md` (not routine pass logs).

## Data quality checks

- Four mandatory Silver checks only; SV-05 business-logic left as stretch and
  was not implemented.
- Intentional defect contract (460 distinct defective rows) from
  `data-quality-strategy.md` drives assertions.

## What is not shared with AI

- No real customer PII (synthetic data only).
- No tokens, `.databrickscfg`, or workspace secrets in prompts or git.
- Isolated CLI config path used for Free Edition (`DE_C1_FREE`).

## Reuse in a real production pipeline

- Keep contracts (data model / DQ strategy) as the source of truth.
- Inject catalog/schema/landing via config; fail fast on missing inputs.
- Separate local unit tests from cloud integration evidence.
- Use Asset Bundles for job + dashboard deploy without baking credentials.

## Lessons learned

- Explicit defect counts and CL-* decisions prevent re-litigating the PRD.
- Separating execution summaries from debugging notes keeps assessment evidence clear.
- Serverless needs entry-point path and exit-code care (`__file__`, `SystemExit`).
- A dedicated Spark validation notebook is simpler for assessors than forcing
  `pytest -m databricks` on Free Edition.
