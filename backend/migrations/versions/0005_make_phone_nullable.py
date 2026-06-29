"""Make users.phone nullable to support email-only registration

Revision ID: 0005_make_phone_nullable
Revises: 0004_create_catalog_products
Create Date: 2026-06-30

Feature 003 email/password auth does not require a phone number.
Migration 0001 created phone as NOT NULL; this migration relaxes it.
"""
import sqlalchemy as sa
from alembic import op

revision = "0005_make_phone_nullable"
down_revision = "0004_create_catalog_products"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "phone", existing_type=sa.String(length=15), nullable=True)


def downgrade() -> None:
    # NOTE: this will fail if any rows have phone=NULL — only run on empty DB
    op.alter_column("users", "phone", existing_type=sa.String(length=15), nullable=False)
