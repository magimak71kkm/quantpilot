"""AuditLogMiddleware 통합 테스트."""
from app.models import db as dbmod
from app.models import orm


def test_audit_logged_for_versions(client, user):
    # 감사 대상 경로 호출
    r = client.post("/versions/strategies", json={"name": "AuditProbe"})
    assert r.status_code == 200

    s = dbmod.SessionLocal()
    try:
        rows = s.query(orm.AuditLog).order_by(orm.AuditLog.id.desc()).limit(3).all()
    finally:
        s.close()

    assert any(r_.endpoint.endswith("/versions/strategies") for r_ in rows)
    top = rows[0]
    assert top.status == 200
    assert top.user_id == user.id
    assert len(top.payload_hash) == 64          # SHA-256 hex
    assert top.duration_ms >= 0


def test_audit_skips_untracked(client):
    r = client.get("/health")
    assert r.status_code == 200

    s = dbmod.SessionLocal()
    try:
        last = s.query(orm.AuditLog).order_by(orm.AuditLog.id.desc()).first()
    finally:
        s.close()

    # /health는 감사 대상 아님 — 최근 로그가 없거나 다른 endpoint여야 한다
    assert last is None or "/health" not in (last.endpoint or "")


def test_audit_does_not_break_error_path(client):
    r = client.get("/versions/strategies/does-not-exist/commits")
    assert r.status_code == 404

    s = dbmod.SessionLocal()
    try:
        row = s.query(orm.AuditLog).order_by(orm.AuditLog.id.desc()).first()
    finally:
        s.close()

    assert row is not None
    assert row.status == 404
    assert row.endpoint.startswith("GET /versions/strategies/")
