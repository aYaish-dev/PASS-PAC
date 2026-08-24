from __future__ import annotations

import re
from dataclasses import dataclass, fields
from typing import Any

from app.services.proxmark_parser import ANSI_ESCAPE_RE
from app.services.proxmark_output_redaction import redacted_field_markers


@dataclass(frozen=True)
class ParsedProxmarkMetadata:
    fields: dict[str, Any]


def parse_metadata_output(command_key: str, output: str) -> ParsedProxmarkMetadata:
    clean_output = ANSI_ESCAPE_RE.sub("", output)
    fields = _parse_key_value_lines(clean_output)
    normalized_key = command_key.strip().lower()

    if normalized_key in {
        "hf_iso14443a",
        "hf_mifare_classic",
        "hf_type2",
        "hf_desfire",
    }:
        fields.update(_parse_hf_iso14443_metadata(clean_output))
    if normalized_key == "hf_type2":
        fields.update(_parse_type2_metadata(clean_output))
    if normalized_key == "hf_iso15693":
        fields.update(_parse_iso15693_metadata(clean_output))
    if normalized_key == "lf_em410x":
        fields.update(_parse_em410x_metadata(clean_output))
    if normalized_key == "lf_hid":
        fields.update(_parse_hid_metadata(clean_output))
    if normalized_key == "lf_t55xx":
        fields.update(_parse_t55xx_metadata(clean_output))
    if normalized_key in {
        "hf_emv_pse",
        "hf_emv_search",
        "hf_emv_reader",
        "hf_emv_history",
    }:
        fields.update(_parse_emv_metadata(clean_output, normalized_key))

    return ParsedProxmarkMetadata(fields=_compact(fields))


def _parse_key_value_lines(output: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    aliases = {
        "uid": "uid",
        "atqa": "atqa",
        "sak": "sak",
        "manufacturer": "manufacturer",
        "product type": "product_type",
        "product subtype": "product_subtype",
        "major product version": "major_product_version",
        "minor product version": "minor_product_version",
        "storage size": "storage_size",
        "protocol type": "protocol_type",
        "dsfid": "dsfid",
        "afi": "afi",
        "ic reference": "ic_reference",
        "chip type": "chip_type",
        "modulation": "modulation",
        "bit rate": "bit_rate",
        "max block": "max_block",
        "password mode": "password_mode",
        "sequence terminator": "sequence_terminator",
    }
    for raw_line in output.splitlines():
        line = _clean_line(raw_line)
        match = re.match(r"^([A-Za-z][A-Za-z0-9 /_-]{1,40})\s*(?:\.{2,}|:|=)\s*(.+?)\s*$", line)
        if not match:
            continue
        label = re.sub(r"\s+", " ", match.group(1).strip().lower())
        key = aliases.get(label)
        if key and key not in fields:
            fields[key] = match.group(2).strip()
    return fields


def _parse_hf_iso14443_metadata(output: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    uid = _hex_field(output, r"\b(?:Card\s+UID|UID)\b\s*(?:\.{2,}|:|=)\s*([0-9A-Fa-f][0-9A-Fa-f :\-]{3,})")
    atqa = _hex_field(output, r"\bATQA\b\s*(?:\.{2,}|:|=)\s*([0-9A-Fa-f][0-9A-Fa-f :\-]{1,})")
    sak = _hex_field(output, r"\bSAK\b\s*(?:\.{2,}|:|=)\s*(0x[0-9A-Fa-f]+|[0-9A-Fa-f]{1,2})")
    if uid:
        fields["uid"] = uid
        fields["uid_length_bytes"] = len(uid.split(":"))
    if atqa:
        fields["atqa"] = atqa
    if sak:
        fields["sak"] = sak

    lower = output.lower()
    if "static nonce" in lower:
        fields["nonce_type"] = "static"
    elif "weak prng" in lower:
        fields["nonce_type"] = "weak_prng"
    elif "hard prng" in lower:
        fields["nonce_type"] = "hard_prng"
    if "magic capabilities" in lower or "magic card" in lower:
        fields["magic_card_indicator"] = True
    uid_classification = re.search(r"\bUID\b[^\r\n]*\(([^\r\n)]+)\)", output, re.I)
    if uid_classification:
        classification = uid_classification.group(1).strip()
        fields["uid_classification"] = classification
        classification_lower = classification.lower()
        fields["non_unique_uid"] = "non-unique" in classification_lower
        fields["fixed_uid"] = "fixed" in classification_lower

    ats = _hex_field(output, r"\bATS\b\s*(?:\.{2,}|:|=)\s*([0-9A-Fa-f][0-9A-Fa-f ]{5,})")
    if ats:
        fields["ats"] = ats
        fields["ats_length_bytes"] = len(ats.split(":"))
    historical = re.search(r"^\s*(?:\[.\]\s*)?([0-9A-Fa-f]{8,})\s+-", output, re.M)
    if historical:
        fields["historical_bytes"] = historical.group(1).upper()
    for key, pattern in {
        "fsci": r"\bFSCI\s+is\s+(\d+)",
        "fsc_bytes": r"\bFSC\s*=\s*(\d+)",
        "sfgi": r"\bSFGI\s*=\s*(\d+)",
        "fwi": r"\bFWI\s*=\s*(\d+)",
    }.items():
        match = re.search(pattern, output, re.I)
        if match:
            fields[key] = int(match.group(1))
    nad = re.search(r"\bNAD\s+is\s+(NOT\s+)?supported", output, re.I)
    cid = re.search(r"\bCID\s+is\s+(NOT\s+)?supported", output, re.I)
    if nad:
        fields["nad_supported"] = nad.group(1) is None
    if cid:
        fields["cid_supported"] = cid.group(1) is None
    return fields


def _parse_type2_metadata(output: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    memory_match = re.search(
        r"(?:available\s+memory|user\s+memory|memory\s+size)\s*(?:\.{2,}|:|=)\s*(\d+)\s*bytes?",
        output,
        re.I,
    )
    pages_match = re.search(r"\b(\d+)\s+pages?\b", output, re.I)
    version_match = re.search(r"\b(?:Version|TYPE)\s*(?:\.{2,}|:|=)\s*(.+)", output, re.I)
    if memory_match:
        fields["memory_size_bytes"] = int(memory_match.group(1))
    if pages_match:
        fields["page_count"] = int(pages_match.group(1))
    if version_match:
        fields["version"] = version_match.group(1).strip()
    fields["password_protection_indicator"] = bool(
        re.search(r"\b(?:AUTH0|PWD|password protection)\b", output, re.I)
    )
    fields["signature_present"] = bool(re.search(r"\boriginality signature\b", output, re.I))
    return fields


def _parse_iso15693_metadata(output: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    uid = _hex_field(output, r"\bUID\b\s*(?:\.{2,}|:|=)\s*([0-9A-Fa-f][0-9A-Fa-f :\-]{7,})")
    memory_match = re.search(
        r"(?:memory|block size)\s*(?:\.{2,}|:|=)\s*(\d+)\s+blocks?\s*(?:x|of)?\s*(\d+)\s+bytes?",
        output,
        re.I,
    )
    if uid:
        fields["uid"] = uid
    if memory_match:
        fields["block_count"] = int(memory_match.group(1))
        fields["block_size_bytes"] = int(memory_match.group(2))
        fields["memory_size_bytes"] = int(memory_match.group(1)) * int(memory_match.group(2))
    return fields


def _parse_em410x_metadata(output: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    identifier = _hex_field(output, r"\bEM\s*410x\s+ID\s*[:=]?\s*([0-9A-Fa-f]{8,})")
    if identifier:
        fields["identifier"] = identifier
        fields["bit_length"] = len(identifier.split(":")) * 8
    return fields


def _parse_hid_metadata(output: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    patterns = {
        "format": r"\b(?:HID\s+)?Prox\s+([^\r\n]+?)(?:\s+FC:|$)",
        "facility_code": r"\bFC\s*[:=]\s*(\d+)",
        "card_number": r"\b(?:Card|CN)\s*[:=]\s*(\d+)",
        "raw": r"\braw\s*[:=]\s*([0-9A-Fa-f]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, output, re.I)
        if match:
            value = match.group(1).strip()
            fields[key] = int(value) if key in {"facility_code", "card_number"} else value
    return fields


def _parse_t55xx_metadata(output: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    config_match = re.search(r"\b(?:Config(?:uration)? block|Block 0)\b[^0-9A-Fa-f]*([0-9A-Fa-f]{8})", output, re.I)
    if config_match:
        fields["configuration_block"] = config_match.group(1).upper()
    return fields


def _parse_emv_metadata(output: str, command_key: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    aids = _extract_emv_aids(output)
    labels = _extract_emv_text_values(output, ("Application", "Label"))
    languages = _extract_emv_text_values(output, ("Language",))
    currencies = _extract_emv_text_values(output, ("Currency Code",))
    effective_dates = _extract_emv_text_values(output, ("Effective date",))
    expiration_dates = _extract_emv_text_values(output, ("Expiration date",))
    pan_sequences = _extract_emv_text_values(output, ("PAN Sequence",))
    redacted_fields = redacted_field_markers(output)
    pan_last_four = re.search(
        r"\[REDACTED:PAN:LAST4-(\d{4})\]",
        output,
        re.I,
    )
    payment_systems = sorted(
        {
            system
            for aid in aids
            if (system := _payment_system_for_aid(aid)) is not None
        }
    )
    if aids:
        fields["emv_application_detected"] = True
        fields["application_identifiers"] = aids
        fields["application_count"] = len(aids)
    if labels:
        fields["application_labels"] = labels
    if languages:
        fields["language_preferences"] = languages
    if currencies:
        fields["currency_metadata"] = currencies
    if effective_dates:
        fields["effective_dates"] = effective_dates
    if expiration_dates:
        fields["expiration_dates"] = expiration_dates
    if pan_sequences:
        fields["pan_sequence_numbers"] = pan_sequences
    if pan_last_four:
        fields["pan"] = f"•••• {pan_last_four.group(1)}"
    if "TRACK_DATA" in redacted_fields:
        fields["track_2_equivalent"] = "Present (redacted)"
    if payment_systems:
        fields["payment_systems"] = payment_systems
    if redacted_fields:
        fields["sensitive_fields_redacted"] = redacted_fields
        fields["sensitive_data_present"] = True

    status_words = sorted(
        {
            re.sub(r"\s+", "", match.group(1)).upper()
            for match in re.finditer(
                r"(?:\bSW\b\s*[:=]?\s*|\[REDACTED:EMV_RESPONSE_BODY\]\s*)([0-9A-Fa-f]{2}\s*[0-9A-Fa-f]{2})",
                output,
                re.I,
            )
        }
    )
    if status_words:
        fields["status_words"] = status_words

    if command_key == "hf_emv_pse":
        fields["ppse_attempted"] = True
        fields["ppse_available"] = bool(aids) and not bool(
            re.search(r"can't select (?:pse|ppse)|not found", output, re.I)
        )
    elif command_key == "hf_emv_search":
        fields["aid_search_completed"] = bool(re.search(r"search completed", output, re.I))
    elif command_key == "hf_emv_reader":
        fields["application_reader_completed"] = bool(
            aids or labels or re.search(r"application|currency code|GPO", output, re.I)
        )
        fields["record_read_evidence"] = bool(
            re.search(r"read\s+record|track\s*[12]|PAN", output, re.I)
        )
    elif command_key == "hf_emv_history":
        fields["apdu_trace_present"] = "[REDACTED:EMV_" in output or bool(
            re.search(r"\b(?:SELECT|GPO|READ RECORD|GET DATA)\b", output, re.I)
        )
        fields["apdu_frame_count"] = sum(
            1
            for line in output.splitlines()
            if len(line.split("|")) >= 5
            and line.split("|")[2].strip().lower() in {"rdr", "reader", "tag", "card"}
        )
    return fields


def _extract_emv_aids(output: str) -> list[str]:
    candidates: list[str] = []
    patterns = (
        r"\bAID\b[^0-9A-Fa-f]{0,20}([0-9A-Fa-f][0-9A-Fa-f ]{9,31})",
        r"\|\s*([0-9A-Fa-f]{10,32})\s*\|",
        r"\bSelecting\s+AID\s*:?\s*([0-9A-Fa-f ]{10,32})",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, output, re.I):
            value = re.sub(r"\s+", "", match.group(1)).upper()
            if 10 <= len(value) <= 32 and len(value) % 2 == 0:
                candidates.append(value)
    return list(dict.fromkeys(candidates))


def _extract_emv_text_values(output: str, labels: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    label_pattern = "|".join(re.escape(item) for item in labels)
    for match in re.finditer(
        rf"^(?:\s*\[[^\]]+\]\s*)?(?:{label_pattern})\s*(?:\.+|:|=)\s*(.+?)\s*$",
        output,
        re.I | re.M,
    ):
        value = match.group(1).strip()
        if value and "[REDACTED:" not in value:
            values.append(value)
    return list(dict.fromkeys(values))


def _payment_system_for_aid(aid: str) -> str | None:
    prefixes = {
        "A000000003": "Visa",
        "A000000004": "Mastercard",
        "A000000025": "American Express",
        "A000000065": "JCB",
        "A000000152": "Discover",
        "A000000333": "UnionPay",
        "A000000228": "Saudi Payments",
    }
    return next((name for prefix, name in prefixes.items() if aid.startswith(prefix)), None)


def _hex_field(output: str, pattern: str) -> str | None:
    match = re.search(pattern, output, re.I)
    if not match:
        return None
    value = match.group(1)
    if value.lower().startswith("0x"):
        return value.upper()
    pairs = re.findall(r"[0-9A-Fa-f]{2}", value)
    return ":".join(pair.upper() for pair in pairs) if pairs else None


def _clean_line(line: str) -> str:
    return re.sub(r"^\s*\[[^\]]+\]\s*", "", line).strip()


def _compact(fields: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in fields.items() if value not in (None, "", {})}
