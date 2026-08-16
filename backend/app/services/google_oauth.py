"""Google OAuth token exchange + refresh (thin httpx wrapper)."""
import httpx

from app.core.config import settings

TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


async def exchange_code(code: str, code_verifier: str) -> dict:
    """Exchange auth code for access + refresh tokens (Authorization Code + PKCE)."""
    if not settings.google_client_id:
        # dev fallback so callback flow can be exercised offline
        return {"access_token": "dev-access", "refresh_token": "dev-refresh", "expires_in": 3600, "email": "dev@example.com"}
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(TOKEN_URL, data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
        })
        r.raise_for_status()
        return r.json()


async def refresh_access_token(refresh_token: str) -> dict:
    if not settings.google_client_id:
        return {"access_token": "dev-access", "expires_in": 3600}
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(TOKEN_URL, data={
            "refresh_token": refresh_token,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "grant_type": "refresh_token",
        })
        r.raise_for_status()
        return r.json()


async def fetch_user_info(access_token: str) -> dict:
    if not settings.google_client_id:
        return {"sub": "dev-google-sub", "email": "dev@example.com"}
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        r.raise_for_status()
        return r.json()
