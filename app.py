from datetime import date, datetime
from typing import Any, Dict, Optional

import streamlit as st

from athlete_context import build_athlete_context
from coach_engine import build_coach_recommendation
from confidence_engine import build_confidence_profile
from daily_advice import build_daily_advice
from database import (
    get_latest_measurement_time,
    get_manual_wrist_temperature_for_date,
    init_db,
    load_recent_wrist_temperatures,
    save_checkin,
    save_manual_wrist_temperature,
    save_xert_status_record,
)
from freshness import (
    build_apple_health_freshness,
    build_withings_freshness,
)
from health_intelligence import build_health_intelligence
from integrations.weather import fetch_weather
from integrations.withings import (
    build_authorization_url,
    exchange_code_for_tokens,
    save_tokens,
    stored_tokens_are_valid,
    withings_is_connected,
)
from integrations.xert import (
    connect_xert,
    fetch_and_save_xert_status,
    xert_is_connected,
)
from morning_brief import build_morning_brief
from readiness_engine import build_readiness_profile
from recovery_engine import build_recovery_profile
from snapshot import build_morning_snapshot
from strain_engine import build_daily_strain
from sync import (
    sync_apple_health_autosync_once_per_session,
    sync_withings_once_per_session,
)
from timeline_engine import build_timeline_context
from version import PHOENIX_VERSION_LABEL
from weather_intelligence import build_weather_intelligence
from workout_engine import (
    build_latest_completed_workout_intelligence,
)


# ---------------------------------------------------------------------
# Page and database setup
# ---------------------------------------------------------------------

init_db()

st.set_page_config(
    page_title="Phoenix",
    page_icon="🔥",
    layout="wide",
)


# ---------------------------------------------------------------------
# General safe helpers
# ---------------------------------------------------------------------

def safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_get(
    source: Any,
    key: str,
    default: Any = None,
) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)

    return getattr(source, key, default)


def format_number(
    value: Any,
    decimals: int = 0,
    fallback: str = "—",
) -> str:
    try:
        if value is None:
            return fallback

        return f"{float(value):.{decimals}f}"

    except (TypeError, ValueError):
        return fallback


# ---------------------------------------------------------------------
# Time-aware Phoenix mode
# ---------------------------------------------------------------------

def build_day_mode(
    current_datetime: Optional[datetime] = None,
) -> Dict[str, str]:
    now = current_datetime or datetime.now()
    hour = now.hour

    if 5 <= hour < 12:
        return {
            "key": "morning",
            "greeting": "Good morning",
            "icon": "🌅",
            "focus": "What should you do today?",
            "intro": (
                "Phoenix has reviewed your overnight recovery, "
                "current health, recent training, goals, and context."
            ),
            "checkin_title": "How are you feeling this morning?",
            "checkin_button": "Complete morning check-in",
        }

    if 12 <= hour < 17:
        return {
            "key": "afternoon",
            "greeting": "Good afternoon",
            "icon": "☀️",
            "focus": "Is today still going to plan?",
            "intro": (
                "Phoenix has reviewed your current condition and "
                "what has happened so far today."
            ),
            "checkin_title": "Has anything changed since this morning?",
            "checkin_button": "Update today’s check-in",
        }

    if 17 <= hour < 22:
        return {
            "key": "evening",
            "greeting": "Good evening",
            "icon": "🌇",
            "focus": "How did today go?",
            "intro": (
                "Phoenix can help review today’s training, recovery, "
                "and what it may mean for tomorrow."
            ),
            "checkin_title": "How are you feeling this evening?",
            "checkin_button": "Update today’s check-in",
        }

    return {
        "key": "night",
        "greeting": "Good night",
        "icon": "🌙",
        "focus": "What should you know before tomorrow?",
        "intro": (
            "Phoenix has reviewed today’s strain and your current "
            "recovery context."
        ),
        "checkin_title": "Anything Phoenix should know before tomorrow?",
        "checkin_button": "Update today’s check-in",
    }


day_mode = build_day_mode()


# ---------------------------------------------------------------------
# Withings connection callback
# ---------------------------------------------------------------------

query_params = st.query_params
withings_code = query_params.get("code", None)

if withings_code:
    if stored_tokens_are_valid():
        st.query_params.clear()

    else:
        try:
            token_response = exchange_code_for_tokens(
                withings_code
            )

            save_tokens(
                token_response
            )

            st.session_state[
                "withings_synced_this_session"
            ] = False

            st.success(
                "✅ Withings connected. Tokens saved locally."
            )

            st.query_params.clear()

        except Exception as error:
            st.error(
                "Withings connection failed. Please reconnect."
            )

            st.caption(
                str(error)
            )

            st.query_params.clear()


# ---------------------------------------------------------------------
# Automatic sync
# ---------------------------------------------------------------------

sync_withings_once_per_session(
    st
)

sync_apple_health_autosync_once_per_session(
    st
)


# ---------------------------------------------------------------------
# Cached weather retrieval
# ---------------------------------------------------------------------

@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def load_weather():
    """
    Weather is cached for 15 minutes so normal Streamlit reruns do not
    repeatedly call Open-Meteo.
    """

    return fetch_weather()


weather_snapshot = load_weather()


# ---------------------------------------------------------------------
# Heading
# ---------------------------------------------------------------------

st.title(
    f"{day_mode['icon']} {day_mode['greeting']}, Nik"
)

st.caption(
    day_mode["intro"]
)

st.markdown(
    f"### {day_mode['focus']}"
)


# ---------------------------------------------------------------------
# What are you considering today?
# ---------------------------------------------------------------------

with st.container(
    border=True
):
    st.markdown(
        "#### Tell Phoenix what you are considering"
    )

    st.caption(
        "This does not commit you to a workout. It gives Phoenix "
        "the context needed to make relevant advice."
    )

    activity_options = [
        "Not sure",
        "Cycling",
        "Strength",
        "Walking",
        "Rest",
    ]

    planned_activity = st.radio(
        "What are you considering?",
        options=activity_options,
        horizontal=True,
        key="planned_activity",
    )

    training_environment = "Indoor"

    if planned_activity == "Cycling":
        training_environment = st.radio(
            "Where would you ride?",
            options=[
                "Indoor",
                "Outdoor",
                "Not sure",
            ],
            horizontal=True,
            key="training_environment",
        )

    elif planned_activity == "Walking":
        training_environment = "Outdoor"

    else:
        training_environment = "Indoor"


# ---------------------------------------------------------------------
# Build Phoenix intelligence
# ---------------------------------------------------------------------

context = build_athlete_context()
snapshot = build_morning_snapshot()
recent_workout_intelligence = (
    build_latest_completed_workout_intelligence(
        reference_date=date.today(),
    )
)

timeline_context = build_timeline_context(
    reference_date=date.today(),
    recent_days=30,
    significant_days=60,
)

baselines = (
    context.get(
        "baselines",
        {},
    )
    if isinstance(
        context,
        dict,
    )
    else {}
)

recovery_profile = build_recovery_profile(
    context
)

readiness_profile = build_readiness_profile(
    context,
    recovery_profile,
)

confidence_profile = build_confidence_profile(
    context=context,
    snapshot=snapshot,
    recovery_profile=recovery_profile,
    readiness_profile=readiness_profile,
    timeline_context=timeline_context,
    workout_intelligence=recent_workout_intelligence,
)

health = build_health_intelligence(
    context=context,
    snapshot=snapshot,
    recovery=recovery_profile,
    readiness=readiness_profile,
)

morning_brief = build_morning_brief(
    context=context,
    recovery_profile=recovery_profile,
    baselines=baselines,
    health_intelligence=health,
    workout_intelligence=recent_workout_intelligence,
)

coach_recommendation = build_coach_recommendation(
    health_intelligence=health,
    workout_intelligence=recent_workout_intelligence,
    recovery_profile=recovery_profile,
    readiness_profile=readiness_profile,
    timeline_context=timeline_context,
)

daily_strain = build_daily_strain(
    readiness_profile
)

weather_intelligence = build_weather_intelligence(
    weather_snapshot,
    training_environment=training_environment,
    activity_type=planned_activity,
)

daily_advice = build_daily_advice(
    coach_recommendation=coach_recommendation,
    weather_intelligence=weather_intelligence,
    planned_activity=planned_activity,
    training_environment=training_environment,
)


# ---------------------------------------------------------------------
# Data availability and freshness
# ---------------------------------------------------------------------

apple_result = st.session_state.get(
    "apple_health_autosync_result"
)

apple_health_available = (
    apple_result is not None
    and apple_result.get(
        "files_seen",
        0,
    ) > 0
)

withings_latest_time = get_latest_measurement_time(
    "withings"
)

withings_freshness = build_withings_freshness(
    withings_latest_time
)

apple_health_latest_time = get_latest_measurement_time(
    "apple_health"
)

apple_health_freshness = build_apple_health_freshness(
    apple_health_latest_time
)


# ---------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------

def freshness_icon(status):
    if status == "current":
        return "🟢"

    if status == "stale":
        return "🟡"

    return "🔴"


def snapshot_icon(is_done):
    return "🟢" if is_done else "🟡"


def status_card(
    title,
    icon,
    label,
    detail=None,
):
    st.markdown(
        f"**{title}**"
    )

    st.markdown(
        f"{icon} {label}"
    )

    if detail:
        st.caption(
            detail
        )


def recommendation_message_type(
    decision: str,
) -> str:
    text = str(
        decision or ""
    ).lower()

    caution_words = [
        "rest",
        "avoid",
        "recovery",
        "light",
        "easy",
        "reduce",
        "conservative",
    ]

    positive_words = [
        "train",
        "ready",
        "go",
        "build",
        "productive",
    ]

    if any(
        word in text
        for word in caution_words
    ):
        return "warning"

    if any(
        word in text
        for word in positive_words
    ):
        return "success"

    return "info"


def render_message(
    message: str,
    message_type: str = "info",
):
    if message_type == "success":
        st.success(
            message
        )

    elif message_type == "warning":
        st.warning(
            message
        )

    elif message_type == "error":
        st.error(
            message
        )

    else:
        st.info(
            message
        )


# ---------------------------------------------------------------------
# Morning / daily check-in
# ---------------------------------------------------------------------

st.divider()

st.header(
    f"💬 {day_mode['checkin_title']}"
)

st.caption(
    "Phoenix already has the measured data. Add only the things "
    "your devices cannot know."
)

with st.form(
    "daily_checkin_form"
):
    form_col1, form_col2, form_col3 = st.columns(
        3
    )

    with form_col1:
        checkin_date = st.date_input(
            "Date",
            value=date.today(),
            max_value=date.today(),
            key="daily_checkin_date",
        )

        lumen_score = st.selectbox(
            "Lumen score",
            options=[
                1,
                2,
                3,
                4,
                5,
            ],
            index=2,
            help=(
                "Leave this at 3 when no Lumen reading is available. "
                "Phoenix will show reduced data confidence."
            ),
        )

        fat_burn_percent = st.slider(
            "Estimated fat burning %",
            min_value=0,
            max_value=100,
            value=45,
        )

        carb_burn_percent = (
            100
            - fat_burn_percent
        )

        st.caption(
            f"Estimated fuel mix: "
            f"{fat_burn_percent}% fat / "
            f"{carb_burn_percent}% carbs"
        )

    with form_col2:
        energy = st.slider(
            "⚡ Energy",
            min_value=1,
            max_value=10,
            value=5,
        )

        mood = st.slider(
            "😊 Mood and motivation",
            min_value=1,
            max_value=10,
            value=5,
        )

    with form_col3:
        soreness = st.slider(
            "💪 Pain or soreness",
            min_value=1,
            max_value=10,
            value=1,
        )

        notes = st.text_area(
            "Tell Phoenix anything else",
            placeholder=(
                "For example: legs feel heavy, slept badly, "
                "slight abdominal discomfort, or feeling great."
            ),
        )

    checkin_submitted = st.form_submit_button(
        f"💾 {day_mode['checkin_button']}",
        type="primary",
    )

if checkin_submitted:
    save_checkin(
        checkin_date,
        lumen_score,
        fat_burn_percent,
        carb_burn_percent,
        energy,
        mood,
        soreness,
        notes,
    )

    st.success(
        "✅ Phoenix has updated today’s context."
    )

    st.rerun()


# ---------------------------------------------------------------------
# The Phoenix answer
# ---------------------------------------------------------------------

st.divider()

st.header(
    "🔥 What Phoenix thinks"
)

with st.container(
    border=True
):
    advice_title = daily_advice.get(
        "title",
        "Today’s recommendation",
    )

    advice_decision = daily_advice.get(
        "decision",
        "Review today’s signals",
    )

    advice_summary = daily_advice.get(
        "summary",
        (
            "Phoenix does not yet have enough information "
            "for a detailed recommendation."
        ),
    )

    advice_mode = daily_advice.get(
        "mode",
        "Monitoring",
    )

    session_type = daily_advice.get(
        "session_type",
        "Easy activity",
    )

    duration_text = daily_advice.get(
        "duration_text",
        "As appropriate",
    )

    intensity_limit = daily_advice.get(
        "intensity_limit",
        "Conservative",
    )

    training_permission = daily_advice.get(
        "training_permission",
        "Unclear",
    )

    primary_focus = daily_advice.get(
        "primary_focus",
        "General fitness",
    )

    purpose = daily_advice.get(
        "purpose",
        "",
    )

    st.markdown(
        f"### {advice_title}"
    )

    render_message(
        advice_summary,
        recommendation_message_type(
            advice_decision
        ),
    )

    top_col1, top_col2, top_col3 = st.columns(
        3
    )

    with top_col1:
        st.metric(
            "Coach mode",
            advice_mode,
        )

    with top_col2:
        st.metric(
            "Today’s decision",
            advice_decision,
        )

    with top_col3:
        st.metric(
            "Training permission",
            training_permission,
        )

    st.divider()

    plan_col1, plan_col2, plan_col3, plan_col4 = st.columns(
        4
    )

    with plan_col1:
        st.markdown(
            "**Session**"
        )

        st.write(
            session_type
        )

    with plan_col2:
        st.markdown(
            "**Duration**"
        )

        st.write(
            duration_text
        )

    with plan_col3:
        st.markdown(
            "**Intensity**"
        )

        st.write(
            intensity_limit
        )

    with plan_col4:
        st.markdown(
            "**Primary focus**"
        )

        st.write(
            primary_focus
        )

    if purpose:
        st.markdown(
            "**Why this session**"
        )

        st.write(
            purpose
        )

    execution = daily_advice.get(
        "execution"
    )

    if execution:
        st.markdown(
            "**How to approach it**"
        )

        st.write(
            execution
        )

    effort_guidance = daily_advice.get(
        "effort_guidance"
    )

    if effort_guidance:
        st.caption(
            f"Effort guidance: {effort_guidance}"
        )

    weather_context = daily_advice.get(
        "weather_context"
    )

    if weather_context:
        st.caption(
            weather_context
        )

    execution_steps = daily_advice.get(
        "execution_steps",
        [],
    )

    stop_conditions = daily_advice.get(
        "stop_conditions",
        [],
    )

    avoid = daily_advice.get(
        "avoid",
        [],
    )

    alternatives = daily_advice.get(
        "alternatives",
        [],
    )

    if (
        execution_steps
        or stop_conditions
        or avoid
        or alternatives
    ):
        st.divider()

        detail_col1, detail_col2 = st.columns(
            2
        )

        with detail_col1:
            if execution_steps:
                st.markdown(
                    "**Session steps**"
                )

                for step in execution_steps:
                    if step:
                        st.write(
                            f"• {step}"
                        )

            if alternatives:
                st.markdown(
                    "**Alternatives**"
                )

                for alternative in alternatives:
                    if alternative:
                        st.write(
                            f"• {alternative}"
                        )

        with detail_col2:
            if stop_conditions:
                st.markdown(
                    "**Stop or shorten the session if**"
                )

                for condition in stop_conditions:
                    if condition:
                        st.write(
                            f"• {condition}"
                        )

            if avoid:
                st.markdown(
                    "**Avoid today**"
                )

                for item in avoid:
                    if item:
                        st.write(
                            f"• {item}"
                        )

    advice_warnings = daily_advice.get(
        "warnings",
        [],
    )

    if advice_warnings:
        st.divider()

        for warning in advice_warnings:
            if warning:
                st.warning(
                    warning
                )

    advice_confidence = daily_advice.get(
        "confidence"
    )

    if advice_confidence is not None:
        st.caption(
            f"Phoenix confidence: "
            f"{advice_confidence}%"
        )


# ---------------------------------------------------------------------
# Weather advice
# ---------------------------------------------------------------------

if planned_activity in {
    "Cycling",
    "Walking",
}:
    st.subheader(
        "🌤️ Weather context"
    )

    if weather_snapshot.status != "Available":
        st.warning(
            weather_intelligence.summary
        )

    elif (
        planned_activity == "Cycling"
        and training_environment == "Indoor"
    ):
        st.info(
            weather_intelligence.recommendation
        )

        current_temp = format_number(
            weather_snapshot.current_temperature_c,
            1,
        )

        st.caption(
            f"Springe is currently around {current_temp} °C. "
            "Outdoor conditions are available in the details below, "
            "but they do not determine an indoor workout."
        )

    else:
        if weather_intelligence.outdoor_suitability in {
            "Excellent",
            "Good",
        }:
            st.success(
                weather_intelligence.summary
            )

        elif weather_intelligence.outdoor_suitability in {
            "Fair",
            "Limited",
        }:
            st.warning(
                weather_intelligence.summary
            )

        else:
            st.error(
                weather_intelligence.summary
            )

        st.write(
            weather_intelligence.recommendation
        )

        if weather_intelligence.best_window:
            st.metric(
                "Best remaining outdoor window",
                weather_intelligence.best_window,
            )

        for warning in weather_intelligence.warnings:
            st.warning(
                warning
            )

    with st.expander(
        "View weather evidence"
    ):
        (
            weather_col1,
            weather_col2,
            weather_col3,
            weather_col4,
        ) = st.columns(
            4
        )

        with weather_col1:
            st.metric(
                "Current",
                (
                    f"{format_number(weather_snapshot.current_temperature_c, 1)} °C"
                    if weather_snapshot.current_temperature_c is not None
                    else "—"
                ),
            )

        with weather_col2:
            st.metric(
                "Heat risk",
                weather_intelligence.heat_risk,
            )

        with weather_col3:
            st.metric(
                "Rain risk",
                weather_intelligence.rain_risk,
            )

        with weather_col4:
            st.metric(
                "Wind risk",
                weather_intelligence.wind_risk,
            )

        st.write(
            f"**Hydration:** "
            f"{weather_intelligence.hydration_guidance}"
        )

        st.write(
            f"**Cooling:** "
            f"{weather_intelligence.cooling_guidance}"
        )

        if training_environment != "Indoor":
            st.write(
                f"**Clothing:** "
                f"{weather_intelligence.clothing_guidance}"
            )

        if weather_intelligence.reasons:
            st.markdown(
                "**Forecast evidence**"
            )

            for reason in weather_intelligence.reasons:
                st.write(
                    f"• {reason}"
                )

        st.caption(
            f"Weather confidence: "
            f"{weather_intelligence.confidence}% · "
            f"Source: {weather_snapshot.source}"
        )


# ---------------------------------------------------------------------
# Compact daily state
# ---------------------------------------------------------------------

st.subheader(
    "Today at a glance"
)

(
    summary_col1,
    summary_col2,
    summary_col3,
    summary_col4,
) = st.columns(
    4
)

with summary_col1:
    st.metric(
        "Recovery",
        morning_brief.get(
            "recovery_label",
            "Unknown",
        ),
        (
            f"{morning_brief.get('recovery_score', '—')}/100"
        ),
    )

with summary_col2:
    st.metric(
        "Training state",
        morning_brief.get(
            "training_label",
            "Unknown",
        ),
    )

with summary_col3:
    st.metric(
        "Capacity",
        (
            f"{daily_strain.get('capacity', '—')}/100"
        ),
    )

with summary_col4:
    st.metric(
        "Confidence",
        (
            f"{morning_brief.get('confidence', '—')}%"
        ),
    )

health_summary = health.get(
    "summary",
    "No health summary is currently available.",
)

st.caption(
    health_summary
)


# ---------------------------------------------------------------------
# Why Phoenix thinks this
# ---------------------------------------------------------------------

with st.expander(
    "Why Phoenix thinks this",
    expanded=True,
):
    highlights = morning_brief.get(
        "highlights",
        [],
    )

    if highlights:
        for item in highlights:
            st.write(
                item
            )

    else:
        st.caption(
            "No additional highlights are available."
        )

    daily_advice_reasons = daily_advice.get(
        "reasons",
        [],
    )

    if daily_advice_reasons:
        st.markdown(
            "**Decision evidence**"
        )

        for reason in daily_advice_reasons:
            if reason:
                st.write(
                    f"• {reason}"
                )

    st.divider()

    (
        evidence_col1,
        evidence_col2,
        evidence_col3,
    ) = st.columns(
        3
    )

    with evidence_col1:
        st.metric(
            "Current strain",
            (
                f"{daily_strain.get('current_strain', '—')}/100"
            ),
        )

    with evidence_col2:
        st.metric(
            "Remaining capacity",
            daily_strain.get(
                "remaining",
                "—",
            ),
        )

    with evidence_col3:
        st.metric(
            "Balance",
            daily_strain.get(
                "balance_label",
                "Unknown",
            ),
        )

    st.caption(
        daily_strain.get(
            "balance_summary",
            "",
        )
    )


# ---------------------------------------------------------------------
# Timeline helpers
# ---------------------------------------------------------------------

TIMELINE_CATEGORY_ICONS = {
    "Medical": "🏥",
    "Illness": "🤒",
    "Recovery": "🌱",
    "Training": "🚴",
    "Nutrition": "🥗",
    "Medication": "💊",
    "Sleep": "😴",
    "Work": "💼",
    "Lifestyle": "🏠",
    "Travel": "✈️",
    "Equipment": "🛠️",
    "Milestone": "🏆",
    "Other": "📌",
}

TIMELINE_SEVERITY_ICONS = {
    "Info": "⚪",
    "Minor": "🔵",
    "Moderate": "🟡",
    "Major": "🟠",
    "Critical": "🔴",
}


def timeline_category_icon(category):
    clean_category = str(
        category or ""
    ).strip()

    return TIMELINE_CATEGORY_ICONS.get(
        clean_category,
        "📌",
    )


def timeline_severity_icon(severity):
    clean_severity = str(
        severity or ""
    ).strip()

    return TIMELINE_SEVERITY_ICONS.get(
        clean_severity,
        "⚪",
    )


def timeline_event_age_text(event):
    days_since_start = event.get(
        "days_since_start"
    )

    if days_since_start is None:
        return "Date unavailable"

    try:
        days_since_start = int(
            days_since_start
        )

    except (TypeError, ValueError):
        return "Date unavailable"

    if event.get(
        "is_active",
        False,
    ):
        if days_since_start == 0:
            return "Started today · active"

        if days_since_start == 1:
            return "Started yesterday · active"

        return (
            f"Started {days_since_start} days ago · active"
        )

    days_since_end = event.get(
        "days_since_end"
    )

    if days_since_end is not None:
        try:
            days_since_end = int(
                days_since_end
            )

        except (TypeError, ValueError):
            days_since_end = None

    start_date_text = event.get(
        "start_date"
    )

    end_date_text = event.get(
        "end_date"
    )

    is_one_day_event = (
        start_date_text
        and end_date_text
        and start_date_text == end_date_text
    )

    if is_one_day_event:
        if days_since_start == 0:
            return "Occurred today"

        if days_since_start == 1:
            return "Occurred yesterday"

        return (
            f"Occurred {days_since_start} days ago"
        )

    if days_since_end == 0:
        return "Ended today"

    if days_since_end == 1:
        return "Ended yesterday"

    if (
        days_since_end is not None
        and days_since_end > 1
    ):
        return (
            f"Ended {days_since_end} days ago"
        )

    return (
        f"Started {days_since_start} days ago"
    )


def timeline_event_period_text(event):
    start_date_text = event.get(
        "start_date"
    )

    end_date_text = event.get(
        "end_date"
    )

    try:
        start_value = date.fromisoformat(
            start_date_text
        )

    except (TypeError, ValueError):
        return ""

    start_text = start_value.strftime(
        "%d %b %Y"
    )

    if not end_date_text:
        return (
            f"{start_text} – Ongoing"
        )

    try:
        end_value = date.fromisoformat(
            end_date_text
        )

    except (TypeError, ValueError):
        return start_text

    if end_value == start_value:
        return start_text

    return (
        f"{start_text} – "
        f"{end_value.strftime('%d %b %Y')}"
    )


def build_context_display_events(
    timeline,
    limit=6,
):
    active_events = timeline.get(
        "active_events",
        [],
    )

    significant_events = timeline.get(
        "significant_events",
        [],
    )

    displayed_events = []
    included_ids = set()

    for event in active_events:
        event_id = event.get(
            "id"
        )

        displayed_events.append(
            event
        )

        if event_id is not None:
            included_ids.add(
                event_id
            )

    for event in significant_events:
        event_id = event.get(
            "id"
        )

        if (
            event_id is not None
            and event_id in included_ids
        ):
            continue

        displayed_events.append(
            event
        )

        if event_id is not None:
            included_ids.add(
                event_id
            )

    return displayed_events[
        :limit
    ]


def render_current_context(timeline):
    display_events = build_context_display_events(
        timeline
    )

    st.write(
        timeline.get(
            "context_summary",
            (
                "No active or recent timeline events "
                "are currently available."
            ),
        )
    )

    if not display_events:
        st.caption(
            "No active or significant recent Timeline events."
        )

        return

    for event in display_events:
        category = event.get(
            "category",
            "Other",
        )

        severity = event.get(
            "severity",
            "Info",
        )

        title = (
            event.get(
                "title"
            )
            or "Timeline event"
        )

        period_text = timeline_event_period_text(
            event
        )

        age_text = timeline_event_age_text(
            event
        )

        event_col, status_col = st.columns(
            [4, 1]
        )

        with event_col:
            st.markdown(
                f"**{timeline_category_icon(category)} "
                f"{title}**"
            )

            detail_parts = [
                str(category),
                age_text,
            ]

            if period_text:
                detail_parts.append(
                    period_text
                )

            st.caption(
                " · ".join(
                    detail_parts
                )
            )

        with status_col:
            st.markdown(
                f"{timeline_severity_icon(severity)} "
                f"{severity}"
            )


with st.expander(
    "Current health and life context"
):
    render_current_context(
        timeline_context
    )

    st.page_link(
        "pages/6_Life_Events.py",
        label="📖 Open full Timeline",
    )


if not st.session_state.get('phoenix_today_handles_wrist_temp', False):
    # ---------------------------------------------------------------------
    # Manual wrist temperature
    # ---------------------------------------------------------------------

    with st.expander(
        "🌡️ Add or review wrist temperature"
    ):
        st.caption(
            "Use this while automatic Apple Watch wrist-temperature "
            "uploads are unavailable."
        )

        temp_col1, temp_col2 = st.columns(
            2
        )

        with temp_col1:
            wrist_temp_date = st.date_input(
                "Measurement date",
                value=date.today(),
                max_value=date.today(),
                key="manual_wrist_temp_date",
            )

        existing_wrist_temp = (
            get_manual_wrist_temperature_for_date(
                wrist_temp_date
            )
        )

        default_wrist_temp = 36.50

        if existing_wrist_temp is not None:
            default_wrist_temp = float(
                existing_wrist_temp[
                    "value"
                ]
            )

        with temp_col2:
            wrist_temperature = st.number_input(
                "Wrist temperature (°C)",
                min_value=30.00,
                max_value=45.00,
                value=default_wrist_temp,
                step=0.01,
                format="%.2f",
                key=(
                    "manual_wrist_temp_value_"
                    f"{wrist_temp_date.isoformat()}"
                ),
            )

        if existing_wrist_temp is not None:
            st.info(
                "A manual reading already exists for "
                f"{wrist_temp_date.strftime('%d %B %Y')}: "
                f"{existing_wrist_temp['value']:.2f} °C."
            )

        save_temp_label = (
            "Update wrist temperature"
            if existing_wrist_temp is not None
            else "Save wrist temperature"
        )

        if st.button(
            f"💾 {save_temp_label}",
            key="save_manual_wrist_temperature",
        ):
            save_manual_wrist_temperature(
                measurement_date=wrist_temp_date,
                temperature=wrist_temperature,
            )

            st.success(
                f"✅ Wrist temperature saved for "
                f"{wrist_temp_date.strftime('%d %B %Y')}: "
                f"{wrist_temperature:.2f} °C"
            )

            st.rerun()

        recent_wrist_temperatures = (
            load_recent_wrist_temperatures(
                limit=10
            )
        )

        if recent_wrist_temperatures.empty:
            st.caption(
                "No wrist-temperature readings are stored yet."
            )

        else:
            wrist_temp_display = (
                recent_wrist_temperatures.copy()
            )

            wrist_temp_display[
                "value"
            ] = (
                wrist_temp_display[
                    "value"
                ]
                .astype(
                    float
                )
                .round(
                    2
                )
            )

            wrist_temp_display[
                "source"
            ] = (
                wrist_temp_display[
                    "source"
                ]
                .replace(
                    {
                        "manual": "Manual",
                        "apple_health": "Apple Health",
                    }
                )
            )

            wrist_temp_display = wrist_temp_display[
                [
                    "measurement_date",
                    "value",
                    "unit",
                    "source",
                ]
            ]

            wrist_temp_display = wrist_temp_display.rename(
                columns={
                    "measurement_date": "Date",
                    "value": "Temperature",
                    "unit": "Unit",
                    "source": "Source",
                }
            )

            st.dataframe(
                wrist_temp_display,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Date": st.column_config.DateColumn(
                        "Date",
                        format="DD MMM YYYY",
                    ),
                    "Temperature": st.column_config.NumberColumn(
                        "Temperature",
                        format="%.2f",
                    ),
                },
            )


if not st.session_state.get('phoenix_today_handles_data_readiness', False):
    # ---------------------------------------------------------------------
    # Data status and sync
    # ---------------------------------------------------------------------

    with st.expander(
        "Data freshness and sync"
    ):
        if (
            snapshot.get(
                "completed"
            )
            == snapshot.get(
                "total"
            )
        ):
            st.success(
                f"✅ Phoenix data is ready · "
                f"{snapshot.get('snapshot_percent', 0)}% complete"
            )

        else:
            st.warning(
                f"Phoenix is "
                f"{snapshot.get('snapshot_percent', 0)}% ready. "
                "Missing information reduces confidence but will not "
                "stop Phoenix."
            )

        (
            fresh_col1,
            fresh_col2,
            fresh_col3,
            fresh_col4,
        ) = st.columns(
            4
        )

        with fresh_col1:
            if withings_is_connected():
                status_card(
                    "Withings",
                    freshness_icon(
                        withings_freshness.get(
                            "status"
                        )
                    ),
                    "Connected",
                    withings_freshness.get(
                        "message"
                    ),
                )

            else:
                status_card(
                    "Withings",
                    "🔴",
                    "Not connected",
                )

        with fresh_col2:
            status_card(
                "Apple Health",
                freshness_icon(
                    apple_health_freshness.get(
                        "status"
                    )
                ),
                (
                    "Available"
                    if apple_health_available
                    else "Waiting"
                ),
                apple_health_freshness.get(
                    "message"
                ),
            )

        with fresh_col3:
            status_card(
                "Check-in",
                snapshot_icon(
                    snapshot.get(
                        "today_checkin_done",
                        False,
                    )
                ),
                (
                    "Complete"
                    if snapshot.get(
                        "today_checkin_done",
                        False,
                    )
                    else "Missing"
                ),
            )

        with fresh_col4:
            status_card(
                "Lumen",
                snapshot_icon(
                    snapshot.get(
                        "lumen_entered",
                        False,
                    )
                ),
                (
                    "Entered"
                    if snapshot.get(
                        "lumen_entered",
                        False,
                    )
                    else "Missing"
                ),
            )

        sync_col1, sync_col2 = st.columns(
            2
        )

        with sync_col1:
            if withings_is_connected():
                if st.button(
                    "🔄 Sync Withings now"
                ):
                    with st.spinner(
                        "Syncing Withings data..."
                    ):
                        sync_withings_once_per_session(
                            st,
                            force=True,
                        )

                    st.success(
                        "Withings sync complete."
                    )

                    st.rerun()

            else:
                st.link_button(
                    "Connect Withings",
                    build_authorization_url(),
                )

        with sync_col2:
            st.caption(
                "Apple Health auto-syncs from local export files."
            )


# ---------------------------------------------------------------------
# Deep-dive navigation
# ---------------------------------------------------------------------

st.divider()

st.subheader(
    "Explore further"
)

nav_col1, nav_col2, nav_col3, nav_col4 = st.columns(
    4
)

with nav_col1:
    st.page_link(
        "pages/2_Insights.py",
        label="🌟 Insights",
    )

with nav_col2:
    st.page_link(
        "pages/3_Training_Coach.py",
        label="🚴 Training Coach",
    )

with nav_col3:
    st.page_link(
        "pages/4_Trends.py",
        label="📈 Trends",
    )

with nav_col4:
    st.page_link(
        "pages/5_Workouts.py",
        label="🏋️ Workouts",
    )


# ---------------------------------------------------------------------
# Developer summary helpers
# ---------------------------------------------------------------------

def build_timeline_debug_summary(timeline):
    return {
        "reference_date": timeline.get(
            "reference_date"
        ),
        "active_event_count": timeline.get(
            "active_event_count",
            0,
        ),
        "recent_event_count": timeline.get(
            "recent_event_count",
            0,
        ),
        "significant_event_count": timeline.get(
            "significant_event_count",
            0,
        ),
        "highest_severity": timeline.get(
            "highest_severity"
        ),
        "has_recent_surgery": timeline.get(
            "has_recent_surgery",
            False,
        ),
        "has_recent_hospital_event": timeline.get(
            "has_recent_hospital_event",
            False,
        ),
        "has_recent_cardiac_event": timeline.get(
            "has_recent_cardiac_event",
            False,
        ),
        "has_recent_illness": timeline.get(
            "has_recent_illness",
            False,
        ),
        "has_active_recovery_event": timeline.get(
            "has_active_recovery_event",
            False,
        ),
        "recovery_phase": timeline.get(
            "recovery_phase",
            False,
        ),
        "context_summary": timeline.get(
            "context_summary"
        ),
    }


# ---------------------------------------------------------------------
# Developer tools
# ---------------------------------------------------------------------

with st.expander(
    "Developer tools"
):
    st.subheader(
        "Xert"
    )

    if xert_is_connected():
        st.success(
            "✅ Xert connected."
        )

        if st.button(
            "Fetch Xert training info"
        ):
            status = fetch_and_save_xert_status()

            save_xert_status_record(
                status
            )

            st.success(
                "✅ Xert training info saved to Phoenix."
            )

    else:
        if st.button(
            "Connect Xert"
        ):
            connect_xert()

            st.success(
                "✅ Xert token saved."
            )

            st.rerun()

    st.divider()

    st.subheader(
        "Confidence Profile"
    )

    st.write(
        confidence_profile
    )

    st.subheader(
        "Recent Workout Intelligence"
    )

    st.write(
        recent_workout_intelligence
    )

    st.subheader(
        "Coach Recommendation"
    )

    st.write(
        coach_recommendation
    )

    st.subheader(
        "Daily Advice"
    )

    st.write(
        daily_advice
    )

    st.subheader(
        "Weather Snapshot"
    )

    st.write(
        weather_snapshot
    )

    st.subheader(
        "Weather Intelligence"
    )

    st.write(
        weather_intelligence
    )

    st.subheader(
        "Timeline Summary"
    )

    st.write(
        build_timeline_debug_summary(
            timeline_context
        )
    )

    with st.expander(
        "Apple Health sync details"
    ):
        st.write(
            apple_result
        )


# ---------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------

st.caption(
    f"{PHOENIX_VERSION_LABEL} · "
    f"Today’s data: "
    f"{snapshot.get('snapshot_percent', 0)}% complete · "
    f"Weather: {weather_snapshot.status}"
)