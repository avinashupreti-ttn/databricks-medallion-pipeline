"""TS-01 checks for the sample CSVs.

Expected counts and columns are literals from data-model.md and
data-quality-strategy.md. This file does not call verify_output() and
does not import generator count constants.
"""

import csv
import subprocess
import sys
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
GENERATOR = REPO_ROOT / "src" / "data_generation" / "generate_sample_data.py"
SEED = 42

CUSTOMER_COLUMNS = (
    "customer_id",
    "customer_name",
    "email",
    "country",
    "signup_date",
    "customer_segment",
    "lifetime_value",
)
ORDER_COLUMNS = (
    "order_id",
    "customer_id",
    "order_date",
    "product_id",
    "quantity",
    "unit_price",
    "total_amount",
    "order_status",
    "payment_date",
)
PRODUCT_COLUMNS = (
    "product_id",
    "product_name",
    "category",
    "price",
    "cost",
    "stock_quantity",
    "reorder_level",
)

CUSTOMER_SEGMENTS = {"Premium", "Standard", "Basic"}
ORDER_STATUSES = {"Pending", "Completed", "Cancelled"}


def _read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return tuple(reader.fieldnames or ()), list(reader)


def _generate(output_dir, seed):
    completed = subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
            "--seed",
            str(seed),
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)


def _keys_seen_more_than_once(values):
    counts = Counter(values)
    return {key for key, count in counts.items() if count > 1}, counts


def _customer_issues(row, duplicate_ids):
    issues = 0
    if row["email"].strip() == "":
        issues += 1
    if row["customer_id"] in duplicate_ids:
        issues += 1
    return issues


def _order_issues(row, parent_customers, parent_products, duplicate_ids):
    issues = 0
    customer_id = row["customer_id"].strip()
    product_id = row["product_id"].strip()
    if customer_id == "":
        issues += 1
    elif int(customer_id) not in parent_customers:
        issues += 1
    if product_id == "":
        issues += 1
    elif int(product_id) not in parent_products:
        issues += 1
    if row["order_id"] in duplicate_ids:
        issues += 1
    return issues


@pytest.fixture(scope="module")
def tables():
    customers = _read_csv(DATA_DIR / "customers.csv")
    orders = _read_csv(DATA_DIR / "orders.csv")
    products = _read_csv(DATA_DIR / "products.csv")
    return {"customers": customers, "orders": orders, "products": products}


def test_schemas_and_row_counts(tables):
    customer_columns, customers = tables["customers"]
    order_columns, orders = tables["orders"]
    product_columns, products = tables["products"]

    assert customer_columns == CUSTOMER_COLUMNS
    assert order_columns == ORDER_COLUMNS
    assert product_columns == PRODUCT_COLUMNS
    assert len(customers) == 10000
    assert len(orders) == 100000
    assert len(products) == 500


def test_source_value_domains(tables):
    _, customers = tables["customers"]
    _, orders = tables["orders"]
    _, products = tables["products"]

    for row in customers:
        assert row["customer_id"].isdigit()
        assert row["customer_name"].strip() != ""
        assert row["country"].strip() != ""
        date.fromisoformat(row["signup_date"])
        assert row["customer_segment"] in CUSTOMER_SEGMENTS
        Decimal(row["lifetime_value"])

    for row in orders:
        assert row["order_id"].isdigit()
        assert row["order_status"] in ORDER_STATUSES
        date.fromisoformat(row["order_date"])
        assert row["quantity"].isdigit()
        Decimal(row["unit_price"])
        Decimal(row["total_amount"])
        if row["customer_id"].strip() != "":
            assert row["customer_id"].strip().isdigit()
        if row["product_id"].strip() != "":
            assert row["product_id"].strip().isdigit()
        if row["payment_date"].strip() != "":
            date.fromisoformat(row["payment_date"])

    product_ids = []
    for row in products:
        assert row["product_id"].isdigit()
        product_ids.append(row["product_id"])
        assert row["product_name"].strip() != ""
        assert row["category"].strip() != ""
        Decimal(row["price"])
        Decimal(row["cost"])
        assert row["stock_quantity"].isdigit()
        assert row["reorder_level"].isdigit()
    assert len(set(product_ids)) == 500


def test_intentional_defect_counts(tables):
    _, customers = tables["customers"]
    _, orders = tables["orders"]
    _, products = tables["products"]
    parent_customers = {int(row["customer_id"]) for row in customers}
    parent_products = {int(row["product_id"]) for row in products}

    assert sum(row["email"].strip() == "" for row in customers) == 50

    _, customer_counts = _keys_seen_more_than_once(row["customer_id"] for row in customers)
    assert sum(count for count in customer_counts.values() if count > 1) == 10

    null_customer = 0
    null_product = 0
    unknown_customer = 0
    unknown_product = 0
    for row in orders:
        customer_id = row["customer_id"].strip()
        product_id = row["product_id"].strip()
        if customer_id == "":
            null_customer += 1
        elif int(customer_id) not in parent_customers:
            unknown_customer += 1
        if product_id == "":
            null_product += 1
        elif int(product_id) not in parent_products:
            unknown_product += 1
    assert null_customer == 100
    assert null_product == 200
    assert unknown_customer == 50
    assert unknown_product == 30

    _, order_counts = _keys_seen_more_than_once(row["order_id"] for row in orders)
    assert sum(count for count in order_counts.values() if count > 1) == 20

    assert all(value.strip() != "" for row in products for value in row.values())


def test_duplicate_groups_are_pairs(tables):
    _, customers = tables["customers"]
    _, orders = tables["orders"]

    _, customer_counts = _keys_seen_more_than_once(row["customer_id"] for row in customers)
    customer_pairs = [count for count in customer_counts.values() if count > 1]
    assert len(customer_pairs) == 5
    assert all(count == 2 for count in customer_pairs)

    _, order_counts = _keys_seen_more_than_once(row["order_id"] for row in orders)
    order_pairs = [count for count in order_counts.values() if count > 1]
    assert len(order_pairs) == 10
    assert all(count == 2 for count in order_pairs)


def test_distinct_defective_rows_and_no_overlap(tables):
    _, customers = tables["customers"]
    _, orders = tables["orders"]
    _, products = tables["products"]
    parent_customers = {int(row["customer_id"]) for row in customers}
    parent_products = {int(row["product_id"]) for row in products}
    duplicate_customers, _ = _keys_seen_more_than_once(row["customer_id"] for row in customers)
    duplicate_orders, _ = _keys_seen_more_than_once(row["order_id"] for row in orders)

    # A row in several defect groups still counts once. Overlap is separate.
    customer_distinct = 0
    customer_overlap = 0
    for row in customers:
        issues = _customer_issues(row, duplicate_customers)
        if issues:
            customer_distinct += 1
        if issues > 1:
            customer_overlap += 1

    order_distinct = 0
    order_overlap = 0
    for row in orders:
        issues = _order_issues(row, parent_customers, parent_products, duplicate_orders)
        if issues:
            order_distinct += 1
        if issues > 1:
            order_overlap += 1

    assert customer_overlap == 0
    assert order_overlap == 0
    assert customer_distinct == 60
    assert order_distinct == 400
    assert customer_distinct + order_distinct == 460
    assert len(products) == 500


def test_non_defective_orders_have_valid_foreign_keys(tables):
    _, customers = tables["customers"]
    _, orders = tables["orders"]
    _, products = tables["products"]
    parent_customers = {int(row["customer_id"]) for row in customers}
    parent_products = {int(row["product_id"]) for row in products}
    duplicate_orders, _ = _keys_seen_more_than_once(row["order_id"] for row in orders)

    clean_orders = 0
    for row in orders:
        if _order_issues(row, parent_customers, parent_products, duplicate_orders):
            continue
        clean_orders += 1
        assert int(row["customer_id"]) in parent_customers
        assert int(row["product_id"]) in parent_products
    assert clean_orders == 100000 - 400


def test_payment_date_follows_status(tables):
    _, orders = tables["orders"]
    for row in orders:
        status = row["order_status"]
        payment_date = row["payment_date"].strip()
        if status == "Completed":
            assert payment_date != ""
            assert date.fromisoformat(payment_date) >= date.fromisoformat(row["order_date"])
        else:
            assert status in {"Pending", "Cancelled"}
            assert payment_date == ""


def test_same_seed_is_byte_identical(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _generate(first, SEED)
    _generate(second, SEED)
    for name in ("customers.csv", "orders.csv", "products.csv"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
        assert (first / name).read_bytes() == (DATA_DIR / name).read_bytes()
