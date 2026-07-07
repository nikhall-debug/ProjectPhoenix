def generate_insights(snapshot):
    insights = []

    insights.extend(_missing_checkin_insights(snapshot))
    insights.extend(_weight_insights(snapshot))
    insights.extend(_muscle_insights(snapshot))
    insights.extend(_blood_pressure_insights(snapshot))
    insights.extend(_lumen_insights(snapshot))
    insights.extend(_recovery_insights(snapshot))

    insights = sorted(insights, key=lambda item: item["priority"], reverse=True)
    return insights[:5]


def generate_daily_focus(insights):
    if not insights:
        return "Complete your morning check-in so Phoenix can give a clearer focus for today."

    warnings = [item for item in insights if item.get("level") == "warning"]

    if warnings:
        top = warnings[0]
    else:
        top = insights[0]

    title = top["title"].lower()
    category = top["category"]

    if category == "Snapshot":
        return "Complete today’s check-in so Phoenix can give reliable daily guidance."

    if category == "Recovery" and "caution" in title:
        return "Keep today easy and prioritise recovery."

    if category == "Recovery":
        return "You look ready for gentle training or steady endurance."

    if category == "Body":
        return "Stay consistent with nutrition, protein, and recovery."

    if category == "Metabolism":
        return "Use your Lumen result as context for fuelling today."

    if category == "Cardiovascular":
        return "Keep an eye on cardiovascular trends, but avoid overreacting to one reading."

    return "Focus on consistency today."


def _today_checkin(snapshot):
    return snapshot.get("today_checkin")


def _weight_insights(snapshot):
    insights = []
    weight = snapshot.get("weight")

    if not weight or weight.get("delta_30d") is None:
        return insights

    if weight["delta_30d"] < -0.5:
        insights.append({
            "level": "win",
            "category": "Body",
            "icon": "🎯",
            "title": "Weight trend",
            "text": "Your weight is continuing to trend downward.",
            "action": "Keep doing what you are doing. Focus on consistency, protein, and recovery.",
            "priority": 8,
            "explanation": (
                f"Your latest weight is {weight['current']:.1f} kg. "
                f"That is {abs(weight['delta_30d']):.1f} kg lower than around 30 days ago."
            ),
            "evidence": [
                f"Current weight: {weight['current']:.1f} kg",
                f"30-day change: {weight['delta_30d']:.1f} kg",
            ],
        })

    elif weight["delta_30d"] > 0.5:
        insights.append({
            "level": "warning",
            "category": "Body",
            "icon": "🟠",
            "title": "Weight trend",
            "text": "Your weight is higher than around 30 days ago.",
            "action": "Do not overreact. Check the 7-day trend, hydration, food volume, and recent training load.",
            "priority": 7,
            "explanation": (
                "This is not automatically a problem, but it may be worth checking whether this is "
                "water retention, training-related, food volume, or a true upward trend."
            ),
            "evidence": [
                f"Current weight: {weight['current']:.1f} kg",
                f"30-day change: +{weight['delta_30d']:.1f} kg",
            ],
        })

    return insights


def _muscle_insights(snapshot):
    insights = []
    muscle = snapshot.get("muscle")

    if not muscle or muscle.get("delta_30d") is None:
        return insights

    if muscle["delta_30d"] > -0.3:
        insights.append({
            "level": "win",
            "category": "Body",
            "icon": "💪",
            "title": "Muscle maintained",
            "text": "Muscle mass appears stable while weight is changing.",
            "action": "Continue prioritising protein and light strength work.",
            "priority": 7,
            "explanation": (
                f"Your muscle mass changed by {muscle['delta_30d']:.1f} kg over roughly 30 days, "
                "which suggests you are not losing meaningful muscle."
            ),
            "evidence": [
                f"Current muscle mass: {muscle['current']:.1f} kg",
                f"30-day change: {muscle['delta_30d']:.1f} kg",
            ],
        })

    elif muscle["delta_30d"] <= -0.5:
        insights.append({
            "level": "warning",
            "category": "Body",
            "icon": "🟠",
            "title": "Muscle trend",
            "text": "Muscle mass appears lower than around 30 days ago.",
            "action": "Check protein intake, strength consistency, and whether this persists over several readings.",
            "priority": 8,
            "explanation": (
                "Withings muscle estimates can fluctuate, but if this persists it may be worth checking "
                "protein intake, strength training consistency, and overall recovery."
            ),
            "evidence": [
                f"Current muscle mass: {muscle['current']:.1f} kg",
                f"30-day change: {muscle['delta_30d']:.1f} kg",
            ],
        })

    return insights


def _blood_pressure_insights(snapshot):
    insights = []
    systolic = snapshot.get("systolic")
    diastolic = snapshot.get("diastolic")

    if not systolic or not diastolic:
        return insights

    if systolic["value"] >= 140 or diastolic["value"] >= 90:
        insights.append({
            "level": "warning",
            "category": "Cardiovascular",
            "icon": "🟠",
            "title": "Blood pressure",
            "text": "Your latest blood pressure reading is higher than ideal.",
            "action": "Recheck calmly later. If high readings persist, discuss them with your doctor.",
            "priority": 9,
            "explanation": (
                "One high reading does not necessarily mean a problem, but it is worth rechecking calmly "
                "and watching whether this becomes a pattern."
            ),
            "evidence": [
                f"Systolic: {systolic['value']:.0f} mmHg",
                f"Diastolic: {diastolic['value']:.0f} mmHg",
            ],
        })

    elif systolic["value"] < 130 and diastolic["value"] < 80:
        insights.append({
            "level": "info",
            "category": "Cardiovascular",
            "icon": "❤️",
            "title": "Blood pressure",
            "text": "Your latest blood pressure is in a good range.",
            "action": "No action needed. Keep tracking the trend.",
            "priority": 6,
            "explanation": (
                f"Your latest reading is {systolic['value']:.0f}/{diastolic['value']:.0f} mmHg."
            ),
            "evidence": [
                f"Systolic: {systolic['value']:.0f} mmHg",
                f"Diastolic: {diastolic['value']:.0f} mmHg",
            ],
        })

    return insights


def _lumen_insights(snapshot):
    insights = []
    today_checkin = _today_checkin(snapshot)

    if not today_checkin:
        return insights

    lumen_score = today_checkin.get("lumen_score")

    if lumen_score is None:
        return insights

    if lumen_score <= 3:
        insights.append({
            "level": "win",
            "category": "Metabolism",
            "icon": "🔥",
            "title": "Fat-burning state",
            "text": "Today’s Lumen score suggests you are leaning toward fat burning.",
            "action": "Good signal for a steady nutrition day. Avoid unnecessary over-fuelling unless training demands it.",
            "priority": 7,
            "explanation": (
                f"Today’s saved Lumen score is {lumen_score}. "
                "Scores around 1–3 usually suggest stronger fat metabolism."
            ),
            "evidence": [
                f"Today’s Lumen score: {lumen_score}",
            ],
        })

    elif lumen_score >= 4:
        insights.append({
            "level": "info",
            "category": "Metabolism",
            "icon": "🍞",
            "title": "Carb-burning state",
            "text": "Today’s Lumen score suggests you are leaning more toward carb burning.",
            "action": "Treat this as context, not failure. Consider yesterday's food, sleep, stress, and training.",
            "priority": 6,
            "explanation": (
                "This may reflect recent food intake, training stress, poor sleep, recovery needs, "
                "or simply a normal day-to-day fluctuation."
            ),
            "evidence": [
                f"Today’s Lumen score: {lumen_score}",
            ],
        })

    return insights


def _recovery_insights(snapshot):
    insights = []
    today_checkin = _today_checkin(snapshot)

    if not today_checkin:
        return insights

    energy = today_checkin.get("energy")
    soreness = today_checkin.get("soreness")

    if energy is None or soreness is None:
        return insights

    if energy >= 7 and soreness <= 3:
        insights.append({
            "level": "win",
            "category": "Recovery",
            "icon": "🟢",
            "title": "Recovery looks good",
            "text": "Your subjective recovery looks positive today.",
            "action": "A gentle endurance ride or light strength work should be reasonable if nothing else feels off.",
            "priority": 8,
            "explanation": (
                f"Today’s energy score is {energy}/10 and soreness is {soreness}/10."
            ),
            "evidence": [
                f"Today’s energy: {energy}/10",
                f"Today’s soreness: {soreness}/10",
            ],
        })

    elif energy <= 4 or soreness >= 7:
        insights.append({
            "level": "warning",
            "category": "Recovery",
            "icon": "🟠",
            "title": "Recovery caution",
            "text": "Your subjective recovery looks a little strained today.",
            "action": "Keep today easy: walking, mobility, recovery, or very light Zone 1/2 only.",
            "priority": 9,
            "explanation": (
                "Low energy or high soreness suggests today may be better suited to recovery, walking, "
                "mobility, or very easy endurance rather than hard training."
            ),
            "evidence": [
                f"Today’s energy: {energy}/10",
                f"Today’s soreness: {soreness}/10",
            ],
        })

    return insights


def _missing_checkin_insights(snapshot):
    insights = []

    if snapshot.get("today_checkin_done"):
        return insights

    insights.append({
        "level": "warning",
        "category": "Snapshot",
        "icon": "🌅",
        "title": "Today’s check-in missing",
        "text": "Phoenix needs today’s morning check-in to give reliable daily guidance.",
        "action": "Complete the morning check-in when you have a moment.",
        "priority": 10,
        "explanation": (
            "The check-in provides context that automatic devices cannot measure, such as today’s energy, mood, "
            "soreness, and Lumen score."
        ),
        "evidence": [
            "No saved morning check-in found for today.",
        ],
    })

    return insights