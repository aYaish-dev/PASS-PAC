from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SimulatedScanRequest(BaseModel):
    technology: str | None = Field(default=None, max_length=50)
    card_type: str | None = Field(default=None, max_length=120)
    source: str | None = Field(default=None, max_length=80)
    dataset: str | None = Field(default=None, max_length=120)
    file_type: str | None = Field(default=None, max_length=20)
    uid: str | None = Field(default=None, max_length=120)


class CardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    technology: str
    frequency: str
    card_type: str
    protocol: str
    uid: str
    risk_level: str
    normalized_data_json: dict[str, Any]
    raw_output_json: dict[str, Any]
    created_at: datetime
