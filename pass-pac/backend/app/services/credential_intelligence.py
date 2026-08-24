from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.detected_card import DetectedCard
from app.services.card_service import get_card_or_404

FINGERPRINT_VERSION = "credential-fingerprint-v1"
COMPARE_FIELDS = (
    "technology",
    "card_type",
    "protocol",
    "atqa",
    "sak",
    "uid_classification",
    "ats",
    "historical_bytes",
    "memory_size_bytes",
    "page_count",
    "block_count",
    "bit_length",
)


def build_card_intelligence(db: Session, card_id: int) -> dict[str, Any]:
    target = get_card_or_404(db, card_id)
    target_uid = _normalize_uid(target.uid)
    all_cards = list(
        db.scalars(
            select(DetectedCard).order_by(
                DetectedCard.created_at.desc(),
                DetectedCard.id.desc(),
            )
        ).all()
    )
    matching_cards = [card for card in all_cards if _normalize_uid(card.uid) == target_uid]
    target_features = _card_features(target)
    observations = [
        _observation(card, target_features)
        for card in matching_cards
    ]
    cross_session = len({card.session_id for card in matching_cards}) > 1
    inconsistent = any(
        observation["differences"]
        for observation in observations
        if observation["card_id"] != target.id
    )
    non_unique_uid = bool(target_features.get("non_unique_uid"))
    risk_level, summary = _risk_summary(
        observation_count=len(matching_cards),
        cross_session=cross_session,
        inconsistent=inconsistent,
        non_unique_uid=non_unique_uid,
    )

    return {
        "fingerprint_version": FINGERPRINT_VERSION,
        "card_id": target.id,
        "uid": target.uid,
        "fingerprint": _fingerprint(target_features),
        "observation_count": len(matching_cards),
        "session_count": len({card.session_id for card in matching_cards}),
        "cross_session_duplicate": cross_session,
        "inconsistent_identity": inconsistent,
        "non_unique_uid": non_unique_uid,
        "risk_level": risk_level,
        "confidence": "high" if len(matching_cards) > 1 else "baseline",
        "summary": summary,
        "compared_fields": list(COMPARE_FIELDS),
        "target_features": target_features,
        "observations": observations,
    }


def _observation(
    card: DetectedCard,
    target_features: dict[str, Any],
) -> dict[str, Any]:
    features = _card_features(card)
    differences: list[dict[str, Any]] = []
    matches: list[str] = []
    for field in COMPARE_FIELDS:
        target_value = target_features.get(field)
        observed_value = features.get(field)
        if target_value in (None, "", 0) or observed_value in (None, "", 0):
            continue
        if _normalize_feature(field, target_value) == _normalize_feature(field, observed_value):
            matches.append(field)
        else:
            differences.append(
                {
                    "field": field,
                    "target": target_value,
                    "observed": observed_value,
                }
            )
    return {
        "card_id": card.id,
        "session_id": card.session_id,
        "created_at": card.created_at,
        "source": features.get("source"),
        "card_type": card.card_type,
        "protocol": card.protocol,
        "fingerprint": _fingerprint(features),
        "matching_fields": matches,
        "differences": differences,
    }


def _card_features(card: DetectedCard) -> dict[str, Any]:
    normalized = _as_dict(card.normalized_data_json)
    raw = _as_dict(card.raw_output_json)
    analysis = _as_dict(normalized.get("analysis_fields"))
    inspection = _as_dict(normalized.get("inspection"))
    inspection_fields = _as_dict(inspection.get("combined_fields"))
    memory = _as_dict(normalized.get("memory"))
    return _compact(
        {
            "technology": card.technology,
            "card_type": card.card_type,
            "protocol": card.protocol,
            "uid": _normalize_uid(card.uid),
            "source": normalized.get("source"),
            "atqa": analysis.get("atqa") or raw.get("atqa"),
            "sak": analysis.get("sak") or raw.get("sak"),
            "uid_classification": analysis.get("uid_classification")
            or inspection_fields.get("uid_classification"),
            "non_unique_uid": analysis.get("non_unique_uid")
            or inspection_fields.get("non_unique_uid"),
            "ats": analysis.get("ats") or inspection_fields.get("ats"),
            "historical_bytes": analysis.get("historical_bytes")
            or inspection_fields.get("historical_bytes"),
            "memory_size_bytes": analysis.get("memory_size_bytes")
            or memory.get("estimated_bytes"),
            "page_count": analysis.get("page_count") or memory.get("page_count"),
            "block_count": analysis.get("block_count") or memory.get("block_count"),
            "bit_length": analysis.get("bit_length") or raw.get("bit_length"),
        }
    )


def _risk_summary(
    observation_count: int,
    cross_session: bool,
    inconsistent: bool,
    non_unique_uid: bool,
) -> tuple[str, str]:
    if cross_session and inconsistent:
        return (
            "high",
            "The same UID appears across sessions with conflicting identity metadata. "
            "Review the observations for credential reuse, copied identifiers, parser "
            "differences, or intentionally non-unique media.",
        )
    if cross_session and non_unique_uid:
        return (
            "low",
            "The UID repeats across sessions, but the card reports that its identifier is "
            "non-unique. Treat the UID as a weak correlation hint rather than an identity.",
        )
    if cross_session:
        return (
            "medium",
            "The same UID was observed in multiple sessions with stable available metadata. "
            "Confirm whether this is expected credential reuse or a duplicated identifier.",
        )
    if observation_count > 1:
        return (
            "informational",
            "The UID was observed repeatedly within one session and provides a local stability baseline.",
        )
    return (
        "informational",
        "This is the first stored observation of the UID. Additional authorized sessions are needed for comparison.",
    )


def _fingerprint(features: dict[str, Any]) -> str:
    identity_features = {
        key: features[key]
        for key in ("uid", "non_unique_uid", *COMPARE_FIELDS)
        if key in features
    }
    canonical = json.dumps(
        identity_features,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def _normalize_feature(field: str, value: Any) -> str:
    text = str(value).strip().upper()
    if field in {"atqa", "sak", "ats", "historical_bytes"}:
        return re.sub(r"[^0-9A-F]", "", text)
    return re.sub(r"\s+", " ", text)


def _normalize_uid(value: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", value).upper()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _compact(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item not in (None, "", 0, {})}
