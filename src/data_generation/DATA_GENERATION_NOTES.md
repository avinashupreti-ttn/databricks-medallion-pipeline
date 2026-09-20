# Sample data generation

How `data/customers.csv`, `data/orders.csv`, and `data/products.csv` are produced.

Schemas: `data-model.md`. Defect counts and Silver expectations: `data-quality-strategy.md`. This note covers the injection method only.

## Run

From the repo root:

```bash
python src/data_generation/generate_sample_data.py --seed 42
```

`--seed` defaults to **42**. `--output-dir` defaults to `data/`. A rerun overwrites the three CSVs. The same seed writes the same bytes (`\n` line endings, UTF-8, no BOM).

After writing, the script re-reads the CSVs and exits non-zero if measured counts do not match the contract. That check is not the pytest suite. TS-01 is `tests/test_data_generation.py`; the run summary is `tests/summary/ts-01-execution.md`.

## Method

- Python standard library only (`random.Random`, `csv`, `Decimal`). No third-party packages.
- One RNG stream, in order: all products, then all customers, then all orders. Attribute draws for a row are unconditional, so the stream does not depend on defect flags.
- Exact volumes: 10,000 / 100,000 / 500. Keys start at 1 and increment by row. Defects overwrite fields on existing rows; no rows are appended.
- Defect positions are fixed index ranges, so **counts do not change with the seed**. The seed only changes synthetic attributes and which valid parent keys clean orders use.
- Money is integer cents, written with two decimal places. Dates are `YYYY-MM-DD`.
- NULL is an empty CSV field. The word `NULL` is not written. Bronze should read empty fields as null (Spark's default).

## Defect injection

Groups are chained slices: each starts at the previous end, so a row is in at most one group. The second row of a duplicate pair copies only the key. Other columns stay as generated, so the pair is not a full-row clone.

### Customers

| 0-based slice | Rows | What changes |
|---|---:|---|
| 0:50 | 50 | `email` cleared |
| 50:60 | 10 | 5 pairs; the odd row copies `customer_id` from the previous row |

Pair `k` (`k` = 0..4) is rows `50 + 2k` and `51 + 2k`. Shared `customer_id` is `51 + 2k`: **51, 53, 55, 57, 59**, each twice. IDs **52, 54, 56, 58, 60** are absent. Those gaps are not the referential-integrity orphans.

### Orders

| 0-based slice | Rows | What changes |
|---|---:|---|
| 0:100 | 100 | `customer_id` cleared; `product_id` left valid |
| 100:300 | 200 | `product_id` cleared; `customer_id` left valid |
| 300:350 | 50 | `customer_id` set to `2000001` .. `2000050` |
| 350:380 | 30 | `product_id` set to `3000001` .. `3000030` |
| 380:400 | 20 | 10 pairs; the odd row copies `order_id` from the previous row |

Pair `k` (`k` = 0..9) is rows `380 + 2k` and `381 + 2k`. Shared `order_id` is `381 + 2k`: **381, 383, 385, 387, 389, 391, 393, 395, 397, 399**, each twice.

Orphan ids sit above any parent key (`2000001+`, `3000001+`), so they are missing from the parent file even on rows that fail other checks. NULL foreign keys are not also unknown ids.

### Products

No intentional defects. `product_id` is `1`..`500`, each once.

### Counts

| Group | Rows |
|---|---:|
| Customers (null email + duplicate keys) | 60 |
| Orders (null FKs + unknown FKs + duplicate keys) | 400 |
| Products | 0 |
| Distinct defective rows | 460 |

No type-validation or business-logic defects are injected.

## Values that are not defects

- `payment_date` is set from `order_status` (see Assumptions). Empty or filled payment dates from that rule are not injected defects.
- `lifetime_value` is a source attribute, not a sum of orders.
- `unit_price` is independent of catalog `price`. `total_amount` equals `quantity * unit_price` exactly.
- `quantity` is 1..5. Prices and amounts are non-negative.
- `customer_segment` is only `Premium`, `Standard`, or `Basic`. `order_status` is only `Pending`, `Completed`, or `Cancelled`.
- Names and emails are synthetic (`Customer 00001`, `customer00001@example.test`). No real PII.

## Assumptions

- Empty CSV fields are the NULL encoding Silver completeness checks will see.
- Duplicate groups are size 2 only (5 customer keys, 10 order keys), inside the target row counts.
- Clean orders reference a **distinct** parent `customer_id` chosen uniformly, including ids that also appear on a null-email or duplicate customer row. Dropped ids (52, 54, 56, 58, 60) are never used.
- Catalog `cost` is positive and strictly less than `price`. That is a generation choice, not a Silver rule.
- Countries are a fixed nine-name list. Product `category` is one of Apparel, Electronics, Grocery, Home, Sports. Neither domain is in the data model.
- Signup dates fall on 2020-01-01 through 2024-12-31. Order dates fall on 2023-01-01 through 2025-12-31.
- `payment_date` follows status. This is a generation choice, not a Silver data-quality rule: `Completed` always has `payment_date` 0..14 days on or after `order_date` (that date may fall in 2026); `Pending` and `Cancelled` always have an empty `payment_date`. There is no separate random null rate. Silver is not required to fail rows that break this pattern.
