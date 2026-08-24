from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.assurance_evidence import CardAssuranceEvidence
    from app.models.finding import Finding
    from app.models.scan_session import ScanSession


class DetectedCard(Base):
    __tablename__ = "detected_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("scan_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    technology: Mapped[str] = mapped_column(String(50), nullable=False)
    frequency: Mapped[str] = mapped_column(String(50), nullable=False)
    card_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    protocol: Mapped[str] = mapped_column(String(120), nullable=False)
    uid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, default="informational")
    normalized_data_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    raw_output_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    session: Mapped[ScanSession] = relationship(back_populates="detected_cards")
    findings: Mapped[list[Finding]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
    )
    assurance_evidence: Mapped[CardAssuranceEvidence | None] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        uselist=False,
    )
