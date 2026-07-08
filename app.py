from datetime import date

import streamlit as st

from athlete_context import build_athlete_context
from database import init_db, save_checkin, save_xert_status_record
from integrations.withings import (
    build_authorization_url,
    exchange_code_for_tokens,
    save_tokens,
    withings_is_connected,
    stored_tokens_are_valid,
)
from integrations.xert import (
    connect_xert,
    xert_is_connected,
    fetch_and_save_xert_status,
)
from morning_brief import build_morning_brief
from recovery_engine import build_recovery_profile
from snapshot import build_morning_snapshot
from sync import (
    sync_withings_once_per_session,
    sync_apple_health_autosync_once_per_session,
)


init_db()

st.set_page_config(page_title="Project Phoenix", page_icon="🔥", layout="wide")

query_params = st.query_params
withings_code = query_params.get("code", None)

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
sync_apple_health_autosync_once_per_session(st)

snapshot = build_morning_snapshot()
context = build_athlete_context()
recovery_profile = build_recovery_profile(context)

baselines = context["baselines"]

morning_brief = build_morning_brief(context, recovery_profile, baselines)

apple_result = st.session_state.get("apple_health_autosync_result")
apple_health_available = apple_result is not None and apple_result.get("files_seen", 0) > 0

st.title("🔥 Good morning, Nik")
st.caption("Phoenix has collected what it can automatically. Here’s what it thinks about today.")

st.divider()

st.header("☀️ Morning Brief")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Recovery", morning_brief["recovery_label"], f"{morning_brief['recovery_score']}/100")

with col2:
    st.metric("Training", morning_brief["training_label"])

with col3:
    st.metric("Metabolism", morning_brief["metabolism_label"])

with col4:
    st.metric("Confidence", f"{morning_brief['confidence']}%")

st.subheader("Today’s Summary")

for item in morning_brief["highlights"]:
    st.write(item)

st.info(morning_brief["recommendation"])

st.divider()

st.header("🌅 Morning Snapshot")

if snapshot["completed"] == snapshot["total"]:
    st.success("✅ Morning Snapshot Complete. Phoenix is ready.")
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

    if apple_health_available:
        st.success("☑ Apple Health")
    else:
        st.warning("☐ Apple Health")

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
    fat_burn_percent = st.slider("Estimated Fat burning %", 0, 100, 65)

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

st.page_link("pages/2_Insights.py", label="🌟 Open Insights")
st.page_link("pages/3_Training_Coach.py", label="🚴 Open Coach")
st.page_link("pages/4_Trends.py", label="📈 Open Trends")

st.divider()

with st.expander("Developer tools"):
    st.subheader("Xert")

    if xert_is_connected():
        st.success("✅ Xert connected.")

        if st.button("Fetch Xert training info"):
            status = fetch_and_save_xert_status()
            save_xert_status_record(status)
            st.success("✅ Xert training info saved to Phoenix.")
    else:
        if st.button("Connect Xert"):
            connect_xert()
            st.success("✅ Xert token saved.")
            st.rerun()

    st.subheader("Apple Health Sync")
    st.write(apple_result)

st.caption(f"Project Phoenix v0.9.2-alpha · Today’s snapshot: {snapshot['snapshot_percent']}% complete")