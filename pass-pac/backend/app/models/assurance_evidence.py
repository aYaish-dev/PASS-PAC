from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.detected_card import DetectedCard


class CardAssuranceEvidence(Base):
    __tablename__ = "card_assurance_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    card_id: Mapped[int] = mapped_column(
        ForeignKey("detected_cards.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    reader_enforcement: Mapped[str | None] = mapped_column(String(40), nullable=True)
    lifecycle_monitoring: Mapped[str | None] = mapped_column(String(40), nullable=True)
    evidence_source: Mapped[str] = mapped_column(String(300), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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

    card: Mapped[DetectedCard] = relationship(back_populates="assurance_evidence")
