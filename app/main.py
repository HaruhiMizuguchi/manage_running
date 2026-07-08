from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .db import connect, init_db
from .strava_import import is_run, parse_strava_export


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Run Manager (Strava Export)")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    with connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS c FROM activities WHERE activity_type IS NOT NULL"
        ).fetchone()["c"]
        runs = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM activities
            WHERE LOWER(COALESCE(activity_type,'')) IN ('run','running')
               OR LOWER(COALESCE(sport_type,'')) IN ('run','running')
            """
        ).fetchone()["c"]
        latest = conn.execute(
            """
            SELECT id, name, start_date_local, distance_m, moving_time_s
            FROM activities
            WHERE (LOWER(COALESCE(activity_type,'')) IN ('run','running')
                OR LOWER(COALESCE(sport_type,'')) IN ('run','running'))
            ORDER BY start_date_local DESC
            LIMIT 10
            """
        ).fetchall()
    return TEMPLATES.TemplateResponse(
        "home.html",
        {"request": request, "total": total, "runs": runs, "latest": latest},
    )


@app.get("/import", response_class=HTMLResponse)
def import_page(request: Request):
    return TEMPLATES.TemplateResponse("import.html", {"request": request})


@app.post("/import")
async def import_strava(file: UploadFile = File(...), only_runs: bool = Form(True)):
    data = await file.read()
    imported = 0
    skipped = 0
    with connect() as conn:
        for a in parse_strava_export(data, file.filename or "upload"):
            if only_runs and not is_run(a):
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
            """
            SELECT id, name, start_date_local, distance_m, moving_time_s,
                   total_elevation_gain_m, average_heartrate
            FROM activities
            WHERE (LOWER(COALESCE(activity_type,'')) IN ('run','running')
                OR LOWER(COALESCE(sport_type,'')) IN ('run','running'))
            ORDER BY start_date_local DESC
            LIMIT 500
            """
        ).fetchall()
    return TEMPLATES.TemplateResponse("runs.html", {"request": request, "rows": rows})


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(request: Request, run_id: int):
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM activities WHERE id=?",
            (run_id,),
        ).fetchone()
    if not row:
        return HTMLResponse("Not found", status_code=404)
    return TEMPLATES.TemplateResponse("run_detail.html", {"request": request, "a": row})


@app.get("/weight", response_class=HTMLResponse)
def weight_page(request: Request):
    with connect() as conn:
        rows = conn.execute(
            "SELECT date, weight_kg, note FROM weight_logs ORDER BY date DESC LIMIT 365"
        ).fetchall()
    return TEMPLATES.TemplateResponse("weight.html", {"request": request, "rows": rows})


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

