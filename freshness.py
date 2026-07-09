from datetime import datetime, date


def format_latest_time(latest_time):
    if latest_time is None:
        return None

    dt = datetime.fromisoformat(latest_time)
    return dt, dt.strftime("%d %b %Y • %H:%M")


def build_withings_freshness(latest_time):
    parsed = format_latest_time(latest_time)

    if parsed is None:
        return {
            "status": "missing",
            "message": "No Withings data received yet.",
        }

    dt, formatted_time = parsed

    if dt.date() == date.today():
        return {
            "status": "current",
            "message": f"Withings last update: {formatted_time}",
        }

    return {
        "status": "stale",
        "message": f"Withings last update: {formatted_time}",
    }


def build_apple_health_freshness(latest_time):
    parsed = format_latest_time(latest_time)

    if parsed is None:
        return {
            "status": "missing",
            "message": "No Apple Health data received yet.",
        }

    dt, formatted_time = parsed

    if dt.date() == date.today():
        return {
            "status": "current",
            "message": f"Apple Health last update: {formatted_time}",
        }

    return {
        "status": "stale",
        "message": f"Apple Health last update: {formatted_time}",
    }