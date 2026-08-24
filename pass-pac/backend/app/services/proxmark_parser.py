from __future__ import annotations

import re
from dataclasses import dataclass


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
HEX_BYTES_RE = re.compile(r"[0-9a-fA-F]{2}")


@dataclass(frozen=True)
class ParsedProxmarkIdentity:
    detected: bool
    card_type: str | None
    protocol: str | None
    uid: str | None
    atqa: str | None
    sak: str | None
    fields: dict[str, str]


def parse_identity_output(technology: str, output: str) -> ParsedProxmarkIdentity:
    normalized_technology = technology.lower()
    clean_output = ANSI_ESCAPE_RE.sub("", output)
    clean_lines = [_clean_line(line) for line in clean_output.splitlines()]
    non_empty_lines = [line for line in clean_lines if line]

    if _looks_like_no_card(clean_output):
        return ParsedProxmarkIdentity(
            detected=False,
            card_type=None,
            protocol=_protocol_for_technology(normalized_technology, clean_output),
            uid=None,
            atqa=None,
            sak=None,
            fields={},
        )

    if normalized_technology == "hf":
        return _parse_hf_identity(clean_output, non_empty_lines)
    if normalized_technology == "lf":
        return _parse_lf_identity(clean_output, non_empty_lines)

    return ParsedProxmarkIdentity(
        detected=False,
        card_type=None,
        protocol=None,
        uid=None,
        atqa=None,
        sak=None,
        fields={},
    )


def _parse_hf_identity(output: str, lines: list[str]) -> ParsedProxmarkIdentity:
    detection_output = _remove_search_progress(output)
    uid = _extract_hex_value(
        detection_output,
        [
            r"\b(?:Card\s+UID|UID|NFC\s*ID|NFCID)\b\s*[:=]\s*([0-9a-fA-F][0-9a-fA-F \t:-]{3,})",
        ],
    )
    atqa = _extract_hex_value(
        detection_output,
        [r"\bATQA\b\s*[:=]\s*([0-9a-fA-F][0-9a-fA-F \t:-]{1,})"],
    )
    sak = _extract_hex_value(
        detection_output,
        [r"\bSAK\b\s*[:=]\s*(0x[0-9a-fA-F]+|[0-9a-fA-F]{1,2})"],
    )
    card_type = _extract_hf_card_type(lines)
    protocol = _protocol_for_technology("hf", detection_output)

    fields: dict[str, str] = {}
    if uid:
        fields["uid_length_bytes"] = str(len(HEX_BYTES_RE.findall(uid)))
    if "manufacturer" in detection_output.lower():
        manufacturer = _extract_text_value(detection_output, r"\bMANUFACTURER\b\s*[:=]\s*(.+)")
        if manufacturer:
            fields["manufacturer"] = manufacturer
    if "doesn't support standard iso14443-3 anticollision" in detection_output.lower():
        fields["anticollision"] = "non-standard"

    detected = bool(
        uid
        or atqa
        or sak
        or card_type
        or re.search(r"\bvalid\b.+\btag found\b", detection_output, re.I)
    )
    return ParsedProxmarkIdentity(
        detected=detected,
        card_type=card_type,
        protocol=protocol,
        uid=uid,
        atqa=atqa,
        sak=sak,
        fields=fields,
    )


def _parse_lf_identity(output: str, lines: list[str]) -> ParsedProxmarkIdentity:
    card_type = _extract_lf_card_type(lines)
    protocol = _protocol_for_technology("lf", output)
    identifier = _extract_hex_value(
        output,
        [
            r"\bEM\s*410x\s+ID\s*[:=]?\s*([0-9a-fA-F]{6,})",
            r"\bID\s*[:=]\s*([0-9a-fA-F]{6,})",
        ],
    )

    fields: dict[str, str] = {}
    bit_length = _extract_text_value(output, r"\b(\d{2,3})\s*[- ]bit\b")
    if bit_length:
        fields["bit_length"] = bit_length

    detected = bool(card_type or identifier or re.search(r"\bvalid\b.+\bfound\b", output, re.I))
    return ParsedProxmarkIdentity(
        detected=detected,
        card_type=card_type,
        protocol=protocol,
        uid=identifier,
        atqa=None,
        sak=None,
        fields=fields,
    )


def _protocol_for_technology(technology: str, output: str) -> str | None:
    output_lower = output.lower()
    if "valid iso 14443-a tag found" in output_lower:
        return "ISO 14443-A"
    if "valid felica tag found" in output_lower:
        return "FeliCa"
    if "valid iso15693 tag found" in output_lower or "valid iso 15693 tag found" in output_lower:
        return "ISO 15693"
    if (
        "iso14443-a" in output_lower
        or "iso 14443-a" in output_lower
        or "iso14443a" in output_lower
        or "atqa" in output_lower
        or "sak" in output_lower
    ):
        return "ISO 14443-A"
    if technology == "hf":
        return "HF/NFC"
    if technology == "lf":
        return "125kHz LF"
    return None


def _extract_hf_card_type(lines: list[str]) -> str | None:
    type_terms = (
        "MIFARE",
        "NTAG",
        "Ultralight",
        "DESFire",
        "FeliCa",
        "iCLASS",
        "ISO 15693",
        "Topaz",
        "LEGIC",
    )

    for index, line in enumerate(lines):
        if "possible types" in line.lower():
            for candidate in lines[index + 1 : index + 5]:
                candidate_lower = candidate.lower()
                is_section_header = bool(
                    re.fullmatch(r"[-=\s]*(?:ATS|Historical bytes|ATR fingerprinting)?[-=\s]*", candidate, re.I)
                )
                if (
                    candidate
                    and any(term.lower() in candidate_lower for term in type_terms)
                    and not is_section_header
                    and not candidate_lower.startswith(("prng", "static", "proprietary"))
                    and not any(
                    marker in candidate_lower
                    for marker in (
                        "failed to fingerprint",
                        "unknown",
                        "n/a",
                        "not available",
                        "tag found",
                    )
                    )
                ):
                    return candidate

    for line in lines:
        if line.lower().startswith("searching for"):
            continue
        if any(term.lower() in line.lower() for term in type_terms):
            if "possible types" not in line.lower():
                return line

    for line in lines:
        match = re.search(r"\bValid\s+(.+?)\s+tag\s+found\b", line, re.I)
        if match:
            normalized_type = re.sub(r"\s+", " ", match.group(1).strip())
            if re.fullmatch(r"ISO\s*14443-A", normalized_type, re.I):
                return "ISO 14443-A tag"
            if re.fullmatch(r"ISO\s*15693", normalized_type, re.I):
                return "ISO 15693 tag"
            return f"{normalized_type} tag"

    return None


def _extract_lf_card_type(lines: list[str]) -> str | None:
    patterns = [
        r"\bEM\s*410x\b",
        r"\bEM\s*4100\b",
        r"\bHID\s+H10301\b",
        r"\bHID\s+Prox\b",
        r"\bIndala\b",
        r"\bAWID\b",
        r"\bIOProx\b",
        r"\bNexWatch\b",
        r"\bViking\b",
        r"\bFDX-B\b",
        r"\bT55(?:xx|77)\b",
        r"\bHitag\b",
        r"\bKeri\b",
        r"\bNedap\b",
    ]
    for line in lines:
        for pattern in patterns:
            match = re.search(pattern, line, re.I)
            if match:
                return match.group(0)
    return None


def _extract_hex_value(output: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, output, re.I)
        if not match:
            continue
        value = match.group(1).strip()
        if value.lower().startswith("0x"):
            return value.upper()
        hex_bytes = HEX_BYTES_RE.findall(value)
        if hex_bytes:
            return " ".join(byte.upper() for byte in hex_bytes)
    return None


def _extract_text_value(output: str, pattern: str) -> str | None:
    match = re.search(pattern, output, re.I)
    if not match:
        return None
    return match.group(1).strip()


def _looks_like_no_card(output: str) -> bool:
    output_lower = output.lower()
    no_card_patterns = (
        "no tag found",
        "no known/supported",
        "no known 125",
        "no data found",
        "no card found",
        "timeout while waiting",
    )
    return any(pattern in output_lower for pattern in no_card_patterns)


def _clean_line(line: str) -> str:
    line = re.sub(r"^\s*\[[^\]]+\]\s*", "", line)
    return line.strip()


def _remove_search_progress(output: str) -> str:
    lines = [_clean_line(line) for line in output.splitlines()]
    detection_lines = [
        line for line in lines if not line.lower().startswith("searching for")
    ]
    return "\n".join(detection_lines)
