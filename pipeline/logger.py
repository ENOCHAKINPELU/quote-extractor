"""LLM call logging for the Quote Extraction Pipeline.

Appends one JSON object per line to a JSONL log file, recording that an
LLM call took place. Existing log entries are never overwritten - new
records are always appended. This module contains no business logic - it
only records and persists that a call happened.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_LOG_PATH = "llm_calls.jsonl"


class LogWriteError(Exception):
    """Raised when an LLM call record cannot be appended to the log file."""


def _current_timestamp() -> str:
    """Return the current UTC time as an ISO-8601 string (e.g. '2026-07-08T10:45:21Z').

    Returns:
        The current UTC timestamp, formatted with a trailing 'Z'.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_jsonl(path: Path, record: dict[str, Any]) -> Path:
    """Append a single record as one JSON line to `path`, creating it if needed.

    Args:
        path: The JSONL file to append to.
        record: The record to serialize and append.

    Returns:
        The path that was appended to.

    Raises:
        LogWriteError: If the record cannot be serialized, or the file
            cannot be created or written to.
    """
    try:
        line = json.dumps(record, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise LogWriteError(f"LLM call record could not be serialized to JSON: {exc}") from exc

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as log_file:
            log_file.write(line + "\n")
    except OSError as exc:
        raise LogWriteError(f"Unable to append to log file '{path}': {exc}") from exc

    return path


def log_llm_call(
    quote_id: str,
    provider: str,
    model: str,
    input_artifact: str,
    output_artifact: str,
    status: str,
    log_path: str = DEFAULT_LOG_PATH,
) -> Path:
    """Append a record of one LLM call to the JSONL call log.

    Args:
        quote_id: Identifier of the quote the call was made for (e.g. "Q-1001").
        provider: Name of the LLM provider used (e.g. "Groq").
        model: Name of the model used for the call.
        input_artifact: Path to the input artifact the call was based on.
        output_artifact: Path to the artifact the call's output was written to.
        status: Outcome of the call (e.g. "success", "error").
        log_path: Path to the JSONL log file. Created if missing.

    Returns:
        The path the record was appended to.

    Raises:
        LogWriteError: If the record cannot be serialized or appended.
    """
    record = {
        "quote_id": quote_id,
        "timestamp": _current_timestamp(),
        "provider": provider,
        "model": model,
        "input_artifact": input_artifact,
        "output_artifact": output_artifact,
        "status": status,
    }
    return _append_jsonl(Path(log_path), record)
