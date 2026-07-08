"""Provider-independent LLM interface for the Quote Extraction Pipeline.

The rest of the application depends only on this abstract interface, never
on a specific provider's SDK. Swapping providers (Groq, a mock, or any
future provider) means writing a new `LLMAdapter` implementation, without
touching pipeline code.
"""

from abc import ABC, abstractmethod


class LLMAdapterError(RuntimeError):
    """Base class for all LLM adapter failures (request, timeout, empty response, ...)."""


class LLMResponseParseError(LLMAdapterError):
    """Raised when a provider responded, but the response body wasn't usable JSON.

    Kept distinct from the base LLMAdapterError so callers can log a
    "parse_error" outcome separately from a transport/API-level failure,
    without needing to know which provider is in use.
    """


class LLMAdapter(ABC):
    """Abstract base class for all LLM providers used by the pipeline."""

    @abstractmethod
    def extract(self, text: str) -> dict:
        """Extract structured quote data from raw text.

        Implementations must return a plain dictionary shaped like the
        `Quote` schema (see `models/schemas.py`), without performing any
        validation or normalization themselves.

        Args:
            text: The raw supplier quote text to extract data from.

        Returns:
            A dictionary of extracted, unvalidated quote data.
        """
        raise NotImplementedError
