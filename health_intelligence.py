"""Phoenix Health Intelligence v2.

This module interprets the health context already assembled elsewhere in Phoenix.
It deliberately keeps the public ``build_health_intelligence`` interface stable so
existing callers do not need to change.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


UNKNOWN = "Unknown"


def build_health_intelligence(
    context: Any,
    snapshot: Any,
    recovery: Any,
    readiness: Any,
    target_date: Any = None,
) -> Dict[str, Any]:
    """Build a prioritised, human-readable interpretation of today's health.

    The function does not fetch data. It only interprets data supplied by the
    existing Phoenix engines and retains the keys expected by current pages.
    """

    target_date = str(target_date or date.today().isoformat())
    context_dict = context if isinstance(context, dict) else {}

    recovery_status = _extract_status(
        recovery,
        ["overall_label", "status", "label", "recovery_status"],
    )
    readiness_status = _extract_status(
        readiness,
        ["readiness_label", "overall_label", "status", "label", "readiness_status"],
    )
    snapshot_percent = _extract_number(
        snapshot,
        ["snapshot_percent", "completion_percent", "percent", "score"],
    )

    metabolism = _interpret_metabolism(context_dict)
    cardiovascular_status = _classify_cardiovascular(context_dict)
    sleep = _interpret_sleep(context_dict)

    overall_status = _classify_overall_health(
        recovery_status=recovery_status,
        readiness_status=readiness_status,
        snapshot_percent=snapshot_percent,
    )
    readiness_label = _classify_health_readiness(overall_status)

    positives, watch_items = _prioritise_health_areas(
        context=context_dict,
        recovery=recovery,
        readiness=readiness,
        metabolism=metabolism,
        sleep=sleep,
    )

    summary = _build_natural_summary(
        overall_status=overall_status,
        recovery_status=recovery_status,
        readiness_status=readiness_status,
        metabolism=metabolism,
        sleep=sleep,
        positives=positives,
        watch_items=watch_items,
    )

    signals = _build_signals(
        snapshot_percent=snapshot_percent,
        recovery=recovery,
        readiness=readiness,
        recovery_status=recovery_status,
        readiness_status=readiness_status,
        metabolism=metabolism,
        cardiovascular_status=cardiovascular_status,
        sleep=sleep,
        positives=positives,
        watch_items=watch_items,
    )

    recommendations = _build_recommendations(
        overall_status=overall_status,
        metabolism=metabolism,
        sleep=sleep,
        watch_items=watch_items,
    )

    return {
        "date": target_date,
        "status": overall_status,
        "readiness": readiness_label,
        "recovery_status": recovery_status,
        "readiness_status": readiness_status,
        # Keep legacy key, but use a more accurate label.
        "metabolic_state": metabolism["label"],
        "metabolic_detail": metabolism,
        "cardiovascular_status": cardiovascular_status,
        "sleep_status": sleep["label"],
        "sleep_detail": sleep,
        "snapshot_percent": snapshot_percent,
        "summary": summary,
        "positive_areas": [item["name"] for item in positives],
        "watch_areas": [item["name"] for item in watch_items],
        "signals": signals,
        "recommendations": recommendations,
        "confidence": _confidence(
            context=context_dict,
            snapshot_percent=snapshot_percent,
            recovery=recovery,
            readiness=readiness,
        ),
        "raw": {
            "snapshot": snapshot,
            "recovery": recovery,
            "readiness": readiness,
        },
    }


def _extract_status(data: Any, preferred_keys: Sequence[str], default: str = "unknown") -> str:
    if not isinstance(data, dict):
        return default
    for key in preferred_keys:
        value = data.get(key)
        if value not in (None, ""):
            return str(value).strip().lower()
    return default


def _extract_number(data: Any, preferred_keys: Sequence[str]) -> Optional[float]:
    if not isinstance(data, dict):
        return None
    for key in preferred_keys:
        value = data.get(key)
        number = _to_float(value)
        if number is not None:
            return number
    return None


def _to_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_number(context: Dict[str, Any], keys: Sequence[str]) -> Optional[float]:
    """Read a number from top-level context or common nested check-in mappings."""
    containers: List[Dict[str, Any]] = [context]
    for nested_key in (
        "today_checkin",
        "latest_checkin",
        "checkin",
        "morning_checkin",
        "latest_morning_checkin",
    ):
        nested = context.get(nested_key)
        if isinstance(nested, dict):
            containers.append(nested)

    for container in containers:
        for key in keys:
            number = _to_float(container.get(key))
            if number is not None:
                return number
    return None


def _classify_overall_health(
    recovery_status: str,
    readiness_status: str,
    snapshot_percent: Optional[float],
) -> str:
    combined = f"{recovery_status} {readiness_status}".lower()
    if any(word in combined for word in ("poor", "low", "red", "fatigued", "caution", "reduced")):
        return "needs_caution"
    if any(word in combined for word in ("moderate", "yellow", "mixed", "fair")):
        return "mixed"
    if any(word in combined for word in ("good", "green", "ready", "strong", "excellent", "high")):
        return "good"
    if snapshot_percent is not None:
        if snapshot_percent >= 80:
            return "good"
        if snapshot_percent >= 50:
            return "mixed"
        return "limited_data"
    return "unknown"


def _classify_health_readiness(overall_status: str) -> str:
    return {
        "good": "High",
        "mixed": "Moderate",
        "needs_caution": "Reduced",
        "limited_data": "Limited",
    }.get(overall_status, UNKNOWN)


def _interpret_metabolism(context: Dict[str, Any]) -> Dict[str, Any]:
    fat_pct = _first_number(
        context,
        ("fat_burn_percent", "fat_burn_pct", "fat_percent", "lumen_fat_percent"),
    )
    carb_pct = _first_number(
        context,
        ("carb_burn_percent", "carb_burn_pct", "carb_percent", "lumen_carb_percent"),
    )
    lumen_score = _first_number(context, ("lumen_score", "lumen", "metabolic_score"))

    # If only one percentage is available, derive the other when plausible.
    if fat_pct is not None and carb_pct is None and 0 <= fat_pct <= 100:
        carb_pct = 100 - fat_pct
    elif carb_pct is not None and fat_pct is None and 0 <= carb_pct <= 100:
        fat_pct = 100 - carb_pct

    if fat_pct is not None and carb_pct is not None:
        if fat_pct >= 65:
            label = "Predominantly Fat-Based"
            phrase = f"fuel use is predominantly fat-based at {fat_pct:.0f}% fat and {carb_pct:.0f}% carbohydrate"
        elif fat_pct >= 55:
            label = "Leaning Toward Fat"
            phrase = f"fuel use leans toward fat at {fat_pct:.0f}% fat and {carb_pct:.0f}% carbohydrate"
        elif carb_pct >= 65:
            label = "Predominantly Carbohydrate-Based"
            phrase = f"fuel use is predominantly carbohydrate-based at {carb_pct:.0f}% carbohydrate and {fat_pct:.0f}% fat"
        elif carb_pct >= 55:
            label = "Leaning Toward Carbohydrate"
            phrase = f"fuel use is fairly balanced but leans slightly toward carbohydrate at {carb_pct:.0f}% carbohydrate and {fat_pct:.0f}% fat"
        else:
            label = "Balanced Fuel Use"
            phrase = f"fuel use is broadly balanced at {fat_pct:.0f}% fat and {carb_pct:.0f}% carbohydrate"
        return {
            "label": label,
            "phrase": phrase,
            "fat_percent": fat_pct,
            "carb_percent": carb_pct,
            "lumen_score": lumen_score,
            "source": "percentages",
        }

    # Backward-compatible fallback when older contexts contain only the score.
    if lumen_score is not None:
        if lumen_score <= 2:
            label, phrase = "Leaning Toward Fat", "Lumen suggests a stronger fat-use state"
        elif lumen_score == 3:
            label, phrase = "Balanced Fuel Use", "Lumen suggests a broadly balanced fuel mix"
        elif lumen_score == 4:
            label, phrase = "Leaning Toward Carbohydrate", "Lumen suggests fuel use is leaning toward carbohydrate"
        else:
            label, phrase = "Predominantly Carbohydrate-Based", "Lumen suggests a strongly carbohydrate-based state"
        return {
            "label": label,
            "phrase": phrase,
            "fat_percent": None,
            "carb_percent": None,
            "lumen_score": lumen_score,
            "source": "score",
        }

    return {
        "label": UNKNOWN,
        "phrase": "",
        "fat_percent": None,
        "carb_percent": None,
        "lumen_score": None,
        "source": "missing",
    }


def _classify_cardiovascular(context: Dict[str, Any]) -> str:
    resting_hr = _first_number(context, ("resting_hr", "resting_heart_rate", "rhr"))
    hrv = _first_number(context, ("hrv", "hrv_ms", "heart_rate_variability"))
    if resting_hr is None and hrv is None:
        return UNKNOWN
    return "Available"


def _interpret_sleep(context: Dict[str, Any]) -> Dict[str, Any]:
    total = _first_number(context, ("sleep_total", "total_sleep", "sleep_hours", "sleep_duration"))
    rem = _first_number(context, ("rem_sleep", "sleep_rem", "rem_hours"))
    awake = _first_number(context, ("awake_time", "sleep_awake", "awake_hours"))

    if total is None:
        return {"label": UNKNOWN, "phrase": "", "total": None, "rem": rem, "awake": awake}
    if total >= 7.5:
        label = "Good"
        phrase = f"sleep duration was supportive at {total:.1f} hours"
    elif total >= 6.5:
        label = "Acceptable"
        phrase = f"sleep was adequate rather than outstanding at {total:.1f} hours"
    elif total >= 5.5:
        label = "Low"
        phrase = f"sleep was below your preferred range at {total:.1f} hours"
    else:
        label = "Very Low"
        phrase = f"sleep was notably short at {total:.1f} hours"
    return {"label": label, "phrase": phrase, "total": total, "rem": rem, "awake": awake}


def _normalise_reasoning(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []
    return [str(item).strip() for item in items if str(item).strip()]


def _contains_any(text: str, words: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in words)


def _prioritise_health_areas(
    context: Dict[str, Any],
    recovery: Any,
    readiness: Any,
    metabolism: Dict[str, Any],
    sleep: Dict[str, Any],
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Group related metrics and select distinct positive/watch areas."""
    positive: List[Dict[str, str]] = []
    watch: List[Dict[str, str]] = []

    recovery_reasoning = _normalise_reasoning(recovery.get("reasoning", [])) if isinstance(recovery, dict) else []
    readiness_reasoning = _normalise_reasoning(readiness.get("reasoning", [])) if isinstance(readiness, dict) else []
    all_reasoning = recovery_reasoning + readiness_reasoning

    groups = {
        "Recovery": ("recovery", "recovering", "fatigue", "strain"),
        "Cardiovascular recovery": ("hrv", "resting heart", "rhr", "heart rate"),
        "Sleep": ("sleep", "rem", "awake", "deep sleep"),
        "Body composition": ("body fat", "fat mass", "fat-free", "weight", "muscle"),
        "Blood pressure": ("blood pressure", "systolic", "diastolic"),
        "Temperature": ("temperature", "wrist temp"),
        "Oxygen and respiration": ("spo2", "oxygen", "respiratory", "breathing"),
    }
    positive_words = ("good", "improv", "favour", "support", "strong", "stable", "normal", "higher", "lower than baseline")
    watch_words = ("low", "high", "worse", "declin", "unfavour", "elevat", "below", "above", "watch", "caution", "poor")

    for group_name, keywords in groups.items():
        matching = [line for line in all_reasoning if _contains_any(line, keywords)]
        if not matching:
            continue
        joined = " ".join(matching)
        if _contains_any(joined, watch_words):
            watch.append({"name": group_name, "detail": matching[0]})
        elif _contains_any(joined, positive_words):
            positive.append({"name": group_name, "detail": matching[0]})

    # Add direct sleep interpretation when reasoning does not already cover it.
    if sleep["label"] in ("Low", "Very Low") and not any(item["name"] == "Sleep" for item in watch):
        watch.append({"name": "Sleep", "detail": sleep["phrase"]})
    elif sleep["label"] == "Good" and not any(item["name"] == "Sleep" for item in positive):
        positive.append({"name": "Sleep", "detail": sleep["phrase"]})

    # A carb-leaning morning is context, not automatically a health problem.
    # Mention it as a watch item only when strongly carbohydrate based.
    if metabolism["label"] == "Predominantly Carbohydrate-Based":
        watch.append({"name": "Fuel use", "detail": metabolism["phrase"]})

    # De-duplicate by category while preserving priority/order.
    positive = _dedupe_areas(positive)[:3]
    watch = _dedupe_areas(watch)[:3]
    return positive, watch


def _dedupe_areas(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    result = []
    for item in items:
        name = item.get("name", "")
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(item)
    return result


def _friendly_status(status: str) -> str:
    return status.replace("_", " ").strip().lower()


def _join_names(items: Sequence[Dict[str, str]]) -> str:
    names = [item["name"] for item in items if item.get("name")]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def _build_natural_summary(
    overall_status: str,
    recovery_status: str,
    readiness_status: str,
    metabolism: Dict[str, Any],
    sleep: Dict[str, Any],
    positives: Sequence[Dict[str, str]],
    watch_items: Sequence[Dict[str, str]],
) -> str:
    if overall_status == "good":
        opening = "Today's health picture is broadly supportive."
    elif overall_status == "mixed":
        opening = "Today's health picture is fairly steady rather than outstanding."
    elif overall_status == "needs_caution":
        opening = "Today's health picture calls for a little caution."
    elif overall_status == "limited_data":
        opening = "Phoenix has only a partial health picture today."
    else:
        opening = "Phoenix does not yet have a clear health read for today."

    status_parts = []
    if recovery_status != "unknown":
        status_parts.append(f"recovery is {_friendly_status(recovery_status)}")
    if readiness_status != "unknown":
        status_parts.append(f"readiness is {_friendly_status(readiness_status)}")
    if status_parts:
        opening += " " + " and ".join(status_parts).capitalize() + "."

    sentences = [opening]

    if metabolism["phrase"]:
        sentences.append(f"Your {metabolism['phrase']}.")
    if sleep["phrase"]:
        sentences.append(f"Overnight, {sleep['phrase']}.")

    positive_names = _join_names(positives)
    watch_names = _join_names(watch_items)
    if positive_names:
        sentences.append(f"The clearest positives are {positive_names}.")
    if watch_names:
        sentences.append(f"The specific areas Phoenix would keep watching are {watch_names}.")
    elif positive_names:
        sentences.append("No distinct health area stands out as needing extra attention from the available signals.")

    if overall_status == "good":
        bottom_line = "Overall, the stronger signals support a normal day, provided your workout load and how you feel agree."
    elif overall_status == "mixed":
        bottom_line = "Overall, this looks more like a controlled, sensible day than one to force."
    elif overall_status == "needs_caution":
        bottom_line = "Overall, recovery should take priority over adding unnecessary strain today."
    elif overall_status == "limited_data":
        bottom_line = "Overall, Phoenix would avoid making a strong recommendation until the missing data is available."
    else:
        bottom_line = "Overall, use your subjective check-in and recent training context cautiously until the picture is clearer."
    sentences.append(bottom_line)
    return " ".join(sentence for sentence in sentences if sentence)


def _build_signals(
    snapshot_percent: Optional[float],
    recovery: Any,
    readiness: Any,
    recovery_status: str,
    readiness_status: str,
    metabolism: Dict[str, Any],
    cardiovascular_status: str,
    sleep: Dict[str, Any],
    positives: Sequence[Dict[str, str]],
    watch_items: Sequence[Dict[str, str]],
) -> List[str]:
    signals: List[str] = []
    if snapshot_percent is not None:
        signals.append(f"Morning snapshot is {snapshot_percent:.0f}% complete.")
    if recovery_status != "unknown":
        signals.append(f"Recovery is classified as {recovery_status}.")
    if readiness_status != "unknown":
        signals.append(f"Readiness is classified as {readiness_status}.")
    if metabolism["label"] != UNKNOWN:
        signals.append(f"Metabolic interpretation: {metabolism['phrase']}.")
    if cardiovascular_status != UNKNOWN:
        signals.append("Cardiovascular signals are available for interpretation.")
    if sleep["label"] != UNKNOWN:
        signals.append(f"Sleep interpretation: {sleep['phrase']}.")
    for item in positives:
        signals.append(f"Positive area — {item['name']}: {item['detail']}")
    for item in watch_items:
        signals.append(f"Watch area — {item['name']}: {item['detail']}")

    for name, data in (("recovery", recovery), ("readiness", readiness)):
        if isinstance(data, dict) and data.get("error"):
            signals.append(f"{name} engine returned an error: {data['error']}")
    if not signals:
        signals.append("Health Intelligence could not find enough health data yet.")
    return signals


def _build_recommendations(
    overall_status: str,
    metabolism: Dict[str, Any],
    sleep: Dict[str, Any],
    watch_items: Sequence[Dict[str, str]],
) -> List[str]:
    recommendations: List[str] = []
    if overall_status == "good":
        recommendations.append("Health signals are supportive today. Normal training is reasonable if workout load also supports it.")
    elif overall_status == "mixed":
        recommendations.append("Health signals are mixed today. Controlled aerobic work is preferable to forcing hard intensity.")
    elif overall_status == "needs_caution":
        recommendations.append("Health signals suggest caution today. Keep training easy and prioritise recovery.")
    elif overall_status == "limited_data":
        recommendations.append("Phoenix has limited health data today. Use the subjective check-in and recent training load to guide decisions.")
    else:
        recommendations.append("Phoenix does not yet have a clear health read. Avoid an aggressive training decision from incomplete data.")

    if sleep["label"] in ("Low", "Very Low"):
        recommendations.append("Sleep was short, so avoid unnecessary intensity unless you feel unusually good.")
    if metabolism["label"] in ("Leaning Toward Carbohydrate", "Predominantly Carbohydrate-Based"):
        recommendations.append("Today's Lumen reading leans toward carbohydrate use; treat this mainly as fuel-context and fuel appropriately if training.")
    if watch_items:
        recommendations.append(f"Keep an eye on {_join_names(watch_items)} in the next health review.")
    return recommendations


def _confidence(
    context: Dict[str, Any],
    snapshot_percent: Optional[float],
    recovery: Any,
    readiness: Any,
) -> int:
    score = 40
    if any(isinstance(context.get(key), dict) for key in ("today_checkin", "latest_checkin", "checkin")):
        score += 10
    if _first_number(context, ("hrv", "hrv_ms", "heart_rate_variability")) is not None:
        score += 10
    if _first_number(context, ("resting_hr", "resting_heart_rate", "rhr")) is not None:
        score += 10
    if _first_number(context, ("sleep_total", "total_sleep", "sleep_hours", "sleep_duration")) is not None:
        score += 10
    if _first_number(context, ("lumen_score", "fat_burn_percent", "carb_burn_percent")) is not None:
        score += 5
    if snapshot_percent is not None:
        score += 5
    if isinstance(recovery, dict) and not recovery.get("error"):
        score += 5
    if isinstance(readiness, dict) and not readiness.get("error"):
        score += 5
    return min(score, 95)
