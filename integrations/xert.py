from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from config import XERT_PASSWORD, XERT_USERNAME
from workout_staging import stage_training_session_from_xert_activity


TOKEN_URL = "https://www.xertonline.com/oauth/token"
TRAINING_INFO_URL = "https://www.xertonline.com/oauth/training_info"
ACTIVITY_URL = "https://www.xertonline.com/oauth/activity"

TOKEN_FILE = Path("xert_tokens.json")
STATUS_FILE = Path("xert_status.json")
ACTIVITIES_FILE = Path("xert_activities.json")


def get_xert_tokens() -> Dict[str, Any]:
    response = requests.post(
        TOKEN_URL,
        auth=("xert_public", "xert_public"),
        data={
            "grant_type": "password",
            "username": XERT_USERNAME,
            "password": XERT_PASSWORD,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def save_xert_tokens(token_response: Dict[str, Any]) -> None:
    TOKEN_FILE.write_text(json.dumps(token_response, indent=2))


def load_xert_tokens() -> Optional[Dict[str, Any]]:
    if not TOKEN_FILE.exists():
        return None
    try:
        value = json.loads(TOKEN_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def clear_xert_tokens() -> None:
    try:
        TOKEN_FILE.unlink()
    except FileNotFoundError:
        pass


def xert_is_connected() -> bool:
    tokens = load_xert_tokens()
    return bool(tokens and tokens.get("access_token"))


def connect_xert() -> Dict[str, Any]:
    tokens = get_xert_tokens()
    save_xert_tokens(tokens)
    return tokens


def get_auth_headers() -> Dict[str, str]:
    if not xert_is_connected():
        connect_xert()

    tokens = load_xert_tokens() or {}
    access_token = tokens.get("access_token")
    if not access_token:
        raise RuntimeError("Xert did not provide an access token.")

    return {"Authorization": f"Bearer {access_token}"}


def _xert_get(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    retry_auth: bool = True,
) -> requests.Response:
    response = requests.get(
        url,
        headers=get_auth_headers(),
        params=params,
        timeout=45,
    )

    if response.status_code == 401 and retry_auth:
        clear_xert_tokens()
        connect_xert()
        return _xert_get(url, params=params, retry_auth=False)

    response.raise_for_status()
    return response


def get_xert_training_info() -> Dict[str, Any]:
    return _xert_get(
        TRAINING_INFO_URL,
        params={"format": "zwo"},
    ).json()


def save_xert_status(status_response: Dict[str, Any]) -> None:
    STATUS_FILE.write_text(json.dumps(status_response, indent=2))


def load_xert_status() -> Optional[Dict[str, Any]]:
    if not STATUS_FILE.exists():
        return None
    try:
        return json.loads(STATUS_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def fetch_and_save_xert_status() -> Dict[str, Any]:
    status = get_xert_training_info()
    save_xert_status(status)
    return status


def get_unix_timestamp(value: datetime) -> int:
    return int(value.timestamp())


def fetch_xert_activity_list(days: int = 30) -> Dict[str, Any]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    return _xert_get(
        ACTIVITY_URL,
        params={
            "from": get_unix_timestamp(start),
            "to": get_unix_timestamp(end),
        },
    ).json()


def fetch_xert_activity_detail(
    activity_path: str,
    include_session_data: int = 1,
) -> Dict[str, Any]:
    safe_path = str(activity_path).strip("/")
    return _xert_get(
        f"{ACTIVITY_URL}/{safe_path}",
        params={"include_session_data": int(include_session_data)},
    ).json()


def save_xert_activities_json(activity_response: Dict[str, Any]) -> None:
    ACTIVITIES_FILE.write_text(json.dumps(activity_response, indent=2))


def load_xert_activities_json() -> Optional[Dict[str, Any]]:
    if not ACTIVITIES_FILE.exists():
        return None
    try:
        return json.loads(ACTIVITIES_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def fetch_and_cache_xert_activity_list(days: int = 30) -> Dict[str, Any]:
    activities = fetch_xert_activity_list(days=days)
    save_xert_activities_json(activities)
    return activities


def is_cycling_activity(activity: Dict[str, Any]) -> bool:
    activity_type = str(
        activity.get("activity_type")
        or activity.get("sport")
        or activity.get("type")
        or ""
    ).lower()
    return "cycl" in activity_type or "bike" in activity_type


def _activity_path(activity: Dict[str, Any]) -> Optional[str]:
    for key in ("path", "activity_id", "id"):
        value = activity.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _combine_activity(
    list_item: Dict[str, Any],
    detail: Dict[str, Any],
    path: str,
) -> Dict[str, Any]:
    combined = dict(list_item)
    combined.update(detail)
    combined["path"] = path

    # Keep the list summary if the detail response omits it.
    if not combined.get("summary") and list_item.get("summary"):
        combined["summary"] = list_item["summary"]

    # Preserve both forms for diagnostics.
    combined["_xert_list_item"] = list_item
    combined["_xert_detail_loaded"] = True
    return combined


def fetch_and_stage_xert_activities(
    days: int = 60,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    activity_response = fetch_xert_activity_list(days=days)
    save_xert_activities_json(activity_response)

    activities = activity_response.get("activities", [])
    if not isinstance(activities, list):
        activities = []

    cycling_activities = [
        activity for activity in activities
        if isinstance(activity, dict) and is_cycling_activity(activity)
    ]

    if limit is not None:
        cycling_activities = cycling_activities[: int(limit)]

    staged = 0
    updated = 0
    duplicates = 0
    skipped = 0
    detailed = 0
    errors = []

    for activity in cycling_activities:
        path = _activity_path(activity)
        if not path:
            skipped += 1
            continue

        try:
            detail = fetch_xert_activity_detail(
                path,
                include_session_data=1,
            )
            combined = _combine_activity(activity, detail, path)
            result = stage_training_session_from_xert_activity(combined)
            detailed += 1

            if result.get("updated"):
                updated += 1
            elif result.get("staged"):
                staged += 1
            else:
                duplicates += 1

        except Exception as error:
            errors.append(f"{path}: {error}")

    skipped += max(len(activities) - len(cycling_activities), 0)

    return {
        "staged": staged,
        "updated": updated,
        "duplicates": duplicates,
        "skipped": skipped,
        "detailed": detailed,
        "total_seen": len(activities),
        "cycling_seen": len(cycling_activities),
        "error": "; ".join(errors) if errors else None,
    }


def fetch_and_save_xert_activities(
    days: int = 60,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    return fetch_and_stage_xert_activities(days=days, limit=limit)
