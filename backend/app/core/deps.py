"""FastAPI dependencies: DB session, current user, simple rate-limit."""
from typing import Generator, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.models.db import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _decode_authorization(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        return decode_token(token)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")


def current_user_id(authorization: Optional[str] = Header(default=None)) -> str:
    payload = _decode_authorization(authorization)
    from app.core.config import settings
    if settings.env == "prod" and not payload.get("twofa_ok", False):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "2fa verification required")
    return payload["sub"]


def pending_user_id(authorization: Optional[str] = Header(default=None)) -> str:
    payload = _decode_authorization(authorization)
    if payload.get("twofa_ok") is not False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "pending 2fa token required")
    return payload["sub"]


# ---- Redis-backed token bucket with a dev/test fallback. --------------------
_BUCKETS: dict[str, tuple[float, float]] = {}


def _redis_client():
    from app.core.config import settings
    if settings.env in {"dev", "test"}:
        return None
    try:
        import redis
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


def rate_limit(key: str, rate_per_min: int) -> bool:
    import time
    client = _redis_client()
    if client is not None:
        bucket = f"quantpilot:rate:{key}"
        try:
            count = client.incr(bucket)
            if count == 1:
                client.expire(bucket, 60)
            return count <= rate_per_min
        except Exception:
            pass
    from app.core.config import settings
    if settings.env == "prod":
        return False
    now = time.time()
    tokens, last = _BUCKETS.get(key, (float(rate_per_min), now))
    tokens = min(rate_per_min, tokens + (now - last) * rate_per_min / 60.0)
    if tokens < 1.0:
        _BUCKETS[key] = (tokens, now)
        return False
    _BUCKETS[key] = (tokens - 1.0, now)
    return True


def require_rate(request: Request, uid: str = Depends(current_user_id)):
    from app.core.config import settings
    if not rate_limit("u:" + uid, settings.rate_per_user_per_min):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "user rate limit exceeded")
    ip = request.client.host if request.client else "0.0.0.0"
    if not rate_limit("ip:" + ip, settings.rate_per_ip_per_min):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "ip rate limit exceeded")
    return uid
