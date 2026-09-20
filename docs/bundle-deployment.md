# Databricks Asset Bundle — deployment guide

Minimal Bronze → Silver → Gold job for Databricks serverless, plus an
optional Gold-only AI/BI dashboard resource. No wheel packaging or
notebook conversion.

Dashboard details: `src/dashboard/DASHBOARD_GUIDE.md`.

After cloning, point the Databricks CLI at **your** workspace with
`--profile <your-profile>`. The bundle does not hardcode a host or
profile; the selected CLI profile supplies the workspace URL.

## Prerequisites

- Databricks CLI installed (`databricks -v`)
- A Databricks CLI profile whose `host` is the target workspace
- Unity Catalog catalog already exists (default variable: `workspace`)
- Landing CSVs on a Volume path your job can read (default variable:
  `/Volumes/workspace/c1_landing/landing` — override if yours differs)
- Schemas for Bronze / Silver / Gold (defaults `c1_bronze` / `c1_silver` /
  `c1_gold`) are created by `database/schema.sql` on first pipeline run,
  or create them beforehand

## Security

- Prefer a project-specific config file over sharing credentials in git.
- Never commit tokens, passwords, or `.databrickscfg`.
- Authentication stays outside the repository; this guide does not
  change how you log in.

Optional (isolated config file instead of the default
`~/.databrickscfg`):

```bash
export DATABRICKS_CONFIG_FILE="/path/to/your/.databrickscfg"
```

## Validate

```bash
cd /path/to/databricks-medallion-pipeline
# If Terraform download fails on checksum verification, point the CLI
# at an already-installed binary. DATABRICKS_TF_VERSION must match the
# version string this CLI expects (often 1.5.5).
export DATABRICKS_TF_VERSION=1.5.5
export DATABRICKS_TF_EXEC_PATH=/opt/homebrew/bin/terraform   # or your path
databricks bundle validate -t free --profile <YOUR_PROFILE>
```

Do not run `terraform init` / `apply` for this project.

Override pipeline variables when your catalog, schemas, or landing path
differ from the defaults:

```bash
databricks bundle validate -t free --profile <YOUR_PROFILE> \
  --var="catalog=workspace" \
  --var="bronze_schema=c1_bronze" \
  --var="silver_schema=c1_silver" \
  --var="gold_schema=c1_gold" \
  --var="landing_path=/Volumes/workspace/c1_landing/landing"
```

## Deploy (you run this)

```bash
databricks bundle deploy -t free --profile <YOUR_PROFILE>
```

Syncs `src/` and `database/` and creates/updates the
`ecommerce-medallion-pipeline` job.

## Run (you run this)

```bash
databricks bundle run ecommerce_medallion_pipeline -t free --profile <YOUR_PROFILE>
```

Optional job-parameter overrides:

```bash
databricks bundle run ecommerce_medallion_pipeline -t free --profile <YOUR_PROFILE> -- \
  --catalog=workspace \
  --bronze_schema=c1_bronze \
  --silver_schema=c1_silver \
  --gold_schema=c1_gold \
  --landing_path=/Volumes/workspace/c1_landing/landing
```

Job flow: `bronze_ingest` → (on success) → `silver_validate` → (on success)
→ `gold_aggregate`. All three tasks use serverless (`environment_key: default`).

## Configurable settings

| Variable / job parameter | Default in `databricks.yml` |
| ------------------------ | --------------------------- |
| `catalog`                | `workspace`                 |
| `bronze_schema`          | `c1_bronze`                 |
| `silver_schema`          | `c1_silver`                 |
| `gold_schema`            | `c1_gold`                   |
| `landing_path`           | `/Volumes/workspace/c1_landing/landing` |
| `warehouse_id`           | Lookup: `Serverless Starter Warehouse` (override with `--var`) |

Dashboard resource `ecommerce_gold_dashboard` also binds:
`dataset_catalog=${var.catalog}` and `dataset_schema=${var.gold_schema}`
so unqualified Gold table names in `.lvdash.json` follow the same overrides
as the pipeline job (requires Databricks CLI ≥ 0.283.0).

Defaults are passed as CLI flags to `src/bronze/ingest_all.py`,
`src/silver/create_silver_tables.py`, and `src/gold/create_gold_tables.py`.
Change them per clone with `--var` at validate/deploy time or by editing
target `variables`.

## Imports on serverless

Entry points add the synced repo root to `sys.path` so `import src...`
works without a wheel. `database/schema.sql` must remain next to `src/`
in the synced workspace files (bundle `sync.include`).

## Local example (DE_C1_FREE)

This is one developer’s isolated Free Edition setup—not a requirement
for other clones.

```bash
export DATABRICKS_CONFIG_FILE="$HOME/.config/databricks-de-c1/.databrickscfg"
export DATABRICKS_TF_VERSION=1.5.5
export DATABRICKS_TF_EXEC_PATH=/opt/homebrew/bin/terraform
databricks bundle validate -t free --profile DE_C1_FREE
databricks bundle deploy -t free --profile DE_C1_FREE
databricks bundle run ecommerce_medallion_pipeline -t free --profile DE_C1_FREE
```

That profile’s config file is separate from `~/.databrickscfg`.

## Workspace validation evidence

Serverless Bronze → Silver → Gold job and table contracts are recorded under
`tests/summary/` (`ts-02` … `ts-07`). The Gold AI/BI dashboard is deployed and
visually verified (four tiles + scoped filters); see
`src/dashboard/DASHBOARD_GUIDE.md`.
