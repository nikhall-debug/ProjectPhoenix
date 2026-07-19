from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set


@dataclass
class WorkoutIntelligence:
    status: str
    training_type: str
    primary_session: str
    primary_focus: str
    load: str
    quality: str
    fatigue_generated: str
    fitness_effect: str
    goal_progress: str
    confidence: float
    summary: str
    signals: List[str]
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------

def build_workout_intelligence(
    workouts: Optional[List[Dict[str, Any]]] = None,
    health_intelligence: Optional[Dict[str, Any]] = None,
    athlete_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Interpret all workout records belonging to one training day.

    Workout Intelligence does not fetch data. It receives normalized
    workout records from the application layer and interprets the
    combined meaning of the day.

    Expected workout fields may include:
        name
        session_type
        source
        duration_minutes
        xss
        distance_km
        intensity_factor
        difficulty
    """

    workouts = workouts or []

    if not workouts:
        return WorkoutIntelligence(
            status="no_workout_data",
            training_type="No training",
            primary_session="None",
            primary_focus="Recovery decision",
            load="None",
            quality="Not applicable",
            fatigue_generated="None",
            fitness_effect="Neutral",
            goal_progress="Unknown",
            confidence=0.70,
            summary="No training sessions are available for this day.",
            signals=[
                "No recorded sessions are available for interpretation."
            ],
            recommendations=[
                "Use health, recovery and readiness signals to decide whether to train."
            ],
        ).to_dict()

    total_minutes = sum(
        _safe_float(workout.get("duration_minutes"))
        for workout in workouts
    )

    total_xss = sum(
        _safe_float(workout.get("xss"))
        for workout in workouts
    )

    total_distance = sum(
        _safe_float(workout.get("distance_km"))
        for workout in workouts
    )

    workout_count = len(workouts)

    intensity_values = [
        _safe_float(workout.get("intensity_factor"))
        for workout in workouts
        if workout.get("intensity_factor") is not None
    ]

    max_intensity = max(intensity_values, default=0.0)
    avg_intensity = _average(intensity_values)

    profile = _build_day_profile(workouts)

    training_type = _classify_training_day(
        workouts=workouts,
        profile=profile,
        total_minutes=total_minutes,
        total_xss=total_xss,
        max_intensity=max_intensity,
        avg_intensity=avg_intensity,
    )

    primary_session = _identify_primary_session(
        workouts=workouts,
        profile=profile,
        max_intensity=max_intensity,
    )

    primary_focus = _identify_primary_focus(
        training_type=training_type,
        primary_session=primary_session,
    )

    load = _classify_load(
        total_xss=total_xss,
        total_minutes=total_minutes,
        workout_count=workout_count,
        profile=profile,
    )

    fatigue = _classify_fatigue(
        load=load,
        max_intensity=max_intensity,
        total_minutes=total_minutes,
        training_type=training_type,
        profile=profile,
    )

    quality = _classify_quality(
        training_type=training_type,
        load=load,
        fatigue=fatigue,
        health_intelligence=health_intelligence,
    )

    fitness_effect = _classify_fitness_effect(
        training_type=training_type,
        load=load,
        fatigue=fatigue,
    )

    goal_progress = _classify_goal_progress(
        load=load,
        fitness_effect=fitness_effect,
        health_intelligence=health_intelligence,
    )

    signals = _build_signals(
        workout_count=workout_count,
        total_minutes=total_minutes,
        total_xss=total_xss,
        total_distance=total_distance,
        max_intensity=max_intensity,
        avg_intensity=avg_intensity,
        training_type=training_type,
        load=load,
        fatigue=fatigue,
        workouts=workouts,
        profile=profile,
    )

    recommendations = _build_recommendations(
        load=load,
        fatigue=fatigue,
        training_type=training_type,
        health_intelligence=health_intelligence,
        profile=profile,
    )

    summary = _build_summary(
        workout_count=workout_count,
        training_type=training_type,
        load=load,
        fatigue=fatigue,
        fitness_effect=fitness_effect,
    )

    return WorkoutIntelligence(
        status="ok",
        training_type=training_type,
        primary_session=primary_session,
        primary_focus=primary_focus,
        load=load,
        quality=quality,
        fatigue_generated=fatigue,
        fitness_effect=fitness_effect,
        goal_progress=goal_progress,
        confidence=_confidence(workouts),
        summary=summary,
        signals=signals,
        recommendations=recommendations,
    ).to_dict()


# ---------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def _average(
    values: List[float],
) -> Optional[float]:
    if not values:
        return None

    return sum(values) / len(values)


def _normalized_values(
    workouts: List[Dict[str, Any]],
    field_name: str,
) -> List[str]:
    values = []

    for workout in workouts:
        value = workout.get(field_name)

        if value is None:
            continue

        normalized = str(value).strip().lower()

        if normalized:
            values.append(normalized)

    return values


def _contains_any(
    values: Set[str],
    candidates: Set[str],
) -> bool:
    return bool(values.intersection(candidates))


# ---------------------------------------------------------------------
# Training-day profile
# ---------------------------------------------------------------------

def _build_day_profile(
    workouts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    session_types = set(
        _normalized_values(workouts, "session_type")
    )

    sources = set(
        _normalized_values(workouts, "source")
    )

    difficulties = set(
        _normalized_values(workouts, "difficulty")
    )

    names = " ".join(
        _normalized_values(workouts, "name")
    )

    strength_types = {
        "strength",
        "strength training",
        "weight training",
        "traditional strength training",
        "functional strength training",
    }

    cycling_types = {
        "cycling",
        "indoor cycling",
        "outdoor cycling",
    }

    movement_types = {
        "walking",
        "hiking",
        "mobility",
        "yoga",
        "other",
    }

    running_types = {
        "running",
        "indoor running",
        "outdoor running",
    }

    easy_difficulties = {
        "easy",
        "very easy",
        "recovery",
    }

    has_strength = (
        _contains_any(session_types, strength_types)
        or "hevy" in sources
        or any(
            word in names
            for word in [
                "strength",
                "weights",
                "weight training",
                "gym",
            ]
        )
    )

    has_cycling = _contains_any(
        session_types,
        cycling_types,
    )

    has_running = _contains_any(
        session_types,
        running_types,
    )

    has_movement = _contains_any(
        session_types,
        movement_types,
    )

    has_easy_difficulty = _contains_any(
        difficulties,
        easy_difficulties,
    )

    cycling_count = sum(
        1
        for workout in workouts
        if str(
            workout.get("session_type", "")
        ).strip().lower() in cycling_types
    )

    strength_count = sum(
        1
        for workout in workouts
        if (
            str(
                workout.get("session_type", "")
            ).strip().lower() in strength_types
            or str(
                workout.get("source", "")
            ).strip().lower() == "hevy"
        )
    )

    movement_count = sum(
        1
        for workout in workouts
        if str(
            workout.get("session_type", "")
        ).strip().lower() in movement_types
    )

    running_count = sum(
        1
        for workout in workouts
        if str(
            workout.get("session_type", "")
        ).strip().lower() in running_types
    )

    cycling_minutes = sum(
        _safe_float(workout.get("duration_minutes"))
        for workout in workouts
        if str(
            workout.get("session_type", "")
        ).strip().lower() in cycling_types
    )

    strength_minutes = sum(
        _safe_float(workout.get("duration_minutes"))
        for workout in workouts
        if (
            str(
                workout.get("session_type", "")
            ).strip().lower() in strength_types
            or str(
                workout.get("source", "")
            ).strip().lower() == "hevy"
        )
    )

    movement_minutes = sum(
        _safe_float(workout.get("duration_minutes"))
        for workout in workouts
        if str(
            workout.get("session_type", "")
        ).strip().lower() in movement_types
    )

    running_minutes = sum(
        _safe_float(workout.get("duration_minutes"))
        for workout in workouts
        if str(
            workout.get("session_type", "")
        ).strip().lower() in running_types
    )

    category_count = sum(
        [
            has_strength,
            has_cycling,
            has_running,
            has_movement,
        ]
    )

    return {
        "session_types": session_types,
        "sources": sources,
        "difficulties": difficulties,
        "has_strength": has_strength,
        "has_cycling": has_cycling,
        "has_running": has_running,
        "has_movement": has_movement,
        "has_easy_difficulty": has_easy_difficulty,
        "cycling_count": cycling_count,
        "strength_count": strength_count,
        "movement_count": movement_count,
        "running_count": running_count,
        "cycling_minutes": cycling_minutes,
        "strength_minutes": strength_minutes,
        "movement_minutes": movement_minutes,
        "running_minutes": running_minutes,
        "category_count": category_count,
    }


# ---------------------------------------------------------------------
# Training-day classification
# ---------------------------------------------------------------------

def _classify_training_day(
    workouts: List[Dict[str, Any]],
    profile: Dict[str, Any],
    total_minutes: float,
    total_xss: float,
    max_intensity: float,
    avg_intensity: Optional[float],
) -> str:
    if total_minutes <= 0:
        return "No training"

    has_strength = profile["has_strength"]
    has_cycling = profile["has_cycling"]
    has_running = profile["has_running"]
    has_movement = profile["has_movement"]
    category_count = profile["category_count"]

    if max_intensity >= 0.95:
        return "High-intensity training day"

    if max_intensity >= 0.88:
        return "Threshold training day"

    if total_xss >= 100:
        return "High-load endurance day"

    if has_strength and (
        has_cycling
        or has_running
    ):
        return "Mixed strength and endurance day"

    if has_strength and has_movement:
        return "Strength and movement day"

    if has_strength:
        return "Strength training day"

    if has_running and has_cycling:
        return "Mixed endurance day"

    if has_running:
        if total_minutes >= 45:
            return "Aerobic endurance day"

        return "Running day"

    cycling_is_easy = _cycling_appears_easy(
        workouts=workouts,
        profile=profile,
        total_xss=total_xss,
        avg_intensity=avg_intensity,
        max_intensity=max_intensity,
    )

    if has_cycling and has_movement and cycling_is_easy:
        if total_minutes >= 120:
            return "High-volume easy day"

        return "Recovery day"

    if has_cycling and has_movement:
        return "Cycling and movement day"

    if has_cycling:
        if cycling_is_easy:
            return "Recovery ride day"

        if total_minutes >= 45:
            return "Aerobic endurance day"

        return "Cycling day"

    if has_movement:
        if total_minutes >= 120:
            return "High-volume movement day"

        if total_minutes >= 90:
            return "Extended movement day"

        return "Light movement day"

    if category_count > 1:
        return "Mixed training day"

    return "General training day"


def _cycling_appears_easy(
    workouts: List[Dict[str, Any]],
    profile: Dict[str, Any],
    total_xss: float,
    avg_intensity: Optional[float],
    max_intensity: float,
) -> bool:
    if not profile["has_cycling"]:
        return False

    cycling_records = [
        workout
        for workout in workouts
        if str(
            workout.get("session_type", "")
        ).strip().lower()
        in {
            "cycling",
            "indoor cycling",
            "outdoor cycling",
        }
    ]

    cycling_xss = sum(
        _safe_float(workout.get("xss"))
        for workout in cycling_records
    )

    cycling_minutes = sum(
        _safe_float(workout.get("duration_minutes"))
        for workout in cycling_records
    )

    easy_difficulty = profile["has_easy_difficulty"]

    if max_intensity >= 0.88:
        return False

    if avg_intensity is not None:
        return (
            avg_intensity < 0.70
            and cycling_xss < 40
        )

    if easy_difficulty:
        return cycling_xss < 40

    if (
        cycling_xss > 0
        and cycling_xss < 25
        and cycling_minutes <= 60
    ):
        return True

    return False


# ---------------------------------------------------------------------
# Primary session and focus
# ---------------------------------------------------------------------

def _identify_primary_session(
    workouts: List[Dict[str, Any]],
    profile: Dict[str, Any],
    max_intensity: float,
) -> str:
    if not workouts:
        return "None"

    if max_intensity >= 0.95:
        return "High-intensity session"

    if max_intensity >= 0.88:
        return "Threshold session"

    if profile["has_strength"] and not (
        profile["has_cycling"]
        or profile["has_running"]
    ):
        return "Strength session"

    if profile["has_cycling"]:
        cycling_records = [
            workout
            for workout in workouts
            if str(
                workout.get("session_type", "")
            ).strip().lower()
            in {
                "cycling",
                "indoor cycling",
                "outdoor cycling",
            }
        ]

        cycling_xss = sum(
            _safe_float(workout.get("xss"))
            for workout in cycling_records
        )

        cycling_minutes = sum(
            _safe_float(workout.get("duration_minutes"))
            for workout in cycling_records
        )

        cycling_difficulties = {
            str(
                workout.get("difficulty", "")
            ).strip().lower()
            for workout in cycling_records
            if workout.get("difficulty")
        }

        easy_difficulties = {
            "easy",
            "very easy",
            "recovery",
        }

        if (
            cycling_xss < 25
            and cycling_minutes <= 60
            and (
                cycling_difficulties.intersection(
                    easy_difficulties
                )
                or not cycling_difficulties
            )
        ):
            return "Recovery ride"

        if cycling_minutes >= 45:
            return "Endurance ride"

        return "Cycling session"

    if profile["has_running"]:
        if profile["running_minutes"] >= 45:
            return "Endurance run"

        return "Running session"

    if profile["has_strength"]:
        return "Strength session"

    if profile["has_movement"]:
        if profile["movement_minutes"] >= 90:
            return "Extended movement"

        return "Recovery walk"

    return "General activity"


def _identify_primary_focus(
    training_type: str,
    primary_session: str,
) -> str:
    if training_type in {
        "Light movement day",
        "Recovery ride day",
        "Recovery day",
    }:
        return "Recovery"

    if training_type in {
        "Aerobic endurance day",
        "Cycling and movement day",
        "Mixed endurance day",
        "High-load endurance day",
    }:
        return "Aerobic development"

    if training_type in {
        "Strength training day",
        "Strength and movement day",
    }:
        return "Strength"

    if training_type == "Mixed strength and endurance day":
        return "Combined development"

    if training_type == "Threshold training day":
        return "Threshold development"

    if training_type == "High-intensity training day":
        return "High-intensity development"

    if training_type in {
        "Extended movement day",
        "High-volume movement day",
        "High-volume easy day",
    }:
        return "Low-intensity endurance"

    if primary_session == "Recovery walk":
        return "Recovery"

    return "General fitness"


# ---------------------------------------------------------------------
# Load and fatigue
# ---------------------------------------------------------------------

def _classify_load(
    total_xss: float,
    total_minutes: float,
    workout_count: int,
    profile: Dict[str, Any],
) -> str:
    if total_minutes <= 0:
        return "None"

    if total_xss > 0:
        if total_xss < 25:
            if total_minutes >= 120:
                return "Moderate"

            return "Low"

        if total_xss < 70:
            return "Moderate"

        if total_xss < 120:
            return "High"

        return "Very high"

    if profile["has_strength"]:
        if total_minutes < 30:
            return "Low"

        if total_minutes < 75:
            return "Moderate"

        return "High"

    if total_minutes < 45:
        return "Low"

    if total_minutes < 90:
        return "Moderate"

    if total_minutes < 150:
        return "High"

    return "Very high"


def _classify_fatigue(
    load: str,
    max_intensity: float,
    total_minutes: float,
    training_type: str,
    profile: Dict[str, Any],
) -> str:
    if load == "None":
        return "None"

    if training_type in {
        "Light movement day",
        "Recovery ride day",
        "Recovery day",
    }:
        if total_minutes >= 120:
            return "Moderate"

        return "Low"

    if training_type == "High-volume easy day":
        return "Moderate"

    if max_intensity >= 0.95:
        return "High"

    if load == "Low":
        return "Low"

    if load == "Moderate":
        return "Moderate"

    if load in {
        "High",
        "Very high",
    }:
        return "High"

    if total_minutes >= 120:
        return "High"

    return "Moderate"


# ---------------------------------------------------------------------
# Interpretation
# ---------------------------------------------------------------------

def _classify_quality(
    training_type: str,
    load: str,
    fatigue: str,
    health_intelligence: Optional[Dict[str, Any]],
) -> str:
    health_status = _health_status(
        health_intelligence
    )

    if (
        health_status == "needs_caution"
        and fatigue == "High"
    ):
        return "Risky"

    if training_type == "No training":
        return "Not applicable"

    if training_type in {
        "Light movement day",
        "Recovery ride day",
        "Recovery day",
    }:
        return "Useful recovery"

    if training_type in {
        "Extended movement day",
        "High-volume movement day",
        "High-volume easy day",
    }:
        return "Useful but potentially tiring"

    if load in {
        "Low",
        "Moderate",
    } and fatigue in {
        "Low",
        "Moderate",
    }:
        return "Controlled"

    if load == "High" and fatigue == "High":
        return "Productive but demanding"

    if load == "Very high":
        return "Very demanding"

    return "Useful"


def _classify_fitness_effect(
    training_type: str,
    load: str,
    fatigue: str,
) -> str:
    if training_type == "No training":
        return "Neutral"

    if training_type in {
        "Light movement day",
        "Recovery ride day",
        "Recovery day",
    }:
        return "Recovery support"

    if training_type in {
        "Extended movement day",
        "High-volume movement day",
        "High-volume easy day",
    }:
        return "Low-intensity endurance"

    if training_type in {
        "Strength training day",
        "Strength and movement day",
    }:
        return "Strength / durability"

    if training_type == "Mixed strength and endurance day":
        return "Combined strength and endurance"

    if training_type in {
        "Aerobic endurance day",
        "Cycling and movement day",
        "Mixed endurance day",
    }:
        return "Aerobic base"

    if training_type == "High-load endurance day":
        return "Endurance fitness building"

    if training_type == "Threshold training day":
        return "Threshold development"

    if training_type == "High-intensity training day":
        return "High-end fitness stimulus"

    if load in {
        "High",
        "Very high",
    }:
        return "Fitness building"

    return "Maintenance / consistency"


def _classify_goal_progress(
    load: str,
    fitness_effect: str,
    health_intelligence: Optional[Dict[str, Any]],
) -> str:
    health_status = _health_status(
        health_intelligence
    )

    if (
        health_status == "needs_caution"
        and load in {
            "High",
            "Very high",
        }
    ):
        return "Positive stimulus, but recovery risk"

    positive_effects = {
        "Aerobic base",
        "Endurance fitness building",
        "Threshold development",
        "High-end fitness stimulus",
        "Strength / durability",
        "Combined strength and endurance",
    }

    if fitness_effect in positive_effects:
        return "Positive"

    if fitness_effect == "Recovery support":
        return "Supports consistency"

    if fitness_effect == "Low-intensity endurance":
        return "Supports general fitness"

    return "Maintenance"


# ---------------------------------------------------------------------
# Signals and recommendations
# ---------------------------------------------------------------------

def _build_signals(
    workout_count: int,
    total_minutes: float,
    total_xss: float,
    total_distance: float,
    max_intensity: float,
    avg_intensity: Optional[float],
    training_type: str,
    load: str,
    fatigue: str,
    workouts: List[Dict[str, Any]],
    profile: Dict[str, Any],
) -> List[str]:
    signals = []

    if workout_count == 1:
        signals.append(
            "One training session was recorded."
        )
    else:
        signals.append(
            f"{workout_count} training sessions were combined "
            "into the daily interpretation."
        )

    signals.append(
        f"{total_minutes:.0f} minutes of total recorded activity."
    )

    if total_xss > 0:
        signals.append(
            f"Combined cycling load was {total_xss:.0f} XSS."
        )

    if total_distance > 0:
        signals.append(
            f"Combined distance was {total_distance:.1f} km."
        )

    if profile["cycling_count"] > 0:
        signals.append(
            f"{profile['cycling_count']} cycling session(s) contributed to the day."
        )

    if profile["strength_count"] > 0:
        signals.append(
            f"{profile['strength_count']} strength session(s) contributed to the day."
        )

    if profile["movement_count"] > 0:
        signals.append(
            f"{profile['movement_count']} movement session(s) contributed to the day."
        )

    if profile["running_count"] > 0:
        signals.append(
            f"{profile['running_count']} running session(s) contributed to the day."
        )

    if max_intensity > 0:
        signals.append(
            f"The highest recorded intensity factor was {max_intensity:.2f}."
        )

    if avg_intensity is not None:
        signals.append(
            f"The average recorded intensity factor was {avg_intensity:.2f}."
        )

    difficulties = set(
        _normalized_values(
            workouts,
            "difficulty",
        )
    )

    if difficulties:
        difficulty_text = ", ".join(
            sorted(difficulties)
        )

        signals.append(
            f"Recorded workout difficulty was {difficulty_text}."
        )

    session_types = set(
        _normalized_values(
            workouts,
            "session_type",
        )
    )

    if session_types:
        session_type_text = ", ".join(
            sorted(session_types)
        )

        signals.append(
            f"Recorded activity types were {session_type_text}."
        )

    signals.append(
        f"The day's primary pattern was {training_type.lower()}."
    )

    signals.append(
        f"Overall training load was {load.lower()}."
    )

    signals.append(
        f"Expected fatigue was {fatigue.lower()}."
    )

    return signals


def _build_recommendations(
    load: str,
    fatigue: str,
    training_type: str,
    health_intelligence: Optional[Dict[str, Any]],
    profile: Dict[str, Any],
) -> List[str]:
    recommendations = []

    health_status = _health_status(
        health_intelligence
    )

    health_readiness = _health_readiness(
        health_intelligence
    )

    if fatigue == "High":
        recommendations.append(
            "Avoid stacking another hard session until recovery "
            "and readiness clearly support it."
        )

    elif load in {
        "Low",
        "Moderate",
    }:
        recommendations.append(
            "The combined training load should be manageable if "
            "health and recovery signals remain stable."
        )

    elif load == "None":
        recommendations.append(
            "No training load was detected. Use health, recovery "
            "and readiness to decide whether to train."
        )

    if training_type == "Recovery day":
        recommendations.append(
            "The combination of easy cycling and light movement "
            "supports recovery without creating substantial fatigue."
        )

    elif training_type == "Recovery ride day":
        recommendations.append(
            "The ride appears to have achieved a recovery objective "
            "without creating substantial additional fatigue."
        )

    elif training_type == "Light movement day":
        recommendations.append(
            "Treat this as useful recovery context rather than a "
            "major training stimulus."
        )

    elif training_type == "High-volume easy day":
        recommendations.append(
            "Although the intensity was easy, the total duration may "
            "still affect freshness. Judge tomorrow by recovery."
        )

    elif training_type in {
        "Extended movement day",
        "High-volume movement day",
    }:
        recommendations.append(
            "Allow for the duration of the movement when judging leg "
            "freshness and overall recovery."
        )

    elif training_type == "Mixed strength and endurance day":
        recommendations.append(
            "Account for both muscular and aerobic recovery before "
            "planning the next demanding session."
        )

    elif training_type in {
        "Aerobic endurance day",
        "High-load endurance day",
        "Mixed endurance day",
    }:
        recommendations.append(
            "This supports the aerobic base and long-term endurance "
            "development."
        )

    elif training_type in {
        "Strength training day",
        "Strength and movement day",
    }:
        recommendations.append(
            "Strength work supports durability, body composition and "
            "long-term athleticism."
        )

    if health_status == "needs_caution":
        recommendations.append(
            "Health signals suggest caution, so avoid increasing the "
            "training stress beyond what is already recorded."
        )

    if (
        health_readiness == "high"
        and load == "None"
    ):
        recommendations.append(
            "Health readiness looks supportive and no workout load is "
            "detected, so this may be a good day to train."
        )

    if not recommendations:
        recommendations.append(
            "Use this training-day interpretation alongside health "
            "and readiness before deciding on the next session."
        )

    return recommendations


def _build_summary(
    workout_count: int,
    training_type: str,
    load: str,
    fatigue: str,
    fitness_effect: str,
) -> str:
    if training_type == "No training":
        return (
            "No training sessions are available, so Phoenix cannot "
            "yet assess the day's training stress."
        )

    if training_type == "Light movement day":
        return (
            "Today is an active recovery day. Light movement maintained "
            "activity while creating very little fatigue, supporting "
            "recovery without compromising future training."
        )

    if training_type == "Recovery ride day":
        return (
            "Today is a cycling recovery day. The ride provided gentle "
            "aerobic movement while keeping training stress and fatigue low."
        )

    if training_type == "Recovery day":
        return (
            "Today is a recovery-focused training day. Easy cycling and "
            "light movement supported recovery while keeping the overall "
            "training cost low."
        )

    if training_type == "Strength training day":
        return (
            "Today is a strength-focused training day. The main stimulus "
            "supports muscular durability and long-term athleticism."
        )

    if training_type == "Strength and movement day":
        return (
            "Today combined strength work with supportive movement. The "
            "main training stimulus was muscular, with light activity adding "
            "recovery and general movement context."
        )

    if training_type == "Mixed strength and endurance day":
        return (
            "Today combined strength and endurance work. The day provided "
            "a broad training stimulus but may require recovery across both "
            "muscular and aerobic systems."
        )

    if training_type == "Aerobic endurance day":
        return (
            "Today is an aerobic development day. The main training stimulus "
            "supports endurance and aerobic base fitness."
        )

    if training_type == "Threshold training day":
        return (
            "Today is a threshold-focused training day. The session provided "
            "a meaningful fitness stimulus with a noticeable recovery cost."
        )

    if training_type == "High-intensity training day":
        return (
            "Today is a high-intensity training day. The session delivered "
            "a strong fitness stimulus and should be followed by appropriate recovery."
        )

    session_word = (
        "session"
        if workout_count == 1
        else "sessions"
    )

    return (
        f"Today's {workout_count} {session_word} created a "
        f"{training_type.lower()}, with {load.lower()} overall load "
        f"and {fatigue.lower()} fatigue. The likely effect is "
        f"{fitness_effect.lower()}."
    )


# ---------------------------------------------------------------------
# Confidence and health helpers
# ---------------------------------------------------------------------

def _confidence(
    workouts: List[Dict[str, Any]],
) -> float:
    score = 60

    if workouts:
        score += 10

    has_duration = any(
        workout.get("duration_minutes") is not None
        for workout in workouts
    )

    has_xss = any(
        workout.get("xss") is not None
        for workout in workouts
    )

    has_intensity = any(
        workout.get("intensity_factor") is not None
        for workout in workouts
    )

    has_source = any(
        workout.get("source") is not None
        for workout in workouts
    )

    has_session_type = any(
        workout.get("session_type") is not None
        for workout in workouts
    )

    has_difficulty = any(
        workout.get("difficulty") is not None
        for workout in workouts
    )

    if has_duration:
        score += 10

    if has_xss:
        score += 8

    if has_intensity:
        score += 5

    if has_source:
        score += 3

    if has_session_type:
        score += 2

    if has_difficulty:
        score += 2

    return min(
        score / 100,
        0.95,
    )


def _health_status(
    health_intelligence: Optional[Dict[str, Any]],
) -> str:
    if not isinstance(
        health_intelligence,
        dict,
    ):
        return "unknown"

    return str(
        health_intelligence.get(
            "status",
            "unknown",
        )
    ).strip().lower()


def _health_readiness(
    health_intelligence: Optional[Dict[str, Any]],
) -> str:
    if not isinstance(
        health_intelligence,
        dict,
    ):
        return "unknown"

    return str(
        health_intelligence.get(
            "readiness",
            "unknown",
        )
    ).strip().lower()