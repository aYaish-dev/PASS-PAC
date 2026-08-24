from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transaction_trace import TransactionTrace
from app.adapters.proxmark_adapter import ProxmarkAdapter
from app.schemas.operator_command import OperatorCommandCreate
from app.schemas.transaction_trace import TraceAnalyzeRequest, TraceBufferRequest
from app.services.operator_command_service import run_operator_command
from app.services.session_service import get_session_or_404

ANALYZER_VERSION = "transaction-trace-analyzer-v1"
SUPPORTED_PROTOCOLS = {
    "14a": "ISO 14443-A",
    "mf": "MIFARE Classic",
    "des": "MIFARE DESFire",
    "7816": "ISO 7816-4",
    "15": "ISO 15693",
    "iclass": "iCLASS",
}
TRACE_BUFFER_COMMANDS = {
    protocol: f"trace list -t {protocol}" for protocol in SUPPORTED_PROTOCOLS
}

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
FRAME_RE = re.compile(
    r"^\s*(?P<start>\d+(?:\.\d+)?)\s*\|"
    r"\s*(?P<end>\d+(?:\.\d+)?)\s*\|"
    r"\s*(?P<source>Rdr|Tag)\s*\|"
    r"(?P<data>.*?)\|(?P<crc>.*?)\|(?P<annotation>.*)$",
    re.IGNORECASE,
)
HEX_TOKEN_RE = re.compile(r"(?i)\b([0-9a-f]{2})([!']?)")

APDU_COMMANDS = {
    0x20: "VERIFY",
    0x2A: "PERFORM SECURITY OPERATION",
    0x70: "MANAGE CHANNEL",
    0x82: "EXTERNAL AUTHENTICATE",
    0x84: "GET CHALLENGE",
    0x87: "GENERAL AUTHENTICATE",
    0x88: "INTERNAL AUTHENTICATE",
    0xA4: "SELECT",
    0xB0: "READ BINARY",
    0xB2: "READ RECORD",
    0xCA: "GET DATA",
    0xCB: "GET DATA",
    0xD2: "WRITE RECORD",
    0xD6: "UPDATE BINARY",
}
APDU_CLASS_BYTES = {0x00, 0x04, 0x0C, 0x80, 0x84, 0x8C, 0x90, 0x94, 0xA0}

LOW_LEVEL_COMMANDS = {
    0x26: "REQA",
    0x30: "MIFARE READ",
    0x50: "HALT",
    0x52: "WUPA",
    0x60: "MIFARE AUTH A / DESFire GET VERSION",
    0x61: "MIFARE AUTH B",
    0x93: "ISO14443-A SELECT CL1",
    0x95: "ISO14443-A SELECT CL2",
    0x97: "ISO14443-A SELECT CL3",
    0xA0: "MIFARE WRITE",
    0xE0: "RATS",
}

DESFIRE_COMMANDS = {
    0x0A: "DESFire AUTHENTICATE LEGACY",
    0x1A: "DESFire AUTHENTICATE ISO",
    0x3D: "DESFire WRITE DATA",
    0x5A: "DESFire SELECT APPLICATION",
    0x6A: "DESFire GET APPLICATION IDS",
    0x71: "DESFire AUTHENTICATE EV2 FIRST",
    0x77: "DESFire AUTHENTICATE EV2 NON-FIRST",
    0xAA: "DESFire AUTHENTICATE AES",
    0xAF: "DESFire ADDITIONAL FRAME",
    0xBD: "DESFire READ DATA",
}

AUTH_COMMAND_MARKERS = (
    "AUTH",
    "GET CHALLENGE",
    "GENERAL AUTHENTICATE",
    "VERIFY",
)
WRITE_COMMAND_MARKERS = ("WRITE", "UPDATE BINARY", "WRITE RECORD")
RISK_ORDER = {"informational": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def list_transaction_traces(db: Session, session_id: int) -> list[TransactionTrace]:
    get_session_or_404(db, session_id)
    statement = (
        select(TransactionTrace)
        .where(TransactionTrace.session_id == session_id)
        .order_by(TransactionTrace.created_at.desc(), TransactionTrace.id.desc())
    )
    return list(db.scalars(statement).all())


def get_transaction_trace_or_404(
    db: Session,
    session_id: int,
    trace_id: int,
) -> TransactionTrace:
    trace = db.get(TransactionTrace, trace_id)
    if trace is None or trace.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction trace {trace_id} was not found in session {session_id}.",
        )
    return trace


def analyze_imported_trace(
    db: Session,
    session_id: int,
    payload: TraceAnalyzeRequest,
) -> TransactionTrace:
    get_session_or_404(db, session_id)
    return _analyze_and_store(
        db=db,
        session_id=session_id,
        name=payload.name,
        protocol=payload.protocol,
        source="manual_import",
        raw_output=payload.raw_output,
    )


def analyze_device_trace_buffer(
    db: Session,
    session_id: int,
    payload: TraceBufferRequest,
    adapter_factory: Callable[[], ProxmarkAdapter] | None = None,
) -> TransactionTrace:
    command = TRACE_BUFFER_COMMANDS[payload.protocol]
    command_record = run_operator_command(
        db,
        session_id,
        OperatorCommandCreate(command=command),
        adapter_factory=adapter_factory,
    )
    raw_output = command_record.output
    if command_record.error:
        raw_output = f"{raw_output}\n{command_record.error}".strip()
    if not raw_output:
        raw_output = "Proxmark trace buffer command returned no output."
    return _analyze_and_store(
        db=db,
        session_id=session_id,
        name=payload.name,
        protocol=payload.protocol,
        source="proxmark_buffer",
        raw_output=raw_output,
    )


def delete_transaction_trace(db: Session, session_id: int, trace_id: int) -> None:
    trace = get_transaction_trace_or_404(db, session_id, trace_id)
    db.delete(trace)
    db.commit()


def analyze_trace_text(raw_output: str, protocol: str) -> dict[str, Any]:
    if protocol not in SUPPORTED_PROTOCOLS:
        raise ValueError(f"Unsupported trace protocol '{protocol}'.")
    frames = _parse_frames(raw_output, protocol)
    findings, features = _analyze_frames(frames, protocol)
    risk_level = max(
        (finding["risk_level"] for finding in findings),
        key=lambda value: RISK_ORDER[value],
        default="informational",
    )
    reader_count = sum(frame["source"] == "reader" for frame in frames)
    card_count = sum(frame["source"] == "card" for frame in frames)
    apdu_count = sum(frame["apdu"] is not None for frame in frames)
    confidence = _confidence(frames, reader_count, card_count)
    status_value = "analyzed" if frames else "no_frames"
    summary = _summary(features, len(frames), confidence, protocol)
    return {
        "status": status_value,
        "risk_level": risk_level,
        "confidence": confidence,
        "frame_count": len(frames),
        "reader_frame_count": reader_count,
        "card_frame_count": card_count,
        "apdu_count": apdu_count,
        "frames": frames,
        "findings": findings,
        "summary": {
            "analyzer_version": ANALYZER_VERSION,
            "protocol_name": SUPPORTED_PROTOCOLS[protocol],
            "summary": summary,
            "authentication_state": features["authentication_state"],
            "trust_hypothesis": features["trust_hypothesis"],
            "uid_selection_observed": features["uid_selection_observed"],
            "authentication_exchange_observed": features[
                "authentication_exchange_observed"
            ],
            "application_exchange_observed": features[
                "application_exchange_observed"
            ],
            "protected_apdu_count": features["protected_apdu_count"],
            "write_command_count": features["write_command_count"],
            "crc_error_count": features["crc_error_count"],
            "limitations": [
                "A passive trace shows observed RF traffic, not the controller's final access decision.",
                "Absence of authentication in an incomplete capture does not prove UID-only authorization.",
                "Encrypted payloads are preserved as evidence and are not decrypted by this analyzer.",
            ],
        },
    }


def _analyze_and_store(
    db: Session,
    session_id: int,
    name: str,
    protocol: str,
    source: str,
    raw_output: str,
) -> TransactionTrace:
    result = analyze_trace_text(raw_output, protocol)
    trace = TransactionTrace(
        session_id=session_id,
        name=name,
        protocol=protocol,
        source=source,
        status=result["status"],
        risk_level=result["risk_level"],
        confidence=result["confidence"],
        frame_count=result["frame_count"],
        reader_frame_count=result["reader_frame_count"],
        card_frame_count=result["card_frame_count"],
        apdu_count=result["apdu_count"],
        raw_sha256=hashlib.sha256(raw_output.encode("utf-8")).hexdigest(),
        summary_json=result["summary"],
        frames_json=result["frames"],
        findings_json=result["findings"],
        raw_output=raw_output,
    )
    db.add(trace)
    db.commit()
    db.refresh(trace)
    return trace


def _parse_frames(raw_output: str, protocol: str) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    clean_output = ANSI_RE.sub("", raw_output).replace("\r", "")
    for line in clean_output.splitlines():
        match = FRAME_RE.match(line)
        if not match:
            continue
        token_matches = HEX_TOKEN_RE.findall(match.group("data"))
        if not token_matches:
            continue
        byte_values = [int(value, 16) for value, _marker in token_matches]
        data_hex = " ".join(f"{value:02X}" for value in byte_values)
        source = "reader" if match.group("source").lower() == "rdr" else "card"
        start = float(match.group("start"))
        end = float(match.group("end"))
        annotation = match.group("annotation").strip() or None
        command = _decode_command(byte_values, source, protocol, annotation)
        apdu = _decode_apdu(byte_values, source)
        frames.append(
            {
                "sequence": len(frames) + 1,
                "start": start,
                "end": end,
                "duration": round(max(0.0, end - start), 3),
                "source": source,
                "direction": "reader_to_card" if source == "reader" else "card_to_reader",
                "data_hex": data_hex,
                "byte_count": len(byte_values),
                "crc": match.group("crc").strip() or None,
                "annotation": annotation,
                "parity_error": any(marker == "!" for _value, marker in token_matches),
                "short_frame": any(marker == "'" for _value, marker in token_matches),
                "command": command,
                "apdu": apdu,
            }
        )
    return frames


def _decode_command(
    data: list[int],
    source: str,
    protocol: str,
    annotation: str | None,
) -> str | None:
    if annotation and annotation.lower() not in {"", "?"}:
        normalized = " ".join(annotation.split())
        if normalized.lower() not in {"ok", "crc"}:
            return normalized
    if source != "reader" or not data:
        return None
    apdu = _decode_apdu(data, source)
    if apdu:
        return str(apdu["name"])
    if protocol == "des" and data[0] in DESFIRE_COMMANDS:
        return DESFIRE_COMMANDS[data[0]]
    return LOW_LEVEL_COMMANDS.get(data[0])


def _decode_apdu(data: list[int], source: str) -> dict[str, Any] | None:
    if source == "card":
        status_word = _find_status_word(data)
        if status_word:
            return {
                "kind": "response",
                "status_word": status_word,
                "status": _status_word_name(status_word),
            }
        return None

    candidates: list[tuple[int, list[int]]] = [(0, data)]
    if data and (data[0] & 0xC0) == 0 and len(data) >= 5:
        position = 1
        if data[0] & 0x08:
            position += 1
        if data[0] & 0x04:
            position += 1
        candidates.append((position, data[position:]))
    for offset, candidate in candidates:
        if (
            len(candidate) < 4
            or candidate[0] not in APDU_CLASS_BYTES
            or candidate[1] not in APDU_COMMANDS
        ):
            continue
        cla, ins, p1, p2 = candidate[:4]
        return {
            "kind": "command",
            "offset": offset,
            "cla": f"{cla:02X}",
            "ins": f"{ins:02X}",
            "p1": f"{p1:02X}",
            "p2": f"{p2:02X}",
            "name": APDU_COMMANDS[ins],
            "secure_messaging": bool(cla & 0x0C),
        }
    return None


def _find_status_word(data: list[int]) -> str | None:
    candidates: list[tuple[int, int]] = []
    if len(data) >= 2:
        candidates.append((data[-2], data[-1]))
    if len(data) >= 4:
        candidates.append((data[-4], data[-3]))
    for sw1, sw2 in candidates:
        if sw1 in {0x61, 0x62, 0x63, 0x67, 0x68, 0x69, 0x6A, 0x6B, 0x6C, 0x6D, 0x6E, 0x6F, 0x90}:
            return f"{sw1:02X}{sw2:02X}"
    return None


def _status_word_name(status_word: str) -> str:
    if status_word == "9000":
        return "success"
    if status_word.startswith("61"):
        return "response bytes available"
    if status_word == "6982":
        return "security status not satisfied"
    if status_word == "6A82":
        return "file or application not found"
    return "status returned"


def _analyze_frames(
    frames: list[dict[str, Any]],
    protocol: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reader_frames = [frame for frame in frames if frame["source"] == "reader"]
    selection_frames = [
        frame
        for frame in reader_frames
        if _contains_any(frame["command"], ("SELECT", "ANTICOLL", "REQA", "WUPA"))
    ]
    authentication_frames = [
        frame
        for frame in reader_frames
        if _contains_any(frame["command"], AUTH_COMMAND_MARKERS)
    ]
    application_frames = [frame for frame in reader_frames if frame["apdu"] is not None]
    protected_frames = [
        frame
        for frame in application_frames
        if bool((frame["apdu"] or {}).get("secure_messaging"))
    ]
    write_frames = [
        frame
        for frame in reader_frames
        if _contains_any(frame["command"], WRITE_COMMAND_MARKERS)
    ]
    crc_error_frames = [
        frame
        for frame in frames
        if frame["crc"] and any(marker in frame["crc"].lower() for marker in ("fail", "bad"))
    ]
    repeated_response_sequences = _repeated_authentication_responses(
        frames, authentication_frames
    )
    findings: list[dict[str, Any]] = []

    if not frames:
        findings.append(
            _finding(
                "trace_no_frames",
                "No transaction frames parsed",
                "low",
                "low",
                "The supplied output did not contain Proxmark trace-list frame rows.",
                "Confirm the trace buffer contains a capture and import the complete `trace list` output.",
                [f"Selected protocol: {SUPPORTED_PROTOCOLS[protocol]}"],
                [],
            )
        )
    elif selection_frames and not authentication_frames and not application_frames:
        findings.append(
            _finding(
                "trace_no_authentication_observed",
                "No authentication exchange observed",
                "medium",
                "medium" if len(frames) >= 4 else "low",
                "The trace contains credential discovery or selection but no recognized authentication or application exchange. This is a UID-only trust candidate, not proof of the controller's access decision.",
                "Capture the complete presentation and verify whether the reader performs cryptographic authentication before granting access.",
                [
                    f"Selection frames: {len(selection_frames)}",
                    f"Total frames: {len(frames)}",
                ],
                [frame["sequence"] for frame in selection_frames],
            )
        )
    elif application_frames and not authentication_frames:
        findings.append(
            _finding(
                "trace_application_without_observed_auth",
                "Application exchange lacks observed authentication",
                "medium",
                "medium",
                "Application commands are visible, but the captured sequence contains no recognized challenge-response or authentication command.",
                "Confirm capture completeness and validate the reader's authentication and secure-messaging configuration.",
                [f"Application APDUs: {len(application_frames)}"],
                [frame["sequence"] for frame in application_frames],
            )
        )

    if authentication_frames:
        findings.append(
            _finding(
                "trace_authentication_observed",
                "Authentication exchange observed",
                "informational",
                "high" if len(authentication_frames) >= 2 else "medium",
                "The passive trace contains recognized authentication or challenge-response commands. This confirms an exchange was attempted, but does not by itself prove secure key management or successful door authorization.",
                "Correlate the exchange with reader configuration and controller decision evidence.",
                [frame["command"] or "Authentication command" for frame in authentication_frames],
                [frame["sequence"] for frame in authentication_frames],
            )
        )

    if application_frames and not protected_frames and len(application_frames) >= 2:
        findings.append(
            _finding(
                "trace_secure_messaging_not_observed",
                "Secure messaging not visible in application commands",
                "low",
                "low",
                "Recognized APDUs do not set standard ISO 7816 secure-messaging class bits. Proprietary protection may still be present and encrypted payloads are not decrypted.",
                "Validate secure-messaging requirements against the credential and reader specification.",
                [f"Unprotected recognized APDUs: {len(application_frames)}"],
                [frame["sequence"] for frame in application_frames],
            )
        )

    if repeated_response_sequences:
        findings.append(
            _finding(
                "trace_repeated_auth_response",
                "Repeated authentication response candidate",
                "medium",
                "medium",
                "Identical card responses appear after recognized authentication commands in the same trace. Repetition may be normal for retries, so analyst validation is required.",
                "Repeat controlled captures and compare nonces before drawing a replayability conclusion.",
                [f"Repeated response frames: {', '.join(map(str, repeated_response_sequences))}"],
                repeated_response_sequences,
            )
        )

    if write_frames:
        findings.append(
            _finding(
                "trace_modification_command_observed",
                "Credential modification command observed",
                "medium",
                "high",
                "The passive trace includes one or more recognized write or update commands.",
                "Confirm that credential modification is expected, authorized, and protected by authentication and transaction controls.",
                [frame["command"] or "Write command" for frame in write_frames],
                [frame["sequence"] for frame in write_frames],
            )
        )

    if crc_error_frames and len(crc_error_frames) / len(frames) >= 0.2:
        findings.append(
            _finding(
                "trace_quality_crc_errors",
                "Trace quality limits interpretation",
                "low",
                "high",
                "At least 20 percent of parsed frames are marked with CRC failures, which can hide or alter protocol interpretation.",
                "Repeat the capture with improved antenna placement and reduced RF interference.",
                [f"CRC failures: {len(crc_error_frames)} of {len(frames)} frames"],
                [frame["sequence"] for frame in crc_error_frames],
            )
        )

    authentication_observed = bool(authentication_frames)
    application_observed = bool(application_frames)
    if authentication_observed:
        trust_hypothesis = "authenticated_exchange_present"
        authentication_state = "observed"
    elif selection_frames and not application_observed:
        trust_hypothesis = "uid_only_candidate"
        authentication_state = "not_observed"
    elif application_observed:
        trust_hypothesis = "application_exchange_without_observed_auth"
        authentication_state = "not_observed"
    else:
        trust_hypothesis = "insufficient_evidence"
        authentication_state = "inconclusive"

    return findings, {
        "uid_selection_observed": bool(selection_frames),
        "authentication_exchange_observed": authentication_observed,
        "application_exchange_observed": application_observed,
        "protected_apdu_count": len(protected_frames),
        "write_command_count": len(write_frames),
        "crc_error_count": len(crc_error_frames),
        "authentication_state": authentication_state,
        "trust_hypothesis": trust_hypothesis,
    }


def _repeated_authentication_responses(
    frames: list[dict[str, Any]],
    authentication_frames: list[dict[str, Any]],
) -> list[int]:
    auth_sequences = {frame["sequence"] for frame in authentication_frames}
    responses: dict[str, list[int]] = {}
    for index, frame in enumerate(frames[:-1]):
        if frame["sequence"] not in auth_sequences:
            continue
        response = frames[index + 1]
        if response["source"] != "card" or response["byte_count"] < 4:
            continue
        normalized = " ".join(response["data_hex"].split()[:-2]) or response["data_hex"]
        responses.setdefault(normalized, []).append(response["sequence"])
    return sorted(
        sequence
        for sequences in responses.values()
        if len(sequences) > 1
        for sequence in sequences
    )


def _finding(
    rule_id: str,
    title: str,
    risk_level: str,
    confidence: str,
    description: str,
    recommendation: str,
    evidence: list[str],
    frame_sequences: list[int],
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "title": title,
        "risk_level": risk_level,
        "confidence": confidence,
        "description": description,
        "recommendation": recommendation,
        "evidence": evidence,
        "frame_sequences": frame_sequences,
    }


def _contains_any(value: str | None, markers: tuple[str, ...]) -> bool:
    normalized = (value or "").upper()
    return any(marker in normalized for marker in markers)


def _confidence(
    frames: list[dict[str, Any]],
    reader_count: int,
    card_count: int,
) -> str:
    if len(frames) >= 8 and reader_count >= 3 and card_count >= 3:
        return "high"
    if len(frames) >= 4 and reader_count and card_count:
        return "medium"
    return "low"


def _summary(
    features: dict[str, Any],
    frame_count: int,
    confidence: str,
    protocol: str,
) -> str:
    if frame_count == 0:
        return "No Proxmark frame rows were parsed from the supplied output."
    if features["authentication_exchange_observed"]:
        posture = "A recognized authentication exchange is present."
    elif features["trust_hypothesis"] == "uid_only_candidate":
        posture = "Selection is visible without a recognized authentication exchange."
    elif features["application_exchange_observed"]:
        posture = "Application traffic is visible without a recognized authentication exchange."
    else:
        posture = "The capture is insufficient to classify the reader authentication path."
    return (
        f"Parsed {frame_count} {SUPPORTED_PROTOCOLS[protocol]} frame(s) with {confidence} "
        f"analysis confidence. {posture}"
    )
