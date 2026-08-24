import unittest

from app.services.dataset_similarity import correlate_payload_with_dataset


class DatasetSimilarityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset = [
            {
                "source": "flipper-import",
                "technology": "HF/NFC",
                "card_type": "NTAG213",
                "protocol": "ISO14443A",
                "uid": "04:11:22:33:44:55:66",
                "risk_level": "low",
                "raw_output": {
                    "atqa": "44 00",
                    "sak": "00",
                    "memory": {f"Page {index}": "00 00 00 00" for index in range(45)},
                },
                "metadata": {
                    "dataset": "test-dataset",
                    "source_path": "NFC/ntag213.nfc",
                    "source_sha256": "abc123",
                },
            },
            {
                "source": "simulator",
                "technology": "LF RFID",
                "card_type": "EM4100",
                "protocol": "EM4100",
                "uid": "01:23:45:67:89",
                "raw_output": {"bit_length": 40},
                "metadata": {"dataset": "test-dataset"},
            },
        ]

    def test_exact_uid_and_metadata_produce_exact_match(self) -> None:
        observed = {
            "technology": "hf",
            "card_type": "NTAG213",
            "protocol": "ISO 14443-A",
            "uid": "04 11 22 33 44 55 66",
            "atqa": "00 44",
            "sak": "00",
            "inspection": {"combined_fields": {"page_count": 45}},
        }

        result = correlate_payload_with_dataset(observed, self.dataset)

        self.assertEqual(result["confidence"], "exact")
        self.assertGreaterEqual(result["best_score"], 90)
        self.assertEqual(result["matches"][0]["source_path"], "NFC/ntag213.nfc")
        self.assertIn("exact_uid", result["matches"][0]["match_reasons"])
        self.assertIn("atqa", result["matches"][0]["match_reasons"])

    def test_family_metadata_produces_explainable_moderate_match(self) -> None:
        observed = {
            "technology": "HF/NFC",
            "card_type": "NTAG213",
            "protocol": "ISO14443A",
            "uid": "04:AA:BB:CC:DD:EE:FF",
            "atqa": "44 00",
            "sak": "00",
            "inspection": {"combined_fields": {"page_count": 45}},
        }

        result = correlate_payload_with_dataset(observed, self.dataset)

        self.assertEqual(result["confidence"], "moderate")
        self.assertGreaterEqual(result["best_score"], 40)
        details = result["matches"][0]["match_details"]
        self.assertTrue(all({"field", "points", "observed", "dataset"} <= detail.keys() for detail in details))

    def test_unrelated_card_is_not_reported_as_match(self) -> None:
        observed = {
            "technology": "HF/NFC",
            "card_type": "FeliCa",
            "protocol": "FeliCa",
            "uid": "01:01:01:01:01:01:01:01",
        }

        result = correlate_payload_with_dataset(observed, self.dataset)

        self.assertEqual(result["confidence"], "none")
        self.assertEqual(result["matches"], [])


if __name__ == "__main__":
    unittest.main()
