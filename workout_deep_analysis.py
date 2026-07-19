from __future__ import annotations

import io
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from timeline_normalizer import normalize_timeline


@dataclass
class ParsedFit:
    filename: str
    start: Optional[datetime]
    end: Optional[datetime]
    duration_seconds: Optional[float]
    device_name: Optional[str]
    metrics: List[str]
    records: pd.DataFrame
    raw_fields: List[str]


FIT_FIELD_ALIASES = {
    "timestamp": "timestamp",
    "heart_rate": "heart_rate",
    "enhanced_speed": "speed_mps",
    "speed": "speed_mps",
    "cadence": "cadence",
    "power": "power",
    "altitude": "altitude_m",
    "enhanced_altitude": "altitude_m",
    "temperature": "temperature_c",
    "core_temperature": "core_temperature_c",
    "core_temp": "core_temperature_c",
    "skin_temperature": "skin_temperature_c",
    "respiration_rate": "breathing_rate",
    "breathing_rate": "breathing_rate",
    "breath_rate": "breathing_rate",
    "tyme_breath_rate": "breathing_rate",
    "minute_ventilation": "minute_ventilation",
    "minute_volume": "minute_ventilation",
    "tyme_minute_volume": "minute_ventilation",
    "tidal_volume": "tidal_volume",
    "tyme_tidal_volume": "tidal_volume",
    "tyme_heart_rate": "heart_rate",
    "tyme_power": "power",
    "tyme_cadence": "cadence",
    "tyme_bike_cadence": "cadence",
    "tyme_gps_speed": "speed_mps",
    "tyme_elevation": "altitude_m",
}


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        return pd.to_datetime(value).to_pydatetime()
    except Exception:
        return None


def _normalise_field(name: Any) -> str:
    return str(name).strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_")


def parse_fit_file(file_bytes: bytes, filename: str) -> ParsedFit:
    try:
        import fitdecode
    except ImportError as exc:
        raise RuntimeError("Install FIT support with: pip install fitdecode") from exc

    records = []
    raw_fields = set()
    device_name = None

    with fitdecode.FitReader(io.BytesIO(file_bytes)) as fit:
        for frame in fit:
            if not isinstance(frame, fitdecode.FitDataMessage):
                continue

            message_name = str(frame.name or "").lower()

            if message_name in {"device_info", "file_id"}:
                for field in frame.fields:
                    if field.name in {"product_name", "manufacturer", "product"} and field.value:
                        device_name = str(field.value)

            if message_name != "record":
                continue

            row: Dict[str, Any] = {}
            for field in frame.fields:
                raw_name = _normalise_field(field.name or field.def_num)
                raw_fields.add(raw_name)
                canonical = FIT_FIELD_ALIASES.get(raw_name, raw_name)
                value = field.value

                if value is None:
                    continue
                if canonical == "timestamp":
                    row["timestamp"] = parse_datetime(value)
                elif isinstance(value, (int, float)):
                    row[canonical] = float(value)

            if row.get("timestamp") is not None:
                records.append(row)

    df = pd.DataFrame(records)
    if df.empty:
        return ParsedFit(filename, None, None, None, device_name, [], df, sorted(raw_fields))

    if "speed_mps" in df:
        df["speed_kmh"] = pd.to_numeric(df["speed_mps"], errors="coerce") * 3.6

    df = normalize_timeline(df)
    start = parse_datetime(df["timestamp"].iloc[0])
    end = parse_datetime(df["timestamp"].iloc[-1])

    metrics = [
        c for c in df.columns
        if c != "timestamp"
        and pd.api.types.is_numeric_dtype(df[c])
        and df[c].notna().any()
    ]

    duration = (end - start).total_seconds() if start and end else None
    return ParsedFit(
        filename=filename,
        start=start,
        end=end,
        duration_seconds=duration,
        device_name=device_name,
        metrics=sorted(metrics),
        records=df.reset_index(drop=True),
        raw_fields=sorted(raw_fields),
    )


def apple_timeline_from_raw(
    apple_raw_data: Optional[str],
    start_time: str,
    end_time: str,
) -> pd.DataFrame:
    if not apple_raw_data:
        return pd.DataFrame()

    workout = json.loads(apple_raw_data)
    frames: List[pd.DataFrame] = []

    def add_series(key: str, output_name: str, multiplier: float = 1.0):
        rows = workout.get(key)
        if not isinstance(rows, list):
            return
        output = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            ts = parse_datetime(row.get("date") or row.get("timestamp"))
            try:
                value = float(row.get("qty")) * multiplier
            except (TypeError, ValueError):
                continue
            if ts is not None:
                output.append({"timestamp": ts, output_name: value})
        if output:
            frames.append(pd.DataFrame(output).sort_values("timestamp"))

    add_series("walkingAndRunningDistance", "speed_kmh", 60.0)
    add_series("distanceWalkingRunning", "speed_kmh", 60.0)
    add_series("heartRate", "heart_rate")
    add_series("averageHeartRate", "heart_rate")
    add_series("stepCount", "steps_per_minute")

    route = workout.get("route")
    if isinstance(route, list):
        rows = []
        for item in route:
            if not isinstance(item, dict):
                continue
            ts = parse_datetime(item.get("timestamp"))
            if ts is None:
                continue
            row = {"timestamp": ts}
            for source, target, multiplier in (
                ("speed", "route_speed_kmh", 3.6),
                ("altitude", "altitude_m", 1.0),
            ):
                try:
                    row[target] = float(item[source]) * multiplier
                except (KeyError, TypeError, ValueError):
                    pass
            rows.append(row)
        if rows:
            frames.append(pd.DataFrame(rows).sort_values("timestamp"))

    if not frames:
        return pd.DataFrame()

    timeline = normalize_timeline(frames[0])
    for frame in frames[1:]:
        frame = normalize_timeline(frame)
        timeline = pd.merge_asof(
            timeline,
            frame,
            on="timestamp",
            direction="nearest",
            tolerance=pd.Timedelta(seconds=35),
        )

    start = pd.to_datetime(start_time, utc=True, errors="coerce")
    end = pd.to_datetime(end_time, utc=True, errors="coerce")
    if not pd.isna(start) and not pd.isna(end):
        timeline = timeline[
            (timeline["timestamp"] >= start - pd.Timedelta(seconds=30))
            & (timeline["timestamp"] <= end + pd.Timedelta(seconds=30))
        ]

    return normalize_timeline(timeline)



def _walk_json(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _numeric_series(value: Any) -> Optional[list]:
    if not isinstance(value, list) or not value:
        return None
    if all(item is None or isinstance(item, (int, float)) for item in value):
        return value
    return None


def _choose_speed_kmh(raw_values: pd.Series) -> pd.Series:
    """Infer Xert speed units and return a plausible km/h series.

    Xert exports seen in the wild may use m/s, km/h, cm/s, or metres/hour.
    We score each interpretation against a realistic cycling distribution
    rather than hard-coding one API layout.
    """
    raw = pd.to_numeric(raw_values, errors="coerce")
    positive = raw[(raw >= 0) & raw.notna()]
    if positive.empty:
        return raw

    candidates = {
        "kmh": raw,
        "mps": raw * 3.6,
        "cmps": raw * 0.036,
        "metres_per_hour": raw / 1000.0,
    }

    def score(series: pd.Series) -> float:
        values = series[(series >= 0) & series.notna()]
        if values.empty:
            return float("inf")
        median = float(values.median())
        p95 = float(values.quantile(0.95))
        # Indoor/outdoor cycling usually centres around 15–45 km/h.
        score_value = abs(median - 27.0)
        if median < 3:
            score_value += 50
        if median > 65:
            score_value += (median - 65) * 4
        if p95 > 130:
            score_value += (p95 - 130) * 8
        return score_value

    best = min(candidates.values(), key=score)
    return best.where((best >= 0) & (best <= 150))


def _clean_physiology(frame: pd.DataFrame) -> pd.DataFrame:
    """Remove impossible sensor values without smoothing genuine variation."""
    frame = frame.copy()
    bounds = {
        "heart_rate": (25, 240),
        "power": (0, 2500),
        "cadence": (0, 250),
        "speed_kmh": (0, 150),
        "breathing_rate": (1, 120),
        "minute_ventilation": (0, 300),
        "tidal_volume": (0, 10),
        "core_temperature_c": (30, 43),
        "skin_temperature_c": (5, 45),
    }
    for column, (low, high) in bounds.items():
        if column in frame:
            values = pd.to_numeric(frame[column], errors="coerce")
            frame[column] = values.where(values.between(low, high))
    return frame


def xert_timeline_from_raw(xert_raw_data: Optional[str]) -> pd.DataFrame:
    """
    Convert Xert's detailed session data into Phoenix's canonical timeline.

    The Xert API has used more than one JSON layout over time, so this
    deliberately supports both:
      * a list of per-record dictionaries
      * parallel arrays such as unix_time, power, hr, cad, alt and dist
    """
    if not xert_raw_data:
        return pd.DataFrame()

    try:
        payload = json.loads(xert_raw_data)
    except (TypeError, json.JSONDecodeError):
        return pd.DataFrame()

    aliases = {
        "timestamp": ("timestamp", "time", "datetime", "date", "unix_time", "unix"),
        "power": ("power", "watts", "pwr"),
        "heart_rate": ("heart_rate", "hr", "heartrate"),
        "cadence": ("cadence", "cad", "rpm"),
        "altitude_m": ("altitude", "altitude_m", "alt", "elevation"),
        "speed_mps": ("speed", "speed_mps", "spd"),
        "distance_km": ("distance_km", "distance", "dist"),
        "latitude": ("latitude", "lat"),
        "longitude": ("longitude", "lng", "lon"),
        "xert_mpa": ("mpa",),
        "xert_xss": ("xss", "xds"),
    }

    # First try list-of-records layouts.
    for node in _walk_json(payload):
        for candidate_key in ("session_data", "records", "samples", "data", "track"):
            candidate = node.get(candidate_key)
            if not isinstance(candidate, list) or not candidate:
                continue
            if not all(isinstance(item, dict) for item in candidate[: min(5, len(candidate))]):
                continue

            rows = []
            for item in candidate:
                row: Dict[str, Any] = {}
                lower = {_normalise_field(k): v for k, v in item.items()}
                for output, names in aliases.items():
                    for name in names:
                        if name in lower and lower[name] is not None:
                            row[output] = lower[name]
                            break
                if "timestamp" in row:
                    rows.append(row)

            if rows:
                frame = pd.DataFrame(rows)
                break
        else:
            continue
        break
    else:
        frame = pd.DataFrame()

    # Then try parallel-array layouts.
    if frame.empty:
        for node in _walk_json(payload):
            lower = {_normalise_field(k): v for k, v in node.items()}
            timestamp_values = None
            for name in aliases["timestamp"]:
                timestamp_values = _numeric_series(lower.get(name))
                if timestamp_values is not None:
                    break
            if timestamp_values is None:
                continue

            data: Dict[str, Any] = {"timestamp": timestamp_values}
            length = len(timestamp_values)

            for output, names in aliases.items():
                if output == "timestamp":
                    continue
                for name in names:
                    values = _numeric_series(lower.get(name))
                    if values is not None and len(values) == length:
                        data[output] = values
                        break

            frame = pd.DataFrame(data)
            break

    if frame.empty or "timestamp" not in frame:
        return pd.DataFrame()

    timestamp_values = frame["timestamp"]
    numeric_timestamps = pd.to_numeric(timestamp_values, errors="coerce")
    if numeric_timestamps.notna().sum() >= max(1, len(frame) // 2):
        median = numeric_timestamps.dropna().median()
        unit = "ms" if median > 10_000_000_000 else "s"
        frame["timestamp"] = pd.to_datetime(
            numeric_timestamps,
            unit=unit,
            utc=True,
            errors="coerce",
        )
    else:
        frame["timestamp"] = pd.to_datetime(
            timestamp_values,
            utc=True,
            errors="coerce",
        )

    for column in frame.columns:
        if column != "timestamp":
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    # Xert has used several speed units across export/API layouts.
    if "speed_mps" in frame:
        frame["speed_kmh"] = _choose_speed_kmh(frame["speed_mps"])

    if "distance_km" in frame and frame["distance_km"].notna().any():
        maximum = frame["distance_km"].max()
        if maximum > 500:
            frame["distance_km"] = frame["distance_km"] / 1000.0

    return normalize_timeline(frame)


def xert_summary_from_raw(xert_raw_data: Optional[str]) -> Dict[str, Any]:
    if not xert_raw_data:
        return {}
    try:
        payload = json.loads(xert_raw_data)
    except (TypeError, json.JSONDecodeError):
        return {}

    summary = payload.get("summary")
    result = dict(summary) if isinstance(summary, dict) else {}

    for key in (
        "name", "path", "activity_type", "focus", "specificity",
        "difficulty", "xss", "distance", "elevation_gain",
    ):
        if key in payload and key not in result:
            result[key] = payload[key]
    return result

def match_score(
    workout_start: datetime,
    workout_end: datetime,
    parsed: ParsedFit,
) -> float:
    if parsed.start is None or parsed.end is None:
        return 0.0

    workout_start = pd.to_datetime(workout_start, utc=True).to_pydatetime()
    workout_end = pd.to_datetime(workout_end, utc=True).to_pydatetime()
    parsed_start = pd.to_datetime(parsed.start, utc=True).to_pydatetime()
    parsed_end = pd.to_datetime(parsed.end, utc=True).to_pydatetime()

    overlap = max(
        (
            min(workout_end, parsed_end)
            - max(workout_start, parsed_start)
        ).total_seconds(),
        0.0,
    )
    workout_duration = max((workout_end - workout_start).total_seconds(), 1.0)
    overlap_ratio = min(overlap / workout_duration, 1.0)
    start_delta = abs((parsed_start - workout_start).total_seconds())
    duration_delta = abs((parsed.duration_seconds or 0.0) - workout_duration)

    score = (
        overlap_ratio * 0.70
        + max(0.0, 1.0 - start_delta / 600.0) * 0.20
        + max(0.0, 1.0 - duration_delta / 900.0) * 0.10
    )
    return round(min(max(score, 0.0), 1.0), 2)


def merge_timelines(
    workout_start: datetime,
    workout_end: datetime,
    xert_df: pd.DataFrame,
    apple_df: pd.DataFrame,
    fit_sources: List[tuple[str, ParsedFit]],
) -> pd.DataFrame:
    """
    Build one canonical Phoenix workout timeline.

    Cycling source priority:
      Xert      -> HR, power, cadence, speed, distance, elevation and route
      Tymewear  -> respiratory metrics only
      Wahoo FIT -> CORE/temperature metrics only

    Apple Health remains the fallback master timeline when no Xert timeline is
    available, chiefly for walking and other non-Xert workouts.
    """
    workout_start_utc = pd.to_datetime(workout_start, utc=True, errors="raise")
    workout_end_utc = pd.to_datetime(workout_end, utc=True, errors="raise")

    master = normalize_timeline(pd.DataFrame({
        "timestamp": pd.date_range(
            start=workout_start_utc,
            end=workout_end_utc,
            freq="5s",
        )
    }))

    def merge_frame(
        frame: pd.DataFrame,
        *,
        keep_columns: Optional[List[str]] = None,
        tolerance_seconds: int = 35,
    ) -> None:
        nonlocal master
        working = normalize_timeline(frame, keep_columns=keep_columns)
        if working.empty or len(working.columns) <= 1:
            return

        # Both sides have passed through normalize_timeline(), so merge_asof
        # always receives identical datetime64[ns, UTC] keys.
        master = pd.merge_asof(
            normalize_timeline(master),
            working,
            on="timestamp",
            direction="nearest",
            tolerance=pd.Timedelta(seconds=tolerance_seconds),
        )
        master = normalize_timeline(master)

    if xert_df is not None and not xert_df.empty:
        merge_frame(
            xert_df,
            keep_columns=[
                "timestamp", "power", "heart_rate", "cadence",
                "speed_kmh", "distance_km", "altitude_m",
                "latitude", "longitude", "xert_mpa", "xert_xss",
            ],
        )
    elif apple_df is not None and not apple_df.empty:
        merge_frame(apple_df)

    for source_name, parsed in fit_sources:
        if parsed.records.empty:
            continue

        source_lower = source_name.lower()

        if source_lower.startswith("tyme"):
            merge_frame(
                parsed.records,
                keep_columns=[
                    "timestamp", "breathing_rate",
                    "minute_ventilation", "tidal_volume",
                ],
            )
        elif source_lower.startswith("wahoo"):
            merge_frame(
                parsed.records,
                keep_columns=[
                    "timestamp", "core_temperature_c",
                    "skin_temperature_c", "temperature_c",
                ],
            )

    master = _clean_physiology(master)

    master["elapsed_minutes"] = (
        master["timestamp"] - workout_start_utc
    ).dt.total_seconds() / 60.0

    return master


def summary_from_merged(merged: pd.DataFrame) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    clean = _clean_physiology(merged)

    average_metrics = (
        "speed_kmh", "heart_rate", "power", "cadence",
        "breathing_rate", "minute_ventilation", "tidal_volume",
        "core_temperature_c", "skin_temperature_c", "xert_mpa", "xert_xss",
    )
    for metric in average_metrics:
        if metric in clean and clean[metric].notna().any():
            values = clean[metric].dropna()
            summary[f"avg_{metric}"] = float(values.mean())
            summary[f"max_{metric}"] = float(values.max())
            summary[f"min_{metric}"] = float(values.min())

    if "distance_km" in clean and clean["distance_km"].notna().any():
        distance = pd.to_numeric(clean["distance_km"], errors="coerce").dropna()
        if not distance.empty:
            summary["total_distance_km"] = float(distance.max() - distance.min())
            if summary["total_distance_km"] <= 0:
                summary["total_distance_km"] = float(distance.max())

    if "altitude_m" in clean and clean["altitude_m"].notna().any():
        altitude = pd.to_numeric(clean["altitude_m"], errors="coerce").dropna()
        if not altitude.empty:
            summary["min_altitude_m"] = float(altitude.min())
            summary["max_altitude_m"] = float(altitude.max())
            gain = altitude.diff().clip(lower=0).sum()
            summary["elevation_gain_m"] = float(gain)

    return summary


def metric_label(metric: str) -> str:
    labels = {
        "speed_kmh": "Speed (km/h)",
        "distance_km": "Distance (km)",
        "heart_rate": "Heart rate (bpm)",
        "power": "Power (W)",
        "cadence": "Cadence (rpm)",
        "breathing_rate": "Breathing rate (/min)",
        "minute_ventilation": "Minute ventilation",
        "tidal_volume": "Tidal volume",
        "core_temperature_c": "CORE temperature (°C)",
        "skin_temperature_c": "Skin temperature (°C)",
        "temperature_c": "Temperature (°C)",
        "altitude_m": "Elevation (m)",
        "latitude": "Latitude",
        "longitude": "Longitude",
        "xert_mpa": "Xert MPA (W)",
        "xert_xss": "Xert strain",
        "steps_per_minute": "Steps/min",
    }
    return labels.get(metric, metric.replace("_", " ").title())
