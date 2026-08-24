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


class DatasetMatchDetail(BaseModel):
    field: str
    points: int
    observed: Any
    dataset: Any


class CardDatasetMatch(BaseModel):
    sample_index: int
    score: int
    confidence: str
    source: str
    dataset: str | None = None
    source_path: str | None = None
    source_file: str | None = None
    source_sha256: str | None = None
    card_type: str | None = None
    protocol: str | None = None
    uid: str | None = None
    risk_level: str | None = None
    match_reasons: list[str]
    match_details: list[DatasetMatchDetail]


class CardDatasetCorrelationResponse(BaseModel):
    scorer_version: str
    evaluated_samples: int
    observed_features: dict[str, Any]
    best_score: int
    confidence: str
    match_count: int
    matches: list[CardDatasetMatch]


class CredentialDifference(BaseModel):
    field: str
    target: Any
    observed: Any


class CredentialObservation(BaseModel):
    card_id: int
    session_id: int
    created_at: datetime
    source: str | None = None
    card_type: str
    protocol: str
    fingerprint: str
    matching_fields: list[str]
    differences: list[CredentialDifference]


class CardIntelligenceResponse(BaseModel):
    fingerprint_version: str
    card_id: int
    uid: str
    fingerprint: str
    observation_count: int
    session_count: int
    cross_session_duplicate: bool
    inconsistent_identity: bool
    non_unique_uid: bool
    risk_level: str
    confidence: str
    summary: str
    compared_fields: list[str]
    target_features: dict[str, Any]
    observations: list[CredentialObservation]
