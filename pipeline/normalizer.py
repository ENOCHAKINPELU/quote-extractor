"""Normalization stage of the Quote Extraction Pipeline.

Takes a validated quote dictionary and deterministically standardizes its
values (whitespace, currency casing, lead-time durations, etc.) before the
review-decision stage. This module does not call an LLM, validate data,
make review decisions, or write output - it only transforms data, and it
never mutates the dictionary it is given.
"""

import re
from typing import Any

WEEK_PATTERN = re.compile(r"^(\d+)\s*weeks?$")
DAY_PATTERN = re.compile(r"^(\d+)\s*days?$")
CURRENCY_CODE_LENGTH = 3

# Only symbols used by a single, unambiguous currency in common practice are
# mapped here. "$" is deliberately excluded: it is shared by USD, CAD, AUD,
# SGD, HKD, and others, so mapping it without surrounding text context would
# mean inventing a currency rather than normalizing one. Bare "$" is left
# unchanged, which causes the review stage to flag it as ambiguous.
CURRENCY_SYMBOL_MAP = {
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
}


def normalize_string(value: Any) -> Any:
    """Trim leading and trailing whitespace from a string value.

    Non-string values are returned unchanged, so this never raises on
    missing or unexpected data.

    Args:
        value: The value to normalize.

    Returns:
        The trimmed string, or the original value if it is not a string.
    """
    if isinstance(value, str):
        return value.strip()
    return value


def normalize_whitespace(value: Any) -> Any:
    """Trim a string and collapse any internal runs of whitespace to a single space.

    Non-string values are returned unchanged.

    Args:
        value: The value to normalize.

    Returns:
        The whitespace-collapsed string, or the original value if it is not a string.
    """
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    return value


def normalize_currency(value: Any) -> Any:
    """Trim a currency value, map unambiguous symbols, and uppercase 3-letter codes.

    Never invents a currency: a symbol is only mapped to a code when that
    symbol is unambiguous (see CURRENCY_SYMBOL_MAP). Anything else that
    isn't exactly three alphabetic characters is returned trimmed but
    otherwise unchanged, leaving genuinely ambiguous values (e.g. a bare
    "$") for the review stage to flag.

    Args:
        value: The value to normalize.

    Returns:
        The mapped or uppercased code, the trimmed original string if it
        doesn't fit either case, or the original value if it is not a string.
    """
    if not isinstance(value, str):
        return value

    trimmed = value.strip()

    if trimmed in CURRENCY_SYMBOL_MAP:
        return CURRENCY_SYMBOL_MAP[trimmed]

    if len(trimmed) == CURRENCY_CODE_LENGTH and trimmed.isalpha():
        return trimmed.upper()

    return trimmed


def normalize_lead_time(value: Any) -> Any:
    """Convert a lead time into an integer number of days where safe to do so.

    Integers are kept as-is. Strings matching common textual durations
    ("1 week", "2 weeks", "5 days", "14 days", ...) are converted to days.
    Strings that do not match a known pattern cannot be safely converted
    and become None, rather than being guessed at. Any other unexpected
    type (e.g. a float, list, or bool) is left unchanged.

    Args:
        value: The value to normalize.

    Returns:
        An integer number of days, None if a string could not be safely
        converted, or the original value for None input or unexpected types.
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value

    if not isinstance(value, str):
        return value

    text = value.strip().lower()

    week_match = WEEK_PATTERN.fullmatch(text)
    if week_match:
        return int(week_match.group(1)) * 7

    day_match = DAY_PATTERN.fullmatch(text)
    if day_match:
        return int(day_match.group(1))

    return None


def normalize_quote_expiry(value: Any) -> Any:
    """Trim whitespace from a quote expiry value without resolving its meaning.

    Relative or ambiguous dates (e.g. "next Friday") are left as-is; only
    whitespace is trimmed. Resolving such values is a review concern, not
    a normalization one.

    Args:
        value: The value to normalize.

    Returns:
        The trimmed string, or the original value if it is not a string.
    """
    return normalize_string(value)


def normalize_string_list(values: Any) -> Any:
    """Trim every string in a list, dropping any that become empty.

    Ordering is preserved. Non-list input is returned unchanged, and any
    non-string entries within the list are preserved as-is.

    Args:
        values: The value to normalize.

    Returns:
        A new list with trimmed, non-empty strings, or the original value
        if it is not a list.
    """
    if not isinstance(values, list):
        return values

    normalized: list[Any] = []
    for entry in values:
        if isinstance(entry, str):
            trimmed = entry.strip()
            if trimmed:
                normalized.append(trimmed)
        else:
            normalized.append(entry)
    return normalized


def normalize_item(item: Any) -> Any:
    """Normalize a single line item's sku, description, and lead time.

    Returns a new dictionary; the original item is not mutated. Quantity
    and unit_price are left untouched, as no normalization rule applies
    to them.

    Args:
        item: The item to normalize.

    Returns:
        A new, normalized item dictionary, or the original value if it is
        not a dictionary.
    """
    if not isinstance(item, dict):
        return item

    normalized = dict(item)

    if "sku" in item:
        normalized["sku"] = normalize_string(item["sku"])

    if "description" in item:
        normalized["description"] = normalize_string(item["description"])

    if "lead_time_days" in item:
        normalized["lead_time_days"] = normalize_lead_time(item["lead_time_days"])

    return normalized


def normalize_items(items: Any) -> Any:
    """Normalize every item in the items list.

    Args:
        items: The value to normalize.

    Returns:
        A new list of normalized items, or the original value if it is not a list.
    """
    if not isinstance(items, list):
        return items
    return [normalize_item(item) for item in items]


def normalize_quote(data: dict) -> dict:
    """Return a new, normalized copy of a validated quote dictionary.

    The input dictionary (and any nested lists/dicts within it) is never
    mutated. Fields without a defined normalization rule (e.g.
    shipping_included, needs_review) are carried over unchanged.

    Args:
        data: The validated quote dictionary to normalize.

    Returns:
        A new dictionary with normalized values, or the original value
        unchanged if it is not a dictionary.
    """
    if not isinstance(data, dict):
        return data

    normalized = dict(data)

    if "supplier_name" in data:
        normalized["supplier_name"] = normalize_whitespace(data["supplier_name"])

    if "currency" in data:
        normalized["currency"] = normalize_currency(data["currency"])

    if "items" in data:
        normalized["items"] = normalize_items(data["items"])

    if "quote_expiry" in data:
        normalized["quote_expiry"] = normalize_quote_expiry(data["quote_expiry"])

    if "notes" in data:
        normalized["notes"] = normalize_string_list(data["notes"])

    if "assumptions" in data:
        normalized["assumptions"] = normalize_string_list(data["assumptions"])

    return normalized
