from collections.abc import Callable

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.proxmark_adapter import (
    ProxmarkAdapter,
    ProxmarkProbeResult,
    normalize_safe_command,
)
from app.core.config import get_settings
from app.core.proxmark_capabilities import recipe_capabilities
from app.models.operator_command import OperatorCommand
from app.schemas.operator_command import OperatorCommandCreate
from app.services.device_lock import proxmark_device_lock
from app.services.session_service import STATUS_RUNNING, get_session_or_404

READ_ONLY_RECIPES: dict[str, dict[str, object]] = {
    recipe["key"]: recipe for recipe in recipe_capabilities()
}


def list_operator_commands(db: Session, session_id: int) -> list[OperatorCommand]:
    get_session_or_404(db, session_id)
    statement = (
        select(OperatorCommand)
        .where(OperatorCommand.session_id == session_id)
        .order_by(OperatorCommand.created_at.desc(), OperatorCommand.id.desc())
    )
    return list(db.scalars(statement).all())


def run_operator_command(
    db: Session,
    session_id: int,
    payload: OperatorCommandCreate,
    adapter_factory: Callable[[], ProxmarkAdapter] | None = None,
) -> OperatorCommand:
    _validate_operator_session(db, session_id)

    command = normalize_safe_command(payload.command)
    if command is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Command is not in the approved read-only allowlist.",
        )

    if not proxmark_device_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The Proxmark device is already in use by another workflow.",
        )
    try:
        adapter = (adapter_factory or _build_adapter)()
        result = adapter.run_safe_command(command)
        record = _command_record(session_id, result)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    finally:
        proxmark_device_lock.release()


def list_operator_recipes(db: Session, session_id: int) -> list[dict[str, object]]:
    get_session_or_404(db, session_id)
    return list(READ_ONLY_RECIPES.values())


def run_operator_recipe(
    db: Session,
    session_id: int,
    recipe_key: str,
    adapter_factory: Callable[[], ProxmarkAdapter] | None = None,
) -> dict[str, object]:
    _validate_operator_session(db, session_id)
    recipe = READ_ONLY_RECIPES.get(recipe_key)
    if recipe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operator recipe '{recipe_key}' was not found.",
        )
    if not proxmark_device_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The Proxmark device is already in use by another workflow.",
        )

    records: list[OperatorCommand] = []
    try:
        adapter = (adapter_factory or _build_adapter)()
        commands = recipe["commands"]
        if not isinstance(commands, list):
            raise RuntimeError("Operator recipe commands are invalid.")
        for command in commands:
            canonical_command = normalize_safe_command(str(command))
            if canonical_command is None:
                raise RuntimeError("Operator recipe contains a non-allowlisted command.")
            result = adapter.run_safe_command(canonical_command)
            record = _command_record(session_id, result)
            db.add(record)
            db.flush()
            records.append(record)
        db.commit()
        for record in records:
            db.refresh(record)
    finally:
        proxmark_device_lock.release()

    successful_count = sum(record.success for record in records)
    return {
        "recipe": recipe,
        "status": (
            "succeeded" if successful_count == len(records) else "completed_with_errors"
        ),
        "command_count": len(records),
        "successful_count": successful_count,
        "results": records,
    }


def _validate_operator_session(db: Session, session_id: int) -> None:
    session = get_session_or_404(db, session_id)
    if session.status != STATUS_RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start the session before running an operator command.",
        )
    if session.mode not in {"proxmark", "live"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Operator commands require a session with mode 'proxmark'.",
        )


def _command_record(session_id: int, result: ProxmarkProbeResult) -> OperatorCommand:
    return OperatorCommand(
        session_id=session_id,
        command=result.command,
        status="succeeded" if result.success else "failed",
        success=result.success,
        exit_code=result.exit_code,
        output=result.output,
        error=result.error,
    )


def _build_adapter() -> ProxmarkAdapter:
    settings = get_settings()
    return ProxmarkAdapter(
        bridge_url=settings.proxmark_bridge_url,
        client_path=settings.proxmark_client_path,
        port=settings.proxmark_port,
        timeout_seconds=settings.proxmark_command_timeout_seconds,
    )
