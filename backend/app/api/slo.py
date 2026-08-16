"""/dashboard/slo — 30일 SLO 계산·전시 API.

registry 스냅샷만으로는 30일 window 계산이 불가하므로 audit_logs를 기반으로
- availability = 1 - (5xx / total)  (30일)
- latency_p95_ms = duration_ms 90/95/99 백분위 (30일)
- ai_schema_fail_rate = /ai/* 요청 중 422 응답 비율 (근사, 30일)
- error_budget_burn = 1h/6h 창의 5xx 비율 / 목표(0.1%)
를 산출한다.  audit_logs 파티션 인덱스(user_id, created_at)와 (endpoint, created_at)를
활용해 30일 스캔이 index-only로 처리된다.

목표(SLO Targets)는 상수로 정의하되, 향후 config로 뺄 수 있게 한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import current_user_id, get_db
from app.models import orm

router = APIRouter()

_DEFAULT_TARGETS = {
    "availability_pct":     99.9,
    "latency_p95_ms":       2000,
    "ai_schema_fail_pct":   5.0,
    "burn_rate_target":     0.001,   # 0.1% 목표 (에러 예산 정의)
}


def _load_targets(db: Session) -> dict:
    """slo_policies 테이블이 비었으면 기본값 사용."""
    p = db.query(orm.SLOPolicy).filter_by(name="default").one_or_none()
    if not p:
        return dict(_DEFAULT_TARGETS)
    return {
        "availability_pct":   p.availability_pct,
        "latency_p95_ms":     p.latency_p95_ms,
        "ai_schema_fail_pct": p.ai_schema_fail_pct,
        "burn_rate_target":   p.burn_rate_target,
    }


def _percentile(values: list[int], q: float) -> int:
    if not values:
        return 0
    values = sorted(values)
    idx = max(0, min(len(values) - 1, int(len(values) * q) - 1))
    return values[idx]


def _burn(db: Session, hours: int, target: float) -> float:
    since = datetime.utcnow() - timedelta(hours=hours)
    total = db.query(func.count(orm.AuditLog.id)).filter(orm.AuditLog.created_at >= since).scalar() or 0
    err   = db.query(func.count(orm.AuditLog.id)).filter(
                orm.AuditLog.created_at >= since,
                orm.AuditLog.status >= 500).scalar() or 0
    rate = (err / total) if total else 0.0
    return round(rate / target, 3) if target else 0.0


def _grade(pct: float, warn: float, crit: float, higher_is_better: bool = True) -> str:
    """3단 등급: ok / warn / crit."""
    if higher_is_better:
        return "ok" if pct >= warn else ("warn" if pct >= crit else "crit")
    return "ok" if pct <= warn else ("warn" if pct <= crit else "crit")


@router.get("/slo")
def slo_summary(uid: str = Depends(current_user_id), db: Session = Depends(get_db)):
    targets = _load_targets(db)
    since = datetime.utcnow() - timedelta(days=30)
    q = db.query(orm.AuditLog).filter(orm.AuditLog.created_at >= since)

    total = q.count()
    err_5xx = q.filter(orm.AuditLog.status >= 500).count()
    availability = (1 - (err_5xx / total)) * 100 if total else 100.0

    durs = [d[0] for d in q.with_entities(orm.AuditLog.duration_ms).all() if d[0] is not None]
    p95 = _percentile(durs, 0.95)
    p99 = _percentile(durs, 0.99)

    ai_q = q.filter(orm.AuditLog.endpoint.contains("/ai/"))
    ai_total = ai_q.count()
    ai_fail  = ai_q.filter(orm.AuditLog.status == 422).count()
    ai_fail_pct = (ai_fail / ai_total * 100) if ai_total else 0.0

    return {
        "window_days": 30,
        "computed_at": datetime.utcnow().isoformat() + "Z",
        "targets": targets,
        "availability": {
            "value_pct": round(availability, 4),
            "target_pct": targets["availability_pct"],
            "grade": _grade(availability, targets["availability_pct"], 99.0, higher_is_better=True),
            "requests": total, "errors_5xx": err_5xx,
        },
        "latency": {
            "p95_ms": p95, "p99_ms": p99,
            "target_p95_ms": targets["latency_p95_ms"],
            "grade": _grade(p95, targets["latency_p95_ms"], 4500, higher_is_better=False),
            "samples": len(durs),
        },
        "ai_quality": {
            "schema_fail_pct": round(ai_fail_pct, 3),
            "target_pct": targets["ai_schema_fail_pct"],
            "grade": _grade(ai_fail_pct, targets["ai_schema_fail_pct"], 10.0, higher_is_better=False),
            "ai_requests": ai_total, "schema_fails": ai_fail,
        },
        "burn_rate": {
            "1h": _burn(db, 1, targets["burn_rate_target"]),
            "6h": _burn(db, 6, targets["burn_rate_target"]),
            "24h": _burn(db, 24, targets["burn_rate_target"]),
            "target_multiple": 1.0,   # 1.0 이상이면 예산 초과 속도
        },
    }
