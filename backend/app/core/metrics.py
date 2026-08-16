"""Prometheus metrics middleware + /metrics endpoint.

Exposes 4 metrics:
  - qp_http_requests_total{method,path_template,status}
  - qp_http_request_duration_seconds{method,path_template}  (Histogram)
  - qp_http_in_flight  (Gauge)
  - qp_ai_calls_total{kind,outcome}                          (AI 성공/실패 카운터)

path_template은 FastAPI 라우트 패턴(예: /versions/strategies/{sid}/commits)을 사용해
카디널리티 폭발을 방지한다.
"""
from __future__ import annotations

import time
from typing import Callable

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.routing import Match
from starlette.types import ASGIApp


REGISTRY = CollectorRegistry()

REQ_COUNT = Counter(
    "qp_http_requests_total",
    "HTTP requests handled by the proxy.",
    ["method", "path_template", "status"],
    registry=REGISTRY,
)
REQ_LATENCY = Histogram(
    "qp_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path_template"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
    registry=REGISTRY,
)
IN_FLIGHT = Gauge(
    "qp_http_in_flight",
    "Number of in-flight HTTP requests.",
    registry=REGISTRY,
)
AI_CALLS = Counter(
    "qp_ai_calls_total",
    "AI calls issued by the proxy.",
    ["kind", "outcome"],
    registry=REGISTRY,
)


def _resolve_template(request: Request) -> str:
    """Match request against FastAPI routes to obtain the pattern, not the concrete path."""
    try:
        for route in request.app.router.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                return getattr(route, "path", request.url.path)
    except Exception:
        pass
    return request.url.path


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # /metrics 자체는 관측 대상에서 제외 (자기 자신 카운트 방지)
        if request.url.path == "/metrics":
            return await call_next(request)

        IN_FLIGHT.inc()
        t0 = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - t0
            IN_FLIGHT.dec()
            tmpl = _resolve_template(request)
            REQ_COUNT.labels(request.method, tmpl, str(status)).inc()
            REQ_LATENCY.labels(request.method, tmpl).observe(elapsed)


def metrics_endpoint() -> Response:
    payload = generate_latest(REGISTRY)
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
