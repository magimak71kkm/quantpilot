#!/usr/bin/env bash
# Alertmanager 알림 라우팅 스모크 테스트.
#
# 사전:
#   1) mock_slack.py 를 5001 포트로 실행중
#   2) Alertmanager alertmanager.yml에서 api_url_file 대신 다음 URL 사용
#        slack-critical → http://mock-slack:5001/critical
#        slack-warning  → http://mock-slack:5001/default
#        slack-ai       → http://mock-slack:5001/ai
#   3) Alertmanager 접근 URL(기본 http://localhost:9093) 지정
#
# 실행:
#   ./trigger_alerts.sh                       # 기본 시나리오
#   ALERTMANAGER_URL=http://am:9093 ./trigger_alerts.sh
#
# 검증:
#   cat /tmp/mock_slack.jsonl | jq -c '{ch:.channel, names:[.payload.alerts[].labels.alertname]}'
set -euo pipefail
AM=${ALERTMANAGER_URL:-http://localhost:9093}
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
END=$(date -u -d "+3 minutes" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v+3M +%Y-%m-%dT%H:%M:%SZ)

send() {
  local name="$1" sev="$2" comp="${3:-}"
  local labels="\"alertname\":\"$name\",\"severity\":\"$sev\",\"service\":\"quantpilot-proxy\""
  [ -n "$comp" ] && labels="$labels,\"component\":\"$comp\""
  cat <<JSON | curl -sS --fail -H 'Content-Type: application/json' -d @- "$AM/api/v2/alerts" >/dev/null
[{"startsAt":"$NOW","endsAt":"$END","labels":{$labels},
  "annotations":{"summary":"smoke test — $name","description":"triggered by trigger_alerts.sh"}}]
JSON
  echo "→ fired $name ($sev${comp:+, component=$comp})"
}

echo "== critical 5xx =="
send "QuantPilotHigh5xxRate" "critical"
sleep 2
echo "== warning latency =="
send "QuantPilotLatencyP95High" "warning"
sleep 2
echo "== critical AI burst =="
send "QuantPilotAISchemaFailBurst" "critical" "ai"

echo
echo "20초 대기 후 그룹핑 결과 확인…"
sleep 20
echo
echo "-- 최근 mock_slack.jsonl --"
tail -20 /tmp/mock_slack.jsonl || true
