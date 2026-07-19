from __future__ import annotations
import streamlit as st
from phoenix_narrative import health_trends_story, timeline_story, today_health_story
from phoenix_ui import render_section_card

st.set_page_config(page_title="Health · Phoenix", page_icon="❤️", layout="wide")
st.title("❤️ Health")
st.caption("The current health story first; the evidence is one click deeper.")

with st.container(border=True):
    st.subheader("Today's health read")
    st.write(today_health_story())

st.subheader("Explore the evidence")
col1, col2 = st.columns(2)
with col1:
    render_section_card("Health Trends", health_trends_story(90), icon="📈", target="pages/4_Trends.py", label="Explore Health Trends")
with col2:
    render_section_card("Timeline", timeline_story(), icon="📖", target="pages/6_Life_Events.py", label="Open Timeline")

st.divider()
st.caption("Health gives the answer. Trends and Timeline explain it. Data Explorer remains available for the raw measurements.")
