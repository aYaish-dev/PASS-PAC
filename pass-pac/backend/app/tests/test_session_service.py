import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.schemas.session import SessionCreate, SessionUpdate
from app.services.session_service import (
    create_session,
    delete_session,
    get_session_or_404,
    list_sessions,
    start_session,
    stop_session,
    update_session,
)


class SessionServiceTests(unittest.TestCase):
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

    def create_example(self):
        return create_session(
            self.db,
            SessionCreate(session_name="Authorized lab assessment"),
        )

    def test_session_lifecycle(self) -> None:
        session = self.create_example()
        self.assertEqual(session.status, "created")
        self.assertEqual(session.mode, "simulator")
        self.assertEqual(session.environment, "local")

        running = start_session(self.db, session.id)
        self.assertEqual(running.status, "running")
        self.assertIsNotNone(running.started_at)

        completed = stop_session(self.db, session.id)
        self.assertEqual(completed.status, "completed")
        self.assertIsNotNone(completed.ended_at)

    def test_invalid_status_transitions_return_clear_errors(self) -> None:
        session = self.create_example()

        with self.assertRaises(HTTPException) as stop_error:
            stop_session(self.db, session.id)
        self.assertEqual(stop_error.exception.status_code, 400)
        self.assertIn("Only sessions with status 'running'", stop_error.exception.detail)

        start_session(self.db, session.id)
        with self.assertRaises(HTTPException) as start_error:
            start_session(self.db, session.id)
        self.assertEqual(start_error.exception.status_code, 400)
        self.assertIn("Only sessions with status 'created'", start_error.exception.detail)

    def test_update_list_and_delete(self) -> None:
        session = self.create_example()
        updated = update_session(
            self.db,
            session.id,
            SessionUpdate(description="Front entrance reader", environment="lab"),
        )
        self.assertEqual(updated.description, "Front entrance reader")
        self.assertEqual(updated.environment, "lab")
        self.assertEqual(len(list_sessions(self.db)), 1)

        delete_session(self.db, session.id)
        with self.assertRaises(HTTPException) as missing_error:
            get_session_or_404(self.db, session.id)
        self.assertEqual(missing_error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
