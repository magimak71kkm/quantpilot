# QuantPilot — 주식 자동매매 & 분석 플랫폼 (Full Stack)

**버전**: 프론트엔드 v13 (14개 화면) · 백엔드 v9 (FastAPI) · **일자**: 2026-08-16

국내·해외 브로커 연동 기반의 주식 자동매매·분석 프로토타입과, 이를 뒷받침하는
백엔드 프록시(Google OAuth + Gemini AI + Git 기반 버전관리 + 관측성 스택) 전체 저장소입니다.

```
quantpilot-repo/
├── frontend/            # 정적 SPA 프로토타입 v13 (index.html, prototype.html, s01~s14.html)
│   └── .github/workflows/pages.yml   # GitHub Pages 자동 배포 워크플로우
├── backend/             # FastAPI 백엔드 프록시 v9
│   ├── app/             # 라우터(auth/google/ai/versions/admin/dashboard/slo/policy) + 미들웨어
│   ├── alembic/         # DB 마이그레이션 (rev 0001~0003)
│   ├── deploy/          # Docker Compose / Helm / Grafana / Thanos / Vault / OTel / Alerting
│   ├── e2e/             # Playwright 스모크 테스트
│   ├── poc/             # AI PoC 하네스 (스크리너·전략 JSON 스키마, 벤치마크)
│   ├── bench/           # Gemini 실측 벤치마크
│   └── scripts/         # init_db.sql, alert_smoke, 마이그레이션 SQL
├── .gitignore
├── .env.example         # 백엔드 환경변수 템플릿 (실제 키는 커밋 금지)
└── README.md
```

---

## 1. 프론트엔드 (GitHub Pages — 무료)

정적 HTML만으로 동작하며 별도 서버가 필요 없습니다. **단, 백엔드 연동 기능**
(S02 실시간 위젯·SLO 배지, S11 감사로그·SLO 정책, S13 실 API 롤백/비교)은
백엔드를 띄운 뒤 상단 툴바에 백엔드 URL을 입력해야 동작합니다.

### 배포 방법 (GitHub Pages)
```bash
cd frontend
git init
git add . && git commit -m "QuantPilot frontend v13"
git branch -M main
git remote add origin https://github.com/<YOUR_ID>/<REPO>.git
git push -u origin main
# 저장소 Settings → Pages → Source: GitHub Actions 선택 (워크플로우 자동 실행)
# 접속: https://<YOUR_ID>.github.io/<REPO>/
```

---

## 2. 백엔드 (FastAPI)

### 로컬 실행 (SQLite — 의존성 최소)
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export QP_DATABASE_URL="sqlite:///./quantpilot.db"
export QP_TEST_DB_URL="sqlite:///./quantpilot.db"
export QP_ENV=dev
uvicorn app.main:app --reload --port 8080
# Swagger: http://localhost:8080/docs
```

### Docker Compose 실행 (PostgreSQL + Redis + Vault + 관측성)
```bash
cd backend/deploy
cp .env.example .env   # 실제 키 입력 (QP_GOOGLE_*, QP_GEMINI_API_KEY, QP_JWT_SECRET …)
docker compose up -d --build
curl http://localhost:8080/health
```

### 테스트 & AI PoC 하네스
```bash
cd backend
pytest -q                          # 21개 테스트
python3 poc/harness.py --all --mock # 스크리너 5/5, 전략 4/4 통과
QP_GEMINI_API_KEY=sk-xxx python3 bench/gemini_bench.py --all   # 실 Gemini 벤치마크
```

### DB 마이그레이션 (Alembic)
```bash
cd backend
alembic upgrade head   # rev 0001(초기 스키마) → 0002(audit_logs 파티션) → 0003(SLO 정책)
```

---

## 3. 프론트엔드 + 백엔드 연동

1. 백엔드를 어디에든 배포합니다 (Render / Fly.io / Cloud Run / Railway / VPS).
2. 백엔드에서 `QP_FRONTEND_ORIGIN=https://<YOUR_ID>.github.io/<REPO>/` 설정 (CORS).
3. 프론트엔드 화면 우측 상단 **백엔드 URL 툴바**에 `https://api.your-backend.com` 입력 → [연결 테스트].
4. 연결 확인 후 S02(실시간), S04/S05(AI), S11(감사·SLO 정책), S13(버전관리)가 실 API로 전환됩니다.
5. 백엔드 미연결 시에도 로컬 폴백(데모 시뮬레이션)으로 전체 화면을 둘러볼 수 있습니다.

---

## 4. 관측성 & 배포 스택 요약

| 영역 | 구성 |
|---|---|
| 관측성 | Prometheus + Alertmanager(HA 2노드) + Grafana(자동 프로비저닝 4개 대시보드) + Thanos(장기 저장) + OTel/Jaeger + Slack 알림 |
| 배포 | Docker Compose(dev/prod/observability/thanos/ha/smoke) · Helm 차트(ServiceMonitor·PrometheusRule) · GitHub Actions CI/CD |
| 보안 | JWT+2FA · Google OAuth 2.0 PKCE · Vault Agent(KMS AES-256-GCM) · SHA-256 감사 로그 |
| 데이터 | PostgreSQL(월별 파티션, 90일 아카이브) · Redis(토큰 버킷 Rate-limit) · MinIO/S3(TSDB) |

> ⚠️ **보안 주의**: `.env`, API 키, JWT 시크릿, OAuth 클라이언트 시크릿은 **절대 git에 커밋하지 마세요**
> (`.gitignore`에 이미 포함). GitHub Secrets(`QP_GEMINI_API_KEY` 등)를 사용하세요.
