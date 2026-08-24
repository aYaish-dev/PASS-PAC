from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finding import Finding
from app.schemas.finding import FindingUpdate
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


def update_finding(
    db: Session,
    finding_id: int,
    payload: FindingUpdate,
) -> Finding:
    finding = get_finding_or_404(db, finding_id)
    changes = payload.model_dump(exclude_unset=True)
    if "review_status" in changes and changes["review_status"] is not None:
        finding.review_status = changes["review_status"]
    if "analyst_notes" in changes:
        notes = changes["analyst_notes"]
        finding.analyst_notes = notes.strip() if notes and notes.strip() else None
    if changes:
        finding.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(finding)
    return finding
