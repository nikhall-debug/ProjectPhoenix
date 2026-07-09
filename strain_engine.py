from datetime import date

from database import get_metric_values_for_date


def build_daily_strain(readiness_profile=None, target_date=None):
    if target_date is None:
        target_date = date.today()

    current_strain = _build_current_strain(target_date)
    capacity = _build_capacity(readiness_profile)

    remaining = capacity - current_strain["strain_score"]

    return {
        "date": target_date.isoformat(),
        "capacity": capacity,
        "current_strain": current_strain["strain_score"],
        "remaining": remaining,
        "balance_label": _balance_label(remaining),
        "balance_summary": _balance_summary(capacity, current_strain["strain_score"], remaining),
        "exercise_minutes": current_strain["exercise_minutes"],
        "active_energy": current_strain["active_energy"],
        "walking_distance": current_strain["walking_distance"],
    }


def _build_capacity(readiness_profile):
    if not readiness_profile:
        return 50

    readiness_score = readiness_profile.get("readiness_score", 50)
    risk_level = readiness_profile.get("risk_level", "Moderate")

    capacity = readiness_score

    if risk_level == "Low":
        capacity += 5
    elif risk_level == "High":
        capacity -= 15

    return max(0, min(100, round(capacity)))


def _build_current_strain(target_date):
    steps = _sum_metric("apple_steps", target_date)
    exercise_minutes = _sum_metric("apple_exercise_minutes", target_date)
    active_energy = _sum_metric("apple_active_energy_kj", target_date)
    walking_distance = _sum_metric("apple_walking_running_distance_km", target_date)

    strain = 0
    strain += steps / 1000 * 2
    strain += exercise_minutes * 1.2
    strain += active_energy / 120
    strain += walking_distance * 4

    return {
        "strain_score": round(strain),
        "steps": steps,
        "exercise_minutes": exercise_minutes,
        "active_energy": active_energy,
        "walking_distance": walking_distance,
    }


def _sum_metric(metric_type, target_date):
    values = get_metric_values_for_date(metric_type, target_date)
    return sum(item["value"] for item in values)


def _balance_label(remaining):
    if remaining >= 40:
        return "Plenty left"
    if remaining >= 20:
        return "On track"
    if remaining >= 0:
        return "Near capacity"
    if remaining >= -15:
        return "Slightly over"
    return "Overreached"


def _balance_summary(capacity, current, remaining):
    if remaining >= 20:
        return f"You have used {current} of today's estimated capacity of {capacity}."
    if remaining >= 0:
        return f"You are close to today's estimated capacity: {current} of {capacity} used."
    return f"You are currently {abs(remaining)} points over today's estimated capacity."