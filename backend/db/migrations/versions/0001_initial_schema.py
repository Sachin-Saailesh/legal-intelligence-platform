"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "firms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("subscription_tier", sa.String(50), nullable=False, server_default="starter"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="attorney"),
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("firms.id"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "matters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("firms.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("matter_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("jurisdiction", sa.String(100), nullable=True),
        sa.Column("practice_area", sa.String(100), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_matters_firm_id", "matters", ["firm_id"])

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("matters.id"), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("doc_type", sa.String(100), nullable=True),
        sa.Column("ingestion_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_documents_matter_id", "documents", ["matter_id"])

    op.create_table(
        "agent_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("matters.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("agent_route", sa.Text, nullable=True),
        sa.Column("final_output", sa.Text, nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="processing"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_sessions_matter_id", "agent_sessions", ["matter_id"])

    op.create_table(
        "source_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_sessions.id"), nullable=False),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("source_doc_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("rank_position", sa.Integer, nullable=True),
    )
    op.create_index("ix_source_chunks_session_id", "source_chunks", ["session_id"])

    op.create_table(
        "compliance_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("matters.id"), nullable=True),
        sa.Column("regulation_title", sa.String(500), nullable=False),
        sa.Column("regulation_url", sa.String(1000), nullable=True),
        sa.Column("delta_summary", sa.Text, nullable=False),
        sa.Column("severity", sa.String(50), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(50), nullable=False, server_default="unread"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_compliance_alerts_matter_id", "compliance_alerts", ["matter_id"])

    op.create_table(
        "attorney_corrections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_sessions.id"), nullable=False),
        sa.Column("original_output", sa.Text, nullable=False),
        sa.Column("corrected_output", sa.Text, nullable=False),
        sa.Column("correction_type", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_attorney_corrections_session_id", "attorney_corrections", ["session_id"])


def downgrade() -> None:
    op.drop_table("attorney_corrections")
    op.drop_table("compliance_alerts")
    op.drop_table("source_chunks")
    op.drop_table("agent_sessions")
    op.drop_table("documents")
    op.drop_table("matters")
    op.drop_table("users")
    op.drop_table("firms")
