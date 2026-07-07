import streamlit as st

from coach import daily_brief
from database import init_db
from snapshot import build_morning_snapshot


init_db()

st.set_page_config(page_title="Phoenix Training Coach", page_icon="🚴", layout="wide")

snapshot = build_morning_snapshot()
latest_checkin = snapshot["latest_checkin"]

st.title("🚴 Training Coach")
st.caption("Basic guidance for now. Race mode and route advice come in v0.8.")

if latest_checkin:
    coach_energy = latest_checkin["energy"]
    coach_soreness = latest_checkin["soreness"]
    coach_fat_burn = latest_checkin["fat_burn_percent"]

    brief = daily_brief(coach_energy, coach_soreness, coach_fat_burn)

    st.header("🔥 Today’s Phoenix Brief")
    st.subheader(brief["recovery"])

    st.markdown("### Recommendation")
    st.write(brief["recommendation"])

    with st.expander("💡 Why?"):
        st.write(brief["reason"])
else:
    st.warning("Complete a morning check-in first so Phoenix can give training guidance.")

st.divider()

st.header("Coming in v0.8")

st.info(
    "Training Coach will later support race mode, route details, pacing, fuelling, "
    "warm-up advice, and context-specific recommendations."
)

training_type = st.selectbox(
    "Planned activity",
    ["Not sure yet", "Rest", "Walk", "Zone 1/2 ride", "Intervals", "Race", "Strength"],
)

notes = st.text_area(
    "Optional training context",
    placeholder="Example: I have a race tonight, or I want to ride an easy hour...",
)

st.caption("These fields are placeholders for v0.8 and are not saved yet.")