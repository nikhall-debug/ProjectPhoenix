import json
import zipfile
from io import BytesIO

from database import save_health_measurement


METRIC_MAP = {
    "heart_rate_variability": ("apple_hrv_ms", "ms"),
    "resting_heart_rate": ("apple_resting_hr_bpm", "bpm"),
    "respiratory_rate": ("apple_respiratory_rate", "breaths/min"),
    "vo2_max": ("apple_vo2_max", "ml/kg/min"),
    "active_energy": ("apple_active_energy_kj", "kJ"),
    "apple_exercise_time": ("apple_exercise_minutes", "min"),
    "step_count": ("apple_steps", "steps"),
    "walking_heart_rate_average": ("apple_walking_hr_bpm", "bpm"),
    "walking_running_distance": ("apple_walking_running_distance_km", "km"),
}


SLEEP_FIELDS = {
    "totalSleep": ("apple_sleep_total_hours", "hr"),
    "deep": ("apple_sleep_deep_hours", "hr"),
    "rem": ("apple_sleep_rem_hours", "hr"),
    "core": ("apple_sleep_core_hours", "hr"),
    "awake": ("apple_sleep_awake_hours", "hr"),
}


def import_health_auto_export_zip(uploaded_file):
    zip_bytes = uploaded_file.getvalue()
    imported = 0
    duplicates = 0

    with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
        json_name = _find_main_json(archive)

        if json_name is None:
            return {
                "imported": 0,
                "duplicates": 0,
                "error": "No JSON export found in ZIP.",
            }

        export_data = json.loads(archive.read(json_name))
        data = export_data.get("data", {})
        metrics = data.get("metrics", [])

        for metric in metrics:
            metric_name = metric.get("name")

            if metric_name in METRIC_MAP:
                new_count, duplicate_count = _import_standard_metric(metric)
                imported += new_count
                duplicates += duplicate_count

            if metric_name == "sleep_analysis":
                new_count, duplicate_count = _import_sleep_metric(metric)
                imported += new_count
                duplicates += duplicate_count

    return {
        "imported": imported,
        "duplicates": duplicates,
        "error": None,
    }


def _find_main_json(archive):
    for name in archive.namelist():
        if name.lower().endswith(".json"):
            return name

    return None


def _import_standard_metric(metric):
    metric_name = metric.get("name")
    metric_type, unit = METRIC_MAP[metric_name]

    imported = 0
    duplicates = 0

    for item in metric.get("data", []):
        measured_at = item.get("date")
        value = item.get("qty")

        if measured_at is None or value is None:
            continue

        inserted = save_health_measurement(
            source="apple_health",
            metric_type=metric_type,
            value=value,
            unit=unit,
            measured_at=measured_at,
            raw_type=None,
            raw_data=json.dumps(item),
        )

        if inserted:
            imported += 1
        else:
            duplicates += 1

    return imported, duplicates


def _import_sleep_metric(metric):
    imported = 0
    duplicates = 0

    for item in metric.get("data", []):
        measured_at = item.get("date")

        if measured_at is None:
            continue

        for sleep_field, metric_info in SLEEP_FIELDS.items():
            value = item.get(sleep_field)

            if value is None:
                continue

            metric_type, unit = metric_info

            inserted = save_health_measurement(
                source="apple_health",
                metric_type=metric_type,
                value=value,
                unit=unit,
                measured_at=measured_at,
                raw_type=None,
                raw_data=json.dumps(item),
            )

            if inserted:
                imported += 1
            else:
                duplicates += 1

    return imported, duplicates