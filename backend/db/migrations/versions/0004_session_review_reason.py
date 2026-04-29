"""add review_reason to agent_sessions

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("agent_sessions", sa.Column("review_reason", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("agent_sessions", "review_reason")
