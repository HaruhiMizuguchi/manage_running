import csv
import io
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.analytics import build_dashboard
from app.db import connect, init_db
from app.formatting import fmt_duration, fmt_km, fmt_pace, pace_sec_per_km
from app.main import app
from app.settings_store import get_weekly_distance_goal_km
from app.strava_import import parse_strava_export


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "test.sqlite3")
    init_db(path)
    return path


def _insert_run(conn, *, activity_id: str, start: str, distance_m: float, moving_time_s: int, calories: float = 300):
    conn.execute(
        """
        INSERT INTO activities (
          strava_activity_id, name, activity_type, sport_type, start_date_local,
          distance_m, moving_time_s, calories
        ) VALUES (?, 'Morning Run', 'Run', 'Run', ?, ?, ?, ?)
        """,
        (activity_id, start, distance_m, moving_time_s, calories),
    )


def test_formatting_helpers():
    assert fmt_km(5000) == "5.00 km"
    assert fmt_duration(125) == "2:05"
    assert fmt_pace(5000, 1500) == "5:00 /km"
    assert pace_sec_per_km(5000, 1500) == 300.0


def test_weekly_stats_and_best_5k(db_path):
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    with connect(db_path) as conn:
        _insert_run(conn, activity_id="1", start=f"{monday.isoformat()} 07:00:00", distance_m=10000, moving_time_s=3000)
        _insert_run(conn, activity_id="2", start=f"{(monday + timedelta(days=1)).isoformat()} 07:00:00", distance_m=5000, moving_time_s=1500)

    with connect(db_path) as conn:
        dashboard = build_dashboard(conn)

    assert dashboard["this_week"]["runs"] == 2
    assert len(dashboard["weekly"]) >= 1
    assert dashboard["best_5k"]["projected_5k_s"] == pytest.approx(1500.0)


def test_strava_zip_import(db_path, monkeypatch):
    csv_buf = io.StringIO()
    writer = csv.DictWriter(
        csv_buf,
        fieldnames=["Activity ID", "Activity Name", "Activity Type", "Activity Date", "Distance", "Moving Time"],
    )
    writer.writeheader()
    writer.writerow(
        {
            "Activity ID": "99",
            "Activity Name": "Test Run",
            "Activity Type": "Run",
            "Activity Date": "2024-01-01 08:00:00",
            "Distance": "8000",
            "Moving Time": "2400",
        }
    )
    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w") as zf:
        zf.writestr("activities.csv", csv_buf.getvalue())
    activities = list(parse_strava_export(zip_bytes.getvalue(), "export.zip"))
    assert len(activities) == 1
    assert activities[0].distance_m == 8000.0


def test_home_and_goals_routes(db_path, monkeypatch):
    monkeypatch.setenv("RUNMGR_DB_PATH", db_path)
    init_db(db_path)
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "ダッシュボード" in response.text

    response = client.post(
        "/goals",
        data={"weekly_distance_km": 25, "target_5k_min": 28, "target_5k_sec": 30},
        follow_redirects=False,
    )
    assert response.status_code == 303

    with connect(db_path) as conn:
        assert get_weekly_distance_goal_km(conn) == 25.0
