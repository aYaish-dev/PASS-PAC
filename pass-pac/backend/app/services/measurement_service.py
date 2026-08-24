from __future__ import annotations

import hashlib
import json
import re
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from statistics import median
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.proxmark_adapter import ProxmarkAdapter, ProxmarkIdentifyResult
from app.core.config import get_settings
from app.models.detected_card import DetectedCard
from app.models.measurement import ExperimentBatch, MeasurementTrial
from app.schemas.measurement import (
    ExperimentBatchCreate,
    ExperimentBatchUpdate,
    LiveMeasurementTrialCreate,
    MeasurementTrialCreate,
    MeasurementTrialUpdate,
)
from app.services.device_lock import proxmark_device_lock
from app.services.observation_store import append_live_card_observation
from app.services.session_service import STATUS_RUNNING, get_session_or_404

METHODOLOGY_VERSION = "controlled-measurement-v1.0"
ANALYSIS_VERSION = "measurement-analysis-v1.0"
CONFIDENCE_LEVEL_PERCENT = 95.0
MINIMUM_CONDITION_ATTEMPTS = 5


def list_experiment_batches(db: Session, session_id: int) -> list[ExperimentBatch]:
    get_session_or_404(db, session_id)
    statement = (
        select(ExperimentBatch)
        .where(ExperimentBatch.session_id == session_id)
        .order_by(ExperimentBatch.created_at.desc(), ExperimentBatch.id.desc())
    )
    return list(db.scalars(statement).all())


def create_experiment_batch(
    db: Session,
    session_id: int,
    payload: ExperimentBatchCreate,
) -> ExperimentBatch:
    get_session_or_404(db, session_id)
    batch = ExperimentBatch(
        session_id=session_id,
        **_clean_strings(payload.model_dump()),
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def get_experiment_batch_or_404(
    db: Session,
    session_id: int,
    batch_id: int,
) -> ExperimentBatch:
    statement = select(ExperimentBatch).where(
        ExperimentBatch.id == batch_id,
        ExperimentBatch.session_id == session_id,
    )
    batch = db.scalar(statement)
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment batch {batch_id} was not found in session {session_id}.",
        )
    return batch


def update_experiment_batch(
    db: Session,
    session_id: int,
    batch_id: int,
    payload: ExperimentBatchUpdate,
) -> ExperimentBatch:
    batch = get_experiment_batch_or_404(db, session_id, batch_id)
    changes = _clean_strings(payload.model_dump(exclude_unset=True))
    requested_status = changes.get("status")

    if requested_status == "completed" and batch.status != "completed":
        changes["completed_at"] = datetime.now(timezone.utc)
    elif requested_status == "open" and batch.status == "completed":
        changes["completed_at"] = None

    for field, value in changes.items():
        setattr(batch, field, value)

    db.commit()
    db.refresh(batch)
    return batch


def list_measurement_trials(
    db: Session,
    session_id: int,
    *,
    batch_id: int | None = None,
    credential_alias: str | None = None,
    technology_family: str | None = None,
) -> list[MeasurementTrial]:
    get_session_or_404(db, session_id)
    statement = select(MeasurementTrial).where(
        MeasurementTrial.session_id == session_id
    )
    if batch_id is not None:
        statement = statement.where(MeasurementTrial.batch_id == batch_id)
    if credential_alias:
        statement = statement.where(
            MeasurementTrial.credential_alias == credential_alias.strip()
        )
    if technology_family:
        statement = statement.where(
            MeasurementTrial.technology_family == technology_family.strip()
        )
    statement = statement.order_by(
        MeasurementTrial.created_at.desc(), MeasurementTrial.id.desc()
    )
    return list(db.scalars(statement).all())


def create_measurement_trial(
    db: Session,
    session_id: int,
    payload: MeasurementTrialCreate,
) -> MeasurementTrial:
    get_session_or_404(db, session_id)
    batch = get_experiment_batch_or_404(db, session_id, payload.batch_id)
    if batch.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reopen the completed experiment batch before adding trials.",
        )

    values = _clean_strings(payload.model_dump())
    source_card = _resolve_source_card(db, session_id, payload.source_card_id)
    _enrich_from_source_card(values, source_card)

    technology = values.get("technology_family")
    if not technology:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Technology family is required when no source card observation is linked.",
        )

    alias = values["credential_alias"]
    highest_trial = db.scalar(
        select(func.max(MeasurementTrial.trial_number)).where(
            MeasurementTrial.session_id == session_id,
            MeasurementTrial.credential_alias == alias,
        )
    )
    trial = MeasurementTrial(
        session_id=session_id,
        trial_number=(highest_trial or 0) + 1,
        **values,
    )
    db.add(trial)
    db.commit()
    db.refresh(trial)
    return trial


def run_live_measurement_trial(
    db: Session,
    session_id: int,
    payload: LiveMeasurementTrialCreate,
    adapter_factory: Callable[[], ProxmarkAdapter] | None = None,
    clock: Callable[[], int] = time.perf_counter_ns,
) -> dict[str, Any]:
    session = get_session_or_404(db, session_id)
    if session.status != STATUS_RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start the Proxmark session before running a live measurement trial.",
        )
    if session.mode not in {"proxmark", "live"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Live measurement trials require a Proxmark session.",
        )

    batch = get_experiment_batch_or_404(db, session_id, payload.batch_id)
    if batch.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reopen the completed experiment batch before running trials.",
        )
    source_card = _resolve_source_card(db, session_id, payload.source_card_id)
    if source_card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A reference card observation is required for a live trial.",
        )
    if not _band_matches_card(payload.band, source_card):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"The selected reference card is {source_card.technology}; "
                f"choose the matching {payload.band.upper()} band."
            ),
        )

    if not proxmark_device_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The Proxmark device is already in use by another workflow.",
        )
    try:
        adapter = (adapter_factory or _build_proxmark_adapter)()
        device_status = adapter.get_status()
        if not device_status.configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The Proxmark bridge or device configuration is unavailable.",
            )
        started_ns = clock()
        result = adapter.identify_card(payload.band)
        duration_ms = max(0, round((clock() - started_ns) / 1_000_000))
    finally:
        proxmark_device_lock.release()

    if not result.detected and not _is_valid_no_detection(result):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.error or "The Proxmark identification command could not complete.",
        )

    classification = (
        "correct"
        if result.detected and _card_families_match(source_card.card_type, result.card_type)
        else "incorrect" if result.detected else "inconclusive"
    )
    uid_match = _uid_match(source_card.uid, result.uid) if result.detected else None
    evidence = _live_trial_evidence(payload, source_card, result, duration_ms)
    evidence_sha256 = hashlib.sha256(
        json.dumps(
            evidence,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()
    observed_type = result.card_type or "No credential detected"
    automatic_note = (
        f"Live {payload.band.upper()} trial; expected {source_card.card_type}; "
        f"observed {observed_type}."
    )
    trial = create_measurement_trial(
        db,
        session_id,
        MeasurementTrialCreate(
            batch_id=payload.batch_id,
            source_card_id=source_card.id,
            credential_alias=payload.credential_alias,
            technology_family=source_card.technology,
            card_family=source_card.card_type,
            distance_cm=payload.distance_cm,
            orientation=payload.orientation,
            presented_face=payload.presented_face,
            success=result.detected,
            classification_result=classification,
            identification_duration_ms=duration_ms,
            metadata_fields_count=_metadata_field_count(result),
            data_extracted_bytes=_identity_byte_count(result),
            nearby_metal=payload.nearby_metal,
            rf_interference=payload.rf_interference,
            environment_notes=payload.environment_notes,
            notes=" ".join(
                part for part in [automatic_note, payload.notes] if part
            ),
            raw_evidence_sha256=evidence_sha256,
        ),
    )

    evidence_path: str | None = None
    try:
        evidence_path = append_live_card_observation(
            get_settings().mock_data_dir,
            {
                "record_type": "controlled-measurement-trial",
                "measurement_trial_id": trial.id,
                "evidence_sha256": evidence_sha256,
                **evidence,
            },
        )
    except OSError:
        evidence_path = None

    return {
        "trial": trial,
        "command": result.command,
        "detected": result.detected,
        "observed_card_type": result.card_type,
        "observed_uid": result.uid,
        "uid_match": uid_match,
        "evidence_path": evidence_path,
        "message": (
            f"Trial #{trial.trial_number} recorded in {duration_ms} ms; "
            + (
                f"identified {result.card_type or 'credential'} ({classification})."
                if result.detected
                else "no credential was detected."
            )
        ),
    }


def get_measurement_trial_or_404(
    db: Session,
    session_id: int,
    trial_id: int,
) -> MeasurementTrial:
    statement = select(MeasurementTrial).where(
        MeasurementTrial.id == trial_id,
        MeasurementTrial.session_id == session_id,
    )
    trial = db.scalar(statement)
    if trial is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Measurement trial {trial_id} was not found in session {session_id}.",
        )
    return trial


def update_measurement_trial(
    db: Session,
    session_id: int,
    trial_id: int,
    payload: MeasurementTrialUpdate,
) -> MeasurementTrial:
    trial = get_measurement_trial_or_404(db, session_id, trial_id)
    changes = _clean_strings(payload.model_dump(exclude_unset=True))

    if "batch_id" in changes:
        get_experiment_batch_or_404(db, session_id, changes["batch_id"])
    if "source_card_id" in changes:
        source_card = _resolve_source_card(db, session_id, changes["source_card_id"])
        _enrich_from_source_card(changes, source_card)

    new_alias = changes.get("credential_alias")
    if new_alias and new_alias != trial.credential_alias:
        highest_trial = db.scalar(
            select(func.max(MeasurementTrial.trial_number)).where(
                MeasurementTrial.session_id == session_id,
                MeasurementTrial.credential_alias == new_alias,
            )
        )
        trial.trial_number = (highest_trial or 0) + 1

    for field, value in changes.items():
        setattr(trial, field, value)

    db.commit()
    db.refresh(trial)
    return trial


def delete_measurement_trial(db: Session, session_id: int, trial_id: int) -> None:
    trial = get_measurement_trial_or_404(db, session_id, trial_id)
    db.delete(trial)
    db.commit()


def summarize_measurements(
    db: Session,
    session_id: int,
    *,
    batch_id: int | None = None,
) -> dict[str, Any]:
    if batch_id is None:
        batches = list_experiment_batches(db, session_id)
    else:
        batches = [get_experiment_batch_or_404(db, session_id, batch_id)]
    trials = list_measurement_trials(db, session_id, batch_id=batch_id)
    classified = [
        trial for trial in trials if trial.classification_result in {"correct", "incorrect"}
    ]
    successful = [trial for trial in trials if trial.success]

    technologies: list[dict[str, Any]] = []
    technology_groups: dict[str, list[MeasurementTrial]] = defaultdict(list)
    for trial in trials:
        technology_groups[trial.technology_family].append(trial)

    for technology, group in sorted(technology_groups.items()):
        group_successful = [trial for trial in group if trial.success]
        group_classified = [
            trial
            for trial in group
            if trial.classification_result in {"correct", "incorrect"}
        ]
        correct = sum(
            trial.classification_result == "correct" for trial in group_classified
        )
        technologies.append(
            {
                "technology_family": technology,
                "trial_count": len(group),
                "unique_credentials": len(
                    {trial.credential_alias for trial in group}
                ),
                "successful_trials": len(group_successful),
                "detection_success_rate": _percentage(len(group_successful), len(group)),
                "classified_trials": len(group_classified),
                "correct_classifications": correct,
                "classification_accuracy": (
                    _percentage(correct, len(group_classified))
                    if group_classified
                    else None
                ),
                "timing": _timing_statistics(group_successful),
                "average_metadata_fields": round(
                    sum(trial.metadata_fields_count for trial in group) / len(group), 2
                ),
                "total_extracted_bytes": sum(
                    trial.data_extracted_bytes or 0 for trial in group
                ),
            }
        )

    correct_total = sum(
        trial.classification_result == "correct" for trial in classified
    )
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "session_id": session_id,
        "batch_count": len(batches),
        "trial_count": len(trials),
        "unique_credentials": len({trial.credential_alias for trial in trials}),
        "successful_trials": len(successful),
        "detection_success_rate": _percentage(len(successful), len(trials)),
        "classified_trials": len(classified),
        "correct_classifications": correct_total,
        "classification_accuracy": (
            _percentage(correct_total, len(classified)) if classified else None
        ),
        "timing": _timing_statistics(successful),
        "reliable_distances": _reliable_distances(trials),
        "technologies": technologies,
    }


def analyze_measurements(
    db: Session,
    session_id: int,
    *,
    batch_id: int | None = None,
) -> dict[str, Any]:
    if batch_id is None:
        batches = list_experiment_batches(db, session_id)
    else:
        batches = [get_experiment_batch_or_404(db, session_id, batch_id)]
    trials = list_measurement_trials(db, session_id, batch_id=batch_id)

    condition_groups: dict[
        tuple[str, int | None, str, str | None, float, str, str],
        list[MeasurementTrial],
    ] = defaultdict(list)
    credential_groups: dict[str, list[MeasurementTrial]] = defaultdict(list)
    for trial in trials:
        condition_groups[
            (
                trial.credential_alias,
                trial.source_card_id,
                trial.technology_family,
                trial.card_family,
                trial.distance_cm,
                trial.orientation,
                trial.presented_face,
            )
        ].append(trial)
        credential_groups[trial.credential_alias].append(trial)

    conditions: list[dict[str, Any]] = []
    for key, attempts in sorted(
        condition_groups.items(),
        key=lambda item: (item[0][0], item[0][4], item[0][5], item[0][6]),
    ):
        alias, source_card_id, technology, card_family, distance, orientation, face = key
        detections = sum(trial.success for trial in attempts)
        correct_trials = [
            trial
            for trial in attempts
            if trial.success and trial.classification_result == "correct"
        ]
        correct = len(correct_trials)
        conditions.append(
            {
                "credential_alias": alias,
                "source_card_id": source_card_id,
                "technology_family": technology,
                "card_family": card_family,
                "distance_cm": distance,
                "orientation": orientation,
                "presented_face": face,
                "detection": _proportion_statistics(detections, len(attempts)),
                "correct_identification": _proportion_statistics(
                    correct, len(attempts)
                ),
                "partial_response_count": sum(
                    trial.success and trial.classification_result != "correct"
                    for trial in attempts
                ),
                "incorrect_classification_count": sum(
                    trial.classification_result == "incorrect" for trial in attempts
                ),
                "inconclusive_count": sum(
                    trial.classification_result == "inconclusive" for trial in attempts
                ),
                "correct_identification_timing": _timing_statistics(correct_trials),
                "meets_minimum_repetitions": (
                    len(attempts) >= MINIMUM_CONDITION_ATTEMPTS
                ),
            }
        )

    reliable_by_alias: dict[str, float] = {}
    for item in _reliable_distances(trials):
        alias = item["credential_alias"]
        reliable_by_alias[alias] = max(
            reliable_by_alias.get(alias, item["reliable_distance_cm"]),
            item["reliable_distance_cm"],
        )

    credentials: list[dict[str, Any]] = []
    for alias, group in sorted(credential_groups.items()):
        detections = sum(trial.success for trial in group)
        correct_trials = [
            trial
            for trial in group
            if trial.success and trial.classification_result == "correct"
        ]
        source_card_ids = sorted(
            {trial.source_card_id for trial in group if trial.source_card_id is not None}
        )
        card_families = sorted(
            {trial.card_family for trial in group if trial.card_family}
        )
        credentials.append(
            {
                "credential_alias": alias,
                "source_card_id": source_card_ids[0] if source_card_ids else None,
                "technology_family": group[0].technology_family,
                "card_family": card_families[0] if card_families else None,
                "trial_count": len(group),
                "condition_count": len(
                    {
                        (trial.distance_cm, trial.orientation, trial.presented_face)
                        for trial in group
                    }
                ),
                "maximum_tested_distance_cm": max(
                    (trial.distance_cm for trial in group), default=0
                ),
                "reliable_identification_distance_cm": reliable_by_alias.get(alias),
                "detection": _proportion_statistics(detections, len(group)),
                "correct_identification": _proportion_statistics(
                    len(correct_trials), len(group)
                ),
                "partial_response_count": sum(
                    trial.success and trial.classification_result != "correct"
                    for trial in group
                ),
                "correct_identification_timing": _timing_statistics(correct_trials),
            }
        )

    quality_flags = _measurement_quality_flags(
        trials=trials,
        batches=batches,
        conditions=conditions,
    )
    interpretation = _measurement_interpretation(credentials, conditions)
    return {
        "analysis_version": ANALYSIS_VERSION,
        "methodology_version": METHODOLOGY_VERSION,
        "session_id": session_id,
        "batch_id": batch_id,
        "confidence_level_percent": CONFIDENCE_LEVEL_PERCENT,
        "interval_method": "Wilson score interval",
        "minimum_attempts_per_condition": MINIMUM_CONDITION_ATTEMPTS,
        "trial_count": len(trials),
        "credential_count": len(credentials),
        "condition_count": len(conditions),
        "credentials": credentials,
        "conditions": conditions,
        "quality_flags": quality_flags,
        "interpretation": interpretation,
    }


def compare_measurement_batches(
    db: Session,
    session_id: int,
    baseline_batch_id: int,
    post_remediation_batch_id: int,
) -> dict[str, Any]:
    if baseline_batch_id == post_remediation_batch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Baseline and post-remediation batches must be different.",
        )
    baseline = get_experiment_batch_or_404(db, session_id, baseline_batch_id)
    post = get_experiment_batch_or_404(db, session_id, post_remediation_batch_id)
    if baseline.condition != "baseline":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected baseline batch is not labeled as baseline.",
        )
    if post.condition != "post_remediation":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The selected post-remediation batch is not labeled as "
                "post_remediation."
            ),
        )

    baseline_summary = summarize_measurements(
        db, session_id, batch_id=baseline_batch_id
    )
    post_summary = summarize_measurements(
        db, session_id, batch_id=post_remediation_batch_id
    )
    detection_delta = round(
        post_summary["detection_success_rate"]
        - baseline_summary["detection_success_rate"],
        2,
    )
    classification_delta = _nullable_delta(
        baseline_summary["classification_accuracy"],
        post_summary["classification_accuracy"],
    )
    duration_delta = _nullable_delta(
        baseline_summary["timing"]["median_ms"],
        post_summary["timing"]["median_ms"],
    )
    distance_changes = _compare_reliable_distances(
        baseline_summary["reliable_distances"],
        post_summary["reliable_distances"],
    )

    interpretation = [
        (
            f"Detection success changed by {detection_delta:+.2f} percentage points "
            f"across {baseline_summary['trial_count']} baseline and "
            f"{post_summary['trial_count']} post-remediation trials."
        )
    ]
    if classification_delta is None:
        interpretation.append(
            "Classification change is unavailable because one batch has no conclusive labels."
        )
    else:
        interpretation.append(
            "Classification accuracy changed by "
            f"{classification_delta:+.2f} percentage points."
        )
    if duration_delta is None:
        interpretation.append(
            "Median identification-time change is unavailable because one batch has no successful trials."
        )
    else:
        interpretation.append(
            f"Median successful identification time changed by {duration_delta:+.2f} ms."
        )
    interpretation.append(
        "These descriptive deltas apply only to the documented setup and do not establish statistical significance."
    )

    return {
        "methodology_version": METHODOLOGY_VERSION,
        "session_id": session_id,
        "baseline_batch": baseline,
        "post_remediation_batch": post,
        "baseline_summary": baseline_summary,
        "post_remediation_summary": post_summary,
        "detection_rate_delta": detection_delta,
        "classification_accuracy_delta": classification_delta,
        "median_duration_delta_ms": duration_delta,
        "trial_count_delta": (
            post_summary["trial_count"] - baseline_summary["trial_count"]
        ),
        "unique_credentials_delta": (
            post_summary["unique_credentials"]
            - baseline_summary["unique_credentials"]
        ),
        "reliable_distance_changes": distance_changes,
        "interpretation": interpretation,
    }


def _resolve_source_card(
    db: Session,
    session_id: int,
    source_card_id: int | None,
) -> DetectedCard | None:
    if source_card_id is None:
        return None
    statement = select(DetectedCard).where(
        DetectedCard.id == source_card_id,
        DetectedCard.session_id == session_id,
    )
    card = db.scalar(statement)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Source card observation {source_card_id} was not found in "
                f"session {session_id}."
            ),
        )
    return card


def _build_proxmark_adapter() -> ProxmarkAdapter:
    settings = get_settings()
    return ProxmarkAdapter(
        bridge_url=settings.proxmark_bridge_url,
        client_path=settings.proxmark_client_path,
        port=settings.proxmark_port,
        timeout_seconds=settings.proxmark_command_timeout_seconds,
    )


def _band_matches_card(band: str, card: DetectedCard) -> bool:
    technology = card.technology.lower()
    return (band == "hf" and ("hf" in technology or "nfc" in technology)) or (
        band == "lf" and "lf" in technology
    )


def _is_valid_no_detection(result: ProxmarkIdentifyResult) -> bool:
    if result.detected:
        return True
    combined = f"{result.error or ''}\n{result.output}".lower()
    infrastructure_errors = (
        "bridge is not reachable",
        "could not open",
        "cannot communicate",
        "client is not configured",
        "configuration is unavailable",
    )
    if any(marker in combined for marker in infrastructure_errors):
        return False
    no_detection_markers = (
        "no tag found",
        "no card found",
        "no data found",
        "no matching card",
        "no known/supported",
        "timed out while searching",
        "command timed out after",
        "timeout while waiting",
    )
    return result.success or any(marker in combined for marker in no_detection_markers)


def _card_families_match(expected: str, observed: str | None) -> bool:
    if not observed:
        return False
    return _family_key(expected) == _family_key(observed)


def _family_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]", "", value.lower())
    families = (
        ("mifareclassic", "mifareclassic"),
        ("desfire", "desfire"),
        ("em410", "em410x"),
        ("ntag", "ntag"),
        ("ultralight", "ultralight"),
        ("iso14443a", "iso14443a"),
        ("iso15693", "iso15693"),
        ("hidprox", "hidprox"),
        ("t55", "t55xx"),
    )
    for marker, family in families:
        if marker in normalized:
            return family
    return normalized


def _uid_match(expected_uid: str, observed_uid: str | None) -> bool | None:
    if not observed_uid or expected_uid.lower() == "unavailable":
        return None
    normalize = lambda value: re.sub(r"[^0-9a-f]", "", value.lower())
    return normalize(expected_uid) == normalize(observed_uid)


def _metadata_field_count(result: ProxmarkIdentifyResult) -> int:
    values = [result.card_type, result.protocol, result.uid, result.atqa, result.sak]
    return sum(value not in (None, "") for value in values) + sum(
        value not in (None, "") for value in result.fields.values()
    )


def _identity_byte_count(result: ProxmarkIdentifyResult) -> int:
    return sum(
        len(re.findall(r"[0-9a-fA-F]{2}", value or ""))
        for value in (result.uid, result.atqa, result.sak)
    )


def _live_trial_evidence(
    payload: LiveMeasurementTrialCreate,
    source_card: DetectedCard,
    result: ProxmarkIdentifyResult,
    duration_ms: int,
) -> dict[str, Any]:
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "batch_id": payload.batch_id,
        "credential_alias": payload.credential_alias,
        "reference_card_id": source_card.id,
        "expected_card_family": source_card.card_type,
        "band": payload.band,
        "distance_cm": payload.distance_cm,
        "orientation": payload.orientation,
        "presented_face": payload.presented_face,
        "duration_ms": duration_ms,
        "command": result.command,
        "command_success": result.success,
        "exit_code": result.exit_code,
        "detected": result.detected,
        "observed_card_type": result.card_type,
        "observed_protocol": result.protocol,
        "observed_uid": result.uid,
        "atqa": result.atqa,
        "sak": result.sak,
        "parsed_fields": result.fields,
        "raw_output": result.output,
        "error": result.error,
    }


def _enrich_from_source_card(
    values: dict[str, Any],
    source_card: DetectedCard | None,
) -> None:
    if source_card is None:
        return
    values["technology_family"] = values.get("technology_family") or source_card.technology
    values["card_family"] = values.get("card_family") or source_card.card_type
    if not values.get("raw_evidence_sha256"):
        canonical = json.dumps(
            {
                "normalized": source_card.normalized_data_json,
                "raw": source_card.raw_output_json,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        values["raw_evidence_sha256"] = hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()


def _timing_statistics(trials: list[MeasurementTrial]) -> dict[str, Any]:
    durations = sorted(float(trial.identification_duration_ms) for trial in trials)
    if not durations:
        return {
            "count": 0,
            "minimum_ms": None,
            "maximum_ms": None,
            "median_ms": None,
            "q1_ms": None,
            "q3_ms": None,
        }
    return {
        "count": len(durations),
        "minimum_ms": durations[0],
        "maximum_ms": durations[-1],
        "median_ms": round(median(durations), 2),
        "q1_ms": _percentile(durations, 0.25),
        "q3_ms": _percentile(durations, 0.75),
    }


def _percentile(values: list[float], fraction: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return round(values[lower] * (1 - weight) + values[upper] * weight, 2)


def _reliable_distances(trials: list[MeasurementTrial]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, float], list[MeasurementTrial]] = defaultdict(list)
    for trial in trials:
        key = (
            trial.credential_alias,
            trial.technology_family,
            trial.orientation,
            trial.presented_face,
            trial.distance_cm,
        )
        grouped[key].append(trial)

    qualified: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for key, attempts in grouped.items():
        alias, technology, orientation, face, distance = key
        success_count = sum(
            trial.success and trial.classification_result == "correct"
            for trial in attempts
        )
        if len(attempts) < 5 or success_count < 4:
            continue
        if success_count / len(attempts) < 0.8:
            continue
        group_key = (alias, technology, orientation, face)
        current = qualified.get(group_key)
        if current is None or distance > current["reliable_distance_cm"]:
            qualified[group_key] = {
                "credential_alias": alias,
                "technology_family": technology,
                "orientation": orientation,
                "presented_face": face,
                "reliable_distance_cm": distance,
                "attempts": len(attempts),
                "successes": success_count,
            }
    return sorted(
        qualified.values(),
        key=lambda item: (
            item["credential_alias"],
            item["orientation"],
            item["presented_face"],
        ),
    )


def _percentage(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


def _proportion_statistics(events: int, attempts: int) -> dict[str, Any]:
    lower, upper = _wilson_interval(events, attempts)
    return {
        "events": events,
        "attempts": attempts,
        "rate_percent": _percentage(events, attempts),
        "ci_lower_percent": lower,
        "ci_upper_percent": upper,
    }


def _wilson_interval(events: int, attempts: int) -> tuple[float, float]:
    if attempts <= 0:
        return 0.0, 0.0
    z = 1.959963984540054
    proportion = events / attempts
    z_squared = z * z
    denominator = 1 + z_squared / attempts
    center = (proportion + z_squared / (2 * attempts)) / denominator
    margin = (
        z
        * (
            (proportion * (1 - proportion) / attempts)
            + z_squared / (4 * attempts * attempts)
        )
        ** 0.5
        / denominator
    )
    return round(max(0.0, center - margin) * 100, 2), round(
        min(1.0, center + margin) * 100, 2
    )


def _measurement_quality_flags(
    *,
    trials: list[MeasurementTrial],
    batches: list[ExperimentBatch],
    conditions: list[dict[str, Any]],
) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    if any(batch.status != "completed" for batch in batches):
        flags.append(
            _quality_flag(
                "open-batch",
                "warning",
                "finalization",
                "study",
                "An experiment batch is still open",
                "Complete the batch before treating exports as final research evidence.",
            )
        )

    incomplete = [
        item for item in conditions if not item["meets_minimum_repetitions"]
    ]
    if incomplete:
        labels = ", ".join(
            f"{item['credential_alias']} at {item['distance_cm']:g} cm"
            for item in incomplete[:4]
        )
        flags.append(
            _quality_flag(
                "under-repeated-condition",
                "high",
                "sample-size",
                "conditions",
                "One or more conditions have fewer than five attempts",
                f"Under-repeated conditions: {labels}.",
            )
        )

    for alias in sorted({item["credential_alias"] for item in conditions}):
        alias_conditions = [
            item for item in conditions if item["credential_alias"] == alias
        ]
        partial = sum(item["partial_response_count"] for item in alias_conditions)
        if partial:
            flags.append(
                _quality_flag(
                    f"partial-response-{alias}",
                    "warning",
                    "classification",
                    alias,
                    "Protocol responses occurred without correct identification",
                    f"{partial} detected response(s) did not correctly identify the expected credential. Detection and identification must be reported separately.",
                )
            )
        near_field = [item for item in alias_conditions if item["distance_cm"] == 0]
        if near_field and any(
            item["correct_identification"]["events"]
            < item["correct_identification"]["attempts"]
            for item in near_field
        ):
            flags.append(
                _quality_flag(
                    f"near-field-miss-{alias}",
                    "info",
                    "repeatability",
                    alias,
                    "A zero-distance trial was not correctly identified",
                    "Retained near-field misses quantify device or parser repeatability and must not be discarded.",
                )
            )

    missing_hashes = sum(not trial.raw_evidence_sha256 for trial in trials)
    hashes = [trial.raw_evidence_sha256 for trial in trials if trial.raw_evidence_sha256]
    duplicate_hashes = len(hashes) - len(set(hashes))
    if missing_hashes or duplicate_hashes:
        flags.append(
            _quality_flag(
                "evidence-integrity",
                "high",
                "evidence",
                "study",
                "Evidence-hash coverage requires review",
                f"Missing hashes: {missing_hashes}; duplicate hashes: {duplicate_hashes}.",
            )
        )

    technology_cards: dict[str, set[int]] = defaultdict(set)
    for trial in trials:
        if trial.source_card_id is not None:
            technology_cards[trial.technology_family].add(trial.source_card_id)
    single_sample_families = sorted(
        technology for technology, card_ids in technology_cards.items() if len(card_ids) == 1
    )
    if single_sample_families:
        flags.append(
            _quality_flag(
                "single-card-per-family",
                "info",
                "external-validity",
                "study",
                "Technology groups contain one physical credential each",
                "Repeated trials estimate the tested cards and setup; they do not establish population-wide properties for the card families.",
            )
        )
    return flags


def _quality_flag(
    flag_id: str,
    severity: str,
    category: str,
    scope: str,
    title: str,
    detail: str,
) -> dict[str, str]:
    return {
        "id": flag_id,
        "severity": severity,
        "category": category,
        "scope": scope,
        "title": title,
        "detail": detail,
    }


def _measurement_interpretation(
    credentials: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
) -> list[str]:
    items = [
        "Rates are descriptive estimates for the tested credentials and setup; Wilson 95% intervals show uncertainty without asserting statistical significance."
    ]
    for credential in credentials:
        distance = credential["reliable_identification_distance_cm"]
        distance_text = "no qualifying distance" if distance is None else f"{distance:g} cm"
        items.append(
            f"{credential['credential_alias']}: {credential['correct_identification']['events']} correct identifications in {credential['trial_count']} trials; reliable identification distance {distance_text}."
        )
    partial_total = sum(item["partial_response_count"] for item in conditions)
    if partial_total:
        items.append(
            f"{partial_total} partial protocol response(s) were detected without correct credential identification and are excluded from the reliable-identification threshold."
        )
    items.append(
        "Security scores are evaluated independently from RF performance; short read range does not by itself imply a secure credential path."
    )
    return items


def _nullable_delta(baseline: float | None, post: float | None) -> float | None:
    if baseline is None or post is None:
        return None
    return round(post - baseline, 2)


def _compare_reliable_distances(
    baseline: list[dict[str, Any]],
    post: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    def key(item: dict[str, Any]) -> tuple[str, str, str, str]:
        return (
            item["credential_alias"],
            item["technology_family"],
            item["orientation"],
            item["presented_face"],
        )

    baseline_by_key = {key(item): item for item in baseline}
    post_by_key = {key(item): item for item in post}
    changes = []
    for item_key in sorted(set(baseline_by_key) | set(post_by_key)):
        baseline_item = baseline_by_key.get(item_key)
        post_item = post_by_key.get(item_key)
        baseline_distance = (
            baseline_item["reliable_distance_cm"] if baseline_item else None
        )
        post_distance = post_item["reliable_distance_cm"] if post_item else None
        changes.append(
            {
                "credential_alias": item_key[0],
                "technology_family": item_key[1],
                "orientation": item_key[2],
                "presented_face": item_key[3],
                "baseline_distance_cm": baseline_distance,
                "post_remediation_distance_cm": post_distance,
                "delta_cm": _nullable_delta(baseline_distance, post_distance),
            }
        )
    return changes


def _clean_strings(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.strip() if isinstance(value, str) else value
        for key, value in values.items()
    }
