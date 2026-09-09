from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.models import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine(settings: Settings) -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    return _engine


def get_session_factory(settings: Settings) -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(settings), autoflush=False, autocommit=False, future=True)
    return _session_factory


def session_scope(settings: Settings) -> Generator[Session, None, None]:
    factory = get_session_factory(settings)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ping_database(settings: Settings) -> bool:
    try:
        with get_engine(settings).connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def metadata() -> type[Base]:
    return Base
