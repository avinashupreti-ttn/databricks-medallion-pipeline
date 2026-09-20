"""Value helpers shared by the Silver checks.

Bronze stores typed columns. Local tests also read CSV text. These helpers
accept both so the same rules cover each path.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def is_blank(value) -> bool:
    """True for NULL and for strings that are empty after trim."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def normalize_key(value):
    """Comparable id for an int column stored as int or CSV text.

    Missing values are None. All missing values compare equal so duplicate
    detection matches Spark grouping of null keys.
    """
    if is_blank(value) or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return value
    if isinstance(value, str):
        text = value.strip()
        sign = ""
        body = text
        if text[:1] in "+-":
            sign = text[:1]
            body = text[1:]
        if body.isdigit():
            number = int(body)
            return -number if sign == "-" else number
        return text
    return value


def is_int_value(value) -> bool:
    if isinstance(value, bool) or is_blank(value):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, Decimal):
        return value == value.to_integral_value()
    return isinstance(normalize_key(value), int)


def is_decimal_value(value) -> bool:
    if isinstance(value, bool) or is_blank(value):
        return False
    if isinstance(value, (Decimal, int)):
        return True
    if isinstance(value, str):
        try:
            Decimal(value.strip())
        except InvalidOperation:
            return False
        return True
    return False


def is_date_value(value) -> bool:
    if is_blank(value):
        return False
    if isinstance(value, date):
        return True
    if isinstance(value, str):
        text = value.strip()
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            return False
        return parsed.strftime("%Y-%m-%d") == text
    return False
