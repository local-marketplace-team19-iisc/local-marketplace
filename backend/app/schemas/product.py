"""Pydantic schemas for the vendor product workflow (feature 006).

Field map between the frontend display shape and the 005 catalog schema (006 FR-10):
    name        <-> product_name
    price       <-> price_inr
    stock       <-> stock_quantity
    category    <-> (sub)category name / subcategory_id
    description <-> description

`vendor_id` is never taken from the request body — it is derived from the
authenticated vendor (006 FR-8). The REST boundary normalizes price to exactly
2 decimal places rather than rejecting under-precise input (friendlier than the
005 model-layer rule, same stored result).
"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.catalog.enums import UnitType


def _normalize_price(v: object) -> Decimal:
    """Coerce to a positive Decimal with exactly 2 dp (005 FR-16..FR-18, normalized)."""
    try:
        amount = Decimal(str(v))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("price must be a valid number") from exc
    if amount <= 0:
        raise ValueError("price must be greater than 0")
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ProductCreate(BaseModel):
    """Direct create from the vendor add-product form.

    Accepts the frontend display shape; `category`/`subcategory_id` are resolved
    to a SubCategory by the service (falling back to General, 006 FR-5).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    price: Decimal
    stock: int = Field(default=0, ge=0)
    description: str = ""
    category: Optional[str] = None
    subcategory_id: Optional[str] = None
    brand: Optional[str] = None
    unit_type: Optional[UnitType] = None
    unit_value: Optional[Decimal] = None

    @field_validator("price", mode="before")
    @classmethod
    def _price(cls, v: object) -> Decimal:
        return _normalize_price(v)

    @field_validator("unit_value")
    @classmethod
    def _unit_value_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("unit_value must be greater than 0")
        return v


class ProductUpdate(BaseModel):
    """Partial update from the edit form. All fields optional."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, min_length=1)
    price: Optional[Decimal] = None
    stock: Optional[int] = Field(default=None, ge=0)
    description: Optional[str] = None
    category: Optional[str] = None

    @field_validator("price", mode="before")
    @classmethod
    def _price(cls, v: object) -> Optional[Decimal]:
        if v is None:
            return None
        return _normalize_price(v)


class ProductDescriptionRequest(BaseModel):
    """Create-from-description / delete-by-description payload."""

    model_config = ConfigDict(str_strip_whitespace=True)

    description_text: str = Field(min_length=1)


class ProductRead(BaseModel):
    """Product as returned to the frontend: display aliases + raw catalog fields."""

    # display aliases (VendorPage renders these unchanged)
    id: str
    name: str
    price: float
    stock: int
    category: str
    description: str
    vendorId: str
    # raw catalog fields
    product_id: str
    subcategory_id: str
    brand: str
    unit_type: UnitType
    unit_value: float
    price_inr: float
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_product(cls, product, category_name: str) -> "ProductRead":
        return cls(
            id=str(product.product_id),
            name=product.product_name,
            price=float(product.price_inr),
            stock=product.stock_quantity,
            category=category_name,
            description=product.description,
            vendorId=str(product.vendor_id),
            product_id=str(product.product_id),
            subcategory_id=str(product.subcategory_id),
            brand=product.brand,
            unit_type=product.unit_type,
            unit_value=float(product.unit_value),
            price_inr=float(product.price_inr),
            created_at=product.created_at,
            updated_at=product.updated_at,
        )


class ProductResponse(BaseModel):
    """Single-product envelope ({ product: ... }) matching the frontend contract."""

    product: ProductRead


class ProductListResponse(BaseModel):
    """Product-list envelope ({ products: [...] }) matching the frontend contract."""

    products: list[ProductRead]


class CategoryRead(BaseModel):
    category_id: str
    category_name: str
    parent_category_id: Optional[str] = None


class SubCategoryRead(BaseModel):
    subcategory_id: str
    subcategory_name: str
    parent_category_id: str
    subcategory_description: str
