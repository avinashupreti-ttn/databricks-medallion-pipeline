# Data Quality Strategy

## Layer Responsibilities

- **Bronze:** Preserve source data as received.
- **Silver:** Validate records, capture quality failures, and retain data for traceability.
- **Gold:** Produce business-ready datasets from data that satisfies the required quality rules.

**Implementation:** Core checks are implemented in `src/silver/01`–`04`.
`create_silver_tables.py` builds the Silver tables and DQ metrics report.
`05_quality_business_logic.py` is supplementary/stretch.

---

## Failed-row handling (all checks)

| Behavior | Rule |
|---|---|
| Retain rows | No deletes; every Bronze row appears in Silver. |
| Record outcome | `quality_check_result`: `PASS` if the row passes **all** checks applied to that entity; otherwise `FAIL`. |
| Failure detail | `failed_checks` lists one or more of: `completeness`, `uniqueness`, `type_validation`, `referential_integrity`, `business_logic`. |
| Multiple failures | Accumulate every failed category on the row (do not stop at the first failure). |
| Gold | Rows with `FAIL` — including **all** duplicate PK rows — are excluded from Gold (CL-04, CL-05). |

**Check order (recommended):** completeness → type_validation → uniqueness → referential_integrity → business_logic. Referential integrity evaluates `customer_id` / `product_id` only when non-NULL so NULLs are completeness-only.

---

## 1. Completeness

**Script:** `01_quality_completeness.py`

| Entity | Column | Rule |
|---|---|---|
| `silver_customers` | `email` | Must not be NULL or blank (after trim). |
| `silver_orders` | `customer_id` | Must not be NULL. |
| `silver_orders` | `product_id` | Must not be NULL. |

Other columns are not part of this check unless extended later.

**On failure:** `quality_check_result` → `FAIL`; add `completeness` to `failed_checks`.

**Expected failures (intentional sample data, PRD):**

| Table | Condition | Expected failing rows |
|---|---|---:|
| customers | NULL `email` | 50 |
| orders | NULL `customer_id` | 100 |
| orders | NULL `product_id` | 200 |

---

## 2. Uniqueness

**Script:** `02_quality_uniqueness.py`

| Entity | Key | Rule |
|---|---|---|
| `silver_customers` | `customer_id` | At most one row per `customer_id`. |
| `silver_orders` | `order_id` | At most one row per `order_id`. |

**On failure:** Every row that shares a duplicated key is `FAIL` with `uniqueness` in `failed_checks` (including all copies in the duplicate group). None of these rows may flow to Gold.

**Expected failures (intentional sample data, PRD):**

| Table | Condition | Expected |
|---|---|---|
| customers | duplicate `customer_id` | 10 rows involved in duplicate-key groups (generator documents exact group sizes) |
| orders | duplicate `order_id` | 20 rows involved in duplicate-key groups |

**Duplicate-count interpretation**

Duplicate counts represent all rows involved in duplicate-key groups,
not additional copies beyond the first occurrence.

- Customers: 5 duplicate `customer_id` pairs = 10 affected rows.
- Orders: 10 duplicate `order_id` pairs = 20 affected rows.

All rows in each duplicate-key group fail uniqueness validation.
Duplicate rows are included within the target source row counts;
no additional rows are appended.

*Test assertion:* count of `FAIL` rows with `uniqueness` in `failed_checks` matches generator documentation; minimum expectation is that all injected duplicate keys are detected.

---

## 3. Type / schema validation

**Script:** `03_quality_type_validation.py`

Validates values against the source contract in `data-model.md`:

| Entity | Checks (summary) |
|---|---|
| customers | `customer_id` INT; `signup_date` parseable DATE; `lifetime_value` DECIMAL; `customer_segment` in `Premium`, `Standard`, `Basic`; string fields non-null where contract requires. |
| orders | `order_id`, `customer_id`, `product_id`, `quantity` INT; dates parseable; decimals for prices/amounts; `order_status` in `Pending`, `Completed`, `Cancelled`. |
| products | Numeric and string columns per `data-model.md`; required fields present. |

**On failure:** `FAIL` + `type_validation` in `failed_checks` (specify column in logs or optional `failed_checks` detail string if useful).

**Intentional defects (PRD):** None injected for type validation. Expect **0** rows failing **only** this category from the standard defect set. Tests should still assert the check runs and valid rows pass.

---

## 4. Referential integrity

**Script:** `04_quality_referential_integrity.py`

| Child | Column | Parent | Rule |
|---|---|---|---|
| `silver_orders` | `customer_id` | `silver_customers` | If `customer_id` IS NOT NULL, it must exist as a `customer_id` in the customer dataset used for RI (see assumptions). |
| `silver_orders` | `product_id` | `silver_products` | If `product_id` IS NOT NULL, it must exist as a `product_id` in the product dataset. |

NULL FKs are **not** RI failures (handled by completeness).

**Implementation note:** Use distinct parent `customer_id` and
`product_id` key sets for FK validation. This prevents duplicate
parent rows from multiplying order records during joins.

**On failure:** `FAIL` + `referential_integrity` in `failed_checks`.

**Expected failures (intentional sample data, PRD):**

| Condition | Expected failing rows |
|---|---:|
| `customer_id` not in customers | 50 |
| `product_id` not in products | 30 |

---

## 5. Business logic (supplementary)

**Script:** `05_quality_business_logic.py` (SV-05; supplementary/stretch).
The four core checks are completeness, uniqueness, type validation,
and referential integrity.

Practical rules on **orders** (adjust in implementation if generator stays clean):

| Rule | Example failure |
|---|---|
| `quantity` > 0 | Zero or negative quantity |
| `unit_price` ≥ 0 | Negative price |
| `total_amount` ≥ 0 | Negative amount |
| Amount consistency (optional) | `total_amount` not approximately `quantity * unit_price` beyond a small tolerance |

**On failure:** `FAIL` + `business_logic` in `failed_checks`.

**Intentional defects:** None. The standard generated dataset is expected
to satisfy the supplementary business-logic rules.

---

## Intentional defects summary (test alignment)

The generator follows the explicit defect counts in `requirement-analysis.md`.

Defect groups are intentionally non-overlapping, and duplicate counts
represent all rows involved in duplicate-key groups.

| Check category | Customers | Orders | Products | Total |
|---|---:|---:|---:|---:|
| Completeness | 50 | 300 | 0 | 350 |
| Uniqueness | 10 | 20 | 0 | 30 |
| Referential integrity | 0 | 80 | 0 | 80 |
| Type validation | 0 | 0 | 0 | 0 |
| Business logic | 0 | 0 | 0 | 0 |
| **Total** | **60** | **400** | **0** | **460** |

**Resolved discrepancy:** The original assessment mentions approximately
700 problematic rows, but its itemized defect counts total 460 under
the agreed duplicate-count interpretation.

The explicit per-defect counts are the implementation and testing
contract. No additional defects are introduced to match the
approximate headline.

### Test Verification Matrix

| Assertion | Expected |
|---|---:|
| Customer rows | 10,000 |
| Order rows | 100,000 |
| Product rows | 500 |
| NULL customer emails | 50 |
| Customer rows failing uniqueness | 10 |
| NULL order customer IDs | 100 |
| NULL order product IDs | 200 |
| Unknown customer IDs | 50 |
| Unknown product IDs | 30 |
| Order rows failing uniqueness | 20 |
| Distinct intentionally defective rows | 460 |

Silver must detect the individual categories and retain all source rows.

With the agreed non-overlapping defect groups, the expected core-check
FAIL counts are 60 customers, 400 orders, and 0 products.

---

## Quality metrics report

**Requirement:** SV-07 / PRD — % passed (or pass/fail counts) **per validation category**.

**Delivery:** Produced after Silver build (notebook output, CSV, or small Delta table e.g. `dq_metrics_report`). Shape:

| Column | Description |
|---|---|
| `check_category` | `completeness`, `uniqueness`, `type_validation`, `referential_integrity`, `business_logic` |
| `entity` | `customers`, `orders`, or `products` (where applicable) |
| `rows_evaluated` | Rows subject to that check |
| `rows_passed` | Rows passing that check |
| `rows_failed` | Rows failing that check |
| `pass_pct` | `rows_passed / rows_evaluated * 100` (rounded for display) |
| `reported_at` | Timestamp of the run |

**Per-category semantics:**

- Count a row as failed for a category if that category appears in `failed_checks` for that row (or if the check sets a per-category flag used to build the report).
- Overall table health (optional): % of rows with `quality_check_result` = `PASS` per `silver_*` table.

**Reviewers:** Report should show completeness, uniqueness, and referential integrity below 100% on the sample dataset so intentional issues are visible.

---

## Assumptions

- **RI parent set:** Orphan checks use `customer_id` / `product_id` values present in `silver_customers` / `silver_products` (or Bronze equivalents before quality flags), including IDs on rows that fail other checks, so “unknown id” means truly absent from the parent file—not merely failing parents.
- **Blank email:** Treated as incomplete (NULL or empty string after trim).
- **Uniqueness:** Window/count-based duplicate detection on full Silver tables after load; no “keep one copy” survivor for Gold.
- **Type validation:** Runs on values as read from Bronze; cast failures or domain violations fail the row.
- **Metrics scope:** Each category is reported independently; a single row can increment `rows_failed` for multiple categories in the report.
- **Products table:** No PRD-injected defects; expect high pass rates on products for all checks.
