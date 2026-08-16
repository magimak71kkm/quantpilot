"""Slack 웹훅 알림 서비스.

- 정책 변경 등 사후 이벤트를 Slack Incoming Webhook에 비동기 발송한다.
- QP_SLACK_WEBHOOK_URL 이 비어 있으면 no-op (dev 기본).
- 실패해도 호출자를 절대 방해하지 않는다. 결과는 반환값(dict)로 전달.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 5.0


def _webhook_url() -> str:
    return os.environ.get("QP_SLACK_WEBHOOK_URL", "").strip()


def _fmt_field(label: str, val: Any) -> dict:
    return {"title": label, "value": str(val), "short": True}


def format_policy_change(prev: dict, next_: dict, changed_by: str, reason: str) -> dict:
    """정책 변경 payload — Slack attachments 형식."""
    keys = ("availability_pct", "latency_p95_ms", "ai_schema_fail_pct", "burn_rate_target")
    diffs = [f"{k}: {prev.get(k)} → {next_.get(k)}" for k in keys if prev.get(k) != next_.get(k)]
    color = "#ffb84d" if diffs else "#8f9dbb"
    return {
        "text": "⚙️ QuantPilot SLO 정책 변경",
        "attachments": [{
            "color": color,
            "fields": [
                _fmt_field("변경자", changed_by[:8] + "…" if len(changed_by) > 8 else changed_by),
                _fmt_field("정책", next_.get("name", "default")),
                {"title": "변경 요약", "value": "\n".join(f"• {d}" for d in diffs) or "(변화 없음)", "short": False},
                {"title": "사유", "value": reason or "(사유 없음)", "short": False},
            ],
            "footer": "quantpilot-proxy",
            "ts": int(time.time()),
        }],
    }


def send_slack(payload: dict, url: str | None = None) -> dict:
    """Sync HTTP POST (백엔드 라우터에서 fire-and-forget 태스크로 감싸 사용)."""
    target = (url or _webhook_url())
    if not target:
        return {"sent": False, "reason": "no-webhook-url"}
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as c:
            r = c.post(target, json=payload)
            return {"sent": r.status_code < 400, "status": r.status_code, "body": r.text[:120]}
    except Exception as e:  # noqa: BLE001
        log.warning("slack notify failed: %s", e)
        return {"sent": False, "reason": str(e)}
