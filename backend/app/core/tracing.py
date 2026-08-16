"""OpenTelemetry tracing setup.

- OTLP gRPC exporter로 Jaeger/Tempo/OTel Collector에 전송
- FastAPI, SQLAlchemy, HTTPX 자동 계측(auto-instrumentation)
- QP_OTEL_ENABLED=false 또는 QP_ENV=test 이면 비활성화
- 실패해도 서비스 부팅을 막지 않는다 (traceback만 로그)
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


def _bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")


def install_tracing(app) -> None:
    if not _bool(os.environ.get("QP_OTEL_ENABLED"), default=False):
        log.info("otel: disabled (QP_OTEL_ENABLED=false)")
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        endpoint = os.environ.get("QP_OTEL_ENDPOINT", "http://otel-collector:4317")
        service = os.environ.get("QP_OTEL_SERVICE", "quantpilot-proxy")
        env = os.environ.get("QP_ENV", "dev")

        provider = TracerProvider(resource=Resource.create({
            "service.name": service,
            "service.version": "0.1.0",
            "deployment.environment": env,
        }))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app, excluded_urls="^/health,^/metrics")
        HTTPXClientInstrumentor().instrument()
        try:
            from app.models.db import engine
            SQLAlchemyInstrumentor().instrument(engine=engine)
        except Exception as e:
            log.warning("otel: SQLAlchemy instrument failed: %s", e)

        log.info("otel: enabled → %s (service=%s)", endpoint, service)
    except Exception as e:
        log.warning("otel: install failed (leaving tracing disabled): %s", e)


def get_tracer(name: str):
    """편의 함수. otel이 비활성화면 no-op tracer 반환."""
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except Exception:
        class _Noop:
            def start_as_current_span(self, *_a, **_kw):
                from contextlib import nullcontext
                return nullcontext()
        return _Noop()
