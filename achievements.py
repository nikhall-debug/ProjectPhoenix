from database import load_health_measurements


def generate_achievements(snapshot):
    achievements = []

    achievements.extend(_weight_achievements(snapshot))
    achievements.extend(_body_composition_achievements(snapshot))
    achievements.extend(_metabolism_achievements(snapshot))

    achievements = sorted(achievements, key=lambda item: item["priority"], reverse=True)
    return achievements[:3]


def _weight_achievements(snapshot):
    achievements = []
    weight = snapshot.get("weight")

    if not weight:
        return achievements

    df = load_health_measurements()

    if df.empty:
        return achievements

    weight_df = df[
        (df["source"] == "withings") &
        (df["metric_type"] == "weight_kg")
    ].copy()

    if len(weight_df) < 2:
        return achievements

    weight_df = weight_df.sort_values("measured_at", ascending=False)

    current_weight = weight["current"]
    previous_low = weight_df.iloc[1:]["value"].min()

    if current_weight < previous_low:
        achievements.append({
            "icon": "🏅",
            "title": "New lowest weight recorded",
            "text": "This is your lowest Withings weight stored in Phoenix.",
            "priority": 10,
            "explanation": (
                "Phoenix compared your latest stored weight with all earlier stored Withings weight readings."
            ),
            "evidence": [
                f"Current weight: {current_weight:.1f} kg",
                f"Previous stored low: {previous_low:.1f} kg",
            ],
        })

    if weight.get("delta_30d") is not None and weight["delta_30d"] <= -2.0:
        achievements.append({
            "icon": "🎯",
            "title": "Strong 30-day weight progress",
            "text": "Your weight is meaningfully lower than around 30 days ago.",
            "priority": 8,
            "explanation": (
                "Phoenix flags this because a 30-day drop of 2 kg or more is meaningful progress."
            ),
            "evidence": [
                f"30-day weight change: {weight['delta_30d']:.1f} kg",
            ],
        })

    return achievements


def _body_composition_achievements(snapshot):
    achievements = []

    weight = snapshot.get("weight")
    muscle = snapshot.get("muscle")

    if not weight or not muscle:
        return achievements

    if weight.get("delta_30d") is None or muscle.get("delta_30d") is None:
        return achievements

    if weight["delta_30d"] <= -1.0 and muscle["delta_30d"] > -0.3:
        achievements.append({
            "icon": "💪",
            "title": "Muscle protected during weight loss",
            "text": "You appear to be losing weight while keeping muscle mass stable.",
            "priority": 9,
            "explanation": (
                "Phoenix looks for weight moving down while muscle mass stays roughly stable."
            ),
            "evidence": [
                f"30-day weight change: {weight['delta_30d']:.1f} kg",
                f"30-day muscle change: {muscle['delta_30d']:.1f} kg",
            ],
        })

    return achievements


def _metabolism_achievements(snapshot):
    achievements = []

    today_checkin = snapshot.get("today_checkin")

    if not today_checkin:
        return achievements

    lumen_score = today_checkin.get("lumen_score")

    if lumen_score is not None and lumen_score <= 2:
        achievements.append({
            "icon": "🔥",
            "title": "Strong fat-burning signal",
            "text": "Today’s Lumen score suggests a strong fat-burning state.",
            "priority": 6,
            "explanation": (
                "Phoenix treats Lumen scores of 1–2 as especially strong fat-burning signals."
            ),
            "evidence": [
                f"Today’s Lumen score: {lumen_score}",
            ],
        })

    return achievements