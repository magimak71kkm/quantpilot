# Google Cloud OAuth 연동 가이드 (개발 → 운영)

**대상**: QuantPilot 백엔드 프록시 (v0.1.0) · **최종 업데이트**: 2026-08-15

## 1. Google Cloud 프로젝트 준비
1. https://console.cloud.google.com/ 에서 새 프로젝트 생성 (예: `quantpilot-dev`).
2. **API and Services → Enabled APIs and services**에서 다음 4개 활성화:
   - Google Sheets API
   - Google Drive API
   - Apps Script API
   - Generative Language API (Gemini)

## 2. OAuth 동의 화면 (Consent screen)
- User type: **External** (Workspace 내부만 쓸 계획이면 Internal).
- App name: `QuantPilot`, 지원 이메일: 관리자 이메일.
- **Scopes** 등록(최소 권한):
  - `openid`
  - `email`
  - `https://www.googleapis.com/auth/spreadsheets`
  - `https://www.googleapis.com/auth/drive.file`
  - `https://www.googleapis.com/auth/script.projects`
- Test users에 개발자 본인 계정 추가 (Publishing status = Testing 유지).

## 3. OAuth 2.0 Client ID 발급
- **Credentials → Create credentials → OAuth client ID**
- Application type: **Web application**
- Authorized redirect URIs:
  - 개발: `http://localhost:8080/auth/google/callback`
  - 스테이징: `https://api-stg.quantpilot.io/auth/google/callback`
  - 운영: `https://api.quantpilot.io/auth/google/callback`
- 생성된 **Client ID / Client Secret**을 `deploy/.env`의 `QP_GOOGLE_CLIENT_ID`, `QP_GOOGLE_CLIENT_SECRET`에 기입.

## 4. Gemini API 키
- **APIs & Services → Credentials → Create credentials → API key**.
- API restrictions에서 Generative Language API만 허용, Application restrictions에서 서버 아웃바운드 IP 화이트리스트.
- `QP_GEMINI_API_KEY`에 값 입력.

## 5. 배포용 KMS 키 생성
```bash
python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())" > .kms_key
export QP_KMS_KEY_B64=$(cat .kms_key)
```
운영에서는 GCP KMS / AWS KMS / HashiCorp Vault Transit로 대체.

## 6. Compose 스택 실행
```bash
cd deploy
cp .env.example .env  # 위 값 채우기
docker compose up -d --build
docker compose ps
curl -s http://localhost:8080/health
# → {"ok":true,"service":"quantpilot-backend","version":"0.1.0"}
```

## 7. 최초 OAuth 흐름 시연
1. 앱 계정 등록:
   ```bash
   curl -X POST http://localhost:8080/auth/_dev/register \
     -H 'Content-Type: application/json' \
     -d '{"email":"me@example.com","password":"pw12345"}'
   ```
2. 로그인 → JWT 획득:
   ```bash
   TOKEN=$(curl -s -X POST http://localhost:8080/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"email":"me@example.com","password":"pw12345"}' | jq -r .access_token)
   ```
3. Google 연동 시작 (브라우저에서 열기):
   `http://localhost:8080/auth/google/start?user_id=<위 로그인의 sub>`
4. 동의 후 `/auth/google/callback` → `{"linked": true}` 응답이면 성공, `google_accounts` 테이블에 KMS 암호화된 refresh_token이 저장됨.

## 8. 보안 체크리스트 (운영 이관 시)
- [ ] `QP_JWT_SECRET`, `QP_KMS_KEY_B64` Vault에서 주입 (Compose env가 아닌 Vault Agent injector)
- [ ] Google OAuth Consent screen → **In production** 전환 + 도메인 소유권 인증
- [ ] `redirect_uri` HTTPS 필수, HSTS 6개월
- [ ] `google_accounts.enc_refresh_token` 백업 시 KMS 키 없이는 복원 불가 상태 유지
- [ ] 감사 로그 90일 이상 보존, S3/GCS 오브젝트 락 적용
