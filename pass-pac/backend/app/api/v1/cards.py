from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.card import CardResponse
from app.schemas.finding import FindingResponse
from app.services.card_service import get_card_or_404, list_cards
from app.services.finding_service import list_card_findings

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("", response_model=list[CardResponse])
def read_cards(db: Session = Depends(get_db)) -> list[CardResponse]:
    return list_cards(db)


@router.get("/{card_id}", response_model=CardResponse)
def read_card(card_id: int, db: Session = Depends(get_db)) -> CardResponse:
    return get_card_or_404(db, card_id)


@router.get("/{card_id}/findings", response_model=list[FindingResponse])
def read_card_findings(
    card_id: int,
    db: Session = Depends(get_db),
) -> list[FindingResponse]:
    return list_card_findings(db, card_id)
