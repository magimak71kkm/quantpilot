# Thanos 원격 저장소 연동 가이드

**목적**: Prometheus 로컬 TSDB(15일 보존)로는 부족한 30일 이상 SLO/감사 지표를 오브젝트 스토리지(S3/GCS/MinIO)에 장기 보관하고, PromQL 그대로 쿼리 가능하도록 Thanos 사이드카·스토어·쿼리어를 구성한다.

## 아키텍처

```
   ┌────────────────────┐        ┌────────────────┐
   │  quantpilot-proxy  │─ /metrics ─▶ Prometheus │
   │  (14 replicas)     │        │  + Thanos      │
   └────────────────────┘        │    sidecar     │
                                 └──────┬─────────┘
                                        │ gRPC (10901)
                                        │           ┌──────────────────┐
                                        ├──────────▶│ Thanos Query     │◀── Grafana
                                        │           └──────────────────┘
                                 uploads blocks
                                        ▼
                              ┌──────────────────┐
                              │  Object Storage  │  (S3 / GCS / MinIO)
                              │  bucket: qp-tsdb │
                              └────────┬─────────┘
                                       │
                              ┌────────▼─────────┐
                              │ Thanos Store GW  │◀── (선택) Compactor + Ruler
                              └──────────────────┘
```

- **Sidecar**: Prometheus의 로컬 블록을 오브젝트 스토리지에 지속 업로드 + 최신 데이터 gRPC 노출
- **Store Gateway**: 오브젝트 스토리지의 과거 블록을 gRPC로 제공
- **Query (Querier)**: Sidecar/Store를 병합, 중복 제거(`--query.replica-label`)하여 단일 PromQL 엔드포인트 제공
- **Compactor**: 블록 압축·다운샘플링(5m/1h) — 장기 보관 비용/속도 최적화
- **Ruler** (선택): Alertmanager로 recording/alerting rule을 서버 측에서 평가

## 1. 오브젝트 스토리지 설정

`deploy/thanos/objstore.yml`:
```yaml
type: S3
config:
  bucket: qp-tsdb
  endpoint: minio.internal:9000
  access_key: ${THANOS_S3_ACCESS_KEY}
  secret_key: ${THANOS_S3_SECRET_KEY}
  insecure: true
```

GCS를 사용할 때는 `type: GCS`, `config.bucket: qp-tsdb`, `service_account: <JSON>`.

## 2. Prometheus에 Thanos Sidecar 부착

`docker-compose.observability.yml`에 다음 서비스를 추가한다.

```yaml
services:
  prometheus:
    image: prom/prometheus:v2.55.0
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.path=/prometheus"
      - "--storage.tsdb.min-block-duration=2h"   # Thanos 요구사항 (compaction 비활성 등가)
      - "--storage.tsdb.max-block-duration=2h"
      - "--storage.tsdb.retention.time=6h"       # sidecar 업로드 이후 로컬은 짧게 유지
      - "--web.enable-lifecycle"
    external_labels:
      cluster: quantpilot-prod
      replica: "0"

  thanos-sidecar:
    image: quay.io/thanos/thanos:v0.36.1
    command:
      - "sidecar"
      - "--tsdb.path=/prometheus"
      - "--prometheus.url=http://prometheus:9090"
      - "--objstore.config-file=/etc/thanos/objstore.yml"
      - "--http-address=0.0.0.0:10902"
      - "--grpc-address=0.0.0.0:10901"
    volumes:
      - prom-data:/prometheus
      - ./thanos/objstore.yml:/etc/thanos/objstore.yml:ro
    ports: ["10901", "10902"]
    depends_on: [prometheus]

  thanos-store:
    image: quay.io/thanos/thanos:v0.36.1
    command:
      - "store"
      - "--data-dir=/data"
      - "--objstore.config-file=/etc/thanos/objstore.yml"
      - "--grpc-address=0.0.0.0:10901"
      - "--http-address=0.0.0.0:10902"
    volumes:
      - ./thanos/objstore.yml:/etc/thanos/objstore.yml:ro
      - thanos-store-data:/data

  thanos-query:
    image: quay.io/thanos/thanos:v0.36.1
    command:
      - "query"
      - "--http-address=0.0.0.0:10902"
      - "--grpc-address=0.0.0.0:10901"
      - "--query.replica-label=replica"
      - "--store=thanos-sidecar:10901"
      - "--store=thanos-store:10901"
    ports: ["10902:10902"]
    depends_on: [thanos-sidecar, thanos-store]

  thanos-compactor:
    image: quay.io/thanos/thanos:v0.36.1
    command:
      - "compact"
      - "--data-dir=/data"
      - "--objstore.config-file=/etc/thanos/objstore.yml"
      - "--wait"
      - "--retention.resolution-raw=30d"
      - "--retention.resolution-5m=180d"
      - "--retention.resolution-1h=2y"
    volumes:
      - ./thanos/objstore.yml:/etc/thanos/objstore.yml:ro
      - thanos-compactor-data:/data

volumes:
  thanos-store-data:
  thanos-compactor-data:
```

**Grafana 데이터소스 교체**: `deploy/grafana/provisioning/datasources/prometheus.yml`의 URL을
`http://prometheus:9090` → `http://thanos-query:10902`으로 변경. PromQL 문법은 동일하므로 대시보드(4종)는 수정 불필요.

## 3. 30일 이상 지표 확인

- 30일 SLO 대시보드(`dashboard_slo.json`)의 `[30d]` 창이 이제 원격 저장소에서 서빙된다.
- 예산 소진 속도 `burn_rate 6h/24h`도 로컬 TSDB 삭제 후 재기동 시 데이터가 사라지지 않는다.
- Compactor의 다운샘플링 정책:
  | 해상도 | 보관 기간 | 사용 사례 |
  |---|---|---|
  | raw (15s) | 30일 | 최근 인시던트 상세 분석 |
  | 5m | 180일 | 분기 리포트, 트렌드 |
  | 1h | 2년 | 연도별 SLO 회고, 계약 준수 감사 |

## 4. Kubernetes 배포 (kube-thanos)

kube-prometheus-stack 사용 시 Helm chart values.yaml에 다음을 추가:

```yaml
prometheus:
  prometheusSpec:
    externalLabels:
      cluster: quantpilot-prod
    thanos:
      image: quay.io/thanos/thanos:v0.36.1
      objectStorageConfig:
        existingSecret:
          name: thanos-objstore
          key: objstore.yml

thanosRuler:
  enabled: false   # Alerting은 Prometheus + Alertmanager 유지

# 별도 Helm chart로 store gateway + querier 설치
# helm repo add bitnami https://charts.bitnami.com/bitnami
# helm install thanos bitnami/thanos --namespace monitoring
```

## 5. 시크릿

- S3 access/secret: Vault Agent Injector로 `thanos-objstore` Secret 렌더.
- KMS 암호화된 백업: S3 버킷에 `SSE-KMS` 활성화, 라이프사이클로 Glacier Deep Archive 이관.

## 6. 트러블슈팅

| 증상 | 원인/조치 |
|---|---|
| Grafana 30일 창이 비어 있음 | Sidecar가 첫 2h 블록 업로드 이전. `docker logs qp-thanos-sidecar`에서 upload started 확인 |
| `Store gateway: block not found` | Compactor 미기동 상태에서 압축된 블록 참조. Compactor 로그 확인 |
| 중복 시계열 (`replica` 라벨) | Query의 `--query.replica-label=replica` 옵션 누락 여부 확인 |
| 오브젝트 스토리지 비용 급증 | Compactor의 다운샘플링 정책(`retention.resolution-*`) 재조정, Glacier Deep Archive 라이프사이클 적용 |

## 7. 도입 순서 요약

1. MinIO/S3 버킷 생성 + 접근키 발급 → Vault에 저장
2. `objstore.yml` 렌더, Sidecar 부착 → Prometheus 재기동
3. Store + Query 컨테이너 기동, Grafana 데이터소스 URL 교체
4. Compactor 기동 후 5m/1h 다운샘플링 확인 (`thanos_compact_downsample_total`)
5. `dashboard_slo.json` 창을 30d → 90d, 1y로 확장 실험
6. Runbook 갱신: Prometheus 재기동 시 데이터 유실 없음 명시
