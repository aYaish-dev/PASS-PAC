from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.simulator_adapter import SimulatorAdapter
from app.core.config import get_settings
from app.models.detected_card import DetectedCard
from app.schemas.card import SimulatedScanRequest
from app.services.analysis_service import create_finding_for_card
from app.services.dataset_similarity import correlate_payload_with_file
from app.services.session_service import STATUS_RUNNING, get_session_or_404

HEX_CHARS = set("0123456789abcdefABCDEF")


def list_cards(db: Session) -> list[DetectedCard]:
    statement = select(DetectedCard).order_by(
        DetectedCard.created_at.desc(),
        DetectedCard.id.desc(),
    )
    return list(db.scalars(statement).all())


def get_card_or_404(db: Session, card_id: int) -> DetectedCard:
    card = db.get(DetectedCard, card_id)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card {card_id} was not found.",
        )
    return card


def get_card_dataset_correlation(db: Session, card_id: int) -> dict[str, Any]:
    card = get_card_or_404(db, card_id)
    settings = get_settings()
    return correlate_payload_with_file(
        {
            "technology": card.technology,
            "card_type": card.card_type,
            "protocol": card.protocol,
            "uid": card.uid,
            "normalized_data_json": card.normalized_data_json,
            "raw_output_json": card.raw_output_json,
        },
        Path(settings.mock_data_dir) / settings.simulator_card_file,
    )


def list_session_cards(db: Session, session_id: int) -> list[DetectedCard]:
    get_session_or_404(db, session_id)
    statement = (
        select(DetectedCard)
        .where(DetectedCard.session_id == session_id)
        .order_by(DetectedCard.created_at.desc(), DetectedCard.id.desc())
    )
    return list(db.scalars(statement).all())


def run_simulated_scan(
    db: Session,
    session_id: int,
    payload: SimulatedScanRequest | None = None,
) -> DetectedCard:
    session = get_session_or_404(db, session_id)
    if session.status != STATUS_RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot simulate scan for session with status '{session.status}'. "
                "Start the session before running a simulated scan."
            ),
        )

    if session.mode != "simulator":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Simulated scans are only available when the session mode is 'simulator'.",
        )

    scan_request = payload or SimulatedScanRequest()
    settings = get_settings()
    adapter = SimulatorAdapter(settings.mock_data_dir, settings.simulator_card_file)

    try:
        sample_card = adapter.pick_card(
            technology=scan_request.technology,
            card_type=scan_request.card_type,
            source=scan_request.source,
            dataset=scan_request.dataset,
            file_type=scan_request.file_type,
            uid=scan_request.uid,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Simulator mock card data file was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    detected_at = datetime.now(timezone.utc)
    raw_output = _as_dict(sample_card.get("raw_output"))
    metadata = _as_dict(sample_card.get("metadata"))
    flipper = _as_dict(sample_card.get("flipper"))
    dataset_info = _build_dataset_info(sample_card, metadata, flipper)
    uid_profile = _build_uid_profile(sample_card["uid"])
    memory_profile = _build_memory_profile(raw_output, flipper)
    normalized_data = {
        "source": sample_card.get("source", "simulator"),
        "dataset": dataset_info.get("dataset", "unknown"),
        "dataset_info": dataset_info,
        "technology": sample_card["technology"],
        "frequency": sample_card["frequency"],
        "card_type": sample_card["card_type"],
        "protocol": sample_card["protocol"],
        "uid": sample_card["uid"],
        "uid_format": uid_profile,
        "memory": memory_profile,
        "flipper": flipper,
        "analysis_fields": _build_analysis_fields(
            sample_card,
            raw_output,
            dataset_info,
            uid_profile,
            memory_profile,
        ),
        "raw_output": raw_output,
        "metadata": metadata,
        "timestamp": detected_at.isoformat(),
    }

    card = DetectedCard(
        session_id=session.id,
        technology=sample_card["technology"],
        frequency=sample_card["frequency"],
        card_type=sample_card["card_type"],
        protocol=sample_card["protocol"],
        uid=sample_card["uid"],
        risk_level=sample_card.get("risk_level", "informational"),
        normalized_data_json=normalized_data,
        raw_output_json=raw_output,
    )
    db.add(card)
    db.flush()
    create_finding_for_card(db, card)
    db.commit()
    db.refresh(card)
    return card


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _build_dataset_info(
    sample_card: dict[str, Any],
    metadata: dict[str, Any],
    flipper: dict[str, Any],
) -> dict[str, Any]:
    return _compact_dict(
        {
            "source": sample_card.get("source", "simulator"),
            "dataset": sample_card.get("dataset") or metadata.get("dataset"),
            "file_type": metadata.get("file_type") or flipper.get("file_type"),
            "source_path": metadata.get("source_path"),
            "source_file": metadata.get("source_file"),
            "source_sha256": metadata.get("source_sha256"),
        }
    )


def _build_uid_profile(uid: str) -> dict[str, Any]:
    parts = uid.split(":")
    byte_values = [
        part.upper()
        for part in parts
        if len(part) == 2 and all(char in HEX_CHARS for char in part)
    ]
    is_colon_hex = len(byte_values) == len(parts) and bool(byte_values)

    return _compact_dict(
        {
            "display_format": "colon_hex" if is_colon_hex else "raw",
            "byte_length": len(byte_values) if byte_values else None,
            "is_hex": bool(byte_values),
            "is_repeated_pattern": len(set(byte_values)) == 1 if byte_values else False,
            "prefix": ":".join(byte_values[:2]) if len(byte_values) >= 2 else None,
        }
    )


def _build_memory_profile(
    raw_output: dict[str, Any],
    flipper: dict[str, Any],
) -> dict[str, Any]:
    memory = raw_output.get("memory")
    memory_entries = memory if isinstance(memory, dict) else {}
    block_count = sum(1 for key in memory_entries if str(key).lower().startswith("block "))
    page_count = sum(1 for key in memory_entries if str(key).lower().startswith("page "))
    estimated_bytes = sum(_hex_byte_count(str(value)) for value in memory_entries.values())
    flipper_memory = _as_dict(flipper.get("memory"))

    return _compact_dict(
        {
            "has_dump": bool(memory_entries) or flipper_memory.get("has_dump"),
            "entry_count": len(memory_entries) or flipper_memory.get("entry_count"),
            "block_count": block_count or flipper_memory.get("block_count"),
            "page_count": page_count or flipper_memory.get("page_count"),
            "estimated_bytes": estimated_bytes or flipper_memory.get("estimated_bytes"),
        }
    )


def _build_analysis_fields(
    sample_card: dict[str, Any],
    raw_output: dict[str, Any],
    dataset_info: dict[str, Any],
    uid_profile: dict[str, Any],
    memory_profile: dict[str, Any],
) -> dict[str, Any]:
    return _compact_dict(
        {
            "dataset_source": dataset_info.get("source"),
            "dataset_name": dataset_info.get("dataset"),
            "file_type": dataset_info.get("file_type"),
            "uid_length_bytes": uid_profile.get("byte_length"),
            "memory_dump_present": memory_profile.get("has_dump"),
            "memory_estimated_bytes": memory_profile.get("estimated_bytes"),
            "atqa": raw_output.get("atqa"),
            "sak": raw_output.get("sak"),
            "key_type": raw_output.get("key_type"),
            "bit_length": raw_output.get("bit_length"),
            "device_type": raw_output.get("device_type"),
            "card_type": sample_card.get("card_type"),
            "protocol": sample_card.get("protocol"),
        }
    )


def _hex_byte_count(value: str) -> int:
    hex_chars = [char for char in value if char in HEX_CHARS]
    return len(hex_chars) // 2


def _compact_dict(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value not in (None, "", {})}
