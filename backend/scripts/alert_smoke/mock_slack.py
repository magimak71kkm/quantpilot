#!/usr/bin/env python3
"""Alertmanager Slack Webhook 시뮬레이터.

역할:
- Alertmanager가 슬랙 웹훅을 POST하면 payload를 화면과 JSONL 파일에 기록.
- 로컬 통합 테스트에서 실제 Slack 없이 알림 라우팅을 검증할 때 사용.
- 3개 엔드포인트로 분기하여 채널별 라우팅(default / critical / ai)이 정상인지 구분.

사용:
    python3 mock_slack.py --port 5001 --out ./received.jsonl
    # → Alertmanager 설정에서 api_url_file 대신 다음 URL 사용
    #   http://mock-slack:5001/default
    #   http://mock-slack:5001/critical
    #   http://mock-slack:5001/ai
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    log_path: str = "/tmp/mock_slack.jsonl"

    def _channel(self) -> str:
        return self.path.strip("/") or "default"

    def do_POST(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n) if n else b""
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            payload = {"raw": raw.decode("utf-8", "replace")}

        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "channel": self._channel(),
            "payload": payload,
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        alerts = payload.get("alerts") or payload.get("Alerts") or []
        names = [a.get("labels", {}).get("alertname", "?") for a in alerts] \
                if isinstance(alerts, list) else []
        print(f"[mock-slack] {entry['ts']} ch={entry['channel']} "
              f"status={payload.get('status', '?')} alerts={names}",
              flush=True)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, fmt: str, *args) -> None:  # silence default access log
        return


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5001)
    ap.add_argument("--out", default="/tmp/mock_slack.jsonl")
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()

    Handler.log_path = args.out
    # 초기화(이전 실행 결과 유지하지 않음)
    open(args.out, "w").close()

    srv = HTTPServer((args.host, args.port), Handler)
    print(f"[mock-slack] listening on {args.host}:{args.port} → {args.out}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
