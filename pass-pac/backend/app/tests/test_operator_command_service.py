import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.adapters.proxmark_adapter import (
    ProxmarkProbeResult,
    normalize_safe_command,
)
from app.core.database import Base
from app.schemas.operator_command import OperatorCommandCreate
from app.schemas.session import SessionCreate
from app.services.operator_command_service import (
    list_operator_commands,
    list_operator_recipes,
    run_operator_command,
    run_operator_recipe,
)
from app.services.session_service import create_session, start_session


class FakeCommandAdapter:
    def run_safe_command(self, command: str) -> ProxmarkProbeResult:
        return ProxmarkProbeResult(command, True, 0, "firmware ok", None)


class OperatorCommandServiceTests(unittest.TestCase):
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

    def create_running_proxmark_session(self):
        session = create_session(
            self.db,
            SessionCreate(session_name="Console test", mode="proxmark"),
        )
        return start_session(self.db, session.id)

    def test_safe_command_is_executed_and_audited(self) -> None:
        session = self.create_running_proxmark_session()
        result = run_operator_command(
            self.db,
            session.id,
            OperatorCommandCreate(command="  HW   VERSION  "),
            adapter_factory=FakeCommandAdapter,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.command, "hw version")
        self.assertEqual(result.output, "firmware ok")
        self.assertEqual(len(list_operator_commands(self.db, session.id)), 1)

    def test_unsafe_command_is_rejected_before_execution(self) -> None:
        session = self.create_running_proxmark_session()
        with self.assertRaises(HTTPException) as error:
            run_operator_command(
                self.db,
                session.id,
                OperatorCommandCreate(command="hf mf autopwn"),
                adapter_factory=FakeCommandAdapter,
            )

        self.assertEqual(error.exception.status_code, 400)
        self.assertIn("read-only allowlist", error.exception.detail)
        self.assertEqual(list_operator_commands(self.db, session.id), [])

    def test_passive_trace_list_is_allowed_but_active_sniff_is_rejected(self) -> None:
        self.assertEqual(
            normalize_safe_command(" TRACE   LIST -T 14A "),
            "trace list -t 14a",
        )
        self.assertIsNone(normalize_safe_command("hf 14a sniff"))

    def test_recipe_executes_and_audits_each_command(self) -> None:
        session = self.create_running_proxmark_session()
        recipes = list_operator_recipes(self.db, session.id)
        self.assertIn("device-baseline", {recipe["key"] for recipe in recipes})

        result = run_operator_recipe(
            self.db,
            session.id,
            "device-baseline",
            adapter_factory=FakeCommandAdapter,
        )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["command_count"], 3)
        history = list_operator_commands(self.db, session.id)
        self.assertEqual(len(history), 3)
        self.assertEqual(
            {record.command for record in history},
            {"hw version", "hw status", "hw tune"},
        )

    def test_unknown_recipe_returns_404(self) -> None:
        session = self.create_running_proxmark_session()
        with self.assertRaises(HTTPException) as error:
            run_operator_recipe(
                self.db,
                session.id,
                "not-a-recipe",
                adapter_factory=FakeCommandAdapter,
            )
        self.assertEqual(error.exception.status_code, 404)

    def test_session_must_be_running_and_use_proxmark_mode(self) -> None:
        created = create_session(
            self.db,
            SessionCreate(session_name="Not started", mode="proxmark"),
        )
        with self.assertRaises(HTTPException) as state_error:
            run_operator_command(
                self.db,
                created.id,
                OperatorCommandCreate(command="hw version"),
                adapter_factory=FakeCommandAdapter,
            )
        self.assertIn("Start the session", state_error.exception.detail)

        simulator = create_session(
            self.db,
            SessionCreate(session_name="Simulator", mode="simulator"),
        )
        start_session(self.db, simulator.id)
        with self.assertRaises(HTTPException) as mode_error:
            run_operator_command(
                self.db,
                simulator.id,
                OperatorCommandCreate(command="hw version"),
                adapter_factory=FakeCommandAdapter,
            )
        self.assertIn("mode 'proxmark'", mode_error.exception.detail)


if __name__ == "__main__":
    unittest.main()
