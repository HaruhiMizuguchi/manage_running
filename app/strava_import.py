from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Iterator


@dataclass(frozen=True)
class StravaActivity:
    strava_activity_id: str | None
    name: str | None
    activity_type: str | None
    sport_type: str | None
    start_date_local: str | None
    distance_m: float | None
    moving_time_s: int | None
    elapsed_time_s: int | None
    total_elevation_gain_m: float | None
    average_speed_mps: float | None
    max_speed_mps: float | None
    average_heartrate: float | None
    max_heartrate: float | None
    calories: float | None
    kudos_count: int | None


def _to_float(v: str | None) -> float | None:
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _to_int(v: str | None) -> int | None:
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def _get(row: dict[str, str], *keys: str) -> str | None:
    for k in keys:
        if k in row:
            return row.get(k)
    return None


def _normalize_datetime(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    # Strava export typically uses ISO-ish strings. Store as text.
    try:
        # Handle "2020-01-01 07:00:00" and "2020-01-01T07:00:00Z"
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.isoformat()
    except Exception:
        return s


def parse_activities_csv(fileobj: io.TextIOBase) -> Iterator[StravaActivity]:
    reader = csv.DictReader(fileobj)
    for row in reader:
        activity_type = _get(row, "Activity Type", "Type")
        sport_type = _get(row, "Sport Type", "Sport")
        yield StravaActivity(
            strava_activity_id=_get(row, "Activity ID", "Activity Id", "Id", "id"),
            name=_get(row, "Activity Name", "Name"),
            activity_type=activity_type,
            sport_type=sport_type,
            start_date_local=_normalize_datetime(
                _get(row, "Activity Date", "Start Date Local", "Start Date", "Date")
            ),
            distance_m=_to_float(_get(row, "Distance", "Distance (m)")),
            moving_time_s=_to_int(_get(row, "Moving Time", "Moving Time (s)", "Moving Time (sec)")),
            elapsed_time_s=_to_int(_get(row, "Elapsed Time", "Elapsed Time (s)", "Elapsed Time (sec)")),
            total_elevation_gain_m=_to_float(
                _get(row, "Elevation Gain", "Total Elevation Gain", "Total Elev Gain")
            ),
            average_speed_mps=_to_float(_get(row, "Average Speed", "Avg Speed")),
            max_speed_mps=_to_float(_get(row, "Max Speed", "Maximum Speed")),
            average_heartrate=_to_float(_get(row, "Average Heart Rate", "Avg HR")),
            max_heartrate=_to_float(_get(row, "Max Heart Rate", "Max HR")),
            calories=_to_float(_get(row, "Calories")),
            kudos_count=_to_int(_get(row, "Kudos")),
        )


def find_activities_csv_in_zip(zf: zipfile.ZipFile) -> str | None:
    candidates = []
    for name in zf.namelist():
        lower = name.lower()
        if lower.endswith("activities.csv"):
            candidates.append(name)
    if not candidates:
        for name in zf.namelist():
            lower = name.lower()
            if "activities" in lower and lower.endswith(".csv"):
                candidates.append(name)
    candidates.sort(key=len)
    return candidates[0] if candidates else None


def parse_strava_export(data: bytes, filename: str) -> Iterable[StravaActivity]:
    lower = filename.lower()
    if lower.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            target = find_activities_csv_in_zip(zf)
            if not target:
                raise ValueError("ZIP内に activities.csv が見つかりませんでした。")
            with zf.open(target, "r") as f:
                text = io.TextIOWrapper(f, encoding="utf-8-sig", newline="")
                yield from parse_activities_csv(text)
        return
    if lower.endswith(".csv"):
        text = io.TextIOWrapper(io.BytesIO(data), encoding="utf-8-sig", newline="")
        yield from parse_activities_csv(text)
        return
    raise ValueError("対応していない形式です（ZIPまたはCSVのみ対応）。")


def is_run(a: StravaActivity) -> bool:
    t = (a.activity_type or "").strip().lower()
    s = (a.sport_type or "").strip().lower()
    return t in {"run", "running"} or s in {"run", "running"}
