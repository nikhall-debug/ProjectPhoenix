from urllib.parse import urlencode

from config import WITHINGS_CLIENT_ID, WITHINGS_REDIRECT_URI


def build_authorization_url():
    params = {
        "response_type": "code",
        "client_id": WITHINGS_CLIENT_ID,
        "scope": "user.info,user.metrics",
        "redirect_uri": WITHINGS_REDIRECT_URI,
        "state": "phoenix-test",
    }

    return "https://account.withings.com/oauth2_user/authorize2?" + urlencode(params)