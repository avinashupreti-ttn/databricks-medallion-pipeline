# AI Prompts — T2 Bronze Ingestion and Testing

Factual log of Cursor interactions in this conversation for Bronze ingest and TS-02.

**Scope:** `database/schema.sql`, `src/bronze/` (`ingest.py`, `ingest_all.py`, `01_ingest_customers.py`, `02_ingest_orders.py`, `03_ingest_products.py`), `src/config.py`, `pytest.ini`, `tests/test_bronze_ingestion.py`, `tests/ts-02-execution.md`, `tests/reports/ts-02-report.html`.  
**Not covered:** T1 generator work, Silver or later layers. The request to write this file is not an entry below.

**Format:** initial creation uses Prompt / Request → Cursor Output → Review / Decision.  
Refinements use Reason → Changes Requested → Cursor Implementation → Review / Decision.  
**Attribution:** constraints you specified are under Request / Changes Requested. Cursor’s file split, Spark calls, and test mechanics are under Output / Implementation.

---

## 1. Implement Bronze ingest and TS-02

**Prompt / Request**  
T1 was treated as done. Start T2 only. Implement `database/schema.sql`, `src/bronze/01_ingest_customers.py`, `02_ingest_orders.py`, `03_ingest_products.py`, and `ingest_all.py`. Read the generated CSVs from a configurable Databricks landing path and write Bronze Delta tables with the agreed schemas and ingestion metadata. Keep every source row and intentional defect. No cleansing, deduplication, or DQ checks. Catalog, schema, and path must stay simple and serverless-compatible. Fail clearly on missing, empty, or unreadable inputs. Overwrite on rerun. Add TS-02 checks for source-to-Bronze row counts and defect preservation. Run feasible local checks. Leave Spark/table validation pending until it runs on Databricks serverless. Do not set up local Spark or mark unexecuted checks as passed.

**Cursor Output**  
Added the SQL file and the four entry scripts. Also added `src/config.py`, `src/bronze/ingest.py`, and `pytest.ini`, which you did not name.

`schema.sql` creates the schema and empty `bronze_customers`, `bronze_orders`, and `bronze_products` (business columns from `data-model.md`, plus `_ingested_at`, `_source_file`, `_ingestion_batch_id`). It does not create a catalog. Names are `__CATALOG__` / `__SCHEMA__` tokens that `ingest.py` substitutes. The numbered scripts and `ingest_all.py` only call `run_main`. Shared read/write lives in `ingest.py`.

Config resolution order was Cursor’s: CLI flags, then `PIPELINE_CATALOG` / `PIPELINE_SCHEMA` / `PIPELINE_LANDING_PATH`, then widgets if a Spark session is already active. Missing settings raise `ValueError`. Catalog and schema must match a simple identifier pattern.

CSV read uses an explicit Spark schema, not `inferSchema`. Cursor’s reason, written in `ingest.py`: inference would widen integers and decimals away from the DDL. Empty fields are read as null. Writes use Delta `overwrite` and `overwriteSchema`. Row count, path, timestamp, and batch id are printed. `ingest_all` checks all three files before writing any table.

You required serverless-compatible Spark usage. The first version still called `DataFrame.cache()` / `unpersist()` and `spark._jvm` / `spark._jsc` for remote file checks. Local paths used `pathlib` only. `get_spark()` does not call `SparkSession.builder.getOrCreate()` unless `DATABRICKS_RUNTIME_VERSION` is set or a session is already active.

`tests/test_bronze_ingestion.py` hardcodes row targets (10,000 / 100,000 / 500) and the defect ids from the generation notes. Five tests are marked `databricks` and skip when `DATABRICKS_RUNTIME_VERSION` is unset. Local tests cover config, missing/empty/unreadable files, schema SQL, and a source scan that forbids `dropDuplicates`, `dropna`, and filters.

First local pytest failed: four tests called `Path.write_text(..., newline=...)`, which Python 3.9 does not accept. Cursor removed that argument. No Bronze logic changed for that failure.

Executed after the fix, including the existing TS-01 file:

`.venv/bin/python -m pytest tests/test_bronze_ingestion.py tests/test_data_generation.py -q` → **29 passed, 5 skipped** in **4.23s**.

Of those, **21 passed** and **5 skipped** in `test_bronze_ingestion.py`. The other **8 passed** were the TS-01 rerun. Cursor wrote `tests/ts-02-execution.md` with that split and left the five Spark checks as not executed. T2 code and “tests written” were checked in `task-breakdown.md`. Staging CSVs, serverless execute, review, and T2 acceptance stayed open. No CSVs were copied to a Databricks landing path.

**Review / Decision**  
No separate review of this drop. The next message kept the schema, metadata, config, overwrite, and defect checks, and rejected the cache and JVM calls (§2).

---

## 2. Serverless file checks, explicit TS-02, HTML report

**Reason for Refinement**  
The first ingest path was not safe to run on Databricks serverless, and a requested Databricks pytest run could still skip and exit clean.

**Changes Requested**  
Before any Databricks execution, remove `cache()`, `persist()`, `unpersist()`, and direct SparkContext/JVM access. Use supported DataFrame operations for file checks and ingestion. Do not change schema, metadata, configuration, overwrite, or defect-preservation requirements. If TS-02 is explicitly requested, it must not skip silently. Write a self-contained HTML report at `tests/reports/ts-02-report.html` with the existing pytest-html pin. Run the local suite, update `tests/ts-02-execution.md` with the real command and results, and separate passed local tests from skipped Databricks tests. Do not treat serverless acceptance as done. No unrelated refactor.

**Cursor Implementation**  
`src/config.py` was inspected and not edited. It had none of the forbidden calls.

In `ingest.py`, the cache/unpersist block is gone. Count and write are separate DataFrame actions. Remote checks no longer use `_jvm` or `_jsc`. Cursor chose `binaryFile` (length, at most two rows) plus a `text` preview (two rows) for missing, empty, not-a-file, header, and no-data-row errors. You did not name those readers.

`_skip_unless_databricks` still skips on a normal local run. If `-m` selects `databricks`, or the test node is named on the command line, and `DATABRICKS_RUNTIME_VERSION` is unset, those tests `pytest.fail` with “This is not a pass.” Cursor added `test_explicit_databricks_request_does_not_skip`, which runs `pytest -m databricks` in a subprocess and expects a non-zero exit. The source scan now also rejects `.cache(`, `.persist(`, `.unpersist(`, `_jvm`, `_jsc`, and `SparkContext` in `ingest.py` and `config.py`.

`requirements-dev.txt` was already `pytest==8.4.2` and `pytest-html==4.2.0`. It was not changed.

Executed:

`.venv/bin/python -m pytest tests/test_bronze_ingestion.py --html=tests/reports/ts-02-report.html --self-contained-html` → **22 passed, 5 skipped** in **0.73s**.

The report is one HTML file (styles embedded; the summary shows 5 Skipped). `tests/ts-02-execution.md` records that command, the 22/5 split, and the five skipped names. Those five were not run. TS-02 serverless acceptance was not marked complete.

**Review / Decision**  
No review of this correction is recorded after the run.

---

## Summary

| Item | Outcome in this conversation |
|---|---|
| Bronze DDL and scripts | Written. Catalog is not created. Ingest overwrites Delta tables and keeps source rows |
| Extra files Cursor added | `src/config.py`, `src/bronze/ingest.py`, `pytest.ini` |
| Serverless correction | Cache and JVM access removed. Remote checks use DataFrame reads. `config.py` unchanged |
| Local pytest | After a Python 3.9 test-helper fix: 29 passed, 5 skipped (4.23s, with TS-01). After the serverless correction: 22 passed, 5 skipped (0.73s) on `test_bronze_ingestion.py` only |
| Report | `tests/reports/ts-02-report.html`; summary is `tests/ts-02-execution.md` |
| Left open | CSVs not staged. Five `databricks` tests not executed. T2 acceptance not checked |
