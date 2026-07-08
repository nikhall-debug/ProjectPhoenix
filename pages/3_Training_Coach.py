from datetime import date

import streamlit as st

from database import init_db, save_coach_plan_override
from decision_engine import build_daily_decision, adapt_training_decision
from narrative_engine import build_coach_narrative

def show_baseline(title, baseline, unit=""):
    if baseline["latest"] is None:
        st.write(f"**{title}**")
        st.caption("No data")
        return

    delta = baseline["delta_percent"]

    if delta is None:
        delta_text = "-"
    elif delta >= 0:
        delta_text = f"▲ {delta:.1f}%"
    else:
        delta_text = f"▼ {abs(delta):.1f}%"

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])

    c1.write(f"**{title}**")
    c2.metric("Latest", f"{baseline['latest']:.1f} {unit}")
    c3.metric("30-day Avg", f"{baseline['average_30']:.1f} {unit}")
    c4.metric("Δ", delta_text)


init_db()

st.set_page_config(page_title="Phoenix Coach", page_icon="🚴", layout="wide")

initial_decision = build_daily_decision()
context = initial_decision["context"]
recovery_profile = initial_decision["recovery_profile"]
readiness_profile = initial_decision["readiness_profile"]
coach_narrative = build_coach_narrative(
    context,
    recovery_profile,
    readiness_profile,
    initial_decision,
)
baselines = context["baselines"]
baseline_hrv = baselines["hrv"]
baseline_resting_hr = baselines["resting_hr"]
baseline_sleep = baselines["sleep"]

st.title("🚴 Training Coach")
st.caption("Phoenix turns today's readiness into a practical training recommendation.")

st.divider()

st.header("🧠 Today's Coaching")
st.subheader(coach_narrative["headline"])
st.write(coach_narrative["opener"])
st.write(coach_narrative["body"])
st.info(coach_narrative["coaching_note"])

st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Readiness",
        readiness_profile["readiness_label"],
        f'{readiness_profile["readiness_score"]}/100',
    )

with col2:
    st.metric("Risk", readiness_profile["risk_level"])

with col3:
    st.metric("Confidence", f'{readiness_profile["confidence"]}%')

st.subheader("🎯 Today's Opportunity")
st.success(readiness_profile["training_window"])

st.subheader(initial_decision["training_type"])

m1, m2, m3 = st.columns(3)

with m1:
    st.metric("Duration", initial_decision["duration"])

with m2:
    st.metric("Intensity", initial_decision["intensity"])

with m3:
    st.metric("Confidence", initial_decision["confidence"])

st.write(initial_decision["summary"])

col_strengths, col_watchouts = st.columns(2)

with col_strengths:
    st.subheader("👍 Working in your favour")
    if readiness_profile["opportunities"]:
        for item in readiness_profile["opportunities"][:6]:
            st.write(f"✅ {item}")
    else:
        st.write("No strong positive signals yet.")

with col_watchouts:
    st.subheader("⚠️ Things to watch")
    if readiness_profile["limiting_factors"]:
        for item in readiness_profile["limiting_factors"][:6]:
            st.write(f"• {item}")
    else:
        st.write("No major limiting factors.")

with st.expander("🧠 Why Phoenix thinks this"):
    for reason in readiness_profile["reasoning"]:
        st.write(f"- {reason}")

if initial_decision.get("action"):
    st.info("Action plan:")
    for item in initial_decision["action"]:
        st.write(f"- {item}")

st.divider()

st.header("Adjust today's plan")

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

if plan != "Yes, use this plan":
    st.subheader("Adjusted Plan")
    st.write(decision["summary"])

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Duration", decision["duration"])

    with c2:
        st.metric("Intensity", decision["intensity"])

    with c3:
        st.metric("Confidence", decision["confidence"])

    if decision.get("action"):
        st.info("Adjusted action plan:")
        for item in decision["action"]:
            st.write(f"- {item}")

    with st.expander("Why this adjustment?"):
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

with st.expander("🧠 Athlete Context (Developer)", expanded=False):
    st.subheader("Recovery Profile")

    st.write({
        "Overall Score": recovery_profile["overall_score"],
        "Overall Label": recovery_profile["overall_label"],
        "Confidence": recovery_profile["confidence"],
        "Strengths": recovery_profile["strengths"],
        "Watchouts": recovery_profile["watchouts"],
        "Subjective": recovery_profile["subjective"],
        "Physiological": recovery_profile["physiological"],
        "Training": recovery_profile["training"],
        "Metabolic": recovery_profile["metabolic"],
    })

    st.divider()

    st.subheader("Readiness Profile")

    st.write(readiness_profile)

    st.divider()

    st.subheader("📈 Personal Baselines")

    show_baseline("HRV", baseline_hrv, "ms")
    show_baseline("Resting HR", baseline_resting_hr, "bpm")
    show_baseline("Sleep", baseline_sleep, "h")

    st.divider()

    st.subheader("Morning Check-in")
    st.write({
        "Energy": context["energy"],
        "Mood": context["mood"],
        "Soreness": context["soreness"],
        "Lumen": context["lumen_score"],
    })

    st.subheader("Body")
    st.write({
        "Weight": context["weight"],
        "Body Fat": context["body_fat"],
        "Muscle": context["muscle"],
        "Blood Pressure": f'{context["systolic"]}/{context["diastolic"]}',
        "PWV": context["pwv"],
    })

    st.subheader("Apple Health")
    st.write({
        "HRV": context["hrv"],
        "Resting HR": context["resting_hr"],
        "Respiratory Rate": context["respiratory_rate"],
        "Blood Oxygen": context["blood_oxygen"],
        "Sleep": context["sleep_total"],
        "Deep": context["sleep_deep"],
        "REM": context["sleep_rem"],
        "Core": context["sleep_core"],
        "Awake": context["sleep_awake"],
        "Steps": context["steps"],
        "Exercise Minutes": context["exercise_minutes"],
        "Active Energy": context["active_energy"],
        "Walking Distance": context["walking_distance"],
        "Walking HR": context["walking_hr"],
    })

    st.subheader("Xert")
    st.write({
        "Status": context["xert_status"],
        "FTP": context["xert_ftp"],
        "LTP": context["xert_ltp"],
        "Training Load": context["xert_training_load"],
        "Target XSS": context["xert_target_xss"],
    })

st.caption("Project Phoenix v0.9.2-alpha")