"""JWT + password + KMS-style AEAD helpers."""
import base64
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import jwt

from app.core.config import settings


def hash_password(pw: str) -> str:
    # bcrypt truncates at 72 bytes; enforce explicitly for safety
    return bcrypt.hashpw(pw.encode("utf-8")[:72], bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(sub: str, extra: Optional[dict] = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_ttl_min)).timestamp()),
        "iss": "quantpilot",
        "aud": "spa",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg], audience="spa")


# ---- KMS stub (AES-GCM via cryptography). In prod, use cloud KMS. ------------
def _key() -> bytes:
    if settings.kms_key_b64:
        return base64.b64decode(settings.kms_key_b64)
    # Deterministic dev key derived from JWT secret (NEVER in prod)
    from hashlib import sha256
    return sha256(settings.jwt_secret.encode()).digest()


def kms_encrypt(plaintext: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aes = AESGCM(_key())
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, plaintext.encode(), b"quantpilot")
    return nonce + ct


def kms_decrypt(blob: bytes) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aes = AESGCM(_key())
    nonce, ct = blob[:12], blob[12:]
    return aes.decrypt(nonce, ct, b"quantpilot").decode()
