from datetime import datetime
from typing import Any

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FindingReviewStatus = Literal[
    "open",
    "confirmed",
    "accepted",
    "false_positive",
    "resolved",
]


class FindingUpdate(BaseModel):
    review_status: FindingReviewStatus | None = None
    analyst_notes: str | None = Field(default=None, max_length=4000)


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
    review_status: FindingReviewStatus
    analyst_notes: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
