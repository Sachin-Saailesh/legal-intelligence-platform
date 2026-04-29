"""add closed_at to matters

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("matters", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("matters", "closed_at")
