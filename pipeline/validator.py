"""Schema validation stage of the Quote Extraction Pipeline.

Validates the raw dictionary returned by the LLM against the expected
quote schema and basic business rules, before normalization or review.

LLM output must never be trusted blindly: every field is checked here.
This module is intentionally deterministic. It does not call an LLM,
normalize values, or make review decisions - it only validates, and it
never modifies the data it is given.
"""

import re
from datetime import datetime

REQUIRED_TOP_LEVEL_KEYS = (
    "supplier_name",
    "currency",
    "items",
    "quote_expiry",
    "shipping_included",
    "notes",
    "assumptions",
    "needs_review",
)

CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

REQUIRED_ITEM_FIELDS = ("description", "quantity", "unit_price")


def validate_top_level_keys(data: dict) -> list[str]:
    """Check that every required top-level key is present in the data.

    Args:
        data: The dictionary to check.

    Returns:
        A list of "Missing required field: ..." messages, one per absent key.
    """
    return [f"Missing required field: {key}" for key in REQUIRED_TOP_LEVEL_KEYS if key not in data]


def validate_optional_string(value: object, field_name: str) -> list[str]:
    """Validate a field that must be a string or null.

    Args:
        value: The value to check.
        field_name: The field's name, used in error messages.

    Returns:
        A list containing one error message if invalid, otherwise an empty list.
    """
    if value is None:
        return []
    if not isinstance(value, str):
        return [f"{field_name} must be a string or null"]
    return []


def validate_currency(value: object) -> list[str]:
    """Validate the currency field: null or a 3-letter uppercase ISO code.

    Args:
        value: The value to check.

    Returns:
        A list containing one error message if invalid, otherwise an empty list.
    """
    if value is None:
        return []
    if not isinstance(value, str) or not CURRENCY_PATTERN.fullmatch(value):
        return ["currency must be null or a 3-letter uppercase ISO code (e.g. USD)"]
    return []


def validate_quote_expiry(value: object) -> list[str]:
    """Validate the quote_expiry field: null or an ISO-8601 date (YYYY-MM-DD).

    This checks that the string is shaped like, and represents, a real
    calendar date. It does not convert or reformat the value in any way;
    date conversion belongs to the normalization stage.

    Args:
        value: The value to check.

    Returns:
        A list containing one error message if invalid, otherwise an empty list.
    """
    if value is None:
        return []

    if not isinstance(value, str) or not ISO_DATE_PATTERN.fullmatch(value):
        return ["quote_expiry must be null or a date string in YYYY-MM-DD format"]

    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return ["quote_expiry must be a valid calendar date in YYYY-MM-DD format"]

    return []


def validate_boolean(value: object, field_name: str) -> list[str]:
    """Validate that a field is strictly a boolean.

    Args:
        value: The value to check.
        field_name: The field's name, used in error messages.

    Returns:
        A list containing one error message if invalid, otherwise an empty list.
    """
    if not isinstance(value, bool):
        return [f"{field_name} must be a boolean"]
    return []


def validate_string_list(value: object, field_name: str) -> list[str]:
    """Validate that a field is a list containing only strings.

    Args:
        value: The value to check.
        field_name: The field's name, used in error messages.

    Returns:
        A list containing one error message if invalid, otherwise an empty list.
    """
    if not isinstance(value, list):
        return [f"{field_name} must be a list of strings"]
    if any(not isinstance(entry, str) for entry in value):
        return [f"{field_name} must contain only strings"]
    return []


def validate_item(item: object, index: int) -> list[str]:
    """Validate a single line item within the items list.

    Args:
        item: The item to check.
        index: The item's position in the items list, used in error messages.

    Returns:
        A list of human-readable error messages for this item.
    """
    errors: list[str] = []

    if not isinstance(item, dict):
        return [f"items[{index}] must be an object"]

    if "sku" in item:
        errors.extend(validate_optional_string(item["sku"], f"items[{index}].sku"))

    for field in REQUIRED_ITEM_FIELDS:
        if field not in item:
            errors.append(f"items[{index}].{field} is required")

    if "description" in item and not isinstance(item["description"], str):
        errors.append(f"items[{index}].description must be a string")

    if "quantity" in item:
        quantity = item["quantity"]
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            errors.append(f"items[{index}].quantity must be an integer")
        elif quantity <= 0:
            errors.append(f"items[{index}].quantity must be greater than zero")

    if "unit_price" in item:
        unit_price = item["unit_price"]
        if isinstance(unit_price, bool) or not isinstance(unit_price, (int, float)):
            errors.append(f"items[{index}].unit_price must be numeric")
        elif unit_price < 0:
            errors.append(f"items[{index}].unit_price must be greater than or equal to zero")

    if "lead_time_days" in item:
        lead_time_days = item["lead_time_days"]
        if lead_time_days is not None and (
            isinstance(lead_time_days, bool) or not isinstance(lead_time_days, int)
        ):
            errors.append(f"items[{index}].lead_time_days must be an integer or null")

    return errors


def validate_items(value: object) -> list[str]:
    """Validate the items field: a non-empty list of valid line items.

    Args:
        value: The value to check.

    Returns:
        A list of human-readable error messages, empty if items is valid.
    """
    if not isinstance(value, list) or len(value) == 0:
        return ["items must be a non-empty list"]

    errors: list[str] = []
    for index, item in enumerate(value):
        errors.extend(validate_item(item, index))
    return errors


def validate_quote(data: dict) -> tuple[dict, list[str]]:
    """Validate a raw, LLM-extracted quote dictionary against the expected schema.

    The input is never modified. Every applicable rule is checked, even
    after earlier rules fail, so callers receive a complete list of issues
    rather than just the first one encountered.

    Args:
        data: The dictionary returned by the LLM extraction stage.

    Returns:
        A tuple of (validated_data, validation_errors):
            - validated_data: the original, unmodified input.
            - validation_errors: a list of human-readable error messages.
              Empty if the data fully conforms to the schema.
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        errors.append("Extracted data must be a JSON object")
        return data, errors

    errors.extend(validate_top_level_keys(data))

    if "supplier_name" in data:
        errors.extend(validate_optional_string(data["supplier_name"], "supplier_name"))

    if "currency" in data:
        errors.extend(validate_currency(data["currency"]))

    if "items" in data:
        errors.extend(validate_items(data["items"]))

    if "quote_expiry" in data:
        errors.extend(validate_quote_expiry(data["quote_expiry"]))

    if "shipping_included" in data:
        errors.extend(validate_boolean(data["shipping_included"], "shipping_included"))

    if "notes" in data:
        errors.extend(validate_string_list(data["notes"], "notes"))

    if "assumptions" in data:
        errors.extend(validate_string_list(data["assumptions"], "assumptions"))

    if "needs_review" in data:
        errors.extend(validate_boolean(data["needs_review"], "needs_review"))

    return data, errors
