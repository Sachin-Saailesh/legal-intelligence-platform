"""Add timeline events and discovery items

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-27 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "timeline_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("matters.id"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False, server_default="other"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="upcoming"),
        sa.Column("source", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("document_ref", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_timeline_events_matter_id", "timeline_events", ["matter_id"])
    op.create_index("ix_timeline_events_event_date", "timeline_events", ["event_date"])

    op.create_table(
        "discovery_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("matters.id"), nullable=False),
        sa.Column("item_type", sa.String(50), nullable=False, server_default="other"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("priority", sa.String(50), nullable=False, server_default="medium"),
        sa.Column("assigned_to", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_discovery_items_matter_id", "discovery_items", ["matter_id"])
    op.create_index("ix_discovery_items_deadline", "discovery_items", ["deadline"])


def downgrade() -> None:
    op.drop_index("ix_discovery_items_deadline")
    op.drop_index("ix_discovery_items_matter_id")
    op.drop_table("discovery_items")
    op.drop_index("ix_timeline_events_event_date")
    op.drop_index("ix_timeline_events_matter_id")
    op.drop_table("timeline_events")
