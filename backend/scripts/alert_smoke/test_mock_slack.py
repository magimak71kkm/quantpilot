"""mock_slack 자기 테스트 — 실제 서버를 띄우고 POST 왕복 확인."""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from http.server import HTTPServer

from scripts.alert_smoke.mock_slack import Handler


def _free_port() -> int:
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close(); return p


def test_mock_slack_records_payload(tmp_path):
    log = tmp_path / "recv.jsonl"
    Handler.log_path = str(log)
    open(log, "w").close()

    port = _free_port()
    srv = HTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    try:
        body = json.dumps({
            "status": "firing",
            "alerts": [
                {"labels": {"alertname": "QuantPilotHigh5xxRate", "severity": "critical"}},
                {"labels": {"alertname": "QuantPilotAISchemaFailBurst",
                            "severity": "critical", "component": "ai"}},
            ],
        }).encode()

        for ch in ("default", "critical", "ai"):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/{ch}", data=body,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=3) as r:
                assert r.status == 200

        # 파일에 3줄 기록되었는지 확인
        time.sleep(0.05)
        lines = log.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
        entries = [json.loads(x) for x in lines]
        channels = sorted(e["channel"] for e in entries)
        assert channels == ["ai", "critical", "default"]
        names_first = [
            a["labels"]["alertname"] for a in entries[0]["payload"]["alerts"]
        ]
        assert "QuantPilotHigh5xxRate" in names_first
    finally:
        srv.shutdown(); srv.server_close()
