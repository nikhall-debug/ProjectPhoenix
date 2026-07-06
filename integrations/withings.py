from urllib.parse import urlencode
import json
from pathlib import Path

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


def get_latest_weight():
    tokens = load_tokens()

    if tokens is None:
        return None

    access_token = tokens["body"]["access_token"]

    response = requests.get(
        MEASURE_URL,
        params={
            "action": "getmeas",
            "access_token": access_token,
            "category": 1,
            "meastype": 1,
            "limit": 1,
        },
        timeout=20,
    )

    response.raise_for_status()
    data = response.json()

    measure = data["body"]["measuregrps"][0]["measures"][0]
    weight_kg = measure["value"] * (10 ** measure["unit"])

    return weight_kg