from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TraceProtocol = Literal["14a", "mf", "des", "7816", "15", "iclass"]


class TraceAnalyzeRequest(BaseModel):
    name: str = Field(default="Imported reader transaction", min_length=1, max_length=160)
    protocol: TraceProtocol = "14a"
    raw_output: str = Field(..., min_length=1, max_length=2_000_000)


class TraceBufferRequest(BaseModel):
    name: str = Field(default="Proxmark trace buffer", min_length=1, max_length=160)
    protocol: TraceProtocol = "14a"


class TraceFrameResponse(BaseModel):
    sequence: int
    start: float
    end: float
    duration: float
    source: str
    direction: str
    data_hex: str
    byte_count: int
    crc: str | None
    annotation: str | None
    parity_error: bool
    short_frame: bool
    command: str | None
    apdu: dict[str, Any] | None


class TraceFindingResponse(BaseModel):
    rule_id: str
    title: str
    risk_level: str
    confidence: str
    description: str
    recommendation: str
    evidence: list[str]
    frame_sequences: list[int]


class TransactionTraceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    name: str
    protocol: str
    source: str
    status: str
    risk_level: str
    confidence: str
    frame_count: int
    reader_frame_count: int
    card_frame_count: int
    apdu_count: int
    raw_sha256: str
    summary_json: dict[str, Any]
    frames_json: list[TraceFrameResponse]
    findings_json: list[TraceFindingResponse]
    raw_output: str
    created_at: datetime


class TransactionTraceSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    name: str
    protocol: str
    source: str
    status: str
    risk_level: str
    confidence: str
    frame_count: int
    reader_frame_count: int
    card_frame_count: int
    apdu_count: int
    raw_sha256: str
    summary_json: dict[str, Any]
    created_at: datetime
