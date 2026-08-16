# QuantPilot Backend Proxy (W1 Skeleton)

**Version**: 0.1.0 · **Date**: 2026-08-15 · **Stack**: FastAPI · SQLAlchemy · Redis · PostgreSQL · Google OAuth 2.0

## 구성
```
app/
  main.py            FastAPI 진입점
  core/              설정·보안·의존성
    config.py        환경변수 (Pydantic Settings)
    security.py      JWT 발급/검증, KMS 스텁 암복호화
    deps.py          DB/Redis/Current User 의존성
  models/            SQLAlchemy 모델 + 스키마
    db.py            엔진/세션
    orm.py           users, google_accounts, audit_logs, strategies, commits …
    schemas.py       Pydantic 요청/응답
  api/               라우터
    auth.py          로그인·2FA·Google OAuth start/callback
    google.py        Sheets/Drive/Apps Script 프록시
    ai.py            /ai/screener, /ai/strategy 프록시
    versions.py      S13 버전관리 API 스텁 (commit/diff/revert/deploy)
  services/
    google_oauth.py  Google OAuth 클라이언트
    google_apis.py   Sheets/Drive/Script HTTP 클라이언트
    gemini_client.py Gemini 호출·JSON 스키마 재시도
    versioning.py    커밋/브랜치/태그/DIFF 계산 로직
  tests/             pytest 스켈레톤
poc/
  harness.py         AI PoC 오프라인 하네스 (mock LLM 지원)
  screener_cases.jsonl
  strategy_cases.jsonl
  schema_screener.json
  schema_strategy.json
scripts/
  init_db.sql        DDL (백엔드 프록시 설계서 + 버전관리 데이터모델)
requirements.txt
```

## 빠른 실행 (개발용)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export QP_ENV=dev
uvicorn app.main:app --reload --port 8080
```

## 검증 (pytest, 오프라인)

```bash
pytest -q
```

## AI PoC 하네스

```bash
python3 poc/harness.py --screener --mock
python3 poc/harness.py --strategy --mock
```

`--mock` 없이 실행하면 `GEMINI_API_KEY` 환경변수로 실제 호출한다.
