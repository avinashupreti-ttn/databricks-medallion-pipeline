# Debugging notes

Meaningful issues and fixes only (symptom → layer → fix). Routine test passes
live under `tests/summary/`.

## 1. Silver applied `schema.sql` before Bronze existence check

| | |
|---|---|
| **Symptom** | Missing Bronze ingest could be masked because `schema.sql` also creates empty `bronze_*` tables. |
| **Layer** | Silver (`create_silver_tables.py`) |
| **Fix** | Require Bronze tables first; only then apply schema and build Silver. Covered by `test_missing_bronze_fails_before_schema_apply`. |
| **Evidence** | `ai-prompts/silver-implementation.md` §2 |

## 2. Databricks entry-point `__file__` / path resolution

| | |
|---|---|
| **Symptom** | Serverless job scripts failed when `__file__` was unavailable or unreliable under notebook/job packaging. |
| **Layer** | Bronze / Silver entry points |
| **Fix** | Resolve repo root via frame `co_filename` fallback; local exec tests in `tests/test_entry_path_resolution.py`. |
| **Evidence** | `ai-prompts/databricks-bronze-silver-implementation.md` |

## 3. `SystemExit(0)` aborting IPython / job runner

| | |
|---|---|
| **Symptom** | Successful runs raised `SystemExit(0)` and appeared as failures in the Databricks runner. |
| **Layer** | Entry-point `finish()` helpers |
| **Fix** | Raise / exit only on nonzero status; treat success as a normal return. |
| **Evidence** | `ai-prompts/databricks-bronze-silver-implementation.md` |

## 4. Defect-count framing (~700 vs 460)

| | |
|---|---|
| **Symptom** | PRD narrative “~700 problematic rows” vs itemized intentional defect groups totaling **460** distinct defective rows. |
| **Layer** | Data generation / DQ strategy / tests |
| **Fix** | Treat the explicit per-defect contract in `data-quality-strategy.md` as authoritative; tests assert 460, not 700. |
| **Evidence** | `data-quality-strategy.md` intentional defects summary; TS-01 / TS-03 |

## 5. Sync exclude would drop the validation notebook

| | |
|---|---|
| **Symptom** | Blanket `tests/**` exclude prevented deploying the serverless validation notebook. |
| **Layer** | Asset Bundle (`databricks.yml`) |
| **Fix** | Include `tests/databricks/ts_02_05_serverless_validation.py`; exclude `tests/**` with gitignore-style `!` exceptions for that path only. |
| **Evidence** | `databricks.yml` sync block |
