"""initial schema — users/google/audit/versioning tables.

Revision ID: 0001
Revises:
Create Date: 2026-08-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(200), unique=True, nullable=False),
        sa.Column("pw_hash", sa.Text, nullable=False),
        sa.Column("totp_secret", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "google_accounts",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("google_sub", sa.String(64), unique=True, nullable=False),
        sa.Column("google_email", sa.String(200)),
        sa.Column("scopes", sa.Text, nullable=False),
        sa.Column("enc_refresh_token", sa.LargeBinary, nullable=False),
        sa.Column("linked_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("endpoint", sa.String(200), nullable=False),
        sa.Column("status", sa.Integer, nullable=False),
        sa.Column("duration_ms", sa.Integer, server_default="0"),
        sa.Column("ip", sa.String(64), server_default=""),
        sa.Column("payload_hash", sa.String(64), server_default=""),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_user_created", "audit_logs", ["user_id", "created_at"])

    op.create_table(
        "strategies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("current_ref", sa.String(100)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "name"),
    )
    op.create_table(
        "commits",
        sa.Column("sha", sa.String(40), primary_key=True),
        sa.Column("strategy_id", sa.String(36), sa.ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_sha", sa.String(40), sa.ForeignKey("commits.sha")),
        sa.Column("merge_parent", sa.String(40), sa.ForeignKey("commits.sha")),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("tree_hash", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_commits_strategy_created", "commits", ["strategy_id", "created_at"])
    op.create_table(
        "commit_files",
        sa.Column("commit_sha", sa.String(40), sa.ForeignKey("commits.sha", ondelete="CASCADE"), primary_key=True),
        sa.Column("path", sa.String(200), primary_key=True),
        sa.Column("blob_sha", sa.String(40), nullable=False),
        sa.Column("content", sa.JSON, nullable=False),
    )
    op.create_table(
        "branches",
        sa.Column("strategy_id", sa.String(36), sa.ForeignKey("strategies.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("name", sa.String(100), primary_key=True),
        sa.Column("head_sha", sa.String(40), sa.ForeignKey("commits.sha"), nullable=False),
        sa.Column("protected", sa.Boolean, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "tags",
        sa.Column("strategy_id", sa.String(36), sa.ForeignKey("strategies.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("name", sa.String(100), primary_key=True),
        sa.Column("target_sha", sa.String(40), sa.ForeignKey("commits.sha"), nullable=False),
        sa.Column("message", sa.Text),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "deployments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("strategy_id", sa.String(36), sa.ForeignKey("strategies.id"), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("commit_sha", sa.String(40), sa.ForeignKey("commits.sha"), nullable=False),
        sa.Column("deployed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("deployed_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("reverted_at", sa.DateTime),
        sa.Column("reason", sa.Text),
        sa.CheckConstraint("environment in ('paper','live')", name="ck_deployment_env"),
    )


def downgrade() -> None:
    for t in ["deployments", "tags", "branches", "commit_files", "commits",
              "strategies", "audit_logs", "google_accounts", "users"]:
        op.drop_table(t)
