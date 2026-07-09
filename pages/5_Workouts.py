from datetime import datetime
import json

import streamlit as st

from database import init_db
from integrations.hevy import fetch_and_save_workouts, hevy_is_connected
from integrations.apple_health_json import sync_apple_workout_exports
from integrations.xert import fetch_and_save_xert_activities
from workout_database import (
    get_latest_strength_session,
    init_workout_tables,
    load_training_exercises_for_session,
    load_training_sessions,
)
from workout_engine import build_workout_summary

init_db()
init_workout_tables()

st.set_page_config(
    page_title="Workouts · Project Phoenix",
    page_icon="🏋️",
    layout="wide",
)

st.title("🏋️ Workouts")
st.caption("Project Phoenix · Workout analysis hub")


def format_date(date_string):
    if not date_string:
        return "Unknown date"

    try:
        return datetime.fromisoformat(date_string).strftime("%d %b %Y")
    except ValueError:
        return date_string


def show_not_ready_message(feature):
    st.warning(f"{feature} will be available in a future update.")


def safe_duration(duration):
    if duration is not None and str(duration) != "nan":
        return f"{duration:.1f} min"

    return "Duration unavailable"


def extract_xert_summary(session):
    try:
        raw = json.loads(session.get("raw_data") or "{}")
    except Exception:
        raw = {}

    summary = raw.get("summary", {})

    return {
        "xss": summary.get("xss"),
        "distance": summary.get("distance"),
        "np": summary.get("normalized_power"),
        "avg_power": summary.get("avg_power"),
        "difficulty": summary.get("difficulty_rating"),
    }


def get_latest_day_sessions(session_types):
    sessions = load_training_sessions(limit=300)

    if sessions.empty:
        return None, None

    filtered = sessions[sessions["session_type"].isin(session_types)]

    if filtered.empty:
        return None, None

    latest_date = filtered["session_date"].max()
    latest_day = filtered[filtered["session_date"] == latest_date].sort_values("start_time")

    return latest_date, latest_day


def get_latest_cycling_day_sessions():
    return get_latest_day_sessions(["Cycling"])


def get_latest_movement_day_sessions():
    return get_latest_day_sessions(["Walking", "Hiking", "Running", "Mobility", "Other"])


def show_latest_cycling_day():
    latest_date, rides = get_latest_cycling_day_sessions()

    if rides is None or rides.empty:
        st.write("No cycling workouts recorded yet.")
        return None

    st.write(f"**{format_date(latest_date)}**")
    st.caption(f"{len(rides)} cycling activities from Xert")

    total_minutes = rides["duration_minutes"].fillna(0).sum()
    st.write(f"⏱ Total: **{total_minutes:.1f} min**")

    for _, ride in rides.iterrows():
        xert = extract_xert_summary(ride)

        with st.container(border=True):
            st.write(f"**{ride['title']}**")
            st.write(f"⏱ {safe_duration(ride.get('duration_minutes'))}")

            details = []

            if xert["distance"] is not None:
                details.append(f"{xert['distance']:.1f} km")

            if xert["xss"] is not None:
                details.append(f"XSS {xert['xss']:.1f}")

            if xert["np"] is not None:
                details.append(f"NP {xert['np']:.0f} W")

            if xert["difficulty"]:
                details.append(f"Difficulty: {xert['difficulty']}")

            if details:
                st.caption(" · ".join(details))

    return rides


def show_latest_movement_day():
    latest_date, movements = get_latest_movement_day_sessions()

    if movements is None or movements.empty:
        st.write("No other movement recorded yet.")
        return None

    st.write(f"**{format_date(latest_date)}**")
    st.caption(f"{len(movements)} movement activities")

    total_minutes = movements["duration_minutes"].fillna(0).sum()
    st.write(f"⏱ Total: **{total_minutes:.1f} min**")

    for _, movement in movements.iterrows():
        with st.container(border=True):
            st.write(f"**{movement['title'] or movement['session_type']}**")
            st.write(f"⏱ {safe_duration(movement.get('duration_minutes'))}")
            st.caption(f"{movement['session_type']} · Source: {movement['source']}")

    return movements


def format_strength_line(sets_count, average_reps, max_weight):
    if max_weight > 0:
        return f"{sets_count} × {average_reps} @ {max_weight:.0f} kg"

    return f"{sets_count} × {average_reps} bodyweight"


def show_exercise_summary(exercises):
    if exercises.empty:
        st.write("No exercise details available yet.")
        return

    st.write("**Exercises**")

    for _, exercise in exercises.iterrows():
        name = exercise["exercise_name"]
        sets_count = int(exercise["sets_count"] or 0)
        total_reps = int(exercise["total_reps"] or 0)
        total_volume = exercise["total_volume_kg"] or 0
        max_weight = exercise["max_weight_kg"] or 0
        duration_seconds = exercise["duration_seconds"] or 0

        average_reps = round(total_reps / sets_count) if sets_count else 0

        with st.container(border=True):
            st.write(f"**{name}**")

            if duration_seconds and total_reps == 0:
                st.write(f"{sets_count} × {duration_seconds / sets_count:.0f} sec")
            elif max_weight > 0:
                st.write(format_strength_line(sets_count, average_reps, max_weight))
                st.caption(f"{total_volume:.0f} kg total volume")
            else:
                st.write(format_strength_line(sets_count, average_reps, max_weight))
                st.caption(f"{total_reps} total reps")


def show_strength_latest():
    latest = get_latest_strength_session()

    if latest is None:
        st.write("No strength sessions recorded yet.")
        return None, None

    exercises = load_training_exercises_for_session(latest["id"])

    st.write(f"**{latest['title'] or 'Untitled strength session'}**")
    st.write(f"📅 {format_date(latest['session_date'])}")
    st.write(f"⏱ {safe_duration(latest.get('duration_minutes'))}")
    st.write(f"🏋️ {len(exercises)} exercises")
    st.caption(f"Source: {latest['source']}")

    return latest, exercises

# ---------------------------------------------------------------------
# Phoenix interpretation
# ---------------------------------------------------------------------

st.divider()

st.subheader("🧠 Phoenix Interpretation")

workout_summary = build_workout_summary()

with st.container(border=True):
    st.write(f"**Training day: {format_date(workout_summary['date'])}**")

    if not workout_summary["has_training"]:
        st.write(workout_summary["summary"])
    else:
        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric(
                "Cycling",
                f"{workout_summary['cycling_minutes']:.1f} min",
                f"XSS {workout_summary['cycling_xss']:.1f}",
            )

        with c2:
            st.metric(
                "Strength",
                f"{workout_summary['strength_minutes']:.1f} min",
                f"{workout_summary['strength_count']} session(s)",
            )

        with c3:
            st.metric(
                "Movement",
                f"{workout_summary['movement_minutes']:.1f} min",
                f"{workout_summary['movement_count']} session(s)",
            )

        st.write("**Interpretation**")
        st.write(workout_summary["interpretation"])

# ---------------------------------------------------------------------
# Cycling
# ---------------------------------------------------------------------

st.divider()

st.header("🚴 Cycling")
st.caption("Primary training source. Phoenix uses Xert without trying to replace Xert.")

with st.container(border=True):
    c1, c2, c3 = st.columns(3)

    with c1:
        st.subheader("Latest cycling day")
        latest_rides = show_latest_cycling_day()

    with c2:
        st.subheader("Cycling strain")
        if latest_rides is None:
            st.write("No cycling strain calculated yet.")
        else:
            total_xss = 0
            for _, ride in latest_rides.iterrows():
                xert = extract_xert_summary(ride)
                if xert["xss"] is not None:
                    total_xss += xert["xss"]

            st.write(f"Total XSS: **{total_xss:.1f}**")
            st.caption("Warm-ups and cool-downs included for now.")

    with c3:
        st.subheader("Core Temp overlay")
        st.write("Planned for cycling workouts.")

    st.write("**Phoenix role**")
    st.write(
        "Cycling analysis will focus on what the ride means for readiness, "
        "recovery, and the daily coaching decision. Xert remains the specialist "
        "cycling platform; Phoenix acts as the interpretation layer."
    )

    c1, c2 = st.columns(2)

    with c1:
        if st.button("🔄 Sync Xert rides", key="sync_xert"):
            with st.spinner("Syncing Xert rides..."):
                summary = fetch_and_save_xert_activities(days=60)

            st.success(
                f"Xert sync complete: {summary['imported']} imported, "
                f"{summary['duplicates']} duplicates, "
                f"{summary['skipped']} skipped, "
                f"{summary['apple_duplicates_removed']} Apple duplicates removed."
            )
            st.rerun()

    with c2:
        if st.button("🌡 Add Core Temp data", key="core_temp"):
            show_not_ready_message("Core Temp overlay")


# ---------------------------------------------------------------------
# Strength
# ---------------------------------------------------------------------

st.divider()

st.header("💪 Strength")
st.caption("Strength is where Phoenix adds major value because Xert does not understand gym load.")

with st.container(border=True):
    c1, c2, c3 = st.columns(3)

    with c1:
        st.subheader("Latest session")
        latest_strength, latest_exercises = show_strength_latest()

    with c2:
        st.subheader("Muscle load")
        if latest_strength is None:
            st.write("No muscle load calculated yet.")
        else:
            st.write("Exercise summaries imported from Hevy.")
            st.caption("Muscle-group classification coming next.")

    with c3:
        st.subheader("Recovery cost")
        if latest_strength is None:
            st.write("No recovery cost estimated yet.")
        else:
            st.write("Recovery cost engine planned.")
            st.caption("This will use duration, exercise type, volume and recent readiness.")

    st.write("**Phoenix role**")
    st.write(
        "Strength analysis will track muscle groups, RPE, soreness risk, "
        "grip strength, and whether lifting supports or conflicts with cycling freshness."
    )

    if hevy_is_connected():
        if st.button("🔄 Sync Hevy workouts", key="sync_hevy"):
            with st.spinner("Syncing Hevy workouts..."):
                summary = fetch_and_save_workouts(page=1, page_size=10)

            st.success(
                f"Hevy sync complete: {summary['imported']} imported, "
                f"{summary['duplicates']} duplicates, {summary['total_seen']} seen."
            )
            st.rerun()
    else:
        st.warning("Hevy API key is not configured.")

    if latest_strength is not None:
        st.divider()
        show_exercise_summary(latest_exercises)


# ---------------------------------------------------------------------
# Other movement
# ---------------------------------------------------------------------

st.divider()

st.header("🚶 Other Movement")
st.caption("Walking, mobility, hiking, recovery movement, and other non-primary activities.")

with st.container(border=True):
    c1, c2, c3 = st.columns(3)

    with c1:
        st.subheader("Latest movement day")
        latest_movements = show_latest_movement_day()

    with c2:
        st.subheader("Recovery support")
        if latest_movements is None:
            st.write("No recovery-support activity recorded yet.")
        else:
            st.write("Apple movement sessions imported.")
            st.caption("Walking, yoga and mobility will feed the recovery context.")

    with c3:
        st.subheader("Fatigue risk")
        if latest_movements is None:
            st.write("No fatigue risk estimated yet.")
        else:
            total_minutes = latest_movements["duration_minutes"].fillna(0).sum()
            st.write(f"Total movement: **{total_minutes:.1f} min**")
            st.caption("Long walks and hikes may eventually affect recovery.")

    st.write("**Phoenix role**")
    st.write(
        "Other movement should provide context without becoming fake strain. "
        "A walk can support recovery, but steps alone should not drive training decisions."
    )

    c1, c2 = st.columns(2)

    with c1:
        if st.button("🔄 Sync Apple workouts", key="sync_apple_workouts"):
            with st.spinner("Syncing Apple workouts..."):
                summary = sync_apple_workout_exports()

            st.success(
                f"Apple workout sync complete: {summary['imported']} imported, "
                f"{summary['duplicates']} duplicates, {summary['files_seen']} files seen."
            )
            st.rerun()

    with c2:
        if st.button("➕ Log other movement", key="movement"):
            show_not_ready_message("Other movement logging")
