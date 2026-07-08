from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .analytics import RUN_FILTER, build_dashboard
from .db import connect, init_db
from .formatting import fmt_duration, fmt_km, fmt_pace, fmt_pace_from_sec
from .settings_store import (
    get_target_5k_time_s,
    get_weekly_distance_goal_km,
    set_setting,
)
from .strava_import import is_run, parse_strava_export


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
TEMPLATES.env.filters["fmt_km"] = fmt_km
TEMPLATES.env.filters["fmt_duration"] = fmt_duration
TEMPLATES.env.filters["fmt_pace_from_sec"] = fmt_pace_from_sec
TEMPLATES.env.globals["fmt_pace_for"] = fmt_pace

app = FastAPI(title="Run Manager (Strava Export)")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.on_event("startup")
def _startup() -> None:
    init_db()


def _goal_progress(conn) -> dict:
    dashboard = build_dashboard(conn)
    weekly_goal_km = get_weekly_distance_goal_km(conn)
    this_week_km = dashboard["this_week"]["distance_km"]
    target_5k_s = get_target_5k_time_s(conn)
    best_5k = dashboard["best_5k"]
    return {
        "weekly_goal_km": weekly_goal_km,
        "this_week_km": this_week_km,
        "weekly_progress_pct": min(100.0, (this_week_km / weekly_goal_km * 100.0) if weekly_goal_km else 0),
        "target_5k_s": target_5k_s,
        "best_5k": best_5k,
        "best_5k_gap_s": (
            best_5k["projected_5k_s"] - target_5k_s
            if best_5k and target_5k_s
            else None
        ),
    }


@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    imported: int | None = Query(default=None),
    skipped: int | None = Query(default=None),
):
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM activities").fetchone()["c"]
        dashboard = build_dashboard(conn)
        goals = _goal_progress(conn)
    return TEMPLATES.TemplateResponse(
        request,
        "home.html",
        {
            "total": total,
            "imported": imported,
            "skipped": skipped,
            "dashboard": dashboard,
            "goals": goals,
        },
    )


@app.get("/import", response_class=HTMLResponse)
def import_page(request: Request):
    return TEMPLATES.TemplateResponse(request, "import.html", {})


@app.post("/import")
async def import_strava(file: UploadFile = File(...), only_runs: str | None = Form(None)):
    data = await file.read()
    imported = 0
    skipped = 0
    only_runs_enabled = only_runs is not None
    with connect() as conn:
        for a in parse_strava_export(data, file.filename or "upload"):
            if only_runs_enabled and not is_run(a):
                skipped += 1
                continue
            conn.execute(
                """
                INSERT INTO activities (
                  strava_activity_id, name, activity_type, sport_type, start_date_local,
                  distance_m, moving_time_s, elapsed_time_s, total_elevation_gain_m,
                  average_speed_mps, max_speed_mps, average_heartrate, max_heartrate,
                  calories, kudos_count
                ) VALUES (
                  ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                )
                ON CONFLICT(strava_activity_id) DO UPDATE SET
                  name=excluded.name,
                  activity_type=excluded.activity_type,
                  sport_type=excluded.sport_type,
                  start_date_local=excluded.start_date_local,
                  distance_m=excluded.distance_m,
                  moving_time_s=excluded.moving_time_s,
                  elapsed_time_s=excluded.elapsed_time_s,
                  total_elevation_gain_m=excluded.total_elevation_gain_m,
                  average_speed_mps=excluded.average_speed_mps,
                  max_speed_mps=excluded.max_speed_mps,
                  average_heartrate=excluded.average_heartrate,
                  max_heartrate=excluded.max_heartrate,
                  calories=excluded.calories,
                  kudos_count=excluded.kudos_count
                """,
                (
                    a.strava_activity_id,
                    a.name,
                    a.activity_type,
                    a.sport_type,
                    a.start_date_local,
                    a.distance_m,
                    a.moving_time_s,
                    a.elapsed_time_s,
                    a.total_elevation_gain_m,
                    a.average_speed_mps,
                    a.max_speed_mps,
                    a.average_heartrate,
                    a.max_heartrate,
                    a.calories,
                    a.kudos_count,
                ),
            )
            imported += 1
    url = f"/?imported={imported}&skipped={skipped}"
    return RedirectResponse(url=url, status_code=303)


@app.get("/runs", response_class=HTMLResponse)
def runs_page(request: Request):
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, name, start_date_local, distance_m, moving_time_s,
                   total_elevation_gain_m, average_heartrate
            FROM activities
            WHERE {RUN_FILTER}
            ORDER BY start_date_local DESC
            LIMIT 500
            """
        ).fetchall()
    return TEMPLATES.TemplateResponse(request, "runs.html", {"rows": rows})


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(request: Request, run_id: int):
    with connect() as conn:
        row = conn.execute("SELECT * FROM activities WHERE id=?", (run_id,)).fetchone()
    if not row:
        return HTMLResponse("Not found", status_code=404)
    return TEMPLATES.TemplateResponse(request, "run_detail.html", {"a": row})


@app.get("/weight", response_class=HTMLResponse)
def weight_page(request: Request):
    with connect() as conn:
        rows = conn.execute(
            "SELECT date, weight_kg, note FROM weight_logs ORDER BY date DESC LIMIT 365"
        ).fetchall()
    return TEMPLATES.TemplateResponse(request, "weight.html", {"rows": rows})


@app.post("/weight")
def add_weight(date: str = Form(...), weight_kg: float = Form(...), note: str = Form("")):
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO weight_logs(date, weight_kg, note)
            VALUES (?,?,?)
            ON CONFLICT(date) DO UPDATE SET
              weight_kg=excluded.weight_kg,
              note=excluded.note
            """,
            (date, weight_kg, note),
        )
    return RedirectResponse(url="/weight", status_code=303)


@app.get("/goals", response_class=HTMLResponse)
def goals_page(request: Request):
    with connect() as conn:
        weekly_goal_km = get_weekly_distance_goal_km(conn)
        target_5k_s = get_target_5k_time_s(conn)
        progress = _goal_progress(conn)
        dashboard = build_dashboard(conn)
    target_5k_min = target_5k_s // 60 if target_5k_s else ""
    target_5k_sec = target_5k_s % 60 if target_5k_s else ""
    return TEMPLATES.TemplateResponse(
        request,
        "goals.html",
        {
            "weekly_goal_km": weekly_goal_km,
            "target_5k_min": target_5k_min,
            "target_5k_sec": target_5k_sec,
            "progress": progress,
            "best_5k": dashboard["best_5k"],
        },
    )


@app.post("/goals")
def save_goals(
    weekly_distance_km: float = Form(...),
    target_5k_min: int | None = Form(None),
    target_5k_sec: int | None = Form(None),
):
    with connect() as conn:
        set_setting(conn, "weekly_distance_km", str(weekly_distance_km))
        if target_5k_min is not None and target_5k_sec is not None:
            total = max(0, target_5k_min) * 60 + max(0, target_5k_sec)
            set_setting(conn, "target_5k_time_s", str(total))
        else:
            set_setting(conn, "target_5k_time_s", "")
    return RedirectResponse(url="/goals", status_code=303)
