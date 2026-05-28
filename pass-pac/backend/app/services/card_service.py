from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.simulator_adapter import SimulatorAdapter
from app.core.config import get_settings
from app.models.detected_card import DetectedCard
from app.schemas.card import SimulatedScanRequest
from app.services.session_service import STATUS_RUNNING, get_session_or_404


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
    adapter = SimulatorAdapter(get_settings().mock_data_dir)

    try:
        sample_card = adapter.pick_card(
            technology=scan_request.technology,
            card_type=scan_request.card_type,
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
    normalized_data = {
        "source": sample_card.get("source", "simulator"),
        "technology": sample_card["technology"],
        "frequency": sample_card["frequency"],
        "card_type": sample_card["card_type"],
        "protocol": sample_card["protocol"],
        "uid": sample_card["uid"],
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
    db.commit()
    db.refresh(card)
    return card


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}
