from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.assessment import AssessmentRun
    from app.models.detected_card import DetectedCard
    from app.models.finding import Finding
    from app.models.measurement import ExperimentBatch, MeasurementTrial
    from app.models.operator_command import OperatorCommand
    from app.models.transaction_trace import TransactionTrace


class ScanSession(Base):
    __tablename__ = "scan_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(String(50), nullable=False, default="simulator")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created")
    environment: Mapped[str] = mapped_column(String(50), nullable=False, default="local")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    detected_cards: Mapped[list[DetectedCard]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    findings: Mapped[list[Finding]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    assessment_runs: Mapped[list[AssessmentRun]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    operator_commands: Mapped[list[OperatorCommand]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    transaction_traces: Mapped[list[TransactionTrace]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    experiment_batches: Mapped[list[ExperimentBatch]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    measurement_trials: Mapped[list[MeasurementTrial]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
