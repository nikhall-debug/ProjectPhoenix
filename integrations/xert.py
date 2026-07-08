import json
from pathlib import Path

import requests

from config import XERT_USERNAME, XERT_PASSWORD


TOKEN_URL = "https://www.xertonline.com/oauth/token"
TRAINING_INFO_URL = "https://www.xertonline.com/oauth/training_info"

TOKEN_FILE = Path("xert_tokens.json")
STATUS_FILE = Path("xert_status.json")


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


def get_xert_training_info():
    tokens = load_xert_tokens()

    if not xert_is_connected():
        return None

    access_token = tokens["access_token"]

    response = requests.get(
        TRAINING_INFO_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
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