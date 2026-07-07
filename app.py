from datetime import date

import streamlit as st

from database import init_db, save_checkin
from integrations.withings import (
    build_authorization_url,
    exchange_code_for_tokens,
    save_tokens,
    withings_is_connected,
    stored_tokens_are_valid,
)
from snapshot import build_morning_snapshot
from sync import sync_withings_once_per_session


init_db()

st.set_page_config(page_title="Project Phoenix", page_icon="🔥", layout="wide")

query_params = st.query_params
withings_code = query_params.get("code", None)

st.title("🔥 Good morning, Nik")
st.subheader("☀ Morning")
st.caption(
    "Phoenix has already collected everything it can automatically. "
    "I just need a few things that only you know."
)

if withings_code:
    if stored_tokens_are_valid():
        st.query_params.clear()
    else:
        try:
            token_response = exchange_code_for_tokens(withings_code)
            save_tokens(token_response)
            st.session_state["withings_synced_this_session"] = False
            st.success("✅ Withings connected. Tokens saved locally.")
            st.query_params.clear()
        except Exception as error:
            st.error("Withings connection failed. Please reconnect.")
            st.caption(str(error))
            st.query_params.clear()

sync_withings_once_per_session(st)

snapshot = build_morning_snapshot()

st.divider()
st.header("🌅 Morning Snapshot")

if snapshot["completed"] == snapshot["total"]:
    st.success(
        "✅ Morning Snapshot Complete. Everything is up to date. "
        "Phoenix is ready to help you make today’s decisions."
    )
else:
    st.warning(
        f"🟡 Morning Snapshot {snapshot['snapshot_percent']}% complete. "
        "Complete the missing items below and Phoenix will update."
    )

col1, col2 = st.columns([3, 1])

with col1:
    if snapshot["body_measurements_available"]:
        st.success("☑ Body measurements")
    else:
        st.warning("☐ Body measurements")

    if snapshot["today_checkin_done"]:
        st.success("☑ Morning check-in")
    else:
        st.warning("☐ Morning check-in")

    if snapshot["lumen_entered"]:
        st.success("☑ Lumen")
    else:
        st.info("☐ Lumen")

with col2:
    st.metric("Snapshot", f"{snapshot['snapshot_percent']}%")

if not withings_is_connected():
    st.warning("Withings is not connected.")
    st.link_button("Connect Withings", build_authorization_url())

st.divider()
st.header("✍️ Tell Phoenix what only you know")
st.caption("Lumen, energy, mood, soreness, and optional notes. Keep it under 30 seconds.")

form_col1, form_col2, form_col3 = st.columns(3)

with form_col1:
    checkin_date = st.date_input("Date", date.today())
    lumen_score = st.selectbox("Morning Lumen score", [1, 2, 3, 4, 5], index=2)
    fat_burn_percent = st.slider(
        "Estimated Fat burning %",
        min_value=0,
        max_value=100,
        value=65,
        help="Carbs are calculated automatically.",
    )

carb_burn_percent = 100 - fat_burn_percent
st.caption(f"Estimated fuel mix: {fat_burn_percent}% fat / {carb_burn_percent}% carbs")

with form_col2:
    energy = st.slider("⚡ Energy", 1, 10, 5)
    mood = st.slider("😊 Mood & Motivation", 1, 10, 5)

with form_col3:
    soreness = st.slider("💪 Pain or Muscle Soreness", 1, 10, 1)
    notes = st.text_area("Notes", placeholder="Optional...")

if st.button("💾 Complete Morning Check-in"):
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
    st.success("✅ Morning check-in complete!")
    st.rerun()

st.divider()
st.header("Your morning routine")

st.markdown("### 1️⃣ Review today’s insights")
st.write("See what Phoenix noticed today.")
st.page_link("pages/2_Insights.py", label="🌟 Open Insights")

st.markdown("### 2️⃣ Review today’s coaching")
st.write("See today’s training recommendation.")
st.page_link("pages/3_Training_Coach.py", label="🚴 Open Coach")

st.markdown("### 3️⃣ Check your trends")
st.write("Review longer-term progress.")
st.page_link("pages/4_Trends.py", label="📈 Open Trends")

st.divider()
st.caption(f"Project Phoenix v0.7 · Today’s snapshot: {snapshot['snapshot_percent']}% complete")