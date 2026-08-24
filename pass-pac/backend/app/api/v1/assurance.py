from fastapi import APIRouter

from app.schemas.assurance import AssurancePolicyResponse
from app.services.assurance_service import list_assurance_policies

router = APIRouter(prefix="/assurance", tags=["assurance"])


@router.get("/policies", response_model=list[AssurancePolicyResponse])
def read_assurance_policies() -> list[AssurancePolicyResponse]:
    return list_assurance_policies()
