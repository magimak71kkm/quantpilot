# Grafana / Prometheus Alerting

## 규칙 요약 (3종 + 보조 2종)

| Alert | 임계값 | 유지 시간 | severity | 채널 |
|---|---|---|---|---|
| `QuantPilotHigh5xxRate` | 5xx > 5% | 5m | critical | Slack #critical + Email |
| `QuantPilotElevated5xxRate` | 5xx > 1% | 10m | warning | Slack #alerts |
| `QuantPilotLatencyP95High` | p95 > 2s | 5m | warning | Slack #alerts |
| `QuantPilotLatencyP95Severe` | p95 > 5s | 3m | critical | Slack #critical + Email |
| `QuantPilotAISchemaFailSpike` | AI schema_fail 10m > 20건 | 1m | warning | Slack #ai |
| `QuantPilotAISchemaFailBurst` | AI schema_fail 5m > 50건 | 30s | critical | Slack #critical + Email + #ai |
| `QuantPilotInFlightHigh` | in-flight > 100 | 2m | warning | Slack #alerts |

## Prometheus 로드
```yaml
# deploy/grafana/prometheus.yml 에 추가
rule_files:
  - "/etc/prometheus/alert_rules.yml"
alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]
```
docker-compose 확장:
```yaml
alertmanager:
  image: prom/alertmanager:v0.27.0
  volumes:
    - ../alerting/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
  secrets:
    - slack_webhook_default
    - slack_webhook_critical
    - slack_webhook_ai
    - smtp_password
```

## 시크릿
`docker compose` v3.9 `secrets:` 또는 Vault Agent Injector로 다음 파일을 주입:
- `/run/secrets/slack_webhook_default` — Slack Incoming Webhook URL
- `/run/secrets/slack_webhook_critical` — critical 채널 웹훅
- `/run/secrets/slack_webhook_ai` — AI 채널 웹훅
- `/run/secrets/smtp_password` — SMTP AUTH 비밀번호

## 테스트
Prometheus UI(`/alerts`)에서 pending → firing 상태 확인. `amtool` 사용:
```bash
amtool check-config deploy/alerting/alertmanager.yml
amtool alert add alertname=QuantPilotHigh5xxRate severity=critical
```
