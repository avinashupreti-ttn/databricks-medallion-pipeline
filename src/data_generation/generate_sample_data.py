#!/usr/bin/env python3
"""Generate synthetic customers, orders, and products CSVs.

Deterministic for a given --seed. Defect groups are fixed, chained index
ranges (not random samples) so counts stay exact and do not overlap.
Contract: data-quality-strategy.md (460 distinct defective rows).
Schemas: data-model.md. Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED = 42
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data"

CUSTOMER_ROW_COUNT = 10000
ORDER_ROW_COUNT = 100000
PRODUCT_ROW_COUNT = 500

# Distinct rows in each defect group. Duplicate counts are rows in the
# group (both copies), not extra rows appended past the file size.
NULL_EMAIL_COUNT = 50
CUSTOMER_DUPLICATE_PAIRS = 5  # 10 customer rows, two per key
NULL_ORDER_CUSTOMER_ID_COUNT = 100
NULL_ORDER_PRODUCT_ID_COUNT = 200
UNKNOWN_CUSTOMER_ID_COUNT = 50
UNKNOWN_PRODUCT_ID_COUNT = 30
ORDER_DUPLICATE_PAIRS = 10  # 20 order rows, two per key

DISTINCT_DEFECT_ROWS = 460
CUSTOMER_DEFECT_ROWS = 60
ORDER_DEFECT_ROWS = 400

# Outside parent key ranges (customers 1..10000, products 1..500).
UNKNOWN_CUSTOMER_ID_BASE = 2_000_001
UNKNOWN_PRODUCT_ID_BASE = 3_000_001

# Chained slices: each group starts where the previous one ends.
NULL_EMAIL_START = 0
NULL_EMAIL_END = NULL_EMAIL_START + NULL_EMAIL_COUNT
CUSTOMER_DUP_START = NULL_EMAIL_END
CUSTOMER_DUP_END = CUSTOMER_DUP_START + (CUSTOMER_DUPLICATE_PAIRS * 2)

NULL_CUSTOMER_START = 0
NULL_CUSTOMER_END = NULL_CUSTOMER_START + NULL_ORDER_CUSTOMER_ID_COUNT
NULL_PRODUCT_START = NULL_CUSTOMER_END
NULL_PRODUCT_END = NULL_PRODUCT_START + NULL_ORDER_PRODUCT_ID_COUNT
UNKNOWN_CUSTOMER_START = NULL_PRODUCT_END
UNKNOWN_CUSTOMER_END = UNKNOWN_CUSTOMER_START + UNKNOWN_CUSTOMER_ID_COUNT
UNKNOWN_PRODUCT_START = UNKNOWN_CUSTOMER_END
UNKNOWN_PRODUCT_END = UNKNOWN_PRODUCT_START + UNKNOWN_PRODUCT_ID_COUNT
ORDER_DUP_START = UNKNOWN_PRODUCT_END
ORDER_DUP_END = ORDER_DUP_START + (ORDER_DUPLICATE_PAIRS * 2)

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

CUSTOMER_SEGMENTS = ("Premium", "Standard", "Basic")
ORDER_STATUSES = ("Pending", "Completed", "Cancelled")
COUNTRIES = (
    "Australia",
    "Brazil",
    "Canada",
    "France",
    "Germany",
    "India",
    "Japan",
    "United Kingdom",
    "United States",
)
CATEGORIES = ("Apparel", "Electronics", "Grocery", "Home", "Sports")

SIGNUP_START = date(2020, 1, 1)
SIGNUP_SPAN_DAYS = (date(2024, 12, 31) - SIGNUP_START).days
ORDER_START = date(2023, 1, 1)
ORDER_SPAN_DAYS = (date(2025, 12, 31) - ORDER_START).days
PAYMENT_LAG_DAYS = 14

MONEY = Decimal("0.01")


def validate_contract() -> None:
    """Fail fast if slice sizes drift from the 460-row contract."""
    customer_defects = NULL_EMAIL_COUNT + (CUSTOMER_DUPLICATE_PAIRS * 2)
    order_defects = (
        NULL_ORDER_CUSTOMER_ID_COUNT
        + NULL_ORDER_PRODUCT_ID_COUNT
        + UNKNOWN_CUSTOMER_ID_COUNT
        + UNKNOWN_PRODUCT_ID_COUNT
        + (ORDER_DUPLICATE_PAIRS * 2)
    )
    if customer_defects != CUSTOMER_DEFECT_ROWS or order_defects != ORDER_DEFECT_ROWS:
        raise ValueError(
            f"defect slice sizes {customer_defects}/{order_defects} "
            f"do not match {CUSTOMER_DEFECT_ROWS}/{ORDER_DEFECT_ROWS}"
        )
    if customer_defects + order_defects != DISTINCT_DEFECT_ROWS:
        raise ValueError("distinct defect total does not equal 460")
    if CUSTOMER_DUP_END > CUSTOMER_ROW_COUNT or ORDER_DUP_END > ORDER_ROW_COUNT:
        raise ValueError("defect slices exceed source row counts")
    if UNKNOWN_CUSTOMER_ID_BASE <= CUSTOMER_ROW_COUNT:
        raise ValueError("unknown customer ids overlap the parent key range")
    if UNKNOWN_PRODUCT_ID_BASE <= PRODUCT_ROW_COUNT:
        raise ValueError("unknown product ids overlap the parent key range")


def random_money(rng: random.Random, min_cents: int, max_cents: int) -> Decimal:
    return (Decimal(rng.randint(min_cents, max_cents)) / Decimal(100)).quantize(MONEY)


def format_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return f"{value.quantize(MONEY):.2f}"
    return str(value)


def write_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=columns,
            lineterminator="\n",
            extrasaction="raise",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({column: format_cell(row[column]) for column in columns})


def generate_products(rng: random.Random) -> list[dict]:
    rows = []
    for index in range(PRODUCT_ROW_COUNT):
        product_id = index + 1
        price_cents = rng.randint(100, 50_000)
        cost_cents = rng.randint(1, price_cents - 1)
        rows.append(
            {
                "product_id": product_id,
                "product_name": f"Product {product_id:04d}",
                "category": CATEGORIES[rng.randrange(len(CATEGORIES))],
                "price": (Decimal(price_cents) / Decimal(100)).quantize(MONEY),
                "cost": (Decimal(cost_cents) / Decimal(100)).quantize(MONEY),
                "stock_quantity": rng.randint(0, 500),
                "reorder_level": rng.randint(0, 100),
            }
        )
    return rows


def generate_customers(rng: random.Random) -> list[dict]:
    rows = []
    for index in range(CUSTOMER_ROW_COUNT):
        customer_id = index + 1
        signup = SIGNUP_START + timedelta(days=rng.randint(0, SIGNUP_SPAN_DAYS))
        rows.append(
            {
                "customer_id": customer_id,
                "customer_name": f"Customer {customer_id:05d}",
                "email": f"customer{customer_id:05d}@example.test",
                "country": COUNTRIES[rng.randrange(len(COUNTRIES))],
                "signup_date": signup.isoformat(),
                "customer_segment": CUSTOMER_SEGMENTS[rng.randrange(len(CUSTOMER_SEGMENTS))],
                "lifetime_value": random_money(rng, 0, 1_000_000),
            }
        )
    apply_customer_defects(rows)
    return rows


def apply_customer_defects(rows: list[dict]) -> None:
    """NULL email on [0, 50); five key pairs on [50, 60). No other changes."""
    for row in rows[NULL_EMAIL_START:NULL_EMAIL_END]:
        row["email"] = None
    for pair_index in range(CUSTOMER_DUPLICATE_PAIRS):
        left = CUSTOMER_DUP_START + (pair_index * 2)
        right = left + 1
        rows[right]["customer_id"] = rows[left]["customer_id"]


def generate_orders(
    rng: random.Random,
    customer_ids: list[int],
    product_ids: list[int],
) -> list[dict]:
    if not customer_ids or not product_ids:
        raise ValueError("cannot generate orders without parent keys")
    rows = []
    for index in range(ORDER_ROW_COUNT):
        # Fixed draw order so the seed stream does not depend on later defects.
        customer_id = customer_ids[rng.randrange(len(customer_ids))]
        product_id = product_ids[rng.randrange(len(product_ids))]
        order_date = ORDER_START + timedelta(days=rng.randint(0, ORDER_SPAN_DAYS))
        quantity = rng.randint(1, 5)
        unit_price = random_money(rng, 100, 20_000)
        status = ORDER_STATUSES[rng.randrange(len(ORDER_STATUSES))]
        # Lag is always drawn. Only Completed keeps it; Pending and Cancelled stay null.
        payment_lag = rng.randint(0, PAYMENT_LAG_DAYS)
        if status == "Completed":
            payment_date = (order_date + timedelta(days=payment_lag)).isoformat()
        else:
            payment_date = None
        rows.append(
            {
                "order_id": index + 1,
                "customer_id": customer_id,
                "order_date": order_date.isoformat(),
                "product_id": product_id,
                "quantity": quantity,
                "unit_price": unit_price,
                "total_amount": (unit_price * quantity).quantize(MONEY),
                "order_status": status,
                "payment_date": payment_date,
            }
        )
    apply_order_defects(rows, set(customer_ids), set(product_ids))
    return rows


def apply_order_defects(
    rows: list[dict],
    valid_customer_ids: set[int],
    valid_product_ids: set[int],
) -> None:
    """Inject order defects on chained slices. Later slices are not rewritten."""
    for row in rows[NULL_CUSTOMER_START:NULL_CUSTOMER_END]:
        row["customer_id"] = None
    for row in rows[NULL_PRODUCT_START:NULL_PRODUCT_END]:
        row["product_id"] = None
    for offset, row in enumerate(rows[UNKNOWN_CUSTOMER_START:UNKNOWN_CUSTOMER_END]):
        orphan_id = UNKNOWN_CUSTOMER_ID_BASE + offset
        if orphan_id in valid_customer_ids:
            raise ValueError(f"orphan customer_id {orphan_id} is present on a customer row")
        row["customer_id"] = orphan_id
    for offset, row in enumerate(rows[UNKNOWN_PRODUCT_START:UNKNOWN_PRODUCT_END]):
        orphan_id = UNKNOWN_PRODUCT_ID_BASE + offset
        if orphan_id in valid_product_ids:
            raise ValueError(f"orphan product_id {orphan_id} is present on a product row")
        row["product_id"] = orphan_id
    for pair_index in range(ORDER_DUPLICATE_PAIRS):
        left = ORDER_DUP_START + (pair_index * 2)
        right = left + 1
        rows[right]["order_id"] = rows[left]["order_id"]


def read_csv(path: Path, columns: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        if fieldnames != columns:
            raise ValueError(f"{path.name} columns {fieldnames} != {columns}")
        return list(reader)


def _parse_int(value: str) -> int | None:
    if value == "":
        return None
    return int(value)


def _key_groups(values: list[int]) -> tuple[int, int, set[int]]:
    """Return rows in duplicate groups, pair-key count, and those keys.

    Keys that appear more than twice are included. Caller checks pair size.
    """
    counts = Counter(values)
    pair_keys = {key for key, count in counts.items() if count > 1}
    involved = sum(counts[key] for key in pair_keys)
    return involved, len(pair_keys), pair_keys


def verify_output(output_dir: Path) -> list[str]:
    """Re-read the CSVs and return contract mismatches. Empty list means pass."""
    errors: list[str] = []

    def expect(name: str, actual: int, expected: int) -> None:
        if actual != expected:
            errors.append(f"{name}: actual {actual}, expected {expected}")

    customers = read_csv(output_dir / "customers.csv", CUSTOMER_COLUMNS)
    orders = read_csv(output_dir / "orders.csv", ORDER_COLUMNS)
    products = read_csv(output_dir / "products.csv", PRODUCT_COLUMNS)

    expect("customer rows", len(customers), CUSTOMER_ROW_COUNT)
    expect("order rows", len(orders), ORDER_ROW_COUNT)
    expect("product rows", len(products), PRODUCT_ROW_COUNT)

    null_email_rows = [row for row in customers if row["email"].strip() == ""]
    expect("null email", len(null_email_rows), NULL_EMAIL_COUNT)
    if any(row["email"] != row["email"].strip() for row in customers):
        errors.append("email has leading or trailing whitespace")

    customer_ids = [_parse_int(row["customer_id"]) for row in customers]
    if any(value is None for value in customer_ids):
        errors.append("customer_id is null on a customer row")
        typed_customer_ids = [value for value in customer_ids if value is not None]
    else:
        typed_customer_ids = [value for value in customer_ids if value is not None]
    customer_dup_rows, customer_dup_keys, customer_dup_ids = _key_groups(typed_customer_ids)
    if any(Counter(typed_customer_ids)[key] != 2 for key in customer_dup_ids):
        errors.append("a customer_id appears more than twice")
    expect("customer uniqueness rows", customer_dup_rows, CUSTOMER_DUPLICATE_PAIRS * 2)
    expect("customer duplicate keys", customer_dup_keys, CUSTOMER_DUPLICATE_PAIRS)
    parent_customer_ids = set(typed_customer_ids)
    null_email_overlap = sum(
        1 for row in null_email_rows if _parse_int(row["customer_id"]) in customer_dup_ids
    )
    if null_email_overlap:
        errors.append(f"null-email rows also in duplicate groups: {null_email_overlap}")
    customer_defect_rows = len(null_email_rows) + customer_dup_rows - null_email_overlap
    expect("customer defect rows", customer_defect_rows, CUSTOMER_DEFECT_ROWS)

    product_ids = [_parse_int(row["product_id"]) for row in products]
    if any(value is None for value in product_ids) or product_ids != list(range(1, PRODUCT_ROW_COUNT + 1)):
        errors.append("product_id values are not 1..500 exactly once")
    parent_product_ids = {value for value in product_ids if value is not None}

    order_ids: list[int] = []
    parsed_orders: list[tuple[dict[str, str], int | None, int | None, int | None]] = []
    for row in orders:
        order_id = _parse_int(row["order_id"])
        parsed_orders.append((row, order_id, _parse_int(row["customer_id"]), _parse_int(row["product_id"])))
        if order_id is not None:
            order_ids.append(order_id)
    order_dup_rows, order_dup_keys, order_dup_ids = _key_groups(order_ids)
    if any(Counter(order_ids)[key] != 2 for key in order_dup_ids):
        errors.append("an order_id appears more than twice")
    expect("order uniqueness rows", order_dup_rows, ORDER_DUPLICATE_PAIRS * 2)
    expect("order duplicate keys", order_dup_keys, ORDER_DUPLICATE_PAIRS)

    null_customer = 0
    null_product = 0
    unknown_customer = 0
    unknown_product = 0
    order_defect_rows = 0
    overlap_rows = 0
    domain_errors = 0
    for row, order_id, customer_id, product_id in parsed_orders:
        categories = 0
        if customer_id is None:
            null_customer += 1
            categories += 1
        elif customer_id not in parent_customer_ids:
            unknown_customer += 1
            categories += 1
        if product_id is None:
            null_product += 1
            categories += 1
        elif product_id not in parent_product_ids:
            unknown_product += 1
            categories += 1
        if order_id in order_dup_ids:
            categories += 1
        if categories > 1:
            overlap_rows += 1
        if categories:
            order_defect_rows += 1
        if order_id is None or not _order_values_ok(row):
            domain_errors += 1

    expect("null order customer_id", null_customer, NULL_ORDER_CUSTOMER_ID_COUNT)
    expect("null order product_id", null_product, NULL_ORDER_PRODUCT_ID_COUNT)
    expect("unknown customer_id", unknown_customer, UNKNOWN_CUSTOMER_ID_COUNT)
    expect("unknown product_id", unknown_product, UNKNOWN_PRODUCT_ID_COUNT)
    expect("order defect rows", order_defect_rows, ORDER_DEFECT_ROWS)
    if overlap_rows:
        errors.append(f"order rows in more than one defect group: {overlap_rows}")
    expect(
        "distinct defective rows",
        customer_defect_rows + order_defect_rows,
        DISTINCT_DEFECT_ROWS,
    )
    if domain_errors:
        errors.append(f"order value/domain violations: {domain_errors}")

    customer_domain_errors = sum(1 for row in customers if not _customer_values_ok(row))
    product_domain_errors = sum(1 for row in products if not _product_values_ok(row))
    if customer_domain_errors:
        errors.append(f"customer value/domain violations: {customer_domain_errors}")
    if product_domain_errors:
        errors.append(f"product value/domain violations: {product_domain_errors}")

    _print_measured(
        output_dir,
        len(customers),
        len(orders),
        len(products),
        len(null_email_rows),
        customer_dup_rows,
        null_customer,
        null_product,
        unknown_customer,
        unknown_product,
        order_dup_rows,
        customer_defect_rows + order_defect_rows,
    )
    return errors


def _order_values_ok(row: dict[str, str]) -> bool:
    status = row["order_status"]
    if status not in ORDER_STATUSES:
        return False
    try:
        quantity = int(row["quantity"])
        unit_price = Decimal(row["unit_price"])
        total_amount = Decimal(row["total_amount"])
        order_date = date.fromisoformat(row["order_date"])
        payment_raw = row["payment_date"]
        payment_date = date.fromisoformat(payment_raw) if payment_raw else None
    except (ValueError, ArithmeticError):
        return False
    # Generation assumption only: Completed is paid on or after order_date.
    if status == "Completed":
        if payment_date is None or payment_date < order_date:
            return False
    elif payment_date is not None:
        return False
    if quantity <= 0 or unit_price < 0 or total_amount < 0:
        return False
    return total_amount == (unit_price * quantity).quantize(MONEY)


def _customer_values_ok(row: dict[str, str]) -> bool:
    if row["customer_segment"] not in CUSTOMER_SEGMENTS:
        return False
    if not row["customer_name"].strip() or not row["country"].strip():
        return False
    try:
        date.fromisoformat(row["signup_date"])
        if Decimal(row["lifetime_value"]) < 0:
            return False
    except (ValueError, ArithmeticError):
        return False
    email = row["email"]
    return email == "" or email.strip() != ""


def _product_values_ok(row: dict[str, str]) -> bool:
    if not row["product_name"].strip() or row["category"] not in CATEGORIES:
        return False
    try:
        price = Decimal(row["price"])
        cost = Decimal(row["cost"])
        stock = int(row["stock_quantity"])
        reorder = int(row["reorder_level"])
    except (ValueError, ArithmeticError):
        return False
    return price >= 0 and cost >= 0 and stock >= 0 and reorder >= 0 and cost < price


def _print_measured(
    output_dir: Path,
    customer_rows: int,
    order_rows: int,
    product_rows: int,
    null_email: int,
    customer_dup_rows: int,
    null_customer: int,
    null_product: int,
    unknown_customer: int,
    unknown_product: int,
    order_dup_rows: int,
    distinct_defects: int,
) -> None:
    print(f"output: {output_dir}")
    print(f"customers.csv rows: {customer_rows}")
    print(f"  null email: {null_email}")
    print(f"  uniqueness rows: {customer_dup_rows}")
    print(f"orders.csv rows: {order_rows}")
    print(f"  null customer_id: {null_customer}")
    print(f"  null product_id: {null_product}")
    print(f"  unknown customer_id: {unknown_customer}")
    print(f"  unknown product_id: {unknown_product}")
    print(f"  uniqueness rows: {order_dup_rows}")
    print(f"products.csv rows: {product_rows}")
    print("  intentional defects: 0")
    print(f"distinct defective rows: {distinct_defects}")


def build_datasets(seed: int) -> tuple[list[dict], list[dict], list[dict]]:
    validate_contract()
    rng = random.Random(seed)
    products = generate_products(rng)
    customers = generate_customers(rng)
    customer_ids = sorted({row["customer_id"] for row in customers})
    product_ids = [row["product_id"] for row in products]
    orders = generate_orders(rng, customer_ids, product_ids)
    return customers, orders, products


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Write synthetic customers, orders, and products CSVs."
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed (default: 42)")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the three CSVs (default: data/)",
    )
    args = parser.parse_args(argv)
    output_dir = args.output_dir
    if output_dir.exists() and not output_dir.is_dir():
        raise SystemExit(f"output path is not a directory: {output_dir}")

    customers, orders, products = build_datasets(args.seed)
    write_csv(output_dir / "customers.csv", CUSTOMER_COLUMNS, customers)
    write_csv(output_dir / "orders.csv", ORDER_COLUMNS, orders)
    write_csv(output_dir / "products.csv", PRODUCT_COLUMNS, products)

    print(f"seed: {args.seed}")
    errors = verify_output(output_dir)
    if errors:
        print("verification failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        raise SystemExit(1)
    print("verification passed")


if __name__ == "__main__":
    main()
