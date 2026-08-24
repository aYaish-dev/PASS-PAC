from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.detected_card import DetectedCard
    from app.models.scan_session import ScanSession


class ExperimentBatch(Base):
    __tablename__ = "experiment_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("scan_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    condition: Mapped[str] = mapped_column(
        String(40), nullable=False, default="baseline", index=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="open", index=True
    )
    authorization_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    operator_label: Mapped[str] = mapped_column(String(80), nullable=False)
    location_label: Mapped[str] = mapped_column(String(120), nullable=False)
    device_model: Mapped[str] = mapped_column(String(120), nullable=False)
    client_version: Mapped[str] = mapped_column(String(160), nullable=False)
    firmware_version: Mapped[str] = mapped_column(String(160), nullable=False)
    antenna_configuration: Mapped[str] = mapped_column(String(160), nullable=False)
    host_os: Mapped[str] = mapped_column(String(120), nullable=False)
    command_profile: Mapped[str] = mapped_column(String(120), nullable=False)
    environment_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    session: Mapped[ScanSession] = relationship(back_populates="experiment_batches")
    trials: Mapped[list[MeasurementTrial]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="MeasurementTrial.trial_number",
    )


class MeasurementTrial(Base):
    __tablename__ = "measurement_trials"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "credential_alias",
            "trial_number",
            name="uq_measurement_trial_alias_number",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("scan_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("experiment_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_card_id: Mapped[int | None] = mapped_column(
        ForeignKey("detected_cards.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trial_number: Mapped[int] = mapped_column(Integer, nullable=False)
    credential_alias: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    technology_family: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    card_family: Mapped[str | None] = mapped_column(String(120), nullable=True)
    distance_cm: Mapped[float] = mapped_column(Float, nullable=False)
    orientation: Mapped[str] = mapped_column(String(40), nullable=False)
    presented_face: Mapped[str] = mapped_column(String(30), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    classification_result: Mapped[str] = mapped_column(String(30), nullable=False)
    identification_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_fields_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data_extracted_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nearby_metal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rf_interference: Mapped[str] = mapped_column(
        String(30), nullable=False, default="unknown"
    )
    environment_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_evidence_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    session: Mapped[ScanSession] = relationship(back_populates="measurement_trials")
    batch: Mapped[ExperimentBatch] = relationship(back_populates="trials")
    source_card: Mapped[DetectedCard | None] = relationship()
