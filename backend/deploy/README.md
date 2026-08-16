# QuantPilot 배포 스택

| 서비스 | 이미지 | 포트 | 설명 |
|---|---|---|---|
| proxy | quantpilot/proxy:0.1.0 (로컬 빌드) | 8080 | FastAPI 백엔드 프록시 |
| postgres | postgres:16-alpine | 5432 | 사용자·토큰·감사·버전 저장 |
| redis | redis:7-alpine | 6379 | rate-limit·OAuth state 캐시 |
| vault | hashicorp/vault:1.17 (dev) | 8200 | 시크릿 저장 (dev 토큰: `qp-dev-root`) |

## 순서
1. `cp .env.example .env` → 값 채우기 (또는 dev 그대로 실행).
2. `docker compose up -d --build`.
3. `curl http://localhost:8080/health` — 정상 응답 확인.
4. `docker compose logs proxy | tail`.

## 자주 쓰는 명령
```bash
docker compose logs -f proxy
docker compose exec proxy pytest -q
docker compose exec postgres psql -U quantpilot -c "\dt"
docker compose down -v   # 볼륨까지 삭제
```

## Vault dev 예시
```bash
docker compose exec vault vault login qp-dev-root
docker compose exec vault vault kv put secret/quantpilot/gemini api_key=sk-xxxx
```
운영에서는 Vault Agent injector로 시크릿을 파일/env에 주입.
