def build_morning_brief(context, recovery_profile, baselines):
    """
    Builds the main Phoenix morning briefing.

    This translates raw data into a simple, readable daily summary.
    """

    highlights = []

    hrv = baselines.get("hrv")
    resting_hr = baselines.get("resting_hr")
    sleep = baselines.get("sleep")

    if sleep and sleep.get("delta_percent") is not None:
        if sleep["delta_percent"] >= 10:
            highlights.append("🟢 You slept noticeably more than your normal.")
        elif sleep["delta_percent"] <= -10:
            highlights.append("🟡 Sleep was lower than your usual.")

    if hrv and hrv.get("delta_percent") is not None:
        if hrv["delta_percent"] >= 10:
            highlights.append("🟢 HRV is above your normal baseline.")
        elif hrv["delta_percent"] <= -10:
            highlights.append("🟡 HRV is below your normal baseline.")
        else:
            highlights.append("🟢 HRV is close to your normal range.")

    if resting_hr and resting_hr.get("delta_percent") is not None:
        if resting_hr["delta_percent"] <= -5:
            highlights.append("🟢 Resting HR is lower than your normal.")
        elif resting_hr["delta_percent"] >= 5:
            highlights.append("🟡 Resting HR is slightly above your normal.")

    xert_status = context.get("xert_status")
    if xert_status:
        highlights.append(f"🔵 Xert status: {xert_status}.")

    lumen_score = context.get("lumen_score")
    if lumen_score is not None:
        if lumen_score <= 3:
            highlights.append("🟢 Lumen suggests good fat-burning availability.")
        else:
            highlights.append("🟡 Lumen suggests more carbohydrate use today.")

    overall_score = recovery_profile["overall_score"]
    overall_label = recovery_profile["overall_label"]

    recommendation = _build_recommendation(context, recovery_profile)

    return {
        "recovery_label": overall_label,
        "recovery_score": overall_score,
        "training_label": _training_label(context),
        "metabolism_label": _metabolism_label(context),
        "highlights": highlights,
        "recommendation": recommendation,
        "confidence": _confidence(context, baselines),
    }


def _build_recommendation(context, recovery_profile):
    score = recovery_profile["overall_score"]
    energy = context.get("energy")
    soreness = context.get("soreness")

    if soreness is not None and soreness >= 7:
        return "Today looks better suited to recovery than training. Keep movement gentle."

    if energy is not None and energy <= 3:
        return "Energy is low today. Recovery, walking, or a very easy spin would be sensible."

    if score >= 75:
        return "Today looks like a good opportunity for endurance work if your schedule allows."

    if score >= 55:
        return "Today looks suitable for controlled aerobic work rather than hard intensity."

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


def _confidence(context, baselines):
    score = 50

    if context.get("today_checkin"):
        score += 15

    if context.get("xert_status"):
        score += 10

    if context.get("hrv") is not None:
        score += 10

    if context.get("sleep_total") is not None:
        score += 10

    if baselines.get("hrv", {}).get("average") is not None:
        score += 5

    return min(score, 95)