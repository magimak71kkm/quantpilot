# Grafana 자동 프로비저닝

Grafana 컨테이너를 재기동하면 다음이 자동 설정됩니다.

| 항목 | 파일 | 마운트 |
|---|---|---|
| Prometheus 데이터소스 | `provisioning/datasources/prometheus.yml` | `/etc/grafana/provisioning/datasources/` |
| 대시보드 프로바이더 | `provisioning/dashboards/dashboards.yml` | `/etc/grafana/provisioning/dashboards/` |
| Latency JSON | `dashboard_latency.json` | `/var/lib/grafana/dashboards/latency.json` |
| Rate JSON | `dashboard_rate.json` | `/var/lib/grafana/dashboards/rate.json` |
| Errors JSON | `dashboard_errors.json` | `/var/lib/grafana/dashboards/errors.json` |
| SLO (30d) JSON | `dashboard_slo.json` | `/var/lib/grafana/dashboards/slo.json` |

## 실행
```bash
cd deploy
docker compose \
  -f docker-compose.yml \
  -f docker-compose.observability.yml up -d
open http://localhost:3000    # admin / admin
```
- 데이터소스: **Prometheus** (default, `http://prometheus:9090`, 15s interval, POST)
- 폴더: **QuantPilot** 아래 4개 대시보드 자동 로드
- `allowUiUpdates: false` 로 프로비저닝 파일이 유일한 진실 소스가 됩니다 (UI 편집 후 저장 불가 → PR로 관리).

## 갱신
- `updateIntervalSeconds: 30` 이므로 대시보드 JSON 편집 → 30초 이내 반영.
- Prometheus rule 리로드: `curl -X POST http://localhost:9090/-/reload`

## 트러블슈팅
| 증상 | 원인/조치 |
|---|---|
| 대시보드 미표시 | `grafana` 컨테이너 로그에서 `Dashboards Provisioning` 오류 확인 |
| Prometheus 연결 실패 | `docker network` 확인, `url: http://prometheus:9090` 이어야 함 |
| Alerting 규칙 미로드 | `docker compose exec prometheus promtool check rules /etc/prometheus/alert_rules.yml` |
