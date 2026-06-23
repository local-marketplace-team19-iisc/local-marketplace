"""Vendor product workflow service (feature 006).

Plain functions over a SQLAlchemy Session, mirroring auth_service.py. Writes are
scoped to the owning vendor (006 FR-8/FR-9). Typed errors are mapped to HTTP
status codes by the route layer.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.catalog.parser import parse_description
from backend.app.catalog.seed_data import GENERAL_SUBCATEGORY_ID
from backend.app.models.category import Category
from backend.app.models.product import Product
from backend.app.models.subcategory import SubCategory
from backend.app.schemas.product import (
    CategoryRead,
    ProductCreate,
    ProductRead,
    ProductUpdate,
    SubCategoryRead,
)


class ProductError(Exception):
    """Base error for product operations."""


class ProductValidationError(ProductError):
    pass


class ProductNotFoundError(ProductError):
    pass


class ProductForbiddenError(ProductError):
    pass


# --------------------------------------------------------------------------- #
# Resolution helpers
# --------------------------------------------------------------------------- #
def _resolve_subcategory(
    db: Session,
    *,
    subcategory_id: str | None = None,
    subcategory_name: str | None = None,
    category_name: str | None = None,
) -> SubCategory:
    """Resolve to a SubCategory, falling back to the seeded General one (006 FR-5)."""
    if subcategory_id:
        sub = db.query(SubCategory).filter(SubCategory.subcategory_id == subcategory_id).first()
        if sub:
            return sub

    if subcategory_name:
        sub = (
            db.query(SubCategory)
            .filter(SubCategory.subcategory_name.ilike(subcategory_name))
            .first()
        )
        if sub:
            return sub

    if category_name:
        cat = db.query(Category).filter(Category.category_name.ilike(category_name)).first()
        if cat:
            sub = (
                db.query(SubCategory)
                .filter(
                    SubCategory.parent_category_id == cat.category_id,
                    SubCategory.subcategory_name.ilike("General"),
                )
                .first()
            )
            if sub:
                return sub

    general = (
        db.query(SubCategory)
        .filter(SubCategory.subcategory_id == GENERAL_SUBCATEGORY_ID)
        .first()
    )
    if not general:
        raise ProductValidationError(
            "Catalog taxonomy is not seeded (General subcategory missing)."
        )
    return general


def _category_name(product: Product) -> str:
    """Parent category name for display (falls back to subcategory name)."""
    sub = product.subcategory
    if sub and sub.category:
        return sub.category.category_name
    return sub.subcategory_name if sub else "General"


def _read(product: Product) -> ProductRead:
    return ProductRead.from_product(product, _category_name(product))


# --------------------------------------------------------------------------- #
# Catalog reads
# --------------------------------------------------------------------------- #
def list_categories(db: Session) -> list[CategoryRead]:
    rows = db.query(Category).order_by(Category.category_name).all()
    return [
        CategoryRead(
            category_id=str(c.category_id),
            category_name=c.category_name,
            parent_category_id=str(c.parent_category_id) if c.parent_category_id else None,
        )
        for c in rows
    ]


def list_subcategories(db: Session) -> list[SubCategoryRead]:
    rows = db.query(SubCategory).order_by(SubCategory.subcategory_name).all()
    return [
        SubCategoryRead(
            subcategory_id=str(s.subcategory_id),
            subcategory_name=s.subcategory_name,
            parent_category_id=str(s.parent_category_id),
            subcategory_description=s.subcategory_description,
        )
        for s in rows
    ]


# --------------------------------------------------------------------------- #
# Product reads
# --------------------------------------------------------------------------- #
def list_products(db: Session, vendor_id: str | None = None) -> list[ProductRead]:
    query = db.query(Product)
    if vendor_id:
        query = query.filter(Product.vendor_id == vendor_id)
    return [_read(p) for p in query.order_by(Product.created_at.desc()).all()]


# --------------------------------------------------------------------------- #
# Product writes (vendor-scoped)
# --------------------------------------------------------------------------- #
def create_product(db: Session, vendor_id: str, data: ProductCreate) -> ProductRead:
    sub = _resolve_subcategory(
        db, subcategory_id=data.subcategory_id, category_name=data.category
    )
    product = Product(
        subcategory_id=sub.subcategory_id,
        vendor_id=vendor_id,
        product_name=data.name,
        brand=(data.brand or "Generic"),
        description=(data.description or data.name),
        unit_type=(data.unit_type or "PIECE"),
        unit_value=(data.unit_value if data.unit_value is not None else Decimal("1")),
        price_inr=data.price,
        stock_quantity=data.stock,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return _read(product)


def create_from_description(db: Session, vendor_id: str, text: str) -> ProductRead:
    parsed = parse_description(text)
    if parsed.price_inr is None:
        raise ProductValidationError(
            "Could not find a price in the description. "
            "Include a price, e.g. ₹58 or Rs 58."
        )
    sub = _resolve_subcategory(
        db,
        subcategory_name=parsed.subcategory_name,
        category_name=parsed.category_name,
    )
    product = Product(
        subcategory_id=sub.subcategory_id,
        vendor_id=vendor_id,
        product_name=parsed.product_name,
        brand=parsed.brand,
        description=parsed.description,
        unit_type=parsed.unit_type,
        unit_value=parsed.unit_value,
        price_inr=parsed.price_inr,
        stock_quantity=parsed.stock_quantity,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return _read(product)


def _owned_product(db: Session, vendor_id: str, product_id: str) -> Product:
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise ProductNotFoundError("Product not found.")
    if str(product.vendor_id) != str(vendor_id):
        raise ProductForbiddenError("You can only modify your own products.")
    return product


def update_product(
    db: Session, vendor_id: str, product_id: str, data: ProductUpdate
) -> ProductRead:
    product = _owned_product(db, vendor_id, product_id)
    if data.name is not None:
        product.product_name = data.name
    if data.price is not None:
        product.price_inr = data.price
    if data.stock is not None:
        product.stock_quantity = data.stock
    if data.description is not None:
        product.description = data.description
    if data.category is not None:
        product.subcategory_id = _resolve_subcategory(
            db, category_name=data.category
        ).subcategory_id
    db.commit()
    db.refresh(product)
    return _read(product)


def delete_product(db: Session, vendor_id: str, product_id: str) -> None:
    product = _owned_product(db, vendor_id, product_id)
    db.delete(product)
    db.commit()


def delete_by_description(db: Session, vendor_id: str, text: str) -> ProductRead:
    """Find the calling vendor's best-matching product and delete it (006 FR-9)."""
    tokens = [w for w in _normalize(text).split() if len(w) > 2]
    candidates = db.query(Product).filter(Product.vendor_id == vendor_id).all()

    best: Product | None = None
    best_score = 0
    for product in candidates:
        haystack = _normalize(
            f"{product.product_name} {product.brand} {product.description}"
        )
        name_norm = _normalize(product.product_name)
        score = sum(1 for t in tokens if t in haystack)
        if name_norm and name_norm in _normalize(text):
            score += 5  # whole product-name match (mirrors the frontend heuristic)
        # deterministic: higher score wins; tie -> most recently created
        if score > 0 and (
            best is None
            or score > best_score
            or (score == best_score and product.created_at > best.created_at)
        ):
            best, best_score = product, score

    if best is None:
        raise ProductNotFoundError(f'No product of yours matches "{text}".')

    read = _read(best)
    db.delete(best)
    db.commit()
    return read


def _normalize(text: str) -> str:
    import re

    return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())
