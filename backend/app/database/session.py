"""SQLAlchemy engine and session helpers."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.base import Base

logger = get_logger(__name__)
settings = get_settings()

connect_args: dict[str, object] = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    future=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection: object, _connection_record: object) -> None:
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _alembic_config():
    from alembic.config import Config

    backend_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def init_db() -> None:
    """Apply Alembic migrations. Stamp existing create_all databases once."""
    from alembic import command

    # Import models so metadata is available for offline tooling.
    from app.database import models  # noqa: F401

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    cfg = _alembic_config()

    if tables and "alembic_version" not in tables:
        logger.info("Existing schema detected without Alembic version; stamping head.")
        Base.metadata.create_all(bind=engine)
        command.stamp(cfg, "head")
        return

    try:
        command.upgrade(cfg, "head")
        # Ensure newly added models exist even if an older DB was stamped ahead.
        Base.metadata.create_all(bind=engine)
    except Exception:
        # Fallback for first boot if alembic env cannot run for any reason.
        logger.exception("Alembic upgrade failed; falling back to metadata.create_all")
        Base.metadata.create_all(bind=engine)
        with engine.begin() as conn:
            if "alembic_version" not in inspect(engine).get_table_names():
                conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
            conn.execute(text("DELETE FROM alembic_version"))
            conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('20261111_0002')"))
