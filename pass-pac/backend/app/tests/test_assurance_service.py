import unittest
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.detected_card import DetectedCard
from app.models.assurance_evidence import CardAssuranceEvidence
from app.models.finding import Finding
from app.schemas.session import SessionCreate
from app.services.assurance_service import (
    evaluate_card_assurance,
    evaluate_session_assurance,
    get_assurance_policy,
    list_assurance_policies,
)
from app.services.session_service import create_session


class AssuranceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def add_card(
        self,
        *,
        session_name: str,
        uid: str = "04:11:22:33:44:55:66",
        card_type: str = "MIFARE DESFire EV3",
        protocol: str = "ISO 14443-A",
        security_fields: dict | None = None,
        finding_risk: str | None = "low",
        review_status: str = "resolved",
    ) -> DetectedCard:
        session = create_session(self.db, SessionCreate(session_name=session_name))
        fields = {
            "authentication": "verified",
            "secure_messaging": "verified",
            "key_management": "diversified per-card",
            "replay_protection": "verified",
            "reader_enforcement": "cryptographic verified",
            "backend_binding": "verified",
            "lifecycle_controls": "verified managed",
            "sak": "20",
            **(security_fields or {}),
        }
        sak = str(fields["sak"])
        card = DetectedCard(
            session_id=session.id,
            technology="HF/NFC",
            frequency="13.56 MHz",
            card_type=card_type,
            protocol=protocol,
            uid=uid,
            risk_level=finding_risk or "informational",
            normalized_data_json={
                "source": "proxmark",
                "analysis_fields": {"sak": sak, "atqa": "03 44"},
                "inspection": {
                    "combined_fields": fields,
                    "commands": [{"command": "hf mfdes info", "success": True}],
                },
            },
            raw_output_json={"sak": sak, "atqa": "03 44"},
        )
        self.db.add(card)
        self.db.flush()
        if finding_risk:
            self.db.add(
                Finding(
                    session_id=session.id,
                    card_id=card.id,
                    title="Test finding",
                    description="Test evidence",
                    risk_level=finding_risk,
                    recommendation="Review the evidence.",
                    evidence_json={"rule_id": "test"},
                    review_status=review_status,
                )
            )
        self.db.commit()
        self.db.refresh(card)
        return card

    def test_policy_profiles_share_one_ten_point_rubric(self) -> None:
        policies = list_assurance_policies()

        self.assertEqual(len(policies), 3)
        self.assertEqual(policies[0]["id"], "university-standard")
        for policy in policies:
            self.assertEqual(
                sum(item["max_points"] for item in policy["criteria"]),
                10,
            )
            self.assertEqual(policy["version"], "2.0")
            self.assertIn("minimum_score", policy)
            self.assertIn("minimum_coverage_percent", policy)

    def test_unknown_policy_returns_clear_404(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            get_assurance_policy("not-a-policy")

        self.assertEqual(caught.exception.status_code, 404)
        self.assertIn("Available policies", caught.exception.detail)

    def test_complete_modern_evidence_scores_ten(self) -> None:
        card = self.add_card(session_name="Complete")

        result = evaluate_card_assurance(self.db, card.id)

        self.assertEqual(result["engine_version"], "assurance-engine-v2.1")
        self.assertEqual(result["methodology_version"], "access-path-score-v2.1")
        self.assertEqual(result["credential_score"], 10.0)
        self.assertEqual(result["credential_coverage_percent"], 100)
        self.assertEqual(result["score"], 10.0)
        self.assertEqual(result["score_lower_bound"], 10)
        self.assertEqual(result["score_upper_bound"], 10)
        self.assertEqual(result["coverage_percent"], 100)
        self.assertEqual(result["grade"], "strong")
        self.assertEqual(result["policy_status"], "pass")
        self.assertTrue(result["meets_policy"])
        self.assertTrue(all(item["rating"] == 2 for item in result["criteria"]))

    def test_unknown_evidence_reports_range_and_inconclusive_status(self) -> None:
        card = self.add_card(
            session_name="Incomplete",
            card_type="MIFARE Classic 1K",
            security_fields={
                "authentication": "unknown",
                "secure_messaging": "unknown",
                "key_management": "",
                "replay_protection": "",
                "reader_enforcement": "",
                "backend_binding": "",
                "lifecycle_controls": "",
                "sak": "08",
            },
            finding_risk="medium",
            review_status="open",
        )

        result = evaluate_card_assurance(self.db, card.id)

        self.assertEqual(result["score"], 5.0)
        self.assertEqual(result["score_lower_bound"], 2)
        self.assertEqual(result["score_upper_bound"], 8)
        self.assertEqual(result["coverage_percent"], 40)
        self.assertEqual(result["unknown_criteria_count"], 3)
        self.assertEqual(result["grade"], "inconclusive")
        self.assertEqual(result["policy_status"], "insufficient_evidence")
        self.assertIsNone(result["meets_policy"])

    def test_operator_evidence_completes_access_path_without_changing_credential_score(self) -> None:
        card = self.add_card(
            session_name="Operator evidence",
            card_type="MIFARE Classic 1K",
            security_fields={
                "authentication": "unknown",
                "secure_messaging": "unknown",
                "key_management": "",
                "replay_protection": "",
                "reader_enforcement": "",
                "backend_binding": "",
                "lifecycle_controls": "",
                "sak": "08",
            },
            finding_risk="medium",
            review_status="open",
        )
        before = evaluate_card_assurance(self.db, card.id)
        self.db.add(
            CardAssuranceEvidence(
                card_id=card.id,
                reader_enforcement="uid_only",
                lifecycle_monitoring="absent",
                evidence_source="Authorized isolated-reader acceptance test",
                confidence="high",
                notes="Controller accepted the presented UID without application authentication.",
                assessed_at=datetime.now(timezone.utc),
            )
        )
        self.db.commit()

        after = evaluate_card_assurance(self.db, card.id)

        self.assertEqual(before["credential_score"], after["credential_score"])
        self.assertEqual(before["credential_coverage_percent"], 67)
        self.assertEqual(after["coverage_percent"], 80)
        self.assertEqual(after["grade"], "weak")
        self.assertEqual(after["policy_status"], "fail")
        self.assertTrue(after["critical_failure"])
        reader_result = next(
            item for item in after["criteria"] if item["id"] == "reader_backend_enforcement"
        )
        self.assertEqual(reader_result["rating"], 0)
        self.assertIn(
            "Operator evidence source: Authorized isolated-reader acceptance test",
            reader_result["evidence"],
        )
        self.assertIsNotNone(after["evidence_snapshot"]["operator_evidence_id"])

    def test_analyst_review_does_not_change_security_score(self) -> None:
        card = self.add_card(
            session_name="Review separation",
            finding_risk="high",
            review_status="open",
        )

        before = evaluate_card_assurance(self.db, card.id)
        finding = self.db.scalar(select(Finding).where(Finding.card_id == card.id))
        assert finding is not None
        finding.review_status = "resolved"
        self.db.commit()
        after = evaluate_card_assurance(self.db, card.id)

        self.assertEqual(before["score"], after["score"])
        self.assertEqual(before["criteria"], after["criteria"])
        self.assertEqual(before["analyst_review"]["status"], "not_started")
        self.assertEqual(after["analyst_review"]["status"], "complete")

    def test_default_key_is_explicit_critical_failure_without_score_cap(self) -> None:
        card = self.add_card(
            session_name="Default key",
            security_fields={"default_key_count": 1},
        )

        result = evaluate_card_assurance(self.db, card.id)

        self.assertEqual(result["score"], 8.0)
        self.assertTrue(result["critical_failure"])
        self.assertEqual(result["policy_status"], "fail")
        key_result = next(
            item for item in result["criteria"] if item["id"] == "key_management"
        )
        self.assertEqual(key_result["rating"], 0)
        self.assertTrue(key_result["critical"])

    def test_score_is_stable_while_policy_decision_changes(self) -> None:
        card = self.add_card(
            session_name="Policy comparison",
            security_fields={
                "key_management": "custom shared",
                "reader_enforcement": "partial backend lookup",
                "lifecycle_controls": "manual",
            },
        )

        standard = evaluate_card_assurance(self.db, card.id, "university-standard")
        restricted = evaluate_card_assurance(self.db, card.id, "restricted-area")

        self.assertEqual(standard["score"], 7.0)
        self.assertEqual(restricted["score"], standard["score"])
        self.assertEqual(standard["policy_status"], "pass")
        self.assertEqual(restricted["policy_status"], "fail")

    def test_session_rollup_orders_weakest_card_first(self) -> None:
        session = create_session(self.db, SessionCreate(session_name="Rollup"))
        strong = DetectedCard(
            session_id=session.id,
            technology="HF/NFC",
            frequency="13.56 MHz",
            card_type="MIFARE DESFire EV3",
            protocol="ISO 14443-A",
            uid="04:AA:BB:CC:DD:EE:01",
            risk_level="low",
            normalized_data_json={
                "source": "proxmark",
                "inspection": {
                    "combined_fields": {
                        "authentication": "verified",
                        "secure_messaging": "verified",
                        "key_management": "diversified per-card",
                        "replay_protection": "verified",
                        "reader_enforcement": "cryptographic verified",
                        "backend_binding": "verified",
                        "lifecycle_controls": "verified managed",
                    },
                    "commands": [{"command": "hf mfdes info", "success": True}],
                },
            },
            raw_output_json={"sak": "20"},
        )
        weak = DetectedCard(
            session_id=session.id,
            technology="LF RFID",
            frequency="125 kHz",
            card_type="T5577",
            protocol="Configurable LF",
            uid="11:22:33:44:55",
            risk_level="high",
            normalized_data_json={
                "source": "proxmark",
                "inspection": {
                    "combined_fields": {
                        "uid_only_authorization": True,
                        "lifecycle_controls": "none",
                    }
                },
            },
            raw_output_json={"key_type": "T5577"},
        )
        self.db.add_all([strong, weak])
        self.db.commit()

        result = evaluate_session_assurance(self.db, session.id)

        self.assertEqual(result["card_count"], 2)
        self.assertEqual(result["cards"][0]["card_id"], weak.id)
        self.assertEqual(result["cards"][0]["score"], 0.0)
        self.assertEqual(result["critical_failure_count"], 1)
        self.assertEqual(result["policy_status_counts"]["pass"], 1)
        self.assertEqual(result["policy_status_counts"]["fail"], 1)
        self.assertEqual(sum(result["grade_counts"].values()), 2)

    def test_em410x_analysis_fields_produce_static_identifier_score(self) -> None:
        session = create_session(self.db, SessionCreate(session_name="EM410x"))
        card = DetectedCard(
            session_id=session.id,
            technology="LF RFID",
            frequency="125 kHz",
            card_type="EM 410x",
            protocol="125kHz LF",
            uid="02:00:AD:3D:4F",
            risk_level="high",
            normalized_data_json={
                "source": "live-proxmark",
                "analysis_fields": {"bit_length": 40},
            },
            raw_output_json={},
        )
        self.db.add(card)
        self.db.commit()

        result = evaluate_card_assurance(self.db, card.id)

        self.assertEqual(result["score"], 0.0)
        self.assertEqual(result["coverage_percent"], 60)
        self.assertEqual(result["score_lower_bound"], 0)
        self.assertEqual(result["score_upper_bound"], 4)
        self.assertTrue(result["critical_failure"])
        self.assertEqual(result["policy_status"], "insufficient_evidence")

    def test_desfire_ev1_gets_capability_credit_without_claiming_verified_use(self) -> None:
        session = create_session(self.db, SessionCreate(session_name="DESFire EV1"))
        card = DetectedCard(
            session_id=session.id,
            technology="HF/NFC",
            frequency="13.56 MHz",
            card_type="MIFARE DESFire EV1",
            protocol="ISO 14443-A",
            uid="04:71:2A:E2:60:63:80",
            risk_level="informational",
            normalized_data_json={"source": "live-proxmark"},
            raw_output_json={"sak": "20"},
        )
        self.db.add(card)
        self.db.commit()

        result = evaluate_card_assurance(self.db, card.id)

        self.assertEqual(result["score"], 5.0)
        self.assertEqual(result["coverage_percent"], 40)
        self.assertEqual(result["score_lower_bound"], 2)
        self.assertEqual(result["score_upper_bound"], 8)
        self.assertEqual(result["grade"], "inconclusive")
        self.assertEqual(result["policy_status"], "insufficient_evidence")

    def test_mifare_default_keys_are_extracted_from_proxmark_output(self) -> None:
        session = create_session(self.db, SessionCreate(session_name="MIFARE keys"))
        card = DetectedCard(
            session_id=session.id,
            technology="HF/NFC",
            frequency="13.56 MHz",
            card_type="MIFARE Classic 1K",
            protocol="ISO 14443-A",
            uid="F9:81:E3:3D",
            risk_level="high",
            normalized_data_json={
                "source": "live-proxmark",
                "raw_output": {
                    "inspection_outputs": {
                        "hf_mifare_classic": (
                            "[+] Sector 0 key A... FFFFFFFFFFFF\n"
                            "[+] Sector 0 key B... FFFFFFFFFFFF\n"
                            "[+] Sector 1 key A... A0A1A2A3A4A5\n"
                            "[+] Sector 1 key B... 123456789ABC"
                        )
                    }
                },
            },
            raw_output_json={"sak": "08"},
        )
        self.db.add(card)
        self.db.commit()

        result = evaluate_card_assurance(self.db, card.id)
        key_result = next(
            item for item in result["criteria"] if item["id"] == "key_management"
        )

        self.assertEqual(key_result["rating"], 0)
        self.assertTrue(key_result["critical"])
        self.assertIn("default_key_count: 3", key_result["evidence"])
        self.assertNotIn("123456789ABC", " ".join(key_result["evidence"]))


if __name__ == "__main__":
    unittest.main()
