import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from config import XERT_USERNAME, XERT_PASSWORD
from workout_database import save_training_session_from_xert_activity


TOKEN_URL = "https://www.xertonline.com/oauth/token"
TRAINING_INFO_URL = "https://www.xertonline.com/oauth/training_info"
ACTIVITY_LIST_URL = "https://www.xertonline.com/oauth/activity"
ACTIVITY_DETAIL_URL = "https://www.xertonline.com/oauth/activity"

TOKEN_FILE = Path("xert_tokens.json")
STATUS_FILE = Path("xert_status.json")
ACTIVITIES_FILE = Path("xert_activities.json")


def get_xert_tokens():
    response = requests.post(
        TOKEN_URL,
        auth=("xert_public", "xert_public"),
        data={
            "grant_type": "password",
            "username": XERT_USERNAME,
            "password": XERT_PASSWORD,
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def save_xert_tokens(token_response):
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_response, f, indent=2)


def load_xert_tokens():
    if not TOKEN_FILE.exists():
        return None

    with open(TOKEN_FILE, "r") as f:
        return json.load(f)


def xert_is_connected():
    tokens = load_xert_tokens()
    return isinstance(tokens, dict) and "access_token" in tokens


def connect_xert():
    token_response = get_xert_tokens()
    save_xert_tokens(token_response)
    return token_response


def get_auth_headers():
    if not xert_is_connected():
        connect_xert()

    tokens = load_xert_tokens()
    access_token = tokens["access_token"]

    return {
        "Authorization": f"Bearer {access_token}",
    }


def get_xert_training_info():
    response = requests.get(
        TRAINING_INFO_URL,
        headers=get_auth_headers(),
        params={
            "format": "zwo",
        },
        timeout=20,
    )

    response.raise_for_status()
    return response.json()


def save_xert_status(status_response):
    with open(STATUS_FILE, "w") as f:
        json.dump(status_response, f, indent=2)


def load_xert_status():
    if not STATUS_FILE.exists():
        return None

    with open(STATUS_FILE, "r") as f:
        return json.load(f)


def fetch_and_save_xert_status():
    status = get_xert_training_info()
    save_xert_status(status)
    return status


def get_unix_timestamp(dt):
    return int(dt.timestamp())


def fetch_xert_activity_list(days=30):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    response = requests.get(
        ACTIVITY_LIST_URL,
        headers=get_auth_headers(),
        params={
            "from": get_unix_timestamp(start),
            "to": get_unix_timestamp(end),
        },
        timeout=20,
    )

    response.raise_for_status()
    return response.json()


def fetch_xert_activity_detail(activity_path, include_session_data=0):
    response = requests.get(
        f"{ACTIVITY_DETAIL_URL}/{activity_path}",
        headers=get_auth_headers(),
        params={
            "include_session_data": include_session_data,
        },
        timeout=20,
    )

    response.raise_for_status()
    return response.json()


def save_xert_activities_json(activity_response):
    with open(ACTIVITIES_FILE, "w") as f:
        json.dump(activity_response, f, indent=2)


def load_xert_activities_json():
    if not ACTIVITIES_FILE.exists():
        return None

    with open(ACTIVITIES_FILE, "r") as f:
        return json.load(f)


def fetch_and_cache_xert_activity_list(days=30):
    activities = fetch_xert_activity_list(days=days)
    save_xert_activities_json(activities)
    return activities


def is_cycling_activity(activity):
    activity_type = (activity.get("activity_type") or "").lower()

    return "cycling" in activity_type


def fetch_and_save_xert_activities(days=60, limit=None):
    activity_response = fetch_xert_activity_list(days=days)
    save_xert_activities_json(activity_response)

    activities = activity_response.get("activities", [])

    imported = 0
    duplicates = 0
    skipped = 0
    apple_duplicates_removed = 0
    errors = []

    cycling_activities = [activity for activity in activities if is_cycling_activity(activity)]

    if limit is not None:
        cycling_activities = cycling_activities[:limit]

    for activity in cycling_activities:
        path = activity.get("path")

        if not path:
            skipped += 1
            continue

        try:
            detail = fetch_xert_activity_detail(path, include_session_data=0)
            detail["path"] = path

            result = save_training_session_from_xert_activity(detail)

            if result["imported"]:
                imported += 1
            else:
                duplicates += 1

            apple_duplicates_removed += result.get("removed_apple_duplicates", 0)

        except Exception as error:
            errors.append(f"{path}: {error}")

    skipped += len(activities) - len(cycling_activities)

    return {
        "imported": imported,
        "duplicates": duplicates,
        "skipped": skipped,
        "apple_duplicates_removed": apple_duplicates_removed,
        "total_seen": len(activities),
        "cycling_seen": len(cycling_activities),
        "error": "; ".join(errors) if errors else None,
    }