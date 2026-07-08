def build_readiness_profile(context, recovery_profile):
    """
    Builds Phoenix's readiness intelligence profile.

    Recovery = how well the body has bounced back.
    Readiness = what kind of training today can support.
    """

    recovery_score = recovery_profile.get("overall_score", 50)
    recovery_label = recovery_profile.get("overall_label", "Unknown")

    readiness_score = recovery_score
    opportunities = []
    limiting_factors = []
    reasoning = []

    _apply_recovery_signals(
        recovery_profile,
        opportunities,
        limiting_factors,
        reasoning,
    )

    readiness_score = _apply_subjective_modifiers(
        readiness_score,
        context,
        opportunities,
        limiting_factors,
        reasoning,
    )

    readiness_score = _apply_training_modifiers(
        readiness_score,
        context,
        opportunities,
        limiting_factors,
        reasoning,
    )

    readiness_score = _apply_metabolic_modifiers(
        readiness_score,
        context,
        opportunities,
        limiting_factors,
        reasoning,
    )

    readiness_score = max(0, min(100, round(readiness_score)))

    return {
        "readiness_score": readiness_score,
        "readiness_label": _label_readiness(readiness_score),
        "training_window": _training_window(readiness_score, context),
        "risk_level": _risk_level(readiness_score, recovery_profile),
        "recovery_label": recovery_label,
        "opportunities": opportunities,
        "limiting_factors": limiting_factors,
        "reasoning": reasoning,
        "confidence": _confidence(context, recovery_profile),
    }


def _apply_recovery_signals(
    recovery_profile,
    opportunities,
    limiting_factors,
    reasoning,
):
    strengths = recovery_profile.get("strengths", [])
    watchouts = recovery_profile.get("watchouts", [])

    for strength in strengths[:4]:
        opportunities.append(strength)

    for watchout in watchouts[:4]:
        limiting_factors.append(watchout)

    if strengths:
        reasoning.append("Recovery profile shows useful positive signals.")

    if watchouts:
        reasoning.append("Recovery profile also contains some watchouts.")


def _apply_subjective_modifiers(
    score,
    context,
    opportunities,
    limiting_factors,
    reasoning,
):
    energy = context.get("energy")
    soreness = context.get("soreness")
    mood = context.get("mood")

    if energy is not None:
        if energy >= 8:
            score += 6
            opportunities.append("Strong subjective energy")
            reasoning.append("High energy increases today's readiness.")
        elif energy <= 3:
            score -= 12
            limiting_factors.append("Low subjective energy")
            reasoning.append("Low energy limits today's readiness.")

    if soreness is not None:
        if soreness >= 7:
            score -= 18
            limiting_factors.append("High soreness")
            reasoning.append("High soreness strongly limits readiness.")
        elif soreness >= 5:
            score -= 8
            limiting_factors.append("Moderate soreness")
            reasoning.append("Elevated soreness suggests caution.")
        elif soreness <= 2:
            score += 4
            opportunities.append("Low soreness")
            reasoning.append("Low soreness supports training readiness.")

    if mood is not None:
        if mood >= 8:
            score += 3
            opportunities.append("Strong motivation")
        elif mood <= 3:
            score -= 5
            limiting_factors.append("Low motivation")

    return score


def _apply_training_modifiers(
    score,
    context,
    opportunities,
    limiting_factors,
    reasoning,
):
    xert_status = context.get("xert_status")
    target_xss = context.get("xert_target_xss")

    if xert_status:
        if xert_status in ["Fresh", "Very Fresh"]:
            score += 8
            opportunities.append("Fresh training status")
            reasoning.append("Xert freshness supports training today.")
        elif xert_status == "Detraining":
            score += 3
            opportunities.append("Low recent training load")
            reasoning.append("Recent training load appears low.")
        elif xert_status == "Tired":
            score -= 10
            limiting_factors.append("Xert tired status")
            reasoning.append("Xert tired status suggests reduced intensity.")
        elif xert_status == "Very Tired":
            score -= 18
            limiting_factors.append("High accumulated fatigue")
            reasoning.append("Very tired training status strongly limits readiness.")

    if target_xss is not None and target_xss == 0:
        limiting_factors.append("No Xert target load today")
        reasoning.append("Xert is not currently asking for training load today.")

    return score


def _apply_metabolic_modifiers(
    score,
    context,
    opportunities,
    limiting_factors,
    reasoning,
):
    lumen_score = context.get("lumen_score")
    fat_burn = context.get("fat_burn_percent")

    if lumen_score is not None:
        if lumen_score <= 3:
            score += 4
            opportunities.append("Good fat-burning availability")
            reasoning.append("Lumen supports aerobic work today.")
        else:
            score -= 3
            limiting_factors.append("Higher carbohydrate use")
            reasoning.append("Lumen suggests more carbohydrate use today.")

    if fat_burn is not None and fat_burn >= 60:
        score += 3

    return score


def _training_window(score, context):
    soreness = context.get("soreness")
    energy = context.get("energy")

    if soreness is not None and soreness >= 7:
        return "Recovery only"

    if energy is not None and energy <= 3:
        return "Recovery or very easy movement"

    if score >= 85:
        return "Quality endurance or controlled intensity"

    if score >= 70:
        return "Endurance training"

    if score >= 55:
        return "Easy aerobic work"

    if score >= 40:
        return "Recovery-focused movement"

    return "Rest or very gentle movement"


def _risk_level(score, recovery_profile):
    watchouts = recovery_profile.get("watchouts", [])

    if score >= 75 and len(watchouts) <= 1:
        return "Low"

    if score >= 55:
        return "Moderate"

    return "High"


def _confidence(context, recovery_profile):
    score = recovery_profile.get("confidence", 50)

    if context.get("baselines"):
        score += 5

    if context.get("xert_status"):
        score += 5

    return min(score, 100)


def _label_readiness(score):
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 55:
        return "Moderate"
    if score >= 40:
        return "Low"
    return "Very Low"