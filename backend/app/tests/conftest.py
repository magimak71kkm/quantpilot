"""Test fixtures: SQLite in-memory + FastAPI TestClient with dev auth bypass."""
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

# Force dev mode + SQLite BEFORE any app import
os.environ["QP_ENV"] = "dev"
os.environ["QP_TEST_DB_URL"] = "sqlite:///:memory:"

from app.core.security import create_access_token, hash_password  # noqa: E402
from app.models import db as db_mod  # noqa: E402
from app.models import orm  # noqa: E402

# Single shared in-memory SQLite across sessions (StaticPool)
db_mod.engine = create_engine(
    "sqlite:///:memory:",
    future=True,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
db_mod.SessionLocal = sessionmaker(bind=db_mod.engine, autoflush=False, autocommit=False, future=True)
db_mod.Base.metadata.create_all(bind=db_mod.engine)

from app.main import app  # noqa: E402


@pytest.fixture()
def db():
    s = db_mod.SessionLocal()
    try:
        yield s
    finally:
        s.rollback(); s.close()


@pytest.fixture()
def user(db):
    """Create a fresh user per test (unique email) to keep tests isolated."""
    email = f"t-{uuid.uuid4().hex[:8]}@example.com"
    u = orm.User(id=str(uuid.uuid4()), email=email, pw_hash=hash_password("pw1234"),
                 totp_secret="JBSWY3DPEHPK3PXP")
    db.add(u); db.commit(); db.refresh(u)
    return u


@pytest.fixture()
def client(user):
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {create_access_token(user.id, {'twofa_ok': True})}"})
    # expose the user's email/id for tests that need it
    c.user_email = user.email
    c.user_id = user.id
    return c
