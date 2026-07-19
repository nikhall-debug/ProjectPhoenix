from math import isfinite
from statistics import mean, stdev
from typing import Any, Optional

from database import get_metric_values_since


BASELINE_METRICS = {
    "hrv": "apple_hrv_ms",
    "resting_hr": "apple_resting_hr_bpm",
    "sleep": "apple_sleep_total_hours",
    "respiratory_rate": "apple_respiratory_rate",
    "blood_oxygen": "apple_blood_oxygen_percent",
    "steps": "apple_steps",
    "exercise_minutes": "apple_exercise_minutes",
    "active_energy": "apple_active_energy_kj",
    "walking_hr": "apple_walking_hr_bpm",
}


def _safe_float(value: Any) -> Optional[float]:
    """
    Converts a value to a finite float.

    Returns None when the value is missing, invalid, NaN, or infinite.
    """

    try:
        if value is None:
            return None

        number = float(value)

        if not isfinite(number):
            return None

        return number

    except (TypeError, ValueError):
        return None


def _extract_values(records: list[dict]) -> list[float]:
    """
    Extracts valid numeric values from database records.
    """

    clean_values = []

    for record in records:
        value = _safe_float(record.get("value"))

        if value is not None:
            clean_values.append(value)

    return clean_values


def _safe_mean(values: list[float]) -> Optional[float]:
    """
    Returns the mean of a list, or None when the list is empty.
    """

    if not values:
        return None

    return mean(values)


def build_all_baselines():
    """
    Builds all standard Phoenix baselines in one place.
    """

    baselines = {}

    for context_key, metric_type in BASELINE_METRICS.items():
        baselines[context_key] = build_metric_baseline(metric_type)

    return baselines


def build_metric_baseline(metric_type):
    """
    Builds a personal baseline for one metric.

    Returns:
        - latest value
        - 7-day average
        - 30-day average
        - personal normal range
        - trend
        - status
        - confidence
        - human summary
    """

    records30 = get_metric_values_since(metric_type, days=30) or []
    records7 = get_metric_values_since(metric_type, days=7) or []

    values30 = _extract_values(records30)
    values7 = _extract_values(records7)

    if not values30:
        return {
            "metric_type": metric_type,
            "latest": None,
            "average_7": None,
            "average_30": None,
            "delta": None,
            "delta_percent": None,
            "normal_low": None,
            "normal_high": None,
            "trend": "Unknown",
            "status": "No data",
            "confidence": 0,
            "summary": "No historical data available.",
        }

    # The database function currently returns newest readings first.
    # Find the first valid value so one invalid record does not break Phoenix.
    latest = None

    for record in records30:
        latest = _safe_float(record.get("value"))

        if latest is not None:
            break

    if latest is None:
        latest = values30[0]

    avg30 = _safe_mean(values30)
    avg7 = _safe_mean(values7)

    # This should always exist because values30 has already been checked,
    # but the guard keeps the function safe if its implementation changes.
    if avg30 is None:
        return {
            "metric_type": metric_type,
            "latest": latest,
            "average_7": avg7,
            "average_30": None,
            "delta": None,
            "delta_percent": None,
            "normal_low": None,
            "normal_high": None,
            "trend": "Unknown",
            "status": "No data",
            "confidence": 0,
            "summary": "No valid historical data available.",
        }

    delta = latest - avg30

    delta_percent = 0.0

    if avg30 != 0:
        delta_percent = (delta / avg30) * 100

    if len(values30) > 1:
        sd = stdev(values30)
    else:
        sd = 0.0

    normal_low = avg30 - sd
    normal_high = avg30 + sd

    trend = _trend(avg7, avg30)
    status = _status(delta_percent)

    confidence = min(len(values30) * 3, 100)

    summary = _summary(
        metric_type,
        latest,
        avg30,
        delta_percent,
        status,
    )

    return {
        "metric_type": metric_type,
        "latest": latest,
        "average_7": avg7,
        "average_30": avg30,
        "delta": delta,
        "delta_percent": delta_percent,
        "normal_low": normal_low,
        "normal_high": normal_high,
        "trend": trend,
        "status": status,
        "confidence": confidence,
        "summary": summary,
    }


def _status(delta_percent):

    if delta_percent >= 15:
        return "Well above baseline"

    if delta_percent >= 5:
        return "Above baseline"

    if delta_percent <= -15:
        return "Well below baseline"

    if delta_percent <= -5:
        return "Below baseline"

    return "Near baseline"


def _trend(avg7, avg30):

    if avg7 is None or avg30 is None:
        return "Unknown"

    if avg7 > avg30 * 1.05:
        return "Improving"

    if avg7 < avg30 * 0.95:
        return "Declining"

    return "Stable"


def _summary(metric, latest, average, delta_percent, status):

    if latest is None or average is None or delta_percent is None:
        return f"{metric} does not yet have enough valid data for comparison."

    if status == "Near baseline":
        return f"{metric} is close to your normal."

    direction = "above" if delta_percent > 0 else "below"

    return (
        f"{metric} is {abs(delta_percent):.1f}% "
        f"{direction} your normal."
    )