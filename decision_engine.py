from athlete_context import build_athlete_context
from recovery_engine import build_recovery_profile
from readiness_engine import build_readiness_profile


def build_daily_decision():
    context = build_athlete_context()
    recovery_profile = build_recovery_profile(context)
    readiness_profile = build_readiness_profile(context, recovery_profile)

    context["recovery_profile"] = recovery_profile
    context["readiness_profile"] = readiness_profile

    decision = build_training_decision(context)
    decision["context"] = context
    decision["recovery_profile"] = recovery_profile
    decision["readiness_profile"] = readiness_profile

    return decision


def build_training_decision(context):
    if not context.get("checkin"):
        return _no_checkin_decision()

    readiness = context["readiness_profile"]

    score = readiness["readiness_score"]
    training_window = readiness["training_window"]
    risk_level = readiness["risk_level"]
    confidence = readiness["confidence"]

    if training_window == "Recovery only":
        return _decision(
            training_type="Recovery",
            duration="20–45 min",
            intensity="Very easy",
            confidence=_confidence_label(confidence),
            summary="Today looks best suited to recovery. Keep movement gentle and avoid intensity.",
            why=readiness["reasoning"],
            alternatives=["Walk with Eathen", "Mobility", "Complete rest"],
            action=[
                "Keep intensity very low.",
                "Prioritise hydration, protein, and sleep.",
                "Do not turn recovery into hidden training.",
            ],
        )

    if training_window == "Recovery or very easy movement":
        return _decision(
            training_type="Very easy movement",
            duration="20–45 min",
            intensity="Very easy",
            confidence=_confidence_label(confidence),
            summary="Readiness is limited today. A walk or very easy spin is the safest option.",
            why=readiness["reasoning"],
            alternatives=["Walk with Eathen", "Mobility", "Rest"],
            action=[
                "Only move if it makes you feel better.",
                "Avoid intensity.",
                "Use today to support tomorrow.",
            ],
        )

    if score >= 85:
        return _decision(
            training_type="Quality endurance",
            duration="60–90 min",
            intensity="Endurance with controlled intensity",
            confidence=_confidence_label(confidence),
            summary=(
                "Readiness looks excellent. Today can support quality endurance work "
                "or controlled intensity if your schedule allows."
            ),
            why=readiness["reasoning"],
            alternatives=[
                "Zone 2 endurance ride",
                "Tempo blocks",
                "Short controlled intensity session",
            ],
            action=[
                "Warm up properly.",
                "Keep intensity controlled rather than maximal.",
                "Extend endurance before chasing harder efforts.",
            ],
        )

    if score >= 70:
        return _decision(
            training_type="Endurance training",
            duration="45–75 min",
            intensity="Zone 2",
            confidence=_confidence_label(confidence),
            summary="Readiness looks good. A steady endurance ride is the best fit today.",
            why=readiness["reasoning"],
            alternatives=[
                "45-minute Zone 2 ride",
                "Long walk with Eathen",
                "Light strength and mobility",
            ],
            action=[
                "Keep the ride mostly aerobic.",
                "Finish feeling like you could do more.",
                "Fuel appropriately if riding longer than an hour.",
            ],
        )

    if score >= 55:
        return _decision(
            training_type="Easy aerobic work",
            duration="30–60 min",
            intensity="Easy Zone 2",
            confidence=_confidence_label(confidence),
            summary=(
                "Readiness is moderate. Easy aerobic work is useful, "
                "but today does not look ideal for hard intensity."
            ),
            why=readiness["reasoning"],
            alternatives=[
                "Easy spin",
                "Walk with Eathen",
                "Mobility",
            ],
            action=[
                "Start gently.",
                "Avoid chasing watts.",
                "Adjust based on how you feel after 15 minutes.",
            ],
        )

    if score >= 40:
        return _decision(
            training_type="Recovery-focused movement",
            duration="20–45 min",
            intensity="Easy",
            confidence=_confidence_label(confidence),
            summary=(
                "Readiness is low to moderate. Movement may help, "
                "but training should stay recovery-focused."
            ),
            why=readiness["reasoning"],
            alternatives=[
                "Walk with Eathen",
                "Mobility",
                "Very easy spin",
            ],
            action=[
                "Keep it easy.",
                "Stop if you feel worse.",
                "Prioritise recovery over training load.",
            ],
        )

    return _decision(
        training_type="Rest day",
        duration="—",
        intensity="None",
        confidence=_confidence_label(confidence),
        summary="Readiness is low. Rest or very gentle movement is the best choice today.",
        why=readiness["reasoning"],
        alternatives=[
            "Complete rest",
            "Short walk",
            "Mobility only",
        ],
        action=[
            "Do not force training.",
            "Prioritise food, hydration, and sleep.",
            "Let Phoenix reassess tomorrow.",
        ],
    )


def adapt_training_decision(decision, plan, extra_context=""):
    if plan == "Yes, use this plan":
        return decision

    if plan == "I have a race today":
        return _decision(
            training_type="Race preparation",
            duration="Race day",
            intensity="Race-specific",
            confidence="Medium",
            summary=(
                "Since you have a race today, the goal is not to add training load. "
                "The goal is to arrive fresh, fuelled, and ready to perform."
            ),
            why=[
                "A race changes the priority from training adaptation to performance.",
                "Avoid adding extra fatigue before the event.",
                "Use Phoenix's readiness assessment as background context.",
            ],
            alternatives=[
                "Rest until race time",
                "Short opener only if you usually respond well to it",
                "Easy walk with Eathen to stay loose",
            ],
            action=[
                "Keep any pre-race riding very easy.",
                "Fuel normally through the day.",
                "Start race-specific carbs around 60–90 minutes before the event.",
                "Warm up progressively rather than going hard from cold.",
            ],
        )

    if plan == "I want to train harder":
        return _decision(
            training_type="Controlled harder session",
            duration="45–60 min",
            intensity="Moderate with caution",
            confidence="Low–Medium",
            summary=(
                "You can train harder if you feel genuinely good, but Phoenix would keep it controlled "
                "rather than turning today into a maximal session."
            ),
            why=[
                "You are overriding the first recommendation toward more intensity.",
                "Use the first 10–15 minutes as a reality check.",
                "If readiness feels worse than expected, return to easy aerobic work.",
            ],
            alternatives=[
                "Tempo blocks",
                "Short sweet spot effort",
                "Zone 2 with a few short openers",
            ],
            action=[
                "Warm up for at least 15 minutes.",
                "If legs feel flat, switch back to Zone 2.",
                "Stop the hard work before it becomes a grind.",
            ],
        )

    if plan == "I only have 30 minutes":
        return _decision(
            training_type="Short efficient session",
            duration="30 min",
            intensity="Easy to moderate",
            confidence="Medium",
            summary=(
                "With only 30 minutes, the best option is a short, clean session that gives you movement "
                "without creating unnecessary fatigue."
            ),
            why=[
                "Time is the limiting factor today.",
                "Short sessions work best when they have a simple purpose.",
                "Consistency matters more than making this session heroic.",
            ],
            alternatives=[
                "30-minute Zone 2 spin",
                "20-minute walk with Eathen",
                "Mobility and light strength",
            ],
            action=[
                "Keep the warm-up short but gentle.",
                "Avoid chasing numbers.",
                "Finish feeling better than when you started.",
            ],
        )

    if plan == "Recovery only":
        return _decision(
            training_type="Recovery day",
            duration="20–45 min",
            intensity="Very easy",
            confidence="High",
            summary=(
                "Today should be treated as a recovery day. The goal is to support tomorrow, "
                "not prove anything today."
            ),
            why=[
                "You selected recovery as today’s priority.",
                "Recovery days are productive when they protect consistency.",
                "Easy movement is enough if it helps you feel better.",
            ],
            alternatives=[
                "Walk with Eathen",
                "Mobility",
                "Complete rest",
            ],
            action=[
                "Keep intensity very low.",
                "Prioritise protein, hydration, and sleep.",
                "Do not turn recovery into secret training.",
            ],
        )

    if plan == "Something else":
        context_text = extra_context.strip() if extra_context else "No extra context provided."

        return _decision(
            training_type="Flexible plan",
            duration="Depends on context",
            intensity="Flexible",
            confidence="Low",
            summary=(
                "Phoenix needs more detail to adapt this properly, but the safest approach is to keep "
                "today aligned with your actual life rather than forcing the original plan."
            ),
            why=[
                "You indicated that today does not fit the original recommendation.",
                f"Your context: {context_text}",
                "Phoenix will handle this better once it starts learning from repeated plan overrides.",
            ],
            alternatives=[
                "Keep it easy",
                "Short session",
                "Rest if the day is already stressful",
            ],
            action=[
                "Use your real-world constraint as the priority.",
                "Avoid forcing a workout just because it was suggested earlier.",
                "Add a note so Phoenix can learn from this later.",
            ],
        )

    return decision


def _confidence_label(confidence):
    if confidence >= 85:
        return "High"
    if confidence >= 65:
        return "Medium"
    return "Low"


def _decision(
    training_type,
    duration,
    intensity,
    confidence,
    summary,
    why,
    alternatives,
    action=None,
):
    return {
        "training_type": training_type,
        "duration": duration,
        "intensity": intensity,
        "confidence": confidence,
        "summary": summary,
        "why": why,
        "alternatives": alternatives,
        "action": action or [],
    }


def _no_checkin_decision():
    return _decision(
        training_type="Check-in needed",
        duration="—",
        intensity="Unknown",
        confidence="Low",
        summary="Complete today’s morning check-in so Phoenix can make a useful recommendation.",
        why=[
            "Phoenix does not yet have today’s energy, soreness, or Lumen data.",
        ],
        alternatives=[
            "Complete morning check-in",
            "Keep activity easy until Phoenix has more context",
        ],
    )