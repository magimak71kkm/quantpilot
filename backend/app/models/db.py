"""SQLAlchemy engine + session (SQLite fallback for tests)."""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# For unit tests we allow SQLite in-memory via env override
DB_URL = os.environ.get("QP_TEST_DB_URL") or settings.database_url

engine = create_engine(DB_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass
