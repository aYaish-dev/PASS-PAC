from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCORER_VERSION = "dataset-similarity-v1"
MINIMUM_MATCH_SCORE = 25


def load_dataset_samples(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def correlate_payload_with_dataset(
    observed: dict[str, Any],
    dataset_samples: list[dict[str, Any]],
    limit: int = 5,
) -> dict[str, Any]:
    observed_features = _feature_vector(observed)
    matches: list[dict[str, Any]] = []

    for index, sample in enumerate(dataset_samples):
        sample_features = _feature_vector(sample)
        reasons = _score_features(observed_features, sample_features)
        score = sum(int(reason["points"]) for reason in reasons)
        if score < MINIMUM_MATCH_SCORE:
            continue

        metadata = _as_dict(sample.get("metadata"))
        matches.append(
            {
                "sample_index": index,
                "score": min(score, 100),
                "confidence": _confidence(score),
                "source": str(sample.get("source") or "dataset"),
                "dataset": _optional_str(sample.get("dataset") or metadata.get("dataset")),
                "source_path": _optional_str(metadata.get("source_path")),
                "source_file": _optional_str(metadata.get("source_file")),
                "source_sha256": _optional_str(metadata.get("source_sha256")),
                "card_type": _optional_str(sample.get("card_type") or sample.get("type")),
                "protocol": _optional_str(sample.get("protocol")),
                "uid": _optional_str(sample.get("uid")),
                "risk_level": _optional_str(sample.get("risk_level") or sample.get("risk")),
                "match_reasons": [str(reason["field"]) for reason in reasons],
                "match_details": reasons,
            }
        )

    matches.sort(
        key=lambda item: (
            -int(item["score"]),
            str(item.get("source_path") or item.get("source_file") or ""),
            int(item["sample_index"]),
        )
    )
    selected_matches = matches[: max(1, limit)]
    best_score = int(selected_matches[0]["score"]) if selected_matches else 0
    return {
        "scorer_version": SCORER_VERSION,
        "evaluated_samples": len(dataset_samples),
        "observed_features": observed_features,
        "best_score": best_score,
        "confidence": _confidence(best_score) if selected_matches else "none",
        "match_count": len(matches),
        "matches": selected_matches,
    }


def correlate_payload_with_file(
    observed: dict[str, Any],
    dataset_path: Path,
    limit: int = 5,
) -> dict[str, Any]:
    return correlate_payload_with_dataset(
        observed,
        load_dataset_samples(dataset_path),
        limit=limit,
    )


def _score_features(
    observed: dict[str, Any],
    sample: dict[str, Any],
) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    _add_exact_reason(reasons, "exact_uid", 50, observed, sample, "uid")

    observed_type = _optional_str(observed.get("card_type"))
    sample_type = _optional_str(sample.get("card_type"))
    if observed_type and sample_type:
        if _normalize_text(observed_type) == _normalize_text(sample_type):
            _add_reason(reasons, "card_type", 15, observed_type, sample_type)
        elif _card_family(observed_type) == _card_family(sample_type):
            _add_reason(reasons, "card_family", 12, observed_type, sample_type)

    observed_protocol = _optional_str(observed.get("protocol"))
    sample_protocol = _optional_str(sample.get("protocol"))
    if observed_protocol and sample_protocol:
        if _normalize_text(observed_protocol) == _normalize_text(sample_protocol):
            _add_reason(reasons, "protocol", 10, observed_protocol, sample_protocol)
        elif _protocol_family(observed_protocol) == _protocol_family(sample_protocol):
            _add_reason(reasons, "protocol_family", 8, observed_protocol, sample_protocol)

    _add_exact_reason(reasons, "technology", 5, observed, sample, "technology")
    _add_exact_reason(reasons, "uid_length", 5, observed, sample, "uid_length")
    _add_equivalent_hex_reason(reasons, "atqa", 4, observed, sample)
    _add_equivalent_hex_reason(reasons, "sak", 4, observed, sample)

    observed_memory = _as_dict(observed.get("memory"))
    sample_memory = _as_dict(sample.get("memory"))
    for key in ("page_count", "block_count", "memory_size_bytes"):
        observed_value = _positive_int(observed_memory.get(key))
        sample_value = _positive_int(sample_memory.get(key))
        if observed_value and sample_value and observed_value == sample_value:
            _add_reason(reasons, f"memory_{key}", 4, observed_value, sample_value)
            break

    _add_exact_reason(reasons, "bit_length", 3, observed, sample, "bit_length")
    return reasons


def _feature_vector(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _as_dict(payload.get("normalized_data_json")) or _as_dict(
        payload.get("normalized_data")
    )
    raw = _as_dict(payload.get("raw_output_json")) or _as_dict(payload.get("raw_output"))
    if not raw:
        raw = _as_dict(normalized.get("raw_output"))
    flipper = _as_dict(payload.get("flipper")) or _as_dict(normalized.get("flipper"))
    inspection = _as_dict(payload.get("inspection")) or _as_dict(normalized.get("inspection"))
    inspection_fields = _as_dict(inspection.get("combined_fields"))
    identity_fields = _as_dict(payload.get("fields"))

    uid = _optional_str(payload.get("uid") or normalized.get("uid"))
    card_type = _optional_str(
        payload.get("card_type")
        or payload.get("type")
        or normalized.get("card_type")
        or raw.get("device_type")
        or flipper.get("device_type")
    )
    protocol = _optional_str(payload.get("protocol") or normalized.get("protocol"))
    technology = _optional_str(payload.get("technology") or normalized.get("technology"))
    atqa = _optional_str(
        payload.get("atqa")
        or raw.get("atqa")
        or flipper.get("atqa")
        or inspection_fields.get("atqa")
    )
    sak = _optional_str(
        payload.get("sak")
        or raw.get("sak")
        or flipper.get("sak")
        or inspection_fields.get("sak")
    )
    bit_length = _positive_int(
        identity_fields.get("bit_length")
        or raw.get("bit_length")
        or flipper.get("bit_length")
        or inspection_fields.get("bit_length")
    )

    normalized_memory = _as_dict(normalized.get("memory"))
    flipper_memory = _as_dict(flipper.get("memory"))
    raw_memory = _as_dict(raw.get("memory"))
    memory = {
        "page_count": _positive_int(
            inspection_fields.get("page_count")
            or normalized_memory.get("page_count")
            or flipper_memory.get("page_count")
            or _count_memory_entries(raw_memory, "page")
        ),
        "block_count": _positive_int(
            inspection_fields.get("block_count")
            or normalized_memory.get("block_count")
            or flipper_memory.get("block_count")
            or _count_memory_entries(raw_memory, "block")
        ),
        "memory_size_bytes": _positive_int(
            inspection_fields.get("memory_size_bytes")
            or normalized_memory.get("estimated_bytes")
            or flipper_memory.get("estimated_bytes")
        ),
    }
    return _compact(
        {
            "uid": _normalize_uid(uid),
            "uid_length": _uid_length(uid),
            "card_type": card_type,
            "protocol": protocol,
            "technology": _technology_family(technology, protocol),
            "atqa": _normalize_hex(atqa),
            "sak": _normalize_hex(sak),
            "bit_length": bit_length,
            "memory": _compact(memory),
        }
    )


def _add_exact_reason(
    reasons: list[dict[str, Any]],
    field: str,
    points: int,
    observed: dict[str, Any],
    sample: dict[str, Any],
    feature_key: str,
) -> None:
    observed_value = observed.get(feature_key)
    sample_value = sample.get(feature_key)
    if observed_value is None or sample_value is None:
        return
    if observed_value == sample_value:
        _add_reason(reasons, field, points, observed_value, sample_value)


def _add_equivalent_hex_reason(
    reasons: list[dict[str, Any]],
    field: str,
    points: int,
    observed: dict[str, Any],
    sample: dict[str, Any],
) -> None:
    observed_value = _optional_str(observed.get(field))
    sample_value = _optional_str(sample.get(field))
    if not observed_value or not sample_value:
        return
    observed_bytes = _hex_bytes(observed_value)
    sample_bytes = _hex_bytes(sample_value)
    if observed_bytes == sample_bytes or observed_bytes == list(reversed(sample_bytes)):
        _add_reason(reasons, field, points, observed_value, sample_value)


def _add_reason(
    reasons: list[dict[str, Any]],
    field: str,
    points: int,
    observed: Any,
    sample: Any,
) -> None:
    reasons.append(
        {
            "field": field,
            "points": points,
            "observed": observed,
            "dataset": sample,
        }
    )


def _confidence(score: int) -> str:
    if score >= 90:
        return "exact"
    if score >= 70:
        return "strong"
    if score >= 40:
        return "moderate"
    if score >= MINIMUM_MATCH_SCORE:
        return "weak"
    return "none"


def _card_family(value: str) -> str:
    normalized = _normalize_text(value)
    families = (
        "MIFARECLASSIC",
        "MIFAREDESFIRE",
        "NTAG",
        "ULTRALIGHT",
        "ISO15693",
        "HIDPROX",
        "EM410",
        "T55",
        "ICLASS",
    )
    for family in families:
        if family in normalized:
            return family
    return normalized


def _protocol_family(value: str) -> str:
    normalized = _normalize_text(value)
    if "14443A" in normalized:
        return "ISO14443A"
    if "15693" in normalized:
        return "ISO15693"
    if "EM410" in normalized:
        return "EM410X"
    if "HID" in normalized:
        return "HIDPROX"
    if "125KHZ" in normalized or "LF" == normalized:
        return "LF"
    return normalized


def _technology_family(value: str | None, protocol: str | None) -> str | None:
    normalized = _normalize_text(value or "")
    protocol_family = _protocol_family(protocol or "")
    if normalized in {"HF", "HFNFC", "NFC"} or protocol_family in {"ISO14443A", "ISO15693"}:
        return "HF"
    if normalized in {"LF", "LFRFID"} or protocol_family in {"EM410X", "HIDPROX", "LF"}:
        return "LF"
    return normalized or None


def _normalize_uid(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[^0-9A-Fa-f]", "", value).upper()
    return normalized or None


def _uid_length(value: str | None) -> int:
    normalized = _normalize_uid(value)
    return len(normalized) // 2 if normalized and len(normalized) % 2 == 0 else 0


def _normalize_hex(value: str | None) -> str | None:
    return _normalize_uid(value)


def _hex_bytes(value: str) -> list[str]:
    normalized = _normalize_hex(value) or ""
    return [normalized[index : index + 2] for index in range(0, len(normalized), 2)]


def _normalize_text(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()


def _count_memory_entries(memory: dict[str, Any], prefix: str) -> int:
    return sum(1 for key in memory if str(key).lower().startswith(f"{prefix} "))


def _positive_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _compact(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item not in (None, "", 0, {})}
