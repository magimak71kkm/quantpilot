"""ORM models — subset of the DDL in scripts/init_db.sql."""
from datetime import datetime

from sqlalchemy import (
    JSON, BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey,
    Integer, LargeBinary, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    pw_hash: Mapped[str] = mapped_column(Text, nullable=False)
    totp_secret: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GoogleAccount(Base):
    __tablename__ = "google_accounts"
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    google_sub: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    google_email: Mapped[str | None] = mapped_column(String(200))
    scopes: Mapped[str] = mapped_column(Text, nullable=False)  # space-joined
    enc_refresh_token: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    ip: Mapped[str] = mapped_column(String(64), default="")
    payload_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---- Versioning (S13) --------------------------------------------------------
class Strategy(Base):
    __tablename__ = "strategies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    current_ref: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "name"),)


class Commit(Base):
    __tablename__ = "commits"
    sha: Mapped[str] = mapped_column(String(40), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(String(36), ForeignKey("strategies.id", ondelete="CASCADE"))
    parent_sha: Mapped[str | None] = mapped_column(String(40), ForeignKey("commits.sha"))
    merge_parent: Mapped[str | None] = mapped_column(String(40), ForeignKey("commits.sha"))
    author_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    tree_hash: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CommitFile(Base):
    __tablename__ = "commit_files"
    commit_sha: Mapped[str] = mapped_column(String(40), ForeignKey("commits.sha", ondelete="CASCADE"), primary_key=True)
    path: Mapped[str] = mapped_column(String(200), primary_key=True)
    blob_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)


class Branch(Base):
    __tablename__ = "branches"
    strategy_id: Mapped[str] = mapped_column(String(36), ForeignKey("strategies.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    head_sha: Mapped[str] = mapped_column(String(40), ForeignKey("commits.sha"), nullable=False)
    protected: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Tag(Base):
    __tablename__ = "tags"
    strategy_id: Mapped[str] = mapped_column(String(36), ForeignKey("strategies.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    target_sha: Mapped[str] = mapped_column(String(40), ForeignKey("commits.sha"), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SLOPolicy(Base):
    __tablename__ = "slo_policies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    availability_pct:   Mapped[float] = mapped_column(default=99.9)
    latency_p95_ms:     Mapped[int]   = mapped_column(default=2000)
    ai_schema_fail_pct: Mapped[float] = mapped_column(default=5.0)
    burn_rate_target:   Mapped[float] = mapped_column(default=0.001)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SLOPolicyHistory(Base):
    __tablename__ = "slo_policy_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("slo_policies.id", ondelete="CASCADE"), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    prev_json: Mapped[dict | None] = mapped_column(JSON)
    next_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Deployment(Base):
    __tablename__ = "deployments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[str] = mapped_column(String(36), ForeignKey("strategies.id"))
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), ForeignKey("commits.sha"))
    deployed_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    deployed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reverted_at: Mapped[datetime | None] = mapped_column(DateTime)
    reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (CheckConstraint("environment in ('paper','live')"),)
