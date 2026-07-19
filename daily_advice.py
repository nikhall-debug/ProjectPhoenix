from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass
class DailyAdvice:
    status: str
    title: str
    decision: str
    summary: str
    execution: str
    weather_context: Optional[str]
    reasons: List[str]
    warnings: List[str]
    confidence: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _safe_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value

    if hasattr(value, "to_dict") and callable(value.to_dict):
        result = value.to_dict()
        return result if isinstance(result, dict) else {}

    if hasattr(value, "__dict__"):
        return dict(value.__dict__)

    return {}


def _clean_text(
    value: Any,
    fallback: str = "",
) -> str:
    if value is None:
        return fallback

    text = str(value).strip()
    return text or fallback


def _normalise_activity(value: Any) -> str:
    activity = _clean_text(value, "Not sure").lower()

    if activity == "cycling":
        return "Cycling"

    if activity == "strength":
        return "Strength"

    if activity == "walking":
        return "Walking"

    if activity == "rest":
        return "Rest"

    return "Not sure"


def _normalise_environment(value: Any) -> str:
    environment = _clean_text(value, "Indoor").lower()

    if environment == "outdoor":
        return "Outdoor"

    if environment in {
        "not sure",
        "unsure",
        "either",
    }:
        return "Not sure"

    return "Indoor"


def _looks_conservative(
    coach: Dict[str, Any],
) -> bool:
    combined_text = " ".join(
        [
            _clean_text(coach.get("title")),
            _clean_text(coach.get("decision")),
            _clean_text(coach.get("recommendation")),
        ]
    ).lower()

    caution_terms = {
        "rest",
        "avoid",
        "recovery",
        "recover",
        "very easy",
        "light movement",
        "no training",
        "do not train",
        "conservative",
        "caution",
    }

    return any(
        term in combined_text
        for term in caution_terms
    )


def _confidence_percent(
    coach: Dict[str, Any],
    weather: Dict[str, Any],
    weather_relevant: bool,
) -> int:
    coach_confidence = coach.get("confidence")

    try:
        coach_confidence = float(coach_confidence)

        if coach_confidence <= 1:
            coach_confidence *= 100

    except (TypeError, ValueError):
        coach_confidence = 75.0

    if not weather_relevant:
        return round(
            max(0, min(coach_confidence, 100))
        )

    weather_confidence = weather.get(
        "confidence",
        0,
    )

    try:
        weather_confidence = float(
            weather_confidence
        )
    except (TypeError, ValueError):
        weather_confidence = 0.0

    # Coach confidence remains dominant. Weather contributes only to
    # execution confidence, not physiological readiness.
    combined = (
        coach_confidence * 0.8
        + weather_confidence * 0.2
    )

    return round(
        max(0, min(combined, 100))
    )


def build_daily_advice(
    coach_recommendation: Any,
    weather_intelligence: Any,
    planned_activity: str = "Not sure",
    training_environment: str = "Indoor",
) -> Dict[str, Any]:
    """
    Compose one Phoenix answer from coaching and weather context.

    Weather may change the timing, environment and execution of a
    session. It must never override a conservative health or recovery
    recommendation.
    """

    coach = _safe_dict(
        coach_recommendation
    )

    weather = _safe_dict(
        weather_intelligence
    )

    activity = _normalise_activity(
        planned_activity
    )

    environment = _normalise_environment(
        training_environment
    )

    coach_title = _clean_text(
        coach.get("title"),
        "Today’s recommendation",
    )

    coach_decision = _clean_text(
        coach.get("decision"),
        "Review today’s signals",
    )

    coach_summary = _clean_text(
        coach.get("recommendation"),
        (
            "Phoenix does not yet have enough information "
            "for a detailed recommendation."
        ),
    )

    reasons = list(
        coach.get("reasons")
        or coach.get("signals")
        or []
    )

    warnings = list(
        coach.get("warnings")
        or []
    )

    weather_available = (
        weather.get("status") == "Available"
        and weather.get(
            "source_available",
            False,
        )
    )

    weather_relevant = bool(
        weather.get(
            "weather_relevant",
            False,
        )
    )

    conservative = _looks_conservative(
        coach
    )

    weather_context = None
    execution = ""

    if activity == "Rest":
        execution = (
            "Treat today as a recovery day. Weather does not need "
            "to influence the decision."
        )

    elif activity == "Strength":
        execution = (
            "Use the Coach recommendation to determine the appropriate "
            "strength volume and intensity."
        )

    elif activity == "Walking":
        if weather_available:
            weather_context = _clean_text(
                weather.get("summary")
            )

            execution = _clean_text(
                weather.get("recommendation"),
                (
                    "Use the forecast to choose a comfortable and "
                    "safe time for the walk."
                ),
            )
        else:
            execution = (
                "Use the Coach recommendation and check local "
                "conditions before walking."
            )

    elif activity == "Cycling":
        if conservative:
            if environment == "Outdoor":
                execution = (
                    "Keep the Coach’s conservative recommendation as "
                    "the limit. Weather may help with timing, but it "
                    "does not justify increasing the workload."
                )

            elif environment == "Indoor":
                execution = (
                    "Keep the session within the Coach’s conservative "
                    "limit. Use strong airflow and stop if symptoms or "
                    "fatigue increase."
                )

            else:
                execution = (
                    "Choose the environment that makes it easiest to "
                    "keep the session within the Coach’s conservative "
                    "limit."
                )

        elif weather_available:
            weather_context = _clean_text(
                weather.get("summary")
            )

            execution = _clean_text(
                weather.get("recommendation"),
                (
                    "Carry out the Coach recommendation in the selected "
                    "training environment."
                ),
            )

        elif environment == "Indoor":
            execution = (
                "Carry out the Coach recommendation indoors and use "
                "a fan from the beginning."
            )

        elif environment == "Outdoor":
            execution = (
                "Carry out the Coach recommendation outdoors only "
                "after checking current local conditions."
            )

        else:
            execution = (
                "Either environment may work. Choose the option that "
                "best supports the Coach recommendation."
            )

    else:
        execution = (
            "Use the Coach recommendation as the primary guide. "
            "Select an activity only after considering how you feel."
        )

    if weather_relevant and weather_available:
        for warning in weather.get(
            "warnings",
            [],
        ):
            if warning not in warnings:
                warnings.append(
                    warning
                )

        best_window = weather.get(
            "best_window"
        )

        if best_window:
            reasons.append(
                f"The best remaining outdoor window is "
                f"{best_window}."
            )

    confidence = _confidence_percent(
        coach=coach,
        weather=weather,
        weather_relevant=(
            weather_relevant
            and weather_available
        ),
    )

    return DailyAdvice(
        status="ok",
        title=coach_title,
        decision=coach_decision,
        summary=coach_summary,
        execution=execution,
        weather_context=weather_context,
        reasons=reasons,
        warnings=warnings,
        confidence=confidence,
    ).to_dict()