from datetime import date, datetime

import streamlit as st

from coach import daily_brief
from database import (
    init_db,
    save_checkin,
    save_health_measurement,
    get_latest_measurement_time,
    save_coach_feedback,
)
from integrations.withings import (
    build_authorization_url,
    exchange_code_for_tokens,
    save_tokens,
    get_withings_measurements,
    withings_is_connected,
    stored_tokens_are_valid,
)
from snapshot import build_morning_snapshot
from insights import generate_insights, generate_daily_focus
from achievements import generate_achievements


init_db()

st.set_page_config(page_title="Project Phoenix", page_icon="🔥", layout="wide")

query_params = st.query_params
withings_code = query_params.get("code", None)

st.title("🔥 Project Phoenix")
st.subheader("Your Personal Health Intelligence")
st.caption("30 seconds now. Better decisions all day.")


# -------------------------
# Withings OAuth handling
# -------------------------

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


# -------------------------
# Withings background sync
# -------------------------

if stored_tokens_are_valid():
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


# -------------------------
# Morning Snapshot
# -------------------------

snapshot = build_morning_snapshot()

st.divider()
st.header("🌅 Morning Snapshot")

if snapshot["completed"] == snapshot["total"]:
    st.success(
        "Good morning Nik. Your Morning Snapshot is complete. "
        "Phoenix has enough information to provide today's recommendations."
    )
else:
    st.warning(
        f"Good morning Nik. Your Morning Snapshot is {snapshot['snapshot_percent']}% complete. "
        "Complete the missing items to improve today's coaching."
    )

snapshot_col1, snapshot_col2 = st.columns([3, 1])

with snapshot_col1:
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

with snapshot_col2:
    st.metric("Snapshot", f"{snapshot['snapshot_percent']}%")

if not withings_is_connected():
    st.warning("Withings is not connected.")
    st.link_button("Connect Withings", build_authorization_url())


# -------------------------
# Morning Check-in
# -------------------------

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

# -------------------------
# Achievements
# -------------------------

achievements = generate_achievements(snapshot)

st.divider()
st.header("🏆 Achievements")

if achievements:
    for achievement in achievements:
        st.markdown(f"### {achievement['icon']} {achievement['title']}")
        st.write(achievement["text"])

        with st.expander("💡 Why?"):
            st.write(achievement["explanation"])

        with st.expander("📚 Evidence"):
            for item in achievement.get("evidence", []):
                st.write(f"- {item}")
else:
    st.caption("No new achievements today.")

# -------------------------
# Today's Insights
# -------------------------

insights = generate_insights(snapshot)
daily_focus = generate_daily_focus(insights)

wins = [item for item in insights if item.get("level") == "win"]
watch_items = [item for item in insights if item.get("level") == "warning"]
info_items = [item for item in insights if item.get("level") == "info"]

st.divider()
st.header("🌟 Today's Insights")
st.info(f"Today’s Focus: {daily_focus}")
with st.form("coach_feedback_form"):
    st.markdown("#### Did this feel right?")

    feedback_response = st.radio(
        "Feedback",
        ["No feedback", "Agree", "Disagree"],
        horizontal=True,
    )

    feedback_reason = st.text_area(
        "Optional reason",
        placeholder="Example: I feel better than this suggests, or I have a race tonight...",
    )

    feedback_submitted = st.form_submit_button("Save feedback")

    if feedback_submitted:
        if feedback_response == "No feedback":
            st.warning("Choose Agree or Disagree before saving.")
        else:
            save_coach_feedback(
                feedback_date=date.today(),
                recommendation=daily_focus,
                response=feedback_response,
                reason=feedback_reason,
            )
            st.success("Feedback saved.")


def render_insight(insight):
    st.markdown(f"### {insight['icon']} {insight['title']}")
    st.write(insight["text"])
    st.info(f"Action: {insight['action']}")

    with st.expander("💡 Why?"):
        st.write(insight["explanation"])

    with st.expander("📚 Evidence"):
        for item in insight.get("evidence", []):
            st.write(f"- {item}")


if wins:
    st.subheader("✅ Today’s Wins")
    for insight in wins:
        render_insight(insight)

if watch_items:
    st.subheader("👀 Things to Watch")
    for insight in watch_items:
        render_insight(insight)

if info_items:
    st.subheader("ℹ️ Good to Know")
    for insight in info_items:
        render_insight(insight)

if not insights:
    st.info("No major insights yet. Phoenix will add insights as more data builds up.")

# -------------------------
# Coach
# -------------------------

latest_checkin = snapshot["latest_checkin"]

if latest_checkin:
    coach_energy = latest_checkin["energy"]
    coach_soreness = latest_checkin["soreness"]
    coach_fat_burn = latest_checkin["fat_burn_percent"]
else:
    coach_energy = energy
    coach_soreness = soreness
    coach_fat_burn = fat_burn_percent

brief = daily_brief(coach_energy, coach_soreness, coach_fat_burn)

st.divider()
st.header("🔥 Today's Phoenix Brief")

st.subheader(brief["recovery"])

st.markdown("### 🚴 Today's Recommendation")
st.write(brief["recommendation"])

st.markdown("### Why?")
st.write(brief["reason"])


# -------------------------
# Dashboard
# -------------------------

st.divider()
st.header("📊 Dashboard")


def format_delta(value, unit):
    if value is None:
        return None

    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f} {unit} in 30d"


weight = snapshot["weight"]
body_fat = snapshot["body_fat"]
muscle = snapshot["muscle"]
pwv = snapshot["pwv"]
latest_systolic = snapshot["systolic"]
latest_diastolic = snapshot["diastolic"]
latest_checkin = snapshot["latest_checkin"]

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


st.subheader("🧠 Subjective State")

state_col1, state_col2, state_col3 = st.columns(3)

with state_col1:
    st.metric("Energy", latest_energy)

with state_col2:
    st.metric("Mood", latest_mood)

with state_col3:
    st.metric("Soreness", latest_soreness)


st.caption("Project Phoenix v0.6-alpha")