from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class AssessmentCreate(BaseModel):
    band: Literal["hf", "lf", "emv"] = "hf"


class AssessmentEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_run_id: int
    session_id: int
    sequence: int
    phase: str
    status: str
    title: str
    command: str | None
    message: str
    evidence_json: dict[str, Any]
    created_at: datetime


class AssessmentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    profile: str
    status: str
    detected_card_count: int
    summary_json: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    events: list[AssessmentEventResponse]
