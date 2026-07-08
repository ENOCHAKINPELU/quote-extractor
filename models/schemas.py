"""Pydantic v2 data models for the Quote Extraction Pipeline.

These models define the normalized contract for a supplier quote: the
shape of data produced by LLM extraction and, after validation and
normalization, consumed by review logic and output writing. They are the
single source of truth for what a "quote" looks like across the pipeline.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _blank_to_none(value: object) -> object:
    """Convert a whitespace-only string to None; pass everything else through."""
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


class Item(BaseModel):
    """A single line item within a supplier quote."""

    model_config = ConfigDict(str_strip_whitespace=True)

    sku: Optional[str] = Field(
        default=None,
        description="Supplier or manufacturer SKU/part number, if provided.",
    )
    description: str = Field(
        description="Human-readable description of the item being quoted.",
    )
    quantity: int = Field(
        ge=0,
        description="Quantity of the item quoted. Cannot be negative.",
    )
    unit_price: float = Field(
        ge=0,
        description="Price per unit, in the quote's currency. Cannot be negative.",
    )
    lead_time_days: Optional[int] = Field(
        default=None,
        ge=0,
        description="Estimated lead time in days, if provided.",
    )

    @field_validator("sku", mode="before")
    @classmethod
    def normalize_sku(cls, value: object) -> object:
        """Treat a blank SKU as absent rather than an empty string."""
        return _blank_to_none(value)

    def to_dict(self) -> dict:
        """Return a plain, JSON-serializable dict representation of this item."""
        return self.model_dump()


class Quote(BaseModel):
    """A normalized supplier quote, ready for review and output."""

    model_config = ConfigDict(str_strip_whitespace=True)

    supplier_name: Optional[str] = Field(
        default=None,
        description="Name of the supplier issuing the quote.",
    )
    currency: Optional[str] = Field(
        default=None,
        description="Currency code the quote is denominated in (e.g. USD, EUR).",
    )
    items: list[Item] = Field(
        description="Line items included in the quote.",
    )
    quote_expiry: Optional[str] = Field(
        default=None,
        description="Quote expiry date in YYYY-MM-DD format, if provided.",
    )
    shipping_included: bool = Field(
        description="Whether shipping costs are included in the quoted price.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Free-form notes extracted from the quote.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions made while extracting or normalizing the quote.",
    )
    needs_review: bool = Field(
        description="Flag indicating the quote requires human review.",
    )

    @field_validator("supplier_name", "quote_expiry", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: object) -> object:
        """Treat blank optional strings as absent rather than empty strings."""
        return _blank_to_none(value)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        """Treat a blank currency as absent, otherwise uppercase it (e.g. usd -> USD)."""
        value = _blank_to_none(value)
        return value.upper() if isinstance(value, str) else value

    def to_dict(self) -> dict:
        """Return a plain, JSON-serializable dict representation of this quote."""
        return self.model_dump()
