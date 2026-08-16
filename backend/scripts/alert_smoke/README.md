# Alertmanager Slack 통합 스모크 테스트

**목적**: Alertmanager의 라우팅 트리(critical/warning/ai)가 실제 Slack 없이도 검증 가능하도록 mock 서버 + 트리거 스크립트 제공.

## 구성
| 파일 | 역할 |
|---|---|
| `mock_slack.py` | HTTP 서버 — POST 페이로드를 채널별로 JSONL에 기록 |
| `alertmanager.smoke.yml` | mock-slack 3개 엔드포인트로 라우팅한 Alertmanager 설정 |
| `docker-compose.smoke.yml` | mock-slack 서비스 오버레이 (5001 포트) |
| `trigger_alerts.sh` | Alertmanager `/api/v2/alerts`에 3건의 알림 fire |
| `test_mock_slack.py` | mock 서버 자기 테스트 (pytest에서 자동 실행) |

## 사용

```bash
cd deploy
docker compose \
  -f docker-compose.yml \
  -f docker-compose.observability.yml \
  -f ../scripts/alert_smoke/docker-compose.smoke.yml up -d

# Alertmanager 설정을 smoke 버전으로 교체 (일회성)
docker cp ../scripts/alert_smoke/alertmanager.smoke.yml \
  qp-alertmanager:/etc/alertmanager/alertmanager.yml
docker restart qp-alertmanager

# 3건의 알림 트리거
bash ../scripts/alert_smoke/trigger_alerts.sh

# 채널별 라우팅 검증
docker exec qp-mock-slack sh -c 'cat /tmp/mock_slack.jsonl' | \
  python3 -c "import json,sys;[print(e['channel'],[a['labels']['alertname'] for a in e['payload']['alerts']]) for e in map(json.loads, sys.stdin)]"
```

기대 출력 예시:
```
critical ['QuantPilotHigh5xxRate']
critical ['QuantPilotAISchemaFailBurst']
default ['QuantPilotLatencyP95High']
ai ['QuantPilotAISchemaFailBurst']
```

## 자동 검증
`pytest -q` 실행 시 `test_mock_slack.py`가 실제로 서버를 띄우고 3개 채널 왕복을 확인합니다.
