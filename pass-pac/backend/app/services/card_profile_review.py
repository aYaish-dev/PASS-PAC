from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from app.services.observation_store import OBSERVATIONS_FILE_NAME
from app.services.dataset_similarity import correlate_payload_with_dataset
from app.services.proxmark_parser import parse_identity_output


DATASET_FILE_NAME = "flipper-imported-cards.json"


def build_card_profile_review(mock_data_dir: str) -> dict[str, Any]:
    mock_data_path = Path(mock_data_dir)
    observations = [_normalize_observation(item) for item in _load_observations(mock_data_path / OBSERVATIONS_FILE_NAME)]
    dataset_samples = _load_json_array(mock_data_path / DATASET_FILE_NAME)
    profiles = _build_profiles(observations, dataset_samples)

    technology_counts = Counter(str(profile["technology"]) for profile in profiles)
    attention_counts = Counter(str(profile["attention_level"]) for profile in profiles)
    dataset_match_count = sum(1 for profile in profiles if profile["dataset_matches"])

    return {
        "summary": {
            "total_observations": len(observations),
            "total_profiles": len(profiles),
            "hf_profiles": technology_counts.get("hf", 0),
            "lf_profiles": technology_counts.get("lf", 0),
            "dataset_samples": len(dataset_samples),
            "dataset_matched_profiles": dataset_match_count,
            "medium_attention_profiles": attention_counts.get("medium", 0),
            "high_attention_profiles": attention_counts.get("high", 0),
        },
        "profiles": profiles,
    }


def _load_observations(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    observations: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("detected") is True:
                observations.append(payload)
    return observations


def _load_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _build_profiles(
    observations: list[dict[str, Any]],
    dataset_samples: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped_observations: dict[str, list[dict[str, Any]]] = {}
    for observation in observations:
        key = _profile_key(observation)
        grouped_observations.setdefault(key, []).append(observation)

    profiles: list[dict[str, Any]] = []
    for group in grouped_observations.values():
        group.sort(key=lambda item: str(item.get("observed_at", "")), reverse=True)
        latest = group[0]
        matches = _find_dataset_matches(latest, dataset_samples)
        findings = _build_findings(latest, matches)

        profiles.append(
            {
                "profile_id": _profile_key(latest),
                "first_seen": str(group[-1].get("observed_at", "")),
                "last_seen": str(latest.get("observed_at", "")),
                "observation_count": len(group),
                "technology": str(latest.get("technology") or "unknown"),
                "card_type": _optional_str(latest.get("card_type")),
                "protocol": _optional_str(latest.get("protocol")),
                "uid": _optional_str(latest.get("uid")),
                "atqa": _optional_str(latest.get("atqa")),
                "sak": _optional_str(latest.get("sak")),
                "fields": _dict_of_strings(latest.get("fields")),
                "attention_level": _attention_level(findings),
                "findings": findings,
                "dataset_matches": matches,
                "raw_output_preview": _preview(str(latest.get("output") or "")),
            }
        )

    return sorted(profiles, key=lambda item: str(item["last_seen"]), reverse=True)


def _normalize_observation(observation: dict[str, Any]) -> dict[str, Any]:
    output = _optional_str(observation.get("output"))
    technology = _optional_str(observation.get("technology"))
    if not output or not technology:
        return observation

    parsed = parse_identity_output(technology, output)
    if not parsed.detected:
        return observation

    normalized = dict(observation)
    normalized["card_type"] = parsed.card_type
    normalized["protocol"] = parsed.protocol
    normalized["uid"] = parsed.uid
    normalized["atqa"] = parsed.atqa
    normalized["sak"] = parsed.sak
    normalized["fields"] = parsed.fields
    return normalized


def _find_dataset_matches(
    observation: dict[str, Any],
    dataset_samples: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return correlate_payload_with_dataset(
        observation,
        dataset_samples,
        limit=8,
    )["matches"]


def _build_findings(
    observation: dict[str, Any],
    matches: list[dict[str, Any]],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    card_type = _optional_str(observation.get("card_type")) or ""
    protocol = _optional_str(observation.get("protocol")) or ""
    uid = _optional_str(observation.get("uid"))
    fields = _dict_of_strings(observation.get("fields"))

    if any("exact_uid" in match["match_reasons"] for match in matches):
        findings.append(
            {
                "level": "medium",
                "title": "Dataset UID match",
                "detail": "This live credential UID appears in the imported local dataset.",
            }
        )

    if "mifare classic" in card_type.lower():
        findings.append(
            {
                "level": "medium",
                "title": "MIFARE Classic profile",
                "detail": "MIFARE Classic credentials should be reviewed carefully in authorized assessments because legacy deployments are often misconfigured.",
            }
        )

    if fields.get("anticollision") == "non-standard":
        findings.append(
            {
                "level": "medium",
                "title": "Non-standard anticollision",
                "detail": "The card responded as ISO 14443-A but did not follow standard anticollision behavior.",
            }
        )

    if protocol and matches and not any("exact_uid" in match["match_reasons"] for match in matches):
        findings.append(
            {
                "level": "informational",
                "title": "Protocol seen in dataset",
                "detail": "The observed protocol family exists in the imported mock dataset.",
            }
        )

    if not uid:
        findings.append(
            {
                "level": "informational",
                "title": "Limited identifier metadata",
                "detail": "No UID or card identifier was parsed from this read-only identify result.",
            }
        )

    if not findings:
        findings.append(
            {
                "level": "informational",
                "title": "No immediate finding",
                "detail": "The profile was saved and is available for local review.",
            }
        )

    return findings


def _attention_level(findings: list[dict[str, str]]) -> str:
    levels = {finding["level"] for finding in findings}
    if "high" in levels:
        return "high"
    if "medium" in levels:
        return "medium"
    return "informational"


def _profile_key(observation: dict[str, Any]) -> str:
    uid = _normalize_uid(_optional_str(observation.get("uid")))
    if uid:
        return f"uid:{uid}"

    protocol = _normalize_text(_optional_str(observation.get("protocol"))) or "unknown-protocol"
    card_type = _normalize_text(_optional_str(observation.get("card_type"))) or "unknown-type"
    technology = _normalize_text(_optional_str(observation.get("technology"))) or "unknown-tech"
    return f"{technology}:{protocol}:{card_type}"


def _normalize_uid(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[^0-9a-fA-F]", "", value).upper()
    return normalized or None


def _normalize_text(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[^a-zA-Z0-9]+", "", value).upper()
    return normalized or None


def _dict_of_strings(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items() if item is not None}


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _preview(value: str, limit: int = 1200) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}..."
