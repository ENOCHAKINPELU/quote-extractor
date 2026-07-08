"""Unit tests for the schema validation stage (pipeline/validator.py).

These tests exercise only deterministic Python logic. No LLM is called,
and no network access is required.
"""

import pytest

from pipeline.validator import validate_quote


def make_valid_quote() -> dict:
    """Return a fresh, fully valid quote dictionary for use as a test fixture."""
    return {
        "supplier_name": "Alpha Industrial Supplies",
        "currency": "USD",
        "items": [
            {
                "sku": "SKU-1",
                "description": "Steel bracket",
                "quantity": 10,
                "unit_price": 4.5,
                "lead_time_days": 7,
            }
        ],
        "quote_expiry": "2026-08-15",
        "shipping_included": True,
        "notes": ["Standard order"],
        "assumptions": [],
        "needs_review": False,
    }


def test_valid_quote_passes_validation():
    """A fully valid quote should produce no validation errors."""
    data, errors = validate_quote(make_valid_quote())

    assert errors == []
    assert data["supplier_name"] == "Alpha Industrial Supplies"


def test_validated_data_is_returned_unchanged():
    """validate_quote must never modify or replace the input dictionary."""
    quote = make_valid_quote()

    data, errors = validate_quote(quote)

    assert data is quote
    assert errors == []


@pytest.mark.parametrize("bad_currency", ["Dollar", "usd$", "123"])
def test_invalid_currency_is_rejected(bad_currency):
    """Currency values that aren't a clean 3-letter uppercase code are rejected."""
    quote = make_valid_quote()
    quote["currency"] = bad_currency

    _, errors = validate_quote(quote)

    assert "currency must be null or a 3-letter uppercase ISO code (e.g. USD)" in errors


@pytest.mark.parametrize("quantity", [0, -1, -5])
def test_quantity_less_than_or_equal_to_zero_is_rejected(quantity):
    """Item quantity must be strictly greater than zero."""
    quote = make_valid_quote()
    quote["items"][0]["quantity"] = quantity

    _, errors = validate_quote(quote)

    assert "items[0].quantity must be greater than zero" in errors


def test_negative_unit_price_is_rejected():
    """Item unit price cannot be negative."""
    quote = make_valid_quote()
    quote["items"][0]["unit_price"] = -2.5

    _, errors = validate_quote(quote)

    assert "items[0].unit_price must be greater than or equal to zero" in errors


def test_missing_required_keys_are_reported():
    """Every missing top-level key should produce its own error message."""
    quote = make_valid_quote()
    del quote["supplier_name"]
    del quote["needs_review"]

    _, errors = validate_quote(quote)

    assert "Missing required field: supplier_name" in errors
    assert "Missing required field: needs_review" in errors


def test_empty_items_list_is_rejected():
    """The items list must not be empty."""
    quote = make_valid_quote()
    quote["items"] = []

    _, errors = validate_quote(quote)

    assert "items must be a non-empty list" in errors


def test_invalid_quote_expiry_format_is_rejected():
    """A non-ISO-8601 quote_expiry format (e.g. MM/DD/YYYY) is rejected."""
    quote = make_valid_quote()
    quote["quote_expiry"] = "08/12/2026"

    _, errors = validate_quote(quote)

    assert "quote_expiry must be null or a date string in YYYY-MM-DD format" in errors


def test_invalid_calendar_date_is_rejected():
    """A value shaped like YYYY-MM-DD but not a real calendar date is rejected."""
    quote = make_valid_quote()
    quote["quote_expiry"] = "2024-13-45"

    _, errors = validate_quote(quote)

    assert "quote_expiry must be a valid calendar date in YYYY-MM-DD format" in errors


def test_shipping_included_must_be_boolean():
    """shipping_included must be a strict boolean, not a truthy string."""
    quote = make_valid_quote()
    quote["shipping_included"] = "yes"

    _, errors = validate_quote(quote)

    assert "shipping_included must be a boolean" in errors


def test_non_dict_input_returns_error_without_crashing():
    """Non-dict input must never raise; it should be reported as an error instead."""
    data, errors = validate_quote("not a dict")

    assert data == "not a dict"
    assert errors == ["Extracted data must be a JSON object"]


def test_validation_never_stops_at_the_first_error():
    """Multiple simultaneous problems should all be collected in one pass."""
    quote = make_valid_quote()
    quote["currency"] = "Dollar"
    quote["shipping_included"] = "yes"
    quote["items"][0]["quantity"] = 0

    _, errors = validate_quote(quote)

    assert "currency must be null or a 3-letter uppercase ISO code (e.g. USD)" in errors
    assert "shipping_included must be a boolean" in errors
    assert "items[0].quantity must be greater than zero" in errors
