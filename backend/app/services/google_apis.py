"""Google API clients with encrypted refresh-token retrieval."""
import httpx

from app.core.config import settings

SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets"
DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files?uploadType=media"
SCRIPT_BASE = "https://script.googleapis.com/v1/scripts"


async def _access_token(user_id: str) -> str:
    if settings.env == "dev":
        return "dev-access-token"
    from datetime import datetime
    from app.core.security import kms_decrypt
    from app.models import orm
    from app.models.db import SessionLocal
    from app.services.google_oauth import refresh_access_token
    db = SessionLocal()
    try:
        account = db.query(orm.GoogleAccount).filter_by(user_id=user_id).one_or_none()
        if not account:
            raise ValueError("google account is not linked")
        tokens = await refresh_access_token(kms_decrypt(account.enc_refresh_token))
        account.last_used_at = datetime.utcnow()
        db.commit()
        return tokens["access_token"]
    finally:
        db.close()


async def sheets_get(user_id: str, sheet_id: str, a1: str) -> dict:
    if settings.env == "dev":
        return {"range": a1, "majorDimension": "ROWS", "values": [["dev", "stub"]]}
    tok = await _access_token(user_id)
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{SHEETS_BASE}/{sheet_id}/values/{a1}", headers={"Authorization": f"Bearer {tok}"})
        r.raise_for_status()
        return r.json()


async def sheets_append(user_id: str, sheet_id: str, a1: str, values: list[list]) -> dict:
    if settings.env == "dev":
        return {"updates": {"updatedRows": len(values)}}
    tok = await _access_token(user_id)
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{SHEETS_BASE}/{sheet_id}/values/{a1}:append?valueInputOption=USER_ENTERED",
                         headers={"Authorization": f"Bearer {tok}"}, json={"values": values})
        r.raise_for_status()
        return r.json()


async def drive_upload(user_id: str, name: str, mime: str, content_b64: str) -> dict:
    if settings.env == "dev":
        return {"id": "dev-file-id", "name": name, "mimeType": mime, "size": len(content_b64)}
    import base64
    tok = await _access_token(user_id)
    payload = base64.b64decode(content_b64)
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(DRIVE_UPLOAD, headers={"Authorization": f"Bearer {tok}", "Content-Type": mime}, content=payload)
        r.raise_for_status()
        return r.json()


async def script_run(user_id: str, script_id: str, function: str, parameters: list) -> dict:
    if settings.env == "dev":
        return {"done": True, "response": {"result": {"function": function, "params": parameters}}}
    tok = await _access_token(user_id)
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{SCRIPT_BASE}/{script_id}:run", headers={"Authorization": f"Bearer {tok}"},
                         json={"function": function, "parameters": parameters})
        r.raise_for_status()
        return r.json()
