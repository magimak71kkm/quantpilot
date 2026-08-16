"""/google/* proxy endpoints (skeleton — real HTTP calls in services/)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_rate
from app.models import orm

router = APIRouter()


@router.get("/sheets/{sheet_id}/values/{a1}")
async def read_sheet(sheet_id: str, a1: str, uid: str = Depends(require_rate), db: Session = Depends(get_db)):
    acc = db.query(orm.GoogleAccount).filter_by(user_id=uid).one_or_none()
    if not acc:
        raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "google not linked")
    from app.services.google_apis import sheets_get
    return await sheets_get(uid, sheet_id, a1)


@router.post("/sheets/{sheet_id}/append")
async def append_sheet(sheet_id: str, body: dict, uid: str = Depends(require_rate), db: Session = Depends(get_db)):
    from app.services.google_apis import sheets_append
    return await sheets_append(uid, sheet_id, body.get("range", "A1"), body.get("values", []))


@router.post("/drive/upload")
async def upload_drive(body: dict, uid: str = Depends(require_rate)):
    from app.services.google_apis import drive_upload
    return await drive_upload(uid, body.get("name", "report.pdf"), body.get("mime", "application/pdf"), body.get("content_b64", ""))


@router.post("/appsscript/run")
async def run_apps_script(body: dict, uid: str = Depends(require_rate)):
    from app.services.google_apis import script_run
    return await script_run(uid, body.get("script_id", ""), body.get("function", ""), body.get("parameters", []))
