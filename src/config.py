"""Runtime configuration for Databricks serverless.

Required settings: catalog, schema, landing_path.
Resolution order: CLI arguments, then environment variables, then
Databricks widgets when a Spark session is already active.

Environment variables: PIPELINE_CATALOG, PIPELINE_SCHEMA, PIPELINE_LANDING_PATH.
Widgets: catalog, schema, landing_path.

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
    "schema": "PIPELINE_SCHEMA",
    "landing_path": "PIPELINE_LANDING_PATH",
}
WIDGET_NAMES = {
    "catalog": "catalog",
    "schema": "schema",
    "landing_path": "landing_path",
}
SETTING_ORDER = ("catalog", "schema", "landing_path")


class PipelineConfig:
    """Catalog, schema, and landing directory for one pipeline run."""

    def __init__(self, catalog: str, schema: str, landing_path: str) -> None:
        self.catalog = catalog
        self.schema = schema
        self.landing_path = landing_path


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
    schema: str | None = None,
    landing_path: str | None = None,
) -> PipelineConfig:
    """Resolve required settings or raise ValueError naming what is missing."""
    provided = {
        "catalog": catalog,
        "schema": schema,
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
        else:
            missing.append(key)
    if missing:
        widgets = _widget_values()
        still_missing = []
        for key in missing:
            value = widgets.get(key, "").strip()
            if value:
                resolved[key] = value
            else:
                still_missing.append(key)
        missing = still_missing
    if missing:
        names = ", ".join(missing)
        raise ValueError(
            f"Missing required configuration: {names}. "
            "Set --catalog, --schema, and --landing-path, "
            "or environment variables PIPELINE_CATALOG, PIPELINE_SCHEMA, "
            "and PIPELINE_LANDING_PATH, "
            "or Databricks widgets named catalog, schema, and landing_path."
        )
    validate_identifier(resolved["catalog"], "catalog")
    validate_identifier(resolved["schema"], "schema")
    return PipelineConfig(
        resolved["catalog"],
        resolved["schema"],
        resolved["landing_path"],
    )
