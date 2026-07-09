import json
from pathlib import Path

from config import APPLE_EXPORT_FOLDER
from database import save_health_measurement
from workout_database import save_training_session_from_apple_workout


METRIC_MAP = {
    "heart_rate_variability": ("apple_hrv_ms", "ms"),
    "resting_heart_rate": ("apple_resting_hr_bpm", "bpm"),
    "respiratory_rate": ("apple_respiratory_rate_bpm", "breaths/min"),
    "vo2_max": ("apple_vo2_max", "ml/kg/min"),
    "active_energy": ("apple_active_energy_kj", "kJ"),
    "apple_exercise_time": ("apple_exercise_minutes", "min"),
    "step_count": ("apple_steps", "steps"),
    "walking_heart_rate_average": ("apple_walking_hr_bpm", "bpm"),
    "walking_running_distance": ("apple_walking_running_distance_km", "km"),
    "blood_oxygen_saturation": ("apple_blood_oxygen_percent", "%"),
    "apple_sleeping_wrist_temperature": ("apple_sleeping_wrist_temperature_c", "degC"),
}


SLEEP_FIELDS = {
    "totalSleep": ("apple_sleep_total_hours", "hr"),
    "deep": ("apple_sleep_deep_hours", "hr"),
    "rem": ("apple_sleep_rem_hours", "hr"),
    "core": ("apple_sleep_core_hours", "hr"),
    "awake": ("apple_sleep_awake_hours", "hr"),
}


def sync_apple_health_json_exports():
    base_folder = Path(APPLE_EXPORT_FOLDER)

    if not base_folder.exists():
        return {
            "imported": 0,
            "duplicates": 0,
            "files_seen": 0,
            "workouts_imported": 0,
            "workouts_duplicates": 0,
            "workout_files_seen": 0,
            "error": f"Apple export folder not found: {base_folder}",
        }

    imported = 0
    duplicates = 0
    files_seen = 0

    health_metrics_folder = base_folder / "Health metrics"

    if health_metrics_folder.exists():
        for json_file in health_metrics_folder.glob("*.json"):
            files_seen += 1
            new_count, duplicate_count = _import_health_metrics_file(json_file)
            imported += new_count
            duplicates += duplicate_count

    workout_summary = sync_apple_workout_exports(base_folder)

    return {
        "imported": imported,
        "duplicates": duplicates,
        "files_seen": files_seen,
        "workouts_imported": workout_summary["imported"],
        "workouts_duplicates": workout_summary["duplicates"],
        "workout_files_seen": workout_summary["files_seen"],
        "error": workout_summary["error"],
    }


def sync_apple_workout_exports(base_folder=None):
    if base_folder is None:
        base_folder = Path(APPLE_EXPORT_FOLDER)

    workouts_folder = base_folder / "Workouts"

    if not workouts_folder.exists():
        return {
            "imported": 0,
            "duplicates": 0,
            "files_seen": 0,
            "error": f"Apple workouts folder not found: {workouts_folder}",
        }

    imported = 0
    duplicates = 0
    files_seen = 0
    errors = []

    for workout_file in workouts_folder.glob("*.json"):
        files_seen += 1

        try:
            workouts = _read_workout_json_file(workout_file)

            for apple_workout in workouts:
                result = save_training_session_from_apple_workout(apple_workout)

                if result["imported"]:
                    imported += 1
                else:
                    duplicates += 1

        except Exception as error:
            errors.append(f"{workout_file.name}: {error}")

    return {
        "imported": imported,
        "duplicates": duplicates,
        "files_seen": files_seen,
        "error": "; ".join(errors) if errors else None,
    }


def _read_workout_json_file(workout_file):
    with open(workout_file, "r", encoding="utf-8") as file:
        export_data = json.load(file)

    return export_data.get("data", {}).get("workouts", [])


def _import_health_metrics_file(json_file):
    imported = 0
    duplicates = 0

    with open(json_file, "r", encoding="utf-8") as file:
        export_data = json.load(file)

    metrics = export_data.get("data", {}).get("metrics", [])

    for metric in metrics:
        metric_name = metric.get("name")

        if metric_name == "sleep_analysis":
            new_count, duplicate_count = _import_sleep_metric(metric)
            imported += new_count
            duplicates += duplicate_count
            continue

        if metric_name not in METRIC_MAP:
            continue

        new_count, duplicate_count = _import_standard_metric(metric)
        imported += new_count
        duplicates += duplicate_count

    return imported, duplicates


def _import_standard_metric(metric):
    metric_name = metric.get("name")
    metric_type, default_unit = METRIC_MAP[metric_name]
    unit = metric.get("units") or default_unit

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
            raw_type=metric_name,
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
                raw_type="sleep_analysis",
                raw_data=json.dumps(item),
            )

            if inserted:
                imported += 1
            else:
                duplicates += 1

    return imported, duplicates