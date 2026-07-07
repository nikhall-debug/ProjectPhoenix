from urllib.parse import urlencode
import json
from pathlib import Path
from datetime import datetime

import requests

from config import (
    WITHINGS_CLIENT_ID,
    WITHINGS_CLIENT_SECRET,
    WITHINGS_REDIRECT_URI,
)

AUTH_URL = "https://account.withings.com/oauth2_user/authorize2"
TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"
MEASURE_URL = "https://wbsapi.withings.net/measure"

TOKEN_FILE = Path("withings_tokens.json")


WITHINGS_MEASURE_TYPES = {
    1: ("weight_kg", "kg"),
    5: ("fat_free_mass_kg", "kg"),
    6: ("fat_percent", "%"),
    8: ("fat_mass_kg", "kg"),
    9: ("diastolic_bp", "mmHg"),
    10: ("systolic_bp", "mmHg"),
    11: ("heart_rate", "bpm"),
    76: ("muscle_mass_kg", "kg"),
    77: ("hydration_kg", "kg"),
    88: ("bone_mass_kg", "kg"),
    91: ("pulse_wave_velocity", "m/s"),
}


def build_authorization_url():
    params = {
        "response_type": "code",
        "client_id": WITHINGS_CLIENT_ID,
        "scope": "user.info,user.metrics",
        "redirect_uri": WITHINGS_REDIRECT_URI,
        "state": "phoenix-test",
    }
    return AUTH_URL + "?" + urlencode(params)


def exchange_code_for_tokens(code):
    payload = {
        "action": "requesttoken",
        "grant_type": "authorization_code",
        "client_id": WITHINGS_CLIENT_ID,
        "client_secret": WITHINGS_CLIENT_SECRET,
        "code": code,
        "redirect_uri": WITHINGS_REDIRECT_URI,
    }

    response = requests.post(TOKEN_URL, data=payload, timeout=20)
    response.raise_for_status()
    return response.json()


def save_tokens(token_response):
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_response, f, indent=2)


def load_tokens():
    if not TOKEN_FILE.exists():
        return None

    with open(TOKEN_FILE, "r") as f:
        return json.load(f)


def withings_is_connected():
    return load_tokens() is not None


def normalize_withings_value(value, unit):
    return value * (10 ** unit)


def get_withings_measurements(limit=100, startdate=None):
    tokens = load_tokens()

    if tokens is None:
        return []

    access_token = tokens["body"]["access_token"]

    params = {
        "action": "getmeas",
        "access_token": access_token,
        "category": 1,
        "limit": limit,
    }

    if startdate is not None:
        params["startdate"] = startdate

    response = requests.get(
        MEASURE_URL,
        params=params,
        timeout=20,
    )

    response.raise_for_status()
    data = response.json()

    measurements = []

    measure_groups = data.get("body", {}).get("measuregrps", [])

    for group in measure_groups:
        measured_at = datetime.fromtimestamp(group["date"]).isoformat(timespec="seconds")

        for measure in group.get("measures", []):
            raw_type = measure.get("type")

            if raw_type not in WITHINGS_MEASURE_TYPES:
                continue

            metric_type, unit = WITHINGS_MEASURE_TYPES[raw_type]

            value = normalize_withings_value(
                measure["value"],
                measure["unit"],
            )

            measurements.append({
                "source": "withings",
                "metric_type": metric_type,
                "value": value,
                "unit": unit,
                "measured_at": measured_at,
                "raw_type": raw_type,
                "raw_data": json.dumps(measure),
            })

    return measurements


def get_latest_weight():
    measurements = get_withings_measurements(limit=10)

    for measurement in measurements:
        if measurement["metric_type"] == "weight_kg":
            return measurement["value"]

    return None