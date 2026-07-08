from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def _default_db_path() -> str:
    return os.environ.get("RUNMGR_DB_PATH", str(Path("data") / "runmgr.sqlite3"))


def ensure_dirs(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def connect(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or _default_db_path()
    ensure_dirs(path)
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS activities (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              strava_activity_id TEXT UNIQUE,
              name TEXT,
              activity_type TEXT,
              sport_type TEXT,
              start_date_local TEXT,
              distance_m REAL,
              moving_time_s INTEGER,
              elapsed_time_s INTEGER,
              total_elevation_gain_m REAL,
              average_speed_mps REAL,
              max_speed_mps REAL,
              average_heartrate REAL,
              max_heartrate REAL,
              calories REAL,
              kudos_count INTEGER,
              created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_activities_start_date_local
              ON activities(start_date_local);

            CREATE TABLE IF NOT EXISTS weight_logs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              date TEXT UNIQUE,
              weight_kg REAL NOT NULL,
              note TEXT,
              created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS settings (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            """
        )
