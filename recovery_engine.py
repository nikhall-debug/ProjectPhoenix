def build_recovery_profile(context):
    subjective = _score_subjective(context)
    physiological = _score_physiological(context)
    training = _score_training(context)
    metabolic = _score_metabolic(context)

    domain_scores = [
        subjective["score"],
        physiological["score"],
        training["score"],
        metabolic["score"],
    ]

    overall_score = round(sum(domain_scores) / len(domain_scores))
    overall_label = _label_score(overall_score)

    strengths = (
        subjective["strengths"]
        + physiological["strengths"]
        + training["strengths"]
        + metabolic["strengths"]
    )

    watchouts = (
        subjective["watchouts"]
        + physiological["watchouts"]
        + training["watchouts"]
        + metabolic["watchouts"]
    )

    reasoning = (
        subjective["reasoning"]
        + physiological["reasoning"]
        + training["reasoning"]
        + metabolic["reasoning"]
    )

    return {
        "overall_score": overall_score,
        "overall_label": overall_label,
        "confidence": _confidence(context),
        "strengths": strengths,
        "watchouts": watchouts,
        "reasoning": reasoning,
        "subjective": subjective,
        "physiological": physiological,
        "training": training,
        "metabolic": metabolic,
    }


def _score_subjective(context):
    score = 50
    strengths = []
    watchouts = []
    reasoning = []

    energy = context.get("energy")
    soreness = context.get("soreness")
    mood = context.get("mood")

    if energy is not None:
        if energy >= 8:
            score += 18
            strengths.append("High energy")
        elif energy >= 6:
            score += 8
        elif energy <= 3:
            score -= 22
            watchouts.append("Low energy")
        else:
            score -= 8

        reasoning.append(f"Energy is {energy}/10.")
    else:
        reasoning.append("Energy is missing.")

    if soreness is not None:
        if soreness <= 2:
            score += 12
            strengths.append("Low soreness")
        elif soreness >= 7:
            score -= 28
            watchouts.append("High soreness")
        elif soreness >= 5:
            score -= 12
            watchouts.append("Moderate soreness")

        reasoning.append(f"Soreness is {soreness}/10.")
    else:
        reasoning.append("Soreness is missing.")

    if mood is not None:
        if mood >= 8:
            score += 8
            strengths.append("Strong motivation")
        elif mood <= 3:
            score -= 10
            watchouts.append("Low motivation")

        reasoning.append(f"Mood/motivation is {mood}/10.")
    else:
        reasoning.append("Mood is missing.")

    return _domain_result(score, strengths, watchouts, reasoning)


def _score_physiological(context):
    score = 50
    strengths = []
    watchouts = []
    reasoning = []

    baselines = context.get("baselines", {})

    score = _apply_baseline(
        score,
        baselines.get("hrv"),
        label="HRV",
        higher_is_better=True,
        strengths=strengths,
        watchouts=watchouts,
        reasoning=reasoning,
    )

    score = _apply_baseline(
        score,
        baselines.get("resting_hr"),
        label="Resting HR",
        higher_is_better=False,
        strengths=strengths,
        watchouts=watchouts,
        reasoning=reasoning,
    )

    score = _apply_baseline(
        score,
        baselines.get("sleep"),
        label="Sleep",
        higher_is_better=True,
        strengths=strengths,
        watchouts=watchouts,
        reasoning=reasoning,
    )

    score = _apply_baseline(
        score,
        baselines.get("respiratory_rate"),
        label="Respiratory rate",
        higher_is_better=False,
        strengths=strengths,
        watchouts=watchouts,
        reasoning=reasoning,
        gentle=True,
    )

    blood_oxygen = context.get("blood_oxygen")
    if blood_oxygen is not None:
        if blood_oxygen >= 95:
            score += 5
            strengths.append("Normal blood oxygen")
        else:
            score -= 8
            watchouts.append("Lower blood oxygen")
        reasoning.append(f"Blood oxygen latest value is {blood_oxygen:.0f}%.")

    return _domain_result(score, strengths, watchouts, reasoning)


def _score_training(context):
    score = 50
    strengths = []
    watchouts = []
    reasoning = []

    xert_status = context.get("xert_status")
    training_load = context.get("xert_training_load")
    target_xss = context.get("xert_target_xss")

    if xert_status:
        reasoning.append(f"Xert status is {xert_status}.")

        if xert_status in ["Fresh", "Very Fresh"]:
            score += 18
            strengths.append("Fresh training status")
        elif xert_status == "Tired":
            score -= 15
            watchouts.append("Xert tired status")
        elif xert_status == "Very Tired":
            score -= 28
            watchouts.append("High accumulated training fatigue")
        elif xert_status == "Detraining":
            score += 5
            strengths.append("Low recent training load")
    else:
        reasoning.append("Xert status is missing.")

    if training_load is not None:
        reasoning.append(f"Xert training load is {training_load:.1f}.")

    if target_xss is not None:
        reasoning.append(f"Xert target XSS is {target_xss:.0f}.")

        if target_xss == 0:
            score -= 4
            reasoning.append("Xert is not asking for additional training load today.")

    return _domain_result(score, strengths, watchouts, reasoning)


def _score_metabolic(context):
    score = 50
    strengths = []
    watchouts = []
    reasoning = []

    lumen_score = context.get("lumen_score")
    fat_burn = context.get("fat_burn_percent")

    if lumen_score is not None:
        reasoning.append(f"Lumen score is {lumen_score}.")

        if lumen_score <= 3:
            score += 12
            strengths.append("Good fat-burning availability")
        else:
            score -= 6
            watchouts.append("Higher carbohydrate use")
    else:
        reasoning.append("Lumen score is missing.")

    if fat_burn is not None:
        reasoning.append(f"Estimated fat burn is {fat_burn}%.")

        if fat_burn >= 60:
            score += 8
            strengths.append("Fat burning is dominant")
        elif fat_burn <= 40:
            score -= 5
            watchouts.append("Lower fat-burning percentage")

    return _domain_result(score, strengths, watchouts, reasoning)


def _apply_baseline(
    score,
    baseline,
    label,
    higher_is_better,
    strengths,
    watchouts,
    reasoning,
    gentle=False,
):
    if not baseline or baseline.get("latest") is None:
        reasoning.append(f"{label} baseline is unavailable.")
        return score

    delta = baseline.get("delta_percent")
    status = baseline.get("status")
    summary = baseline.get("summary")

    if summary:
        reasoning.append(summary)
    else:
        reasoning.append(f"{label} is {status}.")

    if delta is None:
        return score

    multiplier = 0.5 if gentle else 1.0

    if higher_is_better:
        if delta >= 15:
            score += int(16 * multiplier)
            strengths.append(f"{label} well above baseline")
        elif delta >= 5:
            score += int(8 * multiplier)
            strengths.append(f"{label} above baseline")
        elif delta <= -15:
            score -= int(18 * multiplier)
            watchouts.append(f"{label} well below baseline")
        elif delta <= -5:
            score -= int(8 * multiplier)
            watchouts.append(f"{label} below baseline")
    else:
        if delta <= -15:
            score += int(16 * multiplier)
            strengths.append(f"{label} well below baseline")
        elif delta <= -5:
            score += int(8 * multiplier)
            strengths.append(f"{label} below baseline")
        elif delta >= 15:
            score -= int(18 * multiplier)
            watchouts.append(f"{label} well above baseline")
        elif delta >= 5:
            score -= int(8 * multiplier)
            watchouts.append(f"{label} above baseline")

    return score


def _domain_result(score, strengths, watchouts, reasoning):
    score = max(0, min(100, round(score)))

    return {
        "score": score,
        "label": _label_score(score),
        "strengths": strengths,
        "watchouts": watchouts,
        "reasoning": reasoning,
        "reasons": reasoning,
    }


def _confidence(context):
    score = 40

    if context.get("today_checkin"):
        score += 15
    if context.get("baselines"):
        score += 15
    if context.get("xert_status"):
        score += 10
    if context.get("hrv") is not None:
        score += 10
    if context.get("sleep_total") is not None:
        score += 10

    return min(score, 100)


def _label_score(score):
    if score >= 80:
        return "Excellent"
    if score >= 65:
        return "Good"
    if score >= 45:
        return "Moderate"
    return "Low"