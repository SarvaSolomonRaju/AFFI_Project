"""
database.py — SQLite Database Manager
=======================================
WHY A DATABASE?
    Your current code generates a JSON file and a PNG image.
    When you run it again tomorrow, yesterday's files are OVERWRITTEN.
    You lose all history.

    A database KEEPS EVERYTHING:
    - Every forecast run (with timestamp)
    - Every alert issued
    - Every API call (success/failure)

    This lets you:
    1. Track forecast accuracy over time
    2. Show "last 30 days of alerts" in a dashboard
    3. Prove to reviewers that your system ran reliably
    4. Debug issues ("what happened at 3am on July 15?")

WHY SQLITE?
    - No server needed (it's just a file: outputs/floodai.db)
    - Built into Python (no installation)
    - Handles millions of rows easily
    - Perfect for single-user research projects
    - You can open it with DB Browser for SQLite (free GUI)

WHAT IS A "TABLE"?
    Think of it as an Excel spreadsheet inside the database.
    Each table has columns (like Excel headers) and rows (data).

    forecast_runs table:
    | id | run_time            | watershed        | current_alert | json_data |
    |----|---------------------|------------------|---------------|-----------|
    | 1  | 2026-04-07 10:30:00 | Upper Sonoita Ck | GREEN         | {...}     |
    | 2  | 2026-04-08 10:30:00 | Upper Sonoita Ck | WATCH         | {...}     |

WHAT IS SQL?
    SQL = Structured Query Language. It's how you talk to databases.
    Examples:
        "Give me all forecasts"     → SELECT * FROM forecast_runs
        "Give me only warnings"     → SELECT * FROM forecast_runs WHERE current_alert = 'WARNING'
        "How many runs total?"      → SELECT COUNT(*) FROM forecast_runs

    You don't need to learn SQL right now — this file handles it for you.
"""

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from common.logging_setup import get_logger

logger = get_logger(__name__)


class FloodDatabase:
    """
    Manages all database operations for FloodAI.

    HOW TO USE:
        db = FloodDatabase()           # Creates/opens database
        db.save_forecast_run(data)      # Save a forecast
        runs = db.get_recent_runs(7)    # Get last 7 runs
        db.close()                      # Close connection

    Or use "with" statement (auto-closes):
        with FloodDatabase() as db:
            db.save_forecast_run(data)
    """

    def __init__(self, db_path: str = "outputs/floodai.db"):
        """
        Open (or create) the database.

        WHAT HAPPENS:
        1. Creates outputs/ folder if it doesn't exist
        2. Opens (or creates) the .db file
        3. Creates tables if they don't exist yet
        4. Enables WAL mode (faster concurrent reads)
        """
        Path(db_path).parent.mkdir(exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row  # Return dicts instead of tuples
        self.conn.execute("PRAGMA journal_mode=WAL")  # Faster writes
        self._create_tables()
        logger.info("Database opened: %s", db_path)

    def __enter__(self):
        """Support 'with FloodDatabase() as db:' syntax."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Auto-close when exiting 'with' block."""
        self.close()

    def _create_tables(self):
        """
        Create database tables if they don't exist.

        WHY "IF NOT EXISTS"?
            First time: creates the table.
            Every time after: does nothing (table already exists).
            This means you can run the code 1000 times safely.

        TABLE: forecast_runs
            Stores one row per forecast execution.
            - id: auto-incrementing unique number
            - run_time: when the forecast was generated
            - watershed_name: which watershed
            - watershed_huc: HUC code
            - current_alert: GREEN/ADVISORY/WATCH/WARNING
            - max_alert_7day: worst alert in the 7-day forecast
            - p50_max_24hr: median max 24-hr rainfall (inches)
            - p90_max_24hr: 90th percentile max 24-hr rainfall
            - storm_index_max: highest storm severity index
            - data_source: "api" or "synthetic"
            - json_data: full alert packet as JSON string

        TABLE: api_calls
            Tracks every API call for debugging.
            - success: did it work? (1=yes, 0=no)
            - response_time_ms: how fast was the API?
            - error_message: what went wrong (if failed)
        """
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS forecast_runs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                run_time        TEXT NOT NULL,
                watershed_name  TEXT NOT NULL,
                watershed_huc   TEXT NOT NULL,
                current_alert   TEXT NOT NULL,
                max_alert_7day  TEXT,
                p50_max_24hr    REAL,
                p90_max_24hr    REAL,
                storm_index_max REAL,
                data_source     TEXT DEFAULT 'api',
                json_data       TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS api_calls (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                call_time       TEXT NOT NULL,
                endpoint        TEXT NOT NULL,
                grid_point_id   TEXT,
                lat             REAL,
                lon             REAL,
                success         INTEGER NOT NULL,
                response_time_ms REAL,
                error_message   TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS alerts_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_time      TEXT NOT NULL,
                watershed_name  TEXT NOT NULL,
                alert_level     TEXT NOT NULL,
                forecast_day    INTEGER,
                p50_24hr        REAL,
                p90_24hr        REAL,
                storm_index     REAL,
                created_at      TEXT DEFAULT (datetime('now'))
            );
        """)
        self.conn.commit()

    def save_forecast_run(self, alert_packet: Dict[str, Any], 
                          data_source: str = "api") -> int:
        """
        Save a complete forecast run to the database.

        Parameters
        ----------
        alert_packet : dict
            The full alert packet (same as task1_alert_packet.json)
        data_source : str
            "api" if real data, "synthetic" if fallback data

        Returns
        -------
        int
            The ID of the saved row (for reference)
        """
        days = alert_packet.get("forecast_days", [])

        # Find the worst alert in the 7-day forecast
        alert_priority = {"GREEN": 0, "ADVISORY": 1, "WATCH": 2, "WARNING": 3}
        max_alert = "GREEN"
        max_si = 0.0
        max_p50 = 0.0
        max_p90 = 0.0

        for day in days:
            level = day.get("alert_level", "GREEN")
            if alert_priority.get(level, 0) > alert_priority.get(max_alert, 0):
                max_alert = level
            si = day.get("storm_index_24hr", 0)
            if si > max_si:
                max_si = si
            p50 = day.get("p50_24hr", 0)
            p90 = day.get("p90_24hr", 0)
            if p50 > max_p50:
                max_p50 = p50
            if p90 > max_p90:
                max_p90 = p90

        ws = alert_packet.get("watershed", {})

        cursor = self.conn.execute("""
            INSERT INTO forecast_runs 
            (run_time, watershed_name, watershed_huc, current_alert,
             max_alert_7day, p50_max_24hr, p90_max_24hr, storm_index_max,
             data_source, json_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            alert_packet.get("generated_utc", datetime.now(timezone.utc).isoformat()),
            ws.get("name", "Unknown"),
            ws.get("huc", "Unknown"),
            alert_packet.get("current_alert", "GREEN"),
            max_alert,
            round(max_p50, 3),
            round(max_p90, 3),
            round(max_si, 3),
            data_source,
            json.dumps(alert_packet)
        ))
        self.conn.commit()

        run_id = cursor.lastrowid
        logger.info("Saved forecast run #%d (alert: %s, source: %s)", 
                     run_id, max_alert, data_source)
        return run_id

    def save_api_call(self, endpoint: str, grid_point_id: str,
                      lat: float, lon: float, success: bool,
                      response_time_ms: float, 
                      error_message: Optional[str] = None):
        """Log an API call for debugging and reliability tracking."""
        self.conn.execute("""
            INSERT INTO api_calls 
            (call_time, endpoint, grid_point_id, lat, lon, 
             success, response_time_ms, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            endpoint, grid_point_id, lat, lon,
            1 if success else 0,
            response_time_ms,
            error_message
        ))
        self.conn.commit()

    def get_recent_runs(self, n: int = 10) -> List[Dict]:
        """Get the N most recent forecast runs."""
        cursor = self.conn.execute("""
            SELECT id, run_time, watershed_name, current_alert, 
                   max_alert_7day, p50_max_24hr, p90_max_24hr,
                   storm_index_max, data_source
            FROM forecast_runs 
            ORDER BY id DESC 
            LIMIT ?
        """, (n,))
        return [dict(row) for row in cursor.fetchall()]

    def get_alert_stats(self) -> Dict[str, int]:
        """Count how many times each alert level has been issued."""
        cursor = self.conn.execute("""
            SELECT max_alert_7day, COUNT(*) as count
            FROM forecast_runs
            GROUP BY max_alert_7day
        """)
        return {row["max_alert_7day"]: row["count"] for row in cursor.fetchall()}

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            logger.debug("Database connection closed")
