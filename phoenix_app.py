from __future__ import annotations

from pathlib import Path

import streamlit as st

from phoenix_ui import render_brand_header

ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Phoenix",
    page_icon="🔥",
    layout="wide",
)

# The filenames below are intentionally unchanged. Only their visible labels and
# place in the navigation hierarchy are new.
today = st.Page("pages/Phoenix_Today.py", title="Today", icon="🏠", default=True)
performance = st.Page("pages/Phoenix_Performance.py", title="Performance", icon="🚴")
health = st.Page("pages/Phoenix_Health.py", title="Health", icon="❤️")
data = st.Page("pages/1_Data_Explorer.py", title="Data", icon="🗄️")

coach = st.Page(
    "pages/3_Training_Coach.py",
    title="Training Coach",
    icon="🧠",
    visibility="hidden",
)
workouts = st.Page(
    "pages/5_Workouts.py",
    title="Workouts",
    icon="🏋️",
    visibility="hidden",
)
deep_analysis = st.Page(
    "pages/Workout_Deep_Analysis.py",
    title="Workout Deep Analysis",
    icon="🔬",
    visibility="hidden",
)
trends = st.Page(
    "pages/4_Trends.py",
    title="Health Trends",
    icon="📈",
    visibility="hidden",
)
timeline = st.Page(
    "pages/6_Life_Events.py",
    title="Timeline",
    icon="📖",
    visibility="hidden",
)
insights = st.Page(
    "pages/2_Insights.py",
    title="Insights",
    icon="💡",
    visibility="hidden",
)

page = st.navigation(
    [
        today,
        performance,
        health,
        data,
        coach,
        workouts,
        deep_analysis,
        trends,
        timeline,
        insights,
    ],
    position="sidebar",
)

page.run()
