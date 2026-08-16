import pyotp
from app.core.security import decode_token
from app.core.security import create_access_token


def test_login_and_2fa(client, user):
    # login
    r = client.post("/auth/login", json={"email": user.email, "password": "pw1234"})
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    assert decode_token(tok)["sub"] == user.id
    assert r.json()["twofa_required"] is True

    # 2FA verify with a fresh TOTP
    code = pyotp.TOTP(user.totp_secret).now()
    pending = create_access_token(user.id, {"twofa_ok": False})
    r = client.post("/auth/2fa/verify", json={"email": user.email, "code": code},
                    headers={"Authorization": f"Bearer {pending}"})
    assert r.status_code == 200, r.text
    assert r.json()["verified"] is True
    assert r.json()["access_token"]


def test_pending_2fa_token_cannot_access_protected_route(client, user, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "env", "prod")
    pending = create_access_token(user.id, {"twofa_ok": False})
    r = client.get("/google/sheets/demo/values/A1", headers={"Authorization": f"Bearer {pending}"})
    assert r.status_code == 403


def test_login_bad_password(client, user):
    r = client.post("/auth/login", json={"email": user.email, "password": "wrong"})
    assert r.status_code == 401
