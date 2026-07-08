from __future__ import annotations


def fmt_km(distance_m: float | None, digits: int = 2) -> str:
    if not distance_m:
        return "-"
    return f"{distance_m / 1000:.{digits}f} km"


def fmt_duration(seconds: int | float | None) -> str:
    if seconds is None:
        return "-"
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def pace_sec_per_km(distance_m: float | None, moving_time_s: int | float | None) -> float | None:
    if not distance_m or not moving_time_s or distance_m <= 0:
        return None
    return float(moving_time_s) * 1000.0 / float(distance_m)


def fmt_pace(distance_m: float | None, moving_time_s: int | float | None) -> str:
    pace = pace_sec_per_km(distance_m, moving_time_s)
    if pace is None:
        return "-"
    return f"{fmt_duration(pace)} /km"


def fmt_pace_from_sec(pace_sec: float | None) -> str:
    if pace_sec is None:
        return "-"
    return f"{fmt_duration(pace_sec)} /km"
