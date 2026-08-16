"""slo_policies + policy history tables.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-15
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "slo_policies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column("availability_pct",   sa.Float, nullable=False, server_default="99.9"),
        sa.Column("latency_p95_ms",     sa.Integer, nullable=False, server_default="2000"),
        sa.Column("ai_schema_fail_pct", sa.Float, nullable=False, server_default="5.0"),
        sa.Column("burn_rate_target",   sa.Float, nullable=False, server_default="0.001"),
        sa.Column("active",             sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at",         sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at",         sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "slo_policy_history",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("policy_id", sa.Integer, sa.ForeignKey("slo_policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("changed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("prev_json", sa.JSON),
        sa.Column("next_json", sa.JSON, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_slo_policy_history_policy_time",
                    "slo_policy_history", ["policy_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_slo_policy_history_policy_time", table_name="slo_policy_history")
    op.drop_table("slo_policy_history")
    op.drop_table("slo_policies")
