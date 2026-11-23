from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Repository(Base):
    __tablename__ = "repositories"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), unique=True)
    html_url: Mapped[str | None] = mapped_column(String(500))
    default_branch: Mapped[str | None] = mapped_column(String(120))
    license_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class DataSource(Base):
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(255))
    uri: Mapped[str] = mapped_column(String(500))
    repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    license_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    last_cursor: Mapped[str | None] = mapped_column(String(255))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    repository: Mapped[Repository | None] = relationship()
    sync_jobs: Mapped[list["SyncJob"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class SyncJob(Base):
    __tablename__ = "sync_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("data_sources.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(30), index=True)
    items_seen: Mapped[int] = mapped_column(Integer, default=0)
    items_created: Mapped[int] = mapped_column(Integer, default=0)
    items_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source: Mapped[DataSource] = relationship(back_populates="sync_jobs")


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint(
            "source_type", "external_id", name="uq_incident_source_external"
        ),
        Index("ix_incident_repo_status", "repository_id", "status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(50), index=True)
    external_id: Mapped[str] = mapped_column(String(255), index=True)
    repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL")
    )
    product: Mapped[str | None] = mapped_column(String(160), index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    symptoms: Mapped[list[str] | None] = mapped_column(JSON)
    error_codes: Mapped[list[str] | None] = mapped_column(JSON)
    affected_component: Mapped[str | None] = mapped_column(String(255), index=True)
    affected_version: Mapped[str | None] = mapped_column(String(160), index=True)
    reproduction_steps: Mapped[list[str] | None] = mapped_column(JSON)
    logs: Mapped[list[str] | None] = mapped_column(JSON)
    candidate_resolution: Mapped[str | None] = mapped_column(Text)
    confirmed_resolution: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), index=True)
    source_url: Mapped[str] = mapped_column(String(700))
    source_hash: Mapped[str] = mapped_column(String(64), index=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    license_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    provenance: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    repository: Mapped[Repository | None] = relationship()
    comments: Mapped[list["IncidentComment"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    media: Mapped[list["IncidentMedia"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )


class IncidentComment(Base):
    __tablename__ = "incident_comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(255))
    author: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(700))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    incident: Mapped[Incident] = relationship(back_populates="comments")


class IncidentMedia(Base):
    __tablename__ = "incident_media"
    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    media_type: Mapped[str] = mapped_column(String(30))
    source_url: Mapped[str] = mapped_column(String(1000))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    ocr_text: Mapped[str | None] = mapped_column(Text)
    license_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    incident: Mapped[Incident] = relationship(back_populates="media")


class Documentation(Base):
    __tablename__ = "documentation"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(50), default="documentation")
    title: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str] = mapped_column(String(1000), unique=True)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    license_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documentation.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(500))

    document: Mapped[Documentation] = relationship(back_populates="chunks")


class ErrorSignature(Base):
    __tablename__ = "error_signatures"
    id: Mapped[int] = mapped_column(primary_key=True)
    signature: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    error_code: Mapped[str | None] = mapped_column(String(120), index=True)
    exception_name: Mapped[str | None] = mapped_column(String(255))
    normalized_message: Mapped[str | None] = mapped_column(Text)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)


class ImageAsset(Base):
    __tablename__ = "image_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_url: Mapped[str] = mapped_column(String(1000), unique=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    ocr_text: Mapped[str | None] = mapped_column(Text)
    embedding_backend: Mapped[str | None] = mapped_column(String(120))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class AudioAsset(Base):
    __tablename__ = "audio_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_path: Mapped[str] = mapped_column(String(1000))
    transcript: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(20))
    duration_seconds: Mapped[float | None]
    status: Mapped[str] = mapped_column(String(30), default="pending")


class EmbeddingMetadata(Base):
    __tablename__ = "embeddings_metadata"
    id: Mapped[int] = mapped_column(primary_key=True)
    object_type: Mapped[str] = mapped_column(String(50), index=True)
    object_id: Mapped[int] = mapped_column(Integer, index=True)
    backend: Mapped[str] = mapped_column(String(120))
    model_name: Mapped[str | None] = mapped_column(String(255))
    index_path: Mapped[str | None] = mapped_column(String(1000))
    dimension: Mapped[int | None] = mapped_column(Integer)


class IncidentRelation(Base):
    __tablename__ = "incident_relations"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[str] = mapped_column(String(80))
    target_type: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[str] = mapped_column(String(255))
    evidence: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(default=1.0)


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(30), default="medium")
    status: Mapped[str] = mapped_column(String(30), default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class TicketAttachment(Base):
    __tablename__ = "ticket_attachments"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(100))
    storage_path: Mapped[str] = mapped_column(String(1000))


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    mode: Mapped[str] = mapped_column(String(30), default="LIGHT")
    result: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class EvidenceBundle(Base):
    __tablename__ = "evidence_bundles"
    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(Text)
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    retrieval_method: Mapped[str] = mapped_column(String(120))
    latency_ms: Mapped[float] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(30))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Citation(Base):
    __tablename__ = "citations"
    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE")
    )
    source_type: Mapped[str] = mapped_column(String(50))
    source_id: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(String(1000))
    excerpt: Mapped[str] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Evaluation(Base):
    __tablename__ = "evaluations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    dataset_version: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    task: Mapped[str] = mapped_column(String(120))
    backend: Mapped[str] = mapped_column(String(120))
    model_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30))
    latency_ms: Mapped[float | None]
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    actor: Mapped[str | None] = mapped_column(String(255))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
