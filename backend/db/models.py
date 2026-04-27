import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ── Enums ──────────────────────────────────────────────────────────────────────

class UserRole(str, PyEnum):
    attorney = "attorney"
    admin = "admin"


class SubscriptionTier(str, PyEnum):
    starter = "starter"
    professional = "professional"
    enterprise = "enterprise"


class MatterType(str, PyEnum):
    contract = "contract"
    litigation = "litigation"
    compliance = "compliance"


class MatterStatus(str, PyEnum):
    active = "active"
    closed = "closed"
    archived = "archived"


class IngestionStatus(str, PyEnum):
    pending = "pending"
    processing = "processing"
    complete = "complete"
    failed = "failed"


class SessionStatus(str, PyEnum):
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    processing = "processing"
    complete = "complete"


class AlertSeverity(str, PyEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AlertStatus(str, PyEnum):
    unread = "unread"
    read = "read"
    dismissed = "dismissed"


class CorrectionType(str, PyEnum):
    factual = "factual"
    legal_reasoning = "legal_reasoning"
    citation = "citation"
    tone = "tone"
    completeness = "completeness"


# ── ORM Models ─────────────────────────────────────────────────────────────────

class Firm(Base):
    __tablename__ = "firms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subscription_tier: Mapped[str] = mapped_column(
        String(50), default=SubscriptionTier.starter, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    users: Mapped[list["User"]] = relationship("User", back_populates="firm")
    matters: Mapped[list["Matter"]] = relationship("Matter", back_populates="firm")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default=UserRole.attorney, nullable=False)
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    firm: Mapped["Firm"] = relationship("Firm", back_populates="users")
    sessions: Mapped[list["AgentSession"]] = relationship("AgentSession", back_populates="user")


class Matter(Base):
    __tablename__ = "matters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    matter_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=MatterStatus.active, nullable=False)
    jurisdiction: Mapped[str | None] = mapped_column(String(100), nullable=True)
    practice_area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    firm: Mapped["Firm"] = relationship("Firm", back_populates="matters")
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="matter")
    sessions: Mapped[list["AgentSession"]] = relationship("AgentSession", back_populates="matter")
    alerts: Mapped[list["ComplianceAlert"]] = relationship("ComplianceAlert", back_populates="matter")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    matter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matters.id"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ingestion_status: Mapped[str] = mapped_column(
        String(50), default=IngestionStatus.pending, nullable=False
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    matter: Mapped["Matter"] = relationship("Matter", back_populates="documents")
    source_chunks: Mapped[list["SourceChunk"]] = relationship("SourceChunk", back_populates="source_doc")


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    matter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matters.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    agent_route: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default=SessionStatus.processing, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    matter: Mapped["Matter"] = relationship("Matter", back_populates="sessions")
    user: Mapped["User"] = relationship("User", back_populates="sessions")
    source_chunks: Mapped[list["SourceChunk"]] = relationship("SourceChunk", back_populates="session")
    corrections: Mapped[list["AttorneyCorrection"]] = relationship(
        "AttorneyCorrection", back_populates="session"
    )


class SourceChunk(Base):
    __tablename__ = "source_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_sessions.id"), nullable=False, index=True
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_doc_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank_position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    session: Mapped["AgentSession"] = relationship("AgentSession", back_populates="source_chunks")
    source_doc: Mapped["Document | None"] = relationship("Document", back_populates="source_chunks")


class ComplianceAlert(Base):
    __tablename__ = "compliance_alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    matter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matters.id"), nullable=True, index=True
    )
    regulation_title: Mapped[str] = mapped_column(String(500), nullable=False)
    regulation_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    delta_summary: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(
        String(50), default=AlertSeverity.medium, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), default=AlertStatus.unread, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    matter: Mapped["Matter | None"] = relationship("Matter", back_populates="alerts")


class AttorneyCorrection(Base):
    __tablename__ = "attorney_corrections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_sessions.id"), nullable=False, index=True
    )
    original_output: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_output: Mapped[str] = mapped_column(Text, nullable=False)
    correction_type: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped["AgentSession"] = relationship("AgentSession", back_populates="corrections")
