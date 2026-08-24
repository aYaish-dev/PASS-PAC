from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

AssuranceOutcome = Literal["pass", "partial", "fail", "unknown"]
PolicyStatus = Literal["pass", "fail", "insufficient_evidence"]
ReviewStatus = Literal["not_started", "in_progress", "complete"]


class AssuranceCriterionDefinition(BaseModel):
    id: str
    name: str
    description: str
    max_points: int
    levels: dict[str, str]


class AssurancePolicyResponse(BaseModel):
    id: str
    name: str
    version: str
    description: str
    use_case: str
    strictness: str
    minimum_score: float
    minimum_coverage_percent: int
    reject_critical_failures: bool
    criteria: list[AssuranceCriterionDefinition]


class AssuranceCriterionResult(BaseModel):
    id: str
    name: str
    outcome: AssuranceOutcome
    rating: int | None
    max_points: int
    critical: bool
    summary: str
    evidence: list[str]
    recommendations: list[str]


class AnalystReviewSummary(BaseModel):
    status: ReviewStatus
    finding_count: int
    active_finding_count: int
    reviewed_finding_count: int
    unresolved_high_count: int


class CardAssuranceResponse(BaseModel):
    engine_version: str
    methodology_version: str
    evaluated_at: datetime
    policy: AssurancePolicyResponse
    card_id: int
    credential_score: float | None
    credential_coverage_percent: int
    credential_grade: str
    credential_grade_label: str
    score: float | None
    scale_max: int
    score_lower_bound: int
    score_upper_bound: int
    unknown_criteria_count: int
    grade: str
    grade_label: str
    coverage_percent: int
    confidence: str
    policy_status: PolicyStatus
    meets_policy: bool | None
    critical_failure: bool
    summary: str
    criteria: list[AssuranceCriterionResult]
    recommendations: list[str]
    analyst_review: AnalystReviewSummary
    evidence_snapshot: dict[str, Any]


class SessionCardAssuranceSummary(BaseModel):
    card_id: int
    uid: str
    card_type: str
    credential_score: float | None
    credential_coverage_percent: int
    credential_grade: str
    credential_grade_label: str
    score: float | None
    score_lower_bound: int
    score_upper_bound: int
    grade: str
    grade_label: str
    coverage_percent: int
    confidence: str
    policy_status: PolicyStatus
    critical_failure: bool


class SessionAssuranceResponse(BaseModel):
    engine_version: str
    methodology_version: str
    evaluated_at: datetime
    policy: AssurancePolicyResponse
    session_id: int
    card_count: int
    average_score: float | None
    lowest_score: float | None
    critical_failure_count: int
    insufficient_evidence_count: int
    grade_counts: dict[str, int]
    policy_status_counts: dict[str, int]
    summary: str
    cards: list[SessionCardAssuranceSummary]
