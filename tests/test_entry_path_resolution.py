"""Entry-point repo-root resolution without __file__.

Databricks serverless spark_python_task runs scripts via
exec(compile(source, filename, "exec")), so __file__ is undefined while
co_filename still carries the real path.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRY_POINTS = (
    REPO_ROOT / "src" / "bronze" / "ingest_all.py",
    REPO_ROOT / "src" / "silver" / "create_silver_tables.py",
)


@pytest.mark.parametrize("script_path", ENTRY_POINTS, ids=lambda p: p.name)
def test_entry_point_resolves_repo_root_without_file(script_path: Path):
    source = script_path.read_text(encoding="utf-8")
    filename = str(script_path.resolve())
    namespace = {"__name__": "__databricks_exec__"}
    assert "__file__" not in namespace

    code = compile(source, filename, "exec")
    exec(code, namespace)

    assert "__file__" not in namespace
    root = Path(namespace["REPO_ROOT"]).resolve()
    assert root == REPO_ROOT.resolve()
    assert (root / "src").is_dir()
    assert (root / "database" / "schema.sql").is_file()
    assert str(root) in sys.path
    if "SCHEMA_PATH" in namespace:
        assert Path(namespace["SCHEMA_PATH"]).resolve() == (
            REPO_ROOT / "database" / "schema.sql"
        ).resolve()


@pytest.mark.parametrize("script_path", ENTRY_POINTS, ids=lambda p: p.name)
def test_finish_success_does_not_raise_system_exit(script_path: Path):
    source = script_path.read_text(encoding="utf-8")
    namespace = {"__name__": "__databricks_exec__"}
    exec(compile(source, str(script_path.resolve()), "exec"), namespace)
    finish = namespace["finish"]
    assert finish(0) is None


@pytest.mark.parametrize("script_path", ENTRY_POINTS, ids=lambda p: p.name)
def test_finish_failure_raises_nonzero_system_exit(script_path: Path):
    source = script_path.read_text(encoding="utf-8")
    namespace = {"__name__": "__databricks_exec__"}
    exec(compile(source, str(script_path.resolve()), "exec"), namespace)
    finish = namespace["finish"]
    with pytest.raises(SystemExit) as raised:
        finish(1)
    assert raised.value.code == 1


@pytest.mark.parametrize(
    "script_path",
    ENTRY_POINTS,
    ids=lambda p: p.name,
)
def test_cli_failure_still_exits_nonzero(script_path: Path):
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("PIPELINE_")
    }
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert "Missing required configuration" in completed.stderr
    assert "To exit: use 'exit', 'quit', or Ctrl-D." not in completed.stderr
    assert "To exit: use 'exit', 'quit', or Ctrl-D." not in completed.stdout
