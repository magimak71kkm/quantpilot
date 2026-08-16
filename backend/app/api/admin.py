"""/admin/* — 관리자 전용 API.

- `/admin/audit` : audit_logs 조회 (필터: user_id / endpoint / status / from / to / 페이지네이션).
- `/admin/audit/summary` : 최근 24h 요약 통계.

권한: current_user에 `is_admin=True` 컬럼이 필요하나, 스켈레톤 단계에서는
`ADMIN_USER_IDS` 환경변수(또는 dev 모드) 화이트리스트로 대신한다.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import current_user_id, get_db
from app.models import orm

router = APIRouter()


def _require_admin(uid: str) -> None:
    allow = set(x.strip() for x in os.environ.get("QP_ADMIN_USER_IDS", "").split(",") if x.strip())
    if settings.env == "dev" or uid in allow:
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "admin only")


@router.get("/audit")
def list_audit(
    uid: str = Depends(current_user_id),
    db: Session = Depends(get_db),
    user_id: Optional[str] = Query(None),
    endpoint: Optional[str] = Query(None, description="부분 일치 검색"),
    status_code: Optional[int] = Query(None),
    from_: Optional[str] = Query(None, alias="from", description="ISO datetime"),
    to: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    _require_admin(uid)
    q = db.query(orm.AuditLog)
    if user_id:
        q = q.filter(orm.AuditLog.user_id == user_id)
    if endpoint:
        q = q.filter(orm.AuditLog.endpoint.contains(endpoint))
    if status_code is not None:
        q = q.filter(orm.AuditLog.status == status_code)
    if from_:
        q = q.filter(orm.AuditLog.created_at >= datetime.fromisoformat(from_))
    if to:
        q = q.filter(orm.AuditLog.created_at <= datetime.fromisoformat(to))

    total = q.count()
    rows = (q.order_by(orm.AuditLog.id.desc())
              .offset(offset).limit(limit).all())
    return {
        "total": total, "offset": offset, "limit": limit,
        "rows": [
            {
                "id": r.id, "user_id": r.user_id, "endpoint": r.endpoint,
                "status": r.status, "duration_ms": r.duration_ms, "ip": r.ip,
                "payload_hash": r.payload_hash,
                "created_at": r.created_at.isoformat(),
            } for r in rows
        ],
    }


@router.get("/audit/summary")
def summary(
    uid: str = Depends(current_user_id),
    db: Session = Depends(get_db),
    hours: int = Query(24, ge=1, le=168),
):
    _require_admin(uid)
    since = datetime.utcnow() - timedelta(hours=hours)
    base = db.query(orm.AuditLog).filter(orm.AuditLog.created_at >= since)
    total = base.count()
    err = base.filter(orm.AuditLog.status >= 400).count()
    p50, p95 = 0, 0
    durs = sorted(d[0] for d in base.with_entities(orm.AuditLog.duration_ms).all() if d[0] is not None)
    if durs:
        p50 = durs[len(durs) // 2]
        p95 = durs[max(0, int(len(durs) * 0.95) - 1)]
    by_endpoint = (
        base.with_entities(orm.AuditLog.endpoint, func.count(orm.AuditLog.id))
            .group_by(orm.AuditLog.endpoint)
            .order_by(func.count(orm.AuditLog.id).desc())
            .limit(10).all()
    )
    return {
        "window_hours": hours,
        "total": total, "errors": err,
        "error_rate": round((err / total) if total else 0.0, 4),
        "p50_ms": p50, "p95_ms": p95,
        "top_endpoints": [{"endpoint": e, "count": c} for e, c in by_endpoint],
    }
