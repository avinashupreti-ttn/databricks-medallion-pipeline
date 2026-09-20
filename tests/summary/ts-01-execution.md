# TS-01 execution

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

## Run

```bash
.venv/bin/python -m pytest tests/test_data_generation.py --html=tests/reports/ts-01-report.html --self-contained-html
```

## Open the report

Open `tests/reports/ts-01-report.html` in a browser. It is self-contained; no extra asset files are required.

## Result

Date: 2026-09-20

**8 passed** in 3.95s.
