import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.adapters.proxmark_adapter import ProxmarkProbeResult
from app.schemas.session import SessionCreate
from app.schemas.transaction_trace import TraceAnalyzeRequest, TraceBufferRequest
from app.services.session_service import create_session
from app.services.operator_command_service import list_operator_commands
from app.services.session_service import start_session
from app.services.transaction_trace_service import (
    analyze_imported_trace,
    analyze_device_trace_buffer,
    analyze_trace_text,
    delete_transaction_trace,
    get_transaction_trace_or_404,
    list_transaction_traces,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if not (PROJECT_ROOT / "mock-data").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
FIXTURES = PROJECT_ROOT / "mock-data" / "fixtures"


class FakeTraceAdapter:
    def __init__(self, output: str) -> None:
        self.output = output

    def run_safe_command(self, command: str) -> ProxmarkProbeResult:
        return ProxmarkProbeResult(command, True, 0, self.output, None)


class TransactionTraceParserTests(unittest.TestCase):
    def read_fixture(self, name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")

    def test_uid_only_trace_is_explainable_candidate_not_proof(self) -> None:
        result = analyze_trace_text(self.read_fixture("trace-uid-only.txt"), "14a")

        self.assertEqual(result["frame_count"], 6)
        self.assertEqual(result["reader_frame_count"], 3)
        self.assertEqual(result["card_frame_count"], 3)
        self.assertEqual(result["risk_level"], "medium")
        self.assertEqual(result["summary"]["trust_hypothesis"], "uid_only_candidate")
        finding = result["findings"][0]
        self.assertEqual(finding["rule_id"], "trace_no_authentication_observed")
        self.assertIn("not proof", finding["description"])

    def test_apdu_trace_reconstructs_authentication_sequence(self) -> None:
        result = analyze_trace_text(
            self.read_fixture("trace-authenticated-apdu.txt"), "7816"
        )

        commands = [frame["command"] for frame in result["frames"] if frame["command"]]
        self.assertIn("SELECT", commands)
        self.assertIn("GET CHALLENGE", commands)
        self.assertIn("EXTERNAL AUTHENTICATE", commands)
        self.assertEqual(result["apdu_count"], 5)
        self.assertEqual(result["summary"]["authentication_state"], "observed")
        rule_ids = {finding["rule_id"] for finding in result["findings"]}
        self.assertIn("trace_authentication_observed", rule_ids)
        self.assertNotIn("trace_no_authentication_observed", rule_ids)

    def test_write_command_is_reported_from_passive_trace(self) -> None:
        raw = """
          0 | 100 | Rdr |A0  04  CA  FE | ok | MIFARE WRITE
        200 | 300 | Tag |0A              |     |
        """
        result = analyze_trace_text(raw, "mf")

        finding = next(
            finding
            for finding in result["findings"]
            if finding["rule_id"] == "trace_modification_command_observed"
        )
        self.assertEqual(finding["risk_level"], "medium")
        self.assertEqual(finding["frame_sequences"], [1])

    def test_empty_output_is_preserved_as_inconclusive(self) -> None:
        result = analyze_trace_text("trace buffer is empty", "14a")

        self.assertEqual(result["status"], "no_frames")
        self.assertEqual(result["confidence"], "low")
        self.assertEqual(result["findings"][0]["rule_id"], "trace_no_frames")


class TransactionTraceStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.session = create_session(
            self.db, SessionCreate(session_name="Trace analysis")
        )

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_imported_trace_is_hashed_stored_listed_and_deleted(self) -> None:
        raw = (FIXTURES / "trace-uid-only.txt").read_text(encoding="utf-8")
        trace = analyze_imported_trace(
            self.db,
            self.session.id,
            TraceAnalyzeRequest(name="Lobby reader", protocol="14a", raw_output=raw),
        )

        self.assertEqual(trace.source, "manual_import")
        self.assertEqual(trace.frame_count, 6)
        self.assertEqual(len(trace.raw_sha256), 64)
        self.assertEqual(list_transaction_traces(self.db, self.session.id)[0].id, trace.id)
        self.assertEqual(
            get_transaction_trace_or_404(self.db, self.session.id, trace.id).id,
            trace.id,
        )

        delete_transaction_trace(self.db, self.session.id, trace.id)
        self.assertEqual(list_transaction_traces(self.db, self.session.id), [])

    def test_device_buffer_trace_is_audited_and_analyzed(self) -> None:
        session = create_session(
            self.db,
            SessionCreate(session_name="Live trace", mode="proxmark"),
        )
        start_session(self.db, session.id)
        raw = (FIXTURES / "trace-authenticated-apdu.txt").read_text(encoding="utf-8")

        trace = analyze_device_trace_buffer(
            self.db,
            session.id,
            TraceBufferRequest(name="Door reader", protocol="7816"),
            adapter_factory=lambda: FakeTraceAdapter(raw),
        )

        self.assertEqual(trace.source, "proxmark_buffer")
        self.assertEqual(trace.summary_json["authentication_state"], "observed")
        history = list_operator_commands(self.db, session.id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].command, "trace list -t 7816")


if __name__ == "__main__":
    unittest.main()
