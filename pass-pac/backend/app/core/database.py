import time
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(get_settings().sqlalchemy_database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models.detected_card import DetectedCard  # noqa: F401
    from app.models.scan_session import ScanSession  # noqa: F401

    for attempt in range(1, 11):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except OperationalError:
            if attempt == 10:
                raise
            time.sleep(2)
