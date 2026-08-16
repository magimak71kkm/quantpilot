// Vault Agent 사이드카 — AppRole 인증으로 KV v2에서 시크릿을 읽어
// /vault/secrets/proxy.env 파일로 렌더한다. proxy 컨테이너는 이 파일을 source 해서 부팅한다.

pid_file = "/tmp/vault-agent.pid"

auto_auth {
  method "approle" {
    mount_path = "auth/approle"
    config = {
      role_id_file_path   = "/vault/role/role_id"
      secret_id_file_path = "/vault/role/secret_id"
      remove_secret_id_file_after_reading = false
    }
  }
  sink "file" {
    config = { path = "/vault/secrets/.vault-token" }
  }
}

cache { use_auto_auth_token = true }

vault {
  address = "${env "VAULT_ADDR"}"
  retry { num_retries = 5 }
}

template {
  source      = "/etc/vault/templates/proxy.env.tpl"
  destination = "/vault/secrets/proxy.env"
  perms       = "0640"
  // 값이 갱신되면 파일도 자동 갱신되지만, uvicorn 자체 재시작은 별도 컨트롤러가 담당
}
