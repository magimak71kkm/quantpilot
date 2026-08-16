# QuantPilot

QuantPilot is a Korean stock analysis and strategy workspace. It combines a static frontend prototype with a FastAPI backend for authentication, Google APIs, Gemini JSON generation, strategy versioning, audit logs, SLO dashboards, and deployment observability.

## Project status

This repository is deployable as a backend proxy and frontend prototype. It is not a live trading execution engine. Live trading requires a separate broker adapter, order-risk controls, reconciliation, and an operational approval process.

The backend now enforces these production boundaries:

- JWT access tokens must carry a successful 2FA claim when `QP_ENV=prod`.
- Google OAuth state is short-lived and Redis-backed in production.
- Google refresh tokens are encrypted before database storage and refreshed only on the server.
- Rate limits and per-user daily AI quota are Redis-backed in production.
- Production startup rejects default JWT/KMS secrets and non-HTTPS frontend origins.

## Repository layout

```text
frontend/                 Static HTML prototype and GitHub Pages artifact
backend/app/              FastAPI application, services, models, and tests
backend/alembic/          Database migrations
backend/deploy/           Docker Compose, Helm, Vault, observability
backend/poc/              Offline AI schemas and evaluation harness
.github/workflows/        Backend CI and GitHub Pages deployment
```

## Local backend

Requires Python 3.12+.

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
$env:QP_ENV = "dev"
$env:QP_DATABASE_URL = "sqlite:///./quantpilot.db"
uvicorn app.main:app --reload --port 8080
```

Open Swagger at `http://localhost:8080/docs` and verify `http://localhost:8080/health`.

## Tests and checks

```powershell
cd backend
py -m compileall -q app
py -m pytest
py poc/harness.py --all --mock
```

GitHub Actions runs compile checks and the complete pytest suite for pushes and pull requests targeting `main`.

## Docker development stack

```powershell
cd backend\deploy
Copy-Item ..\..\.env.example .env
docker compose up -d --build
curl http://localhost:8080/health
```

The development stack provides the API, PostgreSQL, Redis, and Vault dev mode. Do not use the development Vault token or default database credentials in production.

## Production configuration

Provide secrets through Vault or the platform secret manager. At minimum configure:

- `QP_ENV=prod`
- `QP_DATABASE_URL` for PostgreSQL
- `QP_REDIS_URL` for a persistent Redis service
- `QP_JWT_SECRET` with at least 32 random characters
- `QP_KMS_KEY_B64` containing a base64-encoded AES key
- `QP_FRONTEND_ORIGIN` using HTTPS
- `QP_GOOGLE_CLIENT_ID`, `QP_GOOGLE_CLIENT_SECRET`, and the registered HTTPS callback
- `QP_GEMINI_API_KEY` and `QP_GEMINI_DAILY_QUOTA_PER_USER`

Apply migrations before starting the API:

```bash
cd backend
alembic upgrade head
```

The production compose overlay expects a prebuilt image and Vault Agent. Review `backend/deploy/docker-compose.prod.yml` and `backend/deploy/vault-agent/` before using it with a real cluster.

## Frontend deployment

The `pages.yml` workflow publishes `frontend/` to GitHub Pages. Enable GitHub Pages with the GitHub Actions source in repository settings. The prototype can connect to the backend by entering its HTTPS URL in the frontend connection control; it stores the selected API URL locally in the browser.

## Authentication flow

1. `POST /auth/login` returns a short-lived provisional token when the account has TOTP enabled.
2. `POST /auth/2fa/verify` requires that provisional bearer token and a six-digit TOTP code, then returns a fully authenticated token.
3. In production, protected endpoints reject the provisional token.
4. `GET /auth/google/start` derives the Google OAuth identity from the authenticated bearer token; the user ID is never accepted from the query string.

## Known product boundaries

- The UI is a static prototype with local-storage fallback, not a production frontend application.
- Google API access requires valid OAuth consent, scopes, refresh tokens, and external API availability.
- Redis is required for production rate limits, OAuth state, and AI quota enforcement.
- No broker integration or real-money order execution is included.
