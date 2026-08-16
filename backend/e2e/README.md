# E2E 스모크 (Playwright)

**목적**: 프로토타입 SPA와 백엔드 프록시가 실제 브라우저에서 왕복 동작하는지 자동 검증.

## 시나리오
| 파일 | 시나리오 | 검증 대상 |
|---|---|---|
| `tests/00_smoke.spec.ts` | 홈 → S13 롤백 → S02 SLO 배지 → S04 AI 스크리너 | 14개 화면 렌더 · 백엔드 연결/폴백 · SLO 배지 갱신 |

## 사전 준비
1. 프로토타입 빌드본이 `../proto/prototype.html`에 위치할 것 (`build_proto.py` 실행 산출물).
2. Node.js 20+, Playwright 브라우저 설치.

## 실행

```bash
cd e2e
npm install
npm run install:browsers      # chromium + 시스템 의존성

# 백엔드 프록시가 http://localhost:8080 에 떠 있어야 실 API 시나리오 통과
# (백엔드가 없어도 로컬 폴백 경로는 통과 — 그린 상태 유지)
npm test

# 실패 시 상세 리포트
npm run report
```

## 환경 변수
- `QP_PROTOTYPE_URL` — 기본 `http://localhost:8090/prototype.html` (Playwright가 python3 -m http.server 자동 기동)
- `QP_API_URL` — 백엔드 프록시 URL (기본 `http://localhost:8080`), `localStorage.QP_API_BASE`로 주입됨
- `QP_SKIP_WEBSERVER=1` — Playwright의 자동 python 서버 기동 억제 (다른 곳에서 서빙 중일 때)

## CI 통합
`.github/workflows/ci.yml` 의 `test` job 이후 새 job `e2e`를 추가하면 됩니다.
```yaml
  e2e:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: |
          cd e2e
          npm ci
          npx playwright install --with-deps chromium
      - run: |
          cd .. && python3 -m venv .venv && . .venv/bin/activate
          pip install -r requirements.txt
          uvicorn app.main:app --host 0.0.0.0 --port 8080 &
          sleep 3
      - run: cd e2e && npm test
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-report
          path: e2e/playwright-report
```

## 트러블슈팅
| 증상 | 원인/조치 |
|---|---|
| 8090 포트 충돌 | `QP_SKIP_WEBSERVER=1` 로 자동 기동 억제하고 다른 정적 서버 이용 |
| `data-nav="s13"` 미발견 | 프로토타입 최신 빌드가 아니어서 → `build_proto.py` 재실행 후 재시도 |
| 백엔드 연결 실패로 SLO 배지가 "—" | 로컬 폴백 모드는 정상. 실 백엔드 원할 시 `http://localhost:8080/health` 확인 |
