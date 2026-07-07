def build_training_decision(snapshot):
    today = snapshot.get("today_checkin")
    latest = snapshot.get("latest_checkin")

    checkin = today or latest

    if not checkin:
        return _no_checkin_decision()

    energy = checkin["energy"]
    soreness = checkin["soreness"]
    fat_burn = checkin["fat_burn_percent"]
    lumen_score = checkin["lumen_score"]

    reasons = _build_reasons(energy, soreness, lumen_score)

    if soreness >= 7 or energy <= 3:
        return _decision(
            training_type="Recovery",
            duration="20–45 min",
            intensity="Very easy",
            confidence="Medium",
            summary=(
                "Today looks better suited to recovery than training. "
                "Keep movement gentle and avoid intensity."
            ),
            why=reasons,
            alternatives=["Easy walk", "Mobility", "Rest day"],
        )

    if energy >= 8 and soreness <= 3 and fat_burn >= 60:
        return _decision(
            training_type="Endurance ride",
            duration="60–90 min",
            intensity="Zone 2",
            confidence="Medium",
            summary="Today looks like a good day for a steady aerobic endurance ride.",
            why=reasons,
            alternatives=["45-minute Zone 2 ride", "Light strength work", "Long walk"],
        )

    if energy >= 7 and soreness <= 4:
        return _decision(
            training_type="Easy aerobic ride",
            duration="45–60 min",
            intensity="Easy Zone 2",
            confidence="Medium",
            summary="You look ready for gentle aerobic work without pushing too hard.",
            why=reasons,
            alternatives=["Recovery walk", "Mobility", "Short endurance ride"],
        )

    if energy <= 5 or soreness >= 5:
        return _decision(
            training_type="Light recovery",
            duration="30–45 min",
            intensity="Easy",
            confidence="Medium",
            summary="Today looks like a day to keep things easy and avoid unnecessary fatigue.",
            why=reasons,
            alternatives=["Walk with Eathen", "Mobility", "Very easy spin"],
        )

    return _decision(
        training_type="Steady endurance",
        duration="45–60 min",
        intensity="Easy to moderate",
        confidence="Low–Medium",
        summary=(
            "Nothing strongly points toward either hard training or full recovery, "
            "so a steady endurance session is the safest default."
        ),
        why=reasons,
        alternatives=["Short Zone 2 ride", "Walk", "Light strength"],
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
                "Since you have a race today, the goal is no longer to add training load. "
                "The goal is to arrive fresh, fuelled, and ready to perform."
            ),
            why=[
                "A race changes the priority from training adaptation to performance.",
                "Avoid adding extra fatigue before the event.",
                "Use today’s earlier recommendation only as background context, not the main plan.",
            ],
            alternatives=[
                "Rest until race time",
                "Short opener only if you usually respond well to it",
                "Easy walk to stay loose",
            ],
            action=[
                "Keep any pre-race riding very easy.",
                "Fuel normally through the day.",
                "Start race-specific carbs around 60–90 minutes before the event.",
                "Warm up progressively rather than smashing the first effort cold.",
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
                "Phoenix does not yet have Xert/training-load data, so caution is sensible.",
                "Use the first 10–15 minutes as a reality check.",
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
                "20-minute walk",
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
                "Phoenix will handle this better once v0.8 stores and learns from these plan overrides.",
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


def _build_reasons(energy, soreness, lumen_score):
    reasons = []

    if energy >= 7:
        reasons.append(f"Energy is good at {energy}/10.")
    elif energy <= 4:
        reasons.append(f"Energy is low at {energy}/10.")
    else:
        reasons.append(f"Energy is moderate at {energy}/10.")

    if soreness <= 3:
        reasons.append(f"Soreness is low at {soreness}/10.")
    elif soreness >= 7:
        reasons.append(f"Soreness is high at {soreness}/10.")
    else:
        reasons.append(f"Soreness is moderate at {soreness}/10.")

    if lumen_score <= 3:
        reasons.append(f"Lumen score is {lumen_score}, suggesting good fat-burning availability.")
    else:
        reasons.append(f"Lumen score is {lumen_score}, suggesting more carb use today.")

    return reasons


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
        summary="Complete today's morning check-in so Phoenix can make a useful recommendation.",
        why=[
            "Phoenix does not yet have today's energy, soreness, or Lumen data.",
        ],
        alternatives=[
            "Complete morning check-in",
            "Keep activity easy until Phoenix has more context",
        ],
    )