"""Configuration module for the Quote Extraction Pipeline.

Loads environment variables from a local .env file and exposes them as
typed, module-level constants for the rest of the application to import.
"""

import os

from dotenv import load_dotenv

load_dotenv()


class ConfigurationError(RuntimeError):
    """Raised when required application configuration is missing or invalid."""


def _str_to_bool(value: str) -> bool:
    """Interpret common truthy strings ('1', 'true', 'yes', 'on') as True."""
    return value.strip().lower() in {"1", "true", "yes", "on"}


GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
"""API key used to authenticate with the Groq API. Required unless USE_MOCK is true."""

MODEL: str = os.getenv("MODEL", "llama-3.3-70b-versatile")
"""Name of the Groq-hosted model to use for extraction."""

USE_MOCK: bool = _str_to_bool(os.getenv("USE_MOCK", "false"))
"""When true, the pipeline uses MockAdapter instead of calling the real Groq API."""

if not USE_MOCK and not GROQ_API_KEY:
    raise ConfigurationError(
        "GROQ_API_KEY is not set. Add it to your .env file, or set "
        "USE_MOCK=true in .env to run without calling the Groq API."
    )
