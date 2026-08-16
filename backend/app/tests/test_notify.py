"""notify.format_policy_change + send_slack no-op 경로 검증."""
import os

from app.services.notify import format_policy_change, send_slack


def test_format_policy_change_diff_only():
    prev = {"name": "default", "availability_pct": 99.9, "latency_p95_ms": 2000,
            "ai_schema_fail_pct": 5.0, "burn_rate_target": 0.001}
    next_ = dict(prev, availability_pct=99.5, latency_p95_ms=1500)
    p = format_policy_change(prev, next_, changed_by="a" * 36, reason="예산 재분배")
    assert p["text"].startswith("⚙️")
    fields = p["attachments"][0]["fields"]
    summary = [f for f in fields if f["title"] == "변경 요약"][0]["value"]
    assert "availability_pct: 99.9 → 99.5" in summary
    assert "latency_p95_ms: 2000 → 1500" in summary
    reason_field = [f for f in fields if f["title"] == "사유"][0]["value"]
    assert reason_field == "예산 재분배"


def test_send_slack_noop_when_webhook_missing(monkeypatch):
    monkeypatch.delenv("QP_SLACK_WEBHOOK_URL", raising=False)
    r = send_slack({"text": "hi"})
    assert r["sent"] is False
    assert r["reason"] == "no-webhook-url"


def test_policy_update_triggers_background_task(client, monkeypatch):
    calls = []

    def fake_send(payload, url=None):
        calls.append(payload)
        return {"sent": True, "status": 200}

    monkeypatch.setattr("app.api.policy.send_slack", fake_send)
    r = client.put("/policy/slo", json={
        "availability_pct": 99.7,
        "reason": "국내 브로커 SLA 반영",
    })
    assert r.status_code == 200
    # BackgroundTasks는 TestClient에서 응답 전송 직후 동기 실행됨
    assert len(calls) == 1
    fields = calls[0]["attachments"][0]["fields"]
    summary = [f for f in fields if f["title"] == "변경 요약"][0]["value"]
    assert "99.9" in summary and "99.7" in summary
