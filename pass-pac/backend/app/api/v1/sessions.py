from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.assessment import AssessmentCreate, AssessmentRunResponse
from app.schemas.assurance import SessionAssuranceResponse
from app.schemas.card import CardResponse, SimulatedScanRequest
from app.schemas.finding import FindingResponse
from app.schemas.measurement import (
    ExperimentBatchCreate,
    ExperimentBatchResponse,
    ExperimentBatchUpdate,
    LiveMeasurementTrialCreate,
    LiveMeasurementTrialResponse,
    MeasurementAnalysisResponse,
    MeasurementSummaryResponse,
    MeasurementComparisonResponse,
    MeasurementTrialCreate,
    MeasurementTrialResponse,
    MeasurementTrialUpdate,
)
from app.schemas.operator_command import (
    CapabilityRegistryResponse,
    OperatorCommandCreate,
    OperatorCommandResponse,
    OperatorRecipeResponse,
    OperatorRecipeRunResponse,
)
from app.schemas.evidence_guidance import GuidedEvidenceResponse
from app.schemas.session import SessionCreate, SessionResponse, SessionUpdate
from app.schemas.transaction_trace import (
    TraceAnalyzeRequest,
    TraceBufferRequest,
    TransactionTraceResponse,
    TransactionTraceSummaryResponse,
)
from app.services.card_service import list_session_cards, run_simulated_scan
from app.services.assessment_service import (
    execute_queued_assessment,
    get_assessment_or_404,
    list_assessments,
    queue_assessment,
)
from app.services.finding_service import list_session_findings
from app.services.measurement_service import (
    analyze_measurements,
    create_experiment_batch,
    create_measurement_trial,
    compare_measurement_batches,
    delete_measurement_trial,
    list_experiment_batches,
    list_measurement_trials,
    run_live_measurement_trial,
    summarize_measurements,
    update_experiment_batch,
    update_measurement_trial,
)
from app.services.operator_command_service import (
    list_operator_commands,
    list_operator_recipes,
    run_operator_command,
    run_operator_recipe,
)
from app.services.report_service import (
    generate_measurement_analysis_csv,
    generate_measurement_csv,
    generate_measurement_pdf,
)
from app.services.session_service import (
    create_session,
    delete_session,
    get_session_or_404,
    list_sessions,
    start_session,
    stop_session,
    update_session,
)
from app.services.assurance_service import evaluate_session_assurance
from app.services.evidence_guidance_service import build_evidence_guidance
from app.core.proxmark_capabilities import public_capability_registry
from app.services.transaction_trace_service import (
    analyze_device_trace_buffer,
    analyze_imported_trace,
    delete_transaction_trace,
    get_transaction_trace_or_404,
    list_transaction_traces,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionResponse])
def read_sessions(db: Session = Depends(get_db)) -> list[SessionResponse]:
    return list_sessions(db)


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_new_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
) -> SessionResponse:
    return create_session(db, payload)


@router.get("/{session_id}", response_model=SessionResponse)
def read_session(session_id: int, db: Session = Depends(get_db)) -> SessionResponse:
    return get_session_or_404(db, session_id)


@router.patch("/{session_id}", response_model=SessionResponse)
def patch_session(
    session_id: int,
    payload: SessionUpdate,
    db: Session = Depends(get_db),
) -> SessionResponse:
    return update_session(db, session_id, payload)


@router.post("/{session_id}/start", response_model=SessionResponse)
def start_existing_session(
    session_id: int,
    db: Session = Depends(get_db),
) -> SessionResponse:
    return start_session(db, session_id)


@router.post("/{session_id}/stop", response_model=SessionResponse)
def stop_existing_session(
    session_id: int,
    db: Session = Depends(get_db),
) -> SessionResponse:
    return stop_session(db, session_id)


@router.get(
    "/{session_id}/assessments",
    response_model=list[AssessmentRunResponse],
)
def read_session_assessments(
    session_id: int,
    db: Session = Depends(get_db),
) -> list[AssessmentRunResponse]:
    return list_assessments(db, session_id)


@router.post(
    "/{session_id}/assessments",
    response_model=AssessmentRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_automated_assessment(
    session_id: int,
    background_tasks: BackgroundTasks,
    payload: Annotated[AssessmentCreate | None, Body()] = None,
    db: Session = Depends(get_db),
) -> AssessmentRunResponse:
    assessment = queue_assessment(db, session_id, band=payload.band if payload else "hf")
    background_tasks.add_task(execute_queued_assessment, assessment.id)
    return assessment


@router.get(
    "/{session_id}/assessments/{assessment_id}",
    response_model=AssessmentRunResponse,
)
def read_session_assessment(
    session_id: int,
    assessment_id: int,
    db: Session = Depends(get_db),
) -> AssessmentRunResponse:
    return get_assessment_or_404(db, session_id, assessment_id)


@router.post(
    "/{session_id}/scan/simulate",
    response_model=CardResponse,
    status_code=status.HTTP_201_CREATED,
)
def simulate_scan_for_session(
    session_id: int,
    payload: Annotated[SimulatedScanRequest | None, Body()] = None,
    db: Session = Depends(get_db),
) -> CardResponse:
    return run_simulated_scan(db, session_id, payload)


@router.get("/{session_id}/cards", response_model=list[CardResponse])
def read_session_cards(
    session_id: int,
    db: Session = Depends(get_db),
) -> list[CardResponse]:
    return list_session_cards(db, session_id)


@router.get("/{session_id}/findings", response_model=list[FindingResponse])
def read_session_findings(
    session_id: int,
    db: Session = Depends(get_db),
) -> list[FindingResponse]:
    return list_session_findings(db, session_id)


@router.get(
    "/{session_id}/assurance",
    response_model=SessionAssuranceResponse,
)
def read_session_assurance(
    session_id: int,
    policy_id: str = Query(default="university-standard"),
    db: Session = Depends(get_db),
) -> SessionAssuranceResponse:
    return evaluate_session_assurance(db, session_id, policy_id)


@router.get(
    "/{session_id}/evidence-guidance",
    response_model=GuidedEvidenceResponse,
)
def read_session_evidence_guidance(
    session_id: int,
    policy_id: str = Query(default="university-standard"),
    db: Session = Depends(get_db),
) -> GuidedEvidenceResponse:
    return build_evidence_guidance(db, session_id, policy_id)


@router.get(
    "/{session_id}/capabilities",
    response_model=CapabilityRegistryResponse,
)
def read_session_capabilities(
    session_id: int,
    db: Session = Depends(get_db),
) -> CapabilityRegistryResponse:
    get_session_or_404(db, session_id)
    return public_capability_registry()


@router.get(
    "/{session_id}/experiment-batches",
    response_model=list[ExperimentBatchResponse],
)
def read_session_experiment_batches(
    session_id: int,
    db: Session = Depends(get_db),
) -> list[ExperimentBatchResponse]:
    return list_experiment_batches(db, session_id)


@router.post(
    "/{session_id}/experiment-batches",
    response_model=ExperimentBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_session_experiment_batch(
    session_id: int,
    payload: ExperimentBatchCreate,
    db: Session = Depends(get_db),
) -> ExperimentBatchResponse:
    return create_experiment_batch(db, session_id, payload)


@router.patch(
    "/{session_id}/experiment-batches/{batch_id}",
    response_model=ExperimentBatchResponse,
)
def patch_session_experiment_batch(
    session_id: int,
    batch_id: int,
    payload: ExperimentBatchUpdate,
    db: Session = Depends(get_db),
) -> ExperimentBatchResponse:
    return update_experiment_batch(db, session_id, batch_id, payload)


@router.get(
    "/{session_id}/measurement-trials",
    response_model=list[MeasurementTrialResponse],
)
def read_session_measurement_trials(
    session_id: int,
    batch_id: int | None = Query(default=None),
    credential_alias: str | None = Query(default=None),
    technology_family: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[MeasurementTrialResponse]:
    return list_measurement_trials(
        db,
        session_id,
        batch_id=batch_id,
        credential_alias=credential_alias,
        technology_family=technology_family,
    )


@router.post(
    "/{session_id}/measurement-trials",
    response_model=MeasurementTrialResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_session_measurement_trial(
    session_id: int,
    payload: MeasurementTrialCreate,
    db: Session = Depends(get_db),
) -> MeasurementTrialResponse:
    return create_measurement_trial(db, session_id, payload)


@router.post(
    "/{session_id}/measurement-trials/live",
    response_model=LiveMeasurementTrialResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_session_live_measurement_trial(
    session_id: int,
    payload: LiveMeasurementTrialCreate,
    db: Session = Depends(get_db),
) -> LiveMeasurementTrialResponse:
    return run_live_measurement_trial(db, session_id, payload)


@router.patch(
    "/{session_id}/measurement-trials/{trial_id}",
    response_model=MeasurementTrialResponse,
)
def patch_session_measurement_trial(
    session_id: int,
    trial_id: int,
    payload: MeasurementTrialUpdate,
    db: Session = Depends(get_db),
) -> MeasurementTrialResponse:
    return update_measurement_trial(db, session_id, trial_id, payload)


@router.delete(
    "/{session_id}/measurement-trials/{trial_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_session_measurement_trial(
    session_id: int,
    trial_id: int,
    db: Session = Depends(get_db),
) -> Response:
    delete_measurement_trial(db, session_id, trial_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{session_id}/measurement-summary",
    response_model=MeasurementSummaryResponse,
)
def read_session_measurement_summary(
    session_id: int,
    db: Session = Depends(get_db),
) -> MeasurementSummaryResponse:
    return summarize_measurements(db, session_id)


@router.get(
    "/{session_id}/measurement-analysis",
    response_model=MeasurementAnalysisResponse,
)
def read_session_measurement_analysis(
    session_id: int,
    batch_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
) -> MeasurementAnalysisResponse:
    return analyze_measurements(db, session_id, batch_id=batch_id)


@router.get(
    "/{session_id}/measurement-comparison",
    response_model=MeasurementComparisonResponse,
)
def read_session_measurement_comparison(
    session_id: int,
    baseline_batch_id: int = Query(..., gt=0),
    post_remediation_batch_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> MeasurementComparisonResponse:
    return compare_measurement_batches(
        db,
        session_id,
        baseline_batch_id,
        post_remediation_batch_id,
    )


@router.post("/{session_id}/reports/measurements.csv", response_class=FileResponse)
def export_session_measurements_csv(
    session_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    artifact = generate_measurement_csv(db, session_id)
    return FileResponse(
        artifact.path,
        media_type=artifact.content_type,
        filename=artifact.filename,
        headers={"X-PASS-PAC-SHA256": artifact.sha256},
    )


@router.post(
    "/{session_id}/reports/measurement-analysis.csv",
    response_class=FileResponse,
)
def export_session_measurement_analysis_csv(
    session_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    artifact = generate_measurement_analysis_csv(db, session_id)
    return FileResponse(
        artifact.path,
        media_type=artifact.content_type,
        filename=artifact.filename,
        headers={"X-PASS-PAC-SHA256": artifact.sha256},
    )


@router.post("/{session_id}/reports/research-report.pdf", response_class=FileResponse)
def export_session_research_pdf(
    session_id: int,
    baseline_batch_id: int | None = Query(default=None, gt=0),
    post_remediation_batch_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
) -> FileResponse:
    if (baseline_batch_id is None) != (post_remediation_batch_id is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Select both a baseline and post-remediation batch, or omit both."
            ),
        )
    artifact = generate_measurement_pdf(
        db,
        session_id,
        baseline_batch_id=baseline_batch_id,
        post_remediation_batch_id=post_remediation_batch_id,
    )
    return FileResponse(
        artifact.path,
        media_type=artifact.content_type,
        filename=artifact.filename,
        headers={"X-PASS-PAC-SHA256": artifact.sha256},
    )


@router.get(
    "/{session_id}/traces",
    response_model=list[TransactionTraceSummaryResponse],
)
def read_session_transaction_traces(
    session_id: int,
    db: Session = Depends(get_db),
) -> list[TransactionTraceSummaryResponse]:
    return list_transaction_traces(db, session_id)


@router.post(
    "/{session_id}/traces",
    response_model=TransactionTraceResponse,
    status_code=status.HTTP_201_CREATED,
)
def analyze_session_transaction_trace(
    session_id: int,
    payload: TraceAnalyzeRequest,
    db: Session = Depends(get_db),
) -> TransactionTraceResponse:
    return analyze_imported_trace(db, session_id, payload)


@router.post(
    "/{session_id}/traces/device-buffer",
    response_model=TransactionTraceResponse,
    status_code=status.HTTP_201_CREATED,
)
def analyze_session_device_trace_buffer(
    session_id: int,
    payload: TraceBufferRequest,
    db: Session = Depends(get_db),
) -> TransactionTraceResponse:
    return analyze_device_trace_buffer(db, session_id, payload)


@router.get(
    "/{session_id}/traces/{trace_id}",
    response_model=TransactionTraceResponse,
)
def read_session_transaction_trace(
    session_id: int,
    trace_id: int,
    db: Session = Depends(get_db),
) -> TransactionTraceResponse:
    return get_transaction_trace_or_404(db, session_id, trace_id)


@router.delete(
    "/{session_id}/traces/{trace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_session_transaction_trace(
    session_id: int,
    trace_id: int,
    db: Session = Depends(get_db),
) -> Response:
    delete_transaction_trace(db, session_id, trace_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{session_id}/commands",
    response_model=list[OperatorCommandResponse],
)
def read_session_operator_commands(
    session_id: int,
    db: Session = Depends(get_db),
) -> list[OperatorCommandResponse]:
    return list_operator_commands(db, session_id)


@router.post(
    "/{session_id}/commands",
    response_model=OperatorCommandResponse,
    status_code=status.HTTP_201_CREATED,
)
def execute_session_operator_command(
    session_id: int,
    payload: OperatorCommandCreate,
    db: Session = Depends(get_db),
) -> OperatorCommandResponse:
    return run_operator_command(db, session_id, payload)


@router.get(
    "/{session_id}/recipes",
    response_model=list[OperatorRecipeResponse],
)
def read_session_operator_recipes(
    session_id: int,
    db: Session = Depends(get_db),
) -> list[OperatorRecipeResponse]:
    return list_operator_recipes(db, session_id)


@router.post(
    "/{session_id}/recipes/{recipe_key}",
    response_model=OperatorRecipeRunResponse,
)
def execute_session_operator_recipe(
    session_id: int,
    recipe_key: str,
    db: Session = Depends(get_db),
) -> OperatorRecipeRunResponse:
    return run_operator_recipe(db, session_id, recipe_key)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_session(session_id: int, db: Session = Depends(get_db)) -> Response:
    delete_session(db, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
