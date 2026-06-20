"""Catalog domain models for feature 005-catalog.

Pydantic models for the catalog *definition* layer — `Category`, `SubCategory`,
and `Product` — plus their validation rules. Persistence (the SQL migration) is
deferred until PostgreSQL is introduced; these models are the in-code contract
that the future migration must satisfy (specs/005-catalog/spec.md §4).

Referential-existence checks (FK -> an *existing* Category/SubCategory, FR-4/FR-6)
are enforced at the persistence layer once it exists. At this layer we enforce
presence, type, and value rules only (FR-2, FR-8, FR-9, FR-16..FR-18).
"""

from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.catalog.enums import UnitType


class Category(BaseModel):
    """A top-level catalog category (platform-owned; FR-1, FR-2, FR-11)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    category_id: UUID = Field(default_factory=uuid4)
    category_name: str = Field(min_length=1)
    parent_category_id: UUID | None = None

    @field_validator("parent_category_id")
    @classmethod
    def _parent_must_be_null(cls, v: UUID | None) -> UUID | None:
        # FR-2: a Category is always top-level.
        if v is not None:
            raise ValueError("parent_category_id must be null for a Category (FR-2)")
        return v


class SubCategory(BaseModel):
    """A subcategory belonging to exactly one Category (FR-3, FR-4, FR-12)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    subcategory_id: UUID = Field(default_factory=uuid4)
    subcategory_name: str = Field(min_length=1)
    parent_category_id: UUID  # NOT NULL; references an existing Category (FR-4)
    subcategory_description: str = Field(min_length=1)


class Product(BaseModel):
    """A vendor-authored catalog product (FR-5, FR-6, FR-8, FR-9, FR-13, FR-16..FR-18).

    Each vendor authors their own Product row, so `price_inr` is that vendor's
    authoritative sale price (FR-16, Reading B); duplicates across vendors are
    allowed (FR-15). Currency is always INR and is not a configurable field
    (FR-17) — `extra="forbid"` rejects any attempt to pass one.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    product_id: UUID = Field(default_factory=uuid4)
    subcategory_id: UUID  # NOT NULL; references an existing SubCategory (FR-6)
    product_name: str = Field(min_length=1)
    brand: str = Field(min_length=1)  # required; use "Generic" when unbranded (FR-9)
    description: str = Field(min_length=1)
    unit_type: UnitType
    unit_value: Decimal
    price_inr: Decimal

    @field_validator("unit_value")
    @classmethod
    def _unit_value_positive(cls, v: Decimal) -> Decimal:
        # FR-8: unit_value must be a positive Decimal.
        if v <= 0:
            raise ValueError("unit_value must be greater than 0 (FR-8)")
        return v

    @field_validator("price_inr", mode="before")
    @classmethod
    def _validate_price_inr(cls, v: object) -> Decimal:
        # FR-16..FR-18: mandatory INR price, > 0.00, with exactly 2 decimal places.
        # The "exactly 2 dp" rule is checked on the *raw input* before any
        # normalization — a future NUMERIC(_, 2) column would silently pad
        # "10.1" -> "10.10" and accept it (spec validation note / plan decision #9).
        if isinstance(v, float):
            # Binary floats cannot represent exact 2-dp money values; require a
            # Decimal/str/int so precision is preserved.
            raise ValueError(
                "price_inr must be a Decimal or string, not float, to preserve "
                "exact 2-decimal precision (FR-18)"
            )
        try:
            amount = Decimal(str(v))
        except InvalidOperation as exc:
            raise ValueError("price_inr must be a valid decimal number (FR-16)") from exc
        if amount <= Decimal("0.00"):
            raise ValueError("price_inr must be greater than 0.00 (FR-18)")
        if amount.as_tuple().exponent != -2:
            raise ValueError(
                "price_inr must have exactly 2 decimal places, e.g. 10.00 (FR-18)"
            )
        return amount
