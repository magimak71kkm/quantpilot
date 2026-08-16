# Vault Agent Injector 오버레이

**목적**: 운영에서 `.env` 파일 없이 Vault의 KV v2에서 시크릿을 렌더해 `proxy` 컨테이너에 주입한다.

## 1. Vault 사전 준비 (한 번만)

```bash
# KV v2 마운트 확인
vault secrets enable -path=secret kv-v2 || true

# 시크릿 저장
vault kv put secret/quantpilot/core   \
  jwt_secret="$(openssl rand -hex 32)" \
  kms_key_b64="$(python -c 'import os,base64;print(base64.b64encode(os.urandom(32)).decode())')" \
  frontend_origin="https://app.quantpilot.io" \
  database_url="postgresql+psycopg2://quantpilot:REDACTED@postgres:5432/quantpilot" \
  redis_url="redis://redis:6379/0"

vault kv put secret/quantpilot/google \
  client_id="..."      client_secret="..." \
  redirect_uri="https://api.quantpilot.io/auth/google/callback" \
  scopes="openid email https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/script.projects"

vault kv put secret/quantpilot/gemini \
  api_key="sk-..." model="gemini-1.5-flash" daily_quota_per_user=100
```

## 2. AppRole 발급

```bash
vault auth enable approle
vault policy write quantpilot-proxy - <<'EOF'
path "secret/data/quantpilot/*" { capabilities = ["read"] }
EOF
vault write auth/approle/role/quantpilot-proxy \
  token_ttl=1h token_max_ttl=4h \
  secret_id_ttl=24h token_policies=quantpilot-proxy

ROLE_ID=$(vault read -field=role_id auth/approle/role/quantpilot-proxy/role-id)
SECRET_ID=$(vault write -f -field=secret_id auth/approle/role/quantpilot-proxy/secret-id)

# 컨테이너가 마운트할 볼륨에 파일로 배치
docker run --rm -v qp_vault-role:/r alpine sh -c "
  printf '%s' \"$ROLE_ID\"   > /r/role_id
  printf '%s' \"$SECRET_ID\" > /r/secret_id
"
```

## 3. 오버레이 실행

```bash
export QP_VERSION=v0.1.0        # GHCR 이미지 태그
export GHCR_ORG=quantpilot
export VAULT_ADDR=https://vault.internal:8200

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose logs -f vault-agent | head
docker compose exec proxy sh -c 'ls -l /vault/secrets && head -3 /vault/secrets/proxy.env'
```

## 4. 시크릿 로테이션
- `vault kv put secret/quantpilot/gemini api_key=<new>` — Agent가 템플릿을 재렌더
- 서비스에 반영하려면 `docker compose kill -s HUP proxy` 또는 재시작
- Vault Agent 자체는 `secret_id_ttl` 만료 시 새 secret_id 발급 필요

## 5. 개발 vs 운영
| 항목 | dev (docker-compose.yml) | prod (+ docker-compose.prod.yml) |
|---|---|---|
| Vault | 내장 dev 모드 (`qp-dev-root`) | 외부 Vault 클러스터 |
| 시크릿 | `.env` 파일 | Vault Agent가 렌더한 `/vault/secrets/proxy.env` |
| 이미지 | 로컬 빌드 | GHCR `ghcr.io/<org>/proxy:<tag>` |
| 로그 | 표준 출력 | json-file (10MB × 5 rotate) |
| restart | 미지정 | `unless-stopped` |
