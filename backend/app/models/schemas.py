"""Pydantic request/response schemas."""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---- Auth --------------------------------------------------------------------
class LoginReq(BaseModel):
    email: str
    password: str


class LoginResp(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    twofa_required: bool = True


class TwoFAReq(BaseModel):
    email: str
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class TwoFAResp(BaseModel):
    verified: bool
    access_token: Optional[str] = None
    expires_in: Optional[int] = None


# ---- Versioning (S13) --------------------------------------------------------
class CommitOut(BaseModel):
    sha: str
    parent_sha: Optional[str]
    author_id: str
    message: str
    tree_hash: str
    created_at: datetime
    tag: Optional[str] = None


class CommitCreate(BaseModel):
    message: str = Field(min_length=1)
    files: dict[str, dict]  # {path: json_content}
    parent_sha: Optional[str] = None


class DiffChange(BaseModel):
    op: Literal["add", "remove", "replace"]
    path: str
    value: Any | None = None
    from_: Any | None = Field(default=None, alias="from")
    to: Any | None = None


class DiffOut(BaseModel):
    from_sha: str = Field(alias="from")
    to_sha: str = Field(alias="to")
    files: list[dict]


class RevertReq(BaseModel):
    to_sha: str
    reason: str = Field(min_length=20)
    environment: Literal["paper", "live"] = "live"


class DeployReq(BaseModel):
    environment: Literal["paper", "live"]
    sha: str


# ---- AI ----------------------------------------------------------------------
class ScreenerReq(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class StrategyReq(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
