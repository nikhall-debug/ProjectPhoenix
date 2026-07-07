import streamlit as st
load_coach_plan_overrides

from database import init_db, load_checkins, load_health_measurements, load_coach_feedback

init_db()

st.set_page_config(page_title="Phoenix Data Explorer", page_icon="📊", layout="wide")

st.title("📊 Data Explorer")
st.caption("Raw Phoenix data. Useful for checking imports, debugging, and exploring history.")

st.divider()

st.header("Recent health measurements")

measurements_df = load_health_measurements()

if not measurements_df.empty:
    st.dataframe(measurements_df, use_container_width=True)
else:
    st.info("No health measurements imported yet.")

st.divider()

st.header("Recent morning check-ins")

checkins_df = load_checkins()

if not checkins_df.empty:
    st.dataframe(checkins_df, use_container_width=True)
else:
    st.info("No check-ins saved yet.")

    st.divider()

st.header("Coach feedback")

feedback_df = load_coach_feedback()

if not feedback_df.empty:
    st.dataframe(feedback_df, use_container_width=True)
else:
    st.info("No coach feedback saved yet.")

    st.divider()

st.header("Coach plan overrides")

overrides_df = load_coach_plan_overrides()

if not overrides_df.empty:
    st.dataframe(overrides_df, use_container_width=True)
else:
    st.info("No coach plan overrides saved yet.")