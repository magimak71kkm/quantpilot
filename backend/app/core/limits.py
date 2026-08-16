"""Distributed usage limits for AI calls."""
import time

_MEMORY: dict[str, tuple[int, str]] = {}


class QuotaExceeded(Exception):
    pass


def _client():
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


def consume_ai_quota(user_id: str) -> None:
    from app.core.config import settings
    limit = settings.gemini_daily_quota_per_user
    day = time.strftime("%Y-%m-%d", time.gmtime())
    key = f"quantpilot:ai-quota:{day}:{user_id}"
    client = _client()
    if client is not None:
        count = client.incr(key)
        if count == 1:
            client.expire(key, 172800)
        if count > limit:
            raise QuotaExceeded("daily AI quota exceeded")
        return
    if settings.env == "prod":
        raise RuntimeError("Redis is required for AI quota in prod")
    count, stored_day = _MEMORY.get(user_id, (0, day))
    if stored_day != day:
        count = 0
    if count >= limit:
        raise QuotaExceeded("daily AI quota exceeded")
    _MEMORY[user_id] = (count + 1, day)
