from typing import Any

from pydantic import BaseModel


class CardProfileFinding(BaseModel):
    level: str
    title: str
    detail: str


class DatasetMatch(BaseModel):
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
    match_details: list[dict[str, Any]]


class CardProfile(BaseModel):
    profile_id: str
    first_seen: str
    last_seen: str
    observation_count: int
    technology: str
    card_type: str | None = None
    protocol: str | None = None
    uid: str | None = None
    atqa: str | None = None
    sak: str | None = None
    fields: dict[str, str]
    attention_level: str
    findings: list[CardProfileFinding]
    dataset_matches: list[DatasetMatch]
    raw_output_preview: str


class CardProfileSummary(BaseModel):
    total_observations: int
    total_profiles: int
    hf_profiles: int
    lf_profiles: int
    dataset_samples: int
    dataset_matched_profiles: int
    medium_attention_profiles: int
    high_attention_profiles: int


class CardProfileReviewResponse(BaseModel):
    summary: CardProfileSummary
    profiles: list[CardProfile]
