from datetime import date


def generate_insights(snapshot):
    insights = []

    if snapshot is None:
        return insights

    snapshot_percent = snapshot.get("snapshot_percent", 0)

    if snapshot_percent < 50:
        insights.append(
            {
                "level": "info",
                "icon": "ℹ️",
                "title": "Phoenix is still building today's picture",
                "text": "Some of today's data has not yet arrived.",
                "explanation": (
                    "Phoenix combines multiple sources before drawing conclusions. "
                    "The more complete today's data, the more reliable its coaching becomes."
                ),
            }
        )

    if snapshot.get("withings_status") == "stale":
        insights.append(
            {
                "level": "warning",
                "icon": "⚖️",
                "title": "Withings hasn't updated today",
                "text": "Your latest body measurements are from an earlier day.",
                "explanation": (
                    "Daily weight isn't essential, but Phoenix uses recent body "
                    "measurements to improve long-term trend analysis."
                ),
            }
        )

    if snapshot.get("apple_health_status") == "stale":
        insights.append(
            {
                "level": "warning",
                "icon": "⌚",
                "title": "Apple Health hasn't updated today",
                "text": "Recovery and activity data may be incomplete.",
                "explanation": (
                    "Sleep, HRV, resting heart rate and activity all contribute to "
                    "Phoenix's understanding of your readiness."
                ),
            }
        )

    if snapshot.get("latest_checkin") is None:
        insights.append(
            {
                "level": "info",
                "icon": "📝",
                "title": "Morning check-in missing",
                "text": "Your subjective recovery hasn't been recorded today.",
                "explanation": (
                    "How you actually feel is one of the strongest predictors of "
                    "training quality. Phoenix combines objective and subjective data."
                ),
            }
        )

    if not insights:
        insights.append(
            {
                "level": "win",
                "icon": "✅",
                "title": "Phoenix has a complete picture",
                "text": "Today's data looks complete enough for meaningful coaching.",
                "explanation": (
                    "The major data sources appear to have synchronized successfully, "
                    "giving Phoenix a solid foundation for today's recommendations."
                ),
            }
        )

    return insights


def generate_daily_focus(insights):
    """
    Return a single sentence that summarises today's priority.
    """

    warnings = [i for i in insights if i["level"] == "warning"]
    infos = [i for i in insights if i["level"] == "info"]
    wins = [i for i in insights if i["level"] == "win"]

    if warnings:
        return warnings[0]["title"]

    if infos:
        return infos[0]["title"]

    if wins:
        return wins[0]["title"]

    return "Phoenix has no major focus for today."