import json
from datetime import date

from workout_database import load_training_sessions


def build_workout_summary(target_date=None):
    if target_date is None:
        target_date = date.today().isoformat()
    else:
        target_date = str(target_date)

    sessions = load_training_sessions(limit=500)

    if sessions.empty:
        return {
            "date": target_date,
            "has_training": False,
            "summary": "No workout data recorded yet.",
        }

    day = sessions[sessions["session_date"] == target_date]

    if day.empty:
        latest_date = sessions["session_date"].max()
        day = sessions[sessions["session_date"] == latest_date]
        target_date = latest_date

    cycling = day[day["session_type"] == "Cycling"]
    strength = day[day["session_type"] == "Strength"]
    movement = day[day["session_type"].isin(["Walking", "Hiking", "Running", "Mobility", "Other"])]

    cycling_minutes = _sum_minutes(cycling)
    strength_minutes = _sum_minutes(strength)
    movement_minutes = _sum_minutes(movement)
    xss = _sum_xert_xss(cycling)

    return {
        "date": target_date,
        "has_training": True,
        "cycling_count": len(cycling),
        "cycling_minutes": cycling_minutes,
        "cycling_xss": xss,
        "strength_count": len(strength),
        "strength_minutes": strength_minutes,
        "movement_count": len(movement),
        "movement_minutes": movement_minutes,
        "interpretation": _build_interpretation(
            cycling_count=len(cycling),
            cycling_minutes=cycling_minutes,
            cycling_xss=xss,
            strength_count=len(strength),
            strength_minutes=strength_minutes,
            movement_count=len(movement),
            movement_minutes=movement_minutes,
        ),
    }


def _sum_minutes(df):
    if df.empty or "duration_minutes" not in df:
        return 0.0

    return round(float(df["duration_minutes"].fillna(0).sum()), 1)


def _sum_xert_xss(cycling):
    total = 0.0

    for _, session in cycling.iterrows():
        try:
            raw = json.loads(session.get("raw_data") or "{}")
        except Exception:
            continue

        summary = raw.get("summary", {})
        xss = summary.get("xss")

        if xss is not None:
            total += float(xss)

    return round(total, 1)


def _build_interpretation(
    cycling_count,
    cycling_minutes,
    cycling_xss,
    strength_count,
    strength_minutes,
    movement_count,
    movement_minutes,
):
    notes = []

    if cycling_count:
        if cycling_xss >= 90:
            notes.append("Cycling load was high.")
        elif cycling_xss >= 40:
            notes.append("Cycling load was moderate.")
        else:
            notes.append("Cycling load was light.")

    if strength_count:
        notes.append("Strength work adds muscular recovery cost.")

    if movement_count and not cycling_count and not strength_count:
        notes.append("Movement was recovery-supportive.")
    elif movement_count:
        notes.append("Additional movement adds useful context but should not be treated as fake strain.")

    if not notes:
        notes.append("No meaningful workout load recorded.")

    return " ".join(notes)