from __future__ import annotations

import sqlite3

DEFAULT_WEEKLY_DISTANCE_KM = 20.0


def get_setting(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if row is None:
        return default
    return row["value"]


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO settings(key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (key, value),
    )


def get_weekly_distance_goal_km(conn: sqlite3.Connection) -> float:
    raw = get_setting(conn, "weekly_distance_km")
    if raw is None:
        return DEFAULT_WEEKLY_DISTANCE_KM
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_WEEKLY_DISTANCE_KM


def get_target_5k_time_s(conn: sqlite3.Connection) -> int | None:
    raw = get_setting(conn, "target_5k_time_s")
    if raw is None or raw == "":
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None
