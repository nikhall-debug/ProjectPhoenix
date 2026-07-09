from urllib.parse import urlencode
import json
from pathlib import Path
from datetime import datetime

import requests
import streamlit as st

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


def refresh_withings_tokens():
    tokens = load_tokens()

    if not token_response_is_valid(tokens):
        return None

    refresh_token = tokens["body"]["refresh_token"]

    payload = {
        "action": "requesttoken",
        "grant_type": "refresh_token",
        "client_id": WITHINGS_CLIENT_ID,
        "client_secret": WITHINGS_CLIENT_SECRET,
        "refresh_token": refresh_token,
    }

    response = requests.post(TOKEN_URL, data=payload, timeout=20)
    response.raise_for_status()

    new_tokens = response.json()

    if token_response_is_valid(new_tokens):
        save_tokens(new_tokens)
        return new_tokens

    return None


def token_response_is_valid(token_response):
    return (
        isinstance(token_response, dict)
        and "body" in token_response
        and isinstance(token_response["body"], dict)
        and "access_token" in token_response["body"]
        and "refresh_token" in token_response["body"]
    )


def save_tokens(token_response):
    if not token_response_is_valid(token_response):
        raise ValueError(f"Invalid Withings token response: {token_response}")

    with open(TOKEN_FILE, "w") as f:
        json.dump(token_response, f, indent=2)


def load_tokens():
    if not TOKEN_FILE.exists():
        return None

    with open(TOKEN_FILE, "r") as f:
        return json.load(f)


def stored_tokens_are_valid():
    tokens = load_tokens()
    return token_response_is_valid(tokens)


def withings_is_connected():
    return stored_tokens_are_valid()


def normalize_withings_value(value, unit):
    return value * (10 ** unit)


def fetch_withings_measurements(access_token, limit=100, startdate=None):
    payload = {
        "action": "getmeas",
        "category": 1,
        "limit": limit,
    }

    if startdate is not None:
        payload["startdate"] = startdate

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    response = requests.post(
        MEASURE_URL,
        data=payload,
        headers=headers,
        timeout=20,
    )

    response.raise_for_status()
    return response.json()


def parse_withings_measurements(data):
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

            measurements.append(
                {
                    "source": "withings",
                    "metric_type": metric_type,
                    "value": value,
                    "unit": unit,
                    "measured_at": measured_at,
                    "raw_type": raw_type,
                    "raw_data": json.dumps(measure),
                }
            )

    return measurements


def get_withings_measurements(limit=100, startdate=None):
    tokens = load_tokens()

    if not token_response_is_valid(tokens):
        st.warning("Withings tokens are missing or invalid.")
        return []

    access_token = tokens["body"]["access_token"]

    data = fetch_withings_measurements(
        access_token=access_token,
        limit=limit,
        startdate=startdate,
    )

    if data.get("status") == 401:
        st.warning("Withings access token expired. Refreshing token...")

        refreshed_tokens = refresh_withings_tokens()

        if not token_response_is_valid(refreshed_tokens):
            st.error("Could not refresh Withings token. Please reconnect Withings.")
            return []

        access_token = refreshed_tokens["body"]["access_token"]

        data = fetch_withings_measurements(
            access_token=access_token,
            limit=limit,
            startdate=startdate,
        )


    if data.get("status") != 0:
        st.error("Withings API returned an error.")
        st.write(data)
        return []

    return parse_withings_measurements(data)


def get_latest_weight():
    measurements = get_withings_measurements(limit=10)

    for measurement in measurements:
        if measurement["metric_type"] == "weight_kg":
            return measurement["value"]

    return None