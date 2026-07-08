from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from .formatting import pace_sec_per_km

RUN_FILTER = """
(LOWER(COALESCE(activity_type,'')) IN ('run','running')
 OR LOWER(COALESCE(sport_type,'')) IN ('run','running'))
"""


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[: len(fmt)], fmt).date()
        except ValueError:
            continue
    return None


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _fetch_runs(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
        SELECT id, name, start_date_local, distance_m, moving_time_s, calories,
               average_speed_mps, average_heartrate
        FROM activities
        WHERE {RUN_FILTER}
          AND start_date_local IS NOT NULL
        ORDER BY start_date_local ASC
        """
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["run_date"] = _parse_date(item.get("start_date_local"))
        item["pace_sec_per_km"] = pace_sec_per_km(item.get("distance_m"), item.get("moving_time_s"))
        result.append(item)
    return result


def weekly_stats(runs: list[dict[str, Any]], weeks: int = 12) -> list[dict[str, Any]]:
    buckets: dict[date, dict[str, Any]] = {}
    for run in runs:
        run_date = run.get("run_date")
        if not run_date:
            continue
        week = _week_start(run_date)
        bucket = buckets.setdefault(
            week,
            {
                "week_start": week.isoformat(),
                "distance_m": 0.0,
                "moving_time_s": 0,
                "calories": 0.0,
                "runs": 0,
            },
        )
        bucket["distance_m"] += float(run.get("distance_m") or 0)
        bucket["moving_time_s"] += int(run.get("moving_time_s") or 0)
        bucket["calories"] += float(run.get("calories") or 0)
        bucket["runs"] += 1

    ordered = sorted(buckets.values(), key=lambda x: x["week_start"])
    return ordered[-weeks:]


def this_week_summary(runs: list[dict[str, Any]], today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    start = _week_start(today)
    end = start + timedelta(days=7)
    distance_m = 0.0
    moving_time_s = 0
    calories = 0.0
    count = 0
    for run in runs:
        run_date = run.get("run_date")
        if not run_date or run_date < start or run_date >= end:
            continue
        distance_m += float(run.get("distance_m") or 0)
        moving_time_s += int(run.get("moving_time_s") or 0)
        calories += float(run.get("calories") or 0)
        count += 1
    return {
        "week_start": start.isoformat(),
        "distance_m": distance_m,
        "distance_km": distance_m / 1000.0,
        "moving_time_s": moving_time_s,
        "calories": calories,
        "runs": count,
    }


def _date_label(run: dict[str, Any]) -> str:
    run_date = run.get("run_date")
    if run_date:
        return run_date.isoformat()[:10]
    return (run.get("start_date_local") or "")[:10]


def pace_trend(runs: list[dict[str, Any]], min_distance_m: float = 3000, limit: int = 20) -> list[dict[str, Any]]:
    eligible = [
        run
        for run in runs
        if (run.get("distance_m") or 0) >= min_distance_m and run.get("pace_sec_per_km") is not None
    ]
    recent = eligible[-limit:]
    return [
        {
            "date": _date_label(run),
            "label": (run.get("name") or "Run")[:24],
            "pace_sec_per_km": run["pace_sec_per_km"],
            "distance_km": (run.get("distance_m") or 0) / 1000.0,
        }
        for run in recent
    ]


def best_5k_estimate(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for run in runs:
        distance_m = float(run.get("distance_m") or 0)
        moving_time_s = run.get("moving_time_s")
        if distance_m < 4500 or not moving_time_s:
            continue
        projected_5k_s = float(moving_time_s) * 5000.0 / distance_m
        if best is None or projected_5k_s < best["projected_5k_s"]:
            best = {
                "run_id": run["id"],
                "name": run.get("name"),
                "date": _date_label(run),
                "distance_km": distance_m / 1000.0,
                "projected_5k_s": projected_5k_s,
            }
    return best


def weight_trend(conn, weeks: int = 12) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT date, weight_kg FROM weight_logs ORDER BY date ASC"
    ).fetchall()
    buckets: dict[date, list[float]] = {}
    for row in rows:
        d = _parse_date(row["date"])
        if not d:
            continue
        week = _week_start(d)
        buckets.setdefault(week, []).append(float(row["weight_kg"]))

    result = []
    for week_start in sorted(buckets.keys())[-weeks:]:
        values = buckets[week_start]
        result.append(
            {
                "week_start": week_start.isoformat(),
                "avg_weight_kg": sum(values) / len(values),
            }
        )
    return result


def weight_change(conn, days: int = 30) -> dict[str, Any] | None:
    rows = conn.execute(
        "SELECT date, weight_kg FROM weight_logs ORDER BY date ASC"
    ).fetchall()
    if not rows:
        return None
    parsed = []
    for row in rows:
        d = _parse_date(row["date"])
        if d:
            parsed.append((d, float(row["weight_kg"])))
    if not parsed:
        return None
    latest_date, latest_weight = parsed[-1]
    target_date = latest_date - timedelta(days=days)
    baseline = parsed[0][1]
    for d, weight in parsed:
        if d <= target_date:
            baseline = weight
    return {
        "latest_date": latest_date.isoformat(),
        "latest_weight_kg": latest_weight,
        "baseline_weight_kg": baseline,
        "change_kg": latest_weight - baseline,
        "days": days,
    }


def weekly_weight_vs_distance(
    runs: list[dict[str, Any]], weight_weeks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    distance_by_week = {item["week_start"]: item["distance_m"] / 1000.0 for item in weekly_stats(runs, 52)}
    merged = []
    for item in weight_weeks:
        week = item["week_start"]
        merged.append(
            {
                "week_start": week,
                "avg_weight_kg": item["avg_weight_kg"],
                "distance_km": distance_by_week.get(week, 0.0),
            }
        )
    return merged


def build_dashboard(conn) -> dict[str, Any]:
    runs = _fetch_runs(conn)
    return {
        "runs_count": len(runs),
        "this_week": this_week_summary(runs),
        "weekly": weekly_stats(runs, 12),
        "pace_trend": pace_trend(runs),
        "best_5k": best_5k_estimate(runs),
        "weight_trend": weight_trend(conn, 12),
        "weight_change": weight_change(conn),
        "weight_vs_distance": weekly_weight_vs_distance(runs, weight_trend(conn, 12)),
        "latest": list(reversed(runs[-10:])),
    }
