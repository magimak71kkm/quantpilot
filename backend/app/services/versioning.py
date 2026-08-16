"""Versioning core: commit hashing, DIFF (RFC-6902-style), revert semantics.

- Implements the model from `02_version_control_data_model.md`.
- Uses SHA-1(content|parent|message|ts) for commit SHA (40-hex chars).
- Revert = create new commit that restores the target tree; live branch head moves forward.
"""
import hashlib
import json
from datetime import datetime
from typing import Any, Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import orm

# ----- helpers ---------------------------------------------------------------
def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha1(*parts: str) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _tree_hash(files: dict[str, dict]) -> str:
    lines = [f"{p}:{_sha1(_canonical(c))}" for p, c in sorted(files.items())]
    return _sha1(*lines)


def ensure_strategy(db: Session, sid: str, uid: str) -> orm.Strategy:
    s = db.query(orm.Strategy).filter_by(id=sid, user_id=uid).one_or_none()
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "strategy not found")
    return s


# ----- commit / branch / tag -------------------------------------------------
def _resolve_ref(db: Session, sid: str, ref: str) -> str:
    """Accept SHA, tag name, or branch name."""
    c = db.query(orm.Commit).filter_by(sha=ref, strategy_id=sid).one_or_none()
    if c:
        return c.sha
    t = db.query(orm.Tag).filter_by(strategy_id=sid, name=ref).one_or_none()
    if t:
        return t.target_sha
    b = db.query(orm.Branch).filter_by(strategy_id=sid, name=ref).one_or_none()
    if b:
        return b.head_sha
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"ref not found: {ref}")


def make_commit(db: Session, sid: str, uid: str, message: str,
                files: dict[str, dict], parent_sha: Optional[str]) -> str:
    tree = _tree_hash(files)
    ts = datetime.utcnow().isoformat()
    sha = _sha1(sid, tree, parent_sha or "", message, ts, uid)
    if db.query(orm.Commit).filter_by(sha=sha).one_or_none():
        # tie-break by appending a byte if identical content — extremely unlikely for real data
        sha = _sha1(sha, "1")
    db.add(orm.Commit(sha=sha, strategy_id=sid, parent_sha=parent_sha, author_id=uid,
                      message=message, tree_hash=tree))
    for path, content in files.items():
        db.add(orm.CommitFile(commit_sha=sha, path=path,
                              blob_sha=_sha1(_canonical(content)), content=content))
    db.flush()
    return sha


def set_branch_head(db: Session, sid: str, branch: str, sha: str) -> None:
    b = db.query(orm.Branch).filter_by(strategy_id=sid, name=branch).one_or_none()
    if b and b.protected and branch == "live":
        # only allowed via revert/deploy — controllers call this after policy checks
        pass
    if b:
        b.head_sha = sha; b.updated_at = datetime.utcnow()
    else:
        db.add(orm.Branch(strategy_id=sid, name=branch, head_sha=sha,
                          protected=(branch == "live"), updated_at=datetime.utcnow()))


def tag_commit(db: Session, sid: str, uid: str, name: str, sha: str, message: str = "") -> None:
    db.add(orm.Tag(strategy_id=sid, name=name, target_sha=sha, message=message, created_by=uid))


def list_commits(db: Session, sid: str, limit: int = 50) -> list[dict]:
    q = (db.query(orm.Commit)
           .filter_by(strategy_id=sid)
           .order_by(orm.Commit.created_at.desc())
           .limit(limit).all())
    tags = {t.target_sha: t.name for t in db.query(orm.Tag).filter_by(strategy_id=sid).all()}
    return [{"sha": c.sha, "parent_sha": c.parent_sha, "message": c.message,
             "author_id": c.author_id, "created_at": c.created_at.isoformat(),
             "tree_hash": c.tree_hash, "tag": tags.get(c.sha)}
            for c in q]


# ----- DIFF ------------------------------------------------------------------
def _flatten(prefix: str, obj: Any, out: dict[str, Any]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(f"{prefix}/{k}", v, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _flatten(f"{prefix}/{i}", v, out)
    else:
        out[prefix] = obj


def _diff_file(a: dict, b: dict) -> list[dict]:
    fa, fb = {}, {}
    _flatten("", a, fa); _flatten("", b, fb)
    ops: list[dict] = []
    for k in sorted(set(fa) | set(fb)):
        if k not in fa:
            ops.append({"op": "add", "path": k or "/", "value": fb[k]})
        elif k not in fb:
            ops.append({"op": "remove", "path": k or "/"})
        elif fa[k] != fb[k]:
            ops.append({"op": "replace", "path": k or "/", "from": fa[k], "to": fb[k]})
    return ops


def compute_diff(db: Session, sid: str, from_ref: str, to_ref: str) -> dict:
    from_sha = _resolve_ref(db, sid, from_ref)
    to_sha = _resolve_ref(db, sid, to_ref)
    a_files = {f.path: f.content for f in db.query(orm.CommitFile).filter_by(commit_sha=from_sha).all()}
    b_files = {f.path: f.content for f in db.query(orm.CommitFile).filter_by(commit_sha=to_sha).all()}
    paths = sorted(set(a_files) | set(b_files))
    files_out = []
    for p in paths:
        a = a_files.get(p, {}); b = b_files.get(p, {})
        changes = _diff_file(a, b)
        if changes:
            files_out.append({"path": p, "changes": changes})
    return {"from": from_sha, "to": to_sha, "files": files_out}


# ----- Revert (create revert commit, do NOT hard-reset) ----------------------
def revert_to(db: Session, sid: str, uid: str, to_sha: str, reason: str, environment: str) -> str:
    if len(reason) < 20:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "reason must be at least 20 chars")
    target_sha = _resolve_ref(db, sid, to_sha)
    # snapshot files at target
    files = {f.path: f.content for f in db.query(orm.CommitFile).filter_by(commit_sha=target_sha).all()}
    # parent = current branch head
    branch = db.query(orm.Branch).filter_by(strategy_id=sid, name=environment).one_or_none()
    if not branch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"branch {environment} not found")
    parent = branch.head_sha
    sha = make_commit(db, sid, uid, f"Revert to {target_sha[:7]}: {reason}", files, parent_sha=parent)
    branch.head_sha = sha; branch.updated_at = datetime.utcnow()
    db.add(orm.Deployment(strategy_id=sid, environment=environment, commit_sha=sha,
                          deployed_by=uid, reason=f"revert: {reason}"))
    return sha


# ----- Seed data mirroring the prototype S13 demo ----------------------------
_V1_0 = {"rules.json": {"entry": [{"field": "RSI", "op": "<", "value": 30}],
                          "exit": {"take_profit_pct": 2.0, "stop_loss_pct": -3.0}}}
_V1_1 = {"rules.json": {"entry": [{"field": "RSI", "op": "<", "value": 30},
                                    {"field": "marketCap", "op": ">", "value": 1e11}],
                          "exit": {"take_profit_pct": 2.0, "stop_loss_pct": -3.0}}}
_V1_2 = {"rules.json": {"entry": [{"field": "RSI", "op": "<", "value": 30},
                                    {"field": "marketCap", "op": ">", "value": 1e11}],
                          "exit": {"take_profit_pct": 2.5, "stop_loss_pct": -2.0}}}
_V1_3 = {"rules.json": {"entry": [{"field": "RSI", "op": "<", "value": 30},
                                    {"field": "marketCap", "op": ">", "value": 1e11}],
                          "exit": {"take_profit_pct": 3.0, "stop_loss_pct": -2.0, "trailing_pct": 1.5}}}


def initial_seed(db: Session, sid: str, uid: str) -> None:
    p = None
    for msg, tree, tag in [
        ("v1.0 최초 생성", _V1_0, "v1.0"),
        ("v1.1 종목 필터 추가", _V1_1, "v1.1"),
        ("v1.2 손절 완화", _V1_2, "v1.2"),
        ("v1.3 RSI + 트레일링 추가", _V1_3, "v1.3"),
    ]:
        sha = make_commit(db, sid, uid, msg, tree, parent_sha=p)
        tag_commit(db, sid, uid, tag, sha)
        p = sha
    # branches
    db.add(orm.Branch(strategy_id=sid, name="paper", head_sha=p, protected=False))
    db.add(orm.Branch(strategy_id=sid, name="live",
                      head_sha=db.query(orm.Tag).filter_by(strategy_id=sid, name="v1.2").one().target_sha,
                      protected=True))
