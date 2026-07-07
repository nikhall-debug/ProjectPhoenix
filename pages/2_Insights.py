from datetime import date

import streamlit as st

from achievements import generate_achievements
from database import init_db, save_coach_feedback
from insights import generate_daily_focus, generate_insights
from snapshot import build_morning_snapshot
from ui_helpers import render_explainable_item


init_db()

st.set_page_config(page_title="Phoenix Insights", page_icon="🌟", layout="wide")

snapshot = build_morning_snapshot()
achievements = generate_achievements(snapshot)
insights = generate_insights(snapshot)
daily_focus = generate_daily_focus(insights)

wins = [item for item in insights if item.get("level") == "win"]
watch_items = [item for item in insights if item.get("level") == "warning"]
info_items = [item for item in insights if item.get("level") == "info"]

st.title("🌟 Today’s Insights")
st.caption("What Phoenix thinks is worth knowing today.")

st.info(f"Today’s Focus: {daily_focus}")

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
                recommendation=daily_focus,
                response=feedback_response,
                reason=feedback_reason,
            )
            st.success("Feedback saved.")

st.divider()

st.header("🏆 Achievements")

if achievements:
    for achievement in achievements:
        render_explainable_item(achievement)
else:
    st.caption("No new achievements today.")

st.divider()

if wins:
    st.header("✅ Today’s Wins")
    for insight in wins:
        render_explainable_item(insight)

if watch_items:
    st.header("👀 Things to Watch")
    for insight in watch_items:
        render_explainable_item(insight)

if info_items:
    st.header("ℹ️ Good to Know")
    for insight in info_items:
        render_explainable_item(insight)

if not insights:
    st.info("No major insights yet. Phoenix will add insights as more data builds up.")