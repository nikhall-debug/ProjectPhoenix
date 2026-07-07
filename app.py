from datetime import date, datetime

import streamlit as st

from coach import daily_brief
from database import (
    init_db,
    save_checkin,
    load_checkins,
    save_health_measurement,
    load_health_measurements,
    get_latest_measurement_time,
    get_latest_metric,
)
from integrations.withings import (
    build_authorization_url,
    exchange_code_for_tokens,
    save_tokens,
    get_withings_measurements,
    withings_is_connected,
)


init_db()

st.set_page_config(page_title="Project Phoenix", page_icon="🔥", layout="wide")

query_params = st.query_params
withings_code = query_params.get("code", None)

st.title("🔥 Project Phoenix")
st.subheader("Your Personal Health Intelligence")
st.caption("30 seconds now. Better decisions all day.")

st.divider()

st.header("🔗 Withings")

if withings_code:
    token_response = exchange_code_for_tokens(withings_code)
    save_tokens(token_response)
    st.session_state["withings_synced_this_session"] = False
    st.success("✅ Withings connected. Tokens saved locally.")
    st.query_params.clear()

if not withings_is_connected():
    st.warning("Withings is not connected yet.")
    st.link_button("Connect Withings", build_authorization_url())

else:
    if "withings_synced_this_session" not in st.session_state:
        st.session_state["withings_synced_this_session"] = False

    if not st.session_state["withings_synced_this_session"]:
        latest_time = get_latest_measurement_time("withings")

        startdate = None
        if latest_time is not None:
            startdate = int(datetime.fromisoformat(latest_time).timestamp())

        measurements = get_withings_measurements(limit=100, startdate=startdate)

        new_count = 0
        duplicate_count = 0

        for measurement in measurements:
            inserted = save_health_measurement(
                source=measurement["source"],
                metric_type=measurement["metric_type"],
                value=measurement["value"],
                unit=measurement["unit"],
                measured_at=measurement["measured_at"],
                raw_type=measurement["raw_type"],
                raw_data=measurement["raw_data"],
            )

            if inserted:
                new_count += 1
            else:
                duplicate_count += 1

        st.session_state["withings_synced_this_session"] = True
        st.session_state["withings_new_count"] = new_count
        st.session_state["withings_duplicate_count"] = duplicate_count

    new_count = st.session_state.get("withings_new_count", 0)

    if new_count > 0:
        st.success(f"✅ Withings imported {new_count} new measurements.")
    else:
        st.info("✅ Withings is up to date.")

    latest_weight = get_latest_metric("withings", "weight_kg")

    if latest_weight is not None:
        st.metric("Latest Withings weight", f"{latest_weight['value']:.1f} kg")

st.divider()

st.header("🌅 Morning Check-in")
st.caption("Tell Phoenix what only you know. Keep it under 30 seconds.")

col1, col2, col3 = st.columns(3)

with col1:
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

with col2:
    energy = st.slider(
        "⚡ Energy (1 = Exhausted, 10 = Fantastic)",
        1,
        10,
        5,
    )
    mood = st.slider(
        "😊 Mood & Motivation (1 = Poor, 10 = Excellent)",
        1,
        10,
        5,
    )

with col3:
    soreness = st.slider(
        "💪 Pain or Muscle Soreness (1 = None, 10 = Severe)",
        1,
        10,
        1,
    )
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

brief = daily_brief(energy, soreness, fat_burn_percent)

st.divider()

st.header("🔥 Today's Phoenix Brief")

st.subheader(brief["recovery"])

st.markdown("### 🚴 Today's Recommendation")
st.write(brief["recommendation"])

st.markdown("### Why?")
st.write(brief["reason"])

st.divider()

st.header("Recent check-ins")
df = load_checkins()

if not df.empty:
    st.dataframe(df, use_container_width=True)
else:
    st.caption("No check-ins saved yet.")

st.divider()

st.header("Recent health measurements")
measurements_df = load_health_measurements()

if not measurements_df.empty:
    st.dataframe(measurements_df, use_container_width=True)
else:
    st.caption("No health measurements imported yet.")

st.caption("Version 0.5-alpha with session-based automatic Withings sync")