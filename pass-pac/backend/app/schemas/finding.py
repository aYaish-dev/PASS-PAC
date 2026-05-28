from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    card_id: int
    title: str
    description: str
    risk_level: str
    recommendation: str
    evidence_json: dict[str, Any]
    created_at: datetime
