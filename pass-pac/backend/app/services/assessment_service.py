from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Callable
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.adapters.proxmark_adapter import (
    ProxmarkAdapter,
    ProxmarkIdentifyResult,
    ProxmarkMetadataResult,
    ProxmarkProbeResult,
)
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.assessment import AssessmentEvent, AssessmentRun
from app.models.detected_card import DetectedCard
from app.services.analysis_service import create_finding_for_card
from app.services.dataset_similarity import correlate_payload_with_file
from app.services.device_lock import proxmark_device_lock
from app.services.observation_store import append_live_card_observation
from app.services.proxmark_metadata_parser import parse_metadata_output
from app.services.session_service import STATUS_RUNNING, get_session_or_404

RUN_QUEUED = "queued"
RUN_RUNNING = "running"
RUN_COMPLETED = "completed"
RUN_FAILED = "failed"

def list_assessments(db: Session, session_id: int) -> list[AssessmentRun]:
    get_session_or_404(db, session_id)
    statement = (
        select(AssessmentRun)
        .options(selectinload(AssessmentRun.events))
        .where(AssessmentRun.session_id == session_id)
        .order_by(AssessmentRun.created_at.desc(), AssessmentRun.id.desc())
    )
    return list(db.scalars(statement).all())


def get_assessment_or_404(
    db: Session,
    session_id: int,
    assessment_id: int,
) -> AssessmentRun:
    statement = (
        select(AssessmentRun)
        .options(selectinload(AssessmentRun.events))
        .where(
            AssessmentRun.id == assessment_id,
            AssessmentRun.session_id == session_id,
        )
    )
    assessment = db.scalar(statement)
    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {assessment_id} was not found in session {session_id}.",
        )
    return assessment


def queue_assessment(db: Session, session_id: int, band: str = "hf") -> AssessmentRun:
    session = get_session_or_404(db, session_id)
    if session.status != STATUS_RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start the session before running an automated assessment.",
        )
    if session.mode not in {"proxmark", "live"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Automated device assessments require a session with mode 'proxmark'.",
        )

    active_statement = select(AssessmentRun.id).where(
        AssessmentRun.session_id == session_id,
        AssessmentRun.status.in_([RUN_QUEUED, RUN_RUNNING]),
    )
    if db.scalar(active_statement) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This session already has an automated assessment in progress.",
        )

    normalized_band = band.strip().lower()
    if normalized_band not in {"hf", "lf", "emv"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Assessment profile must be 'hf', 'lf', or 'emv'.",
        )

    identity_band = "hf" if normalized_band == "emv" else normalized_band
    profile = (
        "automated-advanced-emv-read-only-v1"
        if normalized_band == "emv"
        else "automated-read-only-v1"
    )
    planned_commands = ["hw version", "hw status", "hw tune", f"{identity_band} search"]
    if normalized_band == "emv":
        planned_commands.extend(
            [
                "hf 14a info",
                "emv pse -s2",
                "emv search -s",
                "emv reader",
                "emv list",
            ]
        )

    assessment = AssessmentRun(
        session_id=session_id,
        profile=profile,
        status=RUN_QUEUED,
        summary_json={
            "safety_mode": "read-only",
            "bands": [normalized_band],
            "commands": planned_commands,
        },
    )
    db.add(assessment)
    db.flush()
    _add_event(
        db,
        assessment,
        phase="queue",
        event_status="queued",
        title="Assessment queued",
        message=(
            f"The read-only {normalized_band.upper()} assessment is waiting for the Proxmark device."
        ),
    )
    db.commit()
    return get_assessment_or_404(db, session_id, assessment.id)


def execute_queued_assessment(
    assessment_id: int,
    adapter_factory: Callable[[], ProxmarkAdapter] | None = None,
) -> None:
    db = SessionLocal()
    try:
        assessment = db.get(AssessmentRun, assessment_id)
        if assessment is None or assessment.status != RUN_QUEUED:
            return

        if not proxmark_device_lock.acquire(blocking=False):
            _fail_assessment(
                db,
                assessment,
                "The Proxmark device is already being used by another assessment.",
            )
            return

        try:
            _execute_assessment(db, assessment, (adapter_factory or _build_adapter)())
        finally:
            proxmark_device_lock.release()
    except Exception as exc:
        db.rollback()
        assessment = db.get(AssessmentRun, assessment_id)
        if assessment is not None and assessment.status in {RUN_QUEUED, RUN_RUNNING}:
            _fail_assessment(db, assessment, f"Unexpected assessment error: {exc}")
    finally:
        db.close()


def _execute_assessment(
    db: Session,
    assessment: AssessmentRun,
    adapter: ProxmarkAdapter,
) -> None:
    requested_bands = assessment.summary_json.get("bands", ["hf"])
    assessment_modes = [band for band in requested_bands if band in {"hf", "lf", "emv"}]
    if not assessment_modes:
        assessment_modes = ["hf"]

    assessment.status = RUN_RUNNING
    assessment.started_at = datetime.now(timezone.utc)
    _add_event(
        db,
        assessment,
        phase="preflight",
        event_status="running",
        title="Hardware preflight started",
        message="Checking bridge configuration, firmware visibility, and RF diagnostics.",
    )
    db.commit()

    device_status = adapter.get_status()
    _add_event(
        db,
        assessment,
        phase="preflight",
        event_status="succeeded" if device_status.configured else "failed",
        title="Device bridge checked",
        message=(
            "Proxmark bridge and device configuration are ready."
            if device_status.configured
            else "Proxmark bridge or device configuration is unavailable."
        ),
        evidence={
            "connection_mode": device_status.connection_mode,
            "integration_state": device_status.integration_state,
            "port": device_status.port,
            "safe_commands": device_status.safe_commands,
            "notes": device_status.notes,
        },
    )
    db.commit()
    if not device_status.configured:
        _fail_assessment(db, assessment, "Hardware preflight could not reach a configured device.")
        return

    probe = adapter.probe_hw_version()
    _record_command_event(
        db,
        assessment,
        phase="preflight",
        title="Firmware and client checked",
        result=probe,
        success_message="The Proxmark client and device firmware responded successfully.",
    )
    db.commit()
    if not probe.success:
        _fail_assessment(db, assessment, probe.error or "The firmware probe failed.")
        return

    warning_count = 0
    for diagnostic, title, message in [
        ("hardware_status", "Hardware status captured", "Device status and power information were captured."),
        ("antenna_tune", "Antenna diagnostics captured", "HF/LF antenna tuning evidence was captured."),
    ]:
        result = adapter.run_diagnostic(diagnostic)
        _record_command_event(
            db,
            assessment,
            phase="diagnostics",
            title=title,
            result=result,
            success_message=message,
            failure_status="warning",
        )
        warning_count += int(not result.success)
        db.commit()

    detected_cards: list[DetectedCard] = []
    selected_profiles: list[str] = []
    for assessment_mode in assessment_modes:
        technology = "hf" if assessment_mode == "emv" else assessment_mode
        result = adapter.identify_card(technology)
        if result.detected:
            profile = (
                "hf-emv-metadata-v1"
                if assessment_mode == "emv"
                else _select_scan_profile(result)
            )
            selected_profiles.append(profile)
            inspection_results = [
                adapter.inspect_card(command_key)
                for command_key in _inspection_commands_for_profile(profile)
            ]
            warning_count += sum(not inspection.success for inspection in inspection_results)
            card = _store_detected_card(
                db,
                assessment,
                result,
                profile,
                inspection_results,
            )
            detected_cards.append(card)
            _add_event(
                db,
                assessment,
                phase="reconnaissance",
                event_status="succeeded",
                title=f"{assessment_mode.upper()} credential identified",
                command=result.command,
                message=f"Detected {card.card_type}; selected assessment profile {profile}.",
                evidence={
                    "card_id": card.id,
                    "uid": card.uid,
                    "card_type": card.card_type,
                    "protocol": card.protocol,
                    "scan_profile": profile,
                    "parsed_fields": result.fields,
                    "raw_output": result.output,
                },
            )
            for inspection in inspection_results:
                _add_event(
                    db,
                    assessment,
                    phase="metadata",
                    event_status="succeeded" if inspection.success else "warning",
                    title=(
                        f"{_inspection_label(inspection.command_key)} metadata captured"
                        if inspection.success
                        else f"{_inspection_label(inspection.command_key)} metadata unavailable"
                    ),
                    command=inspection.command,
                    message=(
                        f"Parsed {len(inspection.fields)} structured metadata field(s)."
                        if inspection.success
                        else (inspection.error or "The read-only metadata command did not complete.")
                    ),
                    evidence={
                        "card_id": card.id,
                        "command_key": inspection.command_key,
                        "exit_code": inspection.exit_code,
                        "parsed_fields": inspection.fields,
                        "raw_output": inspection.output,
                    },
                )
        elif _is_no_card_result(result):
            _add_event(
                db,
                assessment,
                phase="reconnaissance",
                event_status="no_card",
                title=f"No {assessment_mode.upper()} credential detected",
                command=result.command,
                message=f"The {assessment_mode.upper()} search completed without a supported credential.",
                evidence={"raw_output": result.output, "error": result.error},
            )
        else:
            warning_count += 1
            _add_event(
                db,
                assessment,
                phase="reconnaissance",
                event_status="warning",
                title=f"{assessment_mode.upper()} search could not complete",
                command=result.command,
                message=result.error or "The search command returned an unexpected result.",
                evidence={"exit_code": result.exit_code, "raw_output": result.output},
            )
        db.commit()

    assessment.status = RUN_COMPLETED
    assessment.detected_card_count = len(detected_cards)
    assessment.completed_at = datetime.now(timezone.utc)
    assessment.summary_json = {
        "safety_mode": "read-only",
        "bands_scanned": assessment_modes,
        "detected_card_count": len(detected_cards),
        "warning_count": warning_count,
        "selected_profiles": selected_profiles,
        "result": "completed_with_warnings" if warning_count else "completed",
    }
    _add_event(
        db,
        assessment,
        phase="complete",
        event_status="succeeded",
        title="Assessment completed",
        message=(
            f"Read-only reconnaissance completed with {len(detected_cards)} credential(s) detected."
        ),
        evidence=assessment.summary_json,
    )
    db.commit()


def _store_detected_card(
    db: Session,
    assessment: AssessmentRun,
    result: ProxmarkIdentifyResult,
    profile: str,
    inspection_results: list[ProxmarkMetadataResult],
) -> DetectedCard:
    settings = get_settings()
    uid = _normalize_uid(result.uid) if result.uid else "unavailable"
    technology = "HF/NFC" if result.technology == "hf" else "LF RFID"
    frequency = "13.56 MHz" if result.technology == "hf" else "125 kHz"
    identity_metadata_fields = _identity_metadata_fields(profile, result.output)
    combined_inspection_fields = {
        **identity_metadata_fields,
        **_combined_inspection_fields(inspection_results),
    }
    observed_card_type = result.card_type or "Unknown credential"
    observed_protocol = result.protocol or technology
    if profile == "hf-emv-metadata-v1" and combined_inspection_fields.get(
        "emv_application_detected"
    ):
        observed_card_type = "EMV payment credential"
        observed_protocol = "EMV / ISO 14443-4"
    inspection_evidence = {
        "profile": profile,
        "identity_search_fields": identity_metadata_fields,
        "commands": [
            {
                "command_key": inspection.command_key,
                "command": inspection.command,
                "success": inspection.success,
                "fields": inspection.fields,
                "error": inspection.error,
            }
            for inspection in inspection_results
        ],
        "combined_fields": combined_inspection_fields,
    }
    raw_output = {
        "command": result.command,
        "output": result.output,
        "atqa": result.atqa,
        "sak": result.sak,
        **result.fields,
        "inspection_outputs": {
            inspection.command_key: inspection.output for inspection in inspection_results
        },
    }
    normalized = {
        "source": "live-proxmark",
        "assessment_run_id": assessment.id,
        "technology": technology,
        "frequency": frequency,
        "card_type": observed_card_type,
        "protocol": observed_protocol,
        "uid": uid,
        "uid_format": _uid_profile(uid),
        "memory": {
            "has_dump": False,
            "estimated_bytes": combined_inspection_fields.get("memory_size_bytes"),
            "page_count": combined_inspection_fields.get("page_count"),
            "block_count": combined_inspection_fields.get("block_count"),
            "block_size_bytes": combined_inspection_fields.get("block_size_bytes"),
        },
        "inspection": inspection_evidence,
        "analysis_fields": {
            "atqa": result.atqa,
            "sak": result.sak,
            "bit_length": result.fields.get("bit_length"),
            "card_type": observed_card_type,
            "protocol": observed_protocol,
            **combined_inspection_fields,
        },
        "raw_output": raw_output,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    normalized["dataset_correlation"] = correlate_payload_with_file(
        {
            "technology": technology,
            "card_type": observed_card_type,
            "protocol": observed_protocol,
            "uid": uid,
            "atqa": result.atqa,
            "sak": result.sak,
            "normalized_data_json": normalized,
            "raw_output_json": raw_output,
        },
        Path(settings.mock_data_dir) / settings.simulator_card_file,
    )
    card = DetectedCard(
        session_id=assessment.session_id,
        technology=technology,
        frequency=frequency,
        card_type=observed_card_type,
        protocol=observed_protocol,
        uid=uid,
        risk_level="informational",
        normalized_data_json=normalized,
        raw_output_json=raw_output,
    )
    db.add(card)
    db.flush()
    create_finding_for_card(db, card)
    append_live_card_observation(
        settings.mock_data_dir,
        {
            **asdict(result),
            "inspection": inspection_evidence,
            "dataset_correlation": normalized["dataset_correlation"],
        },
    )
    return card


def _record_command_event(
    db: Session,
    assessment: AssessmentRun,
    phase: str,
    title: str,
    result: ProxmarkProbeResult,
    success_message: str,
    failure_status: str = "failed",
) -> None:
    _add_event(
        db,
        assessment,
        phase=phase,
        event_status="succeeded" if result.success else failure_status,
        title=title,
        command=result.command,
        message=success_message if result.success else (result.error or "Command failed."),
        evidence={"exit_code": result.exit_code, "raw_output": result.output},
    )


def _add_event(
    db: Session,
    assessment: AssessmentRun,
    phase: str,
    event_status: str,
    title: str,
    message: str,
    command: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> AssessmentEvent:
    event = AssessmentEvent(
        assessment_run_id=assessment.id,
        session_id=assessment.session_id,
        sequence=len(assessment.events) + 1,
        phase=phase,
        status=event_status,
        title=title,
        command=command,
        message=message,
        evidence_json=evidence or {},
    )
    assessment.events.append(event)
    db.add(event)
    return event


def _fail_assessment(db: Session, assessment: AssessmentRun, message: str) -> None:
    assessment.status = RUN_FAILED
    assessment.completed_at = datetime.now(timezone.utc)
    assessment.summary_json = {"safety_mode": "read-only", "error": message}
    _add_event(
        db,
        assessment,
        phase="complete",
        event_status="failed",
        title="Assessment stopped",
        message=message,
    )
    db.commit()


def _build_adapter() -> ProxmarkAdapter:
    settings = get_settings()
    return ProxmarkAdapter(
        bridge_url=settings.proxmark_bridge_url,
        client_path=settings.proxmark_client_path,
        port=settings.proxmark_port,
        timeout_seconds=settings.proxmark_command_timeout_seconds,
    )


def _select_scan_profile(result: ProxmarkIdentifyResult) -> str:
    card_type = (result.card_type or "").lower()
    protocol = (result.protocol or "").lower()
    if "mifare classic" in card_type:
        return "hf-mifare-classic-metadata-v1"
    if "ntag" in card_type or "ultralight" in card_type:
        return "hf-type2-tag-metadata-v1"
    if "desfire" in card_type:
        return "hf-desfire-metadata-v1"
    if "15693" in protocol or "15693" in card_type:
        return "hf-iso15693-metadata-v1"
    if "iclass" in card_type:
        return "hf-iclass-metadata-v1"
    if "14443-a" in protocol or "14443a" in protocol:
        return "hf-generic-metadata-v1"
    if "hid" in card_type:
        return "lf-hid-metadata-v1"
    if "t55" in card_type:
        return "lf-t55xx-metadata-v1"
    if "em 410" in card_type or "em410" in card_type:
        return "lf-em410x-metadata-v1"
    return "lf-identifier-metadata-v1"


def _inspection_commands_for_profile(profile: str) -> list[str]:
    commands = {
        "hf-mifare-classic-metadata-v1": ["hf_iso14443a", "hf_mifare_classic"],
        "hf-type2-tag-metadata-v1": ["hf_iso14443a", "hf_type2"],
        "hf-desfire-metadata-v1": ["hf_iso14443a", "hf_desfire"],
        "hf-iso15693-metadata-v1": ["hf_iso15693"],
        "hf-iclass-metadata-v1": ["hf_iclass"],
        "hf-generic-metadata-v1": ["hf_iso14443a"],
        "hf-emv-metadata-v1": [
            "hf_iso14443a",
            "hf_emv_pse",
            "hf_emv_search",
            "hf_emv_reader",
            "hf_emv_history",
        ],
        "lf-em410x-metadata-v1": ["lf_em410x"],
        "lf-hid-metadata-v1": ["lf_hid"],
        "lf-t55xx-metadata-v1": ["lf_t55xx"],
    }
    return commands.get(profile, [])


def _inspection_label(command_key: str) -> str:
    labels = {
        "hf_iso14443a": "ISO14443-A",
        "hf_mifare_classic": "MIFARE Classic",
        "hf_type2": "Ultralight/NTAG",
        "hf_iso15693": "ISO15693",
        "hf_desfire": "DESFire",
        "hf_iclass": "iCLASS",
        "hf_emv_pse": "EMV PPSE",
        "hf_emv_search": "EMV application search",
        "hf_emv_reader": "EMV application",
        "hf_emv_history": "EMV APDU history",
        "lf_em410x": "EM410x",
        "lf_hid": "HID Prox",
        "lf_t55xx": "T55xx",
    }
    return labels.get(command_key, command_key)


def _combined_inspection_fields(
    inspection_results: list[ProxmarkMetadataResult],
) -> dict[str, Any]:
    combined: dict[str, Any] = {}
    for inspection in inspection_results:
        for key, value in inspection.fields.items():
            combined.setdefault(key, value)
    return combined


def _identity_metadata_fields(profile: str, output: str) -> dict[str, Any]:
    combined: dict[str, Any] = {}
    for command_key in _inspection_commands_for_profile(profile):
        parsed = parse_metadata_output(command_key, output)
        for key, value in parsed.fields.items():
            combined.setdefault(key, value)
    return combined


def _is_no_card_result(result: ProxmarkIdentifyResult) -> bool:
    error = (result.error or "").lower()
    output = result.output.lower()
    return not result.detected and (
        result.success
        or "no matching card" in error
        or "no data found" in output
        or "no tag found" in output
        or "no known" in output
        or "couldn't identify" in output
    )


def _normalize_uid(uid: str) -> str:
    return ":".join(uid.replace("-", " ").replace(":", " ").upper().split())


def _uid_profile(uid: str) -> dict[str, Any]:
    parts = uid.split(":")
    valid = bool(parts) and all(
        len(part) == 2 and all(char in "0123456789ABCDEF" for char in part)
        for part in parts
    )
    return {
        "display_format": "colon_hex" if valid else "raw",
        "byte_length": len(parts) if valid else 0,
        "is_hex": valid,
    }
