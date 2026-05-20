"""Add model_name and rdb_imported to datasets

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("datasets", sa.Column("model_name", sa.String(255), nullable=True))
    op.add_column("datasets", sa.Column("rdb_imported", sa.Boolean, nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("datasets", "rdb_imported")
    op.drop_column("datasets", "model_name")
