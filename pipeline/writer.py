"""Output-writing stage of the Quote Extraction Pipeline.

Persists pipeline artifacts (raw LLM responses, normalized quotes, and the
review summary) to disk as pretty-printed, UTF-8 encoded JSON. This module
contains no business logic - it only serializes and writes the data it is
given.
"""

import json
from pathlib import Path
from typing import Any

JSON_INDENT = 2


class OutputWriteError(Exception):
    """Raised when an output artifact cannot be written to disk."""


class SerializationError(Exception):
    """Raised when data cannot be serialized to JSON."""


def _sanitize_quote_id(quote_id: str) -> str:
    """Validate that a quote_id is safe to use as a filename component.

    Args:
        quote_id: The quote identifier to validate.

    Returns:
        The validated quote_id, unchanged.

    Raises:
        OutputWriteError: If quote_id is empty or contains path separators
            or other characters that could escape the output directory.
    """
    if not quote_id or quote_id in {".", ".."} or any(sep in quote_id for sep in ("/", "\\")):
        raise OutputWriteError(f"Invalid quote_id for use as a filename: {quote_id!r}")
    return quote_id


def _serialize(data: Any) -> str:
    """Serialize data to a pretty-printed JSON string.

    Args:
        data: The data to serialize.

    Returns:
        A pretty-printed JSON string.

    Raises:
        SerializationError: If the data cannot be serialized to JSON.
    """
    try:
        return json.dumps(data, indent=JSON_INDENT, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise SerializationError(f"Data could not be serialized to JSON: {exc}") from exc


def _write_json_file(path: Path, data: Any) -> Path:
    """Serialize data and write it to `path`, creating parent directories as needed.

    Args:
        path: The file path to write to.
        data: The data to serialize and write.

    Returns:
        The path that was written to.

    Raises:
        SerializationError: If the data cannot be serialized to JSON.
        OutputWriteError: If the parent directory or file cannot be written.
    """
    content = _serialize(data)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise OutputWriteError(f"Unable to write output file '{path}': {exc}") from exc

    return path


def save_raw_output(quote_id: str, raw_response: dict, output_dir: str = "outputs") -> Path:
    """Persist the raw, unmodified LLM response for a quote.

    Writes to `{output_dir}/{quote_id}_raw.json`.

    Args:
        quote_id: Identifier of the quote (e.g. "Q-1001").
        raw_response: The dictionary returned by the LLM adapter.
        output_dir: Directory to write the file into. Created if missing.

    Returns:
        The path the raw response was written to.

    Raises:
        SerializationError: If raw_response cannot be serialized to JSON.
        OutputWriteError: If the file cannot be written, or quote_id is invalid.
    """
    quote_id = _sanitize_quote_id(quote_id)
    path = Path(output_dir) / f"{quote_id}_raw.json"
    return _write_json_file(path, raw_response)


def save_final_output(quote_id: str, normalized_quote: dict, output_dir: str = "outputs") -> Path:
    """Persist the final, normalized quote.

    Writes to `{output_dir}/{quote_id}.json`.

    Args:
        quote_id: Identifier of the quote (e.g. "Q-1001").
        normalized_quote: The normalized quote dictionary.
        output_dir: Directory to write the file into. Created if missing.

    Returns:
        The path the normalized quote was written to.

    Raises:
        SerializationError: If normalized_quote cannot be serialized to JSON.
        OutputWriteError: If the file cannot be written, or quote_id is invalid.
    """
    quote_id = _sanitize_quote_id(quote_id)
    path = Path(output_dir) / f"{quote_id}.json"
    return _write_json_file(path, normalized_quote)


def write_review_summary(summary: list[dict], filename: str = "review_summary.json") -> Path:
    """Persist the review summary for all processed quotes.

    Args:
        summary: A list of per-quote review summary dicts.
        filename: Path (relative or absolute) to write the summary to.

    Returns:
        The path the summary was written to.

    Raises:
        SerializationError: If summary cannot be serialized to JSON.
        OutputWriteError: If the file cannot be written.
    """
    return _write_json_file(Path(filename), summary)
