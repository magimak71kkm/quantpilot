"""/dashboard/live — S02 실시간 위젯 전용 요약 엔드포인트.

/metrics(Prom text)를 SPA가 직접 파싱하는 대신, 서버에서
Prometheus registry를 조회해 필요한 스칼라만 JSON으로 반환한다.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import current_user_id
from app.core.metrics import (
    AI_CALLS, IN_FLIGHT, REGISTRY, REQ_COUNT, REQ_LATENCY,
)

router = APIRouter()


def _collect() -> dict:
    """Prometheus registry 스냅샷 → 요약 스칼라."""
    total_req = 0
    err_5xx = 0
    err_4xx = 0
    by_path: dict[str, int] = {}
    ai_ok = 0
    ai_fail = 0

    # 카운터 합산
    for metric in REGISTRY.collect():
        if metric.name == "qp_http_requests":
            for sample in metric.samples:
                if sample.name.endswith("_total"):
                    v = sample.value or 0
                    total_req += v
                    st = sample.labels.get("status", "")
                    if st.startswith("5"):
                        err_5xx += v
                    elif st.startswith("4"):
                        err_4xx += v
                    p = sample.labels.get("path_template", "")
                    if p and not p.startswith("/health") and not p.startswith("/metrics"):
                        by_path[p] = by_path.get(p, 0) + v
        elif metric.name == "qp_ai_calls":
            for sample in metric.samples:
                if sample.name.endswith("_total"):
                    out = sample.labels.get("outcome", "")
                    if out == "ok":
                        ai_ok += sample.value or 0
                    elif out == "schema_fail":
                        ai_fail += sample.value or 0

    top = sorted(by_path.items(), key=lambda x: x[1], reverse=True)[:5]

    # in-flight (Gauge)
    in_flight = 0.0
    for metric in REGISTRY.collect():
        if metric.name == "qp_http_in_flight":
            for s in metric.samples:
                in_flight = s.value
                break

    # Histogram → 대략적인 평균 (sum/count) — SPA 표시용
    lat_sum = lat_count = 0.0
    for metric in REGISTRY.collect():
        if metric.name == "qp_http_request_duration_seconds":
            for s in metric.samples:
                if s.name.endswith("_sum"):
                    lat_sum += s.value
                elif s.name.endswith("_count"):
                    lat_count += s.value
    avg_ms = (lat_sum / lat_count * 1000) if lat_count else 0.0

    error_rate = ((err_4xx + err_5xx) / total_req) if total_req else 0.0

    return {
        "in_flight": int(in_flight),
        "total_requests": int(total_req),
        "err_4xx": int(err_4xx),
        "err_5xx": int(err_5xx),
        "error_rate": round(error_rate, 4),
        "avg_latency_ms": round(avg_ms, 1),
        "ai_ok": int(ai_ok),
        "ai_schema_fail": int(ai_fail),
        "top_paths": [{"path": p, "count": int(c)} for p, c in top],
    }


@router.get("/live")
def live_metrics(uid: str = Depends(current_user_id)):
    """SPA S02 대시보드가 5~10초 간격으로 폴링."""
    return _collect()
