import json
from datetime import date

from workout_database import load_training_sessions


def build_workout_intelligence(target_date=None):
    """
    Workout Intelligence v1.

    Purpose:
    - Summarise recorded training for a day.
    - Classify workout load cautiously.
    - Provide structured evidence for the future Coach Engine.
    - Avoid inventing strain from movement/steps.

    This engine answers:
    What did Nik train, how much load did it create, and what does it mean?
    """

    if target_date is None:
        target_date = date.today().isoformat()
    else:
        target_date = str(target_date)

    sessions = load_training_sessions(limit=500)

    if sessions.empty:
        return _empty_intelligence(
            target_date=target_date,
            status="no_data",
            narrative="No workout data recorded yet.",
        )

    day = sessions[sessions["session_date"] == target_date]

    if day.empty:
        latest_date = sessions["session_date"].max()
        day = sessions[sessions["session_date"] == latest_date]
        target_date = latest_date
        status = "latest_available_day"
    else:
        status = "target_day"

    cycling = day[day["session_type"] == "Cycling"]
    strength = day[day["session_type"] == "Strength"]
    movement = day[
        day["session_type"].isin(
            ["Walking", "Hiking", "Running", "Mobility", "Other"]
        )
    ]

    cycling_minutes = _sum_minutes(cycling)
    strength_minutes = _sum_minutes(strength)
    movement_minutes = _sum_minutes(movement)
    cycling_xss = _sum_xert_xss(cycling)

    cycling_load = _classify_cycling_load(cycling_xss, cycling_minutes, len(cycling))
    strength_load = _classify_strength_load(strength_minutes, len(strength))
    movement_context = _classify_movement_context(
        movement_minutes,
        len(movement),
        has_cycling=len(cycling) > 0,
        has_strength=len(strength) > 0,
    )

    overall_load = _classify_overall_load(
        cycling_load=cycling_load,
        strength_load=strength_load,
        cycling_count=len(cycling),
        strength_count=len(strength),
        movement_count=len(movement),
    )

    recovery_cost = _classify_recovery_cost(
        overall_load=overall_load,
        cycling_load=cycling_load,
        strength_load=strength_load,
    )

    evidence = _build_evidence(
        cycling_count=len(cycling),
        cycling_minutes=cycling_minutes,
        cycling_xss=cycling_xss,
        cycling_load=cycling_load,
        strength_count=len(strength),
        strength_minutes=strength_minutes,
        strength_load=strength_load,
        movement_count=len(movement),
        movement_minutes=movement_minutes,
        movement_context=movement_context,
    )

    narrative = _build_narrative(
        cycling_count=len(cycling),
        cycling_minutes=cycling_minutes,
        cycling_xss=cycling_xss,
        cycling_load=cycling_load,
        strength_count=len(strength),
        strength_minutes=strength_minutes,
        strength_load=strength_load,
        movement_count=len(movement),
        movement_minutes=movement_minutes,
        movement_context=movement_context,
        overall_load=overall_load,
        recovery_cost=recovery_cost,
    )

    return {
        "date": target_date,
        "status": status,
        "has_training": _has_meaningful_training(
            cycling_count=len(cycling),
            strength_count=len(strength),
            movement_count=len(movement),
        ),
        "training_load": {
            "cycling": {
                "count": len(cycling),
                "minutes": cycling_minutes,
                "xss": cycling_xss,
                "load": cycling_load,
            },
            "strength": {
                "count": len(strength),
                "minutes": strength_minutes,
                "load": strength_load,
            },
            "movement": {
                "count": len(movement),
                "minutes": movement_minutes,
                "context": movement_context,
            },
        },
        "overall_load": overall_load,
        "recovery_cost": recovery_cost,
        "narrative": narrative,
        "evidence": evidence,
    }


def build_workout_summary(target_date=None):
    """
    Compatibility wrapper for the existing app.

    Keeps the old output shape working while using the new
    Workout Intelligence engine internally.
    """

    intelligence = build_workout_intelligence(target_date)

    cycling = intelligence["training_load"]["cycling"]
    strength = intelligence["training_load"]["strength"]
    movement = intelligence["training_load"]["movement"]

    return {
        "date": intelligence["date"],
        "has_training": intelligence["has_training"],
        "cycling_count": cycling["count"],
        "cycling_minutes": cycling["minutes"],
        "cycling_xss": cycling["xss"],
        "strength_count": strength["count"],
        "strength_minutes": strength["minutes"],
        "movement_count": movement["count"],
        "movement_minutes": movement["minutes"],
        "interpretation": intelligence["narrative"],
    }


def _empty_intelligence(target_date, status, narrative):
    return {
        "date": target_date,
        "status": status,
        "has_training": False,
        "training_load": {
            "cycling": {
                "count": 0,
                "minutes": 0.0,
                "xss": 0.0,
                "load": "none",
            },
            "strength": {
                "count": 0,
                "minutes": 0.0,
                "load": "none",
            },
            "movement": {
                "count": 0,
                "minutes": 0.0,
                "context": "none",
            },
        },
        "overall_load": "none",
        "recovery_cost": "none",
        "narrative": narrative,
        "evidence": [],
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


def _has_meaningful_training(cycling_count, strength_count, movement_count):
    return cycling_count > 0 or strength_count > 0 or movement_count > 0


def _classify_cycling_load(cycling_xss, cycling_minutes, cycling_count):
    if cycling_count == 0:
        return "none"

    if cycling_xss >= 90:
        return "high"

    if cycling_xss >= 40:
        return "moderate"

    if cycling_xss > 0:
        return "light"

    if cycling_minutes >= 90:
        return "moderate"

    if cycling_minutes >= 30:
        return "light"

    return "very_light"


def _classify_strength_load(strength_minutes, strength_count):
    if strength_count == 0:
        return "none"

    if strength_minutes >= 60:
        return "high"

    if strength_minutes >= 30:
        return "moderate"

    return "light"


def _classify_movement_context(movement_minutes, movement_count, has_cycling, has_strength):
    if movement_count == 0:
        return "none"

    if not has_cycling and not has_strength:
        return "recovery_supportive"

    if movement_minutes >= 60:
        return "additional_context"

    return "minor_context"


def _classify_overall_load(
    cycling_load,
    strength_load,
    cycling_count,
    strength_count,
    movement_count,
):
    loads = [cycling_load, strength_load]

    if "high" in loads:
        return "high"

    if "moderate" in loads:
        if cycling_count > 0 and strength_count > 0:
            return "high"
        return "moderate"

    if "light" in loads:
        return "light"

    if cycling_count > 0 or strength_count > 0:
        return "very_light"

    if movement_count > 0:
        return "movement_only"

    return "none"


def _classify_recovery_cost(overall_load, cycling_load, strength_load):
    if overall_load == "high":
        return "high"

    if overall_load == "moderate":
        return "moderate"

    if strength_load in ["moderate", "high"]:
        return "muscular"

    if cycling_load in ["light", "very_light"]:
        return "low"

    if overall_load == "movement_only":
        return "minimal"

    return "none"


def _build_evidence(
    cycling_count,
    cycling_minutes,
    cycling_xss,
    cycling_load,
    strength_count,
    strength_minutes,
    strength_load,
    movement_count,
    movement_minutes,
    movement_context,
):
    evidence = []

    if cycling_count:
        evidence.append(
            f"{cycling_count} cycling session(s), {cycling_minutes} min, {cycling_xss} XSS, classified as {cycling_load} load."
        )

    if strength_count:
        evidence.append(
            f"{strength_count} strength session(s), {strength_minutes} min, classified as {strength_load} load."
        )

    if movement_count:
        evidence.append(
            f"{movement_count} movement session(s), {movement_minutes} min, treated as {movement_context} rather than artificial training strain."
        )

    if not evidence:
        evidence.append("No workout, strength, or movement sessions recorded for this day.")

    return evidence


def _build_narrative(
    cycling_count,
    cycling_minutes,
    cycling_xss,
    cycling_load,
    strength_count,
    strength_minutes,
    strength_load,
    movement_count,
    movement_minutes,
    movement_context,
    overall_load,
    recovery_cost,
):
    notes = []

    if cycling_count:
        if cycling_load == "high":
            notes.append(
                f"Cycling created a high training load with {cycling_xss} XSS across {cycling_count} session(s)."
            )
        elif cycling_load == "moderate":
            notes.append(
                f"Cycling created a moderate training load with {cycling_xss} XSS across {cycling_count} session(s)."
            )
        elif cycling_load == "light":
            notes.append(
                f"Cycling was light, with {cycling_xss} XSS across {cycling_count} session(s)."
            )
        else:
            notes.append(
                f"Cycling was very light, with {cycling_minutes} minutes recorded."
            )

    if strength_count:
        if strength_load == "high":
            notes.append(
                f"Strength work was substantial at {strength_minutes} minutes and may add muscular recovery cost."
            )
        elif strength_load == "moderate":
            notes.append(
                f"Strength work was meaningful at {strength_minutes} minutes and may influence muscle readiness."
            )
        else:
            notes.append(
                f"Strength work was light at {strength_minutes} minutes."
            )

    if movement_count:
        if movement_context == "recovery_supportive":
            notes.append(
                f"Movement was recovery-supportive, with {movement_minutes} minutes recorded."
            )
        else:
            notes.append(
                "Additional movement adds useful context, but Phoenix is not treating it as fake training strain."
            )

    if not notes:
        return "No meaningful workout load recorded."

    if overall_load == "high":
        notes.append("Overall workout load looks high.")
    elif overall_load == "moderate":
        notes.append("Overall workout load looks moderate.")
    elif overall_load == "light":
        notes.append("Overall workout load looks light.")
    elif overall_load == "movement_only":
        notes.append("This was a movement-only day rather than a training-load day.")

    if recovery_cost in ["high", "moderate", "muscular"]:
        notes.append(f"Estimated recovery cost is {recovery_cost}.")

    return " ".join(notes)