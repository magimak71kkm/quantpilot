"""Short-lived OAuth state storage backed by Redis in production."""
import json
import time

_MEMORY: dict[str, dict] = {}


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


def save_oauth_state(state: str, value: dict) -> None:
    value = {**value, "ts": time.time()}
    client = _client()
    if client is not None:
        client.setex(f"quantpilot:oauth:{state}", 300, json.dumps(value))
        return
    from app.core.config import settings
    if settings.env == "prod":
        raise RuntimeError("Redis is required for OAuth state in prod")
    _MEMORY[state] = value


def pop_oauth_state(state: str) -> dict | None:
    client = _client()
    if client is not None:
        raw = client.getdel(f"quantpilot:oauth:{state}")
        return json.loads(raw) if raw else None
    from app.core.config import settings
    if settings.env == "prod":
        return None
    value = _MEMORY.pop(state, None)
    if value and time.time() - value["ts"] <= 300:
        return value
    return None
