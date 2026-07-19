import json
from datetime import date
from typing import Any, Dict, Optional

import pandas as pd

from workout_database import load_training_sessions


# ---------------------------------------------------------------------
# Public builders
# ---------------------------------------------------------------------

def build_workout_intelligence(
    target_date=None,
    fallback_to_latest=True,
):
    """
    Build Workout Intelligence for one training day.

    The engine reports both:
        - factual load details;
        - physiological meaning for the Coach Engine.

    If the requested date has no sessions and fallback_to_latest is
    True, Phoenix uses the latest available training day.
    """

    requested_date = _normalise_date(
        target_date
    )

    sessions = load_training_sessions(
        limit=500
    )

    if sessions is None or sessions.empty:
        return _empty_intelligence(
            target_date=requested_date,
            status="no_data",
            narrative="No workout data recorded yet.",
        )

    sessions = _prepare_sessions(
        sessions
    )

    if sessions.empty:
        return _empty_intelligence(
            target_date=requested_date,
            status="no_data",
            narrative="No valid workout dates are available.",
        )

    day = sessions[
        sessions["session_date"]
        == requested_date
    ].copy()

    status = "target_day"

    if day.empty:
        if not fallback_to_latest:
            return _empty_intelligence(
                target_date=requested_date,
                status="no_training_on_target_day",
                narrative=(
                    "No workout sessions were recorded "
                    "for the requested day."
                ),
            )

        latest_date = sessions[
            "session_date"
        ].max()

        day = sessions[
            sessions["session_date"]
            == latest_date
        ].copy()

        analysis_date = latest_date
        status = "latest_available_day"

    else:
        analysis_date = requested_date

    return _build_day_intelligence(
        day=day,
        analysis_date=analysis_date,
        status=status,
    )


def build_latest_completed_workout_intelligence(
    reference_date=None,
):
    """
    Return Workout Intelligence for the latest completed training day.

    Sessions recorded today are deliberately excluded so an unfinished
    current day does not distort the morning coaching recommendation.
    """

    reference_date_text = _normalise_date(
        reference_date
    )

    sessions = load_training_sessions(
        limit=500
    )

    if sessions is None or sessions.empty:
        return _empty_intelligence(
            target_date=reference_date_text,
            status="no_previous_training",
            narrative=(
                "No completed training day is available "
                "before today."
            ),
        )

    sessions = _prepare_sessions(
        sessions
    )

    if sessions.empty:
        return _empty_intelligence(
            target_date=reference_date_text,
            status="no_previous_training",
            narrative=(
                "No valid completed training day is available."
            ),
        )

    completed_sessions = sessions[
        sessions["session_date"]
        < reference_date_text
    ].copy()

    if completed_sessions.empty:
        return _empty_intelligence(
            target_date=reference_date_text,
            status="no_previous_training",
            narrative=(
                "No completed training day is available "
                "before today."
            ),
        )

    latest_completed_date = completed_sessions[
        "session_date"
    ].max()

    latest_day = completed_sessions[
        completed_sessions["session_date"]
        == latest_completed_date
    ].copy()

    return _build_day_intelligence(
        day=latest_day,
        analysis_date=latest_completed_date,
        status="latest_completed_day",
    )


def build_workout_summary(
    target_date=None,
):
    """
    Compatibility wrapper used by the Workouts page.
    """

    intelligence = build_workout_intelligence(
        target_date=target_date,
        fallback_to_latest=True,
    )

    cycling = intelligence[
        "training_load"
    ][
        "cycling"
    ]

    strength = intelligence[
        "training_load"
    ][
        "strength"
    ]

    movement = intelligence[
        "training_load"
    ][
        "movement"
    ]

    return {
        "date": intelligence["date"],
        "has_training": intelligence[
            "has_training"
        ],
        "summary": intelligence[
            "summary"
        ],
        "cycling_count": cycling[
            "count"
        ],
        "cycling_minutes": cycling[
            "minutes"
        ],
        "cycling_xss": cycling[
            "xss"
        ],
        "strength_count": strength[
            "count"
        ],
        "strength_minutes": strength[
            "minutes"
        ],
        "movement_count": movement[
            "count"
        ],
        "movement_minutes": movement[
            "minutes"
        ],
        "interpretation": intelligence[
            "narrative"
        ],
    }


# ---------------------------------------------------------------------
# Main day builder
# ---------------------------------------------------------------------

def _build_day_intelligence(
    day: pd.DataFrame,
    analysis_date: str,
    status: str,
) -> Dict[str, Any]:
    cycling = day[
        day["session_type"]
        == "Cycling"
    ]

    strength = day[
        day["session_type"]
        == "Strength"
    ]

    movement = day[
        day["session_type"].isin(
            [
                "Walking",
                "Hiking",
                "Running",
                "Mobility",
                "Yoga",
                "Other",
            ]
        )
    ]

    cycling_minutes = _sum_minutes(
        cycling
    )

    strength_minutes = _sum_minutes(
        strength
    )

    movement_minutes = _sum_minutes(
        movement
    )

    cycling_xss = _sum_xert_xss(
        cycling
    )

    cycling_load = _classify_cycling_load(
        cycling_xss=cycling_xss,
        cycling_minutes=cycling_minutes,
        cycling_count=len(cycling),
    )

    strength_load = _classify_strength_load(
        strength_minutes=strength_minutes,
        strength_count=len(strength),
    )

    movement_context = _classify_movement_context(
        movement_minutes=movement_minutes,
        movement_count=len(movement),
        has_cycling=len(cycling) > 0,
        has_strength=len(strength) > 0,
    )

    overall_load = _classify_overall_load(
        cycling_load=cycling_load,
        strength_load=strength_load,
        cycling_count=len(cycling),
        strength_count=len(strength),
        movement_count=len(movement),
    )

    recovery_cost = _classify_recovery_cost(
        overall_load=overall_load,
        cycling_load=cycling_load,
        strength_load=strength_load,
    )

    fatigue_generated = _classify_fatigue_generated(
        recovery_cost=recovery_cost,
        overall_load=overall_load,
    )

    training_type = _classify_training_type(
        cycling_count=len(cycling),
        cycling_minutes=cycling_minutes,
        cycling_load=cycling_load,
        strength_count=len(strength),
        strength_minutes=strength_minutes,
        strength_load=strength_load,
        movement_count=len(movement),
        movement_minutes=movement_minutes,
        movement_context=movement_context,
        overall_load=overall_load,
    )

    primary_session = _identify_primary_session(
        cycling_count=len(cycling),
        cycling_minutes=cycling_minutes,
        strength_count=len(strength),
        strength_minutes=strength_minutes,
        movement_count=len(movement),
        movement_minutes=movement_minutes,
        movement=movement,
    )

    physiological = _build_physiological_interpretation(
        cycling_count=len(cycling),
        cycling_minutes=cycling_minutes,
        cycling_xss=cycling_xss,
        cycling_load=cycling_load,
        strength_count=len(strength),
        strength_minutes=strength_minutes,
        strength_load=strength_load,
        movement_count=len(movement),
        movement_minutes=movement_minutes,
        movement_context=movement_context,
        overall_load=overall_load,
        recovery_cost=recovery_cost,
        fatigue_generated=fatigue_generated,
        training_type=training_type,
    )

    evidence = _build_evidence(
        cycling_count=len(cycling),
        cycling_minutes=cycling_minutes,
        cycling_xss=cycling_xss,
        cycling_load=cycling_load,
        strength_count=len(strength),
        strength_minutes=strength_minutes,
        strength_load=strength_load,
        movement_count=len(movement),
        movement_minutes=movement_minutes,
        movement_context=movement_context,
    )

    narrative = _build_narrative(
        cycling_count=len(cycling),
        cycling_minutes=cycling_minutes,
        cycling_xss=cycling_xss,
        cycling_load=cycling_load,
        strength_count=len(strength),
        strength_minutes=strength_minutes,
        strength_load=strength_load,
        movement_count=len(movement),
        movement_minutes=movement_minutes,
        movement_context=movement_context,
        overall_load=overall_load,
        recovery_cost=recovery_cost,
        physiological=physiological,
    )

    recommendations = _build_recommendations(
        overall_load=overall_load,
        recovery_cost=recovery_cost,
        training_type=training_type,
        coach_meaning=physiological[
            "coach_meaning"
        ],
    )

    confidence = _build_confidence(
        day=day,
        cycling_xss=cycling_xss,
    )

    has_training = _has_meaningful_training(
        cycling_count=len(cycling),
        strength_count=len(strength),
        movement_count=len(movement),
    )

    return {
        "date": analysis_date,
        "status": status,
        "has_training": has_training,

        # Factual load structure
        "training_load": {
            "cycling": {
                "count": len(cycling),
                "minutes": cycling_minutes,
                "xss": cycling_xss,
                "load": cycling_load,
            },
            "strength": {
                "count": len(strength),
                "minutes": strength_minutes,
                "load": strength_load,
            },
            "movement": {
                "count": len(movement),
                "minutes": movement_minutes,
                "context": movement_context,
            },
        },

        "overall_load": overall_load,
        "recovery_cost": recovery_cost,
        "narrative": narrative,
        "evidence": evidence,

        # Coach-compatible fields
        "training_type": training_type,
        "primary_session": primary_session,
        "load": overall_load,
        "fatigue_generated": fatigue_generated,
        "summary": narrative,
        "signals": evidence,
        "recommendations": recommendations,
        "confidence": confidence,

        # Workout Intelligence v2 interpretation
        "workout_type": physiological[
            "workout_type"
        ],
        "primary_stimulus": physiological[
            "primary_stimulus"
        ],
        "primary_stress": physiological[
            "primary_stress"
        ],
        "training_effect": physiological[
            "training_effect"
        ],
        "adaptation_focus": physiological[
            "adaptation_focus"
        ],
        "coach_meaning": physiological[
            "coach_meaning"
        ],
    }


# ---------------------------------------------------------------------
# Physiological interpretation
# ---------------------------------------------------------------------

def _build_physiological_interpretation(
    cycling_count,
    cycling_minutes,
    cycling_xss,
    cycling_load,
    strength_count,
    strength_minutes,
    strength_load,
    movement_count,
    movement_minutes,
    movement_context,
    overall_load,
    recovery_cost,
    fatigue_generated,
    training_type,
):
    has_cycling = cycling_count > 0
    has_strength = strength_count > 0
    has_movement = movement_count > 0

    if (
        has_movement
        and not has_cycling
        and not has_strength
    ):
        if movement_context == "recovery_supportive":
            return {
                "workout_type": "Active recovery day",
                "primary_stimulus": "Recovery movement",
                "primary_stress": "Minimal",
                "training_effect": (
                    "Promoted circulation and maintained activity "
                    "without creating meaningful training fatigue."
                ),
                "adaptation_focus": "Recovery support",
                "coach_meaning": (
                    "Yesterday should not materially limit today’s "
                    "training. Today’s decision should depend mainly "
                    "on health, recovery and readiness signals."
                ),
            }

        return {
            "workout_type": "Movement day",
            "primary_stimulus": "Low-intensity movement",
            "primary_stress": "Low",
            "training_effect": (
                "Added general movement and low-intensity endurance "
                "without a major formal training load."
            ),
            "adaptation_focus": "General activity",
            "coach_meaning": (
                "The movement adds context but should only modestly "
                "influence today’s training decision."
            ),
        }

    if (
        has_cycling
        and has_strength
    ):
        return {
            "workout_type": "Mixed training day",
            "primary_stimulus": (
                "Aerobic and muscular load"
            ),
            "primary_stress": (
                "Combined cardiovascular and muscular"
            ),
            "training_effect": (
                "Created both endurance and strength stimulus, "
                "with recovery demand across multiple systems."
            ),
            "adaptation_focus": (
                "Combined endurance and strength"
            ),
            "coach_meaning": (
                "Today’s plan should consider both aerobic fatigue "
                "and local muscular recovery. Avoid stacking another "
                "demanding mixed session without strong readiness."
            ),
        }

    if has_strength:
        if strength_load == "high":
            return {
                "workout_type": "High-load strength day",
                "primary_stimulus": "Muscular overload",
                "primary_stress": "Muscular",
                "training_effect": (
                    "Created a substantial strength and muscular "
                    "durability stimulus."
                ),
                "adaptation_focus": (
                    "Strength and muscular adaptation"
                ),
                "coach_meaning": (
                    "Cardiovascular freshness may remain reasonable, "
                    "but muscular readiness could be reduced. Avoid "
                    "heavy loading of the same muscles today."
                ),
            }

        if strength_load == "moderate":
            return {
                "workout_type": "Strength development day",
                "primary_stimulus": "Muscular load",
                "primary_stress": "Muscular",
                "training_effect": (
                    "Provided meaningful strength and neuromuscular "
                    "stimulus with moderate recovery cost."
                ),
                "adaptation_focus": "Strength",
                "coach_meaning": (
                    "Today’s cardiovascular training may still be "
                    "possible, but local muscle fatigue should guide "
                    "session choice and intensity."
                ),
            }

        return {
            "workout_type": "Light strength day",
            "primary_stimulus": "Light muscular activation",
            "primary_stress": "Low muscular",
            "training_effect": (
                "Maintained strength routine with limited overall "
                "recovery cost."
            ),
            "adaptation_focus": (
                "Strength maintenance"
            ),
            "coach_meaning": (
                "The session should not strongly limit today unless "
                "subjective soreness or local muscle fatigue is elevated."
            ),
        }

    if has_cycling:
        if cycling_load == "high":
            return {
                "workout_type": "High-stress cycling day",
                "primary_stimulus": (
                    "High aerobic training load"
                ),
                "primary_stress": "Cardiovascular",
                "training_effect": (
                    "Created a large endurance stimulus and a "
                    "meaningful recovery requirement."
                ),
                "adaptation_focus": (
                    "Aerobic fitness and workload tolerance"
                ),
                "coach_meaning": (
                    "Expect reduced freshness. Today should usually "
                    "focus on absorbing the load rather than adding "
                    "another hard cycling stimulus."
                ),
            }

        if cycling_load == "moderate":
            return {
                "workout_type": "Endurance development day",
                "primary_stimulus": (
                    "Moderate aerobic load"
                ),
                "primary_stress": "Cardiovascular",
                "training_effect": (
                    "Provided a useful aerobic endurance stimulus "
                    "with moderate fatigue."
                ),
                "adaptation_focus": "Aerobic base",
                "coach_meaning": (
                    "Today’s session can remain productive if recovery "
                    "signals are supportive, but further hard intensity "
                    "should be considered carefully."
                ),
            }

        if (
            cycling_load in {
                "light",
                "very_light",
            }
            and cycling_minutes <= 60
        ):
            return {
                "workout_type": "Recovery cycling day",
                "primary_stimulus": (
                    "Gentle aerobic movement"
                ),
                "primary_stress": "Low",
                "training_effect": (
                    "Supported circulation and aerobic maintenance "
                    "without meaningful fatigue."
                ),
                "adaptation_focus": "Recovery support",
                "coach_meaning": (
                    "The ride should not materially limit today’s "
                    "training. Health and readiness signals should "
                    "remain the primary decision inputs."
                ),
            }

        return {
            "workout_type": "Aerobic cycling day",
            "primary_stimulus": "Low aerobic load",
            "primary_stress": "Low cardiovascular",
            "training_effect": (
                "Maintained aerobic consistency with limited "
                "recovery cost."
            ),
            "adaptation_focus": (
                "Aerobic maintenance"
            ),
            "coach_meaning": (
                "The previous ride creates only a modest constraint "
                "on today’s training if recovery remains stable."
            ),
        }

    if overall_load == "none":
        return {
            "workout_type": "Rest day",
            "primary_stimulus": "None",
            "primary_stress": "None",
            "training_effect": (
                "No formal training stimulus was recorded."
            ),
            "adaptation_focus": "Recovery",
            "coach_meaning": (
                "There is no recent workout load limiting today. "
                "Use health, recovery and readiness to decide."
            ),
        }

    return {
        "workout_type": training_type,
        "primary_stimulus": "General activity",
        "primary_stress": fatigue_generated.title(),
        "training_effect": (
            "Created a general fitness stimulus."
        ),
        "adaptation_focus": "General fitness",
        "coach_meaning": (
            "Use the recorded load alongside current recovery "
            "and readiness signals."
        ),
    }


# ---------------------------------------------------------------------
# Empty result
# ---------------------------------------------------------------------

def _empty_intelligence(
    target_date,
    status,
    narrative,
):
    return {
        "date": target_date,
        "status": status,
        "has_training": False,
        "training_load": {
            "cycling": {
                "count": 0,
                "minutes": 0.0,
                "xss": 0.0,
                "load": "none",
            },
            "strength": {
                "count": 0,
                "minutes": 0.0,
                "load": "none",
            },
            "movement": {
                "count": 0,
                "minutes": 0.0,
                "context": "none",
            },
        },
        "overall_load": "none",
        "recovery_cost": "none",
        "narrative": narrative,
        "evidence": [],

        "training_type": "No recent training",
        "primary_session": "None",
        "load": "none",
        "fatigue_generated": "none",
        "summary": narrative,
        "signals": [],
        "recommendations": [
            (
                "Use health, recovery and readiness signals "
                "to decide today’s training."
            )
        ],
        "confidence": 55,

        "workout_type": "No recent training",
        "primary_stimulus": "None",
        "primary_stress": "None",
        "training_effect": (
            "No recent formal training stimulus is available."
        ),
        "adaptation_focus": "Recovery and readiness",
        "coach_meaning": (
            "No recent workout load is available to limit today. "
            "The Coach should rely mainly on health, recovery and "
            "readiness signals."
        ),
    }


# ---------------------------------------------------------------------
# Session preparation
# ---------------------------------------------------------------------

def _prepare_sessions(
    sessions: pd.DataFrame,
) -> pd.DataFrame:
    if (
        "session_date"
        not in sessions.columns
    ):
        return pd.DataFrame()

    prepared = sessions.copy()

    prepared = prepared.dropna(
        subset=[
            "session_date"
        ]
    )

    if prepared.empty:
        return prepared

    prepared[
        "session_date"
    ] = (
        prepared[
            "session_date"
        ]
        .astype(
            str
        )
        .str[
            :10
        ]
    )

    return prepared


def _normalise_date(
    value=None,
) -> str:
    if value is None:
        return date.today().isoformat()

    if isinstance(
        value,
        date,
    ):
        return value.isoformat()

    text = str(
        value
    ).strip()

    return text[
        :10
    ]


# ---------------------------------------------------------------------
# Totals
# ---------------------------------------------------------------------

def _sum_minutes(
    dataframe,
):
    if (
        dataframe.empty
        or "duration_minutes"
        not in dataframe.columns
    ):
        return 0.0

    values = pd.to_numeric(
        dataframe[
            "duration_minutes"
        ],
        errors="coerce",
    ).fillna(
        0
    )

    return round(
        float(
            values.sum()
        ),
        1,
    )


def _sum_xert_xss(
    cycling,
):
    total = 0.0

    for _, session in cycling.iterrows():
        try:
            raw = json.loads(
                session.get(
                    "raw_data"
                )
                or "{}"
            )

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            continue

        summary = raw.get(
            "summary",
            {},
        )

        xss = summary.get(
            "xss"
        )

        if xss is None:
            continue

        try:
            total += float(
                xss
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

    return round(
        total,
        1,
    )


def _has_meaningful_training(
    cycling_count,
    strength_count,
    movement_count,
):
    return any(
        [
            cycling_count > 0,
            strength_count > 0,
            movement_count > 0,
        ]
    )


# ---------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------

def _classify_cycling_load(
    cycling_xss,
    cycling_minutes,
    cycling_count,
):
    if cycling_count == 0:
        return "none"

    if cycling_xss >= 90:
        return "high"

    if cycling_xss >= 40:
        return "moderate"

    if cycling_xss > 0:
        return "light"

    if cycling_minutes >= 90:
        return "moderate"

    if cycling_minutes >= 30:
        return "light"

    return "very_light"


def _classify_strength_load(
    strength_minutes,
    strength_count,
):
    if strength_count == 0:
        return "none"

    if strength_minutes >= 60:
        return "high"

    if strength_minutes >= 30:
        return "moderate"

    return "light"


def _classify_movement_context(
    movement_minutes,
    movement_count,
    has_cycling,
    has_strength,
):
    if movement_count == 0:
        return "none"

    if (
        not has_cycling
        and not has_strength
    ):
        return "recovery_supportive"

    if movement_minutes >= 60:
        return "additional_context"

    return "minor_context"


def _classify_overall_load(
    cycling_load,
    strength_load,
    cycling_count,
    strength_count,
    movement_count,
):
    loads = [
        cycling_load,
        strength_load,
    ]

    if "high" in loads:
        return "high"

    if "moderate" in loads:
        if (
            cycling_count > 0
            and strength_count > 0
        ):
            return "high"

        return "moderate"

    if "light" in loads:
        return "light"

    if (
        cycling_count > 0
        or strength_count > 0
    ):
        return "very_light"

    if movement_count > 0:
        return "movement_only"

    return "none"


def _classify_recovery_cost(
    overall_load,
    cycling_load,
    strength_load,
):
    if overall_load == "high":
        return "high"

    if overall_load == "moderate":
        return "moderate"

    if strength_load in {
        "moderate",
        "high",
    }:
        return "muscular"

    if cycling_load in {
        "light",
        "very_light",
    }:
        return "low"

    if overall_load == "movement_only":
        return "minimal"

    return "none"


def _classify_fatigue_generated(
    recovery_cost,
    overall_load,
):
    if recovery_cost == "high":
        return "high"

    if recovery_cost in {
        "moderate",
        "muscular",
    }:
        return "moderate"

    if recovery_cost in {
        "low",
        "minimal",
    }:
        return "low"

    if overall_load == "none":
        return "none"

    return "unknown"


def _classify_training_type(
    cycling_count,
    cycling_minutes,
    cycling_load,
    strength_count,
    strength_minutes,
    strength_load,
    movement_count,
    movement_minutes,
    movement_context,
    overall_load,
):
    if (
        cycling_count > 0
        and strength_count > 0
    ):
        return "Mixed strength and endurance day"

    if strength_count > 0:
        if strength_load == "high":
            return "High-load strength day"

        return "Strength training day"

    if cycling_count > 0:
        if cycling_load == "high":
            return "High-load cycling day"

        if cycling_load == "moderate":
            return "Aerobic endurance day"

        if (
            cycling_load in {
                "light",
                "very_light",
            }
            and cycling_minutes <= 60
        ):
            return "Recovery ride day"

        return "Cycling day"

    if movement_count > 0:
        if movement_context == "recovery_supportive":
            return "Active recovery day"

        if movement_minutes >= 120:
            return "High-volume movement day"

        if movement_minutes >= 60:
            return "Extended movement day"

        return "Light movement day"

    if overall_load == "none":
        return "No training"

    return "General training day"


def _identify_primary_session(
    cycling_count,
    cycling_minutes,
    strength_count,
    strength_minutes,
    movement_count,
    movement_minutes,
    movement,
):
    candidates = []

    if cycling_count > 0:
        candidates.append(
            (
                cycling_minutes,
                "Cycling session",
            )
        )

    if strength_count > 0:
        candidates.append(
            (
                strength_minutes,
                "Strength session",
            )
        )

    if movement_count > 0:
        movement_label = _movement_session_label(
            movement
        )

        candidates.append(
            (
                movement_minutes,
                movement_label,
            )
        )

    if not candidates:
        return "None"

    return max(
        candidates,
        key=lambda item: item[0],
    )[1]


def _movement_session_label(
    movement: pd.DataFrame,
) -> str:
    if movement is None or movement.empty:
        return "Movement session"

    session_types = {
        str(value).strip()
        for value in movement[
            "session_type"
        ].dropna()
        if str(value).strip()
    }

    if session_types == {
        "Walking"
    }:
        return "Recovery walk"

    if session_types == {
        "Running"
    }:
        return "Running session"

    if session_types == {
        "Hiking"
    }:
        return "Hiking session"

    if session_types.issubset(
        {
            "Mobility",
            "Yoga",
        }
    ):
        return "Mobility session"

    return "Movement session"


# ---------------------------------------------------------------------
# Evidence, narrative, recommendations
# ---------------------------------------------------------------------

def _build_evidence(
    cycling_count,
    cycling_minutes,
    cycling_xss,
    cycling_load,
    strength_count,
    strength_minutes,
    strength_load,
    movement_count,
    movement_minutes,
    movement_context,
):
    evidence = []

    if cycling_count:
        evidence.append(
            (
                f"{cycling_count} cycling session(s), "
                f"{cycling_minutes:.1f} min, "
                f"{cycling_xss:.1f} XSS, classified as "
                f"{cycling_load} load."
            )
        )

    if strength_count:
        evidence.append(
            (
                f"{strength_count} strength session(s), "
                f"{strength_minutes:.1f} min, classified as "
                f"{strength_load} load."
            )
        )

    if movement_count:
        evidence.append(
            (
                f"{movement_count} movement session(s), "
                f"{movement_minutes:.1f} min, treated as "
                f"{movement_context} rather than artificial "
                "training strain."
            )
        )

    if not evidence:
        evidence.append(
            (
                "No workout, strength, or movement sessions "
                "were recorded for this day."
            )
        )

    return evidence


def _build_narrative(
    cycling_count,
    cycling_minutes,
    cycling_xss,
    cycling_load,
    strength_count,
    strength_minutes,
    strength_load,
    movement_count,
    movement_minutes,
    movement_context,
    overall_load,
    recovery_cost,
    physiological,
):
    factual_notes = []

    if cycling_count:
        if cycling_load == "high":
            factual_notes.append(
                (
                    "Cycling created a high training load "
                    f"with {cycling_xss:.1f} XSS across "
                    f"{cycling_count} session(s)."
                )
            )

        elif cycling_load == "moderate":
            factual_notes.append(
                (
                    "Cycling created a moderate training load "
                    f"with {cycling_xss:.1f} XSS across "
                    f"{cycling_count} session(s)."
                )
            )

        elif cycling_load == "light":
            factual_notes.append(
                (
                    f"Cycling was light, with {cycling_xss:.1f} "
                    f"XSS across {cycling_count} session(s)."
                )
            )

        else:
            factual_notes.append(
                (
                    "Cycling was very light, with "
                    f"{cycling_minutes:.1f} minutes recorded."
                )
            )

    if strength_count:
        if strength_load == "high":
            factual_notes.append(
                (
                    "Strength work was substantial at "
                    f"{strength_minutes:.1f} minutes."
                )
            )

        elif strength_load == "moderate":
            factual_notes.append(
                (
                    "Strength work was meaningful at "
                    f"{strength_minutes:.1f} minutes."
                )
            )

        else:
            factual_notes.append(
                (
                    "Strength work was light at "
                    f"{strength_minutes:.1f} minutes."
                )
            )

    if movement_count:
        if movement_context == "recovery_supportive":
            factual_notes.append(
                (
                    "Movement was recovery-supportive, with "
                    f"{movement_minutes:.1f} minutes recorded."
                )
            )

        else:
            factual_notes.append(
                (
                    "Additional movement added useful context "
                    "without being treated as artificial strain."
                )
            )

    if not factual_notes:
        factual_notes.append(
            "No meaningful workout load was recorded."
        )

    workout_type = str(
        physiological.get(
            "workout_type",
            "general training day",
        )
    ).strip()

    first_letter = (
        workout_type[0].lower()
        if workout_type
        else ""
    )

    article = (
        "an"
        if first_letter in {
            "a",
            "e",
            "i",
            "o",
            "u",
        }
        else "a"
    )

    interpretation = (
        f"This was classified as {article} "
        f"{workout_type.lower()}. "
        f"{physiological.get('training_effect', '')} "
        f"{physiological.get('coach_meaning', '')}"
    ).strip()

    return (
        " ".join(
            factual_notes
        )
        + " "
        + interpretation
    ).strip()


def _build_recommendations(
    overall_load,
    recovery_cost,
    training_type,
    coach_meaning,
):
    recommendations = [
        coach_meaning
    ]

    if overall_load == "high":
        recommendations.append(
            (
                "Avoid stacking another hard session until "
                "recovery and readiness clearly support it."
            )
        )

    elif overall_load == "moderate":
        recommendations.append(
            (
                "Account for the recent training load before "
                "adding further intensity."
            )
        )

    elif overall_load in {
        "light",
        "very_light",
    }:
        recommendations.append(
            (
                "The recent load should not be strongly limiting "
                "if current recovery signals remain stable."
            )
        )

    elif overall_load == "movement_only":
        recommendations.append(
            (
                "Treat the day as active recovery rather than "
                "a major training stress."
            )
        )

    else:
        recommendations.append(
            (
                "No meaningful recent workout load is available "
                "to limit today’s decision."
            )
        )

    if recovery_cost == "muscular":
        recommendations.append(
            (
                "Consider local muscle fatigue when choosing "
                "today’s activity."
            )
        )

    if training_type == "Recovery ride day":
        recommendations.append(
            (
                "The previous ride appears compatible with "
                "recovery rather than a major fitness stress."
            )
        )

    return _deduplicate(
        recommendations
    )


def _build_confidence(
    day,
    cycling_xss,
):
    score = 60

    if day is not None and not day.empty:
        score += 10

    if (
        "duration_minutes"
        in day.columns
        and day["duration_minutes"].notna().any()
    ):
        score += 10

    if (
        "source"
        in day.columns
        and day["source"].notna().any()
    ):
        score += 5

    if (
        "session_type"
        in day.columns
        and day["session_type"].notna().any()
    ):
        score += 5

    if cycling_xss > 0:
        score += 10

    return min(
        score,
        95,
    )


def _deduplicate(
    values,
):
    result = []

    for value in values:
        if (
            value
            and value not in result
        ):
            result.append(
                value
            )

    return result