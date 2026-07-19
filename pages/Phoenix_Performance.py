from __future__ import annotations
import streamlit as st
from phoenix_narrative import performance_story, render_three_part_brief
from phoenix_ui import render_section_card

st.set_page_config(page_title="Performance · Phoenix", page_icon="🚴", layout="wide")
st.title("🚴 Performance")
st.caption("What is improving, what needs work, and what Phoenix thinks you should do next.")
render_three_part_brief("Today's performance read", *performance_story())

st.subheader("Explore the evidence")
col1, col2 = st.columns(2)
with col1:
    render_section_card("Training Coach", "Today's practical recommendation, including the strongest readiness signals and the specific limits Phoenix is respecting.", icon="🧠", target="pages/3_Training_Coach.py", label="Open Training Coach")
    render_section_card("Workout Deep Analysis", "The route-aware explanation of what went well and what needs attention across power, heart rate, cadence, breathing, heat and terrain.", icon="🔬", target="pages/Workout_Deep_Analysis.py", label="Open Deep Analysis")
with col2:
    render_section_card("Workouts", "A concise interpretation of the latest training day, followed by the individual sessions and their evidence.", icon="🏋️", target="pages/5_Workouts.py", label="View Workouts")
    render_section_card("Today's Insights", "The combined health, recovery and coaching interpretation behind today's recommendation.", icon="💡", target="pages/2_Insights.py", label="Open Insights")
