import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.detected_card import DetectedCard
from app.schemas.measurement import ExperimentBatchCreate, MeasurementTrialCreate
from app.schemas.session import SessionCreate
from app.services.measurement_service import (
    create_experiment_batch,
    create_measurement_trial,
)
from app.services.report_service import (
    generate_measurement_analysis_csv,
    generate_measurement_csv,
    generate_measurement_pdf,
)
from app.services.session_service import create_session


class ReportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.session = create_session(
            self.db,
            SessionCreate(session_name="Research report fixture", mode="proxmark"),
        )
        self.batch = create_experiment_batch(
            self.db,
            self.session.id,
            ExperimentBatchCreate(
                name="Baseline report batch",
                authorization_reference="REPORT-AUTH-001",
                operator_label="operator-1",
                location_label="RFID laboratory",
                device_model="Proxmark3 Easy 512K",
                client_version="Iceman v4.21611",
                firmware_version="Iceman v4.21611",
                antenna_configuration="Stock LF/HF antennas",
                host_os="Windows 11",
            ),
        )
        card = DetectedCard(
            session_id=self.session.id,
            technology="HF/NFC",
            frequency="13.56 MHz",
            card_type="MIFARE Classic 1K",
            protocol="ISO 14443-A",
            uid="SECRET-UID-1234",
            risk_level="high",
            normalized_data_json={"uid": "SECRET-UID-1234", "sak": "08"},
            raw_output_json={"output": "SECRET RAW PROXMARK OUTPUT"},
        )
        self.db.add(card)
        self.db.commit()
        self.trial = create_measurement_trial(
            self.db,
            self.session.id,
            MeasurementTrialCreate(
                batch_id=self.batch.id,
                source_card_id=card.id,
                credential_alias="CARD-HF-01",
                distance_cm=4,
                orientation="parallel",
                presented_face="front",
                success=True,
                classification_result="correct",
                identification_duration_ms=125,
                metadata_fields_count=5,
                data_extracted_bytes=16,
                rf_interference="none",
            ),
        )

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_csv_is_trial_level_and_excludes_operational_uid_and_raw_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = generate_measurement_csv(
                self.db,
                self.session.id,
                output_dir=Path(directory),
            )
            text = artifact.path.read_text(encoding="utf-8-sig")
            rows = list(csv.DictReader(text.splitlines()))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["credential_alias"], "CARD-HF-01")
            self.assertEqual(rows[0]["success"], "true")
            self.assertEqual(rows[0]["batch_status"], "open")
            self.assertEqual(rows[0]["batch_completed_at"], "")
            self.assertEqual(rows[0]["evidence_sha256"], self.trial.raw_evidence_sha256)
            self.assertNotIn("SECRET-UID-1234", text)
            self.assertNotIn("SECRET RAW PROXMARK OUTPUT", text)
            self.assertEqual(
                artifact.sha256,
                hashlib.sha256(artifact.path.read_bytes()).hexdigest(),
            )

    def test_pdf_is_generated_with_a_valid_header_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = generate_measurement_pdf(
                self.db,
                self.session.id,
                output_dir=Path(directory),
            )
            content = artifact.path.read_bytes()

            self.assertTrue(content.startswith(b"%PDF-"))
            self.assertGreater(len(content), 3000)
            self.assertEqual(artifact.content_type, "application/pdf")
            self.assertEqual(artifact.sha256, hashlib.sha256(content).hexdigest())

    def test_analysis_csv_contains_condition_statistics_without_sensitive_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = generate_measurement_analysis_csv(
                self.db,
                self.session.id,
                output_dir=Path(directory),
            )
            text = artifact.path.read_text(encoding="utf-8-sig")
            rows = list(csv.DictReader(text.splitlines()))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["analysis_version"], "measurement-analysis-v1.0")
            self.assertEqual(rows[0]["credential_alias"], "CARD-HF-01")
            self.assertEqual(rows[0]["detection_events"], "1")
            self.assertEqual(rows[0]["correct_identification_events"], "1")
            self.assertEqual(rows[0]["correct_identification_rate_percent"], "100.0")
            self.assertEqual(rows[0]["meets_minimum_repetitions"], "false")
            self.assertNotIn("SECRET-UID-1234", text)
            self.assertNotIn("SECRET RAW PROXMARK OUTPUT", text)


if __name__ == "__main__":
    unittest.main()
