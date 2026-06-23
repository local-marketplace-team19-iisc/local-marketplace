from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.models.user import UserRole
from backend.app.schemas.product import (
    ProductCreate,
    ProductDescriptionRequest,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from backend.app.services import auth_service, product_service

router = APIRouter()


def get_db() -> Session:
    """Dependency: database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_vendor(request: Request, db: Session = Depends(get_db)) -> str:
    """Resolve the authenticated vendor's id from the Bearer token (006 FR-8)."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = auth_header[7:]
    try:
        user = auth_service.get_current_user(db, token)
    except auth_service.AuthUnauthorizedError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    if user.get("user_type") != UserRole.vendor.value or not user.get("vendor_id"):
        raise HTTPException(status_code=403, detail="Vendor account required.")
    return user["vendor_id"]


def _map_error(exc: product_service.ProductError) -> HTTPException:
    if isinstance(exc, product_service.ProductNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, product_service.ProductForbiddenError):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("", response_model=ProductListResponse)
def list_products(vendor_id: str | None = None, db: Session = Depends(get_db)):
    """List products (optionally filtered by vendor). Public read."""
    return {"products": product_service.list_products(db, vendor_id=vendor_id)}


@router.post("", response_model=ProductResponse, status_code=201)
def create_product(
    data: ProductCreate,
    vendor_id: str = Depends(get_current_vendor),
    db: Session = Depends(get_db),
):
    try:
        return {"product": product_service.create_product(db, vendor_id, data)}
    except product_service.ProductError as e:
        raise _map_error(e) from e


@router.post("/from-description", response_model=ProductResponse, status_code=201)
def create_from_description(
    data: ProductDescriptionRequest,
    vendor_id: str = Depends(get_current_vendor),
    db: Session = Depends(get_db),
):
    try:
        return {"product": product_service.create_from_description(db, vendor_id, data.description_text)}
    except product_service.ProductError as e:
        raise _map_error(e) from e


@router.post("/delete-by-description", response_model=ProductResponse)
def delete_by_description(
    data: ProductDescriptionRequest,
    vendor_id: str = Depends(get_current_vendor),
    db: Session = Depends(get_db),
):
    try:
        return {"product": product_service.delete_by_description(db, vendor_id, data.description_text)}
    except product_service.ProductError as e:
        raise _map_error(e) from e


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str,
    data: ProductUpdate,
    vendor_id: str = Depends(get_current_vendor),
    db: Session = Depends(get_db),
):
    try:
        return {"product": product_service.update_product(db, vendor_id, product_id, data)}
    except product_service.ProductError as e:
        raise _map_error(e) from e


@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: str,
    vendor_id: str = Depends(get_current_vendor),
    db: Session = Depends(get_db),
):
    try:
        product_service.delete_product(db, vendor_id, product_id)
    except product_service.ProductError as e:
        raise _map_error(e) from e
