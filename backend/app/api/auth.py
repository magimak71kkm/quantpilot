"""/auth endpoints — login, 2FA, Google OAuth start/callback (skeleton)."""
import secrets
import time
import uuid
from urllib.parse import urlencode

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, current_user_id, pending_user_id
from app.core.security import create_access_token, hash_password, verify_password
from app.models import orm
from app.models.schemas import LoginReq, LoginResp, TwoFAReq, TwoFAResp

router = APIRouter()

# state store (dev): in prod use Redis with 5-min TTL
_OAUTH_STATE: dict[str, dict] = {}


@router.post("/login", response_model=LoginResp)
def login(body: LoginReq, db: Session = Depends(get_db)):
    user = db.query(orm.User).filter_by(email=body.email).one_or_none()
    if not user or not verify_password(body.password, user.pw_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    needs_2fa = bool(user.totp_secret)
    tok = create_access_token(sub=user.id, extra={"twofa_ok": not needs_2fa})
    return LoginResp(access_token=tok, expires_in=settings.jwt_ttl_min * 60, twofa_required=needs_2fa)


@router.post("/2fa/verify", response_model=TwoFAResp)
def verify_2fa(body: TwoFAReq, uid: str = Depends(pending_user_id), db: Session = Depends(get_db)):
    user = db.query(orm.User).filter_by(email=body.email).one_or_none()
    if not user or user.id != uid or not user.totp_secret:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "2fa not enrolled")
    if not pyotp.TOTP(user.totp_secret).verify(body.code, valid_window=1):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid 2fa code")
    tok = create_access_token(sub=user.id, extra={"twofa_ok": True})
    return TwoFAResp(verified=True, access_token=tok, expires_in=settings.jwt_ttl_min * 60)


@router.get("/google/start")
def google_start(user_id: str = Depends(current_user_id)):
    """SPA calls after JWT login. Redirects to Google consent screen."""
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    # code_challenge = SHA256(verifier) base64url no-pad — kept short for skeleton
    import base64, hashlib
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    from app.core.oauth_state import save_oauth_state
    save_oauth_state(state, {"uid": user_id, "verifier": verifier})
    qs = urlencode({
        "client_id": settings.google_client_id or "PLACEHOLDER_CLIENT_ID",
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "scope": settings.google_scopes,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + qs, status_code=302)


@router.get("/google/callback")
async def google_callback(request: Request, code: str, state: str, db: Session = Depends(get_db)):
    from app.core.oauth_state import pop_oauth_state
    ctx = pop_oauth_state(state)
    if not ctx:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid or expired state")
    # NOTE: real token exchange lives in services/google_oauth.py
    from app.services.google_oauth import exchange_code, fetch_user_info
    tokens = await exchange_code(code=code, code_verifier=ctx["verifier"])
    profile = await fetch_user_info(tokens["access_token"])
    # Persist encrypted refresh_token
    from app.core.security import kms_encrypt
    acc = db.query(orm.GoogleAccount).filter_by(user_id=ctx["uid"]).one_or_none()
    if acc:
        if tokens.get("refresh_token"):
            acc.enc_refresh_token = kms_encrypt(tokens["refresh_token"])
        acc.google_sub = profile["sub"]
        acc.google_email = profile.get("email")
        acc.scopes = settings.google_scopes
    else:
        if not tokens.get("refresh_token"):
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Google did not return a refresh token")
        acc = orm.GoogleAccount(
            user_id=ctx["uid"],
            google_sub=profile["sub"],
            google_email=profile.get("email"),
            scopes=settings.google_scopes,
            enc_refresh_token=kms_encrypt(tokens["refresh_token"]),
        )
        db.add(acc)
    db.commit()
    return {"linked": True}


@router.post("/logout")
def logout():
    # Stateless JWT — real impl would blacklist token id in Redis
    return {"ok": True}


# ---- Dev helper: create a user with a known password + TOTP -----------------
@router.post("/_dev/register")
def dev_register(body: LoginReq, db: Session = Depends(get_db)):
    if settings.env != "dev":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if db.query(orm.User).filter_by(email=body.email).one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "email exists")
    u = orm.User(
        id=str(uuid.uuid4()),
        email=body.email,
        pw_hash=hash_password(body.password),
        totp_secret=pyotp.random_base32(),
    )
    db.add(u); db.commit()
    return {"user_id": u.id, "totp_secret": u.totp_secret}
