import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.detected_card import DetectedCard
from app.schemas.session import SessionCreate
from app.services.credential_intelligence import build_card_intelligence
from app.services.session_service import create_session


class CredentialIntelligenceTests(unittest.TestCase):
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
        session_name: str,
        uid: str,
        card_type: str = "MIFARE Classic 1K",
        sak: str = "08",
        non_unique_uid: bool = False,
    ) -> DetectedCard:
        session = create_session(
            self.db,
            SessionCreate(session_name=session_name),
        )
        card = DetectedCard(
            session_id=session.id,
            technology="HF/NFC",
            frequency="13.56 MHz",
            card_type=card_type,
            protocol="ISO 14443-A",
            uid=uid,
            risk_level="medium",
            normalized_data_json={
                "source": "test",
                "analysis_fields": {
                    "atqa": "00 04",
                    "sak": sak,
                    "non_unique_uid": non_unique_uid,
                },
            },
            raw_output_json={"atqa": "00 04", "sak": sak},
        )
        self.db.add(card)
        self.db.commit()
        self.db.refresh(card)
        return card

    def test_first_observation_creates_baseline(self) -> None:
        card = self.add_card("Baseline", "01:02:03:04")
        intelligence = build_card_intelligence(self.db, card.id)

        self.assertEqual(intelligence["observation_count"], 1)
        self.assertFalse(intelligence["cross_session_duplicate"])
        self.assertEqual(intelligence["risk_level"], "informational")

    def test_stable_cross_session_uid_is_medium(self) -> None:
        target = self.add_card("First", "01:02:03:04")
        self.add_card("Second", "01020304")
        intelligence = build_card_intelligence(self.db, target.id)

        self.assertTrue(intelligence["cross_session_duplicate"])
        self.assertFalse(intelligence["inconsistent_identity"])
        self.assertEqual(intelligence["risk_level"], "medium")
        self.assertEqual(intelligence["session_count"], 2)

    def test_conflicting_metadata_is_high_and_explainable(self) -> None:
        target = self.add_card("First", "01:02:03:04", sak="08")
        self.add_card(
            "Second",
            "01-02-03-04",
            card_type="MIFARE DESFire",
            sak="20",
        )
        intelligence = build_card_intelligence(self.db, target.id)

        self.assertTrue(intelligence["inconsistent_identity"])
        self.assertEqual(intelligence["risk_level"], "high")
        changed_fields = {
            difference["field"]
            for observation in intelligence["observations"]
            for difference in observation["differences"]
        }
        self.assertIn("card_type", changed_fields)
        self.assertIn("sak", changed_fields)

    def test_reported_non_unique_uid_lowers_duplicate_risk(self) -> None:
        target = self.add_card(
            "First",
            "01:02:03:04",
            non_unique_uid=True,
        )
        self.add_card(
            "Second",
            "01:02:03:04",
            non_unique_uid=True,
        )
        intelligence = build_card_intelligence(self.db, target.id)
        self.assertEqual(intelligence["risk_level"], "low")


if __name__ == "__main__":
    unittest.main()
