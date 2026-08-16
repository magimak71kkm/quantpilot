# Alertmanager HA + Thanos Ruler

## 목표
- Alertmanager 단일 장애 지점(SPOF) 제거 — 2대(`alertmanager`, `alertmanager-2`)가 gossip으로 상태 동기화하며 알림 중복 제거를 자동 처리
- Prometheus에 부착된 alerting rule을 **Thanos Ruler**로 이관 → Prometheus 재시작·롤링 배포 시에도 규칙 평가 중단 없음
- Recording rule은 사전 집계로 30d 창 쿼리 비용을 O(수집기) 만큼 절감

## 구성 요약

```
Prometheus + Sidecar ──┐
Thanos Store ──────────┼──▶ Thanos Query ◀── Thanos Ruler
                       │                            │
                       └────────────────────────────┴──▶ AlertManager HA
                                                          ├─ alertmanager   (9093)
                                                          └─ alertmanager-2 (9193)
                                                             gossip: 9094
```

- Ruler는 두 Alertmanager 모두에 알림 전송, Alertmanager 클러스터는 gossip으로 dedup 처리.
- `--label=replica="0"` — Ruler 자체를 HA 배포할 때 다른 replica는 `"1"` 로 라벨링.

## 파일
| 파일 | 역할 |
|---|---|
| `rules/quantpilot.rules.yml` | recording 6개 + alerting 4개 (Thanos Ruler가 평가) |
| `docker-compose.ha.yml` | Alertmanager 2대 + Thanos Ruler 오버레이 |

## 실행

```bash
cd deploy
docker compose \
  -f docker-compose.yml \
  -f docker-compose.observability.yml \
  -f thanos/docker-compose.thanos.yml \
  -f thanos/docker-compose.ha.yml up -d

# Alertmanager HA 상태 확인
curl -s http://localhost:9093/api/v2/status | jq .cluster
curl -s http://localhost:9193/api/v2/status | jq .cluster
#   { "status":"ready", "peers":[{"address":"alertmanager:9094"},{"address":"alertmanager-2:9094"}] }

# Thanos Ruler 규칙 상태
curl -s http://localhost:10903/api/v1/rules | jq '.data.groups[].name'
```

## 이관 절차
1. **Prometheus의 alerting rule 제거** — `deploy/grafana/prometheus.yml`의 `rule_files:` 라인을 주석 처리
2. **Ruler 규칙 검증** — `docker exec qp-thanos-ruler thanos tools rules-check --rules /etc/thanos/rules/quantpilot.rules.yml`
3. **롤링 재기동** — Prometheus 재시작 후에도 알림 평가가 Ruler에서 계속됨을 관찰
4. **Alertmanager 이중화 검증** — `docker stop qp-alertmanager` 후에도 Ruler가 `alertmanager-2:9093`로 라우팅되는지 확인

## 트러블슈팅
| 증상 | 원인/조치 |
|---|---|
| Alertmanager 클러스터 unhealthy | 9094 gossip 포트 통신 확인, `--cluster.advertise-address` 이름이 컨테이너에서 도달 가능한지 확인 |
| Ruler에 규칙이 표시되지 않음 | `--rule-file` 글롭 경로, 마운트 볼륨 확인 (`docker exec qp-thanos-ruler ls /etc/thanos/rules`) |
| 알림이 두 번 오는 것처럼 보임 | Alertmanager cluster 미형성 상태에서 두 노드가 각자 발송 중 — `peers` 목록 확인 |
| 30d recording이 비어 있음 | Thanos Store가 오브젝트 스토리지에서 30d 블록을 아직 못 읽는 상태. Store 로그 확인 |
