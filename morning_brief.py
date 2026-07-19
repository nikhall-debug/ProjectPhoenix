def build_morning_brief(
    context,
    recovery_profile,
    baselines,
    health_intelligence=None,
    workout_intelligence=None,
):
    """
    Builds the main Phoenix morning briefing.

    Morning Brief does not analyse raw health, recovery, metabolism,
    or workout data directly.

    It simply assembles the outputs from the specialist engines into
    a readable daily summary.
    """

    highlights = []

    if health_intelligence:
        health_summary = health_intelligence.get("summary")
        health_signals = health_intelligence.get("signals", [])

        if health_summary:
            highlights.append(f"❤️ {health_summary}")

        for signal in health_signals[:3]:
            highlights.append(f"• {signal}")

    if workout_intelligence:
        workout_summary = workout_intelligence.get("summary")
        workout_signals = workout_intelligence.get("signals", [])

        if workout_summary:
            highlights.append(f"🚴 {workout_summary}")

        for signal in workout_signals[:3]:
            highlights.append(f"• {signal}")

    overall_score = recovery_profile["overall_score"]
    overall_label = recovery_profile["overall_label"]

    recommendation = _build_recommendation(
        context=context,
        recovery_profile=recovery_profile,
        health_intelligence=health_intelligence,
        workout_intelligence=workout_intelligence,
    )

    return {
        "recovery_label": overall_label,
        "recovery_score": overall_score,
        "training_label": _training_label(context),
        "metabolism_label": _metabolism_label(context),
        "highlights": highlights,
        "recommendation": recommendation,
        "confidence": _confidence(
            context=context,
            baselines=baselines,
            health_intelligence=health_intelligence,
            workout_intelligence=workout_intelligence,
        ),
        "health_intelligence": health_intelligence,
        "workout_intelligence": workout_intelligence,
    }


def _build_recommendation(
    context,
    recovery_profile,
    health_intelligence=None,
    workout_intelligence=None,
):
    score = recovery_profile["overall_score"]

    if health_intelligence:
        health_status = health_intelligence.get("status")
        health_readiness = health_intelligence.get("readiness")
        health_recommendations = health_intelligence.get("recommendations", [])

        if health_status in ["warning", "poor"]:
            if health_recommendations:
                return health_recommendations[0]

        if health_readiness in ["Low", "Reduced"]:
            return "Health signals look reduced today. Keep training easy unless you feel clearly better than the data suggests."

    if workout_intelligence:
        fatigue = workout_intelligence.get("fatigue_generated")
        load = workout_intelligence.get("load")
        workout_recommendations = workout_intelligence.get("recommendations", [])

        if fatigue == "High":
            if workout_recommendations:
                return workout_recommendations[0]

            return "Recent training appears to have generated significant fatigue. Prioritise recovery or easy aerobic work today."

        if load == "Very high":
            return "Recent training load was very high. Today should lean toward recovery unless readiness is exceptional."

    if score >= 75:
        return "Recovery looks strong today. This is a good opportunity for endurance work if your schedule allows."

    if score >= 55:
        return "Recovery looks usable but not perfect. Controlled aerobic work is the sensible choice."

    return "Recovery looks mixed today. Keep things easy and avoid unnecessary intensity."


def _training_label(context):
    xert_status = context.get("xert_status")

    if not xert_status:
        return "Unknown"

    if xert_status in ["Fresh", "Very Fresh"]:
        return "Fresh"

    if xert_status in ["Tired", "Very Tired"]:
        return "Fatigued"

    return xert_status


def _metabolism_label(context):
    lumen_score = context.get("lumen_score")

    if lumen_score is None:
        return "Unknown"

    if lumen_score <= 3:
        return "Fat Burning"

    return "Carb Using"


def _confidence(
    context,
    baselines,
    health_intelligence=None,
    workout_intelligence=None,
):
    score = 40

    if health_intelligence:
        score += 20

    if workout_intelligence:
        score += 15

    if context.get("today_checkin"):
        score += 10

    if context.get("xert_status"):
        score += 5

    if baselines:
        score += 5

    return min(score, 95)