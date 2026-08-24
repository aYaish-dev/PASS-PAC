import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.adapters.proxmark_adapter import ProxmarkIdentifyResult, ProxmarkStatus
from app.core.database import Base
from app.models.detected_card import DetectedCard
from app.schemas.measurement import (
    ExperimentBatchCreate,
    ExperimentBatchUpdate,
    LiveMeasurementTrialCreate,
    MeasurementTrialCreate,
)
from app.schemas.session import SessionCreate
from app.services.measurement_service import (
    analyze_measurements,
    compare_measurement_batches,
    create_experiment_batch,
    create_measurement_trial,
    list_measurement_trials,
    run_live_measurement_trial,
    summarize_measurements,
    update_experiment_batch,
)
from app.services.session_service import create_session, start_session


class FakeLiveAdapter:
    def __init__(self, result: ProxmarkIdentifyResult) -> None:
        self.result = result
        self.identify_calls: list[str] = []

    def get_status(self) -> ProxmarkStatus:
        return ProxmarkStatus(
            enabled=True,
            configured=True,
            connection_mode="test",
            bridge_url="http://test",
            bridge_available=True,
            client_path="pm3",
            client_available=True,
            port="COM8",
            detected_ports=["COM8"],
            safe_commands=["hf search", "lf search"],
            integration_state="ready-to-probe",
            notes=[],
        )

    def identify_card(self, technology: str) -> ProxmarkIdentifyResult:
        self.identify_calls.append(technology)
        return self.result


class MeasurementServiceTests(unittest.TestCase):
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
            SessionCreate(session_name="Controlled RFID experiment", mode="proxmark"),
        )
        self.batch = self.create_batch()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def create_batch(self):
        return create_experiment_batch(
            self.db,
            self.session.id,
            ExperimentBatchCreate(
                name="Baseline lab batch",
                authorization_reference="LAB-AUTH-001",
                operator_label="operator-1",
                location_label="RFID laboratory",
                device_model="Proxmark3 Easy 512K",
                client_version="Iceman v4.21611",
                firmware_version="Iceman v4.21611",
                antenna_configuration="Stock LF/HF antennas",
                host_os="Windows 11",
            ),
        )

    def create_trial(self, **overrides):
        values = {
            "batch_id": self.batch.id,
            "credential_alias": "CARD-HF-01",
            "technology_family": "HF",
            "card_family": "MIFARE Classic 1K",
            "distance_cm": 4.0,
            "orientation": "parallel",
            "presented_face": "front",
            "success": True,
            "classification_result": "correct",
            "identification_duration_ms": 100,
            "metadata_fields_count": 5,
            "data_extracted_bytes": 16,
            "rf_interference": "none",
        }
        values.update(overrides)
        return create_measurement_trial(
            self.db,
            self.session.id,
            MeasurementTrialCreate(**values),
        )

    def create_source_card(
        self,
        *,
        technology: str = "HF/NFC",
        card_type: str = "MIFARE Classic 1K",
        uid: str = "04:AA:BB:CC",
    ) -> DetectedCard:
        card = DetectedCard(
            session_id=self.session.id,
            technology=technology,
            frequency="13.56 MHz" if technology.startswith("HF") else "125 kHz",
            card_type=card_type,
            protocol="ISO 14443-A" if technology.startswith("HF") else "125kHz LF",
            uid=uid,
            risk_level="informational",
            normalized_data_json={"uid": uid},
            raw_output_json={"output": "reference observation"},
        )
        self.db.add(card)
        self.db.commit()
        self.db.refresh(card)
        return card

    def test_live_runner_times_classifies_hashes_and_links_trial(self) -> None:
        start_session(self.db, self.session.id)
        source_card = self.create_source_card()
        result = ProxmarkIdentifyResult(
            technology="hf",
            command="hf search",
            success=True,
            exit_code=0,
            detected=True,
            card_type="MIFARE Classic 1K CL2",
            protocol="ISO 14443-A",
            uid="04 AA BB CC",
            atqa="00 04",
            sak="08",
            fields={"uid_length_bytes": "4"},
            output="authorized live fixture",
            error=None,
        )
        adapter = FakeLiveAdapter(result)
        ticks = iter([1_000_000_000, 1_123_000_000])

        with patch(
            "app.services.measurement_service.append_live_card_observation",
            return_value="/tmp/live-card-observations.jsonl",
        ) as observation_mock:
            response = run_live_measurement_trial(
                self.db,
                self.session.id,
                LiveMeasurementTrialCreate(
                    batch_id=self.batch.id,
                    source_card_id=source_card.id,
                    credential_alias="HF-MFC-01",
                    band="hf",
                    distance_cm=2,
                ),
                adapter_factory=lambda: adapter,
                clock=lambda: next(ticks),
            )

        trial = response["trial"]
        self.assertTrue(trial.success)
        self.assertEqual(trial.classification_result, "correct")
        self.assertEqual(trial.identification_duration_ms, 123)
        self.assertEqual(trial.source_card_id, source_card.id)
        self.assertEqual(len(trial.raw_evidence_sha256), 64)
        self.assertTrue(response["uid_match"])
        self.assertEqual(adapter.identify_calls, ["hf"])
        self.assertEqual(self.db.scalar(select(func.count(DetectedCard.id))), 1)
        observation_mock.assert_called_once()

    def test_live_runner_records_a_valid_no_detection_trial(self) -> None:
        start_session(self.db, self.session.id)
        source_card = self.create_source_card(
            technology="LF RFID",
            card_type="EM 410x",
            uid="01:02:03:04:05",
        )
        adapter = FakeLiveAdapter(
            ProxmarkIdentifyResult(
                technology="lf",
                command="lf search",
                success=False,
                exit_code=None,
                detected=False,
                card_type=None,
                protocol="125kHz LF",
                uid=None,
                atqa=None,
                sak=None,
                fields={},
                output="No data found",
                error="Command timed out after 20 seconds.",
            )
        )
        ticks = iter([2_000_000_000, 22_000_000_000])

        with patch(
            "app.services.measurement_service.append_live_card_observation",
            return_value="/tmp/live-card-observations.jsonl",
        ):
            response = run_live_measurement_trial(
                self.db,
                self.session.id,
                LiveMeasurementTrialCreate(
                    batch_id=self.batch.id,
                    source_card_id=source_card.id,
                    credential_alias="LF-EM-01",
                    band="lf",
                    distance_cm=20,
                ),
                adapter_factory=lambda: adapter,
                clock=lambda: next(ticks),
            )

        self.assertFalse(response["trial"].success)
        self.assertEqual(response["trial"].classification_result, "inconclusive")
        self.assertEqual(response["trial"].identification_duration_ms, 20_000)

    def test_live_runner_rejects_band_that_does_not_match_reference_card(self) -> None:
        start_session(self.db, self.session.id)
        source_card = self.create_source_card()

        with self.assertRaises(HTTPException) as error:
            run_live_measurement_trial(
                self.db,
                self.session.id,
                LiveMeasurementTrialCreate(
                    batch_id=self.batch.id,
                    source_card_id=source_card.id,
                    credential_alias="HF-MFC-01",
                    band="lf",
                    distance_cm=0,
                ),
            )

        self.assertEqual(error.exception.status_code, 400)
        self.assertIn("matching LF band", error.exception.detail)

    def test_source_observation_enriches_trial_and_hashes_evidence(self) -> None:
        card = DetectedCard(
            session_id=self.session.id,
            technology="HF",
            frequency="13.56 MHz",
            card_type="MIFARE Classic 1K",
            protocol="ISO 14443-A",
            uid="04AABBCC",
            risk_level="high",
            normalized_data_json={"uid": "04AABBCC", "sak": "08"},
            raw_output_json={"output": "authorized fixture"},
        )
        self.db.add(card)
        self.db.commit()

        first = self.create_trial(
            source_card_id=card.id,
            technology_family=None,
            card_family=None,
        )
        second = self.create_trial(source_card_id=card.id)

        self.assertEqual(first.technology_family, "HF")
        self.assertEqual(first.card_family, "MIFARE Classic 1K")
        self.assertEqual(len(first.raw_evidence_sha256), 64)
        self.assertEqual(first.raw_evidence_sha256, second.raw_evidence_sha256)
        self.assertEqual(first.trial_number, 1)
        self.assertEqual(second.trial_number, 2)

    def test_completed_batch_rejects_new_trials_until_reopened(self) -> None:
        completed = update_experiment_batch(
            self.db,
            self.session.id,
            self.batch.id,
            ExperimentBatchUpdate(status="completed"),
        )
        self.assertIsNotNone(completed.completed_at)

        with self.assertRaises(HTTPException) as error:
            self.create_trial()
        self.assertEqual(error.exception.status_code, 409)

        reopened = update_experiment_batch(
            self.db,
            self.session.id,
            self.batch.id,
            ExperimentBatchUpdate(status="open"),
        )
        self.assertIsNone(reopened.completed_at)
        self.assertEqual(self.create_trial().trial_number, 1)

    def test_summary_calculates_reliable_distance_and_timing(self) -> None:
        for duration in (100, 110, 120, 130):
            self.create_trial(identification_duration_ms=duration)
        self.create_trial(
            success=False,
            classification_result="incorrect",
            identification_duration_ms=1000,
        )

        summary = summarize_measurements(self.db, self.session.id)

        self.assertEqual(summary["methodology_version"], "controlled-measurement-v1.0")
        self.assertEqual(summary["trial_count"], 5)
        self.assertEqual(summary["unique_credentials"], 1)
        self.assertEqual(summary["detection_success_rate"], 80.0)
        self.assertEqual(summary["classification_accuracy"], 80.0)
        self.assertEqual(summary["timing"]["median_ms"], 115.0)
        self.assertEqual(summary["timing"]["q1_ms"], 107.5)
        self.assertEqual(summary["timing"]["q3_ms"], 122.5)
        self.assertEqual(len(summary["reliable_distances"]), 1)
        self.assertEqual(
            summary["reliable_distances"][0]["reliable_distance_cm"], 4.0
        )
        self.assertEqual(summary["reliable_distances"][0]["successes"], 4)

    def test_reliable_distance_requires_correct_identification(self) -> None:
        for _ in range(4):
            self.create_trial(
                distance_cm=8,
                success=True,
                classification_result="incorrect",
            )
        self.create_trial(
            distance_cm=8,
            success=False,
            classification_result="inconclusive",
        )

        summary = summarize_measurements(self.db, self.session.id)

        self.assertEqual(summary["detection_success_rate"], 80.0)
        self.assertEqual(summary["classification_accuracy"], 0.0)
        self.assertEqual(summary["reliable_distances"], [])

    def test_analysis_reports_wilson_intervals_and_partial_responses(self) -> None:
        for duration in (100, 110, 120, 130):
            self.create_trial(identification_duration_ms=duration)
        self.create_trial(
            success=True,
            classification_result="incorrect",
            identification_duration_ms=140,
        )

        analysis = analyze_measurements(self.db, self.session.id)

        self.assertEqual(analysis["analysis_version"], "measurement-analysis-v1.0")
        self.assertEqual(analysis["trial_count"], 5)
        self.assertEqual(analysis["credential_count"], 1)
        self.assertEqual(analysis["condition_count"], 1)
        condition = analysis["conditions"][0]
        self.assertEqual(condition["detection"]["rate_percent"], 100.0)
        self.assertEqual(condition["correct_identification"]["rate_percent"], 80.0)
        self.assertAlmostEqual(
            condition["correct_identification"]["ci_lower_percent"],
            37.55,
            places=2,
        )
        self.assertAlmostEqual(
            condition["correct_identification"]["ci_upper_percent"],
            96.38,
            places=2,
        )
        self.assertEqual(condition["partial_response_count"], 1)
        self.assertEqual(condition["correct_identification_timing"]["median_ms"], 115.0)
        self.assertTrue(condition["meets_minimum_repetitions"])
        self.assertTrue(
            any(
                item["id"] == "partial-response-CARD-HF-01"
                for item in analysis["quality_flags"]
            )
        )

    def test_session_filters_and_source_ownership_are_enforced(self) -> None:
        self.create_trial()
        self.create_trial(technology_family="LF", credential_alias="CARD-LF-01")
        filtered = list_measurement_trials(
            self.db,
            self.session.id,
            technology_family="LF",
        )
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].credential_alias, "CARD-LF-01")

        other = create_session(self.db, SessionCreate(session_name="Other session"))
        other_card = DetectedCard(
            session_id=other.id,
            technology="LF",
            frequency="125 kHz",
            card_type="EM410x",
            protocol="EM4100",
            uid="0011223344",
            risk_level="high",
            normalized_data_json={"uid": "0011223344"},
            raw_output_json={"output": "fixture"},
        )
        self.db.add(other_card)
        self.db.commit()

        with self.assertRaises(HTTPException) as error:
            self.create_trial(source_card_id=other_card.id)
        self.assertEqual(error.exception.status_code, 404)

    def test_baseline_and_remediation_comparison_reports_deltas(self) -> None:
        for duration in (100, 110, 120, 130):
            self.create_trial(identification_duration_ms=duration)
        self.create_trial(
            success=False,
            classification_result="incorrect",
            identification_duration_ms=1000,
        )
        post_batch = create_experiment_batch(
            self.db,
            self.session.id,
            ExperimentBatchCreate(
                name="Post-remediation batch",
                condition="post_remediation",
                authorization_reference="LAB-AUTH-001",
                operator_label="operator-1",
                location_label="RFID laboratory",
                device_model="Proxmark3 Easy 512K",
                client_version="Iceman v4.21611",
                firmware_version="Iceman v4.21611",
                antenna_configuration="Stock LF/HF antennas",
                host_os="Windows 11",
            ),
        )
        for duration in (80, 90, 100, 110, 120):
            self.create_trial(
                batch_id=post_batch.id,
                distance_cm=2,
                identification_duration_ms=duration,
            )

        comparison = compare_measurement_batches(
            self.db,
            self.session.id,
            self.batch.id,
            post_batch.id,
        )

        self.assertEqual(comparison["detection_rate_delta"], 20.0)
        self.assertEqual(comparison["classification_accuracy_delta"], 20.0)
        self.assertEqual(comparison["median_duration_delta_ms"], -15.0)
        self.assertEqual(
            comparison["reliable_distance_changes"][0]["delta_cm"], -2.0
        )
        self.assertIn("do not establish statistical significance", comparison["interpretation"][-1])


if __name__ == "__main__":
    unittest.main()
