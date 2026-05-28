from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finding import Finding
from app.services.card_service import get_card_or_404
from app.services.session_service import get_session_or_404


def list_findings(db: Session) -> list[Finding]:
    statement = select(Finding).order_by(Finding.created_at.desc(), Finding.id.desc())
    return list(db.scalars(statement).all())


def get_finding_or_404(db: Session, finding_id: int) -> Finding:
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding {finding_id} was not found.",
        )
    return finding


def list_session_findings(db: Session, session_id: int) -> list[Finding]:
    get_session_or_404(db, session_id)
    statement = (
        select(Finding)
        .where(Finding.session_id == session_id)
        .order_by(Finding.created_at.desc(), Finding.id.desc())
    )
    return list(db.scalars(statement).all())


def list_card_findings(db: Session, card_id: int) -> list[Finding]:
    get_card_or_404(db, card_id)
    statement = (
        select(Finding)
        .where(Finding.card_id == card_id)
        .order_by(Finding.created_at.desc(), Finding.id.desc())
    )
    return list(db.scalars(statement).all())
