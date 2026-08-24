from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.finding import FindingResponse, FindingUpdate
from app.services.finding_service import get_finding_or_404, list_findings, update_finding

router = APIRouter(prefix="/findings", tags=["findings"])


@router.get("", response_model=list[FindingResponse])
def read_findings(db: Session = Depends(get_db)) -> list[FindingResponse]:
    return list_findings(db)


@router.get("/{finding_id}", response_model=FindingResponse)
def read_finding(
    finding_id: int,
    db: Session = Depends(get_db),
) -> FindingResponse:
    return get_finding_or_404(db, finding_id)


@router.patch("/{finding_id}", response_model=FindingResponse)
def patch_finding(
    finding_id: int,
    payload: FindingUpdate,
    db: Session = Depends(get_db),
) -> FindingResponse:
    return update_finding(db, finding_id, payload)
