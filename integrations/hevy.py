import json
from pathlib import Path

import requests

from config import HEVY_API_KEY
from workout_database import save_training_sessions_from_hevy_response


BASE_URL = "https://api.hevyapp.com/v1"
WORKOUTS_URL = f"{BASE_URL}/workouts"

WORKOUTS_FILE = Path("hevy_workouts.json")


def hevy_is_connected():
    return HEVY_API_KEY is not None and len(HEVY_API_KEY.strip()) > 0


def get_headers():
    return {
        "api-key": HEVY_API_KEY,
        "accept": "application/json",
    }


def fetch_recent_workouts(page=1, page_size=10):
    if not hevy_is_connected():
        raise RuntimeError("Hevy API key not configured.")

    response = requests.get(
        WORKOUTS_URL,
        headers=get_headers(),
        params={
            "page": page,
            "pageSize": page_size,
        },
        timeout=20,
    )

    response.raise_for_status()
    return response.json()


def save_workouts_json(workouts):
    with open(WORKOUTS_FILE, "w") as f:
        json.dump(workouts, f, indent=2)


def load_workouts_json():
    if not WORKOUTS_FILE.exists():
        return None

    with open(WORKOUTS_FILE, "r") as f:
        return json.load(f)


def fetch_and_cache_workouts(page=1, page_size=10):
    workouts = fetch_recent_workouts(page=page, page_size=page_size)
    save_workouts_json(workouts)
    return workouts


def fetch_and_save_workouts(page=1, page_size=10):
    workouts = fetch_recent_workouts(page=page, page_size=page_size)

    save_workouts_json(workouts)

    import_summary = save_training_sessions_from_hevy_response(workouts)

    return import_summary