from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from database import (
    load_checkins,
    load_health_measurements,
    load_xert_status_history,
)


# ---------------------------------------------------------------------
# Metric configuration
# ---------------------------------------------------------------------

HEALTH_METRICS = {
    # Body composition
    "weight": {
        "metric_type": "weight_kg",
        "label": "Weight",
        "unit": "kg",
        "group": "body",
        "aggregation": "last",
        "preference": "neutral",
        "decimals": 1,
        "absolute_threshold": 0.3,
        "relative_threshold": 0.003,
        "minimum_readings": 3,
        "expected_frequency": "intermittent",
        "stale_after_days": 7,
    },
    "body_fat": {
        "metric_type": "fat_percent",
        "label": "Body Fat",
        "unit": "%",
        "group": "body",
        "aggregation": "last",
        "preference": "lower",
        "decimals": 1,
        "absolute_threshold": 0.5,
        "relative_threshold": 0.02,
        "minimum_readings": 3,
        "expected_frequency": "intermittent",
        "stale_after_days": 7,
    },
    "fat_mass": {
        "metric_type": "fat_mass_kg",
        "label": "Fat Mass",
        "unit": "kg",
        "group": "body",
        "aggregation": "last",
        "preference": "lower",
        "decimals": 1,
        "absolute_threshold": 0.3,
        "relative_threshold": 0.02,
        "minimum_readings": 3,
        "expected_frequency": "intermittent",
        "stale_after_days": 7,
    },
    "fat_free_mass": {
        "metric_type": "fat_free_mass_kg",
        "label": "Fat-Free Mass",
        "unit": "kg",
        "group": "body",
        "aggregation": "last",
        "preference": "higher",
        "decimals": 1,
        "absolute_threshold": 0.4,
        "relative_threshold": 0.01,
        "minimum_readings": 3,
        "expected_frequency": "intermittent",
        "stale_after_days": 7,
    },
    "muscle_mass": {
        "metric_type": "muscle_mass_kg",
        "label": "Muscle Mass",
        "unit": "kg",
        "group": "body",
        "aggregation": "last",
        "preference": "higher",
        "decimals": 1,
        "absolute_threshold": 0.4,
        "relative_threshold": 0.01,
        "minimum_readings": 3,
        "expected_frequency": "intermittent",
        "stale_after_days": 7,
    },
    "hydration": {
        "metric_type": "hydration_kg",
        "label": "Hydration",
        "unit": "kg",
        "group": "body",
        "aggregation": "last",
        "preference": "neutral",
        "decimals": 1,
        "absolute_threshold": 0.5,
        "relative_threshold": 0.02,
        "minimum_readings": 3,
        "expected_frequency": "intermittent",
        "stale_after_days": 7,
    },
    "bone_mass": {
        "metric_type": "bone_mass_kg",
        "label": "Bone Mass",
        "unit": "kg",
        "group": "body",
        "aggregation": "last",
        "preference": "neutral",
        "decimals": 1,
        "absolute_threshold": 0.1,
        "relative_threshold": 0.02,
        "minimum_readings": 4,
        "expected_frequency": "intermittent",
        "stale_after_days": 14,
    },

    # Cardiovascular and recovery
    "resting_hr": {
        "metric_type": "apple_resting_hr_bpm",
        "label": "Resting Heart Rate",
        "unit": "bpm",
        "group": "cardiovascular",
        "aggregation": "mean",
        "preference": "lower",
        "decimals": 1,
        "absolute_threshold": 2.0,
        "relative_threshold": 0.04,
        "minimum_readings": 5,
        "expected_frequency": "daily",
        "stale_after_days": 3,
    },
    "hrv": {
        "metric_type": "apple_hrv_ms",
        "label": "HRV",
        "unit": "ms",
        "group": "cardiovascular",
        "aggregation": "mean",
        "preference": "higher",
        "decimals": 0,
        "absolute_threshold": 5.0,
        "relative_threshold": 0.07,
        "minimum_readings": 5,
        "expected_frequency": "daily",
        "stale_after_days": 3,
    },
    "walking_hr": {
        "metric_type": "apple_walking_hr_bpm",
        "label": "Walking Heart Rate",
        "unit": "bpm",
        "group": "cardiovascular",
        "aggregation": "mean",
        "preference": "lower",
        "decimals": 1,
        "absolute_threshold": 3.0,
        "relative_threshold": 0.04,
        "minimum_readings": 5,
        "expected_frequency": "daily",
        "stale_after_days": 5,
    },
    "respiratory_rate": {
        "metric_type": [
            "apple_respiratory_rate_bpm",
            "apple_respiratory_rate",
        ],
        "label": "Respiratory Rate",
        "unit": "breaths/min",
        "group": "cardiovascular",
        "aggregation": "mean",
        "preference": "neutral",
        "decimals": 1,
        "absolute_threshold": 1.0,
        "relative_threshold": 0.05,
        "minimum_readings": 5,
        "expected_frequency": "daily",
        "stale_after_days": 3,
    },
    "blood_oxygen": {
        "metric_type": "apple_blood_oxygen_percent",
        "label": "Blood Oxygen",
        "unit": "%",
        "group": "cardiovascular",
        "aggregation": "mean",
        "preference": "higher",
        "decimals": 1,
        "absolute_threshold": 1.0,
        "relative_threshold": 0.01,
        "minimum_readings": 5,
        "expected_frequency": "daily",
        "stale_after_days": 5,
    },

    "wrist_temperature": {
    "metric_type": [
        "apple_sleeping_wrist_temperature_c",
        "wrist_temperature",
    ],
    "label": "Wrist Temperature",
    "unit": "°C",
    "group": "cardiovascular",
    "aggregation": "mean",
    "preference": "neutral",
    "decimals": 2,
    "absolute_threshold": 0.15,
    "relative_threshold": 0.004,
    "minimum_readings": 5,
    "expected_frequency": "daily",
    "stale_after_days": 3,
    },

    "systolic_bp": {
        "metric_type": "systolic_bp",
        "label": "Systolic Blood Pressure",
        "unit": "mmHg",
        "group": "cardiovascular",
        "aggregation": "last",
        "preference": "neutral",
        "decimals": 0,
        "absolute_threshold": 5.0,
        "relative_threshold": 0.04,
        "minimum_readings": 3,
        "expected_frequency": "intermittent",
        "stale_after_days": 14,
    },
    "diastolic_bp": {
        "metric_type": "diastolic_bp",
        "label": "Diastolic Blood Pressure",
        "unit": "mmHg",
        "group": "cardiovascular",
        "aggregation": "last",
        "preference": "neutral",
        "decimals": 0,
        "absolute_threshold": 4.0,
        "relative_threshold": 0.05,
        "minimum_readings": 3,
        "expected_frequency": "intermittent",
        "stale_after_days": 14,
    },
    "pwv": {
        "metric_type": "pulse_wave_velocity",
        "label": "Pulse Wave Velocity",
        "unit": "m/s",
        "group": "cardiovascular",
        "aggregation": "last",
        "preference": "lower",
        "decimals": 2,
        "absolute_threshold": 0.25,
        "relative_threshold": 0.04,
        "minimum_readings": 3,
        "expected_frequency": "intermittent",
        "stale_after_days": 14,
    },

    # Sleep
    "sleep_total": {
        "metric_type": "apple_sleep_total_hours",
        "label": "Total Sleep",
        "unit": "h",
        "group": "sleep",
        "aggregation": "mean",
        "preference": "higher",
        "decimals": 1,
        "absolute_threshold": 0.3,
        "relative_threshold": 0.05,
        "minimum_readings": 5,
        "expected_frequency": "daily",
        "stale_after_days": 3,
    },
    "sleep_deep": {
        "metric_type": "apple_sleep_deep_hours",
        "label": "Deep Sleep",
        "unit": "h",
        "group": "sleep",
        "aggregation": "mean",
        "preference": "higher",
        "decimals": 1,
        "absolute_threshold": 0.2,
        "relative_threshold": 0.12,
        "minimum_readings": 5,
        "expected_frequency": "daily",
        "stale_after_days": 3,
    },
    "sleep_rem": {
        "metric_type": "apple_sleep_rem_hours",
        "label": "REM Sleep",
        "unit": "h",
        "group": "sleep",
        "aggregation": "mean",
        "preference": "higher",
        "decimals": 1,
        "absolute_threshold": 0.2,
        "relative_threshold": 0.10,
        "minimum_readings": 5,
        "expected_frequency": "daily",
        "stale_after_days": 3,
    },
    "sleep_core": {
        "metric_type": "apple_sleep_core_hours",
        "label": "Core Sleep",
        "unit": "h",
        "group": "sleep",
        "aggregation": "mean",
        "preference": "neutral",
        "decimals": 1,
        "absolute_threshold": 0.3,
        "relative_threshold": 0.08,
        "minimum_readings": 5,
        "expected_frequency": "daily",
        "stale_after_days": 3,
    },
    "sleep_awake": {
        "metric_type": "apple_sleep_awake_hours",
        "label": "Awake Time",
        "unit": "h",
        "group": "sleep",
        "aggregation": "mean",
        "preference": "lower",
        "decimals": 1,
        "absolute_threshold": 0.2,
        "relative_threshold": 0.15,
        "minimum_readings": 5,
        "expected_frequency": "daily",
        "stale_after_days": 3,
    },

    # Activity
    "steps": {
        "metric_type": "apple_steps",
        "label": "Steps",
        "unit": "steps",
        "group": "activity",
        "aggregation": "sum",
        "preference": "neutral",
        "decimals": 0,
        "absolute_threshold": 1000.0,
        "relative_threshold": 0.15,
        "minimum_readings": 5,
        "expected_frequency": "daily",
        "stale_after_days": 3,
    },
    "exercise_minutes": {
        "metric_type": "apple_exercise_minutes",
        "label": "Exercise Minutes",
        "unit": "min",
        "group": "activity",
        "aggregation": "sum",
        "preference": "neutral",
        "decimals": 0,
        "absolute_threshold": 10.0,
        "relative_threshold": 0.15,
        "minimum_readings": 5,
        "expected_frequency": "daily",
        "stale_after_days": 3,
    },
    "active_energy": {
        "metric_type": "apple_active_energy_kj",
        "label": "Active Energy",
        "unit": "kJ",
        "group": "activity",
        "aggregation": "sum",
        "preference": "neutral",
        "decimals": 0,
        "absolute_threshold": 300.0,
        "relative_threshold": 0.12,
        "minimum_readings": 5,
        "expected_frequency": "daily",
        "stale_after_days": 3,
    },
    "walking_distance": {
        "metric_type": "apple_walking_running_distance_km",
        "label": "Walking & Running Distance",
        "unit": "km",
        "group": "activity",
        "aggregation": "sum",
        "preference": "neutral",
        "decimals": 1,
        "absolute_threshold": 1.0,
        "relative_threshold": 0.15,
        "minimum_readings": 5,
        "expected_frequency": "daily",
        "stale_after_days": 3,
    },
}


SLEEP_CONSISTENCY_CONFIG = {
    "key": "sleep_consistency",
    "label": "Sleep Consistency",
    "unit": "min variation",
    "group": "sleep",
    "preference": "lower",
    "decimals": 0,
    "absolute_threshold": 10.0,
    "relative_threshold": 0.15,
    "minimum_readings": 5,
    "expected_frequency": "daily",
    "stale_after_days": 3,
}


CHECKIN_METRICS = {
    "lumen_score": {
        "column": "lumen_score",
        "label": "Lumen Score",
        "unit": "",
        "group": "metabolism",
        "preference": "neutral",
        "decimals": 1,
        "absolute_threshold": 0.5,
        "relative_threshold": 0.15,
        "minimum_readings": 4,
        "expected_frequency": "intermittent",
        "stale_after_days": 7,
    },
    "fat_burn_percent": {
        "column": "fat_burn_percent",
        "label": "Fat Burn",
        "unit": "%",
        "group": "metabolism",
        "preference": "higher",
        "decimals": 0,
        "absolute_threshold": 10.0,
        "relative_threshold": 0.15,
        "minimum_readings": 4,
        "expected_frequency": "intermittent",
        "stale_after_days": 7,
    },
    "carb_burn_percent": {
        "column": "carb_burn_percent",
        "label": "Carb Burn",
        "unit": "%",
        "group": "metabolism",
        "preference": "neutral",
        "decimals": 0,
        "absolute_threshold": 10.0,
        "relative_threshold": 0.15,
        "minimum_readings": 4,
        "expected_frequency": "intermittent",
        "stale_after_days": 7,
    },
    "energy": {
        "column": "energy",
        "label": "Energy",
        "unit": "/10",
        "group": "wellbeing",
        "preference": "higher",
        "decimals": 1,
        "absolute_threshold": 0.7,
        "relative_threshold": 0.10,
        "minimum_readings": 4,
        "expected_frequency": "intermittent",
        "stale_after_days": 7,
    },
    "mood": {
        "column": "mood",
        "label": "Mood",
        "unit": "/10",
        "group": "wellbeing",
        "preference": "higher",
        "decimals": 1,
        "absolute_threshold": 0.7,
        "relative_threshold": 0.10,
        "minimum_readings": 4,
        "expected_frequency": "intermittent",
        "stale_after_days": 7,
    },
    "soreness": {
        "column": "soreness",
        "label": "Soreness",
        "unit": "/10",
        "group": "wellbeing",
        "preference": "lower",
        "decimals": 1,
        "absolute_threshold": 0.7,
        "relative_threshold": 0.15,
        "minimum_readings": 4,
        "expected_frequency": "intermittent",
        "stale_after_days": 7,
    },
}


XERT_METRICS = {
    "ftp": {
        "column": "ftp",
        "label": "FTP",
        "unit": "W",
        "group": "performance",
        "preference": "higher",
        "decimals": 0,
        "absolute_threshold": 5.0,
        "relative_threshold": 0.02,
        "minimum_readings": 3,
        "expected_frequency": "intermittent",
        "stale_after_days": 7,
    },
    "ltp": {
        "column": "ltp",
        "label": "Lower Threshold Power",
        "unit": "W",
        "group": "performance",
        "preference": "higher",
        "decimals": 0,
        "absolute_threshold": 5.0,
        "relative_threshold": 0.02,
        "minimum_readings": 3,
        "expected_frequency": "intermittent",
        "stale_after_days": 7,
    },
    "training_load": {
        "column": "tl_total",
        "label": "Xert Training Load",
        "unit": "",
        "group": "performance",
        "preference": "neutral",
        "decimals": 1,
        "absolute_threshold": 3.0,
        "relative_threshold": 0.08,
        "minimum_readings": 3,
        "expected_frequency": "intermittent",
        "stale_after_days": 7,
    },
    "target_xss": {
        "column": "target_xss_total",
        "label": "Target XSS",
        "unit": "XSS",
        "group": "performance",
        "preference": "neutral",
        "decimals": 1,
        "absolute_threshold": 5.0,
        "relative_threshold": 0.10,
        "minimum_readings": 3,
        "expected_frequency": "intermittent",
        "stale_after_days": 7,
    },
}


GROUP_LABELS = {
    "body": "Body Composition",
    "cardiovascular": "Cardiovascular",
    "sleep": "Sleep",
    "metabolism": "Metabolism",
    "activity": "Daily Activity",
    "wellbeing": "Subjective Wellbeing",
    "performance": "Performance Context",
}


# ---------------------------------------------------------------------
# Structured result
# ---------------------------------------------------------------------

@dataclass
class TrendMetric:
    key: str
    label: str
    group: str
    unit: str

    current: Optional[float]
    current_date: Optional[str]

    average_7d: Optional[float]
    average_28d: Optional[float]
    recent_average: Optional[float]
    previous_average: Optional[float]
    period_average: Optional[float]

    baseline_deviation: Optional[float]
    baseline_deviation_percent: Optional[float]

    change: Optional[float]
    change_percent: Optional[float]

    direction: str
    favorable_direction: str

    reading_count: int
    days_covered: int
    latest_age_days: Optional[int]
    is_stale: bool

    expected_frequency: str
    reading_density: float
    coverage_percent: int

    minimum_readings: int
    has_enough_data: bool
    confidence: float

    summary: str
    points: List[Dict[str, Any]]
    smoothed_points: List[Dict[str, Any]]
    decimals: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------

def build_health_trends(
    days: int = 90,
) -> Dict[str, Any]:
    """
    Build historical health trends for the selected period.
    """
    days = _normalise_period(days)

    measurements = _prepare_health_measurements(
        load_health_measurements(),
        days=days,
    )

    checkins = _prepare_checkins(
        load_checkins(),
        days=days,
    )

    xert_history = _prepare_xert_history(
        load_xert_status_history(),
        days=days,
    )

    metrics: Dict[str, Dict[str, Any]] = {}

    for key, config in HEALTH_METRICS.items():
        series = _measurement_daily_series(
            measurements=measurements,
            metric_type=config["metric_type"],
            aggregation=config["aggregation"],
        )

        trend = _build_trend_metric(
            key=key,
            label=config["label"],
            group=config["group"],
            unit=config["unit"],
            series=series,
            preference=config["preference"],
            decimals=config["decimals"],
            days=days,
            absolute_threshold=config["absolute_threshold"],
            relative_threshold=config["relative_threshold"],
            minimum_readings=config["minimum_readings"],
            expected_frequency=config["expected_frequency"],
            stale_after_days=config["stale_after_days"],
        )

        metrics[key] = trend.to_dict()

    sleep_total_series = _measurement_daily_series(
        measurements=measurements,
        metric_type=HEALTH_METRICS["sleep_total"]["metric_type"],
        aggregation=HEALTH_METRICS["sleep_total"]["aggregation"],
    )

    sleep_consistency_series = _build_sleep_consistency_series(
        sleep_total_series
    )

    sleep_consistency_trend = _build_trend_metric(
        key=SLEEP_CONSISTENCY_CONFIG["key"],
        label=SLEEP_CONSISTENCY_CONFIG["label"],
        group=SLEEP_CONSISTENCY_CONFIG["group"],
        unit=SLEEP_CONSISTENCY_CONFIG["unit"],
        series=sleep_consistency_series,
        preference=SLEEP_CONSISTENCY_CONFIG["preference"],
        decimals=SLEEP_CONSISTENCY_CONFIG["decimals"],
        days=days,
        absolute_threshold=(
            SLEEP_CONSISTENCY_CONFIG["absolute_threshold"]
        ),
        relative_threshold=(
            SLEEP_CONSISTENCY_CONFIG["relative_threshold"]
        ),
        minimum_readings=(
            SLEEP_CONSISTENCY_CONFIG["minimum_readings"]
        ),
        expected_frequency=(
            SLEEP_CONSISTENCY_CONFIG["expected_frequency"]
        ),
        stale_after_days=(
            SLEEP_CONSISTENCY_CONFIG["stale_after_days"]
        ),
    )

    metrics["sleep_consistency"] = (
        sleep_consistency_trend.to_dict()
    )

    for key, config in CHECKIN_METRICS.items():
        series = _frame_daily_series(
            frame=checkins,
            date_column="date",
            value_column=config["column"],
            aggregation="last",
        )

        trend = _build_trend_metric(
            key=key,
            label=config["label"],
            group=config["group"],
            unit=config["unit"],
            series=series,
            preference=config["preference"],
            decimals=config["decimals"],
            days=days,
            absolute_threshold=config["absolute_threshold"],
            relative_threshold=config["relative_threshold"],
            minimum_readings=config["minimum_readings"],
            expected_frequency=config["expected_frequency"],
            stale_after_days=config["stale_after_days"],
        )

        metrics[key] = trend.to_dict()

    for key, config in XERT_METRICS.items():
        series = _frame_daily_series(
            frame=xert_history,
            date_column="date",
            value_column=config["column"],
            aggregation="last",
        )

        trend = _build_trend_metric(
            key=key,
            label=config["label"],
            group=config["group"],
            unit=config["unit"],
            series=series,
            preference=config["preference"],
            decimals=config["decimals"],
            days=days,
            absolute_threshold=config["absolute_threshold"],
            relative_threshold=config["relative_threshold"],
            minimum_readings=config["minimum_readings"],
            expected_frequency=config["expected_frequency"],
            stale_after_days=config["stale_after_days"],
        )

        metrics[key] = trend.to_dict()

    groups = _group_metrics(metrics)
    group_summaries = _build_group_summaries(groups)
    overall = _build_overall_summary(groups)

    available_metrics = sum(
        1
        for metric in metrics.values()
        if metric["current"] is not None
    )

    fresh_metrics = sum(
        1
        for metric in metrics.values()
        if (
            metric["current"] is not None
            and not metric["is_stale"]
        )
    )

    sufficiently_populated_metrics = sum(
        1
        for metric in metrics.values()
        if metric["has_enough_data"]
    )

    total_metrics = len(metrics)

    metric_availability_percent = (
        round(
            available_metrics
            / total_metrics
            * 100
        )
        if total_metrics
        else 0
    )

    average_data_coverage_percent = _average_metric_coverage(
        metrics
    )

    return {
        "period_days": days,
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "overall": overall,
        "groups": groups,
        "group_summaries": group_summaries,
        "metrics": metrics,
        "available_metrics": available_metrics,
        "fresh_metrics": fresh_metrics,
        "sufficiently_populated_metrics": sufficiently_populated_metrics,
        "total_metrics": total_metrics,
        "metric_availability_percent": metric_availability_percent,
        "average_data_coverage_percent": average_data_coverage_percent,

        # Compatibility with the original Trends page.
        "coverage_percent": metric_availability_percent,
    }


# ---------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------

def _normalise_period(
    days: Any,
) -> int:
    try:
        parsed = int(days)
    except (TypeError, ValueError):
        return 90

    return max(
        parsed,
        7,
    )


def _parse_measurement_timestamp(
    value: Any,
) -> pd.Timestamp:
    """
    Parse the timestamp formats stored by Phoenix.

    Examples:
        2026-07-13T08:49:00
        2026-07-13 08:49:00 +0200

    Timezone information is removed while preserving the recorded
    local date and time. This allows Apple Health and Withings rows
    to be compared using one consistent timezone-naive series.
    """
    if value is None:
        return pd.NaT

    try:
        parsed = pd.Timestamp(
            value
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return pd.NaT

    if parsed.tzinfo is not None:
        parsed = parsed.tz_localize(
            None
        )

    return parsed


def _prepare_health_measurements(
    frame: pd.DataFrame,
    days: int,
) -> pd.DataFrame:
    columns = [
        "metric_type",
        "value",
        "measured_at",
        "date",
        "source",
        "unit",
    ]

    if frame is None or frame.empty:
        return pd.DataFrame(
            columns=columns
        )

    prepared = frame.copy()

    required_columns = {
        "metric_type",
        "value",
        "measured_at",
    }

    if not required_columns.issubset(
        prepared.columns
    ):
        return pd.DataFrame(
            columns=columns
        )

    prepared["measured_at"] = prepared[
        "measured_at"
    ].apply(
        _parse_measurement_timestamp
    )

    prepared["value"] = pd.to_numeric(
        prepared["value"],
        errors="coerce",
    )

    prepared["metric_type"] = (
        prepared["metric_type"]
        .astype(str)
        .str.strip()
    )

    prepared = prepared.dropna(
        subset=[
            "measured_at",
            "metric_type",
            "value",
        ]
    )

    cutoff = (
        pd.Timestamp.now()
        .normalize()
        - pd.Timedelta(
            days=days - 1
        )
    )

    prepared = prepared[
        prepared["measured_at"]
        >= cutoff
    ].copy()

    prepared["date"] = (
        prepared["measured_at"]
        .dt.normalize()
    )

    return prepared.sort_values(
        "measured_at"
    )


def _prepare_checkins(
    frame: pd.DataFrame,
    days: int,
) -> pd.DataFrame:
    columns = [
        "date",
        *[
            config["column"]
            for config in CHECKIN_METRICS.values()
        ],
    ]

    if (
        frame is None
        or frame.empty
        or "checkin_date" not in frame.columns
    ):
        return pd.DataFrame(
            columns=columns
        )

    prepared = frame.copy()

    prepared["date"] = pd.to_datetime(
        prepared["checkin_date"],
        errors="coerce",
    ).dt.normalize()

    if "timestamp" in prepared.columns:
        prepared["timestamp_parsed"] = pd.to_datetime(
            prepared["timestamp"],
            errors="coerce",
        )
    else:
        prepared["timestamp_parsed"] = pd.NaT

    prepared = prepared.dropna(
        subset=["date"]
    )

    cutoff = (
        pd.Timestamp.now()
        .normalize()
        - pd.Timedelta(
            days=days - 1
        )
    )

    prepared = prepared[
        prepared["date"]
        >= cutoff
    ].copy()

    for config in CHECKIN_METRICS.values():
        column = config["column"]

        if column not in prepared.columns:
            prepared[column] = pd.NA

        prepared[column] = pd.to_numeric(
            prepared[column],
            errors="coerce",
        )

    prepared = prepared.sort_values(
        [
            "date",
            "timestamp_parsed",
        ]
    )

    prepared = prepared.drop_duplicates(
        subset=["date"],
        keep="last",
    )

    return prepared


def _prepare_xert_history(
    frame: pd.DataFrame,
    days: int,
) -> pd.DataFrame:
    columns = [
        "date",
        *[
            config["column"]
            for config in XERT_METRICS.values()
        ],
    ]

    if (
        frame is None
        or frame.empty
        or "fetched_at" not in frame.columns
    ):
        return pd.DataFrame(
            columns=columns
        )

    prepared = frame.copy()

    prepared["fetched_at_parsed"] = pd.to_datetime(
        prepared["fetched_at"],
        errors="coerce",
    )

    prepared["date"] = (
        prepared["fetched_at_parsed"]
        .dt.normalize()
    )

    prepared = prepared.dropna(
        subset=["date"]
    )

    cutoff = (
        pd.Timestamp.now()
        .normalize()
        - pd.Timedelta(
            days=days - 1
        )
    )

    prepared = prepared[
        prepared["date"]
        >= cutoff
    ].copy()

    for config in XERT_METRICS.values():
        column = config["column"]

        if column not in prepared.columns:
            prepared[column] = pd.NA

        prepared[column] = pd.to_numeric(
            prepared[column],
            errors="coerce",
        )

    prepared = prepared.sort_values(
        [
            "date",
            "fetched_at_parsed",
        ]
    )

    prepared = prepared.drop_duplicates(
        subset=["date"],
        keep="last",
    )

    return prepared


# ---------------------------------------------------------------------
# Daily series builders
# ---------------------------------------------------------------------

def _measurement_daily_series(
    measurements: pd.DataFrame,
    metric_type: Any,
    aggregation: str,
) -> pd.Series:
    if measurements is None or measurements.empty:
        return pd.Series(
            dtype="float64"
        )

    if isinstance(
        metric_type,
        (
            list,
            tuple,
            set,
        ),
    ):
        accepted_types = [
            str(value).strip()
            for value in metric_type
        ]

        filtered = measurements[
            measurements["metric_type"].isin(
                accepted_types
            )
        ].copy()

    else:
        expected_type = str(
            metric_type
        ).strip()

        filtered = measurements[
            measurements["metric_type"]
            == expected_type
        ].copy()

    if filtered.empty:
        return pd.Series(
            dtype="float64"
        )

    filtered = filtered.sort_values(
        "measured_at"
    )

    grouped = filtered.groupby(
        "date"
    )["value"]

    if aggregation == "sum":
        series = grouped.sum()

    elif aggregation == "mean":
        series = grouped.mean()

    elif aggregation == "min":
        series = grouped.min()

    elif aggregation == "max":
        series = grouped.max()

    else:
        series = grouped.last()

    return _clean_series(
        series
    )


def _frame_daily_series(
    frame: pd.DataFrame,
    date_column: str,
    value_column: str,
    aggregation: str = "last",
) -> pd.Series:
    if (
        frame is None
        or frame.empty
        or date_column not in frame.columns
        or value_column not in frame.columns
    ):
        return pd.Series(
            dtype="float64"
        )

    working = frame[
        [
            date_column,
            value_column,
        ]
    ].copy()

    working[value_column] = pd.to_numeric(
        working[value_column],
        errors="coerce",
    )

    working = working.dropna(
        subset=[
            date_column,
            value_column,
        ]
    )

    if working.empty:
        return pd.Series(
            dtype="float64"
        )

    grouped = working.groupby(
        date_column
    )[value_column]

    if aggregation == "sum":
        series = grouped.sum()

    elif aggregation == "mean":
        series = grouped.mean()

    else:
        series = grouped.last()

    return _clean_series(
        series
    )


def _clean_series(
    series: pd.Series,
) -> pd.Series:
    if series is None or series.empty:
        return pd.Series(
            dtype="float64"
        )

    cleaned = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()

    cleaned.index = pd.to_datetime(
        cleaned.index,
        errors="coerce",
    )

    cleaned = cleaned[
        ~cleaned.index.isna()
    ]

    cleaned = cleaned[
        ~cleaned.index.duplicated(
            keep="last"
        )
    ]

    return cleaned.sort_index()


def _build_sleep_consistency_series(
    sleep_series: pd.Series,
) -> pd.Series:
    """
    Convert daily sleep duration into rolling seven-day variability.

    The result is the standard deviation of sleep duration over the
    latest seven-day window, expressed in minutes.

    Lower values indicate more consistent sleep duration.
    """
    if sleep_series is None or sleep_series.empty:
        return pd.Series(
            dtype="float64"
        )

    cleaned = _clean_series(
        sleep_series
    )

    if cleaned.empty:
        return pd.Series(
            dtype="float64"
        )

    complete_index = pd.date_range(
        start=cleaned.index.min().normalize(),
        end=cleaned.index.max().normalize(),
        freq="D",
    )

    daily = cleaned.reindex(
        complete_index
    )

    rolling_variation_hours = daily.rolling(
        window=7,
        min_periods=3,
    ).std()

    rolling_variation_minutes = (
        rolling_variation_hours
        * 60
    )

    rolling_variation_minutes = (
        rolling_variation_minutes
        .dropna()
    )

    return _clean_series(
        rolling_variation_minutes
    )


# ---------------------------------------------------------------------
# Trend calculation
# ---------------------------------------------------------------------

def _build_trend_metric(
    key: str,
    label: str,
    group: str,
    unit: str,
    series: pd.Series,
    preference: str,
    decimals: int,
    days: int,
    absolute_threshold: float,
    relative_threshold: float,
    minimum_readings: int,
    expected_frequency: str,
    stale_after_days: int,
) -> TrendMetric:
    if series is None or series.empty:
        return _empty_trend_metric(
            key=key,
            label=label,
            group=group,
            unit=unit,
            decimals=decimals,
            minimum_readings=minimum_readings,
            expected_frequency=expected_frequency,
        )

    current = float(
        series.iloc[-1]
    )

    current_timestamp = (
        series.index[-1]
        .normalize()
    )

    current_date = (
        current_timestamp
        .date()
        .isoformat()
    )

    today = (
        pd.Timestamp.now()
        .normalize()
    )

    latest_age_days = max(
        int(
            (
                today
                - current_timestamp
            ).days
        ),
        0,
    )

    is_stale = (
        latest_age_days
        > stale_after_days
    )

    period_average = float(
        series.mean()
    )

    average_7d = _window_average(
        series=series,
        window_days=7,
    )

    average_28d = _window_average(
        series=series,
        window_days=28,
    )

    recent_average, previous_average = (
        _comparison_averages(
            series
        )
    )

    baseline_average = _baseline_average(
        series
    )

    baseline_deviation = None
    baseline_deviation_percent = None

    if baseline_average is not None:
        comparison_value = (
            average_7d
            if average_7d is not None
            else current
        )

        baseline_deviation = (
            comparison_value
            - baseline_average
        )

        if baseline_average != 0:
            baseline_deviation_percent = (
                baseline_deviation
                / abs(baseline_average)
                * 100
            )

    change, change_percent = _calculate_change(
        series=series,
        recent_average=recent_average,
        previous_average=previous_average,
    )

    reading_count = int(
        series.count()
    )

    has_enough_data = (
        reading_count
        >= minimum_readings
    )

    direction = _classify_direction(
        change=change,
        reference=previous_average,
        absolute_threshold=absolute_threshold,
        relative_threshold=relative_threshold,
        has_enough_data=has_enough_data,
    )

    favorable_direction = (
        _classify_favorable_direction(
            direction=direction,
            preference=preference,
        )
    )

    days_covered = (
        int(
            (
                series.index[-1].normalize()
                - series.index[0].normalize()
            ).days
        )
        + 1
    )

    reading_density = _reading_density(
        reading_count=reading_count,
        days=days,
        expected_frequency=expected_frequency,
    )

    coverage_percent = int(
        round(
            reading_density
            * 100
        )
    )

    confidence = _trend_confidence(
        reading_count=reading_count,
        days_covered=days_covered,
        requested_days=days,
        reading_density=reading_density,
        has_enough_data=has_enough_data,
        is_stale=is_stale,
        expected_frequency=expected_frequency,
    )

    summary = _build_metric_summary(
        label=label,
        unit=unit,
        current=current,
        average_7d=average_7d,
        average_28d=average_28d,
        change=change,
        direction=direction,
        favorable_direction=favorable_direction,
        decimals=decimals,
        reading_count=reading_count,
        minimum_readings=minimum_readings,
        latest_age_days=latest_age_days,
        is_stale=is_stale,
    )

    points = _series_to_points(
        series
    )

    smoothed_points = _smoothed_points(
        series
    )

    return TrendMetric(
        key=key,
        label=label,
        group=group,
        unit=unit,
        current=current,
        current_date=current_date,
        average_7d=average_7d,
        average_28d=average_28d,
        recent_average=recent_average,
        previous_average=previous_average,
        period_average=period_average,
        baseline_deviation=baseline_deviation,
        baseline_deviation_percent=baseline_deviation_percent,
        change=change,
        change_percent=change_percent,
        direction=direction,
        favorable_direction=favorable_direction,
        reading_count=reading_count,
        days_covered=days_covered,
        latest_age_days=latest_age_days,
        is_stale=is_stale,
        expected_frequency=expected_frequency,
        reading_density=reading_density,
        coverage_percent=coverage_percent,
        minimum_readings=minimum_readings,
        has_enough_data=has_enough_data,
        confidence=confidence,
        summary=summary,
        points=points,
        smoothed_points=smoothed_points,
        decimals=decimals,
    )


def _empty_trend_metric(
    key: str,
    label: str,
    group: str,
    unit: str,
    decimals: int,
    minimum_readings: int,
    expected_frequency: str,
) -> TrendMetric:
    return TrendMetric(
        key=key,
        label=label,
        group=group,
        unit=unit,
        current=None,
        current_date=None,
        average_7d=None,
        average_28d=None,
        recent_average=None,
        previous_average=None,
        period_average=None,
        baseline_deviation=None,
        baseline_deviation_percent=None,
        change=None,
        change_percent=None,
        direction="no_data",
        favorable_direction="unknown",
        reading_count=0,
        days_covered=0,
        latest_age_days=None,
        is_stale=False,
        expected_frequency=expected_frequency,
        reading_density=0.0,
        coverage_percent=0,
        minimum_readings=minimum_readings,
        has_enough_data=False,
        confidence=0.0,
        summary=(
            f"No {label.lower()} history is available yet."
        ),
        points=[],
        smoothed_points=[],
        decimals=decimals,
    )


def _window_average(
    series: pd.Series,
    window_days: int,
) -> Optional[float]:
    if series is None or series.empty:
        return None

    latest_date = (
        series.index.max()
        .normalize()
    )

    start_date = (
        latest_date
        - pd.Timedelta(
            days=window_days - 1
        )
    )

    normalized_index = (
        series.index.normalize()
    )

    window = series[
        normalized_index
        >= start_date
    ]

    if window.empty:
        return None

    return float(
        window.mean()
    )


def _comparison_averages(
    series: pd.Series,
) -> tuple[
    Optional[float],
    Optional[float],
]:
    if series is None or series.empty:
        return None, None

    latest_date = (
        series.index.max()
        .normalize()
    )

    recent_start = (
        latest_date
        - pd.Timedelta(days=6)
    )

    previous_start = (
        latest_date
        - pd.Timedelta(days=13)
    )

    previous_end = (
        latest_date
        - pd.Timedelta(days=7)
    )

    normalized_index = (
        series.index.normalize()
    )

    recent = series[
        normalized_index
        >= recent_start
    ]

    previous = series[
        (
            normalized_index
            >= previous_start
        )
        & (
            normalized_index
            <= previous_end
        )
    ]

    recent_average = (
        float(recent.mean())
        if not recent.empty
        else None
    )

    previous_average = (
        float(previous.mean())
        if not previous.empty
        else None
    )

    return (
        recent_average,
        previous_average,
    )


def _baseline_average(
    series: pd.Series,
) -> Optional[float]:
    """
    Build a longer personal baseline.

    Phoenix first uses the 28 days immediately before the latest
    seven-day window. When that is unavailable, it uses any older
    readings before the latest seven days.
    """
    if series is None or series.empty:
        return None

    latest_date = (
        series.index.max()
        .normalize()
    )

    baseline_end = (
        latest_date
        - pd.Timedelta(days=7)
    )

    baseline_start = (
        latest_date
        - pd.Timedelta(days=34)
    )

    normalized_index = (
        series.index.normalize()
    )

    baseline = series[
        (
            normalized_index
            >= baseline_start
        )
        & (
            normalized_index
            <= baseline_end
        )
    ]

    if not baseline.empty:
        return float(
            baseline.mean()
        )

    fallback = series[
        normalized_index
        <= baseline_end
    ]

    if fallback.empty:
        return None

    return float(
        fallback.mean()
    )


def _calculate_change(
    series: pd.Series,
    recent_average: Optional[float],
    previous_average: Optional[float],
) -> tuple[
    Optional[float],
    Optional[float],
]:
    change = None
    change_percent = None

    if (
        recent_average is not None
        and previous_average is not None
    ):
        change = (
            recent_average
            - previous_average
        )

        if previous_average != 0:
            change_percent = (
                change
                / abs(previous_average)
                * 100
            )

    elif len(series) >= 2:
        oldest = float(
            series.iloc[0]
        )

        current = float(
            series.iloc[-1]
        )

        change = (
            current
            - oldest
        )

        if oldest != 0:
            change_percent = (
                change
                / abs(oldest)
                * 100
            )

    return (
        change,
        change_percent,
    )


def _classify_direction(
    change: Optional[float],
    reference: Optional[float],
    absolute_threshold: float,
    relative_threshold: float,
    has_enough_data: bool,
) -> str:
    if change is None:
        return "insufficient_data"

    if not has_enough_data:
        return "insufficient_data"

    absolute_change = abs(
        change
    )

    reference_value = abs(
        reference or 0.0
    )

    relative_change = (
        absolute_change
        / reference_value
        if reference_value > 0
        else 0.0
    )

    absolute_is_meaningful = (
        absolute_change
        >= absolute_threshold
    )

    relative_is_meaningful = (
        relative_change
        >= relative_threshold
    )

    if not (
        absolute_is_meaningful
        and relative_is_meaningful
    ):
        return "stable"

    if change > 0:
        return "increasing"

    if change < 0:
        return "decreasing"

    return "stable"


def _classify_favorable_direction(
    direction: str,
    preference: str,
) -> str:
    if direction in {
        "no_data",
        "insufficient_data",
    }:
        return "unknown"

    if direction == "stable":
        return "stable"

    if preference == "neutral":
        return "contextual"

    if preference == "higher":
        return (
            "improving"
            if direction == "increasing"
            else "worsening"
        )

    if preference == "lower":
        return (
            "improving"
            if direction == "decreasing"
            else "worsening"
        )

    return "contextual"


def _reading_density(
    reading_count: int,
    days: int,
    expected_frequency: str,
) -> float:
    if reading_count <= 0:
        return 0.0

    if expected_frequency == "daily":
        expected_readings = max(
            days,
            1,
        )

    else:
        expected_readings = max(
            round(
                days
                * 2
                / 7
            ),
            1,
        )

    return min(
        reading_count
        / expected_readings,
        1.0,
    )


def _trend_confidence(
    reading_count: int,
    days_covered: int,
    requested_days: int,
    reading_density: float,
    has_enough_data: bool,
    is_stale: bool,
    expected_frequency: str,
) -> float:
    if reading_count <= 0:
        return 0.0

    score = 0.20

    if reading_count >= 2:
        score += 0.10

    if reading_count >= 5:
        score += 0.15

    if reading_count >= 10:
        score += 0.15

    if reading_count >= 20:
        score += 0.10

    period_span_ratio = min(
        days_covered
        / max(
            requested_days,
            1,
        ),
        1.0,
    )

    score += (
        period_span_ratio
        * 0.10
    )

    score += (
        reading_density
        * 0.20
    )

    if not has_enough_data:
        score = min(
            score,
            0.49,
        )

    if is_stale:
        score -= (
            0.15
            if expected_frequency == "daily"
            else 0.10
        )

    return min(
        max(
            round(
                score,
                2,
            ),
            0.0,
        ),
        0.95,
    )


def _series_to_points(
    series: pd.Series,
) -> List[Dict[str, Any]]:
    return [
        {
            "date": index.date().isoformat(),
            "value": float(value),
        }
        for index, value in series.items()
    ]


def _smoothed_points(
    series: pd.Series,
) -> List[Dict[str, Any]]:
    if series is None or series.empty:
        return []

    if len(series) < 3:
        return _series_to_points(
            series
        )

    complete_index = pd.date_range(
        start=series.index.min().normalize(),
        end=series.index.max().normalize(),
        freq="D",
    )

    daily = series.reindex(
        complete_index
    )

    smoothed = daily.rolling(
        window=7,
        min_periods=1,
    ).mean()

    smoothed = smoothed.dropna()

    return [
        {
            "date": index.date().isoformat(),
            "value": float(value),
        }
        for index, value in smoothed.items()
    ]


# ---------------------------------------------------------------------
# Human-readable interpretation
# ---------------------------------------------------------------------

def _build_metric_summary(
    label: str,
    unit: str,
    current: float,
    average_7d: Optional[float],
    average_28d: Optional[float],
    change: Optional[float],
    direction: str,
    favorable_direction: str,
    decimals: int,
    reading_count: int,
    minimum_readings: int,
    latest_age_days: int,
    is_stale: bool,
) -> str:
    current_text = _format_value(
        current,
        unit,
        decimals,
    )

    if reading_count == 1:
        return (
            f"The latest {label.lower()} reading is "
            f"{current_text}. More history is needed before "
            "Phoenix can judge the trend."
        )

    if reading_count < minimum_readings:
        return (
            f"The latest {label.lower()} reading is "
            f"{current_text}. Phoenix has {reading_count} daily "
            f"reading(s), but needs at least {minimum_readings} "
            "before assigning a trend direction."
        )

    freshness_sentence = ""

    if is_stale:
        freshness_sentence = (
            f" The latest reading is {latest_age_days} days old, "
            "so this trend may not reflect your current state."
        )

    average_sentence = ""

    if (
        average_7d is not None
        and average_28d is not None
    ):
        seven_day_text = _format_value(
            average_7d,
            unit,
            decimals,
        )

        twenty_eight_day_text = _format_value(
            average_28d,
            unit,
            decimals,
        )

        average_sentence = (
            f" The seven-day average is {seven_day_text}, "
            f"compared with {twenty_eight_day_text} over 28 days."
        )

    if direction == "stable":
        return (
            f"{label} is broadly stable. The latest value is "
            f"{current_text}.{average_sentence}{freshness_sentence}"
        ).strip()

    if direction == "insufficient_data":
        return (
            f"The latest {label.lower()} reading is "
            f"{current_text}, but Phoenix does not yet have enough "
            f"comparable history to judge the direction."
            f"{freshness_sentence}"
        ).strip()

    if change is None:
        return (
            f"The latest {label.lower()} reading is "
            f"{current_text}. A reliable change could not yet be "
            f"calculated.{freshness_sentence}"
        ).strip()

    change_text = _format_value(
        abs(change),
        unit,
        decimals,
    )

    if direction == "increasing":
        movement_text = (
            f"increased by approximately {change_text}"
        )
    else:
        movement_text = (
            f"decreased by approximately {change_text}"
        )

    if favorable_direction == "improving":
        meaning = (
            "This is moving in a favourable direction."
        )

    elif favorable_direction == "worsening":
        meaning = (
            "This is moving in a less favourable direction, "
            "although it should be interpreted alongside recovery, "
            "training and health context."
        )

    elif favorable_direction == "contextual":
        meaning = (
            "The meaning depends on your wider health, recovery "
            "and training context."
        )

    else:
        meaning = ""

    return (
        f"{label} has {movement_text}. "
        f"The latest value is {current_text}. "
        f"{meaning}"
        f"{average_sentence}"
        f"{freshness_sentence}"
    ).strip()


def _format_number(
    value: float,
    decimals: int,
) -> str:
    if decimals <= 0:
        return f"{value:.0f}"

    return f"{value:.{decimals}f}"


def _format_value(
    value: float,
    unit: str,
    decimals: int,
) -> str:
    number = _format_number(
        value,
        decimals,
    )

    clean_unit = str(
        unit or ""
    ).strip()

    if not clean_unit:
        return number

    if clean_unit.startswith("/"):
        return f"{number}{clean_unit}"

    return f"{number} {clean_unit}"


# ---------------------------------------------------------------------
# Grouping and summaries
# ---------------------------------------------------------------------

def _group_metrics(
    metrics: Dict[str, Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    groups = {
        group_key: []
        for group_key in GROUP_LABELS
    }

    for metric in metrics.values():
        group = metric["group"]

        if group not in groups:
            groups[group] = []

        groups[group].append(
            metric
        )

    return groups


def _build_group_summaries(
    groups: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Dict[str, Any]]:
    summaries = {}

    for group_key, metrics in groups.items():
        available = [
            metric
            for metric in metrics
            if metric["current"] is not None
        ]

        fresh = [
            metric
            for metric in available
            if not metric["is_stale"]
        ]

        adequately_populated = [
            metric
            for metric in available
            if metric["has_enough_data"]
        ]

        improving = [
            metric
            for metric in adequately_populated
            if metric["favorable_direction"]
            == "improving"
        ]

        worsening = [
            metric
            for metric in adequately_populated
            if metric["favorable_direction"]
            == "worsening"
        ]

        stable = [
            metric
            for metric in adequately_populated
            if metric["favorable_direction"]
            == "stable"
        ]

        contextual = [
            metric
            for metric in adequately_populated
            if metric["favorable_direction"]
            == "contextual"
        ]

        group_label = GROUP_LABELS.get(
            group_key,
            group_key.replace(
                "_",
                " ",
            ).title(),
        )

        stale_count = (
            len(available)
            - len(fresh)
        )

        if not available:
            status = "no_data"
            summary = (
                f"No {group_label.lower()} history is available "
                "for this period."
            )

        elif not adequately_populated:
            status = "contextual"
            summary = (
                f"{group_label} data is available, but more readings "
                "are needed before Phoenix can judge the direction."
            )

        elif worsening and improving:
            status = "mixed"
            summary = (
                f"{group_label} trends are mixed: "
                f"{len(improving)} improving and "
                f"{len(worsening)} moving less favourably."
            )

        elif worsening:
            status = "needs_attention"
            summary = (
                f"{len(worsening)} {group_label.lower()} trend(s) "
                "are moving in a less favourable direction."
            )

        elif improving:
            status = "improving"
            summary = (
                f"{len(improving)} {group_label.lower()} trend(s) "
                "are moving favourably."
            )

        elif stable:
            status = "stable"
            summary = (
                f"{group_label} looks broadly stable."
            )

        else:
            status = "contextual"
            summary = (
                f"{group_label} data is available, but its "
                "direction needs wider context."
            )

        if stale_count:
            summary += (
                f" {stale_count} metric(s) may be out of date."
            )

        summaries[group_key] = {
            "label": group_label,
            "status": status,
            "summary": summary,
            "available_count": len(available),
            "fresh_count": len(fresh),
            "stale_count": stale_count,
            "adequately_populated_count": len(
                adequately_populated
            ),
            "improving_count": len(improving),
            "worsening_count": len(worsening),
            "stable_count": len(stable),
            "contextual_count": len(contextual),
        }

    return summaries


def _build_overall_summary(
    groups: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    health_group_keys = {
        "body",
        "cardiovascular",
        "sleep",
        "metabolism",
        "wellbeing",
    }

    health_metrics: List[
        Dict[str, Any]
    ] = []

    for group_key in health_group_keys:
        health_metrics.extend(
            groups.get(
                group_key,
                [],
            )
        )

    available = [
        metric
        for metric in health_metrics
        if metric["current"] is not None
    ]

    sufficiently_populated = [
        metric
        for metric in available
        if metric["has_enough_data"]
    ]

    fresh = [
        metric
        for metric in available
        if not metric["is_stale"]
    ]

    improving = [
        metric
        for metric in sufficiently_populated
        if metric["favorable_direction"]
        == "improving"
    ]

    worsening = [
        metric
        for metric in sufficiently_populated
        if metric["favorable_direction"]
        == "worsening"
    ]

    stable = [
        metric
        for metric in sufficiently_populated
        if metric["favorable_direction"]
        == "stable"
    ]

    contextual = [
        metric
        for metric in sufficiently_populated
        if metric["favorable_direction"]
        == "contextual"
    ]

    stale_count = (
        len(available)
        - len(fresh)
    )

    if not available:
        return {
            "status": "no_data",
            "headline": "Not enough health history yet",
            "summary": (
                "Phoenix needs more historical measurements before "
                "it can describe your overall health direction."
            ),
            "improving_count": 0,
            "worsening_count": 0,
            "stable_count": 0,
            "contextual_count": 0,
            "available_count": 0,
            "fresh_count": 0,
            "stale_count": 0,
            "sufficiently_populated_count": 0,
        }

    if not sufficiently_populated:
        status = "contextual"
        headline = "Health history is building"
        summary = (
            "Phoenix has health measurements, but more repeated "
            "readings are needed before it can judge the overall "
            "direction reliably."
        )

    elif worsening and improving:
        status = "mixed"
        headline = "Health trends are mixed"
        summary = (
            f"{len(improving)} tracked health metric(s) are moving "
            f"favourably, while {len(worsening)} are moving less "
            "favourably."
        )

    elif worsening:
        status = "needs_attention"
        headline = "Some health trends need attention"
        summary = (
            f"{len(worsening)} tracked health metric(s) are moving "
            "in a less favourable direction. Phoenix should interpret "
            "these alongside recovery, training load and recent health "
            "events rather than as isolated warnings."
        )

    elif improving:
        status = "improving"
        headline = "Health direction is improving"
        summary = (
            f"{len(improving)} tracked health metric(s) are moving "
            "in a favourable direction."
        )

    elif stable:
        status = "stable"
        headline = "Health trends look stable"
        summary = (
            "The available health metrics are broadly stable over "
            "the selected period."
        )

    else:
        status = "contextual"
        headline = "Health history is available"
        summary = (
            "Phoenix has historical health data, but the current "
            "direction depends on wider context."
        )

    if stale_count:
        summary += (
            f" {stale_count} available health metric(s) may be "
            "out of date."
        )

    return {
        "status": status,
        "headline": headline,
        "summary": summary,
        "improving_count": len(improving),
        "worsening_count": len(worsening),
        "stable_count": len(stable),
        "contextual_count": len(contextual),
        "available_count": len(available),
        "fresh_count": len(fresh),
        "stale_count": stale_count,
        "sufficiently_populated_count": len(
            sufficiently_populated
        ),
    }


def _average_metric_coverage(
    metrics: Dict[str, Dict[str, Any]],
) -> int:
    available = [
        metric
        for metric in metrics.values()
        if metric["current"] is not None
    ]

    if not available:
        return 0

    coverage_values = [
        int(
            metric.get(
                "coverage_percent",
                0,
            )
        )
        for metric in available
    ]

    return int(
        round(
            sum(coverage_values)
            / len(coverage_values)
        )
    )