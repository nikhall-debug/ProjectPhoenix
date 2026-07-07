from datetime import date, datetime

import streamlit as st

from analytics import weight_summary, body_fat_summary, muscle_summary, pwv_summary
from coach import daily_brief
from database import (
    init_db,
    save_checkin,
    save_health_measurement,
    get_latest_measurement_time,
    get_latest_metric,
    has_checkin_for_date,
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

if withings_code:
    token_response = exchange_code_for_tokens(withings_code)
    save_tokens(token_response)
    st.session_state["withings_synced_this_session"] = False
    st.success("✅ Withings connected. Tokens saved locally.")
    st.query_params.clear()

if withings_is_connected():
    if "withings_synced_this_session" not in st.session_state:
        st.session_state["withings_synced_this_session"] = False

    if not st.session_state["withings_synced_this_session"]:
        latest_time = get_latest_measurement_time("withings")

        startdate = None
        if latest_time is not None:
            startdate = int(datetime.fromisoformat(latest_time).timestamp())

        measurements = get_withings_measurements(limit=100, startdate=startdate)

        for measurement in measurements:
            save_health_measurement(
                source=measurement["source"],
                metric_type=measurement["metric_type"],
                value=measurement["value"],
                unit=measurement["unit"],
                measured_at=measurement["measured_at"],
                raw_type=measurement["raw_type"],
                raw_data=measurement["raw_data"],
            )

        st.session_state["withings_synced_this_session"] = True


st.divider()

st.header("🌅 Morning Snapshot")

today_checkin_done = has_checkin_for_date(date.today())

weight = weight_summary()
body_fat = body_fat_summary()
muscle = muscle_summary()
pwv = pwv_summary()

body_measurements_available = weight is not None

# Temporary: later this will check the latest check-in record directly.
lumen_entered = today_checkin_done

completed = 0
total = 3

if body_measurements_available:
    completed += 1

if today_checkin_done:
    completed += 1

if lumen_entered:
    completed += 1

snapshot_percent = round((completed / total) * 100)

if completed == total:
    st.success(
        "Good morning Nik. Your Morning Snapshot is complete. "
        "Phoenix has enough information to provide today's recommendations."
    )
else:
    st.warning(
        f"Good morning Nik. Your Morning Snapshot is {snapshot_percent}% complete. "
        "Complete the missing items to improve today's coaching."
    )

snapshot_col1, snapshot_col2 = st.columns([3, 1])

with snapshot_col1:
    if body_measurements_available:
        st.success("☑ Body measurements")
    else:
        st.warning("☐ Body measurements")

    if today_checkin_done:
        st.success("☑ Morning check-in")
    else:
        st.warning("☐ Morning check-in")

    if lumen_entered:
        st.success("☑ Lumen")
    else:
        st.info("☐ Lumen")

with snapshot_col2:
    st.metric("Snapshot", f"{snapshot_percent}%")

if not withings_is_connected():
    st.warning("Withings is not connected.")
    st.link_button("Connect Withings", build_authorization_url())


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
    st.rerun()

brief = daily_brief(energy, soreness, fat_burn_percent)

st.divider()

st.header("🔥 Today's Phoenix Brief")

st.subheader(brief["recovery"])

st.markdown("### 🚴 Today's Recommendation")
st.write(brief["recommendation"])

st.markdown("### Why?")
st.write(brief["reason"])


st.divider()

st.header("📊 Dashboard")

latest_systolic = get_latest_metric("withings", "systolic_bp")
latest_diastolic = get_latest_metric("withings", "diastolic_bp")

latest_lumen = "—"
latest_fat_burn = "—"
latest_carb_burn = "—"


def format_delta(value, unit):
    if value is None:
        return None

    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f} {unit} in 30d"


st.subheader("⚖️ Body")

body_col1, body_col2, body_col3 = st.columns(3)

with body_col1:
    if weight:
        st.metric(
            "Weight",
            f"{weight['current']:.1f} kg",
            delta=format_delta(weight["delta_30d"], "kg"),
        )
    else:
        st.metric("Weight", "—")

with body_col2:
    if body_fat:
        st.metric(
            "Body Fat",
            f"{body_fat['current']:.1f} %",
            delta=format_delta(body_fat["delta_30d"], "%"),
        )
    else:
        st.metric("Body Fat", "—")

with body_col3:
    if muscle:
        st.metric(
            "Muscle Mass",
            f"{muscle['current']:.1f} kg",
            delta=format_delta(muscle["delta_30d"], "kg"),
        )
    else:
        st.metric("Muscle Mass", "—")


st.subheader("❤️ Cardiovascular")

cardio_col1, cardio_col2 = st.columns(2)

with cardio_col1:
    if latest_systolic and latest_diastolic:
        st.metric(
            "Blood Pressure",
            f"{latest_systolic['value']:.0f}/{latest_diastolic['value']:.0f} mmHg",
        )
    else:
        st.metric("Blood Pressure", "—")

with cardio_col2:
    if pwv:
        st.metric(
            "Pulse Wave Velocity",
            f"{pwv['current']:.2f} m/s",
            delta=format_delta(pwv["delta_30d"], "m/s"),
        )
    else:
        st.metric("Pulse Wave Velocity", "—")


st.subheader("🔥 Metabolism")

met_col1, met_col2, met_col3 = st.columns(3)

with met_col1:
    st.metric("Lumen Score", latest_lumen)

with met_col2:
    st.metric("Fat Burn", latest_fat_burn)

with met_col3:
    st.metric("Carb Burn", latest_carb_burn)


st.caption("Version 0.5-alpha with Morning Snapshot")