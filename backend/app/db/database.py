from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import DATABASE_URL
from app.db.models import Base

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA secure_delete=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create tables if they do not exist yet (M1 uses create_all as its
    migration mechanism; docs/architecture.md records the follow-up to a
    real migration tool such as Alembic before schema changes ship)."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope():
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
