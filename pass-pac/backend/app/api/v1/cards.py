from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.card import (
    CardDatasetCorrelationResponse,
    CardIntelligenceResponse,
    CardResponse,
)
from app.schemas.card_profiles import CardProfileReviewResponse
from app.schemas.assurance import CardAssuranceResponse
from app.schemas.assurance_evidence import (
    CardAssuranceEvidenceResponse,
    CardAssuranceEvidenceUpsert,
)
from app.schemas.finding import FindingResponse
from app.services.card_service import (
    get_card_dataset_correlation,
    get_card_or_404,
    list_cards,
)
from app.services.card_profile_review import build_card_profile_review
from app.services.credential_intelligence import build_card_intelligence
from app.services.finding_service import list_card_findings
from app.services.assurance_service import evaluate_card_assurance
from app.services.assurance_evidence_service import (
    delete_card_assurance_evidence,
    get_card_assurance_evidence,
    upsert_card_assurance_evidence,
)

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/profiles", response_model=CardProfileReviewResponse)
def read_card_profiles() -> CardProfileReviewResponse:
    settings = get_settings()
    review = build_card_profile_review(settings.mock_data_dir)
    return CardProfileReviewResponse.model_validate(review)


@router.get("", response_model=list[CardResponse])
def read_cards(db: Session = Depends(get_db)) -> list[CardResponse]:
    return list_cards(db)


@router.get("/{card_id}", response_model=CardResponse)
def read_card(card_id: int, db: Session = Depends(get_db)) -> CardResponse:
    return get_card_or_404(db, card_id)


@router.get(
    "/{card_id}/dataset-correlation",
    response_model=CardDatasetCorrelationResponse,
)
def read_card_dataset_correlation(
    card_id: int,
    db: Session = Depends(get_db),
) -> CardDatasetCorrelationResponse:
    return get_card_dataset_correlation(db, card_id)


@router.get(
    "/{card_id}/intelligence",
    response_model=CardIntelligenceResponse,
)
def read_card_intelligence(
    card_id: int,
    db: Session = Depends(get_db),
) -> CardIntelligenceResponse:
    return build_card_intelligence(db, card_id)


@router.get(
    "/{card_id}/assurance",
    response_model=CardAssuranceResponse,
)
def read_card_assurance(
    card_id: int,
    policy_id: str = Query(default="university-standard"),
    db: Session = Depends(get_db),
) -> CardAssuranceResponse:
    return evaluate_card_assurance(db, card_id, policy_id)


@router.get(
    "/{card_id}/assurance-evidence",
    response_model=CardAssuranceEvidenceResponse | None,
)
def read_card_assurance_evidence(
    card_id: int,
    db: Session = Depends(get_db),
) -> CardAssuranceEvidenceResponse | None:
    return get_card_assurance_evidence(db, card_id)


@router.put(
    "/{card_id}/assurance-evidence",
    response_model=CardAssuranceEvidenceResponse,
)
def write_card_assurance_evidence(
    card_id: int,
    payload: CardAssuranceEvidenceUpsert,
    db: Session = Depends(get_db),
) -> CardAssuranceEvidenceResponse:
    return upsert_card_assurance_evidence(db, card_id, payload)


@router.delete(
    "/{card_id}/assurance-evidence",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_card_assurance_evidence(
    card_id: int,
    db: Session = Depends(get_db),
) -> Response:
    delete_card_assurance_evidence(db, card_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{card_id}/findings", response_model=list[FindingResponse])
def read_card_findings(
    card_id: int,
    db: Session = Depends(get_db),
) -> list[FindingResponse]:
    return list_card_findings(db, card_id)
