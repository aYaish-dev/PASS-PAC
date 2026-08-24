import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.detected_card import DetectedCard
from app.models.finding import Finding
from app.schemas.finding import FindingUpdate
from app.schemas.session import SessionCreate
from app.services.finding_service import update_finding
from app.services.session_service import create_session


class FindingReviewTests(unittest.TestCase):
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

    def create_finding(self) -> Finding:
        session = create_session(
            self.db,
            SessionCreate(session_name="Finding review test"),
        )
        card = DetectedCard(
            session_id=session.id,
            technology="HF/NFC",
            frequency="13.56 MHz",
            card_type="ISO 14443-A tag",
            protocol="ISO 14443-A",
            uid="01:02:03:04",
            risk_level="medium",
            normalized_data_json={},
            raw_output_json={},
        )
        self.db.add(card)
        self.db.flush()
        finding = Finding(
            session_id=session.id,
            card_id=card.id,
            title="Review required",
            description="Test finding",
            risk_level="medium",
            recommendation="Review locally",
            evidence_json={},
        )
        self.db.add(finding)
        self.db.commit()
        self.db.refresh(finding)
        return finding

    def test_review_status_and_notes_are_persisted(self) -> None:
        finding = self.create_finding()
        self.assertEqual(finding.review_status, "open")

        updated = update_finding(
            self.db,
            finding.id,
            FindingUpdate(
                review_status="confirmed",
                analyst_notes="  Confirmed with the assessment owner.  ",
            ),
        )

        self.assertEqual(updated.review_status, "confirmed")
        self.assertEqual(updated.analyst_notes, "Confirmed with the assessment owner.")
        self.assertIsNotNone(updated.reviewed_at)

    def test_blank_notes_are_normalized_to_none(self) -> None:
        finding = self.create_finding()
        updated = update_finding(
            self.db,
            finding.id,
            FindingUpdate(analyst_notes="   "),
        )
        self.assertIsNone(updated.analyst_notes)


if __name__ == "__main__":
    unittest.main()
