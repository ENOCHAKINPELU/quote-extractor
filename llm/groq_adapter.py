"""Groq-backed implementation of the LLMAdapter interface.

Sends exactly one chat completion request to a Groq-hosted model and
returns the raw, parsed JSON payload. This module owns every Groq-specific
concern (client setup, prompting, error translation) so the rest of the
pipeline can depend solely on `llm.adapter.LLMAdapter`.
"""

import json

from groq import Groq, GroqError

import config
from llm.adapter import LLMAdapter

SYSTEM_PROMPT = """You are a precise data-extraction engine for supplier price quotes.

Extract structured data from the quote text provided by the user, following these rules strictly:

- Extract only facts that are explicitly present in the text. Never invent or guess information.
- Never invent supplier names, SKUs, currencies, or shipping terms that are not explicitly stated.
- If a value is not present or cannot be determined with confidence, set it to null.
- Never resolve a relative date (e.g. "in 30 days", "next month") into an absolute date. If a date
  cannot be determined as an explicit calendar date, leave it null and note the uncertainty in
  "assumptions" instead of guessing.
- Record any interpretation, uncertainty, or inference you had to make in the "assumptions" list.
- Set "needs_review" to true whenever an important field (such as supplier name, items, or unit
  prices) is missing or ambiguous.
- Respond with ONLY a single JSON object. Do not include prose, markdown, or code fences.

Return JSON matching exactly this shape:
{
  "supplier_name": "string | null",
  "currency": "string | null",
  "items": [
    {
      "sku": "string | null",
      "description": "string",
      "quantity": 0,
      "unit_price": 0,
      "lead_time_days": 0 | null
    }
  ],
  "quote_expiry": "YYYY-MM-DD | null",
  "shipping_included": true,
  "notes": ["string"],
  "assumptions": ["string"],
  "needs_review": false
}
"""


class GroqAdapterError(RuntimeError):
    """Raised when the Groq adapter fails to produce a usable extraction."""


class GroqAdapter(LLMAdapter):
    """LLMAdapter implementation backed by the Groq chat completions API."""

    def __init__(self) -> None:
        self._client = Groq(api_key=config.GROQ_API_KEY)
        self._model = config.MODEL

    def extract(self, text: str) -> dict:
        """Send one Groq chat completion request and return the parsed JSON payload.

        Performs no validation or normalization: the returned dictionary is
        exactly what the model produced, parsed from JSON.

        Args:
            text: The raw supplier quote text to extract data from.

        Returns:
            The raw, unvalidated dictionary parsed from the model's JSON response.

        Raises:
            GroqAdapterError: If the request fails, the response is empty, or
                the response body is not a valid JSON object.
        """
        content = self._request_completion(text)
        return self._parse_json(content)

    def _request_completion(self, text: str) -> str:
        """Send the extraction request to Groq and return the raw text content."""
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
            )
        except GroqError as exc:
            raise GroqAdapterError(f"Groq API request failed: {exc}") from exc

        if not response.choices:
            raise GroqAdapterError("Groq API returned no choices in the response.")

        content = response.choices[0].message.content
        if not content or not content.strip():
            raise GroqAdapterError("Groq API returned an empty response.")

        return content

    @staticmethod
    def _parse_json(content: str) -> dict:
        """Parse raw model output as a JSON object, raising on malformed content."""
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise GroqAdapterError(f"Groq API returned malformed JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise GroqAdapterError(
                "Groq API returned valid JSON but not a JSON object "
                f"(got {type(parsed).__name__})."
            )

        return parsed
