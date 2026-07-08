from datetime import date

import streamlit as st

from database import init_db, save_coach_plan_override
from decision_engine import build_daily_decision, adapt_training_decision


init_db()

st.set_page_config(page_title="Phoenix Coach", page_icon="🚴", layout="wide")

initial_decision = build_daily_decision()

st.title("🚴 Training Coach")
st.caption("Phoenix makes the first suggestion. You decide whether it fits today.")

st.divider()

st.header("Phoenix Recommendation")

plan = st.radio(
    "Does this fit today’s plans?",
    [
        "Yes, use this plan",
        "I have a race today",
        "I want to train harder",
        "I only have 30 minutes",
        "Recovery only",
        "Something else",
    ],
)

extra_context = st.text_area(
    "Optional context",
    placeholder="Example: I have a race tonight, I slept badly, or I only have 45 minutes...",
)

decision = adapt_training_decision(initial_decision, plan, extra_context)

st.subheader(decision["training_type"])

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Duration", decision["duration"])

with col2:
    st.metric("Intensity", decision["intensity"])

with col3:
    st.metric("Confidence", decision["confidence"])

st.write(decision["summary"])

if decision.get("action"):
    st.info("Action plan:")
    for item in decision["action"]:
        st.write(f"- {item}")

with st.expander("💡 Why?"):
    for reason in decision["why"]:
        st.write(f"- {reason}")

with st.expander("🔁 Alternatives"):
    for alternative in decision["alternatives"]:
        st.write(f"- {alternative}")

if st.button("💾 Save today's plan"):
    save_coach_plan_override(
        override_date=date.today(),
        original_training_type=initial_decision["training_type"],
        selected_plan=plan,
        extra_context=extra_context,
        final_training_type=decision["training_type"],
    )

    st.success("Today's coaching decision has been saved.")

st.divider()

st.caption("Project Phoenix v0.8.6-alpha")