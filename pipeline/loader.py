"""Input loading stage of the Quote Extraction Pipeline.

Reads raw quote records from a JSON file on disk and performs only the
minimal structural checks needed to hand clean, well-shaped records to the
next pipeline stage (LLM extraction). No extraction, validation,
normalization, review, or output logic belongs here.
"""

import json
from pathlib import Path


class InputFileError(Exception):
    """Raised when the input file is missing, unreadable, or not valid JSON."""


class InvalidQuoteFormatError(Exception):
    """Raised when parsed JSON does not match the expected quote record structure."""


def load_quotes(file_path: str) -> list[dict]:
    """Load and structurally validate quote records from a JSON file.

    Args:
        file_path: Path to a JSON file containing a list of quote records,
            each with an "id" and "text" string field.

    Returns:
        A list of dicts, each with "id" and "text" keys, whitespace-stripped.
        Records where both fields are empty after stripping are dropped.

    Raises:
        InputFileError: If the file does not exist, cannot be read, or does
            not contain valid JSON.
        InvalidQuoteFormatError: If the JSON root is not a list, or any
            record is not an object, is missing "id"/"text", or has
            non-string values for those fields.
    """
    raw_text = _read_file(file_path)
    data = _parse_json(raw_text, file_path)
    _ensure_root_is_list(data, file_path)

    quotes: list[dict] = []
    for index, record in enumerate(data):
        cleaned = _validate_and_clean_record(record, index)
        if cleaned is not None:
            quotes.append(cleaned)

    return quotes


def _read_file(file_path: str) -> str:
    """Read the raw contents of the input file.

    Raises:
        InputFileError: If the file does not exist or cannot be read.
    """
    path = Path(file_path)
    if not path.is_file():
        raise InputFileError(f"Input file not found: {file_path}")

    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputFileError(f"Unable to read input file '{file_path}': {exc}") from exc


def _parse_json(raw_text: str, file_path: str) -> object:
    """Parse raw text as JSON.

    Raises:
        InputFileError: If the text is not valid JSON.
    """
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise InputFileError(f"Input file '{file_path}' is not valid JSON: {exc}") from exc


def _ensure_root_is_list(data: object, file_path: str) -> None:
    """Ensure the parsed JSON root element is a list.

    Raises:
        InvalidQuoteFormatError: If the root element is not a list.
    """
    if not isinstance(data, list):
        raise InvalidQuoteFormatError(
            f"Input file '{file_path}' must contain a JSON list at the root, "
            f"got {type(data).__name__}."
        )


def _validate_and_clean_record(record: object, index: int) -> dict | None:
    """Validate a single quote record and return a cleaned dict, or None if empty.

    Args:
        record: The raw record parsed from the JSON list.
        index: The record's position in the input list, used for error messages.

    Returns:
        A dict with stripped "id" and "text" string values, or None if both
        fields are empty after stripping.

    Raises:
        InvalidQuoteFormatError: If the record is not an object, is missing
            "id"/"text", or either field is not a string.
    """
    if not isinstance(record, dict):
        raise InvalidQuoteFormatError(
            f"Quote record at index {index} must be a JSON object, "
            f"got {type(record).__name__}."
        )

    missing_fields = [key for key in ("id", "text") if key not in record]
    if missing_fields:
        raise InvalidQuoteFormatError(
            f"Quote record at index {index} is missing required field(s): "
            f"{', '.join(missing_fields)}."
        )

    quote_id, text = record["id"], record["text"]
    if not isinstance(quote_id, str) or not isinstance(text, str):
        raise InvalidQuoteFormatError(
            f"Quote record at index {index} must have string 'id' and 'text' fields."
        )

    quote_id = quote_id.strip()
    text = text.strip()

    if not quote_id and not text:
        return None

    return {"id": quote_id, "text": text}
