from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.api.audit import AuditLogger


@pytest.fixture
def audit_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    logger = AuditLogger(db_path)
    yield logger
    logger.close()
    Path(db_path).unlink(missing_ok=True)


class TestAuditLogger:
    def test_log_event_returns_id(self, audit_db):
        eid = audit_db.log_event("TEST_EVENT", actor="pytest")
        assert isinstance(eid, int)
        assert eid > 0

    def test_log_pipeline_start(self, audit_db):
        eid = audit_db.log_pipeline_start("pytest", "test_watershed")
        assert eid > 0

    def test_log_pipeline_complete(self, audit_db):
        eid = audit_db.log_pipeline_complete("GREEN", details={"nse": 0.85})
        assert eid > 0

    def test_log_alert_issued(self, audit_db):
        eid = audit_db.log_alert_issued("WARNING", "upper_sonoita_creek", {"p90": 4.5})
        assert eid > 0

    def test_get_recent_events(self, audit_db):
        audit_db.log_event("E1")
        audit_db.log_event("E2")
        audit_db.log_event("E3")
        events = audit_db.get_recent_events(limit=2)
        assert len(events) == 2
        assert events[0]["event_type"] == "E3"

    def test_context_manager(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        with AuditLogger(db_path) as logger:
            logger.log_event("CONTEXT_TEST")
        Path(db_path).unlink(missing_ok=True)
