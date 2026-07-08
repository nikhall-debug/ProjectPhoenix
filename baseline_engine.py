from statistics import mean, stdev

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

    values30 = get_metric_values_since(metric_type, days=30)
    values7 = get_metric_values_since(metric_type, days=7)

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

    latest = values30[0]["value"]

    avg30 = mean(v["value"] for v in values30)
    avg7 = mean(v["value"] for v in values7)

    delta = latest - avg30

    delta_percent = 0
    if avg30 != 0:
        delta_percent = (delta / avg30) * 100

    if len(values30) > 1:
        sd = stdev(v["value"] for v in values30)
    else:
        sd = 0

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

    if avg7 > avg30 * 1.05:
        return "Improving"

    if avg7 < avg30 * 0.95:
        return "Declining"

    return "Stable"


def _summary(metric, latest, average, delta_percent, status):

    if status == "Near baseline":
        return f"{metric} is close to your normal."

    direction = "above" if delta_percent > 0 else "below"

    return (
        f"{metric} is {abs(delta_percent):.1f}% "
        f"{direction} your normal."
    )