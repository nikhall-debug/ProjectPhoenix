def daily_brief(energy, soreness, fat_burn_percent):
    """
    Returns today's recommendation.
    """

    if soreness >= 7:
        return {
            "recovery": "🔴 Recovery",
            "recommendation": "Rest today.",
            "reason": "Pain and soreness are too high."
        }

    if energy >= 8 and fat_burn_percent >= 60:
        return {
            "recovery": "🟢 Excellent",
            "recommendation": "Great day for quality training.",
            "reason": "Energy is high and fat burning is strong."
        }

    if energy >= 6:
        return {
            "recovery": "🟢 Good",
            "recommendation": "Good day for Zone 2.",
            "reason": "You appear reasonably well recovered."
        }

    return {
        "recovery": "🟡 Moderate",
        "recommendation": "Recovery walk or easy spin.",
        "reason": "Energy is a little low today."
    }