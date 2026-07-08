import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import APPLE_AUTOSYNC_FOLDER
from database import save_health_measurement


APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)


KNOWN_METRICS = {
    "Heart Rate Variability": ("apple_hrv_ms", "ms"),
    "Resting Heart Rate": ("apple_resting_hr_bpm", "bpm"),
    "Respiratory Rate": ("apple_respiratory_rate", "breaths/min"),
    "VO2 Max": ("apple_vo2_max", "ml/kg/min"),
    "Active Energy": ("apple_active_energy_kj", "kJ"),
    "Exercise Time": ("apple_exercise_minutes", "min"),
    "Step Count": ("apple_steps", "steps"),
    "Walking Heart Rate Average": ("apple_walking_hr_bpm", "bpm"),
    "Walking + Running Distance": ("apple_walking_running_distance_km", "km"),
    "Sleeping Wrist Temperature": ("apple_sleeping_wrist_temperature_c", "degC"),
    "Blood Oxygen Saturation": ("apple_blood_oxygen_percent", "%"),
    "Sleep Analysis": ("apple_sleep_analysis", "unknown"),
}


def sync_health_auto_export_folder():
    folder = Path(APPLE_AUTOSYNC_FOLDER).expanduser()

    if not folder.exists():
        return {
            "imported": 0,
            "duplicates": 0,
            "files_seen": 0,
            "error": f"AutoSync folder not found: {folder}",
        }

    imported = 0
    duplicates = 0
    files_seen = 0

    for hae_file in folder.rglob("*.hae"):
        files_seen += 1

        measurement = _parse_hae_file(hae_file)

        if measurement is None:
            continue

        inserted = save_health_measurement(
            source="apple_health",
            metric_type=measurement["metric_type"],
            value=measurement["value"],
            unit=measurement["unit"],
            measured_at=measurement["measured_at"],
            raw_type=None,
            raw_data=measurement["raw_data"],
        )

        if inserted:
            imported += 1
        else:
            duplicates += 1

    return {
        "imported": imported,
        "duplicates": duplicates,
        "files_seen": files_seen,
        "error": None,
    }


def _parse_hae_file(path):
    data = path.read_bytes()
    text = data.decode("utf-8", errors="ignore")

    metric_type, unit = _detect_metric(path, text)

    if metric_type is None:
        return None

    value = _extract_float(text, "qty")
    date_seconds = _extract_float(text, "date")

    if value is None or date_seconds is None:
        return None

    measured_at = _apple_time_to_iso(date_seconds)

    return {
        "metric_type": metric_type,
        "value": value,
        "unit": unit,
        "measured_at": measured_at,
        "raw_data": text[:1000],
    }


def _detect_metric(path, text):
    combined = f"{path} {text}"

    for metric_name, metric_info in KNOWN_METRICS.items():
        if metric_name in combined:
            return metric_info

    return None, None


def _extract_float(text, key):
    pattern = rf'"{key}"\s*:\s*(-?\d+(?:\.\d+)?)'
    match = re.search(pattern, text)

    if not match:
        return None

    return float(match.group(1))


def _apple_time_to_iso(seconds):
    date_time = APPLE_EPOCH + timedelta(seconds=seconds)
    return date_time.isoformat()