"""Add email/password authentication support to auth tables

Revision ID: 0003_add_email_password_auth
Revises: 0002_add_otp_lockout_columns
Create Date: 2026-06-21

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_add_email_password_auth"
down_revision = "0002_add_otp_lockout_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add email and password_hash columns to users table (nullable for backward compat with phone auth)
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_index("ix_users_email", "users", ["email"])

    # Add shop_description and is_active columns to vendors table
    op.add_column("vendors", sa.Column("shop_description", sa.String(length=1000), nullable=True))
    op.add_column("vendors", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

    # Add revoked_at timestamp to refresh_tokens table (for spec-defined logout behavior)
    op.add_column("refresh_tokens", sa.Column("revoked_at", sa.DateTime(), nullable=True))
    op.create_index("ix_refresh_tokens_revoked_at", "refresh_tokens", ["revoked_at"])


def downgrade() -> None:
    # Drop refresh_tokens revoked_at
    op.drop_index("ix_refresh_tokens_revoked_at", table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "revoked_at")

    # Drop vendors columns
    op.drop_column("vendors", "is_active")
    op.drop_column("vendors", "shop_description")

    # Drop users email/password columns
    op.drop_index("ix_users_email", table_name="users")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "email")
