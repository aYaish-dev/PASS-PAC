from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ReaderEnforcementState = Literal["uid_only", "partial", "cryptographic"]
LifecycleMonitoringState = Literal["absent", "partial", "managed"]
EvidenceConfidence = Literal["low", "medium", "high"]


class CardAssuranceEvidenceUpsert(BaseModel):
    reader_enforcement: ReaderEnforcementState | None = None
    lifecycle_monitoring: LifecycleMonitoringState | None = None
    evidence_source: str = Field(min_length=2, max_length=300)
    confidence: EvidenceConfidence = "medium"
    notes: str | None = Field(default=None, max_length=4000)
    assessed_at: datetime

    @model_validator(mode="after")
    def require_a_control_state(self) -> "CardAssuranceEvidenceUpsert":
        if self.reader_enforcement is None and self.lifecycle_monitoring is None:
            raise ValueError("Select at least one reader or lifecycle control state.")
        return self


class CardAssuranceEvidenceResponse(BaseModel):
    id: int
    card_id: int
    reader_enforcement: ReaderEnforcementState | None
    lifecycle_monitoring: LifecycleMonitoringState | None
    evidence_source: str
    confidence: EvidenceConfidence
    notes: str | None
    assessed_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
