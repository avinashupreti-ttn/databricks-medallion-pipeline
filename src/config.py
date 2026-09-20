"""Runtime configuration for Databricks serverless.

Required settings: catalog, bronze_schema, silver_schema, landing_path.
Optional: gold_schema (reserved for Gold; not used by Bronze/Silver yet).

Resolution order: CLI arguments, then environment variables, then
Databricks widgets when a Spark session is already active.

Environment variables: PIPELINE_CATALOG, PIPELINE_BRONZE_SCHEMA,
PIPELINE_SILVER_SCHEMA, PIPELINE_GOLD_SCHEMA, PIPELINE_LANDING_PATH.
Widgets: catalog, bronze_schema, silver_schema, gold_schema, landing_path.

Databricks Free Edition example:
  catalog=workspace, bronze_schema=c1_bronze, silver_schema=c1_silver,
  gold_schema=c1_gold, landing_path=/Volumes/workspace/c1_landing/landing

landing_path is the directory that contains customers.csv, orders.csv,
and products.csv. On serverless, use a Unity Catalog Volume
(/Volumes/...) or a dbfs: URI. Do not rely on the /dbfs FUSE mount.
"""

from __future__ import annotations

import os
import re

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

ENV_VARS = {
    "catalog": "PIPELINE_CATALOG",
    "bronze_schema": "PIPELINE_BRONZE_SCHEMA",
    "silver_schema": "PIPELINE_SILVER_SCHEMA",
    "gold_schema": "PIPELINE_GOLD_SCHEMA",
    "landing_path": "PIPELINE_LANDING_PATH",
}
WIDGET_NAMES = {
    "catalog": "catalog",
    "bronze_schema": "bronze_schema",
    "silver_schema": "silver_schema",
    "gold_schema": "gold_schema",
    "landing_path": "landing_path",
}
REQUIRED_SETTINGS = ("catalog", "bronze_schema", "silver_schema", "landing_path")
OPTIONAL_SETTINGS = ("gold_schema",)
SETTING_ORDER = REQUIRED_SETTINGS + OPTIONAL_SETTINGS


class PipelineConfig:
    """Catalog, layer schemas, and landing directory for one pipeline run."""

    def __init__(
        self,
        catalog: str,
        bronze_schema: str,
        silver_schema: str,
        landing_path: str,
        gold_schema: str | None = None,
    ) -> None:
        self.catalog = catalog
        self.bronze_schema = bronze_schema
        self.silver_schema = silver_schema
        self.landing_path = landing_path
        self.gold_schema = gold_schema


def validate_identifier(value: str, label: str) -> str:
    """Reject catalog or schema names that are unsafe to interpolate into SQL."""
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(
            f"Invalid {label} {value!r}. Use a letter or underscore, "
            "then only letters, digits, or underscores."
        )
    return value


def validate_batch_id(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or any(char in cleaned for char in ("`", ";", "\n", "\r")):
        raise ValueError(f"Invalid batch id: {value!r}.")
    return cleaned


def _widget_values() -> dict[str, str]:
    """Read widgets only from an already-active Databricks session.

    Does not create a Spark session. Local runs without PySpark get no widgets.
    """
    try:
        from pyspark.sql import SparkSession
    except ImportError:
        return {}
    spark = SparkSession.getActiveSession()
    if spark is None:
        return {}
    try:
        from pyspark.dbutils import DBUtils
    except ImportError:
        return {}
    dbutils = DBUtils(spark)
    found = {}
    for key, widget_name in WIDGET_NAMES.items():
        try:
            found[key] = str(dbutils.widgets.get(widget_name)).strip()
        except Exception:
            found[key] = ""
    return found


def resolve_config(
    catalog: str | None = None,
    bronze_schema: str | None = None,
    silver_schema: str | None = None,
    landing_path: str | None = None,
    gold_schema: str | None = None,
) -> PipelineConfig:
    """Resolve required settings or raise ValueError naming what is missing."""
    provided = {
        "catalog": catalog,
        "bronze_schema": bronze_schema,
        "silver_schema": silver_schema,
        "gold_schema": gold_schema,
        "landing_path": landing_path,
    }
    resolved = {}
    missing = []
    for key in SETTING_ORDER:
        value = (provided[key] or "").strip()
        if not value:
            value = os.environ.get(ENV_VARS[key], "").strip()
        if value:
            resolved[key] = value
        elif key in REQUIRED_SETTINGS:
            missing.append(key)
    if missing or "gold_schema" not in resolved:
        widgets = _widget_values()
        still_missing = []
        for key in missing:
            value = widgets.get(key, "").strip()
            if value:
                resolved[key] = value
            else:
                still_missing.append(key)
        missing = still_missing
        if "gold_schema" not in resolved:
            gold_value = widgets.get("gold_schema", "").strip()
            if gold_value:
                resolved["gold_schema"] = gold_value
    if missing:
        names = ", ".join(missing)
        raise ValueError(
            f"Missing required configuration: {names}. "
            "Set --catalog, --bronze-schema, --silver-schema, and --landing-path, "
            "or environment variables PIPELINE_CATALOG, PIPELINE_BRONZE_SCHEMA, "
            "PIPELINE_SILVER_SCHEMA, and PIPELINE_LANDING_PATH, "
            "or Databricks widgets named catalog, bronze_schema, silver_schema, "
            "and landing_path."
        )
    validate_identifier(resolved["catalog"], "catalog")
    validate_identifier(resolved["bronze_schema"], "bronze_schema")
    validate_identifier(resolved["silver_schema"], "silver_schema")
    gold = resolved.get("gold_schema")
    if gold:
        validate_identifier(gold, "gold_schema")
    return PipelineConfig(
        resolved["catalog"],
        resolved["bronze_schema"],
        resolved["silver_schema"],
        resolved["landing_path"],
        gold,
    )
