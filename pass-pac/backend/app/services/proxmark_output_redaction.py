from __future__ import annotations

import re

SENSITIVE_LABELS: tuple[tuple[str, str], ...] = (
    (r"\bTrack\s*1(?:\s+equivalent)?\b", "TRACK_DATA"),
    (r"\bTrack\s*2(?:\s+equivalent)?\b", "TRACK_DATA"),
    (r"\bCardhold(?:er)?\s+Name\b", "CARDHOLDER_NAME"),
    (r"\bPAN\b(?!\s+Sequence\b)", "PAN"),
)


def redact_proxmark_output(output: str, command: str = "") -> str:
    normalized_command = " ".join(command.strip().lower().split())
    if not (
        normalized_command.startswith("emv ")
        or normalized_command.startswith("hf emv ")
    ):
        return output

    redacted_lines: list[str] = []
    for raw_line in output.splitlines():
        line = _redact_labeled_line(raw_line)
        line = _redact_emv_trace_line(line)
        redacted_lines.append(line)
    return "\n".join(redacted_lines)


def redacted_field_markers(output: str) -> list[str]:
    return sorted(set(re.findall(r"\[REDACTED:([A-Z_]+)(?::[^\]]+)?\]", output)))


def _redact_labeled_line(line: str) -> str:
    for pattern, marker in SENSITIVE_LABELS:
        match = re.search(pattern, line, re.I)
        if not match:
            continue
        separator = re.search(r"(?:\.{2,}|\s*[:=]\s*)", line[match.end() :])
        value_start = (
            match.end() + separator.end()
            if separator
            else match.end()
        )
        prefix = line[:value_start].rstrip()
        suffix = ""
        if marker == "PAN":
            digits = re.sub(r"\D", "", line[value_start:])
            if len(digits) >= 4:
                suffix = f":LAST4-{digits[-4:]}"
        return f"{prefix} [REDACTED:{marker}{suffix}]"
    return line


def _redact_emv_trace_line(line: str) -> str:
    parts = line.split("|")
    if len(parts) < 5:
        return line

    direction = parts[2].strip().lower()
    if direction not in {"rdr", "reader", "tag", "card"}:
        return line

    payload = re.findall(r"\b[0-9A-Fa-f]{2}\b", parts[3])
    if not payload:
        return line

    if direction in {"rdr", "reader"}:
        header = " ".join(item.upper() for item in payload[:5])
        parts[3] = f" {header} [REDACTED:EMV_APDU_BODY] "
    else:
        status_word = " ".join(item.upper() for item in payload[-2:])
        parts[3] = f" [REDACTED:EMV_RESPONSE_BODY] {status_word} "
    return "|".join(parts)
