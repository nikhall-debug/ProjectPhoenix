from integrations.withings import (
    build_authorization_url,
    exchange_code_for_tokens,
    save_tokens,
    get_latest_weight,
)
from datetime import date
import streamlit as st
from database import init_db, save_checkin, load_checkins
from coach import daily_brief
from integrations.withings import build_authorization_url, exchange_code_for_tokens

init_db()

query_params = st.query_params

withings_code = query_params.get("code", None)
withings_state = query_params.get("state", None)

st.set_page_config(page_title="Project Phoenix", page_icon="🔥", layout="wide")

st.title("🔥 Project Phoenix")
st.subheader("Your Personal Health Intelligence")
st.caption("30 seconds now. Better decisions all day.")

st.divider()

st.header("🔗 Withings Connection Test")

withings_url = build_authorization_url()
st.link_button("Connect Withings", withings_url)

if withings_code:
    st.success("✅ Withings returned an authorization code.")

    if st.button("Exchange code for tokens"):
        token_response = exchange_code_for_tokens(withings_code)
        save_tokens(token_response)
        st.success("✅ Withings tokens saved locally.")

    st.write("State:", withings_state)
    st.caption("Next step: use the saved tokens to fetch weight.")

else:
    st.info("Withings is not connected yet.")

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
    help="Carbs are calculated automatically.")

carb_burn_percent = 100 - fat_burn_percent

st.caption(f"Estimated fuel mix: {fat_burn_percent}% fat / {carb_burn_percent}% carbs")

with col2:
    energy = st.slider(
    "⚡ Energy (1 = Exhausted, 10 = Fantastic)",
    1,
    10,
    5
)
    mood = st.slider(
    "😊 Mood & Motivation (1 = Poor, 10 = Excellent)",
    1,
    10,
    5
)

with col3:
    soreness = st.slider(
    "💪 Pain or Muscle Soreness (1 = None, 10 = Severe)",
    1,
    10,
    1
)
    notes = st.text_area("Notes", placeholder="Optional...")

if st.button("💾 Complete Morning Check-in"):
    save_checkin(checkin_date, lumen_score, fat_burn_percent, carb_burn_percent, energy, mood, soreness, notes)
brief = daily_brief(energy, soreness, fat_burn_percent)

st.success("✅ Morning check-in complete!")

st.divider()

st.header("🔥 Today's Phoenix Brief")

st.subheader(brief["recovery"])

st.markdown(f"### 🚴 Today's Recommendation")
st.write(brief["recommendation"])

st.markdown("### Why?")
st.write(brief["reason"])
st.divider()

st.header("Phoenix Daily Brief")

if energy >= 7 and soreness <= 4:
    st.success("Today looks like a good low-risk day. Gentle activity is fine.")
elif soreness >= 7:
    st.warning("High soreness/pain. Recovery focus today.")
else:
    st.info("Steady recovery day. Walk, eat protein, hydrate, sleep.")

st.divider()

st.header("Recent check-ins")
st.caption("Temporary history view while Phoenix is still under development.")

df = load_checkins()

if not df.empty:
    st.dataframe(df, use_container_width=True)
else:
    st.caption("No check-ins saved yet.")

    from integrations.withings import get_latest_weight

if st.button("Download latest Withings weight"):
    weight = get_latest_weight()
    st.metric("Latest Withings weight", f"{weight:.1f} kg")


st.caption("Version 0.4-alpha with local database")