from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class EvidenceGapResponse(BaseModel):
    criterion_id: str
    criterion_name: str
    detail: str


class GuidedCardResponse(BaseModel):
    card_id: int
    card_type: str
    technology: str
    score: float | None
    score_lower_bound: int
    score_upper_bound: int
    coverage_percent: int
    policy_status: str
    critical_failure: bool
    evidence_gaps: list[EvidenceGapResponse]


class EvidenceRecommendationResponse(BaseModel):
    id: str
    rank: int
    priority: Literal["now", "next", "later"]
    category: str
    scope: str
    card_ids: list[int]
    title: str
    rationale: str
    expected_evidence: list[str]
    safety_tier: str
    action_type: Literal["recipe", "navigate", "manual"]
    recipe_key: str | None
    href: str | None
    target_workspace: str | None
    can_execute: bool
    blocking_reason: str | None


class GuidedEvidenceResponse(BaseModel):
    engine_version: str
    registry_version: str
    generated_at: datetime
    session_id: int
    policy_id: str
    overall_status: str
    card_count: int
    average_coverage_percent: float
    critical_path_count: int
    open_gap_count: int
    executable_recommendation_count: int
    cards: list[GuidedCardResponse]
    recommendations: list[EvidenceRecommendationResponse]
