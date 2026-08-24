from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.scan_session import ScanSession


class TransactionTrace(Base):
    __tablename__ = "transaction_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("scan_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    protocol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    confidence: Mapped[str] = mapped_column(String(40), nullable=False)
    frame_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reader_frame_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    card_frame_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    apdu_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    frames_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    findings_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    raw_output: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    session: Mapped[ScanSession] = relationship(back_populates="transaction_traces")
