from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.detected_card import DetectedCard
from app.models.finding import Finding


@dataclass(frozen=True)
class AnalysisRuleResult:
    rule_id: str
    title: str
    description: str
    risk_level: str
    recommendation: str


def analyze_card(card: DetectedCard) -> AnalysisRuleResult:
    context = build_analysis_context(card)
    card_type = card.card_type.lower()
    protocol = card.protocol.lower()

    if context["is_configurable_lf"]:
        return AnalysisRuleResult(
            rule_id="lf_configurable_credential",
            title="Configurable LF credential observed",
            description=(
                "The simulator evidence indicates a configurable low-frequency "
                "credential. The rule matched on card type, protocol, or parsed "
                "dataset fields rather than the display label alone."
            ),
            risk_level="high",
            recommendation=(
                "Validate whether this credential type is expected in the scoped "
                "environment, document its business purpose, and review replacement "
                "or compensating controls if it is not required."
            ),
        )

    if context["is_mifare_classic"] and context["memory_dump_present"]:
        risk_level = "high" if context["memory_estimated_bytes"] >= 1024 else "medium"
        return AnalysisRuleResult(
            rule_id="hf_mifare_memory_dump",
            title="MIFARE Classic memory dump observed",
            description=(
                "The simulator evidence includes MIFARE Classic indicators and parsed "
                "memory data from the dataset. PASS-PAC preserved the memory summary, "
                "ATQA/SAK values, source file metadata, and UID profile for review."
            ),
            risk_level=risk_level,
            recommendation=(
                "Confirm that the imported dataset belongs to the authorized scope, "
                "review the memory evidence with the assessment owner, and prioritize "
                "migration or compensating controls when full credential memory is "
                "present."
            ),
        )

    if context["is_mifare_classic"]:
        return AnalysisRuleResult(
            rule_id="hf_mifare_classic",
            title="Legacy MIFARE Classic credential observed",
            description=(
                "The simulator evidence indicates a MIFARE Classic credential using "
                "card type, protocol, ATQA/SAK, or Flipper device fields. This "
                "credential family should be reviewed as part of an authorized "
                "access-control assessment."
            ),
            risk_level="medium",
            recommendation=(
                "Confirm whether MIFARE Classic is approved for the assessed site, "
                "verify whether stronger credential options are available, and include "
                "the result in the assessment report for stakeholder review."
            ),
        )

    if context["is_hid_prox"]:
        return AnalysisRuleResult(
            rule_id="lf_hid_prox",
            title="Legacy proximity credential observed",
            description=(
                "The simulator evidence indicates a HID/proximity credential through "
                "card type, protocol, or imported RFID key type fields."
            ),
            risk_level="medium",
            recommendation=(
                "Confirm that this credential format is intentionally supported and "
                "document any planned migration, monitoring, or compensating controls."
            ),
        )

    if context["is_short_hf_uid"]:
        return AnalysisRuleResult(
            rule_id="hf_short_uid",
            title="Short HF UID observed",
            description=(
                "The simulator evidence shows an HF/NFC credential with a short UID "
                "profile. PASS-PAC flagged this from normalized UID length, not only "
                "from the card type."
            ),
            risk_level="medium",
            recommendation=(
                "Review whether short UID credentials are expected in the scoped "
                "environment and confirm the access-control system does not rely on "
                "UID-only trust decisions."
            ),
        )

    if context["is_basic_lf_identifier"]:
        return AnalysisRuleResult(
            rule_id="lf_basic_identifier",
            title="Basic LF identifier credential observed",
            description=(
                "The simulator evidence indicates a basic low-frequency identifier "
                "credential. The rule used card type, protocol, key type, and bit "
                "length from imported RFID data where available."
            ),
            risk_level="low",
            recommendation=(
                "Confirm that the credential belongs to the authorized environment "
                "and include the identifier in local evidence records."
            ),
        )

    if context["is_nfc_tag"]:
        return AnalysisRuleResult(
            rule_id="hf_nfc_tag",
            title="NFC tag credential observed",
            description=(
                "The simulator evidence indicates an NFC tag-style credential. Parsed "
                "memory and UID metadata are preserved when the source is an imported "
                "Flipper dataset file."
            ),
            risk_level="low",
            recommendation=(
                "Record the tag details, confirm the intended use with the project "
                "scope, and review whether additional controls are needed."
            ),
        )

    if context["is_flipper_import"]:
        return AnalysisRuleResult(
            rule_id="dataset_manual_review",
            title="Imported dataset credential requires review",
            description=(
                "The credential came from an imported dataset and includes source file "
                "metadata, but it does not yet match a dedicated PASS-PAC risk rule."
            ),
            risk_level="informational",
            recommendation=(
                "Review the Flipper parsed fields, normalized evidence, and source "
                "path, then add a dedicated rule if this card family matters for the "
                "assessment scope."
            ),
        )

    return AnalysisRuleResult(
        rule_id="manual_review",
        title="Credential requires manual review",
        description=(
            "The simulated scan identified a credential type that does not yet match "
            "a specific PASS-PAC rule. The result has been saved for manual analyst "
            "review."
        ),
        risk_level="informational",
        recommendation=(
            "Review the normalized and raw evidence, then add a dedicated rule if this "
            "credential type is important for the assessment scope."
        ),
    )


def create_finding_for_card(db: Session, card: DetectedCard) -> Finding:
    result = analyze_card(card)
    card.risk_level = result.risk_level

    finding = Finding(
        session_id=card.session_id,
        card_id=card.id,
        title=result.title,
        description=result.description,
        risk_level=result.risk_level,
        recommendation=result.recommendation,
        evidence_json=build_evidence(card, result),
    )
    db.add(finding)
    return finding


def build_evidence(
    card: DetectedCard,
    result: AnalysisRuleResult,
) -> dict[str, Any]:
    normalized = card.normalized_data_json or {}
    context = build_analysis_context(card)
    return {
        "rule_id": result.rule_id,
        "uid": card.uid,
        "card_type": card.card_type,
        "technology": card.technology,
        "frequency": card.frequency,
        "protocol": card.protocol,
        "source": normalized.get("source", "unknown"),
        "dataset_info": normalized.get("dataset_info", {}),
        "uid_format": normalized.get("uid_format", {}),
        "memory": normalized.get("memory", {}),
        "flipper": normalized.get("flipper", {}),
        "metadata": normalized.get("metadata", {}),
        "analysis_fields": normalized.get("analysis_fields", {}),
        "analysis_context": context,
    }


def build_analysis_context(card: DetectedCard) -> dict[str, Any]:
    normalized = card.normalized_data_json or {}
    raw_output = _as_dict(normalized.get("raw_output")) or _as_dict(card.raw_output_json)
    dataset_info = _as_dict(normalized.get("dataset_info"))
    metadata = _as_dict(normalized.get("metadata"))
    uid_format = _as_dict(normalized.get("uid_format"))
    memory = _as_dict(normalized.get("memory"))
    flipper = _as_dict(normalized.get("flipper"))

    card_type = card.card_type.lower()
    protocol = card.protocol.lower()
    key_type = _lower_text(raw_output.get("key_type") or flipper.get("key_type"))
    device_type = _lower_text(raw_output.get("device_type") or flipper.get("device_type"))
    atqa = _lower_text(raw_output.get("atqa") or flipper.get("atqa"))
    sak = _lower_text(raw_output.get("sak") or flipper.get("sak"))
    source = _lower_text(normalized.get("source") or dataset_info.get("source"))
    file_type = _lower_text(dataset_info.get("file_type") or flipper.get("file_type"))
    dataset = _lower_text(dataset_info.get("dataset") or metadata.get("dataset"))
    uid_length = _as_int(uid_format.get("byte_length") or flipper.get("uid_length_bytes"))
    bit_length = _as_int(raw_output.get("bit_length") or flipper.get("bit_length"))
    memory_estimated_bytes = _as_int(memory.get("estimated_bytes"))
    memory_dump_present = bool(memory.get("has_dump"))

    is_mifare_classic = (
        "mifare classic" in card_type
        or "mifare classic" in device_type
        or sak in {"08", "18"}
    )
    is_configurable_lf = (
        "t5577" in card_type
        or "t5577" in key_type
        or "configurable" in protocol
        or "configurable" in key_type
    )
    is_hid_prox = (
        "hid prox" in card_type
        or "hid" in protocol
        or "hid" in key_type
    )
    is_basic_lf_identifier = (
        any(keyword in card_type for keyword in ["em4100", "tk4100"])
        or any(keyword in protocol for keyword in ["em4100", "tk4100"])
        or any(keyword in key_type for keyword in ["em4100", "tk4100"])
        or (card.technology.lower() == "lf rfid" and 0 < bit_length <= 40)
    )
    is_nfc_tag = any(keyword in card_type for keyword in ["ntag", "ultralight"])
    is_flipper_import = source == "flipper-import" or dataset == "uberguidoz-flipper"
    is_short_hf_uid = card.technology.lower() == "hf/nfc" and 0 < uid_length <= 4

    return {
        "matched_rule_context": "dataset-aware-analysis-v1",
        "source": source,
        "dataset": dataset,
        "file_type": file_type,
        "uid_length_bytes": uid_length,
        "bit_length": bit_length,
        "atqa": atqa,
        "sak": sak,
        "memory_dump_present": memory_dump_present,
        "memory_estimated_bytes": memory_estimated_bytes,
        "is_flipper_import": is_flipper_import,
        "is_configurable_lf": is_configurable_lf,
        "is_mifare_classic": is_mifare_classic,
        "is_hid_prox": is_hid_prox,
        "is_short_hf_uid": is_short_hf_uid,
        "is_basic_lf_identifier": is_basic_lf_identifier,
        "is_nfc_tag": is_nfc_tag,
    }


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _lower_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).lower()


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0
