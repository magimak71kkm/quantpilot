"""Audit log middleware.

- 모든 /google/*, /ai/*, /versions/* 요청을 audit_logs 테이블에 기록한다.
- 페이로드 원문은 저장하지 않고 SHA-256 해시만 남긴다(PII/키 노출 방지).
- DB 쓰기 실패는 요청 처리에 영향을 주지 않도록 예외를 삼킨다(감사 실패로 서비스 중단 방지).
- 소요 시간(ms)과 응답 상태를 함께 저장한다.
"""
from __future__ import annotations

import hashlib
import time
from typing import Iterable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from app.core.security import decode_token
from app.models import orm
from app.models.db import SessionLocal


DEFAULT_PATH_PREFIXES = ("/google/", "/ai/", "/versions/", "/admin/", "/policy/")


def _payload_hash(body: bytes) -> str:
    if not body:
        return ""
    return hashlib.sha256(body).hexdigest()


def _extract_uid(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    try:
        return decode_token(auth.split(" ", 1)[1]).get("sub")
    except Exception:
        return None


class AuditLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, prefixes: Iterable[str] = DEFAULT_PATH_PREFIXES) -> None:
        super().__init__(app)
        self.prefixes = tuple(prefixes)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        tracked = any(path.startswith(p) for p in self.prefixes)
        if not tracked:
            return await call_next(request)

        # body를 한 번만 읽고 다운스트림에서 다시 사용할 수 있도록 재사용 스트림 구성
        body = await request.body()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}
        request._receive = receive  # type: ignore[attr-defined]

        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            try:
                s = SessionLocal()
                try:
                    s.add(orm.AuditLog(
                        user_id=_extract_uid(request),
                        endpoint=f"{request.method} {path}",
                        status=status,
                        duration_ms=duration_ms,
                        ip=(request.client.host if request.client else "")[:64],
                        payload_hash=_payload_hash(body)[:64],
                    ))
                    s.commit()
                finally:
                    s.close()
            except Exception:
                # 감사 실패는 절대로 사용자 응답을 방해하지 않는다
                pass
