# QuantPilot Helm Chart

**목적**: 프로덕션 Kubernetes 클러스터에 백엔드 프록시를 배포하고, Vault Agent Injector로 시크릿을 파일로 주입한다.

## 사전 요구사항
- Kubernetes 1.27+
- ingress-nginx 컨트롤러
- cert-manager (또는 사전 발급 TLS Secret `quantpilot-tls`)
- [Vault Agent Injector](https://developer.hashicorp.com/vault/docs/platform/k8s/injector) 설치 + AppRole/Kubernetes 인증 마운트
- Postgres, Redis는 별도 관리형 서비스 사용 권장 (본 chart에는 미포함)

## 배포

```bash
helm upgrade --install quantpilot deploy/helm/quantpilot \
  --namespace quantpilot --create-namespace \
  --set image.tag=0.1.0 \
  --set ingress.host=api.quantpilot.io
```

Vault 사이드에서 미리 준비할 것:
```bash
vault write auth/kubernetes/role/quantpilot-proxy \
  bound_service_account_names=quantpilot-proxy \
  bound_service_account_namespaces=quantpilot \
  policies=quantpilot-proxy ttl=1h
```

## 렌더 확인 (드라이런)
```bash
helm template quantpilot deploy/helm/quantpilot | kubectl apply --dry-run=client -f -
```

## 시크릿 로테이션
- Vault KV 값을 갱신하면 사이드카가 `/vault/secrets/*.env`를 자동 재작성.
- Deployment는 파일 변경을 자동 감지하지 않으므로 `kubectl rollout restart deployment/quantpilot-proxy`로 반영.

## Prometheus Operator CRD 통합

`monitoring.enabled=true`일 때 다음 CRD가 자동 생성됩니다.

| CRD | 목적 |
|---|---|
| `ServiceMonitor` | `app.kubernetes.io/name=quantpilot` Service를 15초 간격으로 `/metrics` 스크래핑 |
| `PrometheusRule` | 7개 알림 규칙(SLO 6개 + saturation 1개), Compose 스택의 `alert_rules.yml`과 동일 |

`kube-prometheus-stack` 예시 (Prometheus 인스턴스가 `release: kube-prometheus-stack` 라벨의 CRD만 스크래핑하는 기본 구성):
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install kps prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace

helm upgrade --install quantpilot deploy/helm/quantpilot \
  --namespace quantpilot --create-namespace \
  --set monitoring.releaseLabel=kps
```
검증:
```bash
kubectl -n quantpilot get servicemonitor,prometheusrule
kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-prometheus 9090
# → http://localhost:9090/alerts 에서 규칙 로드 확인
```

## values 주요 항목
| 키 | 기본값 | 설명 |
|---|---|---|
| `replicaCount` | 2 | Deployment 파드 수 |
| `autoscaling.enabled` | true | HPA 활성화 (CPU 70%) |
| `vault.enabled` | true | Vault Agent Injector 주석 자동 추가 |
| `vault.role` | quantpilot-proxy | Vault 인증 역할 |
| `image.tag` | 0.1.0 | 프록시 이미지 태그 |
| `ingress.host` | api.quantpilot.io | 외부 노출 도메인 |
