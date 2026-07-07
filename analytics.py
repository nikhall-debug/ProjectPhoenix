from datetime import datetime, timedelta

from database import load_health_measurements


def get_metric_summary(source, metric_type):
    df = load_health_measurements()

    if df.empty:
        return None

    df = df[
        (df["source"] == source) &
        (df["metric_type"] == metric_type)
    ].copy()

    if df.empty:
        return None

    df["measured_at"] = df["measured_at"].apply(datetime.fromisoformat)
    df = df.sort_values("measured_at", ascending=False)

    latest = df.iloc[0]
    latest_value = latest["value"]
    latest_time = latest["measured_at"]

    def nearest_delta(days):
        target_time = latest_time - timedelta(days=days)
        older = df[df["measured_at"] <= target_time]

        if older.empty:
            return None

        comparison = older.iloc[0]
        return latest_value - comparison["value"]

    return {
        "current": latest_value,
        "unit": latest["unit"],
        "measured_at": latest_time,
        "delta_1d": nearest_delta(1),
        "delta_7d": nearest_delta(7),
        "delta_30d": nearest_delta(30),
    }


def weight_summary():
    return get_metric_summary("withings", "weight_kg")


def body_fat_summary():
    return get_metric_summary("withings", "fat_percent")


def muscle_summary():
    return get_metric_summary("withings", "muscle_mass_kg")


def pwv_summary():
    return get_metric_summary("withings", "pulse_wave_velocity")