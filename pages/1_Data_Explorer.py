import streamlit as st

from database import init_db, load_checkins, load_health_measurements


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