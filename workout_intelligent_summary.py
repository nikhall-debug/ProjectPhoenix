from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from database import DB_FILE, get_checkin_for_date


HISTORICAL_METRICS = {
    "hrv": "apple_hrv_ms",
    "resting_hr": "apple_resting_hr_bpm",
    "sleep": "apple_sleep_total_hours",
    "blood_oxygen": "apple_blood_oxygen_percent",
    "wrist_temperature": "apple_sleeping_wrist_temperature_c",
}


@dataclass
class InsightSection:
    title: str
    body: str
    status: str = "neutral"
    evidence: List[str] = field(default_factory=list)


@dataclass
class WorkoutInsight:
    goal_assessment: InsightSection
    phoenix_noticed: InsightSection
    bigger_picture: InsightSection
    next_step: InsightSection
    looking_ahead: InsightSection
    positives: List[str]
    watchouts: List[str]
    confidence: int
    confidence_label: str
    context: Dict[str, Any]
    signals: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)



def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None



def _first_number(mapping: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = _safe_float(mapping.get(key))
        if value is not None:
            return value
    return None



def _normalise_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed



def _latest_metric_on_or_before(metric_type: str, cutoff: datetime) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT metric_type, value, unit, measured_at, source
        FROM health_measurements
        WHERE metric_type = ?
          AND datetime(measured_at) <= datetime(?)
        ORDER BY datetime(measured_at) DESC, id DESC
        LIMIT 1
        """,
        (metric_type, cutoff.isoformat()),
    ).fetchone()
    conn.close()
    return dict(row) if row else None



def _recent_training(workout_start: datetime, days: int = 7) -> Dict[str, Any]:
    window_start = workout_start - timedelta(days=days)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, session_type, title, session_date, start_time,
               duration_minutes, raw_data
        FROM training_sessions
        WHERE datetime(COALESCE(start_time, session_date)) < datetime(?)
          AND datetime(COALESCE(start_time, session_date)) >= datetime(?)
        ORDER BY datetime(COALESCE(start_time, session_date)) DESC
        """,
        (workout_start.isoformat(), window_start.isoformat()),
    ).fetchall()
    conn.close()

    sessions = [dict(row) for row in rows]
    minutes = sum(_safe_float(row.get("duration_minutes")) or 0 for row in sessions)
    by_type: Dict[str, int] = {}
    for row in sessions:
        label = str(row.get("session_type") or "Other")
        by_type[label] = by_type.get(label, 0) + 1

    return {
        "count": len(sessions),
        "minutes": round(minutes, 1),
        "by_type": by_type,
        "sessions": sessions,
    }




def _previous_comparable_workouts(
    pending: Dict[str, Any],
    workout_start: datetime,
    limit: int = 12,
) -> List[Dict[str, Any]]:
    """
    Load Phoenix's own previously analysed sessions of the same type.

    Comparisons deliberately use workouts saved before the current workout,
    so reopening an old workout never leaks future information into the report.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT
            ts.id,
            ts.title,
            ts.session_type,
            ts.session_date,
            ts.start_time,
            ts.duration_minutes,
            wda.summary_json
        FROM training_sessions ts
        JOIN workout_deep_analyses wda
          ON wda.session_id = ts.id
        WHERE ts.source = 'Phoenix merged'
          AND ts.session_type = ?
          AND datetime(COALESCE(ts.start_time, ts.session_date)) < datetime(?)
        ORDER BY datetime(COALESCE(ts.start_time, ts.session_date)) DESC
        LIMIT ?
        """,
        (
            pending.get("session_type"),
            workout_start.isoformat(),
            int(limit),
        ),
    ).fetchall()
    conn.close()

    comparable: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            summary = json.loads(item.get("summary_json") or "{}")
        except json.JSONDecodeError:
            summary = {}
        item["summary"] = summary if isinstance(summary, dict) else {}
        comparable.append(item)
    return comparable


def _median(values: List[float]) -> Optional[float]:
    clean = sorted(value for value in values if value is not None)
    if not clean:
        return None
    midpoint = len(clean) // 2
    if len(clean) % 2:
        return float(clean[midpoint])
    return float((clean[midpoint - 1] + clean[midpoint]) / 2.0)


def _personal_baseline(
    pending: Dict[str, Any],
    workout_start: datetime,
) -> Dict[str, Any]:
    sessions = _previous_comparable_workouts(pending, workout_start)
    metric_keys = (
        "avg_power",
        "avg_heart_rate",
        "avg_breathing_rate",
        "max_core_temperature_c",
        "duration_minutes",
        "distance_km",
        "elevation_gain_m",
    )

    medians: Dict[str, float] = {}
    for key in metric_keys:
        values: List[float] = []
        for session in sessions:
            summary = session.get("summary") or {}
            value = _safe_float(summary.get(key))
            if value is None and key == "duration_minutes":
                value = _safe_float(session.get("duration_minutes"))
            if value is not None:
                values.append(value)
        median = _median(values)
        if median is not None:
            medians[key] = median

    return {
        "sample_size": len(sessions),
        "medians": medians,
        "sessions": sessions,
    }


def _relative_difference(current: Optional[float], baseline: Optional[float]) -> Optional[float]:
    if current is None or baseline in (None, 0):
        return None
    return (current - baseline) / abs(baseline) * 100.0

def build_historical_workout_context(
    pending: Dict[str, Any],
    xert_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    start = _normalise_datetime(pending.get("start_time"))
    if start is None:
        start = datetime.fromisoformat(str(pending["session_date"])).replace(
            tzinfo=timezone.utc
        )

    day_cutoff = start.replace(
        hour=23, minute=59, second=59, microsecond=999999
    )
    metrics = {
        name: _latest_metric_on_or_before(metric_type, day_cutoff)
        for name, metric_type in HISTORICAL_METRICS.items()
    }

    return {
        "workout_date": pending.get("session_date"),
        "workout_start": start.isoformat(),
        "session_type": pending.get("session_type"),
        "checkin": get_checkin_for_date(pending.get("session_date")),
        "metrics": metrics,
        "recent_training_7d": _recent_training(start, days=7),
        "personal_baseline": _personal_baseline(pending, start),
        "xert_summary": xert_summary or {},
    }



def _series_change(
    merged: pd.DataFrame,
    column: str,
    fraction: float = 0.33,
) -> Optional[Dict[str, float]]:
    if merged.empty or column not in merged:
        return None
    values = pd.to_numeric(merged[column], errors="coerce").dropna()
    if len(values) < 20:
        return None
    count = max(int(len(values) * fraction), 5)
    early = float(values.iloc[:count].mean())
    late = float(values.iloc[-count:].mean())
    absolute = late - early
    relative = absolute / abs(early) * 100 if early else 0.0
    return {
        "early": early,
        "late": late,
        "absolute": absolute,
        "relative_percent": relative,
    }



def _timeline_signals(merged: pd.DataFrame) -> Dict[str, Any]:
    signals: Dict[str, Any] = {}
    for output, column in (
        ("heart_rate_change", "heart_rate"),
        ("power_change", "power"),
        ("breathing_change", "breathing_rate"),
        ("ventilation_change", "minute_ventilation"),
        ("core_change", "core_temperature_c"),
        ("cadence_change", "cadence"),
    ):
        change = _series_change(merged, column)
        if change:
            signals[output] = change

    if "power" in merged:
        power = pd.to_numeric(merged["power"], errors="coerce").dropna()
        if len(power) >= 20 and power.mean() > 0:
            signals["power_variability_percent"] = float(
                power.std() / power.mean() * 100
            )

    hr = signals.get("heart_rate_change")
    power = signals.get("power_change")
    if hr and power:
        # A useful descriptive marker, not a clinical determination.
        signals["cardiovascular_drift_marker"] = (
            hr["relative_percent"] - power["relative_percent"]
        )

    return signals



def _classify_session(
    pending: Dict[str, Any],
    xert: Dict[str, Any],
) -> Tuple[str, str]:
    focus = str(
        xert.get("focus")
        or xert.get("focus_name")
        or xert.get("specificity")
        or ""
    ).lower()
    xss = _first_number(xert, "xss", "strain_score", "xss_total")
    duration = _safe_float(pending.get("duration_minutes")) or 0
    session_type = str(pending.get("session_type") or "").lower()

    if session_type == "walking":
        return "light_movement", "light movement"
    if "recovery" in focus or (xss is not None and xss <= 35 and duration <= 75):
        return "recovery", "low-load aerobic work"
    if "endurance" in focus or (xss is not None and xss <= 75):
        return "endurance", "endurance work"
    if "threshold" in focus or "tempo" in focus:
        return "quality", "sustained quality work"
    if "sprint" in focus or "anaerobic" in focus or "vo2" in focus:
        return "high_intensity", "high-intensity work"
    return "general", "training"



def _morning_state(context: Dict[str, Any]) -> Dict[str, Optional[float]]:
    checkin = context.get("checkin") or {}
    metrics = context.get("metrics") or {}
    return {
        "energy": _safe_float(checkin.get("energy")),
        "soreness": _safe_float(checkin.get("soreness")),
        "mood": _safe_float(checkin.get("mood")),
        "sleep": _safe_float((metrics.get("sleep") or {}).get("value")),
        "hrv": _safe_float((metrics.get("hrv") or {}).get("value")),
        "resting_hr": _safe_float((metrics.get("resting_hr") or {}).get("value")),
    }



def _goal_section(
    category: str,
    label: str,
    morning: Dict[str, Optional[float]],
    signals: Dict[str, Any],
) -> InsightSection:
    energy = morning.get("energy")
    soreness = morning.get("soreness")
    core = signals.get("core_change")

    if category in {"recovery", "light_movement"}:
        body = (
            "This session did what a recovery-oriented workout should do: it kept "
            "you moving and provided an aerobic stimulus without turning into a "
            "second training battle."
        )
        if energy is not None and energy <= 5:
            body += (
                " Given that you did not begin the day with abundant energy, the "
                "controlled approach was especially appropriate."
            )
        if soreness is not None and soreness <= 3:
            body += " Low soreness also suggests the session was well timed."
        return InsightSection(
            title="The objective was achieved",
            body=body,
            status="positive",
            evidence=[label],
        )

    if category == "endurance":
        return InsightSection(
            title="A useful aerobic session",
            body=(
                "The workout delivered steady aerobic work without obvious signs "
                "that the effort unravelled late. It looks more like productive "
                "endurance than accumulated fatigue for its own sake."
            ),
            status="positive",
            evidence=[label],
        )

    if category in {"quality", "high_intensity"}:
        return InsightSection(
            title="The quality work was completed",
            body=(
                "The session supplied a meaningful training stimulus. The more "
                "important question now is not whether it was hard enough, but how "
                "well your recovery markers respond over the next day."
            ),
            status="positive",
            evidence=[label],
        )

    return InsightSection(
        title="A completed training stimulus",
        body=(
            "The session added useful work. Phoenix has enough information to "
            "describe the response, although the intended workout objective was "
            "not explicit enough to judge execution more precisely."
        ),
        status="neutral",
        evidence=[label],
    )



def _noticed_section(
    signals: Dict[str, Any],
    summary: Dict[str, Any],
) -> Tuple[InsightSection, List[str], List[str]]:
    positives: List[str] = []
    watchouts: List[str] = []

    hr = signals.get("heart_rate_change")
    breathing = signals.get("breathing_change")
    ventilation = signals.get("ventilation_change")
    core = signals.get("core_change")
    power = signals.get("power_change")
    drift = _safe_float(signals.get("cardiovascular_drift_marker"))

    observations: List[Tuple[int, str, str, str]] = []

    if core:
        rise = core["absolute"]
        max_core = _safe_float(summary.get("max_core_temperature_c"))
        if max_core is not None and max_core < 38.6 and rise < 1.2:
            observations.append((100, "positive", "Thermal strain stayed controlled", (
                "CORE temperature rose gradually rather than surging. That is a "
                "reassuring pattern for a controlled aerobic session and suggests "
                "heat was not the factor limiting the workout."
            )))
            positives.append("controlled thermal response")
        elif max_core is not None and max_core >= 39.0:
            observations.append((100, "watch", "Heat became a meaningful part of the effort", (
                "CORE temperature reached a level where thermal strain deserves "
                "attention. That does not make the workout unsuccessful, but it "
                "does make cooling, hydration and the following recovery response "
                "more relevant."
            )))
            watchouts.append("elevated thermal strain")

    if breathing:
        change = breathing["relative_percent"]
        if abs(change) < 12:
            observations.append((90, "positive", "Breathing remained composed", (
                "Respiratory demand moved with the workout but did not show a large "
                "late-session escalation. In practical terms, your breathing stayed "
                "under control rather than becoming the story of the ride."
            )))
            positives.append("stable respiratory response")
        elif change >= 18:
            observations.append((95, "watch", "Breathing demand rose late", (
                "Breathing rate was noticeably higher in the closing part of the "
                "session. If power was not rising at the same time, this may be an "
                "early sign that the same work was becoming more costly."
            )))
            watchouts.append("late respiratory rise")

    if drift is not None:
        if drift < 7:
            observations.append((85, "positive", "Cardiovascular efficiency held together", (
                "Heart rate did not drift far beyond the change in power. That is "
                "what we want to see when an aerobic session is being absorbed well."
            )))
            positives.append("limited cardiovascular drift")
        elif drift >= 12:
            observations.append((92, "watch", "The same work became more costly", (
                "Heart rate rose more than power late in the session. This is not a "
                "red flag on its own, but it is a useful marker of accumulating "
                "fatigue, heat or hydration demand."
            )))
            watchouts.append("cardiovascular drift")

    if power:
        if power["relative_percent"] <= -15:
            observations.append((80, "watch", "Power faded in the closing phase", (
                "Output dropped meaningfully toward the end. On an easy day that may "
                "simply reflect easing off; on a planned steady session it would be "
                "worth comparing with breathing and heart-rate drift."
            )))
            watchouts.append("late power fade")

    if observations:
        observations.sort(key=lambda item: item[0], reverse=True)
        _, status, title, body = observations[0]
        return (
            InsightSection(
                title=title,
                body=body,
                status="positive" if status == "positive" else "watch",
                evidence=[item[2] for item in observations[:3]],
            ),
            list(dict.fromkeys(positives)),
            list(dict.fromkeys(watchouts)),
        )

    return (
        InsightSection(
            title="The response was broadly steady",
            body=(
                "Nothing in the available timeline stands out as a strong limiter. "
                "That is useful information in itself, although Phoenix needs more "
                "complete sensor coverage or more comparable sessions before making "
                "a stronger claim."
            ),
            status="neutral",
        ),
        positives,
        watchouts,
    )



def _bigger_picture_section(
    category: str,
    context: Dict[str, Any],
    morning: Dict[str, Optional[float]],
    positives: List[str],
    watchouts: List[str],
) -> InsightSection:
    recent = context.get("recent_training_7d") or {}
    count = int(recent.get("count") or 0)
    minutes = _safe_float(recent.get("minutes")) or 0
    energy = morning.get("energy")
    soreness = morning.get("soreness")
    sleep = morning.get("sleep")

    if count >= 7 or minutes >= 300:
        load_phrase = (
            "You had already accumulated a fair amount of movement and training in "
            "the preceding week, so this session should be judged as part of that "
            "total rather than as an isolated workout."
        )
    elif count >= 3 or minutes >= 120:
        load_phrase = (
            "This sat within a moderately active week, adding continuity without "
            "dramatically changing the overall load."
        )
    else:
        load_phrase = (
            "Recent training volume was relatively light, so this session mainly "
            "contributed consistency and a gentle return to rhythm."
        )

    context_phrase = ""
    if energy is not None and energy <= 4:
        context_phrase = (
            " Your morning energy was low, which makes the controlled execution more "
            "important than the headline performance numbers."
        )
    elif soreness is not None and soreness >= 6:
        context_phrase = (
            " Elevated soreness before the workout argues for caution when deciding "
            "how quickly to progress."
        )
    elif sleep is not None and sleep < 6:
        context_phrase = (
            " Short sleep reduced the margin for absorbing extra load, even though "
            "the workout itself may have looked comfortable."
        )
    elif positives and not watchouts:
        context_phrase = (
            " The physiological response supports the idea that the workload was "
            "appropriate for where you were that day."
        )

    return InsightSection(
        title="How it fits the bigger picture",
        body=load_phrase + context_phrase,
        status="watch" if watchouts else "neutral",
    )



def _next_step_section(
    category: str,
    morning: Dict[str, Optional[float]],
    watchouts: List[str],
) -> InsightSection:
    energy = morning.get("energy")
    soreness = morning.get("soreness")
    sleep = morning.get("sleep")

    if watchouts or (energy is not None and energy <= 4) or (soreness is not None and soreness >= 6):
        return InsightSection(
            title="Let the next morning decide",
            body=(
                "Do not force progression from this workout alone. Check how energy, "
                "soreness, resting heart rate and HRV respond the next morning; if "
                "they deteriorate, keep the next session easy or take the day off."
            ),
            status="watch",
        )

    if category in {"recovery", "light_movement"}:
        return InsightSection(
            title="Build duration before intensity",
            body=(
                "If the following day's recovery remains stable, the sensible next "
                "step is a little more easy aerobic time—not a sudden return to hard "
                "efforts. That keeps the progression useful and easy to reverse."
            ),
            status="positive",
        )

    if category == "endurance":
        return InsightSection(
            title="Progress one variable at a time",
            body=(
                "A slightly longer endurance session is the cleanest progression if "
                "recovery stays positive. Keep intensity broadly similar so Phoenix "
                "can tell whether the extra duration is being absorbed well."
            ),
            status="positive",
        )

    return InsightSection(
        title="Judge the response before adding load",
        body=(
            "Use the next day's recovery trend to decide what comes next. A successful "
            "workout is not only one you complete; it is one your body absorbs without "
            "an unnecessary recovery cost."
        ),
        status="neutral",
    )




def _personal_comparison(
    summary: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    baseline = context.get("personal_baseline") or {}
    medians = baseline.get("medians") or {}
    sample_size = int(baseline.get("sample_size") or 0)

    comparisons: Dict[str, Any] = {"sample_size": sample_size}
    for key in (
        "avg_power",
        "avg_heart_rate",
        "avg_breathing_rate",
        "max_core_temperature_c",
        "duration_minutes",
    ):
        current = _safe_float(summary.get(key))
        median = _safe_float(medians.get(key))
        difference = _relative_difference(current, median)
        if difference is not None:
            comparisons[key] = {
                "current": current,
                "median": median,
                "relative_percent": difference,
            }
    return comparisons


def _surprise_section(
    category: str,
    summary: Dict[str, Any],
    signals: Dict[str, Any],
    context: Dict[str, Any],
) -> Optional[InsightSection]:
    comparison = _personal_comparison(summary, context)
    sample_size = int(comparison.get("sample_size") or 0)
    if sample_size < 3:
        return None

    hr = comparison.get("avg_heart_rate")
    breathing = comparison.get("avg_breathing_rate")
    power = comparison.get("avg_power")
    core = comparison.get("max_core_temperature_c")

    # Lower HR or breathing at similar/higher power is a genuinely useful,
    # personal efficiency observation.
    if power and hr:
        if power["relative_percent"] >= -5 and hr["relative_percent"] <= -5:
            return InsightSection(
                title="Phoenix noticed a more economical response",
                body=(
                    f"Compared with your previous {sample_size} analysed "
                    f"{str(context.get('session_type') or 'similar').lower()} sessions, "
                    "you produced a broadly comparable workload with a lower "
                    "cardiovascular cost. That is more meaningful than the headline "
                    "power number alone because it suggests the work was becoming "
                    "easier for your system to support."
                ),
                status="positive",
                evidence=["personal heart-rate baseline", "personal power baseline"],
            )

    if power and breathing:
        if power["relative_percent"] >= -5 and breathing["relative_percent"] <= -7:
            return InsightSection(
                title="Phoenix noticed quieter breathing for the work produced",
                body=(
                    f"Against your previous {sample_size} comparable sessions, "
                    "breathing demand was lower without a meaningful reduction in "
                    "workload. That points toward improving aerobic economy, although "
                    "Phoenix will want to see the pattern repeat before treating it "
                    "as a firm trend."
                ),
                status="positive",
                evidence=["personal respiratory baseline", "personal power baseline"],
            )

    if core and core["relative_percent"] <= -2:
        return InsightSection(
            title="Phoenix noticed a cooler-than-usual response",
            body=(
                f"Maximum CORE temperature was lower than the median from your "
                f"previous {sample_size} comparable sessions. Conditions and cooling "
                "can influence this, but it is still a useful sign that heat was not "
                "driving the effort on this occasion."
            ),
            status="positive",
            evidence=["personal CORE baseline"],
        )

    drift = _safe_float(signals.get("cardiovascular_drift_marker"))
    if drift is not None and abs(drift) < 4:
        return InsightSection(
            title="Nothing unusual happened—and that is useful",
            body=(
                f"Relative to your previous {sample_size} comparable sessions, no "
                "single physiological response stood out as abnormal. For a "
                "controlled workout, an ordinary and well-contained response is often "
                "exactly the result Phoenix wants to see."
            ),
            status="neutral",
            evidence=["personal session baseline"],
        )
    return None


def _looking_ahead_section(
    category: str,
    context: Dict[str, Any],
    positives: List[str],
    watchouts: List[str],
) -> InsightSection:
    baseline = context.get("personal_baseline") or {}
    sample_size = int(baseline.get("sample_size") or 0)

    if watchouts:
        body = (
            "Phoenix will be watching whether the same late-session signal appears "
            "again. One workout is an observation; repetition across the next two or "
            "three comparable sessions is what turns it into a pattern."
        )
        status = "watch"
    elif category in {"recovery", "light_movement"}:
        body = (
            "Phoenix will now watch whether your next easy sessions can either last "
            "slightly longer at the same physiological cost, or produce the same work "
            "with calmer heart rate and breathing. Either would be evidence that the "
            "recovery trajectory is moving in the right direction."
        )
        status = "positive"
    elif category == "endurance":
        body = (
            "Phoenix will be looking for repeatability: similar power with no extra "
            "heart-rate, breathing or thermal drift. Once that response becomes "
            "consistent, a modest increase in duration becomes easier to justify."
        )
        status = "positive"
    else:
        body = (
            "Phoenix will compare the next similar workout with this one rather than "
            "judging it in isolation. The key question is whether the stimulus can be "
            "repeated with equal or lower physiological cost."
        )
        status = "neutral"

    if sample_size < 3:
        body += (
            " The personal comparison set is still small, so each newly analysed "
            "workout will make this guidance more specific."
        )

    return InsightSection(
        title="Looking ahead",
        body=body,
        status=status,
    )


def _format_minutes(value: float) -> str:
    minutes = max(float(value), 0.0)
    whole = int(minutes)
    seconds = int(round((minutes - whole) * 60))
    if seconds == 60:
        whole += 1
        seconds = 0
    return f"{whole}:{seconds:02d}"


def _numeric_timeline(merged: pd.DataFrame) -> pd.DataFrame:
    if merged is None or merged.empty:
        return pd.DataFrame()

    frame = merged.copy()
    if "elapsed_minutes" not in frame:
        if "timestamp" not in frame:
            return pd.DataFrame()
        timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
        if timestamps.notna().sum() == 0:
            return pd.DataFrame()
        frame["elapsed_minutes"] = (
            timestamps - timestamps.dropna().min()
        ).dt.total_seconds() / 60.0

    numeric_columns = (
        "elapsed_minutes",
        "altitude_m",
        "speed_kmh",
        "power",
        "heart_rate",
        "cadence",
        "breathing_rate",
        "minute_ventilation",
        "core_temperature_c",
    )
    for column in numeric_columns:
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = (
        frame.dropna(subset=["elapsed_minutes"])
        .sort_values("elapsed_minutes")
        .drop_duplicates("elapsed_minutes")
        .reset_index(drop=True)
    )
    return frame


def _windowed_timeline(merged: pd.DataFrame, window_seconds: int = 60) -> pd.DataFrame:
    """
    Build overlapping one-minute windows.

    Route effects are identified before physiological drift is assessed.
    This prevents Phoenix from treating normal climbing responses or
    downhill coasting as fatigue.
    """
    frame = _numeric_timeline(merged)
    if frame.empty or len(frame) < 12:
        return pd.DataFrame()

    elapsed_seconds = frame["elapsed_minutes"] * 60.0
    typical_step = elapsed_seconds.diff().dropna().median()
    if pd.isna(typical_step) or typical_step <= 0:
        typical_step = 5.0

    points = max(int(round(window_seconds / typical_step)), 3)
    minimum = max(points // 2, 3)

    result = pd.DataFrame(index=frame.index)
    result["elapsed_minutes"] = frame["elapsed_minutes"]

    mean_columns = (
        "speed_kmh",
        "power",
        "heart_rate",
        "cadence",
        "breathing_rate",
        "minute_ventilation",
        "core_temperature_c",
    )
    for column in mean_columns:
        if column in frame:
            result[column] = frame[column].rolling(
                points, center=True, min_periods=minimum
            ).mean()

    if "altitude_m" in frame:
        altitude = frame["altitude_m"].interpolate(limit_direction="both")
        result["altitude_m"] = altitude.rolling(
            points, center=True, min_periods=minimum
        ).mean()
        # Change across the window, expressed as metres per minute.
        result["vertical_rate_m_min"] = (
            altitude.shift(-points // 2) - altitude.shift(points // 2)
        ) / max(window_seconds / 60.0, 0.1)

    # Short-term direction of the main signals.
    for column in (
        "speed_kmh",
        "power",
        "heart_rate",
        "cadence",
        "breathing_rate",
        "minute_ventilation",
        "core_temperature_c",
    ):
        if column in result:
            result[f"{column}_change"] = (
                result[column].shift(-points // 2)
                - result[column].shift(points // 2)
            )

    return result.dropna(subset=["elapsed_minutes"]).reset_index(drop=True)


def _route_state(windowed: pd.DataFrame) -> pd.Series:
    if windowed.empty:
        return pd.Series(dtype="object")

    state = pd.Series("unknown", index=windowed.index, dtype="object")
    vertical = windowed.get(
        "vertical_rate_m_min",
        pd.Series(0.0, index=windowed.index),
    ).fillna(0.0)
    speed_change = windowed.get(
        "speed_kmh_change",
        pd.Series(0.0, index=windowed.index),
    ).fillna(0.0)
    power = windowed.get(
        "power",
        pd.Series(float("nan"), index=windowed.index),
    )
    cadence = windowed.get(
        "cadence",
        pd.Series(float("nan"), index=windowed.index),
    )

    average_power = float(power.dropna().median()) if power.notna().any() else None

    climb = vertical >= 3.0
    descent = vertical <= -3.0

    state.loc[climb] = "climb"
    state.loc[descent] = "descent"

    # Coasting is inferred only when workload data support it.
    if average_power is not None:
        coasting = (
            (power <= max(45.0, average_power * 0.42))
            & (
                (cadence <= 55)
                | cadence.isna()
            )
        )
        state.loc[coasting & ~climb] = "coasting"

    flat = vertical.abs() < 1.5
    state.loc[flat & (state == "unknown")] = "steady_or_flat"

    # When altitude is missing, speed/power context still helps separate
    # recovery/coasting from physiological drift.
    state.loc[
        (state == "unknown")
        & (speed_change > 4)
        & power.notna()
        & (power < max(50.0, (average_power or 100.0) * 0.5))
    ] = "coasting"

    return state


def _contiguous_events(
    windowed: pd.DataFrame,
    state: pd.Series,
    minimum_seconds: int = 35,
) -> List[Dict[str, Any]]:
    if windowed.empty or state.empty:
        return []

    elapsed = windowed["elapsed_minutes"].to_numpy()
    events: List[Dict[str, Any]] = []
    start = 0

    for index in range(1, len(state) + 1):
        boundary = index == len(state) or state.iloc[index] != state.iloc[start]
        if not boundary:
            continue

        end = index - 1
        duration_seconds = max(
            (elapsed[end] - elapsed[start]) * 60.0,
            0.0,
        )
        label = str(state.iloc[start])
        if duration_seconds >= minimum_seconds and label != "unknown":
            segment = windowed.iloc[start:index]
            event: Dict[str, Any] = {
                "type": label,
                "start_minute": float(elapsed[start]),
                "end_minute": float(elapsed[end]),
                "duration_seconds": float(duration_seconds),
            }

            for column in (
                "vertical_rate_m_min",
                "speed_kmh",
                "speed_kmh_change",
                "power",
                "power_change",
                "heart_rate",
                "heart_rate_change",
                "cadence",
                "cadence_change",
                "breathing_rate",
                "breathing_rate_change",
                "minute_ventilation",
                "minute_ventilation_change",
                "core_temperature_c",
                "core_temperature_c_change",
            ):
                if column in segment and segment[column].notna().any():
                    event[column] = float(segment[column].mean())

            events.append(event)
        start = index

    return events


def _strongest_event(
    events: List[Dict[str, Any]],
    event_type: str,
    score_key: str,
    reverse: bool = False,
) -> Optional[Dict[str, Any]]:
    candidates = [
        event for event in events
        if event.get("type") == event_type and event.get(score_key) is not None
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda event: float(event.get(score_key) or 0),
        reverse=not reverse,
    )[0]


def _steady_drift(windowed: pd.DataFrame, state: pd.Series) -> Dict[str, Any]:
    """
    Compare early and late physiology only during comparable steady work.

    Climbs, descents and coasting are excluded. Power must remain reasonably
    similar before a rise in HR or breathing can be described as drift.
    """
    if windowed.empty:
        return {}

    usable = windowed.copy()
    usable["route_state"] = state.values
    usable = usable[usable["route_state"] == "steady_or_flat"]

    if "power" in usable and usable["power"].notna().any():
        power_median = usable["power"].median()
        if power_median > 0:
            usable = usable[
                usable["power"].between(power_median * 0.75, power_median * 1.25)
            ]

    if len(usable) < 12:
        return {}

    third = max(len(usable) // 3, 4)
    early = usable.iloc[:third]
    late = usable.iloc[-third:]

    result: Dict[str, Any] = {}
    for column in (
        "power",
        "heart_rate",
        "breathing_rate",
        "minute_ventilation",
        "cadence",
        "core_temperature_c",
    ):
        if column not in usable:
            continue
        early_value = early[column].mean()
        late_value = late[column].mean()
        if pd.isna(early_value) or pd.isna(late_value):
            continue
        absolute = float(late_value - early_value)
        relative = float(absolute / abs(early_value) * 100) if early_value else 0.0
        result[column] = {
            "early": float(early_value),
            "late": float(late_value),
            "absolute": absolute,
            "relative_percent": relative,
        }

    hr = result.get("heart_rate")
    power = result.get("power")
    if hr and power:
        result["cardiovascular_drift_marker"] = (
            hr["relative_percent"] - power["relative_percent"]
        )

    breathing = result.get("breathing_rate")
    if breathing and power:
        result["respiratory_drift_marker"] = (
            breathing["relative_percent"] - power["relative_percent"]
        )

    return result


def build_route_aware_event_analysis(
    merged: pd.DataFrame,
) -> Dict[str, Any]:
    windowed = _windowed_timeline(merged)
    if windowed.empty:
        return {
            "events": [],
            "steady_drift": {},
            "coverage": "limited",
        }

    state = _route_state(windowed)
    events = _contiguous_events(windowed, state)
    steady_drift = _steady_drift(windowed, state)

    counts: Dict[str, int] = {}
    for event in events:
        event_type = str(event.get("type"))
        counts[event_type] = counts.get(event_type, 0) + 1

    return {
        "events": events,
        "steady_drift": steady_drift,
        "event_counts": counts,
        "coverage": "good" if events else "limited",
    }


def _domain_card(
    good_title: str,
    good_body: str,
    watch_title: Optional[str] = None,
    watch_body: Optional[str] = None,
    evidence: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "good": {
            "title": good_title,
            "body": good_body,
        },
        "watch": (
            {
                "title": watch_title,
                "body": watch_body,
            }
            if watch_title and watch_body
            else None
        ),
        "evidence": evidence or [],
    }


def build_route_aware_tab_insights(
    merged: pd.DataFrame,
    summary: Dict[str, Any],
    coach_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Explain each graph tab using cross-signal, route-aware events.

    The same climb may be described from several lenses, but the underlying
    event classification remains shared so the tabs cannot contradict one
    another.
    """
    analysis = build_route_aware_event_analysis(merged)
    events = analysis.get("events") or []
    drift = analysis.get("steady_drift") or {}

    climb = _strongest_event(
        events, "climb", "vertical_rate_m_min"
    )
    descent = _strongest_event(
        events, "descent", "vertical_rate_m_min", reverse=True
    )
    coasting = _strongest_event(
        events, "coasting", "duration_seconds"
    )

    hr_drift = _safe_float(drift.get("cardiovascular_drift_marker"))
    respiratory_drift = _safe_float(drift.get("respiratory_drift_marker"))
    core_change = (
        drift.get("core_temperature_c", {}).get("absolute")
        if isinstance(drift.get("core_temperature_c"), dict)
        else None
    )
    power_change = (
        drift.get("power", {}).get("relative_percent")
        if isinstance(drift.get("power"), dict)
        else None
    )
    cadence_change = (
        drift.get("cadence", {}).get("relative_percent")
        if isinstance(drift.get("cadence"), dict)
        else None
    )

    evidence: List[str] = []
    if climb:
        evidence.append(
            f"Main climb around {_format_minutes(climb['start_minute'])}–"
            f"{_format_minutes(climb['end_minute'])}"
        )
    if descent:
        evidence.append(
            f"Descent around {_format_minutes(descent['start_minute'])}–"
            f"{_format_minutes(descent['end_minute'])}"
        )
    if coasting:
        evidence.append(
            f"Low-load/coasting phase around "
            f"{_format_minutes(coasting['start_minute'])}–"
            f"{_format_minutes(coasting['end_minute'])}"
        )

    # Overview
    if climb and _safe_float(climb.get("heart_rate_change")) is not None:
        overview_good = (
            "The larger changes in speed, heart rate and cadence were tied to "
            "changes in elevation rather than appearing randomly. Phoenix found "
            "a coherent terrain-driven response: effort rose on the climb and "
            "settled again when the route eased."
        )
    else:
        overview_good = (
            "The main signals moved together in a coherent way. Phoenix did not "
            "find a strong mismatch between workload and physiological response."
        )

    overview_watch = None
    overview_watch_body = None
    if hr_drift is not None and hr_drift > 7:
        overview_watch = "Some genuine late-session drift remained"
        overview_watch_body = (
            "Even after climbs, descents and coasting were excluded, heart rate "
            "rose more than power during comparable steady work. That is worth "
            "watching if it repeats."
        )

    # Respiration
    if climb and _safe_float(climb.get("breathing_rate_change")) is not None:
        respiration_good = (
            "Breathing rose when the route and workload demanded it, particularly "
            "on the main climb, then eased as the effort reduced. That pattern is "
            "more consistent with appropriate workload response than unexplained "
            "respiratory strain."
        )
    else:
        respiration_good = (
            "Breathing broadly tracked workload rather than drifting independently."
        )

    respiration_watch = None
    respiration_watch_body = None
    if respiratory_drift is not None and respiratory_drift > 9:
        respiration_watch = "Breathing drifted during comparable steady work"
        respiration_watch_body = (
            "After terrain effects were removed, breathing still rose more than "
            "power late in the session. One occurrence is not a trend, but Phoenix "
            "will compare this with the next similar workout."
        )

    # Cardiovascular
    if climb and _safe_float(climb.get("heart_rate_change")) is not None:
        cardiovascular_good = (
            "The heart-rate rise coincided with increasing elevation and workload. "
            "Heart rate then moved back down when the route eased, so Phoenix reads "
            "this primarily as a normal response to the climb—not unexplained "
            "cardiovascular drift."
        )
    else:
        cardiovascular_good = (
            "Heart rate remained broadly proportional to workload throughout the "
            "session."
        )

    cardiovascular_watch = None
    cardiovascular_watch_body = None
    if hr_drift is not None and hr_drift > 7:
        cardiovascular_watch = "A smaller terrain-independent drift signal remains"
        cardiovascular_watch_body = (
            "During steady sections with similar power, late heart rate was still "
            "higher than early heart rate. Phoenix will watch whether this repeats "
            "before treating it as meaningful."
        )

    # Thermal
    thermal_good = (
        "CORE temperature rose progressively rather than surging during a single "
        "climb or effort change. Phoenix therefore sees heat as a background load, "
        "not the main explanation for changes in speed, cadence or heart rate."
    )
    thermal_watch = None
    thermal_watch_body = None
    if core_change is not None and core_change > 0.45:
        thermal_watch = "Thermal load continued to accumulate"
        thermal_watch_body = (
            "CORE temperature kept rising during comparable steady work. It did not "
            "appear to drive this workout, but longer or hotter sessions may expose "
            "more thermal strain."
        )

    # Efficiency
    if coasting or descent:
        efficiency_good = (
            "Lower cadence and power during the easier route sections were paired "
            "with falling workload or descending terrain. Phoenix treats those "
            "changes as coasting/recovery rather than loss of efficiency."
        )
    else:
        efficiency_good = (
            "Workload and physiological demand remained reasonably aligned."
        )

    efficiency_watch = None
    efficiency_watch_body = None
    if (
        power_change is not None
        and power_change < -8
        and hr_drift is not None
        and hr_drift > 6
    ):
        efficiency_watch = "Efficiency softened late on comparable terrain"
        efficiency_watch_body = (
            "Power fell while cardiovascular cost remained elevated during steady "
            "sections. Because route effects were excluded, this is more compatible "
            "with fatigue than downhill coasting."
        )
    elif cadence_change is not None and cadence_change < -12 and not coasting:
        efficiency_watch = "Cadence declined outside an obvious descent"
        efficiency_watch_body = (
            "Cadence was lower late during otherwise comparable work. Phoenix will "
            "watch whether this represents fatigue, gearing choice or a repeatable "
            "pacing pattern."
        )

    # Elevation
    if climb:
        elevation_good = (
            f"The clearest climb occurred around "
            f"{_format_minutes(climb['start_minute'])}–"
            f"{_format_minutes(climb['end_minute'])}. Speed fell while workload and "
            "physiological demand increased, which is the expected relationship on "
            "rising terrain."
        )
    else:
        elevation_good = (
            "Phoenix did not identify a long, sustained climb strongly enough to "
            "attribute the workout's main changes to one terrain segment."
        )

    elevation_watch = None
    elevation_watch_body = None
    if climb and _safe_float(climb.get("power_change")) is not None:
        if float(climb.get("power_change") or 0) < -20:
            elevation_watch = "Power eased during the main climb"
            elevation_watch_body = (
                "The fall in power happened while elevation was still rising. That "
                "may be pacing or gearing rather than a problem, but it is the climb "
                "segment Phoenix would revisit on the next comparable route."
            )

    # Route
    if climb and descent:
        route_good = (
            "Phoenix could connect the main changes across the route: speed reduced "
            "and heart rate rose on the climb, while cadence/power eased and heart "
            "rate recovered as the route descended. Those are coordinated route "
            "effects, not isolated warning signals."
        )
    elif climb:
        route_good = (
            "The main slowdown aligned with rising elevation and greater effort. "
            "Phoenix therefore interprets it as terrain-driven rather than a sudden "
            "loss of fitness."
        )
    elif coasting:
        route_good = (
            "The lowest cadence and power occurred during an identifiable low-load "
            "or coasting phase, explaining the apparent drop without labelling it "
            "as fatigue."
        )
    else:
        route_good = (
            "Route coordinates are available, but Phoenix did not identify a strong "
            "terrain event that explained the workout better than the workload data."
        )

    route_watch = None
    route_watch_body = None
    if overview_watch:
        route_watch = "One signal persisted after route effects were removed"
        route_watch_body = overview_watch_body

    tabs = {
        "overview": _domain_card(
            "The workout behaved coherently",
            overview_good,
            overview_watch,
            overview_watch_body,
            evidence,
        ),
        "respiration": _domain_card(
            "Breathing matched the demands of the route",
            respiration_good,
            respiration_watch,
            respiration_watch_body,
            evidence,
        ),
        "cardiovascular": _domain_card(
            "Heart rate responded appropriately to terrain",
            cardiovascular_good,
            cardiovascular_watch,
            cardiovascular_watch_body,
            evidence,
        ),
        "thermal": _domain_card(
            "Heat was not the main limiter",
            thermal_good,
            thermal_watch,
            thermal_watch_body,
            evidence,
        ),
        "efficiency": _domain_card(
            "Easier sections were recognised as recovery, not failure",
            efficiency_good,
            efficiency_watch,
            efficiency_watch_body,
            evidence,
        ),
        "elevation": _domain_card(
            "Terrain explains the main pacing changes",
            elevation_good,
            elevation_watch,
            elevation_watch_body,
            evidence,
        ),
        "route": _domain_card(
            "Phoenix linked route, effort and recovery",
            route_good,
            route_watch,
            route_watch_body,
            evidence,
        ),
    }

    tabs["_analysis"] = analysis
    return tabs

def _confidence(
    pending: Dict[str, Any],
    merged: pd.DataFrame,
    summary: Dict[str, Any],
    xert: Dict[str, Any],
    context: Dict[str, Any],
) -> Tuple[int, str]:
    checkin = context.get("checkin") or {}
    metrics = context.get("metrics") or {}
    available = {
        "timeline": not merged.empty,
        "xert": bool(xert),
        "checkin": bool(checkin),
        "historical_health": any(metrics.values()),
        "heart_rate": summary.get("avg_heart_rate") is not None,
        "power_or_noncycling": (
            summary.get("avg_power") is not None
            or pending.get("session_type") != "Cycling"
        ),
        "breathing": summary.get("avg_breathing_rate") is not None,
        "thermal": summary.get("max_core_temperature_c") is not None,
    }
    score = round(100 * sum(available.values()) / len(available))
    if score >= 85:
        label = "High"
    elif score >= 60:
        label = "Moderate"
    else:
        label = "Limited"
    return score, label



def build_workout_insights(
    pending: Dict[str, Any],
    merged: pd.DataFrame,
    summary: Dict[str, Any],
    xert_summary: Optional[Dict[str, Any]] = None,
) -> WorkoutInsight:
    xert = xert_summary or {}
    context = build_historical_workout_context(pending, xert)
    morning = _morning_state(context)
    signals = _timeline_signals(merged)
    category, label = _classify_session(pending, xert)

    goal = _goal_section(category, label, morning, signals)
    noticed, positives, watchouts = _noticed_section(signals, summary)

    personal_noticed = _surprise_section(
        category=category,
        summary=summary,
        signals=signals,
        context=context,
    )
    if personal_noticed is not None:
        noticed = personal_noticed

    bigger = _bigger_picture_section(
        category, context, morning, positives, watchouts
    )
    next_step = _next_step_section(category, morning, watchouts)
    looking_ahead = _looking_ahead_section(
        category, context, positives, watchouts
    )
    score, confidence_label = _confidence(
        pending, merged, summary, xert, context
    )

    return WorkoutInsight(
        goal_assessment=goal,
        phoenix_noticed=noticed,
        bigger_picture=bigger,
        next_step=next_step,
        looking_ahead=looking_ahead,
        positives=positives,
        watchouts=watchouts,
        confidence=score,
        confidence_label=confidence_label,
        context=context,
        signals=signals,
    )



def build_intelligent_workout_summary(
    pending: Dict[str, Any],
    merged: pd.DataFrame,
    summary: Dict[str, Any],
    xert_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Backward-compatible entry point used by the Streamlit page and saver."""
    insight = build_workout_insights(
        pending=pending,
        merged=merged,
        summary=summary,
        xert_summary=xert_summary,
    )
    result = insight.to_dict()
    result["headline"] = "Phoenix Coach"
    result["objective_assessment"] = insight.goal_assessment.body
    result["paragraphs"] = [
        insight.goal_assessment.body,
        insight.phoenix_noticed.body,
        insight.bigger_picture.body,
        insight.next_step.body,
        insight.looking_ahead.body,
    ]
    return result
