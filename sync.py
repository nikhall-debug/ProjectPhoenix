from datetime import datetime, timedelta

from database import get_latest_measurement_time, save_health_measurement
from integrations.withings import get_withings_measurements, stored_tokens_are_valid
from integrations.apple_health_json import sync_apple_health_json_exports


def sync_withings_once_per_session(st, force=False):
    if not stored_tokens_are_valid():
        return

    if "withings_synced_this_session" not in st.session_state:
        st.session_state["withings_synced_this_session"] = False

    if st.session_state["withings_synced_this_session"] and not force:
        return

    latest_time = get_latest_measurement_time("withings")

    if force:
        # Manual sync: look back further to catch anything missed
        startdate = int((datetime.now() - timedelta(days=30)).timestamp())
    elif latest_time is not None:
        # Auto sync: small overlap to avoid missing late-arriving data
        latest_dt = datetime.fromisoformat(latest_time)
        startdate = int((latest_dt - timedelta(days=2)).timestamp())
    else:
        startdate = None

    measurements = get_withings_measurements(limit=100, startdate=startdate)

    for measurement in measurements:
        save_health_measurement(
            source=measurement["source"],
            metric_type=measurement["metric_type"],
            value=measurement["value"],
            unit=measurement["unit"],
            measured_at=measurement["measured_at"],
            raw_type=measurement["raw_type"],
            raw_data=measurement["raw_data"],
        )

    st.session_state["withings_synced_this_session"] = True


def sync_apple_health_autosync_once_per_session(st):
    if "apple_health_autosync_done" not in st.session_state:
        st.session_state["apple_health_autosync_done"] = False

    if st.session_state["apple_health_autosync_done"]:
        return

    result = sync_apple_health_json_exports()

    st.session_state["apple_health_autosync_done"] = True
    st.session_state["apple_health_autosync_result"] = result