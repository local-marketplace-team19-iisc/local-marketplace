"""add otp lockout tracking columns (attempts, locked_until)

Revision ID: 0002_add_otp_lockout_columns
Revises: 0001_create_auth_tables
Create Date: 2026-06-20

"""
import sqlalchemy as sa
from alembic import op

revision = "0002_add_otp_lockout_columns"
down_revision = "0001_create_auth_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "otps",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("otps", sa.Column("locked_until", sa.DateTime(), nullable=True))
    op.create_index("ix_otps_locked_until", "otps", ["locked_until"])


def downgrade() -> None:
    op.drop_index("ix_otps_locked_until", table_name="otps")
    op.drop_column("otps", "locked_until")
    op.drop_column("otps", "attempts")
