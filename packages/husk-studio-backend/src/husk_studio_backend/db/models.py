from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RunRow(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    parent_run_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("runs.id"), nullable=True
    )
    fork_span_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    script_path: Mapped[str] = mapped_column(Text, nullable=False)
    script_argv: Mapped[list] = mapped_column(JSON, default=list)
    framework: Mapped[str] = mapped_column(String(32), default="unknown")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    started_at: Mapped[int] = mapped_column(BigInteger, index=True)
    finished_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    env_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("idx_runs_parent", "parent_run_id"),
        Index("idx_runs_started", "started_at"),
    )


class SpanRow(Base):
    __tablename__ = "spans"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    parent_span_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(Text)
    started_at: Mapped[int] = mapped_column(BigInteger, index=True)
    finished_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    input_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_inline: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    output_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_inline: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    http_request_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attrs: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (
        Index("idx_spans_run_started", "run_id", "started_at"),
        Index("idx_spans_run_parent", "run_id", "parent_span_id"),
    )


class SnapshotRow(Base):
    __tablename__ = "snapshots"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    span_id: Mapped[str] = mapped_column(String(26), index=True)
    created_at: Mapped[int] = mapped_column(BigInteger)
    state_ref: Mapped[str] = mapped_column(Text)
    state_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    rng_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    http_cassette_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    serializer: Mapped[str] = mapped_column(String(32), default="pydantic_v0")


class BranchRow(Base):
    __tablename__ = "branches"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    parent_run_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    child_run_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("runs.id", ondelete="CASCADE"), unique=True
    )
    fork_span_id: Mapped[str] = mapped_column(String(26))
    override_payload: Mapped[dict] = mapped_column(JSON)
    override_type: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[int] = mapped_column(BigInteger)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class HttpCassetteRow(Base):
    __tablename__ = "http_cassettes"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    span_id: Mapped[str] = mapped_column(String(26), index=True)
    method: Mapped[str] = mapped_column(String(8))
    url: Mapped[str] = mapped_column(Text)
    request_hash: Mapped[str] = mapped_column(String(64), index=True)
    request_body_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_status: Mapped[int] = mapped_column(Integer)
    response_body_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_headers: Mapped[dict] = mapped_column(JSON, default=dict)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (UniqueConstraint("run_id", "request_hash", name="uq_cassette_run_hash"),)


class CursorEventRow(Base):
    """Observability events captured from IDE bridges (Cursor, VS Code).

    Stores fire-and-forget events such as `afterFileEdit`, `stop`, and
    `terminal.command` so the Studio can render IDE activity alongside agent
    spans. Husk does not block the IDE or return permission decisions.
    """

    __tablename__ = "cursor_events"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    hook: Mapped[str] = mapped_column(String(64), index=True)
    project: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[int] = mapped_column(BigInteger, index=True)

    __table_args__ = (Index("idx_cursor_hook_created", "hook", "created_at"),)
