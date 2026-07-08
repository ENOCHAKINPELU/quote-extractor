"""Unit tests for the normalization stage (pipeline/normalizer.py).

These tests exercise only deterministic Python logic. No LLM is called,
and no network access is required.
"""

import pytest

from pipeline.normalizer import (
    normalize_currency,
    normalize_lead_time,
    normalize_quote,
    normalize_string_list,
    normalize_whitespace,
)


def test_currency_lowercase_is_uppercased():
    """A lowercase 3-letter currency code is uppercased."""
    assert normalize_currency("usd") == "USD"


def test_currency_already_uppercase_is_unchanged():
    assert normalize_currency("EUR") == "EUR"


@pytest.mark.parametrize("value", ["US Dollars", "usd$", "US"])
def test_currency_that_cannot_become_a_code_is_left_unchanged(value):
    """Values that don't reasonably fit a 3-letter code are never invented or guessed."""
    assert normalize_currency(value) == value


@pytest.mark.parametrize(
    "symbol, expected_code",
    [
        ("€", "EUR"),
        ("£", "GBP"),
        ("¥", "JPY"),
    ],
)
def test_unambiguous_currency_symbols_are_mapped_to_codes(symbol, expected_code):
    """Symbols used by exactly one common currency are mapped deterministically."""
    assert normalize_currency(symbol) == expected_code


def test_ambiguous_dollar_symbol_is_left_unchanged():
    """'$' is shared by many currencies, so it is never guessed - left for review instead."""
    assert normalize_currency("$") == "$"


def test_whitespace_is_trimmed():
    """Leading and trailing whitespace is removed."""
    assert normalize_whitespace(" Alpha Industrial Supplies ") == "Alpha Industrial Supplies"


def test_multiple_internal_spaces_are_collapsed():
    """Repeated internal spaces collapse to a single space."""
    assert normalize_whitespace("Alpha     Industrial") == "Alpha Industrial"


@pytest.mark.parametrize(
    "raw_value, expected_days",
    [
        ("1 week", 7),
        ("2 weeks", 14),
        ("3 weeks", 21),
        ("5 days", 5),
        ("14 days", 14),
        (14, 14),
    ],
)
def test_lead_time_conversion(raw_value, expected_days):
    """Recognized textual durations convert to days; integers pass through unchanged."""
    assert normalize_lead_time(raw_value) == expected_days


def test_unknown_lead_time_value_becomes_none():
    """A textual lead time that doesn't match a known pattern is never guessed at."""
    assert normalize_lead_time("soon") is None


def test_notes_normalization_trims_and_removes_empty_strings():
    """Every string is trimmed, empty entries are dropped, and order is preserved."""
    result = normalize_string_list(["  keep this  ", "   ", "also keep"])

    assert result == ["keep this", "also keep"]


def test_normalize_quote_does_not_mutate_original_input():
    """normalize_quote must return a new dictionary and leave the original untouched."""
    original = {
        "supplier_name": "  Alpha     Industrial  Supplies  ",
        "currency": "usd",
        "items": [],
        "notes": ["  note  ", ""],
    }
    snapshot = dict(original)

    result = normalize_quote(original)

    assert original == snapshot
    assert result["supplier_name"] == "Alpha Industrial Supplies"
    assert result["currency"] == "USD"
    assert result["notes"] == ["note"]
