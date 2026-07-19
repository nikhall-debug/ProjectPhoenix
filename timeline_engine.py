from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from database import (
    load_active_life_events,
    load_life_events,
    load_life_events_between,
    load_recent_life_events,
)


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

SEVERITY_RANKS = {
    "Info": 1,
    "Minor": 2,
    "Moderate": 3,
    "Major": 4,
    "Critical": 5,
}

MEDICAL_CATEGORIES = {
    "Medical",
    "Illness",
    "Medication",
}

RECOVERY_CATEGORIES = {
    "Recovery",
    "Medical",
    "Illness",
}

TRAINING_CATEGORIES = {
    "Training",
    "Milestone",
}

CONTEXT_RELEVANT_CATEGORIES = {
    "Medical",
    "Illness",
    "Recovery",
    "Medication",
    "Training",
    "Nutrition",
    "Sleep",
    "Work",
    "Lifestyle",
    "Travel",
    "Milestone",
}

SIGNIFICANT_SEVERITIES = {
    "Moderate",
    "Major",
    "Critical",
}


# ---------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------

def _clean_text(
    value: Any,
) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _normalise_date(
    value: Any,
    default: Optional[date] = None,
) -> Optional[date]:
    if value is None:
        return default

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    try:
        parsed = pd.to_datetime(
            value,
            errors="coerce",
        )
    except Exception:
        return default

    if pd.isna(parsed):
        return default

    return parsed.date()


def _normalise_reference_date(
    reference_date: Optional[Any],
) -> date:
    resolved = _normalise_date(
        reference_date,
        default=date.today(),
    )

    if resolved is None:
        return date.today()

    return resolved


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        if value is None:
            return default

        return int(value)

    except (TypeError, ValueError):
        return default


def _severity_rank(
    severity: Any,
) -> int:
    return SEVERITY_RANKS.get(
        _clean_text(severity),
        0,
    )


def _split_tags(
    tags: Any,
) -> List[str]:
    clean_tags = _clean_text(
        tags
    )

    if not clean_tags:
        return []

    return [
        tag.strip()
        for tag in clean_tags.split(",")
        if tag.strip()
    ]


def _days_between(
    earlier: Optional[date],
    later: date,
) -> Optional[int]:
    if earlier is None:
        return None

    return (
        later
        - earlier
    ).days


def _event_start_date(
    event: Dict[str, Any],
) -> Optional[date]:
    return _normalise_date(
        event.get("start_date")
        or event.get("event_date")
    )


def _event_end_date(
    event: Dict[str, Any],
) -> Optional[date]:
    return _normalise_date(
        event.get("end_date")
    )


def _event_is_active(
    event: Dict[str, Any],
    reference_date: date,
) -> bool:
    start_date = _event_start_date(
        event
    )

    end_date = _event_end_date(
        event
    )

    if start_date is None:
        return False

    if start_date > reference_date:
        return False

    if end_date is None:
        return True

    return end_date >= reference_date


def _event_is_recent(
    event: Dict[str, Any],
    reference_date: date,
    days: int,
) -> bool:
    start_date = _event_start_date(
        event
    )

    end_date = _event_end_date(
        event
    )

    if start_date is None:
        return False

    cutoff = (
        reference_date
        - timedelta(
            days=max(
                days - 1,
                0,
            )
        )
    )

    effective_end = (
        end_date
        if end_date is not None
        else reference_date
    )

    return (
        start_date <= reference_date
        and effective_end >= cutoff
    )


def _event_duration_days(
    event: Dict[str, Any],
    reference_date: date,
) -> Optional[int]:
    start_date = _event_start_date(
        event
    )

    if start_date is None:
        return None

    end_date = _event_end_date(
        event
    )

    effective_end = (
        end_date
        if end_date is not None
        else reference_date
    )

    return max(
        (
            effective_end
            - start_date
        ).days
        + 1,
        1,
    )


def _event_to_dict(
    event: Dict[str, Any],
    reference_date: date,
) -> Dict[str, Any]:
    start_date = _event_start_date(
        event
    )

    end_date = _event_end_date(
        event
    )

    severity = _clean_text(
        event.get("severity")
    )

    category = _clean_text(
        event.get("category")
    )

    is_active = _event_is_active(
        event,
        reference_date,
    )

    days_since_start = _days_between(
        start_date,
        reference_date,
    )

    days_since_end = None

    if (
        end_date is not None
        and end_date < reference_date
    ):
        days_since_end = _days_between(
            end_date,
            reference_date,
        )

    return {
        "id": event.get("id"),
        "title": _clean_text(
            event.get("title")
        ),
        "category": category,
        "severity": severity,
        "severity_rank": _severity_rank(
            severity
        ),
        "description": _clean_text(
            event.get("description")
        ),
        "tags": _split_tags(
            event.get("tags")
        ),
        "source": _clean_text(
            event.get("source")
        ),
        "event_time": _clean_text(
            event.get("event_time")
        ),
        "start_date": (
            start_date.isoformat()
            if start_date is not None
            else None
        ),
        "end_date": (
            end_date.isoformat()
            if end_date is not None
            else None
        ),
        "is_active": is_active,
        "is_ongoing": (
            start_date is not None
            and end_date is None
        ),
        "days_since_start": days_since_start,
        "days_since_end": days_since_end,
        "duration_days": _event_duration_days(
            event,
            reference_date,
        ),
        "is_medical": (
            category in MEDICAL_CATEGORIES
        ),
        "is_recovery_related": (
            category in RECOVERY_CATEGORIES
        ),
        "is_training_related": (
            category in TRAINING_CATEGORIES
        ),
        "is_significant": (
            severity in SIGNIFICANT_SEVERITIES
        ),
    }


def _frame_to_event_dicts(
    frame: pd.DataFrame,
    reference_date: date,
) -> List[Dict[str, Any]]:
    if frame is None or frame.empty:
        return []

    records = frame.to_dict(
        orient="records"
    )

    events = [
        _event_to_dict(
            event=record,
            reference_date=reference_date,
        )
        for record in records
    ]

    return sorted(
        events,
        key=lambda event: (
            event.get(
                "severity_rank",
                0,
            ),
            event.get(
                "start_date"
            )
            or "",
            event.get(
                "id"
            )
            or 0,
        ),
        reverse=True,
    )


# ---------------------------------------------------------------------
# Public event queries
# ---------------------------------------------------------------------

def get_active_events(
    reference_date: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Return events that are active on the reference date.

    An event is active when:
        start_date <= reference_date
        and end_date is either missing or >= reference_date
    """
    resolved_date = _normalise_reference_date(
        reference_date
    )

    frame = load_active_life_events(
        target_date=resolved_date
    )

    return _frame_to_event_dicts(
        frame=frame,
        reference_date=resolved_date,
    )


def get_recent_events(
    days: int = 30,
    reference_date: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Return events overlapping the recent period.

    This includes ongoing events that started before the selected window.
    """
    resolved_date = _normalise_reference_date(
        reference_date
    )

    try:
        clean_days = max(
            int(days),
            1,
        )
    except (TypeError, ValueError):
        clean_days = 30

    start_date = (
        resolved_date
        - timedelta(
            days=clean_days - 1
        )
    )

    frame = load_life_events_between(
        start_date=start_date,
        end_date=resolved_date,
    )

    events = _frame_to_event_dicts(
        frame=frame,
        reference_date=resolved_date,
    )

    return [
        event
        for event in events
        if _event_is_recent(
            event,
            reference_date=resolved_date,
            days=clean_days,
        )
    ]


def get_events_by_category(
    category: str,
    days: Optional[int] = None,
    reference_date: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Return events belonging to one category.

    When days is supplied, only events overlapping that recent period
    are returned. Otherwise the complete stored history is searched.
    """
    clean_category = _clean_text(
        category
    )

    if not clean_category:
        return []

    resolved_date = _normalise_reference_date(
        reference_date
    )

    if days is None:
        frame = load_life_events()
    else:
        try:
            clean_days = max(
                int(days),
                1,
            )
        except (TypeError, ValueError):
            clean_days = 30

        start_date = (
            resolved_date
            - timedelta(
                days=clean_days - 1
            )
        )

        frame = load_life_events_between(
            start_date=start_date,
            end_date=resolved_date,
        )

    events = _frame_to_event_dicts(
        frame=frame,
        reference_date=resolved_date,
    )

    return [
        event
        for event in events
        if event.get("category") == clean_category
    ]


def get_significant_events(
    days: int = 60,
    reference_date: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Return recent Moderate, Major, and Critical events.
    """
    events = get_recent_events(
        days=days,
        reference_date=reference_date,
    )

    return [
        event
        for event in events
        if event.get(
            "is_significant",
            False,
        )
    ]


# ---------------------------------------------------------------------
# Context interpretation
# ---------------------------------------------------------------------

def _highest_severity(
    events: List[Dict[str, Any]],
) -> Optional[str]:
    if not events:
        return None

    highest = max(
        events,
        key=lambda event: event.get(
            "severity_rank",
            0,
        ),
    )

    severity = _clean_text(
        highest.get("severity")
    )

    return severity or None


def _contains_category(
    events: List[Dict[str, Any]],
    categories: set,
) -> bool:
    return any(
        event.get("category") in categories
        for event in events
    )


def _contains_text(
    events: List[Dict[str, Any]],
    terms: set,
) -> bool:
    clean_terms = {
        term.lower()
        for term in terms
    }

    for event in events:
        searchable_parts = [
            event.get("title"),
            event.get("description"),
            event.get("category"),
            *event.get(
                "tags",
                [],
            ),
        ]

        searchable = " ".join(
            _clean_text(part)
            for part in searchable_parts
        ).lower()

        if any(
            term in searchable
            for term in clean_terms
        ):
            return True

    return False


def _build_context_summary(
    active_events: List[Dict[str, Any]],
    recent_events: List[Dict[str, Any]],
) -> str:
    significant_active = [
        event
        for event in active_events
        if event.get(
            "is_significant",
            False,
        )
    ]

    significant_recent = [
        event
        for event in recent_events
        if (
            event.get(
                "is_significant",
                False,
            )
            and not event.get(
                "is_active",
                False,
            )
        )
    ]

    if significant_active:
        titles = [
            event.get(
                "title",
                "event",
            )
            for event in significant_active[:3]
        ]

        if len(titles) == 1:
            return (
                f"One significant event is currently active: "
                f"{titles[0]}."
            )

        return (
            "Significant events currently affecting the wider context "
            f"include {', '.join(titles)}."
        )

    if significant_recent:
        titles = [
            event.get(
                "title",
                "event",
            )
            for event in significant_recent[:3]
        ]

        if len(titles) == 1:
            return (
                f"A recent significant event may still be relevant: "
                f"{titles[0]}."
            )

        return (
            "Recent significant events include "
            f"{', '.join(titles)}."
        )

    if active_events:
        return (
            f"{len(active_events)} timeline event(s) are currently active, "
            "although none are marked as major or critical."
        )

    if recent_events:
        return (
            f"{len(recent_events)} timeline event(s) were recorded recently, "
            "but none are currently active."
        )

    return (
        "No active or recent timeline events are currently influencing "
        "Phoenix's context."
    )


def build_timeline_context(
    reference_date: Optional[Any] = None,
    recent_days: int = 30,
    significant_days: int = 60,
) -> Dict[str, Any]:
    """
    Build reusable Timeline context for Phoenix engines.

    This function is the main Timeline interface for the Morning Brief,
    Recovery Engine, Health Intelligence, Coach, and future event
    detection logic.
    """
    resolved_date = _normalise_reference_date(
        reference_date
    )

    active_events = get_active_events(
        reference_date=resolved_date
    )

    recent_events = get_recent_events(
        days=recent_days,
        reference_date=resolved_date,
    )

    significant_events = get_significant_events(
        days=significant_days,
        reference_date=resolved_date,
    )

    medical_events = [
        event
        for event in recent_events
        if event.get(
            "is_medical",
            False,
        )
    ]

    recovery_events = [
        event
        for event in recent_events
        if event.get(
            "is_recovery_related",
            False,
        )
    ]

    training_events = [
        event
        for event in recent_events
        if event.get(
            "is_training_related",
            False,
        )
    ]

    active_medical_events = [
        event
        for event in active_events
        if event.get(
            "is_medical",
            False,
        )
    ]

    active_recovery_events = [
        event
        for event in active_events
        if event.get(
            "is_recovery_related",
            False,
        )
    ]

    active_significant_events = [
        event
        for event in active_events
        if event.get(
            "is_significant",
            False,
        )
    ]

    context_events = [
        event
        for event in recent_events
        if event.get("category")
        in CONTEXT_RELEVANT_CATEGORIES
    ]

    has_recent_surgery = _contains_text(
        significant_events,
        {
            "surgery",
            "operation",
            "appendectomy",
            "appendicitis",
            "post-operative",
            "postoperative",
        },
    )

    has_recent_illness = (
        _contains_category(
            recent_events,
            {"Illness"},
        )
        or _contains_text(
            recent_events,
            {
                "illness",
                "infection",
                "virus",
                "covid",
                "flu",
                "fever",
            },
        )
    )

    has_recent_hospital_event = _contains_text(
        recent_events,
        {
            "hospital",
            "icu",
            "intensive care",
            "admission",
            "discharge",
        },
    )

    has_recent_cardiac_event = _contains_text(
        significant_events,
        {
            "cardiac arrest",
            "heart arrest",
            "asystole",
            "cpr",
            "resuscitation",
        },
    )

    has_recent_travel = _contains_category(
        recent_events,
        {"Travel"},
    )

    has_recent_work_change = _contains_category(
        recent_events,
        {"Work"},
    )

    has_recent_training_change = _contains_category(
        recent_events,
        TRAINING_CATEGORIES,
    )

    has_active_recovery_event = bool(
        active_recovery_events
    )

    recovery_phase = (
        has_active_recovery_event
        or has_recent_surgery
        or has_recent_hospital_event
        or has_recent_cardiac_event
    )

    highest_severity = _highest_severity(
        active_events
        or significant_events
        or recent_events
    )

    context_summary = _build_context_summary(
        active_events=active_events,
        recent_events=recent_events,
    )

    return {
        "reference_date": resolved_date.isoformat(),
        "recent_days": int(
            recent_days
        ),
        "significant_days": int(
            significant_days
        ),

        "active_events": active_events,
        "recent_events": recent_events,
        "significant_events": significant_events,
        "context_events": context_events,

        "medical_events": medical_events,
        "recovery_events": recovery_events,
        "training_events": training_events,

        "active_medical_events": active_medical_events,
        "active_recovery_events": active_recovery_events,
        "active_significant_events": active_significant_events,

        "active_event_count": len(
            active_events
        ),
        "recent_event_count": len(
            recent_events
        ),
        "significant_event_count": len(
            significant_events
        ),

        "highest_severity": highest_severity,

        "has_active_events": bool(
            active_events
        ),
        "has_significant_active_event": bool(
            active_significant_events
        ),
        "has_recent_medical_event": bool(
            medical_events
        ),
        "has_active_medical_event": bool(
            active_medical_events
        ),
        "has_active_recovery_event": has_active_recovery_event,

        "has_recent_surgery": has_recent_surgery,
        "has_recent_illness": has_recent_illness,
        "has_recent_hospital_event": has_recent_hospital_event,
        "has_recent_cardiac_event": has_recent_cardiac_event,
        "has_recent_travel": has_recent_travel,
        "has_recent_work_change": has_recent_work_change,
        "has_recent_training_change": has_recent_training_change,

        "recovery_phase": recovery_phase,
        "context_summary": context_summary,
    }