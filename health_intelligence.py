from datetime import date

from athlete_context import build_athlete_context
from morning_brief import build_morning_brief
from readiness_engine import build_readiness_profile
from recovery_engine import build_recovery_profile
from snapshot import build_morning_snapshot


def build_health_intelligence(target_date=None):
    if target_date is None:
        target_date = date.today().isoformat()
    else:
        target_date = str(target_date)

    context = _safe_call(build_athlete_context)
    snapshot = _safe_call(build_morning_snapshot)

    baselines = context.get("baselines", {}) if isinstance(context, dict) else {}

    recovery = _safe_call(build_recovery_profile, context)

    readiness = _safe_call(
        build_readiness_profile,
        context,
        recovery,
    )

    morning_brief = _safe_call(
        build_morning_brief,
        context,
        recovery,
        baselines,
    )

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
        ["snapshot_percent", "completion_percent", "percent"],
    )

    overall_status = _classify_overall_health(
        recovery_status=recovery_status,
        readiness_status=readiness_status,
        snapshot_percent=snapshot_percent,
    )

    evidence = _build_evidence(
        snapshot_percent=snapshot_percent,
        recovery=recovery,
        readiness=readiness,
        morning_brief=morning_brief,
        recovery_status=recovery_status,
        readiness_status=readiness_status,
    )

    narrative = _build_narrative(
        overall_status=overall_status,
        recovery_status=recovery_status,
        readiness_status=readiness_status,
        snapshot_percent=snapshot_percent,
    )

    return {
        "date": target_date,
        "overall_status": overall_status,
        "recovery_status": recovery_status,
        "readiness_status": readiness_status,
        "snapshot_percent": snapshot_percent,
        "narrative": narrative,
        "evidence": evidence,
        "raw": {
            "context": context,
            "snapshot": snapshot,
            "recovery": recovery,
            "readiness": readiness,
            "morning_brief": morning_brief,
        },
    }


def _safe_call(func, *args):
    try:
        return func(*args)
    except Exception as error:
        return {"error": str(error)}


def _extract_status(data, preferred_keys, default="unknown"):
    if not isinstance(data, dict):
        return default

    for key in preferred_keys:
        value = data.get(key)
        if value is not None:
            return str(value).lower()

    return default


def _extract_number(data, preferred_keys):
    if not isinstance(data, dict):
        return None

    for key in preferred_keys:
        value = data.get(key)

        if value is None:
            continue

        try:
            return float(value)
        except (TypeError, ValueError):
            continue

    return None


def _classify_overall_health(recovery_status, readiness_status, snapshot_percent):
    combined = f"{recovery_status} {readiness_status}".lower()

    if any(word in combined for word in ["poor", "low", "red", "fatigued", "caution"]):
        return "needs_caution"

    if any(word in combined for word in ["moderate", "yellow", "mixed"]):
        return "mixed"

    if any(word in combined for word in ["good", "green", "ready", "strong"]):
        return "good"

    if snapshot_percent is not None:
        if snapshot_percent >= 80:
            return "good"
        if snapshot_percent >= 50:
            return "mixed"
        return "limited_data"

    return "unknown"


def _build_evidence(
    snapshot_percent,
    recovery,
    readiness,
    morning_brief,
    recovery_status,
    readiness_status,
):
    evidence = []

    if snapshot_percent is not None:
        evidence.append(f"Morning snapshot is {snapshot_percent:.0f}% complete.")

    if recovery_status != "unknown":
        evidence.append(f"Recovery is classified as {recovery_status}.")

    if readiness_status != "unknown":
        evidence.append(f"Readiness is classified as {readiness_status}.")

    if isinstance(recovery, dict):
        for item in recovery.get("reasoning", [])[:5]:
            evidence.append(item)

    if isinstance(readiness, dict):
        for item in readiness.get("reasoning", [])[:5]:
            evidence.append(item)

    brief_text = _extract_brief_text(morning_brief)
    if brief_text:
        evidence.append(f"Morning brief: {brief_text}")

    for name, data in [
        ("recovery", recovery),
        ("readiness", readiness),
        ("morning brief", morning_brief),
    ]:
        if isinstance(data, dict) and data.get("error"):
            evidence.append(f"{name} engine returned an error: {data['error']}")

    if not evidence:
        evidence.append("Health Intelligence could not find enough health data yet.")

    return evidence


def _extract_brief_text(morning_brief):
    if isinstance(morning_brief, str):
        return morning_brief

    if not isinstance(morning_brief, dict):
        return None

    for key in ["summary", "brief", "narrative", "message"]:
        value = morning_brief.get(key)
        if value:
            return str(value)

    return None


def _build_narrative(
    overall_status,
    recovery_status,
    readiness_status,
    snapshot_percent,
):
    if overall_status == "good":
        opening = "Health signals look broadly supportive today."
    elif overall_status == "mixed":
        opening = "Health signals look mixed today."
    elif overall_status == "needs_caution":
        opening = "Health signals suggest some caution today."
    elif overall_status == "limited_data":
        opening = "Phoenix has limited health data for today."
    else:
        opening = "Phoenix does not yet have a clear health read for today."

    details = []

    if recovery_status != "unknown":
        details.append(f"Recovery is {recovery_status}.")

    if readiness_status != "unknown":
        details.append(f"Readiness is {readiness_status}.")

    if snapshot_percent is not None:
        details.append(f"The morning snapshot is {snapshot_percent:.0f}% complete.")

    return " ".join([opening] + details)