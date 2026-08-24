from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ExperimentCondition = Literal["baseline", "post_remediation"]
BatchStatus = Literal["open", "completed"]
TrialOrientation = Literal["parallel", "perpendicular", "edge", "custom"]
PresentedFace = Literal["front", "back", "not_applicable"]
ClassificationResult = Literal["correct", "incorrect", "inconclusive"]
RFInterference = Literal["none", "low", "moderate", "high", "unknown"]


class ExperimentBatchCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    condition: ExperimentCondition = "baseline"
    authorization_reference: str = Field(..., min_length=1, max_length=160)
    operator_label: str = Field(..., min_length=1, max_length=80)
    location_label: str = Field(..., min_length=1, max_length=120)
    device_model: str = Field(..., min_length=1, max_length=120)
    client_version: str = Field(..., min_length=1, max_length=160)
    firmware_version: str = Field(..., min_length=1, max_length=160)
    antenna_configuration: str = Field(..., min_length=1, max_length=160)
    host_os: str = Field(..., min_length=1, max_length=120)
    command_profile: str = Field(
        default="read-only-identification-v1", min_length=1, max_length=120
    )
    environment_notes: str | None = Field(default=None, max_length=2000)


class ExperimentBatchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    condition: ExperimentCondition | None = None
    status: BatchStatus | None = None
    authorization_reference: str | None = Field(
        default=None, min_length=1, max_length=160
    )
    operator_label: str | None = Field(default=None, min_length=1, max_length=80)
    location_label: str | None = Field(default=None, min_length=1, max_length=120)
    device_model: str | None = Field(default=None, min_length=1, max_length=120)
    client_version: str | None = Field(default=None, min_length=1, max_length=160)
    firmware_version: str | None = Field(default=None, min_length=1, max_length=160)
    antenna_configuration: str | None = Field(
        default=None, min_length=1, max_length=160
    )
    host_os: str | None = Field(default=None, min_length=1, max_length=120)
    command_profile: str | None = Field(default=None, min_length=1, max_length=120)
    environment_notes: str | None = Field(default=None, max_length=2000)


class ExperimentBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    name: str
    condition: str
    status: str
    authorization_reference: str
    operator_label: str
    location_label: str
    device_model: str
    client_version: str
    firmware_version: str
    antenna_configuration: str
    host_os: str
    command_profile: str
    environment_notes: str | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MeasurementTrialCreate(BaseModel):
    batch_id: int = Field(..., gt=0)
    source_card_id: int | None = Field(default=None, gt=0)
    credential_alias: str = Field(..., min_length=1, max_length=80)
    technology_family: str | None = Field(default=None, min_length=1, max_length=80)
    card_family: str | None = Field(default=None, max_length=120)
    distance_cm: float = Field(..., ge=0, le=100)
    orientation: TrialOrientation = "parallel"
    presented_face: PresentedFace = "front"
    success: bool
    classification_result: ClassificationResult
    identification_duration_ms: int = Field(..., ge=0, le=3_600_000)
    metadata_fields_count: int = Field(default=0, ge=0, le=10_000)
    data_extracted_bytes: int | None = Field(default=None, ge=0, le=100_000_000)
    nearby_metal: bool = False
    rf_interference: RFInterference = "unknown"
    environment_notes: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)
    raw_evidence_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-fA-F]{64}$"
    )


class LiveMeasurementTrialCreate(BaseModel):
    batch_id: int = Field(..., gt=0)
    source_card_id: int = Field(..., gt=0)
    credential_alias: str = Field(..., min_length=1, max_length=80)
    band: Literal["hf", "lf"]
    distance_cm: float = Field(..., ge=0, le=100)
    orientation: TrialOrientation = "parallel"
    presented_face: PresentedFace = "front"
    nearby_metal: bool = False
    rf_interference: RFInterference = "none"
    environment_notes: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)


class MeasurementTrialUpdate(BaseModel):
    batch_id: int | None = Field(default=None, gt=0)
    source_card_id: int | None = Field(default=None, gt=0)
    credential_alias: str | None = Field(default=None, min_length=1, max_length=80)
    technology_family: str | None = Field(default=None, min_length=1, max_length=80)
    card_family: str | None = Field(default=None, max_length=120)
    distance_cm: float | None = Field(default=None, ge=0, le=100)
    orientation: TrialOrientation | None = None
    presented_face: PresentedFace | None = None
    success: bool | None = None
    classification_result: ClassificationResult | None = None
    identification_duration_ms: int | None = Field(
        default=None, ge=0, le=3_600_000
    )
    metadata_fields_count: int | None = Field(default=None, ge=0, le=10_000)
    data_extracted_bytes: int | None = Field(default=None, ge=0, le=100_000_000)
    nearby_metal: bool | None = None
    rf_interference: RFInterference | None = None
    environment_notes: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)
    raw_evidence_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-fA-F]{64}$"
    )


class MeasurementTrialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    batch_id: int
    source_card_id: int | None
    trial_number: int
    credential_alias: str
    technology_family: str
    card_family: str | None
    distance_cm: float
    orientation: str
    presented_face: str
    success: bool
    classification_result: str
    identification_duration_ms: int
    metadata_fields_count: int
    data_extracted_bytes: int | None
    nearby_metal: bool
    rf_interference: str
    environment_notes: str | None
    notes: str | None
    raw_evidence_sha256: str | None
    created_at: datetime
    updated_at: datetime


class LiveMeasurementTrialResponse(BaseModel):
    trial: MeasurementTrialResponse
    command: str
    detected: bool
    observed_card_type: str | None
    observed_uid: str | None
    uid_match: bool | None
    evidence_path: str | None
    message: str


class TimingStatistics(BaseModel):
    count: int
    minimum_ms: float | None
    maximum_ms: float | None
    median_ms: float | None
    q1_ms: float | None
    q3_ms: float | None


class ReliableDistanceResult(BaseModel):
    credential_alias: str
    technology_family: str
    orientation: str
    presented_face: str
    reliable_distance_cm: float
    attempts: int
    successes: int


class TechnologyMeasurementSummary(BaseModel):
    technology_family: str
    trial_count: int
    unique_credentials: int
    successful_trials: int
    detection_success_rate: float
    classified_trials: int
    correct_classifications: int
    classification_accuracy: float | None
    timing: TimingStatistics
    average_metadata_fields: float
    total_extracted_bytes: int


class MeasurementSummaryResponse(BaseModel):
    methodology_version: str
    session_id: int
    batch_count: int
    trial_count: int
    unique_credentials: int
    successful_trials: int
    detection_success_rate: float
    classified_trials: int
    correct_classifications: int
    classification_accuracy: float | None
    timing: TimingStatistics
    reliable_distances: list[ReliableDistanceResult]
    technologies: list[TechnologyMeasurementSummary]


class ProportionStatistics(BaseModel):
    events: int
    attempts: int
    rate_percent: float
    ci_lower_percent: float
    ci_upper_percent: float


class MeasurementConditionAnalysis(BaseModel):
    credential_alias: str
    source_card_id: int | None
    technology_family: str
    card_family: str | None
    distance_cm: float
    orientation: str
    presented_face: str
    detection: ProportionStatistics
    correct_identification: ProportionStatistics
    partial_response_count: int
    incorrect_classification_count: int
    inconclusive_count: int
    correct_identification_timing: TimingStatistics
    meets_minimum_repetitions: bool


class CredentialMeasurementAnalysis(BaseModel):
    credential_alias: str
    source_card_id: int | None
    technology_family: str
    card_family: str | None
    trial_count: int
    condition_count: int
    maximum_tested_distance_cm: float
    reliable_identification_distance_cm: float | None
    detection: ProportionStatistics
    correct_identification: ProportionStatistics
    partial_response_count: int
    correct_identification_timing: TimingStatistics


class MeasurementQualityFlag(BaseModel):
    id: str
    severity: Literal["info", "warning", "high"]
    category: str
    scope: str
    title: str
    detail: str


class MeasurementAnalysisResponse(BaseModel):
    analysis_version: str
    methodology_version: str
    session_id: int
    batch_id: int | None
    confidence_level_percent: float
    interval_method: str
    minimum_attempts_per_condition: int
    trial_count: int
    credential_count: int
    condition_count: int
    credentials: list[CredentialMeasurementAnalysis]
    conditions: list[MeasurementConditionAnalysis]
    quality_flags: list[MeasurementQualityFlag]
    interpretation: list[str]


class ReliableDistanceChange(BaseModel):
    credential_alias: str
    technology_family: str
    orientation: str
    presented_face: str
    baseline_distance_cm: float | None
    post_remediation_distance_cm: float | None
    delta_cm: float | None


class MeasurementComparisonResponse(BaseModel):
    methodology_version: str
    session_id: int
    baseline_batch: ExperimentBatchResponse
    post_remediation_batch: ExperimentBatchResponse
    baseline_summary: MeasurementSummaryResponse
    post_remediation_summary: MeasurementSummaryResponse
    detection_rate_delta: float
    classification_accuracy_delta: float | None
    median_duration_delta_ms: float | None
    trial_count_delta: int
    unique_credentials_delta: int
    reliable_distance_changes: list[ReliableDistanceChange]
    interpretation: list[str]
