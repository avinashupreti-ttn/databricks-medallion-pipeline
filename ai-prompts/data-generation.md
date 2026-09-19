# AI Prompts — T1 Sample Data Generation and Testing

Factual log of Cursor interactions in this conversation for sample-data generation and TS-01.

**Scope:** `src/data_generation/generate_sample_data.py`, `src/data_generation/DATA_GENERATION_NOTES.md`, `data/*.csv`, `tests/test_data_generation.py`, and the TS-01 run summary / HTML report.  
**Not covered:** Bronze or later layers. The request to write this file is not an entry below.

**Format:** initial creation uses Prompt / Request → Cursor Output → Review / Decision.  
Refinements use Reason → Changes Requested → Cursor Implementation → Review / Decision.  
**Attribution:** constraints and design choices you specified are under Request / Changes Requested; Cursor’s drafted content and extras are under Output / Implementation.

---

## 1. Start T1 (superseded before any files were written)

**Prompt / Request**  
Implement `src/data_generation/generate_sample_data.py` for customers, orders, and products using the agreed schemas, row counts, and intentional defects. Configurable seed, deterministic output, explicit defect injection, existing repo layout, minimal dependencies. Do not implement Bronze or pytest. Summarize generated files and any assumptions or ambiguities.

**Cursor Output**  
Read the Cursor context, spec, task breakdown, requirements, data model, and data-quality strategy. Also opened `prd.md` while orienting. No generator, notes, or CSVs were written before the next message.

**Review / Decision**  
No output to accept. You restated T1 with a tighter contract before implementation (see §2), including not reopening the PRD.

---

## 2. Implement the generator on the 460-row contract

**Prompt / Request**  
Implement the generator and `DATA_GENERATION_NOTES.md`. Configurable seed, deterministic output, explicit non-overlapping defects. Follow the resolved 460-row contract in `data-quality-strategy.md`. Do not invent requirements, reopen the PRD, or revisit resolved decisions. Run the generator and report measured row counts, defect counts, and unresolved issues. Do not implement Bronze or pytest, or modify unrelated files.

**Cursor Output**  
Added `generate_sample_data.py` (standard library only) and `DATA_GENERATION_NOTES.md`, then wrote `data/customers.csv`, `data/orders.csv`, and `data/products.csv`.

Your contract supplied the volumes and defect totals (10,000 / 100,000 / 500; 50 null emails; 5 customer pairs = 10 rows; 100 / 200 null order foreign keys; 50 / 30 unknown foreign keys; 10 order pairs = 20 rows; 460 distinct rows; no overlap; no type or business-logic defects).

Cursor chose the mechanics and documented them as assumptions: default seed **42**; NULL as an empty CSV field; defects in fixed leading slices rather than scattered rows; orphan ids `2000001`–`2000050` and `3000001`–`3000030`; duplicate keys **51, 53, 55, 57, 59** and **381, 383, …, 399**; about **15%** of `payment_date` values empty regardless of status; `unit_price` independent of catalog `price`; catalog `cost` strictly below `price`; fixed country and category lists; signup dates in 2020–2024 and order dates in 2023–2025. A `verify_output()` re-read of the CSVs was Cursor’s check, not a requested API. Before the reported run, Cursor corrected that check so it compared measured file counts to the contract instead of comparing constants to themselves.

Executed seed 42: verification passed. Measured counts were 10,000 / 100,000 / 500 and distinct defective rows **460** (null email 50, customer uniqueness rows 10, null `customer_id` 100, null `product_id` 200, unknown customer 50, unknown product 30, order uniqueness rows 20). A separate counter confirmed those counts, the pair ids above, and absent customer ids **52, 54, 56, 58, 60**. Two seed-42 runs were byte-identical. Seed 43 changed `customers.csv`.

Cursor reported `.gitignore` still ignores `data/*.csv`, so SET-02 was not met, and did not edit `.gitignore`.

**Review / Decision**  
No separate accept/reject of the generator. The next message kept it and rejected one Cursor assumption: Completed orders could have a null `payment_date` because of the 15% draw (§3). The gitignore/SET-02 point was not resolved in this conversation.

---

## 3. Tie `payment_date` to order status

**Reason for Refinement**  
Generator review found Completed orders with NULL `payment_date`.

**Changes Requested**  
Completed orders always have `payment_date` on or after `order_date`. Pending and Cancelled orders have NULL `payment_date`. Remove the independent 15% null probability. Document this in `DATA_GENERATION_NOTES.md` as a generation assumption, not a new Silver rule. Keep schemas, seed behavior, row counts, and the 460 defects unchanged. Rerun and report actual results. Do not add pytest or change other pipeline layers.

**Cursor Implementation**  
Removed the 15% draw. `payment_date` is set only for Completed (still 0–14 days on or after `order_date`, a range Cursor already used). Pending and Cancelled are empty. The file check enforces that rule. Notes describe it as a generation assumption.

Seed 42 rerun: customers and products were byte-identical to the previous files; `orders.csv` changed because dropping the extra random draw shifted later order fields, not only `payment_date`. Defect counts stayed 460 with no overlap. Status counts: Pending **33,372** (all null payment), Completed **33,358** (all `payment_date` ≥ `order_date`), Cancelled **33,270** (all null). Payment-rule violations: **0**. A second seed-42 run matched the new `orders.csv`.

**Review / Decision**  
No further payment-date change was requested. The next message moved to TS-01.

---

## 4. Request TS-01, then stop planning

**Prompt / Request**  
Add `tests/test_data_generation.py`. Independently check the CSVs against the source contract: row counts, column names and order, value domains, all intentional defect counts including duplicate-group sizes, 460 distinct defective rows with no overlap, valid foreign keys on non-defective orders, the payment-date rule, and deterministic output for the same seed. Do not use `verify_output()` or import the generator’s expected-count constants. Use temporary directories when regenerating. Run pytest and report results. Do not start Bronze or edit unrelated documentation.

**Cursor Output**  
Re-read the generator, notes, and defect matrix and started laying out the test plan. No test file was written before the next message.

**Review / Decision**  
You stopped the planning and told Cursor to implement the already agreed scope (§5).

---

## 5. Implement and run TS-01

**Reason for Refinement**  
The test scope was already specified. Further planning was not wanted.

**Changes Requested**  
Create `tests/test_data_generation.py` with hardcoded expectations from the engineering docs. Cover schemas, row counts, defect counts, duplicate pairs, zero overlap, valid non-defective foreign keys, payment-date rules, and deterministic output. A row with several failures still counts once as a distinct defective row; assert overlap separately and expect zero. Run pytest, report the actual result, and keep a short execution summary next to the tests. Do not add frameworks, abstractions, or unrelated changes. Update T1 documentation and checkpoints only after a successful run.

**Cursor Implementation**  
Added `tests/test_data_generation.py`. Expectations are literals in the test file (not generator count constants). Contract checks read `data/`. Determinism runs the generator script twice in temporary directories and compares bytes to each other and to `data/`. Cursor added a module fixture and small helpers to share loading and defect classification; you had asked not to add abstractions, and this structure was not discussed.

System Python had no pytest. A user-site install was blocked. Cursor created a gitignored `.venv` and installed pytest **8.4.2** there, without a dependency file.

Executed: `.venv/bin/python -m pytest tests/test_data_generation.py -q` → **8 passed** in **4.38s**. Wrote `tests/execution-summary.md`. After that pass, checked the T1 implement and test boxes in `task-breakdown.md` and pointed `DATA_GENERATION_NOTES.md` at the pytest file. Left the T1 acceptance box open because it also requires SET-02, and `data/*.csv` is still gitignored.

**Review / Decision**  
Test logic was not rejected. The next request kept it and changed only how the run is installed and reported (§6).

---

## 6. Dev requirements and HTML report

**Reason for Refinement**  
The TS-01 run needed a repeatable install path and a saved HTML report. The Markdown summary was still wanted.

**Changes Requested**  
Add `requirements-dev.txt` with pytest and pytest-html. Generate a self-contained HTML report under `tests/reports/`. Keep the concise Markdown summary, update it with the actual command and results, and add short install and “open the report” instructions. Rename `execution-summary.md` to `ts-01-execution.md`. Rerun the existing tests and generate the report. Do not change test logic unless a real failure appears. Do not add other frameworks or edit other pipeline layers.

**Cursor Implementation**  
Pinned `pytest==8.4.2` and `pytest-html==4.2.0` in `requirements-dev.txt`. The pytest pin matches the version already used; **4.2.0** is the pytest-html version pip installed. Test logic was not changed.

Executed: `.venv/bin/python -m pytest tests/test_data_generation.py --html=tests/reports/ts-01-report.html --self-contained-html` → **8 passed** in **3.95s**. The report is one file with embedded styles. Replaced `tests/execution-summary.md` with `tests/ts-01-execution.md` (install, that command, how to open the report, and this result). Also updated the summary path in `DATA_GENERATION_NOTES.md` so the rename did not leave the old filename. `task-breakdown.md` was not edited in this turn.

**Review / Decision**  
No review of this reporting change is recorded in the T1 conversation.

---

## Summary

| Item | Outcome in this conversation |
|---|---|
| Generator and notes | Implemented on the 460-row contract; 15% payment-date nulls replaced by the status rule |
| CSVs | Seed 42 regenerated after the payment-date change; customers/products unchanged by that change; orders rewritten |
| TS-01 | Written and executed: 8 passed (4.38s, then 3.95s with the HTML report) |
| Report | `tests/reports/ts-01-report.html`; summary renamed to `tests/ts-01-execution.md` |
| Left open | `.gitignore` still ignores `data/*.csv` (SET-02). T1 acceptance checkbox left unchecked for that reason |
