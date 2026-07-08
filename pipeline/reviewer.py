"""Review-decision stage of the Quote Extraction Pipeline.

Applies deterministic business rules to a normalized quote (and the
validation errors produced earlier in the pipeline) to decide whether the
quote requires manual review. This module never calls an LLM, never
validates, and never normalizes data - it only inspects data and reports a
decision.

The input quote is never mutated: `determine_review` returns a new,
independent decision dictionary. Applying that decision to the quote
itself (e.g. setting quote["needs_review"]) is left to the caller.
"""

import re

REQUIRED_TOP_LEVEL_FIELDS = (
    "supplier_name",
    "currency",
    "items",
    "quote_expiry",
    "shipping_included",
    "notes",
    "assumptions",
)

CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URGENCY_KEYWORDS = ("urgent", "rush", "expedite", "priority")


def _dedupe(reasons: list[str]) -> list[str]:
    """Remove duplicate reasons while preserving first-seen order."""
    seen: set[str] = set()
    unique: list[str] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            unique.append(reason)
    return unique


def check_completeness(quote: dict) -> list[str]:
    """Flag a quote whose top-level structure is missing keys or malformed.

    This is a defensive check independent of validation_errors, covering
    cases where the LLM output was incomplete: missing keys, a missing or
    wrongly-typed items array, or similarly malformed structure.

    Args:
        quote: The normalized quote dictionary.

    Returns:
        A list containing "Quote data is incomplete" if incomplete, otherwise empty.
    """
    missing_fields = [field for field in REQUIRED_TOP_LEVEL_FIELDS if field not in quote]
    if missing_fields or not isinstance(quote.get("items"), list):
        return ["Quote data is incomplete"]
    return []


def check_supplier(quote: dict) -> list[str]:
    """Flag a quote with a missing supplier name.

    Args:
        quote: The normalized quote dictionary.

    Returns:
        A list containing "Supplier name missing" if applicable, otherwise empty.
    """
    supplier_name = quote.get("supplier_name")
    if not isinstance(supplier_name, str) or not supplier_name.strip():
        return ["Supplier name missing"]
    return []


def check_currency(quote: dict) -> list[str]:
    """Flag a quote with a missing or ambiguous currency.

    A currency is considered ambiguous if it is not exactly a 3-letter
    uppercase code (e.g. "$", "Dollar", "Currency Unknown", "Unknown").

    Args:
        quote: The normalized quote dictionary.

    Returns:
        A list with one reason if applicable, otherwise empty.
    """
    currency = quote.get("currency")
    if not isinstance(currency, str) or not currency.strip():
        return ["Currency missing"]
    if not CURRENCY_PATTERN.fullmatch(currency.strip()):
        return ["Currency is ambiguous"]
    return []


def check_items(quote: dict) -> list[str]:
    """Flag issues with the items list and its individual line items.

    Covers: an empty items list, items missing description/quantity/unit
    price, a quantity of zero, a negative unit price, and a lead time that
    could not be interpreted (normalized to None).

    Args:
        quote: The normalized quote dictionary.

    Returns:
        A list of human-readable, deduplicated reasons.
    """
    items = quote.get("items")
    if not isinstance(items, list) or not items:
        return ["Items list is empty"]

    reasons: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            reasons.append("Item is missing required fields")
            continue

        description = item.get("description")
        if not isinstance(description, str) or not description.strip():
            reasons.append("Item description missing")

        quantity = item.get("quantity")
        if quantity is None:
            reasons.append("Item quantity missing")
        elif isinstance(quantity, (int, float)) and not isinstance(quantity, bool) and quantity == 0:
            reasons.append("Item quantity is zero")

        unit_price = item.get("unit_price")
        if unit_price is None:
            reasons.append("Item unit price missing")
        elif isinstance(unit_price, (int, float)) and not isinstance(unit_price, bool) and unit_price < 0:
            reasons.append("Item unit price is negative")

        if "lead_time_days" in item and item["lead_time_days"] is None:
            reasons.append("Lead time could not be interpreted")

    return _dedupe(reasons)


def check_expiry(quote: dict) -> list[str]:
    """Flag a quote expiry expressed as an unresolved relative date.

    Examples: "next Friday", "tomorrow", "end of month", "next week". The
    value itself is never modified or resolved here; it is only flagged.

    Args:
        quote: The normalized quote dictionary.

    Returns:
        A list containing one reason if applicable, otherwise empty.
    """
    quote_expiry = quote.get("quote_expiry")
    if not isinstance(quote_expiry, str):
        return []

    trimmed = quote_expiry.strip()
    if not trimmed or ISO_DATE_PATTERN.fullmatch(trimmed):
        return []

    return ["Relative expiry date cannot be resolved safely"]


def check_notes(quote: dict) -> list[str]:
    """Flag notes that mention urgency-related keywords.

    This is not an error condition, but may warrant human attention.

    Args:
        quote: The normalized quote dictionary.

    Returns:
        A list containing one reason if applicable, otherwise empty.
    """
    notes = quote.get("notes")
    if not isinstance(notes, list):
        return []

    combined_text = " ".join(note for note in notes if isinstance(note, str)).lower()
    if any(keyword in combined_text for keyword in URGENCY_KEYWORDS):
        return ["Notes indicate urgency and may warrant attention"]
    return []


def determine_review(quote: dict, validation_errors: list[str]) -> dict:
    """Decide whether a quote requires manual review.

    Applies every deterministic business rule, collects a deduplicated
    list of human-readable reasons, and never modifies the input quote.

    Args:
        quote: The normalized quote dictionary.
        validation_errors: The validation errors produced by validator.py
            for this quote.

    Returns:
        A dictionary: {"needs_review": bool, "review_reasons": list[str]}.
    """
    if not isinstance(quote, dict):
        return {"needs_review": True, "review_reasons": ["Quote data is incomplete"]}

    reasons: list[str] = []
    reasons.extend(check_completeness(quote))
    reasons.extend(check_supplier(quote))
    reasons.extend(check_currency(quote))
    reasons.extend(check_items(quote))
    reasons.extend(check_expiry(quote))
    reasons.extend(check_notes(quote))

    if validation_errors:
        reasons.append("Validation failed")

    review_reasons = _dedupe(reasons)

    return {
        "needs_review": bool(review_reasons),
        "review_reasons": review_reasons,
    }
