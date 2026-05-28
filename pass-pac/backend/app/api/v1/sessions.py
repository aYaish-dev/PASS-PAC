from typing import Annotated

from fastapi import APIRouter, Body, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.card import CardResponse, SimulatedScanRequest
from app.schemas.finding import FindingResponse
from app.schemas.session import SessionCreate, SessionResponse, SessionUpdate
from app.services.card_service import list_session_cards, run_simulated_scan
from app.services.finding_service import list_session_findings
from app.services.session_service import (
    create_session,
    delete_session,
    get_session_or_404,
    list_sessions,
    start_session,
    stop_session,
    update_session,
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


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_session(session_id: int, db: Session = Depends(get_db)) -> Response:
    delete_session(db, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
