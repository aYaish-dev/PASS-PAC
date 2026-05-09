from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.scan_session import ScanSession
from app.schemas.session import SessionCreate, SessionUpdate

STATUS_CREATED = "created"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"


def list_sessions(db: Session) -> list[ScanSession]:
    statement = select(ScanSession).order_by(
        ScanSession.created_at.desc(),
        ScanSession.id.desc(),
    )
    return list(db.scalars(statement).all())


def get_session_or_404(db: Session, session_id: int) -> ScanSession:
    session = db.get(ScanSession, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} was not found.",
        )
    return session


def create_session(db: Session, payload: SessionCreate) -> ScanSession:
    session = ScanSession(
        session_name=payload.session_name,
        description=payload.description,
        mode=payload.mode,
        status=STATUS_CREATED,
        environment=payload.environment,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def update_session(db: Session, session_id: int, payload: SessionUpdate) -> ScanSession:
    session = get_session_or_404(db, session_id)
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(session, field, value)

    db.commit()
    db.refresh(session)
    return session


def start_session(db: Session, session_id: int) -> ScanSession:
    session = get_session_or_404(db, session_id)
    if session.status != STATUS_CREATED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot start session with status '{session.status}'. "
                "Only sessions with status 'created' can be started."
            ),
        )

    session.status = STATUS_RUNNING
    session.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


def stop_session(db: Session, session_id: int) -> ScanSession:
    session = get_session_or_404(db, session_id)
    if session.status != STATUS_RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot stop session with status '{session.status}'. "
                "Only sessions with status 'running' can be stopped."
            ),
        )

    session.status = STATUS_COMPLETED
    session.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


def delete_session(db: Session, session_id: int) -> None:
    session = get_session_or_404(db, session_id)
    db.delete(session)
    db.commit()
