from dataclasses import asdict, is_dataclass
from datetime import datetime
import json
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import streamlit as st

from database import init_db
from integrations.apple_health_json import sync_apple_workout_exports
from integrations.hevy import fetch_and_save_workouts, hevy_is_connected
from integrations.xert import fetch_and_save_xert_activities
from workout_database import (
    get_latest_strength_session,
    init_workout_tables,
    load_training_exercises_for_session,
    load_training_sessions,
)
from workout_engine import build_workout_summary
from workout_intelligence import build_workout_intelligence


# ---------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="Workouts · Project Phoenix",
    page_icon="🏋️",
    layout="wide",
)

init_db()
init_workout_tables()

st.title("🏋️ Workouts")
st.caption(
    "Project Phoenix · What you did, what it means, and what comes next"
)


# ---------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------

def format_date(value: Any) -> str:
    if value is None or value == "":
        return "Unknown date"

    try:
        return datetime.fromisoformat(str(value)).strftime("%d %b %Y")
    except (TypeError, ValueError):
        return str(value)


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value is None or pd.isna(value):
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def safe_duration(value: Any) -> str:
    if value is None:
        return "Duration unavailable"

    try:
        if pd.isna(value):
            return "Duration unavailable"
    except (TypeError, ValueError):
        pass

    try:
        return f"{float(value):.1f} min"
    except (TypeError, ValueError):
        return "Duration unavailable"


def clean_text(
    value: Any,
    fallback: str = "Not available",
) -> str:
    if value is None:
        return fallback

    text = str(value).strip()

    if not text:
        return fallback

    return text


def humanise_label(value: Any) -> str:
    text = clean_text(value, "Unknown")
    return text.replace("_", " ").strip().title()


def show_not_ready_message(feature: str) -> None:
    st.warning(
        f"{feature} will be available in a future update."
    )


def object_to_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if hasattr(value, "to_dict") and callable(value.to_dict):
        converted = value.to_dict()

        if isinstance(converted, dict):
            return converted

    if is_dataclass(value):
        return asdict(value)

    if hasattr(value, "__dict__"):
        return dict(value.__dict__)

    return {}


# ---------------------------------------------------------------------
# Xert helpers
# ---------------------------------------------------------------------

def extract_xert_summary(
    session: Any,
) -> Dict[str, Any]:
    try:
        raw = json.loads(
            session.get("raw_data") or "{}"
        )
    except (
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        raw = {}

    summary = raw.get("summary") or {}

    return {
        "xss": summary.get("xss"),
        "distance": summary.get("distance"),
        "np": summary.get("normalized_power"),
        "avg_power": summary.get("avg_power"),
        "difficulty": summary.get(
            "difficulty_rating"
        ),
    }


# ---------------------------------------------------------------------
# Session loading helpers
# ---------------------------------------------------------------------

def get_latest_day_sessions(
    session_types: list[str],
) -> Tuple[
    Optional[Any],
    Optional[pd.DataFrame],
]:
    sessions = load_training_sessions(
        limit=300
    )

    if sessions is None or sessions.empty:
        return None, None

    if "session_type" not in sessions.columns:
        return None, None

    filtered = sessions[
        sessions["session_type"].isin(
            session_types
        )
    ].copy()

    if filtered.empty:
        return None, None

    filtered = filtered.dropna(
        subset=["session_date"]
    )

    if filtered.empty:
        return None, None

    latest_date = filtered[
        "session_date"
    ].max()

    latest_day = filtered[
        filtered["session_date"]
        == latest_date
    ].copy()

    if "start_time" in latest_day.columns:
        latest_day = latest_day.sort_values(
            "start_time",
            na_position="last",
        )

    return latest_date, latest_day


def get_latest_cycling_day_sessions():
    return get_latest_day_sessions(
        ["Cycling"]
    )


def get_latest_movement_day_sessions():
    return get_latest_day_sessions(
        [
            "Walking",
            "Hiking",
            "Running",
            "Mobility",
            "Yoga",
            "Other",
        ]
    )


# ---------------------------------------------------------------------
# Workout Intelligence data handoff
# ---------------------------------------------------------------------

def build_latest_day_workout_records(
    workout_summary: Dict[str, Any],
) -> list[Dict[str, Any]]:
    """
    Build normalized workout records for the same training day shown
    in the Phoenix overview.

    Workout Intelligence interprets these records. It does not fetch
    workout data itself.
    """
    training_date = workout_summary.get(
        "date"
    )

    if not training_date:
        return []

    sessions = load_training_sessions(
        limit=300
    )

    if sessions is None or sessions.empty:
        return []

    if "session_date" not in sessions.columns:
        return []

    day_sessions = sessions[
        sessions["session_date"].astype(str)
        == str(training_date)
    ].copy()

    if day_sessions.empty:
        return []

    workout_records = []

    for _, session in day_sessions.iterrows():
        session_type = clean_text(
            session.get("session_type"),
            "Other",
        )

        record = {
            "name": clean_text(
                session.get("title"),
                session_type,
            ),
            "session_type": session_type,
            "source": clean_text(
                session.get("source"),
                "Unknown",
            ),
            "duration_minutes": safe_float(
                session.get(
                    "duration_minutes"
                )
            ),
            "xss": None,
            "distance_km": None,
            "intensity_factor": None,
            "difficulty": None,
        }

        if session_type == "Cycling":
            xert = extract_xert_summary(
                session
            )

            record["xss"] = xert.get(
                "xss"
            )

            record["distance_km"] = (
                xert.get("distance")
            )

            record["difficulty"] = (
                xert.get("difficulty")
            )

        workout_records.append(record)

    return workout_records


def build_current_workout_intelligence(
    workout_summary: Dict[str, Any],
) -> Tuple[
    Optional[Any],
    Optional[str],
]:
    """
    Generate Workout Intelligence for the same latest training day
    shown in the factual workout summary.
    """
    try:
        workout_records = (
            build_latest_day_workout_records(
                workout_summary
            )
        )

        intelligence = (
            build_workout_intelligence(
                workouts=workout_records,
            )
        )

        return intelligence, None

    except Exception as exc:
        return None, str(exc)


# ---------------------------------------------------------------------
# Phoenix training-day summary
# ---------------------------------------------------------------------

def render_training_summary(
    workout_summary: Dict[str, Any],
) -> None:
    st.subheader("Latest training day")

    with st.container(border=True):
        training_date = (
            workout_summary.get("date")
        )

        st.write(
            f"**{format_date(training_date)}**"
        )

        if not workout_summary.get(
            "has_training",
            False,
        ):
            st.info(
                clean_text(
                    workout_summary.get(
                        "summary"
                    ),
                    (
                        "No training was recorded "
                        "for the latest day."
                    ),
                )
            )
            return

        cycling_minutes = safe_float(
            workout_summary.get(
                "cycling_minutes"
            )
        )

        cycling_xss = safe_float(
            workout_summary.get(
                "cycling_xss"
            )
        )

        strength_minutes = safe_float(
            workout_summary.get(
                "strength_minutes"
            )
        )

        strength_count = int(
            safe_float(
                workout_summary.get(
                    "strength_count"
                )
            )
        )

        movement_minutes = safe_float(
            workout_summary.get(
                "movement_minutes"
            )
        )

        movement_count = int(
            safe_float(
                workout_summary.get(
                    "movement_count"
                )
            )
        )

        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric(
                "Cycling",
                f"{cycling_minutes:.1f} min",
                f"XSS {cycling_xss:.1f}",
            )

        with c2:
            st.metric(
                "Strength",
                f"{strength_minutes:.1f} min",
                (
                    f"{strength_count} "
                    "session(s)"
                ),
            )

        with c3:
            st.metric(
                "Other movement",
                f"{movement_minutes:.1f} min",
                (
                    f"{movement_count} "
                    "session(s)"
                ),
            )

        interpretation = (
            workout_summary.get(
                "interpretation"
            )
        )

        if interpretation:
            st.write("**Day summary**")
            st.write(interpretation)


# ---------------------------------------------------------------------
# Workout Intelligence display
# ---------------------------------------------------------------------

def render_list_section(
    title: str,
    values: Any,
    empty_message: Optional[str] = None,
) -> None:
    st.write(f"**{title}**")

    if not values:
        if empty_message:
            st.caption(empty_message)

        return

    if isinstance(values, str):
        values = [values]

    for value in values:
        if value:
            st.write(f"• {value}")


def render_workout_intelligence(
    intelligence_result: Any,
    error_message: Optional[str],
) -> None:
    st.subheader(
        "🧠 Workout Intelligence"
    )

    st.caption(
        "Phoenix combines every recorded session from the latest "
        "training day and interprets what the day means as a whole."
    )

    if error_message:
        with st.container(border=True):
            st.error(
                "Workout Intelligence could not be generated."
            )
            st.caption(error_message)

        return

    intelligence = object_to_dict(
        intelligence_result
    )

    if not intelligence:
        with st.container(border=True):
            st.info(
                "Workout Intelligence returned no result for the "
                "latest training day."
            )

        return

    training_type = humanise_label(
        intelligence.get(
            "training_type"
        )
    )

    primary_session = humanise_label(
        intelligence.get(
            "primary_session"
        )
    )

    primary_focus = humanise_label(
        intelligence.get(
            "primary_focus"
        )
    )

    load = humanise_label(
        intelligence.get("load")
    )

    quality = humanise_label(
        intelligence.get("quality")
    )

    fatigue = humanise_label(
        intelligence.get(
            "fatigue_generated"
        )
    )

    fitness_effect = humanise_label(
        intelligence.get(
            "fitness_effect"
        )
    )

    goal_progress = humanise_label(
        intelligence.get(
            "goal_progress"
        )
    )

    confidence_raw = safe_float(
        intelligence.get(
            "confidence"
        ),
        default=0.0,
    )

    if confidence_raw <= 1:
        confidence_percent = (
            confidence_raw * 100
        )
    else:
        confidence_percent = (
            confidence_raw
        )

    with st.container(border=True):
        top_left, top_middle, top_right = (
            st.columns(
                [1.45, 1, 1]
            )
        )

        with top_left:
            st.caption(
                "Training-day classification"
            )

            st.markdown(
                f"### {training_type}"
            )

            st.write(
                clean_text(
                    intelligence.get(
                        "summary"
                    )
                )
            )

        with top_middle:
            st.metric(
                "Primary session",
                primary_session,
            )

            st.metric(
                "Primary focus",
                primary_focus,
            )

        with top_right:
            st.metric(
                "Daily load",
                load,
            )

            st.metric(
                "Confidence",
                f"{confidence_percent:.0f}%",
            )

        st.divider()

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.write(
                "**Workout quality**"
            )
            st.write(quality)

        with c2:
            st.write(
                "**Fatigue generated**"
            )
            st.write(fatigue)

        with c3:
            st.write(
                "**Fitness effect**"
            )
            st.write(fitness_effect)

        with c4:
            st.write(
                "**Goal progress**"
            )
            st.write(goal_progress)

        signals = (
            intelligence.get(
                "signals"
            )
            or []
        )

        recommendations = (
            intelligence.get(
                "recommendations"
            )
            or []
        )

        if signals or recommendations:
            st.divider()

            left, right = st.columns(2)

            with left:
                render_list_section(
                    "What Phoenix noticed",
                    signals,
                    (
                        "No notable signals "
                        "were identified."
                    ),
                )

            with right:
                render_list_section(
                    "Coaching guidance",
                    recommendations,
                    (
                        "No additional "
                        "recommendation is needed."
                    ),
                )


# ---------------------------------------------------------------------
# Cycling display
# ---------------------------------------------------------------------

def show_latest_cycling_day():
    latest_date, rides = (
        get_latest_cycling_day_sessions()
    )

    if rides is None or rides.empty:
        st.write(
            "No cycling workouts recorded yet."
        )
        return None

    st.write(
        f"**{format_date(latest_date)}**"
    )

    st.caption(
        f"{len(rides)} cycling activities from Xert"
    )

    total_minutes = (
        rides["duration_minutes"]
        .fillna(0)
        .sum()
    )

    st.write(
        f"⏱ Total: **{total_minutes:.1f} min**"
    )

    for _, ride in rides.iterrows():
        xert = extract_xert_summary(
            ride
        )

        with st.container(border=True):
            title = clean_text(
                ride.get("title"),
                "Untitled cycling activity",
            )

            st.write(f"**{title}**")

            st.write(
                f"⏱ "
                f"{safe_duration(ride.get('duration_minutes'))}"
            )

            details = []

            if xert["distance"] is not None:
                details.append(
                    f"{safe_float(xert['distance']):.1f} km"
                )

            if xert["xss"] is not None:
                details.append(
                    f"XSS "
                    f"{safe_float(xert['xss']):.1f}"
                )

            if xert["np"] is not None:
                details.append(
                    f"NP "
                    f"{safe_float(xert['np']):.0f} W"
                )

            if xert["avg_power"] is not None:
                details.append(
                    f"Avg "
                    f"{safe_float(xert['avg_power']):.0f} W"
                )

            if xert["difficulty"]:
                details.append(
                    f"Difficulty: "
                    f"{xert['difficulty']}"
                )

            if details:
                st.caption(
                    " · ".join(details)
                )

    return rides


def calculate_total_xss(
    rides: Optional[pd.DataFrame],
) -> float:
    if rides is None or rides.empty:
        return 0.0

    total_xss = 0.0

    for _, ride in rides.iterrows():
        xert = extract_xert_summary(
            ride
        )

        total_xss += safe_float(
            xert.get("xss")
        )

    return total_xss


# ---------------------------------------------------------------------
# Strength display
# ---------------------------------------------------------------------

def format_strength_line(
    sets_count: int,
    average_reps: int,
    max_weight: float,
) -> str:
    if max_weight > 0:
        return (
            f"{sets_count} × "
            f"{average_reps} "
            f"@ {max_weight:.0f} kg"
        )

    return (
        f"{sets_count} × "
        f"{average_reps} bodyweight"
    )


def show_exercise_summary(
    exercises: pd.DataFrame,
) -> None:
    if (
        exercises is None
        or exercises.empty
    ):
        st.write(
            "No exercise details available yet."
        )
        return

    st.write("**Exercises**")

    for _, exercise in exercises.iterrows():
        name = clean_text(
            exercise.get(
                "exercise_name"
            ),
            "Unnamed exercise",
        )

        sets_count = int(
            safe_float(
                exercise.get(
                    "sets_count"
                )
            )
        )

        total_reps = int(
            safe_float(
                exercise.get(
                    "total_reps"
                )
            )
        )

        total_volume = safe_float(
            exercise.get(
                "total_volume_kg"
            )
        )

        max_weight = safe_float(
            exercise.get(
                "max_weight_kg"
            )
        )

        duration_seconds = safe_float(
            exercise.get(
                "duration_seconds"
            )
        )

        average_reps = (
            round(
                total_reps
                / sets_count
            )
            if sets_count
            else 0
        )

        with st.container(border=True):
            st.write(f"**{name}**")

            if (
                duration_seconds > 0
                and total_reps == 0
            ):
                average_seconds = (
                    duration_seconds
                    / sets_count
                    if sets_count
                    else duration_seconds
                )

                st.write(
                    f"{sets_count} × "
                    f"{average_seconds:.0f} sec"
                )

            elif max_weight > 0:
                st.write(
                    format_strength_line(
                        sets_count,
                        average_reps,
                        max_weight,
                    )
                )

                st.caption(
                    f"{total_volume:.0f} kg "
                    "total volume"
                )

            else:
                st.write(
                    format_strength_line(
                        sets_count,
                        average_reps,
                        max_weight,
                    )
                )

                st.caption(
                    f"{total_reps} total reps"
                )


def show_strength_latest():
    latest = (
        get_latest_strength_session()
    )

    if latest is None:
        st.write(
            "No strength sessions recorded yet."
        )
        return None, None

    exercises = (
        load_training_exercises_for_session(
            latest["id"]
        )
    )

    title = clean_text(
        latest.get("title"),
        "Untitled strength session",
    )

    st.write(f"**{title}**")

    st.write(
        f"📅 "
        f"{format_date(latest.get('session_date'))}"
    )

    st.write(
        f"⏱ "
        f"{safe_duration(latest.get('duration_minutes'))}"
    )

    st.write(
        f"🏋️ {len(exercises)} exercises"
    )

    st.caption(
        f"Source: "
        f"{clean_text(latest.get('source'))}"
    )

    return latest, exercises


# ---------------------------------------------------------------------
# Other movement display
# ---------------------------------------------------------------------

def show_latest_movement_day():
    latest_date, movements = (
        get_latest_movement_day_sessions()
    )

    if (
        movements is None
        or movements.empty
    ):
        st.write(
            "No other movement recorded yet."
        )
        return None

    st.write(
        f"**{format_date(latest_date)}**"
    )

    st.caption(
        f"{len(movements)} movement activities"
    )

    total_minutes = (
        movements["duration_minutes"]
        .fillna(0)
        .sum()
    )

    st.write(
        f"⏱ Total: **{total_minutes:.1f} min**"
    )

    for _, movement in movements.iterrows():
        title = clean_text(
            movement.get("title"),
            clean_text(
                movement.get(
                    "session_type"
                ),
                "Movement activity",
            ),
        )

        session_type = clean_text(
            movement.get(
                "session_type"
            ),
            "Other",
        )

        source = clean_text(
            movement.get("source"),
            "Unknown",
        )

        with st.container(border=True):
            st.write(
                f"**{title}**"
            )

            st.write(
                f"⏱ "
                f"{safe_duration(movement.get('duration_minutes'))}"
            )

            st.caption(
                f"{session_type} · "
                f"Source: {source}"
            )

    return movements


# ---------------------------------------------------------------------
# Build Phoenix interpretation
# ---------------------------------------------------------------------

try:
    workout_summary = (
        build_workout_summary()
    )

except Exception as exc:
    workout_summary = {
        "date": None,
        "has_training": False,
        "summary": (
            "The workout summary could not be generated."
        ),
        "interpretation": "",
        "cycling_minutes": 0.0,
        "cycling_xss": 0.0,
        "strength_minutes": 0.0,
        "strength_count": 0,
        "movement_minutes": 0.0,
        "movement_count": 0,
    }

    workout_summary_error = str(exc)

else:
    workout_summary_error = None


(
    workout_intelligence,
    workout_intelligence_error,
) = build_current_workout_intelligence(
    workout_summary
)


# ---------------------------------------------------------------------
# Phoenix overview
# ---------------------------------------------------------------------

st.divider()

render_training_summary(
    workout_summary
)

if workout_summary_error:
    st.caption(
        "Workout summary diagnostic: "
        f"{workout_summary_error}"
    )

st.divider()

render_workout_intelligence(
    workout_intelligence,
    workout_intelligence_error,
)


# ---------------------------------------------------------------------
# Cycling
# ---------------------------------------------------------------------

st.divider()

st.header("🚴 Cycling")

st.caption(
    "Xert remains the specialist cycling platform. "
    "Phoenix interprets what each ride means for recovery, "
    "readiness and the coaching decision."
)

with st.container(border=True):
    c1, c2, c3 = st.columns(3)

    with c1:
        st.subheader(
            "Latest cycling day"
        )

        latest_rides = (
            show_latest_cycling_day()
        )

    with c2:
        st.subheader(
            "Cycling strain"
        )

        if latest_rides is None:
            st.write(
                "No cycling strain calculated yet."
            )

        else:
            total_xss = (
                calculate_total_xss(
                    latest_rides
                )
            )

            total_minutes = (
                latest_rides[
                    "duration_minutes"
                ]
                .fillna(0)
                .sum()
            )

            st.metric(
                "Total XSS",
                f"{total_xss:.1f}",
            )

            st.caption(
                f"{total_minutes:.1f} minutes of cycling. "
                "Warm-ups and cool-downs are currently included."
            )

    with c3:
        st.subheader(
            "CORE temperature"
        )

        st.write(
            "Workout overlay planned."
        )

        st.caption(
            "CORE data will eventually add heat-strain "
            "context to cycling analysis."
        )

    st.divider()

    st.write("**Phoenix role**")

    st.write(
        "Phoenix does not try to reproduce Xert's specialist "
        "power analysis. It uses the resulting workout load as "
        "one input when interpreting fatigue, fitness effect and "
        "the appropriate next training decision."
    )

    c1, c2 = st.columns(2)

    with c1:
        if st.button(
            "🔄 Sync Xert rides",
            key="sync_xert",
            use_container_width=True,
        ):
            with st.spinner(
                "Syncing Xert rides..."
            ):
                try:
                    summary = (
                        fetch_and_save_xert_activities(
                            days=60
                        )
                    )

                except Exception as exc:
                    st.error(
                        f"Xert sync failed: {exc}"
                    )

                else:
                    st.success(
                        "Xert sync complete: "
                        f"{summary.get('imported', 0)} imported, "
                        f"{summary.get('duplicates', 0)} duplicates, "
                        f"{summary.get('skipped', 0)} skipped, "
                        f"{summary.get('apple_duplicates_removed', 0)} "
                        "Apple duplicates removed."
                    )

                    st.rerun()

    with c2:
        if st.button(
            "🌡 Add CORE Temp data",
            key="core_temp",
            use_container_width=True,
        ):
            show_not_ready_message(
                "CORE Temp overlay"
            )


# ---------------------------------------------------------------------
# Strength
# ---------------------------------------------------------------------

st.divider()

st.header("💪 Strength")

st.caption(
    "Phoenix adds context that cycling platforms cannot provide: "
    "exercise load, muscle stress and interaction with cycling recovery."
)

with st.container(border=True):
    c1, c2, c3 = st.columns(3)

    with c1:
        st.subheader(
            "Latest session"
        )

        (
            latest_strength,
            latest_exercises,
        ) = show_strength_latest()

    with c2:
        st.subheader(
            "Strength load"
        )

        if latest_strength is None:
            st.write(
                "No strength load available yet."
            )

        else:
            st.write(
                "Exercise and volume data imported from Hevy."
            )

            st.caption(
                "Muscle-group classification is a future "
                "Workout Intelligence extension."
            )

    with c3:
        st.subheader(
            "Recovery context"
        )

        if latest_strength is None:
            st.write(
                "No strength recovery context available."
            )

        else:
            st.write(
                "The session contributes to the daily "
                "workout summary and Workout Intelligence result."
            )

            st.caption(
                "Future versions can estimate local muscle "
                "fatigue and soreness risk."
            )

    st.divider()

    st.write("**Phoenix role**")

    st.write(
        "Strength training should be interpreted in relation to "
        "the athlete's wider goals. Phoenix will ultimately track "
        "which muscles were trained, the likely recovery demand, "
        "and whether lifting supports or conflicts with planned "
        "cycling."
    )

    if hevy_is_connected():
        if st.button(
            "🔄 Sync Hevy workouts",
            key="sync_hevy",
            use_container_width=True,
        ):
            with st.spinner(
                "Syncing Hevy workouts..."
            ):
                try:
                    summary = (
                        fetch_and_save_workouts(
                            page=1,
                            page_size=10,
                        )
                    )

                except Exception as exc:
                    st.error(
                        f"Hevy sync failed: {exc}"
                    )

                else:
                    st.success(
                        "Hevy sync complete: "
                        f"{summary.get('imported', 0)} imported, "
                        f"{summary.get('duplicates', 0)} duplicates, "
                        f"{summary.get('total_seen', 0)} seen."
                    )

                    st.rerun()

    else:
        st.warning(
            "Hevy API key is not configured."
        )

    if latest_strength is not None:
        st.divider()

        show_exercise_summary(
            latest_exercises
        )


# ---------------------------------------------------------------------
# Other movement
# ---------------------------------------------------------------------

st.divider()

st.header("🚶 Other Movement")

st.caption(
    "Walking, hiking, running, yoga, mobility and other "
    "non-primary activities."
)

with st.container(border=True):
    c1, c2, c3 = st.columns(3)

    with c1:
        st.subheader(
            "Latest movement day"
        )

        latest_movements = (
            show_latest_movement_day()
        )

    with c2:
        st.subheader(
            "Recovery support"
        )

        if latest_movements is None:
            st.write(
                "No recovery-support activity recorded yet."
            )

        else:
            st.write(
                "Movement sessions provide context for recovery "
                "without automatically becoming training strain."
            )

            st.caption(
                "Easy walking and mobility may support recovery."
            )

    with c3:
        st.subheader(
            "Fatigue context"
        )

        if latest_movements is None:
            st.write(
                "No movement fatigue context available."
            )

        else:
            total_minutes = (
                latest_movements[
                    "duration_minutes"
                ]
                .fillna(0)
                .sum()
            )

            st.metric(
                "Movement duration",
                f"{total_minutes:.1f} min",
            )

            st.caption(
                "Long walks, hikes and runs may create meaningful "
                "fatigue; ordinary steps should not."
            )

    st.divider()

    st.write("**Phoenix role**")

    st.write(
        "Other movement provides context without creating fake "
        "strain. Phoenix should distinguish a gentle recovery walk "
        "from a long hike or run rather than treating every step as "
        "equivalent training."
    )

    c1, c2 = st.columns(2)

    with c1:
        if st.button(
            "🔄 Sync Apple workouts",
            key="sync_apple_workouts",
            use_container_width=True,
        ):
            with st.spinner(
                "Syncing Apple workouts..."
            ):
                try:
                    summary = (
                        sync_apple_workout_exports()
                    )

                except Exception as exc:
                    st.error(
                        "Apple workout sync failed: "
                        f"{exc}"
                    )

                else:
                    st.success(
                        "Apple workout sync complete: "
                        f"{summary.get('imported', 0)} imported, "
                        f"{summary.get('duplicates', 0)} duplicates, "
                        f"{summary.get('files_seen', 0)} files seen."
                    )

                    st.rerun()

    with c2:
        if st.button(
            "➕ Log other movement",
            key="movement",
            use_container_width=True,
        ):
            show_not_ready_message(
                "Manual movement logging"
            )