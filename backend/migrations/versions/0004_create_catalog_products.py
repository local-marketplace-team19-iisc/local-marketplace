"""create catalog tables: categories, subcategories, products (+ seed taxonomy)

Revision ID: 0004_create_catalog_products
Revises: 0003_add_email_password_auth
Create Date: 2026-06-23

Feature 006-vendor-product-management. Persists the Feature 005 catalog schema
(Category -> SubCategory -> Product) plus the four operational fields 005
deferred (vendor_id, stock_quantity, created_at, updated_at) and seeds the
deterministic taxonomy from backend.app.catalog.seed_data.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from backend.app.catalog.seed_data import iter_categories, iter_subcategories

# revision identifiers, used by Alembic.
revision = "0004_create_catalog_products"
down_revision = "0003_add_email_password_auth"
branch_labels = None
depends_on = None

unit_type = sa.Enum(
    "LITER", "MILLILITER", "KILOGRAM", "GRAM", "PIECE", "PACK", "DOZEN", name="unit_type"
)


def upgrade() -> None:
    unit_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "categories",
        sa.Column("category_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("category_name", sa.String(length=255), nullable=False),
        sa.Column("parent_category_id", UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint("category_name", name="uq_categories_category_name"),
    )

    op.create_table(
        "subcategories",
        sa.Column("subcategory_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("subcategory_name", sa.String(length=255), nullable=False),
        sa.Column(
            "parent_category_id",
            UUID(as_uuid=True),
            sa.ForeignKey("categories.category_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subcategory_description", sa.String(length=500), nullable=False),
    )
    op.create_index(
        "ix_subcategories_parent_category_id", "subcategories", ["parent_category_id"]
    )

    op.create_table(
        "products",
        sa.Column("product_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "subcategory_id",
            UUID(as_uuid=True),
            sa.ForeignKey("subcategories.subcategory_id"),
            nullable=False,
        ),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("brand", sa.String(length=255), nullable=False, server_default="Generic"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit_type", unit_type, nullable=False),
        sa.Column("unit_value", sa.Numeric(10, 3), nullable=False),
        sa.Column("price_inr", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "vendor_id",
            UUID(as_uuid=True),
            sa.ForeignKey("vendors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_products_vendor_id", "products", ["vendor_id"])
    op.create_index("ix_products_subcategory_id", "products", ["subcategory_id"])

    # Seed the deterministic taxonomy (single source: catalog/seed_data.py).
    categories_tbl = sa.table(
        "categories",
        sa.column("category_id", UUID(as_uuid=True)),
        sa.column("category_name", sa.String),
        sa.column("parent_category_id", UUID(as_uuid=True)),
    )
    op.bulk_insert(categories_tbl, iter_categories())

    subcategories_tbl = sa.table(
        "subcategories",
        sa.column("subcategory_id", UUID(as_uuid=True)),
        sa.column("subcategory_name", sa.String),
        sa.column("parent_category_id", UUID(as_uuid=True)),
        sa.column("subcategory_description", sa.String),
    )
    op.bulk_insert(subcategories_tbl, iter_subcategories())


def downgrade() -> None:
    op.drop_index("ix_products_subcategory_id", table_name="products")
    op.drop_index("ix_products_vendor_id", table_name="products")
    op.drop_table("products")

    op.drop_index("ix_subcategories_parent_category_id", table_name="subcategories")
    op.drop_table("subcategories")

    op.drop_table("categories")

    unit_type.drop(op.get_bind(), checkfirst=True)
