from app.core.config import settings


def test_ai_daily_quota_returns_429(client, monkeypatch):
    monkeypatch.setattr(settings, "gemini_daily_quota_per_user", 1)
    payload = {"text": "RSI 70 screen"}
    assert client.post("/ai/screener/nl-to-filter", json=payload).status_code == 200
    response = client.post("/ai/screener/nl-to-filter", json=payload)
    assert response.status_code == 429
