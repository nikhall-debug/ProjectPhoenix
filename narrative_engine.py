def build_coach_narrative(context, recovery_profile, readiness_profile, decision):
    """
    Turns Phoenix's structured intelligence into a short coaching narrative.
    """

    readiness_label = readiness_profile.get("readiness_label", "Unknown")
    readiness_score = readiness_profile.get("readiness_score")
    training_window = readiness_profile.get("training_window")
    risk_level = readiness_profile.get("risk_level")
    opportunities = readiness_profile.get("opportunities", [])
    limiting_factors = readiness_profile.get("limiting_factors", [])

    opener = _build_opener(readiness_label, readiness_score, training_window)
    body = _build_body(opportunities, limiting_factors, risk_level)
    coaching_note = _build_coaching_note(decision, readiness_profile)

    return {
        "headline": _headline(readiness_label, training_window),
        "opener": opener,
        "body": body,
        "coaching_note": coaching_note,
        "short_summary": f"{opener} {body}",
    }


def _headline(readiness_label, training_window):
    if readiness_label in ["Excellent", "Good"]:
        return f"Today looks like a good opportunity for {training_window.lower()}."

    if readiness_label == "Moderate":
        return f"Today looks suitable for {training_window.lower()}."

    return "Today looks better suited to recovery-focused work."


def _build_opener(readiness_label, readiness_score, training_window):
    if readiness_score is None:
        return "Phoenix does not yet have enough information to judge today clearly."

    return (
        f"Your readiness is {readiness_label.lower()} today "
        f"at {readiness_score}/100, pointing toward {training_window.lower()}."
    )


def _build_body(opportunities, limiting_factors, risk_level):
    positives = opportunities[:3]
    watchouts = limiting_factors[:2]

    if positives and watchouts:
        return (
            f"The main positives are { _join_items(positives) }. "
            f"The main things to watch are { _join_items(watchouts) }. "
            f"Overall risk looks {risk_level.lower()}."
        )

    if positives:
        return (
            f"The main positives are { _join_items(positives) }. "
            f"Overall risk looks {risk_level.lower()}."
        )

    if watchouts:
        return (
            f"The main things to watch are { _join_items(watchouts) }. "
            f"Overall risk looks {risk_level.lower()}."
        )

    return f"There are no major standout signals today. Overall risk looks {risk_level.lower()}."


def _build_coaching_note(decision, readiness_profile):
    training_type = decision.get("training_type", "training")
    risk_level = readiness_profile.get("risk_level", "Unknown")

    if risk_level == "Low":
        return (
            f"Use today for {training_type.lower()}, but keep it controlled. "
            "Build the session rather than forcing intensity early."
        )

    if risk_level == "Moderate":
        return (
            f"{training_type} is still reasonable, but stay flexible. "
            "Use the first 15 minutes as a reality check."
        )

    return (
        "Keep the goal conservative today. Recovery and consistency matter more "
        "than adding training load."
    )


def _join_items(items):
    if not items:
        return ""

    if len(items) == 1:
        return items[0].lower()

    if len(items) == 2:
        return f"{items[0].lower()} and {items[1].lower()}"

    return ", ".join(item.lower() for item in items[:-1]) + f", and {items[-1].lower()}"