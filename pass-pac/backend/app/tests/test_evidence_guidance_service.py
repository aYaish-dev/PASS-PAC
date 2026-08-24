import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.detected_card import DetectedCard
from app.models.measurement import ExperimentBatch
from app.schemas.session import SessionCreate
from app.services.evidence_guidance_service import build_evidence_guidance
from app.services.session_service import create_session, start_session


class EvidenceGuidanceServiceTests(unittest.TestCase):
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

    def test_empty_running_live_session_prioritizes_safe_acquisition(self) -> None:
        session = create_session(
            self.db,
            SessionCreate(session_name="Guided acquisition", mode="proxmark"),
        )
        start_session(self.db, session.id)

        result = build_evidence_guidance(self.db, session.id)
        recommendations = {item["id"]: item for item in result["recommendations"]}

        self.assertEqual(result["overall_status"], "acquisition_required")
        self.assertEqual(result["registry_version"], "proxmark-capability-registry-v1.1")
        self.assertTrue(recommendations["device-baseline"]["can_execute"])
        self.assertTrue(recommendations["discover-hf"]["can_execute"])
        self.assertTrue(recommendations["discover-lf"]["can_execute"])
        self.assertEqual(result["executable_recommendation_count"], 3)

    def test_simulator_session_explains_why_recipes_cannot_run(self) -> None:
        session = create_session(
            self.db,
            SessionCreate(session_name="Simulator guidance", mode="simulator"),
        )

        result = build_evidence_guidance(self.db, session.id)
        recipe_actions = [
            item for item in result["recommendations"] if item["action_type"] == "recipe"
        ]

        self.assertTrue(recipe_actions)
        self.assertTrue(all(not item["can_execute"] for item in recipe_actions))
        self.assertTrue(all(item["blocking_reason"] for item in recipe_actions))

    def test_incomplete_card_yields_family_profile_and_control_gaps(self) -> None:
        session = create_session(
            self.db,
            SessionCreate(session_name="Incomplete card", mode="proxmark"),
        )
        start_session(self.db, session.id)
        card = DetectedCard(
            session_id=session.id,
            technology="HF/NFC",
            frequency="13.56 MHz",
            card_type="MIFARE DESFire EV2",
            protocol="ISO 14443-A",
            uid="04:11:22:33:44:55:66",
            risk_level="informational",
            normalized_data_json={
                "source": "live-proxmark",
                "inspection": {
                    "combined_fields": {
                        "authentication": "unknown",
                        "secure_messaging": "unknown",
                        "key_management": "",
                        "replay_protection": "",
                        "reader_enforcement": "",
                        "backend_binding": "",
                        "lifecycle_controls": "",
                    },
                    "commands": [{"command": "hf 14a info", "success": True}],
                },
            },
            raw_output_json={"sak": "20"},
        )
        self.db.add(card)
        self.db.commit()

        result = build_evidence_guidance(self.db, session.id)
        recommendation_ids = {item["id"] for item in result["recommendations"]}

        self.assertIn(f"card-{card.id}-hf-desfire-profile", recommendation_ids)
        self.assertIn("gap-reader_backend_enforcement", recommendation_ids)
        self.assertIn("create-baseline", recommendation_ids)
        self.assertGreater(result["open_gap_count"], 0)
        self.assertEqual(result["overall_status"], "evidence_incomplete")

    def test_completed_baseline_recommends_matched_post_remediation_batch(self) -> None:
        session = create_session(
            self.db,
            SessionCreate(session_name="Completed baseline", mode="proxmark"),
        )
        card = DetectedCard(
            session_id=session.id,
            technology="LF RFID",
            frequency="125 kHz",
            card_type="EM410x",
            protocol="EM410x",
            uid="11:22:33:44:55",
            risk_level="high",
            normalized_data_json={
                "source": "live-proxmark",
                "inspection": {
                    "commands": [
                        {"command": "lf search", "success": True},
                        {"command": "lf em 410x reader", "success": True},
                    ]
                },
            },
            raw_output_json={"output": "authorized observation"},
        )
        self.db.add(card)
        self.db.flush()
        self.db.add(
            ExperimentBatch(
                session_id=session.id,
                name="Baseline",
                condition="baseline",
                status="completed",
                authorization_reference="LAB-001",
                operator_label="operator-1",
                location_label="RFID lab",
                device_model="Proxmark3 Easy 512K",
                client_version="Iceman",
                firmware_version="Iceman",
                antenna_configuration="Stock antennas",
                host_os="Windows 11",
                command_profile="read-only-identification-v1",
            )
        )
        self.db.commit()

        result = build_evidence_guidance(self.db, session.id)
        recommendation_ids = {item["id"] for item in result["recommendations"]}

        self.assertIn("create-post-remediation", recommendation_ids)
        self.assertNotIn("create-baseline", recommendation_ids)
        self.assertNotIn(f"card-{card.id}-lf-em410x-profile", recommendation_ids)


if __name__ == "__main__":
    unittest.main()
