from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assurance_evidence import CardAssuranceEvidence
from app.schemas.assurance_evidence import CardAssuranceEvidenceUpsert
from app.services.card_service import get_card_or_404


def get_card_assurance_evidence(
    db: Session,
    card_id: int,
) -> CardAssuranceEvidence | None:
    get_card_or_404(db, card_id)
    return db.scalar(
        select(CardAssuranceEvidence).where(CardAssuranceEvidence.card_id == card_id)
    )


def upsert_card_assurance_evidence(
    db: Session,
    card_id: int,
    payload: CardAssuranceEvidenceUpsert,
) -> CardAssuranceEvidence:
    get_card_or_404(db, card_id)
    record = db.scalar(
        select(CardAssuranceEvidence).where(CardAssuranceEvidence.card_id == card_id)
    )
    values = payload.model_dump()
    if record is None:
        record = CardAssuranceEvidence(card_id=card_id, **values)
        db.add(record)
    else:
        for field, value in values.items():
            setattr(record, field, value)

    db.commit()
    db.refresh(record)
    return record


def delete_card_assurance_evidence(db: Session, card_id: int) -> bool:
    record = get_card_assurance_evidence(db, card_id)
    if record is None:
        return False
    db.delete(record)
    db.commit()
    return True
