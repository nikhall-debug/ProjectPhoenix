from datetime import date


def build_withings_freshness(latest_date):
    today = date.today().isoformat()

    if latest_date is None:
        return {
            "status": "missing",
            "message": "No Withings data received yet.",
        }

    if latest_date == today:
        return {
            "status": "current",
            "message": f"Withings updated today: {latest_date}",
        }

    return {
        "status": "stale",
        "message": f"Last Withings update: {latest_date}",
    }


def build_apple_health_freshness(latest_date):
    today = date.today().isoformat()

    if latest_date is None:
        return {
            "status": "missing",
            "message": "No Apple Health data received yet.",
        }

    if latest_date == today:
        return {
            "status": "current",
            "message": f"Apple Health updated today: {latest_date}",
        }

    return {
        "status": "stale",
        "message": f"Last Apple Health update: {latest_date}",
    }