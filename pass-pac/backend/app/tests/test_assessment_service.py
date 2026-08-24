import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.adapters.proxmark_adapter import (
    ProxmarkIdentifyResult,
    ProxmarkMetadataResult,
    ProxmarkProbeResult,
    ProxmarkStatus,
)
from app.core.database import Base
from app.models.detected_card import DetectedCard
from app.models.finding import Finding
from app.schemas.session import SessionCreate
from app.services.assessment_service import (
    _execute_assessment,
    _identity_metadata_fields,
    _inspection_commands_for_profile,
    _select_scan_profile,
    queue_assessment,
)
from app.services.session_service import create_session, start_session


class FakeAdapter:
    def __init__(self, configured: bool = True) -> None:
        self.configured = configured
        self.identify_calls: list[str] = []
        self.inspect_calls: list[str] = []

    def get_status(self) -> ProxmarkStatus:
        return ProxmarkStatus(
            enabled=self.configured,
            configured=self.configured,
            connection_mode="test",
            bridge_url="http://test",
            bridge_available=self.configured,
            client_path="pm3",
            client_available=self.configured,
            port="COM8",
            detected_ports=["COM8"],
            safe_commands=["hw version", "hw status", "hw tune", "hf search", "lf search"],
            integration_state="ready-to-probe" if self.configured else "configuration-required",
            notes=[],
        )

    def probe_hw_version(self) -> ProxmarkProbeResult:
        return ProxmarkProbeResult("hw version", True, 0, "firmware ok", None)

    def run_diagnostic(self, diagnostic: str) -> ProxmarkProbeResult:
        command = "hw status" if diagnostic == "hardware_status" else "hw tune"
        return ProxmarkProbeResult(command, True, 0, f"{diagnostic} ok", None)

    def identify_card(self, technology: str) -> ProxmarkIdentifyResult:
        self.identify_calls.append(technology)
        if technology == "hf":
            return ProxmarkIdentifyResult(
                technology="hf",
                command="hf search",
                success=True,
                exit_code=0,
                detected=True,
                card_type="MIFARE Classic 1K",
                protocol="ISO 14443-A",
                uid="04 11 22 33",
                atqa="00 04",
                sak="08",
                fields={"uid_length_bytes": "4"},
                output="MIFARE Classic test output",
                error=None,
            )
        return ProxmarkIdentifyResult(
            technology="lf",
            command="lf search",
            success=True,
            exit_code=0,
            detected=False,
            card_type=None,
            protocol="125kHz LF",
            uid=None,
            atqa=None,
            sak=None,
            fields={},
            output="No data found",
            error=None,
        )

    def inspect_card(self, command_key: str) -> ProxmarkMetadataResult:
        self.inspect_calls.append(command_key)
        commands = {
            "hf_iso14443a": "hf 14a info",
            "hf_mifare_classic": "hf mf info",
            "hf_emv_pse": "emv pse -s2",
            "hf_emv_search": "emv search -s",
            "hf_emv_reader": "emv reader",
            "hf_emv_history": "emv list",
        }
        fields = {
            "uid": "04:11:22:33",
            "manufacturer": "NXP",
        }
        if command_key.startswith("hf_emv"):
            fields = {
                "emv_application_detected": True,
                "application_identifiers": ["A0000000031010"],
                "payment_systems": ["Visa"],
                "sensitive_fields_redacted": ["PAN", "TRACK_DATA"],
            }
        return ProxmarkMetadataResult(
            command_key=command_key,
            command=commands[command_key],
            success=True,
            exit_code=0,
            fields=fields,
            output=f"{command_key} metadata",
            error=None,
        )


class AssessmentServiceTests(unittest.TestCase):
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

    def create_running_session(self, mode: str = "proxmark"):
        session = create_session(
            self.db,
            SessionCreate(session_name="Automated lab assessment", mode=mode),
        )
        return start_session(self.db, session.id)

    def test_card_families_select_expected_read_only_recipes(self) -> None:
        cases = [
            ("MIFARE Classic 1K", "ISO 14443-A", "hf", "hf-mifare-classic-metadata-v1", ["hf_iso14443a", "hf_mifare_classic"]),
            ("NTAG213", "ISO 14443-A", "hf", "hf-type2-tag-metadata-v1", ["hf_iso14443a", "hf_type2"]),
            ("MIFARE DESFire EV2", "ISO 14443-A", "hf", "hf-desfire-metadata-v1", ["hf_iso14443a", "hf_desfire"]),
            ("ISO 15693 tag", "ISO 15693", "hf", "hf-iso15693-metadata-v1", ["hf_iso15693"]),
            ("HID Prox", "125kHz LF", "lf", "lf-hid-metadata-v1", ["lf_hid"]),
            ("EM 410x", "125kHz LF", "lf", "lf-em410x-metadata-v1", ["lf_em410x"]),
            ("T55xx", "125kHz LF", "lf", "lf-t55xx-metadata-v1", ["lf_t55xx"]),
        ]

        for card_type, protocol, technology, expected_profile, expected_commands in cases:
            with self.subTest(card_type=card_type):
                identity = ProxmarkIdentifyResult(
                    technology=technology,
                    command=f"{technology} search",
                    success=True,
                    exit_code=0,
                    detected=True,
                    card_type=card_type,
                    protocol=protocol,
                    uid="01 02 03 04",
                    atqa=None,
                    sak=None,
                    fields={},
                    output="test",
                    error=None,
                )
                profile = _select_scan_profile(identity)
                self.assertEqual(profile, expected_profile)
                self.assertEqual(_inspection_commands_for_profile(profile), expected_commands)

        self.assertEqual(
            _inspection_commands_for_profile("hf-emv-metadata-v1"),
            [
                "hf_iso14443a",
                "hf_emv_pse",
                "hf_emv_search",
                "hf_emv_reader",
                "hf_emv_history",
            ],
        )

    def test_identity_search_output_is_reused_as_metadata_evidence(self) -> None:
        fields = _identity_metadata_fields(
            "hf-generic-metadata-v1",
            """
            [+] UID: CF 74 D0 B4 ( FNUID, fixed, non-unique ID )
            [+] ATQA: 00 08
            [+] SAK: 20
            [+] ATS: 14 78 80 75 02
            """,
        )

        self.assertTrue(fields["non_unique_uid"])
        self.assertTrue(fields["fixed_uid"])
        self.assertEqual(fields["ats"], "14:78:80:75:02")

    @patch("app.services.assessment_service.append_live_card_observation")
    def test_read_only_assessment_persists_timeline_card_and_finding(self, observation_mock) -> None:
        session = self.create_running_session()
        assessment = queue_assessment(self.db, session.id)
        adapter = FakeAdapter()

        _execute_assessment(self.db, assessment, adapter)
        self.db.refresh(assessment)

        card = self.db.scalar(select(DetectedCard))
        finding = self.db.scalar(select(Finding))
        self.assertEqual(assessment.status, "completed")
        self.assertEqual(assessment.detected_card_count, 1)
        self.assertEqual(card.uid, "04:11:22:33")
        self.assertEqual(card.normalized_data_json["source"], "live-proxmark")
        self.assertEqual(card.normalized_data_json["assessment_run_id"], assessment.id)
        self.assertEqual(finding.evidence_json["rule_id"], "hf_mifare_classic")
        self.assertIn("hf-mifare-classic-metadata-v1", assessment.summary_json["selected_profiles"])
        self.assertEqual(assessment.summary_json["bands_scanned"], ["hf"])
        self.assertEqual(adapter.identify_calls, ["hf"])
        self.assertEqual(card.normalized_data_json["inspection"]["profile"], "hf-mifare-classic-metadata-v1")
        self.assertEqual(len(card.normalized_data_json["inspection"]["commands"]), 2)
        self.assertEqual([event.sequence for event in assessment.events], list(range(1, 11)))
        self.assertEqual(assessment.events[-1].title, "Assessment completed")
        observation_mock.assert_called_once()

    def test_lf_assessment_does_not_start_an_hf_search(self) -> None:
        session = self.create_running_session()
        assessment = queue_assessment(self.db, session.id, band="lf")
        adapter = FakeAdapter()

        _execute_assessment(self.db, assessment, adapter)
        self.db.refresh(assessment)

        self.assertEqual(assessment.status, "completed")
        self.assertEqual(assessment.summary_json["bands_scanned"], ["lf"])
        self.assertEqual(adapter.identify_calls, ["lf"])

    @patch("app.services.assessment_service.append_live_card_observation")
    def test_advanced_emv_assessment_stores_redacted_structured_profile(
        self,
        observation_mock,
    ) -> None:
        session = self.create_running_session()
        assessment = queue_assessment(self.db, session.id, band="emv")
        adapter = FakeAdapter()

        _execute_assessment(self.db, assessment, adapter)
        self.db.refresh(assessment)

        card = self.db.scalar(select(DetectedCard))
        self.assertEqual(assessment.profile, "automated-advanced-emv-read-only-v1")
        self.assertEqual(assessment.summary_json["bands_scanned"], ["emv"])
        self.assertEqual(adapter.identify_calls, ["hf"])
        self.assertEqual(
            adapter.inspect_calls,
            [
                "hf_iso14443a",
                "hf_emv_pse",
                "hf_emv_search",
                "hf_emv_reader",
                "hf_emv_history",
            ],
        )
        self.assertEqual(card.card_type, "EMV payment credential")
        self.assertEqual(card.protocol, "EMV / ISO 14443-4")
        self.assertEqual(
            card.normalized_data_json["analysis_fields"]["payment_systems"],
            ["Visa"],
        )
        self.assertNotIn("PAN", str(card.raw_output_json))
        observation_mock.assert_called_once()

    def test_invalid_assessment_band_is_rejected(self) -> None:
        session = self.create_running_session()

        with self.assertRaises(HTTPException) as error:
            queue_assessment(self.db, session.id, band="both")

        self.assertEqual(error.exception.status_code, 422)
        self.assertIn("'hf', 'lf', or 'emv'", error.exception.detail)

    def test_unavailable_device_fails_during_preflight(self) -> None:
        session = self.create_running_session()
        assessment = queue_assessment(self.db, session.id)

        _execute_assessment(self.db, assessment, FakeAdapter(configured=False))
        self.db.refresh(assessment)

        self.assertEqual(assessment.status, "failed")
        self.assertEqual(assessment.events[-1].title, "Assessment stopped")
        self.assertIn("preflight", assessment.summary_json["error"].lower())

    def test_simulator_session_cannot_queue_device_assessment(self) -> None:
        session = self.create_running_session(mode="simulator")

        with self.assertRaises(HTTPException) as error:
            queue_assessment(self.db, session.id)

        self.assertEqual(error.exception.status_code, 400)
        self.assertIn("mode 'proxmark'", error.exception.detail)


if __name__ == "__main__":
    unittest.main()
