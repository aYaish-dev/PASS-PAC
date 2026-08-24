import time
from collections.abc import Generator

from sqlalchemy import create_engine, text
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
    from app.models.assessment import AssessmentEvent, AssessmentRun  # noqa: F401
    from app.models.assurance_evidence import CardAssuranceEvidence  # noqa: F401
    from app.models.detected_card import DetectedCard  # noqa: F401
    from app.models.finding import Finding  # noqa: F401
    from app.models.measurement import ExperimentBatch, MeasurementTrial  # noqa: F401
    from app.models.operator_command import OperatorCommand  # noqa: F401
    from app.models.scan_session import ScanSession  # noqa: F401
    from app.models.transaction_trace import TransactionTrace  # noqa: F401

    for attempt in range(1, 11):
        try:
            Base.metadata.create_all(bind=engine)
            _upgrade_existing_postgresql_schema()
            return
        except OperationalError:
            if attempt == 10:
                raise
            time.sleep(2)


def _upgrade_existing_postgresql_schema() -> None:
    if engine.dialect.name != "postgresql":
        return

    statements = (
        "ALTER TABLE findings ADD COLUMN IF NOT EXISTS review_status VARCHAR(40) NOT NULL DEFAULT 'open'",
        "ALTER TABLE findings ADD COLUMN IF NOT EXISTS analyst_notes TEXT",
        "ALTER TABLE findings ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ",
        "ALTER TABLE findings ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "CREATE INDEX IF NOT EXISTS ix_findings_review_status ON findings (review_status)",
    )
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
