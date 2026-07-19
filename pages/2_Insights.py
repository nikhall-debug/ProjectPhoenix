from datetime import date

import streamlit as st

from achievements import generate_achievements
from athlete_context import build_athlete_context
from coach_engine import build_coach_recommendation
from database import init_db, save_coach_feedback
from health_intelligence import build_health_intelligence
from readiness_engine import build_readiness_profile
from recovery_engine import build_recovery_profile
from snapshot import build_morning_snapshot
from version import PHOENIX_VERSION_LABEL


init_db()

st.set_page_config(page_title="Phoenix Insights", page_icon="🌟", layout="wide")


def render_signal(text):
    st.write(f"• {text}")


snapshot = build_morning_snapshot()
context = build_athlete_context()

recovery_profile = build_recovery_profile(context)
readiness_profile = build_readiness_profile(context, recovery_profile)

health = build_health_intelligence(
    context=context,
    snapshot=snapshot,
    recovery=recovery_profile,
    readiness=readiness_profile,
)

coach = build_coach_recommendation(
    health_intelligence=health,
    workout_intelligence=None,
    recovery_profile=recovery_profile,
    readiness_profile=readiness_profile,
)

achievements = generate_achievements(snapshot)

st.title("🌟 Today’s Insights")
st.caption("What Phoenix thinks is worth knowing today.")

st.info(f"Today’s Focus: {coach['recommendation']}")

with st.form("coach_feedback_form"):
    st.markdown("#### Did this feel right?")

    feedback_response = st.radio(
        "Feedback",
        ["No feedback", "Agree", "Disagree"],
        horizontal=True,
    )

    feedback_reason = st.text_area(
        "Optional reason",
        placeholder="Example: I feel better than this suggests, or I have a race tonight...",
    )

    feedback_submitted = st.form_submit_button("Save feedback")

    if feedback_submitted:
        if feedback_response == "No feedback":
            st.warning("Choose Agree or Disagree before saving.")
        else:
            save_coach_feedback(
                feedback_date=date.today(),
                recommendation=coach["recommendation"],
                response=feedback_response,
                reason=feedback_reason,
            )
            st.success("Feedback saved.")

st.divider()

st.header("🧭 Coach Read")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Coach Status", coach["title"])

with col2:
    st.metric("Training Permission", coach["training_permission"])

with col3:
    st.metric("Intensity Limit", coach["intensity_limit"])

st.subheader("Why Phoenix thinks this")

for reason in coach.get("reasoning", []):
    render_signal(reason)

st.divider()

st.header("❤️ Health Intelligence")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Health Status", health["status"])

with col2:
    st.metric("Readiness", health["readiness"])

with col3:
    st.metric("Metabolism", health["metabolic_state"])

with col4:
    st.metric("Sleep", health["sleep_status"])

st.caption(health["summary"])

st.subheader("Health signals")

for signal in health.get("signals", []):
    render_signal(signal)

st.subheader("Health recommendations")

for recommendation in health.get("recommendations", []):
    render_signal(recommendation)

st.divider()

st.header("🏆 Achievements")

if achievements:
    for achievement in achievements:
        title = achievement.get("title", "Achievement")
        message = achievement.get("message", "")
        explanation = achievement.get("explanation", "")

        st.markdown(f"**{title}**")

        if message:
            st.write(message)

        if explanation:
            st.caption(explanation)
else:
    st.caption("No new achievements today.")

st.divider()

with st.expander("Developer data"):
    st.subheader("Snapshot")
    st.write(snapshot)

    st.subheader("Recovery Profile")
    st.write(recovery_profile)

    st.subheader("Readiness Profile")
    st.write(readiness_profile)

    st.subheader("Health Intelligence")
    st.write(health)

    st.subheader("Coach Recommendation")
    st.write(coach)

st.caption(f"{PHOENIX_VERSION_LABEL} · Today’s snapshot: {snapshot['snapshot_percent']}% complete")