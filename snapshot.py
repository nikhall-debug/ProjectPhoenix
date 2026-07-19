from datetime import date
from typing import Any, Dict, List, Optional

from database import (
    get_checkin_for_date,
    get_latest_checkin,
    get_latest_health_metric,
    get_metric_values_since,
)


# ---------------------------------------------------------------------
# Metric names
# ---------------------------------------------------------------------

WEIGHT_METRIC = "weight_kg"
BODY_FAT_METRIC = "fat_percent"
MUSCLE_METRIC = "muscle_mass_kg"
PWV_METRIC = "pulse_wave_velocity"
SYSTOLIC_METRIC = "systolic_bp"
DIASTOLIC_METRIC = "diastolic_bp"


# ---------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------

def _safe_float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def _build_latest_metric(
    metric_type: str,
) -> Optional[Dict[str, Any]]:
    """
    Return the latest stored health measurement in a consistent format.
    """
    metric = get_latest_health_metric(metric_type)

    if not metric:
        return None

    value = _safe_float(metric.get("value"))

    if value is None:
        return None

    return {
        "metric_type": metric_type,
        "value": value,
        "unit": metric.get("unit"),
        "measured_at": metric.get("measured_at"),
        "source": metric.get("source"),
    }


def _build_metric_trend(
    metric_type: str,
    days: int = 30,
) -> Optional[Dict[str, Any]]:
    """
    Build a current-value and period-change summary for one metric.

    The latest reading is compared with the oldest available reading
    inside the requested period.
    """
    latest = _build_latest_metric(metric_type)

    if latest is None:
        return None

    values = get_metric_values_since(
        metric_type=metric_type,
        days=days,
    )

    valid_values = []

    for item in values:
        value = _safe_float(item.get("value"))

        if value is None:
            continue

        valid_values.append(
            {
                "value": value,
                "unit": item.get("unit"),
                "measured_at": item.get("measured_at"),
                "source": item.get("source"),
            }
        )

    # get_metric_values_since returns newest first.
    if len(valid_values) >= 2:
        current_value = valid_values[0]["value"]
        oldest_value = valid_values[-1]["value"]
        delta = current_value - oldest_value
    else:
        delta = None

    return {
        "metric_type": metric_type,
        "current": latest["value"],
        "value": latest["value"],
        "unit": latest.get("unit"),
        "measured_at": latest.get("measured_at"),
        "source": latest.get("source"),
        "delta_30d": delta,
        "reading_count_30d": len(valid_values),
    }


def _has_value(value: Any) -> bool:
    """
    Treat zero as a valid value while still identifying missing data.
    """
    return value is not None


# ---------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------

def build_morning_snapshot(
    target_date: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Build the current Phoenix morning snapshot.

    The snapshot owns current-state collection and completeness only.
    It does not interpret health, recovery or readiness.
    """
    if target_date is None:
        target_date = date.today()

    target_date_string = str(target_date)

    today_checkin = get_checkin_for_date(
        target_date_string
    )

    latest_checkin = get_latest_checkin()

    weight = _build_metric_trend(
        WEIGHT_METRIC,
        days=30,
    )

    body_fat = _build_metric_trend(
        BODY_FAT_METRIC,
        days=30,
    )

    muscle = _build_metric_trend(
        MUSCLE_METRIC,
        days=30,
    )

    pwv = _build_metric_trend(
        PWV_METRIC,
        days=30,
    )

    systolic = _build_latest_metric(
        SYSTOLIC_METRIC
    )

    diastolic = _build_latest_metric(
        DIASTOLIC_METRIC
    )

    today_checkin_done = today_checkin is not None

    lumen_entered = bool(
        today_checkin
        and _has_value(
            today_checkin.get("lumen_score")
        )
    )

    # Snapshot completeness deliberately tracks the morning inputs
    # Phoenix currently depends on most directly.
    completion_items = {
        "weight_available": weight is not None,
        "body_fat_available": body_fat is not None,
        "muscle_available": muscle is not None,
        "pwv_available": pwv is not None,
        "blood_pressure_available": (
            systolic is not None
            and diastolic is not None
        ),
        "today_checkin_done": today_checkin_done,
        "lumen_entered": lumen_entered,
    }

    completed = sum(
        1
        for is_complete in completion_items.values()
        if is_complete
    )

    total = len(completion_items)

    snapshot_percent = (
        round((completed / total) * 100)
        if total
        else 0
    )

    return {
        "date": target_date_string,

        # Body and cardiovascular measurements
        "weight": weight,
        "body_fat": body_fat,
        "muscle": muscle,
        "pwv": pwv,
        "systolic": systolic,
        "diastolic": diastolic,

        # Check-ins
        "today_checkin": today_checkin,
        "latest_checkin": latest_checkin,
        "today_checkin_done": today_checkin_done,
        "lumen_entered": lumen_entered,

        # Completeness
        "completed": completed,
        "total": total,
        "snapshot_percent": snapshot_percent,
        "completion_items": completion_items,
    }