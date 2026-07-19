from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------
# Structured result
# ---------------------------------------------------------------------

@dataclass
class ConfidenceResult:
    score: int
    label: str
    status: str
    summary: str

    available_signals: List[str]
    missing_signals: List[str]
    stale_signals: List[str]

    strengths: List[str]
    limitations: List[str]
    signal_details: List[Dict[str, Any]]

    available_count: int
    missing_count: int
    stale_count: int
    total_signals: int

    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------

def build_confidence_profile(
    context: Optional[Dict[str, Any]] = None,
    snapshot: Optional[Dict[str, Any]] = None,
    recovery_profile: Optional[Dict[str, Any]] = None,
    readiness_profile: Optional[Dict[str, Any]] = None,
    timeline_context: Optional[Dict[str, Any]] = None,
    workout_intelligence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a shared Phoenix confidence profile.

    Confidence reflects data completeness, freshness, and agreement.
    It does not represent medical certainty.
    """
    context = context if isinstance(context, dict) else {}
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    recovery_profile = (
        recovery_profile
        if isinstance(recovery_profile, dict)
        else {}
    )
    readiness_profile = (
        readiness_profile
        if isinstance(readiness_profile, dict)
        else {}
    )
    timeline_context = (
        timeline_context
        if isinstance(timeline_context, dict)
        else {}
    )
    workout_intelligence = (
        workout_intelligence
        if isinstance(workout_intelligence, dict)
        else {}
    )

    signal_details: List[Dict[str, Any]] = []

    signal_details.append(
        _build_signal(
            key="hrv",
            label="HRV",
            available=_has_value(
                context,
                [
                    "hrv",
                    "latest_hrv",
                    "apple_hrv_ms",
                ],
            ),
            stale=_is_context_signal_stale(
                context,
                [
                    "hrv_age_days",
                    "latest_hrv_age_days",
                ],
                stale_after_days=3,
            ),
            weight=12,
            strength_text="Recent HRV is available.",
            missing_text="HRV is unavailable.",
            stale_text="HRV may be out of date.",
        )
    )

    signal_details.append(
        _build_signal(
            key="resting_hr",
            label="Resting heart rate",
            available=_has_value(
                context,
                [
                    "resting_hr",
                    "latest_resting_hr",
                    "apple_resting_hr_bpm",
                ],
            ),
            stale=_is_context_signal_stale(
                context,
                [
                    "resting_hr_age_days",
                    "latest_resting_hr_age_days",
                ],
                stale_after_days=3,
            ),
            weight=10,
            strength_text="Recent resting heart rate is available.",
            missing_text="Resting heart rate is unavailable.",
            stale_text="Resting heart rate may be out of date.",
        )
    )

    signal_details.append(
        _build_signal(
            key="sleep",
            label="Sleep",
            available=_has_value(
                context,
                [
                    "sleep",
                    "sleep_hours",
                    "sleep_total",
                    "apple_sleep_total_hours",
                ],
            ),
            stale=_is_context_signal_stale(
                context,
                [
                    "sleep_age_days",
                    "latest_sleep_age_days",
                ],
                stale_after_days=3,
            ),
            weight=12,
            strength_text="Recent sleep data is available.",
            missing_text="Sleep data is unavailable.",
            stale_text="Sleep data may be out of date.",
        )
    )

    signal_details.append(
        _build_signal(
            key="blood_oxygen",
            label="Blood oxygen",
            available=_has_value(
                context,
                [
                    "blood_oxygen",
                    "spo2",
                    "apple_blood_oxygen_percent",
                ],
            ),
            stale=_is_context_signal_stale(
                context,
                [
                    "blood_oxygen_age_days",
                    "spo2_age_days",
                ],
                stale_after_days=5,
            ),
            weight=5,
            strength_text="Blood oxygen data is available.",
            missing_text="Blood oxygen data is unavailable.",
            stale_text="Blood oxygen data may be out of date.",
        )
    )

    signal_details.append(
        _build_signal(
            key="wrist_temperature",
            label="Wrist temperature",
            available=_has_value(
                context,
                [
                    "wrist_temperature",
                    "apple_sleeping_wrist_temperature_c",
                ],
            ),
            stale=_is_context_signal_stale(
                context,
                [
                    "wrist_temperature_age_days",
                ],
                stale_after_days=3,
            ),
            weight=7,
            strength_text="Wrist temperature is available.",
            missing_text="Wrist temperature is unavailable.",
            stale_text="Wrist temperature may be out of date.",
        )
    )

    signal_details.append(
        _build_signal(
            key="checkin",
            label="Morning check-in",
            available=bool(
                snapshot.get(
                    "today_checkin_done",
                    False,
                )
            ),
            stale=False,
            weight=10,
            strength_text="Today's subjective check-in is complete.",
            missing_text="Today's subjective check-in is missing.",
            stale_text="",
        )
    )

    signal_details.append(
        _build_signal(
            key="lumen",
            label="Lumen",
            available=bool(
                snapshot.get(
                    "lumen_entered",
                    False,
                )
            ),
            stale=False,
            weight=5,
            strength_text="Today's Lumen reading is available.",
            missing_text="Today's Lumen reading is missing.",
            stale_text="",
        )
    )

    signal_details.append(
        _build_signal(
            key="body_composition",
            label="Body composition",
            available=_has_any_value(
                context,
                [
                    "weight",
                    "body_fat",
                    "muscle",
                    "weight_kg",
                    "fat_percent",
                    "muscle_mass_kg",
                ],
            ),
            stale=_is_context_signal_stale(
                context,
                [
                    "withings_age_days",
                    "body_composition_age_days",
                ],
                stale_after_days=7,
            ),
            weight=6,
            strength_text="Body-composition context is available.",
            missing_text="Body-composition context is unavailable.",
            stale_text="Body-composition data may be out of date.",
        )
    )

    signal_details.append(
        _build_signal(
            key="recovery_profile",
            label="Recovery profile",
            available=bool(
                recovery_profile
            ),
            stale=False,
            weight=8,
            strength_text="Recovery analysis is available.",
            missing_text="Recovery analysis is unavailable.",
            stale_text="",
        )
    )

    signal_details.append(
        _build_signal(
            key="readiness_profile",
            label="Readiness profile",
            available=bool(
                readiness_profile
            ),
            stale=False,
            weight=8,
            strength_text="Readiness analysis is available.",
            missing_text="Readiness analysis is unavailable.",
            stale_text="",
        )
    )

    signal_details.append(
        _build_signal(
            key="timeline",
            label="Timeline context",
            available=_timeline_is_available(
                timeline_context
            ),
            stale=False,
            weight=7,
            strength_text="Timeline context is available.",
            missing_text="No Timeline context is currently available.",
            stale_text="",
        )
    )

    signal_details.append(
        _build_signal(
            key="workout_context",
            label="Workout context",
            available=bool(
                workout_intelligence
            ),
            stale=False,
            weight=10,
            strength_text="Recent workout context is available.",
            missing_text="Recent workout context is unavailable.",
            stale_text="",
        )
    )

    score = _calculate_score(
        signal_details
    )

    score = _apply_profile_quality_adjustments(
        score=score,
        recovery_profile=recovery_profile,
        readiness_profile=readiness_profile,
        timeline_context=timeline_context,
    )

    score = max(
        0,
        min(
            int(round(score)),
            95,
        ),
    )

    label, status = _classify_confidence(
        score
    )

    available_signals = [
        signal["label"]
        for signal in signal_details
        if signal["available"]
        and not signal["stale"]
    ]

    missing_signals = [
        signal["label"]
        for signal in signal_details
        if not signal["available"]
    ]

    stale_signals = [
        signal["label"]
        for signal in signal_details
        if signal["available"]
        and signal["stale"]
    ]

    strengths = [
        signal["strength_text"]
        for signal in signal_details
        if signal["available"]
        and not signal["stale"]
        and signal["strength_text"]
    ]

    limitations = []

    limitations.extend(
        signal["missing_text"]
        for signal in signal_details
        if not signal["available"]
        and signal["missing_text"]
    )

    limitations.extend(
        signal["stale_text"]
        for signal in signal_details
        if signal["available"]
        and signal["stale"]
        and signal["stale_text"]
    )

    summary = _build_summary(
        score=score,
        label=label,
        missing_signals=missing_signals,
        stale_signals=stale_signals,
    )

    result = ConfidenceResult(
        score=score,
        label=label,
        status=status,
        summary=summary,
        available_signals=available_signals,
        missing_signals=missing_signals,
        stale_signals=stale_signals,
        strengths=strengths,
        limitations=limitations,
        signal_details=signal_details,
        available_count=len(
            available_signals
        ),
        missing_count=len(
            missing_signals
        ),
        stale_count=len(
            stale_signals
        ),
        total_signals=len(
            signal_details
        ),
        generated_at=datetime.now().isoformat(
            timespec="seconds"
        ),
    )

    return result.to_dict()


# ---------------------------------------------------------------------
# Signal construction
# ---------------------------------------------------------------------

def _build_signal(
    key: str,
    label: str,
    available: bool,
    stale: bool,
    weight: int,
    strength_text: str,
    missing_text: str,
    stale_text: str,
) -> Dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "available": bool(
            available
        ),
        "stale": bool(
            stale
            if available
            else False
        ),
        "weight": int(
            weight
        ),
        "strength_text": strength_text,
        "missing_text": missing_text,
        "stale_text": stale_text,
    }


# ---------------------------------------------------------------------
# Score calculation
# ---------------------------------------------------------------------

def _calculate_score(
    signal_details: List[Dict[str, Any]],
) -> float:
    total_weight = sum(
        signal.get(
            "weight",
            0,
        )
        for signal in signal_details
    )

    if total_weight <= 0:
        return 0.0

    earned_weight = 0.0

    for signal in signal_details:
        weight = float(
            signal.get(
                "weight",
                0,
            )
        )

        if not signal.get(
            "available",
            False,
        ):
            continue

        if signal.get(
            "stale",
            False,
        ):
            earned_weight += (
                weight
                * 0.40
            )

        else:
            earned_weight += weight

    return (
        earned_weight
        / total_weight
        * 100
    )


def _apply_profile_quality_adjustments(
    score: float,
    recovery_profile: Dict[str, Any],
    readiness_profile: Dict[str, Any],
    timeline_context: Dict[str, Any],
) -> float:
    adjusted = float(
        score
    )

    recovery_confidence = _normalise_confidence_value(
        recovery_profile.get(
            "confidence"
        )
    )

    readiness_confidence = _normalise_confidence_value(
        readiness_profile.get(
            "confidence"
        )
    )

    if recovery_confidence is not None:
        if recovery_confidence >= 80:
            adjusted += 2
        elif recovery_confidence < 50:
            adjusted -= 3

    if readiness_confidence is not None:
        if readiness_confidence >= 80:
            adjusted += 2
        elif readiness_confidence < 50:
            adjusted -= 3

    if timeline_context.get(
        "has_recent_medical_event",
        False,
    ):
        if timeline_context.get(
            "recent_event_count",
            0,
        ) > 0:
            adjusted += 2

    return adjusted


# ---------------------------------------------------------------------
# Classification and summary
# ---------------------------------------------------------------------

def _classify_confidence(
    score: int,
) -> tuple[str, str]:
    if score >= 85:
        return (
            "Very high",
            "very_high",
        )

    if score >= 70:
        return (
            "Good",
            "good",
        )

    if score >= 55:
        return (
            "Moderate",
            "moderate",
        )

    if score >= 35:
        return (
            "Limited",
            "limited",
        )

    return (
        "Low",
        "low",
    )


def _build_summary(
    score: int,
    label: str,
    missing_signals: List[str],
    stale_signals: List[str],
) -> str:
    if score >= 85:
        base = (
            "Phoenix has a strong, current set of inputs for "
            "today's interpretation."
        )

    elif score >= 70:
        base = (
            "Phoenix has enough current data for a useful and "
            "well-supported interpretation."
        )

    elif score >= 55:
        base = (
            "Phoenix can provide a useful interpretation, but some "
            "important inputs are incomplete."
        )

    elif score >= 35:
        base = (
            "Phoenix has limited information, so today's interpretation "
            "should remain cautious."
        )

    else:
        base = (
            "Phoenix does not have enough reliable information for a "
            "strong recommendation today."
        )

    details = []

    if missing_signals:
        details.append(
            "Missing: "
            + ", ".join(
                missing_signals[:4]
            )
        )

    if stale_signals:
        details.append(
            "Possibly stale: "
            + ", ".join(
                stale_signals[:4]
            )
        )

    if details:
        return (
            f"{base} "
            + " · ".join(
                details
            )
            + "."
        )

    return base


# ---------------------------------------------------------------------
# Availability helpers
# ---------------------------------------------------------------------

def _has_value(
    data: Dict[str, Any],
    keys: List[str],
) -> bool:
    for key in keys:
        value = _find_nested_value(
            data,
            key,
        )

        if _value_is_present(
            value
        ):
            return True

    return False


def _has_any_value(
    data: Dict[str, Any],
    keys: List[str],
) -> bool:
    return _has_value(
        data,
        keys,
    )


def _find_nested_value(
    data: Any,
    target_key: str,
) -> Any:
    if isinstance(
        data,
        dict,
    ):
        if target_key in data:
            return data.get(
                target_key
            )

        for value in data.values():
            found = _find_nested_value(
                value,
                target_key,
            )

            if _value_is_present(
                found
            ):
                return found

    elif isinstance(
        data,
        list,
    ):
        for item in data:
            found = _find_nested_value(
                item,
                target_key,
            )

            if _value_is_present(
                found
            ):
                return found

    return None


def _value_is_present(
    value: Any,
) -> bool:
    if value is None:
        return False

    if isinstance(
        value,
        str,
    ):
        return bool(
            value.strip()
        )

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
            dict,
        ),
    ):
        return bool(
            value
        )

    return True


def _timeline_is_available(
    timeline_context: Dict[str, Any],
) -> bool:
    if not timeline_context:
        return False

    return bool(
        timeline_context.get(
            "active_event_count",
            0,
        )
        or timeline_context.get(
            "recent_event_count",
            0,
        )
        or timeline_context.get(
            "context_summary"
        )
    )


# ---------------------------------------------------------------------
# Freshness helpers
# ---------------------------------------------------------------------

def _is_context_signal_stale(
    context: Dict[str, Any],
    age_keys: List[str],
    stale_after_days: int,
) -> bool:
    for key in age_keys:
        age_value = _find_nested_value(
            context,
            key,
        )

        age_days = _safe_int(
            age_value
        )

        if age_days is not None:
            return (
                age_days
                > stale_after_days
            )

    return False


# ---------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------

def _normalise_confidence_value(
    value: Any,
) -> Optional[float]:
    numeric = _safe_float(
        value
    )

    if numeric is None:
        return None

    if numeric <= 1:
        numeric *= 100

    return max(
        0.0,
        min(
            numeric,
            100.0,
        ),
    )


def _safe_float(
    value: Any,
) -> Optional[float]:
    try:
        if value is None:
            return None

        return float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def _safe_int(
    value: Any,
) -> Optional[int]:
    try:
        if value is None:
            return None

        return int(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None