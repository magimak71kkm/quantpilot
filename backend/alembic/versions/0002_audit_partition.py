"""audit_logs 파티션 전환 + 90일 아카이브 함수 (PostgreSQL 전용).

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-15
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels = None
depends_on = None


PG_UPGRADE = """
ALTER TABLE audit_logs RENAME TO audit_logs__legacy;

CREATE TABLE audit_logs (
    id           BIGSERIAL,
    user_id      UUID,
    endpoint     TEXT NOT NULL,
    status       INT  NOT NULL,
    duration_ms  INT DEFAULT 0,
    ip           INET,
    payload_hash TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE INDEX audit_logs_user_created  ON audit_logs (user_id, created_at DESC);
CREATE INDEX audit_logs_endpoint_time ON audit_logs (endpoint, created_at DESC);
CREATE INDEX audit_logs_status_err    ON audit_logs (status) WHERE status >= 400;

CREATE TABLE audit_logs_2026_06 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE audit_logs_2026_07 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE audit_logs_2026_08 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE audit_logs_2026_09 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE audit_logs_default PARTITION OF audit_logs DEFAULT;

INSERT INTO audit_logs (id, user_id, endpoint, status, duration_ms, ip, payload_hash, created_at)
SELECT id, user_id::uuid, endpoint, status, duration_ms, ip::inet, payload_hash, created_at
FROM audit_logs__legacy;

CREATE SCHEMA IF NOT EXISTS archive;

CREATE OR REPLACE FUNCTION archive.audit_prune_90d() RETURNS int AS $$
DECLARE part RECORD; moved INT := 0;
BEGIN
    FOR part IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_inherits i ON i.inhrelid = c.oid
        JOIN pg_class p ON p.oid = i.inhparent
        WHERE p.relname = 'audit_logs'
          AND c.relname ~ '^audit_logs_\\d{4}_\\d{2}$'
          AND to_date(substring(c.relname from 12), 'YYYY_MM') < (CURRENT_DATE - INTERVAL '90 days')
    LOOP
        EXECUTE format('ALTER TABLE audit_logs DETACH PARTITION %I', part.relname);
        EXECUTE format('ALTER TABLE %I SET SCHEMA archive',       part.relname);
        moved := moved + 1;
    END LOOP;
    RETURN moved;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.audit_next_partition() RETURNS void AS $$
DECLARE
    nxt DATE := date_trunc('month', now())::date + INTERVAL '1 month';
    part_name TEXT := 'audit_logs_' || to_char(nxt, 'YYYY_MM');
BEGIN
    EXECUTE format(
      'CREATE TABLE IF NOT EXISTS %I PARTITION OF audit_logs FOR VALUES FROM (%L) TO (%L)',
      part_name, nxt, (nxt + INTERVAL '1 month')::date
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE audit_logs IS 'API 감사 로그 (월 파티션, 90일 후 archive 스키마로 이관)';
"""

PG_DOWNGRADE = """
DROP FUNCTION IF EXISTS public.audit_next_partition();
DROP FUNCTION IF EXISTS archive.audit_prune_90d();
DROP TABLE IF EXISTS audit_logs CASCADE;
ALTER TABLE audit_logs__legacy RENAME TO audit_logs;
"""


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgres():
        op.execute(PG_UPGRADE)
    else:
        # SQLite/dev — no partitioning support, keep legacy table intact
        pass


def downgrade() -> None:
    if _is_postgres():
        op.execute(PG_DOWNGRADE)
