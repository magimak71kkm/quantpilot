-- QuantPilot 감사 로그 90일 파티션 마이그레이션
-- 2026-08-15 · PostgreSQL 12+ 대상
--
-- 목적:
--   1) audit_logs 테이블을 파티션 테이블로 재구성(created_at 기준 월 단위 RANGE)
--   2) 조회 성능(사용자·엔드포인트·시간)을 위한 인덱스
--   3) 90일 이전 파티션은 자동 아카이브(별도 스키마 archive)로 이동
--
-- 실행 순서:
--   BEGIN;  \i 2026_08_15_audit_partition.sql;  COMMIT;
-- 대용량 환경에서는 서비스 점검 창에서 실행하거나 pg_partman 전환을 권장한다.

-- 0) 기존 테이블 백업
ALTER TABLE audit_logs RENAME TO audit_logs__legacy;

-- 1) 파티션 부모 테이블 재생성
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
CREATE INDEX audit_logs_status        ON audit_logs (status)  WHERE status >= 400;

-- 2) 최근 3개월치 파티션 미리 생성
CREATE TABLE audit_logs_2026_06 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE audit_logs_2026_07 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE audit_logs_2026_08 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE audit_logs_2026_09 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');

-- 3) 레거시 데이터 이관 (created_at 범위 벗어난 것은 audit_logs_default로)
CREATE TABLE audit_logs_default PARTITION OF audit_logs DEFAULT;
INSERT INTO audit_logs (id, user_id, endpoint, status, duration_ms, ip, payload_hash, created_at)
SELECT id, user_id::uuid, endpoint, status, duration_ms, ip::inet, payload_hash, created_at
FROM audit_logs__legacy;

-- 4) 90일 이전 아카이브 함수 (매일 03:00 cron 권장)
CREATE SCHEMA IF NOT EXISTS archive;

CREATE OR REPLACE FUNCTION archive.audit_prune_90d() RETURNS int AS $$
DECLARE
    part RECORD;
    moved INT := 0;
BEGIN
    FOR part IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_inherits i ON i.inhrelid = c.oid
        JOIN pg_class p ON p.oid = i.inhparent
        WHERE p.relname = 'audit_logs'
          AND c.relname ~ '^audit_logs_\d{4}_\d{2}$'
          AND to_date(substring(c.relname from 12), 'YYYY_MM')
              < (CURRENT_DATE - INTERVAL '90 days')
    LOOP
        EXECUTE format('ALTER TABLE audit_logs DETACH PARTITION %I', part.relname);
        EXECUTE format('ALTER TABLE %I SET SCHEMA archive',       part.relname);
        moved := moved + 1;
    END LOOP;
    RETURN moved;
END;
$$ LANGUAGE plpgsql;

-- 5) 다음 달 파티션 자동 생성 함수 (매월 25일 cron 권장)
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

-- 6) 정리
-- DROP TABLE audit_logs__legacy;   -- 이관 검증 후 수동으로 제거
COMMENT ON TABLE audit_logs IS 'API 감사 로그(월 파티션, 90일 후 archive 스키마 이관)';
