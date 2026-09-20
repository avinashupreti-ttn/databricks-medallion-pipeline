# AI Prompts — T5 Dashboard Implementation

Factual log of Cursor interactions in this conversation for the Gold-only AI/BI dashboard.

**Scope:** `src/dashboard/` (`dashboard_queries.sql`, `DASHBOARD_GUIDE.md`, `ecommerce_gold_dashboard.lvdash.json`), `resources/ecommerce_gold_dashboard.yml`, `databricks.yml` (`warehouse_id`, sync exclude for `*.lvdash.json`), light notes in `docs/bundle-deployment.md` and T5 checkboxes in `tool-specific/cursor-workflow/task-breakdown.md`.  
**Not covered:** Bronze / Silver / Gold calculation changes, pipeline job task changes, `bundle deploy` / `bundle run` by the agent, or the request to write this file.  
**Format:** initial creation uses Prompt / Request → Cursor Output → Review / Decision; later turns use Reason for Refinement → Changes Requested → Cursor Implementation → Review / Decision.  
**Attribution:** constraints you specified are under Request / Changes Requested. Cursor’s file mechanics and validation runs are under Output / Implementation.

---

## 1. Start T5 — Gold-only dashboard SQL and setup guide

**Prompt / Request**  
Start T5 — Databricks dashboard. Bronze → Silver → Gold already run on Free Edition serverless; Gold validation complete. Catalog `workspace`, Gold schema `c1_gold`; tables `gold_customer_segmentation`, `gold_daily_weekly_trends`, `gold_revenue_by_customer`, `gold_sales_by_product`. Follow T5 task and design docs; Gold tables exclusively; prefer native Databricks AI/BI; keep simple and reproducible. Include short setup guide with exact UI steps; document T5 validation checks and screenshots; mark dashboard creation, visual verification, and publishing as **PENDING**. Do not claim the dashboard was created, validated, or published. Do not alter Bronze, Silver, Gold, or the job; no new business rules. Implement directly; report completed deliverables and workspace steps you must perform. Context: `task-breakdown.md`, `data-quality-strategy.md`, `data-model.md`, `database/schema.sql`, `spec.md`, `src/gold/`.

**Cursor Output**  
Added `src/dashboard/dashboard_queries.sql` (Gold-only SELECTs for top 10 products, bucketed revenue distribution, segmentation, daily/weekly trends) and `src/dashboard/DASHBOARD_GUIDE.md` (UI recreate steps, validation checklist, screenshot list; creation / verify / publish marked PENDING). Updated T5 checkboxes in `task-breakdown.md` for repo SQL + guide only. No Databricks dashboard creation or publish claimed.

**Review / Decision**  
Accepted as the repo-side T5 start; UI work left to you.

---

## 2. Make the dashboard deployable via Asset Bundle

**Prompt / Request**  
Complete T5 by making the Gold-only AI/BI dashboard deployable through the existing Databricks Asset Bundle. Create a valid `.lvdash.json` and a resource YAML under `resources/` with: top 10 bar, revenue histogram-style bar, segmentation pie, daily revenue line (DAY only). Reuse Gold-only SQL; keep warehouse ID configurable; no hardcoded host/credentials; leave Bronze → Silver → Gold job unchanged. Update `DASHBOARD_GUIDE.md` with bundle deploy/validate instructions. Run `bundle validate` with isolated `DE_C1_FREE` and `/opt/homebrew/bin/databricks` only (`$HOME/.config/databricks-de-c1/.databrickscfg`); never access `~/.databrickscfg` or change auth. Do not deploy or run the pipeline. Report files, validation results, and exact deploy commands for you.

**Cursor Output**  
Added `src/dashboard/ecommerce_gold_dashboard.lvdash.json` (four tiles) and `resources/ecommerce_gold_dashboard.yml`. Extended `databricks.yml` with `warehouse_id` lookup (`Serverless Starter Warehouse`) and sync exclude for `src/dashboard/*.lvdash.json`. Aligned `dashboard_queries.sql` dataset 4 to `period_grain = 'DAY'`; rewrote guide for bundle workflow; light updates to `docs/bundle-deployment.md` and T5 tracker. Executed `databricks bundle validate -t free --profile DE_C1_FREE` → **Validation OK!** No deploy.

**Review / Decision**  
Accepted; you deploy manually.

---

## 3. Presentation refine from screenshot (horizontal bars, buckets, legend, category filter)

**Reason for Refinement**  
Deployed dashboard screenshot: vertical top-products labels hard to read; technical bucket names; want clearer presentation while keeping four Gold tiles.

**Changes Requested**  
Horizontal Top 10 with readable `product_name` and `total_revenue`; human-readable histogram buckets with correct order; keep segmentation legend including zero-count Inactive; keep daily trend; add a simple category filter if supported cleanly. Update `.lvdash.json` and SQL; correct guide for actual `c1_gold` names, `period_grain=DAY`, and Asset Bundle workflow. Validate with isolated C1 config; do not deploy.

**Cursor Implementation**  
Top products: horizontal bar (revenue on X, product on Y, labels on). Buckets: `$0–$99` … `$5,000+` with sort order. Pie: explicit segment order including Inactive, legend visible. Page multi-select **Product category** bound to products dataset. Guide updated. `bundle validate` → **Validation OK!**

**Review / Decision**  
Accepted as a presentation pass; further filter-layout feedback followed.

---

## 4. Local filter placement (beside charts; add date range)

**Reason for Refinement**  
Category filter in the header looked global though it only affected Top 10.

**Changes Requested**  
Move **Top products: category** beside the Top 10 chart; add **Daily trend: date range** beside the daily line; do not apply filters to Gold datasets lacking category/date; no Gold/job changes. Validate; do not deploy.

**Cursor Implementation**  
Relabeled and repositioned category filter beside Top 10; added date-range filter beside daily trend bound only to `ds04dayt` / `period_start`. Guide updated for local (not global) filters. `bundle validate` → **Validation OK!**

**Review / Decision**  
Accepted for scoping; screenshot then showed full-height filter tiles squeezing chart width.

---

## 5. Compact filters above charts; category before LIMIT 10

**Reason for Refinement**  
Screenshot: filters as full-height side tiles narrowed charts and broke the two-column look. Also needed top-10 **within** a selected category (filter before `LIMIT 10`).

**Changes Requested**  
Compact category dropdown above Top 10; compact date range above daily trend; restore two-column chart widths; category selection must rank top 10 within category (`ORDER BY total_revenue DESC` after filter, before `LIMIT 10`); date filter daily-only; no Gold/job changes. Update definition and SQL; validate; do not deploy.

**Cursor Implementation**  
Layout: `height: 1` filters above charts; charts `width: 3`. Products dataset: MULTI param `:category_filter` with `WHERE (size(:category_filter) = 0 OR array_contains(...))` before `LIMIT 10`; `ds01cats` for DISTINCT category options. Date filter remains `ds04dayt` only. SQL + guide updated. `bundle validate` → **Validation OK!**

**Review / Decision**  
Accepted pending your deploy; deploy then failed on a missing parameter field (next turn).

---

## 6. Fix deploy validation — parameter `displayName`

**Reason for Refinement**  
Deploy error: `dashboard.datasets[ds01prod].parameters[0].displayName should not be empty` (400 INVALID_PARAMETER_VALUE).

**Changes Requested**  
Fix; validate the bundle; do not deploy.

**Cursor Implementation**  
Set `displayName: "Category"` on `ds01prod.parameters[0]`. `bundle validate -t free --profile DE_C1_FREE` → **Validation OK!**

**Review / Decision**  
Accepted; redeploy left to you.

---

## Summary

| Item | Outcome in this conversation |
|---|---|
| Gold-only SQL + guide | `dashboard_queries.sql`, `DASHBOARD_GUIDE.md`; UI create/verify/publish left PENDING for you |
| Bundle dashboard | `.lvdash.json` + `resources/ecommerce_gold_dashboard.yml`; `warehouse_id` lookup; job unchanged |
| Visualizations | Horizontal top 10; readable revenue buckets; segmentation pie (incl. Inactive); daily line (`period_grain = 'DAY'`) |
| Filters | Compact category above Top 10 (MULTI param **before** LIMIT 10); compact date range above daily trend only |
| `bundle validate` | Repeatedly **Validation OK!** under isolated `DE_C1_FREE` |
| Left open | Your `bundle deploy`; visual verification and publish in workspace |
