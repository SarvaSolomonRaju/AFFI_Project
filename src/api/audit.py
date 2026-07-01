from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class AuditLogger:
    def __init__(self, db_path: str = "outputs/floodai.db"):
        Path(db_path).parent.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                event_type  TEXT NOT NULL,
                actor       TEXT,
                watershed   TEXT,
                alert_level TEXT,
                details     TEXT,
                input_hash  TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
            CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log(event_type);
        """)
        self.conn.commit()

    def log_event(
        self,
        event_type: str,
        actor: Optional[str] = None,
        watershed: Optional[str] = None,
        alert_level: Optional[str] = None,
        details: Optional[dict] = None,
        input_hash: Optional[str] = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            "INSERT INTO audit_log (timestamp, event_type, actor, watershed, alert_level, details, input_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                now,
                event_type,
                actor,
                watershed,
                alert_level,
                json.dumps(details) if details else None,
                input_hash,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def log_pipeline_start(self, actor: str = "scheduler", watershed: str = "upper_sonoita_creek") -> int:
        return self.log_event("PIPELINE_START", actor=actor, watershed=watershed)

    def log_pipeline_complete(
        self, alert_level: str, actor: str = "scheduler",
        watershed: str = "upper_sonoita_creek", details: Optional[dict] = None,
    ) -> int:
        return self.log_event(
            "PIPELINE_COMPLETE", actor=actor, watershed=watershed,
            alert_level=alert_level, details=details,
        )

    def log_alert_issued(
        self, alert_level: str, watershed: str, details: Optional[dict] = None,
    ) -> int:
        return self.log_event(
            "ALERT_ISSUED", watershed=watershed,
            alert_level=alert_level, details=details,
        )

    def log_api_access(self, actor: str, endpoint: str, details: Optional[dict] = None) -> int:
        return self.log_event("API_ACCESS", actor=actor, details={"endpoint": endpoint, **(details or {})})

    def get_recent_events(self, limit: int = 100) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        cols = [d[0] for d in self.conn.execute("SELECT * FROM audit_log LIMIT 0").description]
        return [dict(zip(cols, row)) for row in rows]

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
