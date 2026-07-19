from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------

def build_coach_recommendation(
    health_intelligence,
    workout_intelligence=None,
    recovery_profile=None,
    readiness_profile=None,
    timeline_context=None,
    athlete_context=None,
    goal_context=None,
):
    """
    Build a structured daily coaching prescription.

    Coach Engine v2 decides:
        - whether training is appropriate;
        - the best session type;
        - duration range;
        - intensity ceiling;
        - purpose;
        - execution steps;
        - stop conditions;
        - alternatives;
        - activities to avoid.

    Weather and indoor/outdoor context are handled later by Daily Advice.
    Weather may change when and how a session is performed, but must not
    override health, recovery, or Timeline guardrails.
    """

    health = _safe_dict(
        health_intelligence
    )

    workout = _safe_dict(
        workout_intelligence
    )

    recovery = _safe_dict(
        recovery_profile
    )

    readiness = _safe_dict(
        readiness_profile
    )

    timeline = _safe_dict(
        timeline_context
    )

    athlete = _safe_dict(
        athlete_context
    )

    goals = _safe_dict(
        goal_context
    )

    assessment = _build_coaching_assessment(
        health=health,
        workout=workout,
        recovery=recovery,
        readiness=readiness,
        timeline=timeline,
        athlete=athlete,
        goals=goals,
    )

    prescription = _choose_prescription(
        assessment
    )

    prescription = _apply_timeline_guardrail(
        prescription=prescription,
        timeline_assessment=assessment[
            "timeline"
        ],
    )

    reasoning = _build_reasoning(
        assessment=assessment,
        prescription=prescription,
    )

    confidence = _build_confidence(
        health=health,
        workout=workout,
        recovery=recovery,
        readiness=readiness,
        timeline=timeline,
    )

    return {
        "status": prescription["status"],
        "mode": prescription["mode"],
        "title": prescription["title"],
        "decision": prescription["decision"],
        "recommendation": prescription[
            "recommendation"
        ],

        # Specific training prescription
        "training_permission": prescription[
            "training_permission"
        ],
        "session_type": prescription[
            "session_type"
        ],
        "primary_focus": prescription[
            "primary_focus"
        ],
        "purpose": prescription[
            "purpose"
        ],
        "duration_min": prescription[
            "duration_min"
        ],
        "duration_max": prescription[
            "duration_max"
        ],
        "duration_text": _duration_text(
            prescription["duration_min"],
            prescription["duration_max"],
        ),
        "intensity_limit": prescription[
            "intensity_limit"
        ],
        "effort_guidance": prescription[
            "effort_guidance"
        ],
        "execution_steps": prescription[
            "execution_steps"
        ],
        "stop_conditions": prescription[
            "stop_conditions"
        ],
        "avoid": prescription[
            "avoid"
        ],
        "alternatives": prescription[
            "alternatives"
        ],

        # Explanation
        "reasoning": reasoning,
        "reasons": reasoning,
        "warnings": prescription.get(
            "warnings",
            [],
        ),
        "opportunities": prescription.get(
            "opportunities",
            [],
        ),
        "confidence": confidence,

        # Current-state transparency
        "health_status": assessment[
            "health_status"
        ],
        "health_readiness": assessment[
            "health_readiness"
        ],
        "recovery_state": assessment[
            "recovery_state"
        ],
        "readiness_state": assessment[
            "readiness_state"
        ],
        "recent_workout_load": assessment[
            "workout_load"
        ],
        "recent_workout_fatigue": assessment[
            "workout_fatigue"
        ],
        "recent_workout_type": assessment[
            "workout_type"
        ],
        "physiological_state": assessment[
            "physiological_state"
        ],
        "recent_load_state": assessment[
            "recent_load_state"
        ],
        "primary_goal": assessment[
            "primary_goal"
        ],

        # Timeline transparency
        "timeline_awareness": assessment[
            "timeline"
        ][
            "has_relevant_context"
        ],
        "timeline_guardrail_applied": (
            prescription.get(
                "timeline_guardrail_applied",
                False,
            )
        ),
        "timeline_context_note": assessment[
            "timeline"
        ][
            "context_note"
        ],
        "timeline_reasons": assessment[
            "timeline"
        ][
            "reasons"
        ],
    }


# ---------------------------------------------------------------------
# Coaching assessment
# ---------------------------------------------------------------------

def _build_coaching_assessment(
    health: Dict[str, Any],
    workout: Dict[str, Any],
    recovery: Dict[str, Any],
    readiness: Dict[str, Any],
    timeline: Dict[str, Any],
    athlete: Dict[str, Any],
    goals: Dict[str, Any],
) -> Dict[str, Any]:
    health_status = _normalise_state(
        _get_first(
            health,
            [
                "status",
                "health_status",
            ],
            "unknown",
        )
    )

    health_readiness = _normalise_state(
        _get_first(
            health,
            [
                "readiness",
                "readiness_label",
            ],
            "unknown",
        )
    )

    recovery_state = _normalise_state(
        _get_first(
            recovery,
            [
                "status",
                "label",
                "recovery_label",
                "state",
            ],
            "unknown",
        )
    )

    readiness_state = _normalise_state(
        _get_first(
            readiness,
            [
                "status",
                "label",
                "readiness_label",
                "state",
            ],
            "unknown",
        )
    )

    recovery_score = _get_numeric(
        recovery,
        [
            "score",
            "recovery_score",
        ],
    )

    readiness_score = _get_numeric(
        readiness,
        [
            "score",
            "readiness_score",
            "capacity",
        ],
    )

    workout_load = _normalise_state(
        _get_first(
            workout,
            [
                "load",
            ],
            "unknown",
        )
    )

    workout_fatigue = _normalise_state(
        _get_first(
            workout,
            [
                "fatigue_generated",
                "fatigue",
            ],
            "unknown",
        )
    )

    workout_type = _clean_text(
        _get_first(
            workout,
            [
                "training_type",
                "primary_session",
            ],
            "Unknown",
        ),
        "Unknown",
    )

    timeline_assessment = _assess_timeline_context(
        timeline
    )

    physiological_state = _classify_physiological_state(
        health_status=health_status,
        health_readiness=health_readiness,
        recovery_state=recovery_state,
        readiness_state=readiness_state,
        recovery_score=recovery_score,
        readiness_score=readiness_score,
    )

    recent_load_state = _classify_recent_load(
        workout_load=workout_load,
        workout_fatigue=workout_fatigue,
    )

    primary_goal = _extract_primary_goal(
        goals=goals,
        athlete=athlete,
        timeline_assessment=timeline_assessment,
    )

    return {
        "health_status": health_status,
        "health_readiness": health_readiness,
        "recovery_state": recovery_state,
        "readiness_state": readiness_state,
        "recovery_score": recovery_score,
        "readiness_score": readiness_score,
        "workout_load": workout_load,
        "workout_fatigue": workout_fatigue,
        "workout_type": workout_type,
        "physiological_state": physiological_state,
        "recent_load_state": recent_load_state,
        "primary_goal": primary_goal,
        "timeline": timeline_assessment,
    }


def _classify_physiological_state(
    health_status: str,
    health_readiness: str,
    recovery_state: str,
    readiness_state: str,
    recovery_score: Optional[float],
    readiness_score: Optional[float],
) -> str:
    caution_terms = {
        "needs caution",
        "needs_caution",
        "reduced",
        "poor",
        "low",
        "not ready",
        "unwell",
        "warning",
        "caution",
    }

    moderate_terms = {
        "mixed",
        "moderate",
        "fair",
        "limited",
        "recovering",
    }

    positive_terms = {
        "good",
        "high",
        "ready",
        "strong",
        "excellent",
        "optimal",
    }

    states = {
        health_status,
        health_readiness,
        recovery_state,
        readiness_state,
    }

    if states.intersection(
        caution_terms
    ):
        return "protecting"

    if (
        recovery_score is not None
        and recovery_score < 45
    ):
        return "protecting"

    if (
        readiness_score is not None
        and readiness_score < 45
    ):
        return "protecting"

    if states.intersection(
        moderate_terms
    ):
        return "monitoring"

    if (
        recovery_score is not None
        and recovery_score < 65
    ):
        return "monitoring"

    if (
        readiness_score is not None
        and readiness_score < 65
    ):
        return "monitoring"

    positive_count = sum(
        state in positive_terms
        for state in states
    )

    if positive_count >= 2:
        return "ready"

    return "uncertain"


def _classify_recent_load(
    workout_load: str,
    workout_fatigue: str,
) -> str:
    if (
        workout_load in {
            "very high",
            "high",
        }
        or workout_fatigue == "high"
    ):
        return "heavy"

    if (
        workout_load == "moderate"
        or workout_fatigue == "moderate"
    ):
        return "meaningful"

    if (
        workout_load in {
            "none",
            "low",
            "unknown",
        }
        and workout_fatigue in {
            "none",
            "low",
            "unknown",
        }
    ):
        return "light"

    return "unknown"


# ---------------------------------------------------------------------
# Prescription selection
# ---------------------------------------------------------------------

def _choose_prescription(
    assessment: Dict[str, Any],
) -> Dict[str, Any]:
    physiological_state = assessment[
        "physiological_state"
    ]

    recent_load_state = assessment[
        "recent_load_state"
    ]

    timeline = assessment[
        "timeline"
    ]

    if timeline[
        "requires_medical_caution"
    ]:
        return _medical_recovery_prescription()

    if physiological_state == "protecting":
        return _recovery_prescription()

    if recent_load_state == "heavy":
        return _absorb_load_prescription()

    if physiological_state == "monitoring":
        return _controlled_aerobic_prescription()

    if (
        physiological_state == "ready"
        and recent_load_state == "light"
    ):
        return _productive_training_prescription()

    if (
        physiological_state == "ready"
        and recent_load_state == "meaningful"
    ):
        return _endurance_prescription()

    return _conservative_prescription()


# ---------------------------------------------------------------------
# Prescription templates
# ---------------------------------------------------------------------

def _medical_recovery_prescription() -> Dict[str, Any]:
    return {
        "status": "caution",
        "mode": "Protecting",
        "title": "Recovery context takes priority",
        "decision": "Very easy movement only",
        "recommendation": (
            "Today should remain recovery-led. If you choose "
            "to train, keep the session short, gentle, and "
            "easy to stop."
        ),
        "training_permission": "Easy only",
        "session_type": "Recovery ride or easy walk",
        "primary_focus": "Recovery",
        "purpose": (
            "Promote circulation and maintain routine without "
            "creating meaningful additional fatigue."
        ),
        "duration_min": 20,
        "duration_max": 40,
        "intensity_limit": "Zone 1",
        "effort_guidance": (
            "Very easy, fully conversational effort. There "
            "should be no pressure to complete the full duration."
        ),
        "execution_steps": [
            "Begin with 10 minutes at an extremely easy effort.",
            (
                "Reassess energy, comfort, and symptoms after "
                "the warm-up."
            ),
            (
                "Continue only while the effort feels genuinely "
                "restorative."
            ),
            (
                "Finish early rather than trying to achieve a "
                "training target."
            ),
        ],
        "stop_conditions": [
            "New or increasing pain",
            "Unusual fatigue or weakness",
            "Dizziness or light-headedness",
            "Chest discomfort",
            "Unexpected shortness of breath",
            "A clear deterioration in how you feel",
        ],
        "avoid": [
            "Intervals",
            "Threshold work",
            "Sprinting",
            "Heavy strength training",
            "Long duration",
            "Training through symptoms",
        ],
        "alternatives": [
            "Complete rest",
            "Short easy walk",
            "Gentle mobility",
        ],
        "warnings": [
            (
                "Recent medical context places a conservative "
                "ceiling on training."
            )
        ],
        "opportunities": [
            (
                "Maintain movement without compromising "
                "recovery."
            )
        ],
    }


def _recovery_prescription() -> Dict[str, Any]:
    return {
        "status": "caution",
        "mode": "Recovering",
        "title": "Recovery-first day",
        "decision": "Recovery session",
        "recommendation": (
            "Your current signals favour recovery rather than "
            "training stress. A very easy ride, short walk, "
            "or rest is the best fit."
        ),
        "training_permission": "Easy only",
        "session_type": "Recovery ride",
        "primary_focus": "Recovery",
        "purpose": (
            "Support circulation and movement while protecting "
            "recovery."
        ),
        "duration_min": 25,
        "duration_max": 45,
        "intensity_limit": "Zone 1",
        "effort_guidance": (
            "Keep breathing completely conversational and avoid "
            "any sustained pressure on the pedals."
        ),
        "execution_steps": [
            "Ride very easily for the first 10 minutes.",
            "Keep cadence comfortable and resistance low.",
            "Do not chase power, speed, or distance.",
            (
                "Stop at the lower end of the duration if "
                "energy does not improve."
            ),
        ],
        "stop_conditions": [
            "Energy falls during the session",
            "Soreness or pain increases",
            (
                "Heart rate feels unusually high for the "
                "effort"
            ),
            "The session stops feeling restorative",
        ],
        "avoid": [
            "Intervals",
            "Threshold work",
            "Hard climbs",
            "Sprints",
            "Long endurance volume",
        ],
        "alternatives": [
            "Easy walk",
            "Mobility",
            "Rest",
        ],
        "warnings": [],
        "opportunities": [
            (
                "Use gentle activity to support recovery and "
                "consistency."
            )
        ],
    }


def _absorb_load_prescription() -> Dict[str, Any]:
    return {
        "status": "controlled",
        "mode": "Absorbing",
        "title": "Absorb the recent training load",
        "decision": "Easy endurance or recovery",
        "recommendation": (
            "Recent training created meaningful fatigue. Today "
            "is better used to absorb that work than to add "
            "another hard stimulus."
        ),
        "training_permission": "Yes, controlled",
        "session_type": "Easy aerobic ride",
        "primary_focus": "Recovery and aerobic maintenance",
        "purpose": (
            "Maintain aerobic movement while allowing adaptation "
            "from recent training."
        ),
        "duration_min": 35,
        "duration_max": 60,
        "intensity_limit": "Zone 1 to low Zone 2",
        "effort_guidance": (
            "Comfortable aerobic effort with no sustained work "
            "near threshold."
        ),
        "execution_steps": [
            "Start with at least 10 easy minutes.",
            (
                "Keep most of the session in Zone 1 or low "
                "Zone 2."
            ),
            (
                "Avoid surges, hard climbs, and unnecessary "
                "resistance."
            ),
            (
                "Finish feeling that you could comfortably have "
                "continued."
            ),
        ],
        "stop_conditions": [
            "Leg fatigue becomes progressively worse",
            "Heart rate is unusually elevated",
            "Power feels unexpectedly difficult",
            "General energy declines",
        ],
        "avoid": [
            "VO₂ intervals",
            "Threshold intervals",
            "Race efforts",
            "Heavy lower-body strength work",
        ],
        "alternatives": [
            "Recovery ride",
            "Easy walk",
            "Rest",
        ],
        "warnings": [],
        "opportunities": [
            (
                "Consolidate recent training rather than dilute "
                "it with excess fatigue."
            )
        ],
    }


def _controlled_aerobic_prescription() -> Dict[str, Any]:
    return {
        "status": "moderate",
        "mode": "Monitoring",
        "title": "Controlled aerobic day",
        "decision": "Zone 2 endurance",
        "recommendation": (
            "Training is reasonable today, but the best return "
            "comes from controlled aerobic work rather than "
            "hard intensity."
        ),
        "training_permission": "Yes",
        "session_type": "Endurance ride",
        "primary_focus": "Aerobic base",
        "purpose": (
            "Build aerobic consistency without creating "
            "excessive fatigue."
        ),
        "duration_min": 45,
        "duration_max": 75,
        "intensity_limit": "Zone 2",
        "effort_guidance": (
            "Steady conversational effort. Avoid drifting into "
            "threshold or turning the ride into a test."
        ),
        "execution_steps": [
            "Warm up gradually for 10 to 15 minutes.",
            "Settle into a sustainable Zone 2 rhythm.",
            (
                "Keep the effort smooth rather than responding "
                "to every change in terrain."
            ),
            (
                "Reduce duration if energy or comfort "
                "deteriorates."
            ),
        ],
        "stop_conditions": [
            (
                "Zone 2 power requires unusually high effort"
            ),
            "Heart rate drifts excessively",
            "Fatigue rises quickly",
            "Pain or symptoms appear",
        ],
        "avoid": [
            "VO₂ intervals",
            "Maximal efforts",
            "Unplanned racing",
            "Very long duration",
        ],
        "alternatives": [
            "Short Zone 1 ride",
            "Easy walk",
            "Mobility",
        ],
        "warnings": [],
        "opportunities": [
            (
                "Add useful aerobic work while keeping recovery "
                "manageable."
            )
        ],
    }


def _productive_training_prescription() -> Dict[str, Any]:
    return {
        "status": "green",
        "mode": "Building",
        "title": "Good opportunity to train",
        "decision": "Quality or endurance session",
        "recommendation": (
            "Health and recovery signals are supportive, and "
            "recent load does not appear limiting. Today can "
            "accommodate productive training."
        ),
        "training_permission": "Yes",
        "session_type": "Planned quality or endurance ride",
        "primary_focus": "Fitness development",
        "purpose": (
            "Use good readiness for a meaningful training "
            "stimulus that supports the current plan."
        ),
        "duration_min": 60,
        "duration_max": 90,
        "intensity_limit": "As planned, controlled",
        "effort_guidance": (
            "Complete the intended quality work with discipline. "
            "Good readiness is permission to train, not a reason "
            "to overreach."
        ),
        "execution_steps": [
            (
                "Warm up fully before deciding how hard the "
                "session should become."
            ),
            (
                "Complete the planned main set without adding "
                "extra intervals."
            ),
            "Keep technique and pacing controlled.",
            "Finish with an appropriate cool-down.",
        ],
        "stop_conditions": [
            "Warm-up response is unexpectedly poor",
            (
                "Target power cannot be held with normal "
                "effort"
            ),
            (
                "Heart rate response is abnormal for the "
                "session"
            ),
            "Pain, dizziness, or unusual symptoms occur",
        ],
        "avoid": [
            "Adding unnecessary volume",
            "Turning the session into an all-out test",
            "Ignoring a poor warm-up response",
        ],
        "alternatives": [
            "Zone 2 endurance",
            "Strength session",
            "Shorter quality session",
        ],
        "warnings": [],
        "opportunities": [
            (
                "Use supportive recovery to create a productive "
                "fitness stimulus."
            )
        ],
    }


def _endurance_prescription() -> Dict[str, Any]:
    return {
        "status": "green",
        "mode": "Maintaining",
        "title": "Productive endurance day",
        "decision": "Aerobic endurance",
        "recommendation": (
            "Your current condition supports training, but "
            "recent load makes steady endurance a better choice "
            "than another demanding session."
        ),
        "training_permission": "Yes",
        "session_type": "Zone 2 endurance ride",
        "primary_focus": "Aerobic development",
        "purpose": (
            "Build aerobic fitness while keeping the total "
            "recovery cost controlled."
        ),
        "duration_min": 50,
        "duration_max": 80,
        "intensity_limit": "Zone 2",
        "effort_guidance": (
            "Steady, controlled aerobic work with enough "
            "restraint to remain fresh afterward."
        ),
        "execution_steps": [
            "Warm up progressively.",
            "Ride primarily in Zone 2.",
            (
                "Avoid prolonged surges above the planned "
                "intensity."
            ),
            "Finish with stable form and energy.",
        ],
        "stop_conditions": [
            (
                "Legs feel markedly worse as the ride "
                "progresses"
            ),
            "Heart rate response is unusually high",
            (
                "The planned endurance effort becomes "
                "threshold-like"
            ),
            "Pain or unusual symptoms occur",
        ],
        "avoid": [
            "Hard intervals",
            "Racing",
            "Excess duration",
        ],
        "alternatives": [
            "Short endurance ride",
            "Recovery ride",
            "Strength session with controlled volume",
        ],
        "warnings": [],
        "opportunities": [
            (
                "Continue building aerobic consistency without "
                "stacking excessive intensity."
            )
        ],
    }


def _conservative_prescription() -> Dict[str, Any]:
    return {
        "status": "unknown",
        "mode": "Monitoring",
        "title": "Use a conservative approach",
        "decision": "Easy aerobic training",
        "recommendation": (
            "Phoenix does not yet have enough clear evidence for "
            "a demanding session. Use the warm-up as a readiness "
            "check and keep the day sensible."
        ),
        "training_permission": "Conditional",
        "session_type": "Easy ride or walk",
        "primary_focus": "Assessment and consistency",
        "purpose": (
            "Maintain movement while gathering feedback from "
            "how the body responds."
        ),
        "duration_min": 30,
        "duration_max": 60,
        "intensity_limit": "Zone 1 to low Zone 2",
        "effort_guidance": (
            "Begin very easily and increase only if the response "
            "is clearly normal."
        ),
        "execution_steps": [
            (
                "Use the first 10 to 15 minutes as an "
                "assessment."
            ),
            (
                "Stay easy unless energy and cardiovascular "
                "response feel normal."
            ),
            "Choose the shorter duration when uncertain.",
            "Finish before fatigue becomes meaningful.",
        ],
        "stop_conditions": [
            "Warm-up response feels abnormal",
            "Energy remains poor",
            "Heart rate is unexpectedly high",
            "Pain or symptoms develop",
        ],
        "avoid": [
            "Hard intervals",
            "Maximal testing",
            (
                "Committing to a long session before the "
                "warm-up"
            ),
        ],
        "alternatives": [
            "Easy walk",
            "Mobility",
            "Rest",
        ],
        "warnings": [
            (
                "The available signals do not support a "
                "high-confidence hard-training decision."
            )
        ],
        "opportunities": [
            (
                "Use an easy session to learn more about current "
                "readiness."
            )
        ],
    }


# ---------------------------------------------------------------------
# Timeline assessment and guardrail
# ---------------------------------------------------------------------

def _assess_timeline_context(
    timeline_context: Dict[str, Any],
) -> Dict[str, Any]:
    if not timeline_context:
        return {
            "has_relevant_context": False,
            "requires_medical_caution": False,
            "requires_recovery_caution": False,
            "has_active_recovery_event": False,
            "highest_severity": None,
            "context_note": None,
            "reasons": [],
        }

    has_recent_surgery = bool(
        timeline_context.get(
            "has_recent_surgery",
            False,
        )
    )

    has_recent_cardiac_event = bool(
        timeline_context.get(
            "has_recent_cardiac_event",
            False,
        )
    )

    has_recent_hospital_event = bool(
        timeline_context.get(
            "has_recent_hospital_event",
            False,
        )
    )

    has_recent_illness = bool(
        timeline_context.get(
            "has_recent_illness",
            False,
        )
    )

    has_active_recovery_event = bool(
        timeline_context.get(
            "has_active_recovery_event",
            False,
        )
    )

    recovery_phase = bool(
        timeline_context.get(
            "recovery_phase",
            False,
        )
    )

    highest_severity = _clean_text(
        timeline_context.get(
            "highest_severity"
        )
    )

    reasons: List[str] = []

    if has_recent_surgery:
        reasons.append(
            "Recent surgery remains relevant."
        )

    if has_recent_cardiac_event:
        reasons.append(
            (
                "A recent cardiac or resuscitation event "
                "remains relevant."
            )
        )

    if has_recent_hospital_event:
        reasons.append(
            (
                "Recent hospital treatment remains part of "
                "the recovery context."
            )
        )

    if has_recent_illness:
        reasons.append(
            (
                "Recent illness may still affect training "
                "tolerance."
            )
        )

    if has_active_recovery_event:
        reasons.append(
            "A recovery event is currently active."
        )

    requires_medical_caution = any(
        [
            has_recent_surgery,
            has_recent_cardiac_event,
            has_recent_hospital_event,
        ]
    )

    requires_recovery_caution = any(
        [
            requires_medical_caution,
            has_recent_illness,
            has_active_recovery_event,
            recovery_phase,
        ]
    )

    has_relevant_context = bool(
        reasons
        or timeline_context.get(
            "has_active_events",
            False,
        )
    )

    context_note = None

    if (
        has_recent_cardiac_event
        and has_recent_surgery
    ):
        context_note = (
            "Recent surgery and the cardiac event during the "
            "operation remain important recovery context."
        )

    elif has_recent_surgery:
        context_note = (
            "Recent surgery remains important recovery context."
        )

    elif has_recent_cardiac_event:
        context_note = (
            (
                "The recent cardiac event remains important "
                "recovery context."
            )
        )

    elif has_active_recovery_event:
        context_note = (
            (
                "An active recovery event remains recorded on "
                "the Timeline."
            )
        )

    elif has_recent_illness:
        context_note = (
            (
                "A recent illness remains relevant to training "
                "tolerance."
            )
        )

    elif recovery_phase:
        context_note = (
            "Recent recovery events remain relevant."
        )

    return {
        "has_relevant_context": has_relevant_context,
        "requires_medical_caution": (
            requires_medical_caution
        ),
        "requires_recovery_caution": (
            requires_recovery_caution
        ),
        "has_active_recovery_event": (
            has_active_recovery_event
        ),
        "highest_severity": highest_severity or None,
        "context_note": context_note,
        "reasons": reasons,
    }


def _apply_timeline_guardrail(
    prescription: Dict[str, Any],
    timeline_assessment: Dict[str, Any],
) -> Dict[str, Any]:
    result = dict(
        prescription
    )

    if timeline_assessment[
        "requires_medical_caution"
    ]:
        protected = _medical_recovery_prescription()

        protected[
            "timeline_guardrail_applied"
        ] = True

        if timeline_assessment[
            "context_note"
        ]:
            protected["recommendation"] = (
                f"{protected['recommendation']} "
                f"{timeline_assessment['context_note']}"
            )

        return protected

    if (
        timeline_assessment[
            "requires_recovery_caution"
        ]
        and result["status"] in {
            "green",
            "moderate",
            "unknown",
        }
    ):
        controlled = _recovery_prescription()

        controlled.update(
            {
                "status": "controlled",
                "mode": "Recovering",
                "title": "Keep recovery in view",
                "decision": "Easy aerobic or recovery",
                "training_permission": "Yes, easy only",
                "session_type": (
                    "Recovery ride or easy walk"
                ),
                "duration_min": 25,
                "duration_max": 50,
                "intensity_limit": (
                    "Zone 1 to low Zone 2"
                ),
                "timeline_guardrail_applied": True,
            }
        )

        controlled["recommendation"] = (
            "Current measurements may support activity, but "
            "recent Timeline events justify a conservative "
            "session."
        )

        if timeline_assessment[
            "context_note"
        ]:
            controlled["recommendation"] += (
                f" {timeline_assessment['context_note']}"
            )

        return controlled

    result[
        "timeline_guardrail_applied"
    ] = False

    return result


# ---------------------------------------------------------------------
# Reasoning and confidence
# ---------------------------------------------------------------------

def _build_reasoning(
    assessment: Dict[str, Any],
    prescription: Dict[str, Any],
) -> List[str]:
    reasoning: List[str] = []

    reasoning.append(
        f"Health status is {assessment['health_status']}."
    )

    reasoning.append(
        (
            "Health readiness is "
            f"{assessment['health_readiness']}."
        )
    )

    if assessment[
        "recovery_state"
    ] != "unknown":
        reasoning.append(
            (
                "Recovery state is "
                f"{assessment['recovery_state']}."
            )
        )

    if assessment[
        "readiness_state"
    ] != "unknown":
        reasoning.append(
            (
                "Readiness state is "
                f"{assessment['readiness_state']}."
            )
        )

    if assessment[
        "workout_type"
    ] != "Unknown":
        reasoning.append(
            (
                "Most recent training pattern: "
                f"{assessment['workout_type']}."
            )
        )

    if assessment[
        "workout_load"
    ] != "unknown":
        reasoning.append(
            (
                "Recent workout load is "
                f"{assessment['workout_load']}."
            )
        )

    if assessment[
        "workout_fatigue"
    ] != "unknown":
        reasoning.append(
            (
                "Recent workout fatigue is "
                f"{assessment['workout_fatigue']}."
            )
        )

    for timeline_reason in assessment[
        "timeline"
    ][
        "reasons"
    ]:
        reasoning.append(
            f"Timeline: {timeline_reason}"
        )

    reasoning.append(
        (
            "The recommended session is designed primarily "
            f"for {prescription['primary_focus'].lower()}."
        )
    )

    return reasoning


def _build_confidence(
    health: Dict[str, Any],
    workout: Dict[str, Any],
    recovery: Dict[str, Any],
    readiness: Dict[str, Any],
    timeline: Dict[str, Any],
) -> int:
    weighted_components: List[float] = []
    total_weight = 0.0

    health_confidence = _normalise_confidence(
        health.get(
            "confidence"
        )
    )

    workout_confidence = _normalise_confidence(
        workout.get(
            "confidence"
        )
    )

    recovery_confidence = _normalise_confidence(
        recovery.get(
            "confidence"
        )
    )

    readiness_confidence = _normalise_confidence(
        readiness.get(
            "confidence"
        )
    )

    confidence_sources = [
        (
            health_confidence,
            0.40,
        ),
        (
            recovery_confidence,
            0.25,
        ),
        (
            readiness_confidence,
            0.25,
        ),
        (
            workout_confidence,
            0.10,
        ),
    ]

    for confidence, weight in confidence_sources:
        if confidence is None:
            continue

        weighted_components.append(
            confidence * weight
        )

        total_weight += weight

    if not weighted_components or total_weight <= 0:
        return 55

    confidence = (
        sum(weighted_components)
        / total_weight
    )

    if timeline:
        confidence = min(
            confidence + 3,
            95,
        )

    return round(
        max(
            0,
            min(
                confidence,
                95,
            ),
        )
    )


# ---------------------------------------------------------------------
# Goal helpers
# ---------------------------------------------------------------------

def _extract_primary_goal(
    goals: Dict[str, Any],
    athlete: Dict[str, Any],
    timeline_assessment: Dict[str, Any],
) -> str:
    if timeline_assessment[
        "requires_recovery_caution"
    ]:
        return "Recovery"

    goal = _get_first(
        goals,
        [
            "primary_goal",
            "current_goal",
            "goal",
        ],
        None,
    )

    if goal:
        return _clean_text(
            goal,
            "General fitness",
        )

    athlete_goal = _get_first(
        athlete,
        [
            "primary_goal",
            "current_goal",
            "goal",
        ],
        None,
    )

    if athlete_goal:
        return _clean_text(
            athlete_goal,
            "General fitness",
        )

    return "General fitness"


# ---------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------

def _safe_dict(
    value: Any,
) -> Dict[str, Any]:
    if isinstance(
        value,
        dict,
    ):
        return value

    if (
        hasattr(
            value,
            "to_dict",
        )
        and callable(
            value.to_dict
        )
    ):
        result = value.to_dict()

        if isinstance(
            result,
            dict,
        ):
            return result

    if hasattr(
        value,
        "__dict__",
    ):
        return dict(
            value.__dict__
        )

    return {}


def _get_first(
    data: Dict[str, Any],
    keys: List[str],
    default: Any = None,
) -> Any:
    for key in keys:
        value = data.get(
            key
        )

        if value is not None:
            return value

    return default


def _get_numeric(
    data: Dict[str, Any],
    keys: List[str],
) -> Optional[float]:
    value = _get_first(
        data,
        keys,
        None,
    )

    if value is None:
        return None

    try:
        return float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def _normalise_state(
    value: Any,
) -> str:
    text = _clean_text(
        value,
        "unknown",
    )

    return (
        text
        .replace(
            "_",
            " ",
        )
        .strip()
        .lower()
    )


def _clean_text(
    value: Any,
    fallback: str = "",
) -> str:
    if value is None:
        return fallback

    text = str(
        value
    ).strip()

    return text or fallback


def _normalise_confidence(
    value: Any,
) -> Optional[float]:
    if value is None:
        return None

    try:
        result = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if result <= 1:
        result *= 100

    return max(
        0,
        min(
            result,
            100,
        ),
    )


def _duration_text(
    minimum: Optional[int],
    maximum: Optional[int],
) -> str:
    if (
        minimum is None
        and maximum is None
    ):
        return "As appropriate"

    if maximum is None:
        return f"At least {minimum} minutes"

    if minimum is None:
        return f"Up to {maximum} minutes"

    if minimum == maximum:
        return f"{minimum} minutes"

    return f"{minimum}–{maximum} minutes"