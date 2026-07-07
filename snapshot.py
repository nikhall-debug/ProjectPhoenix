from datetime import date

from analytics import weight_summary, body_fat_summary, muscle_summary, pwv_summary
from database import (
    get_latest_metric,
    get_latest_checkin,
    get_checkin_for_date,
)


def build_morning_snapshot():
    today_checkin = get_checkin_for_date(date.today())
    latest_checkin = get_latest_checkin()

    weight = weight_summary()
    body_fat = body_fat_summary()
    muscle = muscle_summary()
    pwv = pwv_summary()

    systolic = get_latest_metric("withings", "systolic_bp")
    diastolic = get_latest_metric("withings", "diastolic_bp")

    body_measurements_available = weight is not None
    today_checkin_done = today_checkin is not None
    lumen_entered = today_checkin is not None and today_checkin.get("lumen_score") is not None

    completed = 0
    total = 3

    if body_measurements_available:
        completed += 1

    if today_checkin_done:
        completed += 1

    if lumen_entered:
        completed += 1

    snapshot_percent = round((completed / total) * 100)

    return {
        "completed": completed,
        "total": total,
        "snapshot_percent": snapshot_percent,
        "body_measurements_available": body_measurements_available,
        "today_checkin_done": today_checkin_done,
        "lumen_entered": lumen_entered,
        "today_checkin": today_checkin,
        "latest_checkin": latest_checkin,
        "weight": weight,
        "body_fat": body_fat,
        "muscle": muscle,
        "pwv": pwv,
        "systolic": systolic,
        "diastolic": diastolic,
    }