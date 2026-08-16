# Prometheus + Grafana 대시보드

## 스크래핑
- 프록시가 `/metrics`에 4개 메트릭 노출:
  - `qp_http_requests_total{method,path_template,status}`
  - `qp_http_request_duration_seconds{method,path_template}` (Histogram)
  - `qp_http_in_flight` (Gauge)
  - `qp_ai_calls_total{kind,outcome}`
- Prometheus 설정: `deploy/grafana/prometheus.yml` (기본 `proxy:8080` 15초 간격).

## Grafana 대시보드 3종
| 파일 | 목적 | 주요 패널 |
|---|---|---|
| `dashboard_latency.json` | 응답 지연 | p50/p95/p99 전체, path 별 p95, in-flight |
| `dashboard_rate.json` | 트래픽 | 경로별 RPS, AI ok/schema_fail RPS, 24h 총합 |
| `dashboard_errors.json` | 오류율 | 5xx %, path·status별 4xx/5xx, 24h AI 실패 |

## 로컬 스택 확장 예시
`docker compose`에 다음을 추가하면 됩니다.
```yaml
  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes:
      - ../deploy/grafana/prometheus.yml:/etc/prometheus/prometheus.yml:ro
  grafana:
    image: grafana/grafana:11.2.0
    ports: ["3000:3000"]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
    volumes:
      - ../deploy/grafana:/var/lib/grafana/dashboards:ro
```
Grafana UI에서 3개 JSON을 Import → Prometheus 데이터소스(`http://prometheus:9090`) 지정.
