"""/policy/slo — SLO 목표(정책) 외부화 및 변경 이력 API.

- 기본 정책 `default` 을 첫 조회 시 자동 생성한다.
- PUT 은 활성 정책의 SLO 값을 갱신하되, 이전값을 slo_policy_history 에 스냅샷으로 저장한다.
- 관리자만 변경 가능(dev 모드는 자동 허용).
"""
from __future__ import annotations

import os
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.services.notify import format_policy_change, send_slack

from app.core.config import settings
from app.core.deps import current_user_id, get_db
from app.models import orm

router = APIRouter()

DEFAULTS = {
    "availability_pct":     99.9,
    "latency_p95_ms":       2000,
    "ai_schema_fail_pct":   5.0,
    "burn_rate_target":     0.001,
}


def _require_admin(uid: str) -> None:
    allow = set(x.strip() for x in os.environ.get("QP_ADMIN_USER_IDS", "").split(",") if x.strip())
    if settings.env == "dev" or uid in allow:
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "admin only")


def _ensure_default(db: Session) -> orm.SLOPolicy:
    p = db.query(orm.SLOPolicy).filter_by(name="default").one_or_none()
    if p:
        return p
    p = orm.SLOPolicy(name="default", **DEFAULTS)
    db.add(p); db.commit(); db.refresh(p)
    return p


def _to_dict(p: orm.SLOPolicy) -> dict:
    return {
        "id": p.id, "name": p.name, "active": p.active,
        "availability_pct":   p.availability_pct,
        "latency_p95_ms":     p.latency_p95_ms,
        "ai_schema_fail_pct": p.ai_schema_fail_pct,
        "burn_rate_target":   p.burn_rate_target,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


class SLOUpdate(BaseModel):
    availability_pct:   float | None = Field(None, ge=90.0, le=100.0)
    latency_p95_ms:     int   | None = Field(None, ge=100, le=60000)
    ai_schema_fail_pct: float | None = Field(None, ge=0.0, le=50.0)
    burn_rate_target:   float | None = Field(None, gt=0.0,  le=0.1)
    reason:             str   | None = Field(None, min_length=10, max_length=500)


@router.get("/slo")
def get_policy(uid: str = Depends(current_user_id), db: Session = Depends(get_db)):
    return _to_dict(_ensure_default(db))


@router.put("/slo")
def update_policy(body: SLOUpdate,
                  bg: BackgroundTasks,
                  uid: str = Depends(current_user_id),
                  db: Session = Depends(get_db)):
    _require_admin(uid)
    p = _ensure_default(db)
    prev = _to_dict(p)

    changed = False
    for k in ("availability_pct", "latency_p95_ms", "ai_schema_fail_pct", "burn_rate_target"):
        v = getattr(body, k)
        if v is not None and getattr(p, k) != v:
            setattr(p, k, v)
            changed = True
    if not changed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no fields to update")
    p.updated_at = datetime.utcnow()

    next_ = _to_dict(p)
    db.add(orm.SLOPolicyHistory(
        policy_id=p.id, changed_by=uid,
        prev_json=prev, next_json=next_,
        reason=body.reason,
    ))
    db.commit(); db.refresh(p)

    # 사후 Slack 알림 — 사용자 응답에 지연/실패를 전파하지 않는다
    payload = format_policy_change(prev=prev, next_=next_, changed_by=uid, reason=body.reason or "")
    bg.add_task(send_slack, payload)
    return _to_dict(p)


@router.get("/slo/history")
def list_history(uid: str = Depends(current_user_id), db: Session = Depends(get_db),
                 limit: int = 50):
    _require_admin(uid)
    p = _ensure_default(db)
    rows = (db.query(orm.SLOPolicyHistory)
              .filter_by(policy_id=p.id)
              .order_by(orm.SLOPolicyHistory.id.desc())
              .limit(max(1, min(500, limit))).all())
    return {
        "policy_id": p.id, "total": len(rows),
        "rows": [
            {"id": r.id, "changed_by": r.changed_by, "prev": r.prev_json, "next": r.next_json,
             "reason": r.reason, "created_at": r.created_at.isoformat()}
            for r in rows
        ],
    }
