"""/versions/* — S13 versioning API (commit/history/diff/revert/deploy).

Backing store: SQLAlchemy ORM matching the DDL in scripts/init_db.sql.
The prototype S13 UI can hit these endpoints once the SPA replaces
its localStorage seed with real API calls.
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import current_user_id, get_db
from app.models import orm
from app.models.schemas import CommitCreate, DeployReq, RevertReq
from app.services.versioning import (
    compute_diff, ensure_strategy, initial_seed, list_commits, make_commit,
    revert_to, set_branch_head,
)

router = APIRouter()


@router.post("/strategies")
def create_strategy(body: dict, uid: str = Depends(current_user_id), db: Session = Depends(get_db)):
    sid = str(uuid.uuid4())
    strat = orm.Strategy(id=sid, user_id=uid, name=body["name"], description=body.get("description"), current_ref="live")
    db.add(strat); db.flush()
    # Seed 4 versions (matches prototype S13 demo data)
    initial_seed(db, sid, uid)
    db.commit()
    return {"id": sid}


@router.get("/strategies/{sid}/commits")
def get_commits(sid: str, limit: int = 50, uid: str = Depends(current_user_id), db: Session = Depends(get_db)):
    ensure_strategy(db, sid, uid)
    return list_commits(db, sid, limit=limit)


@router.get("/strategies/{sid}/commits/{sha}")
def get_commit(sid: str, sha: str, uid: str = Depends(current_user_id), db: Session = Depends(get_db)):
    ensure_strategy(db, sid, uid)
    c = db.query(orm.Commit).filter_by(sha=sha, strategy_id=sid).one_or_none()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "commit not found")
    files = db.query(orm.CommitFile).filter_by(commit_sha=sha).all()
    return {
        "sha": c.sha, "parent_sha": c.parent_sha, "message": c.message,
        "created_at": c.created_at, "tree_hash": c.tree_hash,
        "files": {f.path: f.content for f in files},
    }


@router.get("/strategies/{sid}/diff")
def diff(sid: str, from_: str, to: str, uid: str = Depends(current_user_id), db: Session = Depends(get_db)):
    """Query params: ?from=<sha>&to=<sha>. Uses tag names too."""
    ensure_strategy(db, sid, uid)
    return compute_diff(db, sid, from_, to)


@router.post("/strategies/{sid}/commits")
def new_commit(sid: str, body: CommitCreate, uid: str = Depends(current_user_id), db: Session = Depends(get_db)):
    ensure_strategy(db, sid, uid)
    sha = make_commit(db, sid, uid, body.message, body.files, parent_sha=body.parent_sha)
    db.commit()
    return {"sha": sha}


@router.post("/strategies/{sid}/revert")
def revert(sid: str, body: RevertReq, uid: str = Depends(current_user_id), db: Session = Depends(get_db)):
    ensure_strategy(db, sid, uid)
    sha = revert_to(db, sid, uid, body.to_sha, body.reason, body.environment)
    db.commit()
    return {"revert_sha": sha}


@router.post("/strategies/{sid}/deploy")
def deploy(sid: str, body: DeployReq, uid: str = Depends(current_user_id), db: Session = Depends(get_db)):
    ensure_strategy(db, sid, uid)
    set_branch_head(db, sid, body.environment, body.sha)
    dep = orm.Deployment(strategy_id=sid, environment=body.environment, commit_sha=body.sha, deployed_by=uid, reason="manual deploy")
    db.add(dep); db.commit()
    return {"deployed": True, "environment": body.environment, "sha": body.sha}
