import streamlit as st

from database import init_db
from snapshot import build_morning_snapshot
from ui_helpers import format_delta


init_db()

st.set_page_config(page_title="Phoenix Dashboard", page_icon="📊", layout="wide")

snapshot = build_morning_snapshot()

weight = snapshot["weight"]
body_fat = snapshot["body_fat"]
muscle = snapshot["muscle"]
pwv = snapshot["pwv"]
latest_systolic = snapshot["systolic"]
latest_diastolic = snapshot["diastolic"]
latest_checkin = snapshot["latest_checkin"]

st.title("📊 Dashboard")
st.caption("Current metrics and trends. Charts will come later.")

st.divider()

st.header("⚖️ Body")

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

st.divider()

st.header("❤️ Cardiovascular")

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

st.divider()

st.header("🔥 Metabolism")

met_col1, met_col2, met_col3 = st.columns(3)

if latest_checkin:
    latest_lumen = latest_checkin["lumen_score"]
    latest_fat_burn = latest_checkin["fat_burn_percent"]
    latest_carb_burn = latest_checkin["carb_burn_percent"]
    latest_energy = latest_checkin["energy"]
    latest_mood = latest_checkin["mood"]
    latest_soreness = latest_checkin["soreness"]
else:
    latest_lumen = "—"
    latest_fat_burn = "—"
    latest_carb_burn = "—"
    latest_energy = "—"
    latest_mood = "—"
    latest_soreness = "—"

with met_col1:
    st.metric("Lumen Score", latest_lumen)

with met_col2:
    if latest_fat_burn != "—":
        st.metric("Fat Burn", f"{latest_fat_burn}%")
    else:
        st.metric("Fat Burn", "—")

with met_col3:
    if latest_carb_burn != "—":
        st.metric("Carb Burn", f"{latest_carb_burn}%")
    else:
        st.metric("Carb Burn", "—")

st.divider()

st.header("🧠 Subjective State")

state_col1, state_col2, state_col3 = st.columns(3)

with state_col1:
    st.metric("Energy", latest_energy)

with state_col2:
    st.metric("Mood", latest_mood)

with state_col3:
    st.metric("Soreness", latest_soreness)

from version import PHOENIX_VERSION_LABEL
st.caption(f"{PHOENIX_VERSION_LABEL} · Today’s snapshot: {snapshot['snapshot_percent']}% complete")