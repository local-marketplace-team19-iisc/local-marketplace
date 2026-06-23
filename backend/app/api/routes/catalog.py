from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.schemas.product import CategoryRead, SubCategoryRead
from backend.app.services import product_service

router = APIRouter()


def get_db() -> Session:
    """Dependency: database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/categories", response_model=list[CategoryRead])
def list_categories(db: Session = Depends(get_db)):
    """List predefined catalog categories (platform-owned; 005 FR-11)."""
    return product_service.list_categories(db)


@router.get("/subcategories", response_model=list[SubCategoryRead])
def list_subcategories(db: Session = Depends(get_db)):
    """List predefined catalog subcategories (platform-owned; 005 FR-12)."""
    return product_service.list_subcategories(db)
