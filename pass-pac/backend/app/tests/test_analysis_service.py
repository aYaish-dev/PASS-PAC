import unittest
from typing import Any

from app.models.detected_card import DetectedCard
from app.services.analysis_service import analyze_card, build_evidence


def make_card(
    *,
    card_type: str,
    technology: str = "LF RFID",
    protocol: str = "Unknown",
    uid: str = "01:23:45:67:89",
    source: str = "simulator",
    dataset: str | None = None,
    file_type: str | None = None,
    uid_length: int | None = None,
    raw_output: dict[str, Any] | None = None,
    memory: dict[str, Any] | None = None,
    flipper: dict[str, Any] | None = None,
    inspection_fields: dict[str, Any] | None = None,
) -> DetectedCard:
    raw_output = raw_output or {}
    flipper = flipper or {}
    dataset_info = {
        "source": source,
        "dataset": dataset,
        "file_type": file_type,
        "source_path": "NFC/example.nfc" if file_type == "nfc" else None,
    }
    normalized_data = {
        "source": source,
        "dataset": dataset,
        "dataset_info": {
            key: value for key, value in dataset_info.items() if value is not None
        },
        "uid_format": {"byte_length": uid_length} if uid_length else {},
        "memory": memory or {},
        "flipper": flipper,
        "inspection": {"combined_fields": inspection_fields or {}},
        "raw_output": raw_output,
        "metadata": {"dataset": dataset} if dataset else {},
    }

    return DetectedCard(
        session_id=1,
        technology=technology,
        frequency="125kHz" if technology == "LF RFID" else "13.56MHz",
        card_type=card_type,
        protocol=protocol,
        uid=uid,
        risk_level="informational",
        normalized_data_json=normalized_data,
        raw_output_json=raw_output,
    )


class AnalysisServiceTests(unittest.TestCase):
    def assert_rule(
        self,
        card: DetectedCard,
        rule_id: str,
        risk_level: str,
    ) -> None:
        result = analyze_card(card)
        self.assertEqual(result.rule_id, rule_id)
        self.assertEqual(result.risk_level, risk_level)

    def test_magic_card_indicator_is_high_risk(self) -> None:
        card = make_card(
            card_type="MIFARE Classic 1K",
            technology="HF/NFC",
            protocol="ISO 14443-A",
            inspection_fields={"magic_card_indicator": True},
        )

        self.assert_rule(card, "hf_magic_card_indicator", "high")

    def test_weak_nonce_indicator_is_high_risk(self) -> None:
        card = make_card(
            card_type="MIFARE Classic 1K",
            technology="HF/NFC",
            protocol="ISO 14443-A",
            inspection_fields={"nonce_type": "weak_prng"},
        )

        self.assert_rule(card, "hf_weak_nonce_indicator", "high")

    def test_non_unique_uid_has_specific_medium_finding(self) -> None:
        card = make_card(
            card_type="ISO 14443-A tag",
            technology="HF/NFC",
            protocol="ISO 14443-A",
            inspection_fields={"non_unique_uid": True},
        )

        self.assert_rule(card, "hf_non_unique_uid", "medium")

    def test_configurable_lf_rule_uses_protocol_context(self) -> None:
        card = make_card(
            card_type="Writable test credential",
            protocol="Configurable LF",
        )

        self.assert_rule(card, "lf_configurable_credential", "high")

    def test_mifare_memory_dump_rule_preserves_dataset_context(self) -> None:
        card = make_card(
            card_type="MIFARE Classic 1K",
            technology="HF/NFC",
            protocol="ISO14443A",
            uid="04:A1:B2:C3:D4:E5:80",
            source="flipper-import",
            dataset="uberguidoz-flipper",
            file_type="nfc",
            uid_length=7,
            raw_output={"device_type": "Mifare Classic", "atqa": "00 04", "sak": "08"},
            memory={"has_dump": True, "entry_count": 2, "estimated_bytes": 32},
            flipper={"file_type": "nfc", "filetype": "Flipper NFC device"},
        )

        result = analyze_card(card)
        evidence = build_evidence(card, result)

        self.assertEqual(result.rule_id, "hf_mifare_memory_dump")
        self.assertEqual(result.risk_level, "medium")
        self.assertEqual(evidence["dataset_info"]["dataset"], "uberguidoz-flipper")
        self.assertEqual(evidence["uid_format"]["byte_length"], 7)
        self.assertTrue(evidence["memory"]["has_dump"])
        self.assertEqual(evidence["flipper"]["filetype"], "Flipper NFC device")

    def test_mifare_full_memory_dump_escalates_to_high(self) -> None:
        card = make_card(
            card_type="MIFARE Classic 1K",
            technology="HF/NFC",
            protocol="ISO14443A",
            source="flipper-import",
            dataset="uberguidoz-flipper",
            file_type="nfc",
            uid_length=7,
            raw_output={"sak": "08"},
            memory={"has_dump": True, "entry_count": 64, "estimated_bytes": 1024},
        )

        self.assert_rule(card, "hf_mifare_memory_dump", "high")

    def test_mifare_without_memory_uses_legacy_rule(self) -> None:
        card = make_card(
            card_type="MIFARE Classic 1K",
            technology="HF/NFC",
            protocol="ISO14443A",
            uid_length=7,
            raw_output={"sak": "08"},
        )

        self.assert_rule(card, "hf_mifare_classic", "medium")

    def test_hid_prox_rule_uses_imported_key_type(self) -> None:
        card = make_card(
            card_type="Imported LF key",
            protocol="Legacy RFID",
            source="flipper-import",
            dataset="uberguidoz-flipper",
            file_type="rfid",
            raw_output={"key_type": "HID Prox"},
            flipper={"file_type": "rfid", "key_type": "HID Prox"},
        )

        self.assert_rule(card, "lf_hid_prox", "medium")

    def test_short_hf_uid_rule_uses_uid_profile(self) -> None:
        card = make_card(
            card_type="Unknown HF badge",
            technology="HF/NFC",
            protocol="ISO14443A",
            uid="DE:AD:BE:EF",
            uid_length=4,
        )

        self.assert_rule(card, "hf_short_uid", "medium")

    def test_basic_lf_identifier_rule_uses_bit_length(self) -> None:
        card = make_card(
            card_type="Imported LF key",
            protocol="Legacy RFID",
            raw_output={"key_type": "EM4100", "bit_length": "40"},
            flipper={"file_type": "rfid", "key_type": "EM4100", "bit_length": 40},
        )

        self.assert_rule(card, "lf_basic_identifier", "low")

    def test_nfc_tag_rule_handles_long_uid_tag_samples(self) -> None:
        card = make_card(
            card_type="NTAG213",
            technology="HF/NFC",
            protocol="ISO14443A",
            uid="04:21:42:63:84:A5:C6",
            uid_length=7,
        )

        self.assert_rule(card, "hf_nfc_tag", "low")

    def test_imported_dataset_unknown_card_requires_dataset_review(self) -> None:
        card = make_card(
            card_type="Custom imported NFC",
            technology="HF/NFC",
            protocol="NFC",
            uid_length=7,
            source="flipper-import",
            dataset="uberguidoz-flipper",
            file_type="nfc",
            flipper={"file_type": "nfc", "filetype": "Flipper NFC device"},
        )

        self.assert_rule(card, "dataset_manual_review", "informational")

    def test_unknown_non_dataset_card_requires_manual_review(self) -> None:
        card = make_card(
            card_type="Custom local badge",
            technology="HF/NFC",
            protocol="NFC",
            uid_length=7,
        )

        self.assert_rule(card, "manual_review", "informational")


if __name__ == "__main__":
    unittest.main()
