from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import runpy
from typing import Any

import pandas as pd
import streamlit as st

from database import (
    get_latest_measurement_time,
    get_manual_wrist_temperature_for_date,
    init_db,
    load_recent_wrist_temperatures,
    save_manual_wrist_temperature,
)
from freshness import build_apple_health_freshness, build_withings_freshness
from integrations.withings import build_authorization_url, withings_is_connected
from phoenix_narrative import (
    health_trends_story,
    performance_story,
    timeline_story,
    today_health_story,
)
from snapshot import build_morning_snapshot
from sync import sync_withings_once_per_session


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_TODAY = ROOT / "app.py"
LOGO_PATH = ROOT / "assets" / "phoenix_logo.png"

init_db()


def _safe_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _format_updated(value: Any) -> str:
    parsed = _safe_datetime(value)
    if parsed is None:
        return "No recent update found"
    return parsed.astimezone().strftime("%d %b %Y · %H:%M")


def _status_icon(status: str) -> str:
    return {"current": "🟢", "stale": "🟡"}.get(status, "🔴")


def _render_status(title: str, icon: str, label: str, detail: str | None = None) -> None:
    st.markdown(f"**{title}**")
    st.markdown(f"{icon} {label}")
    if detail:
        st.caption(detail)


def _latest_wrist_temperature() -> tuple[date | None, float | None, str | None]:
    try:
        recent = load_recent_wrist_temperatures(limit=1)
    except Exception:
        return None, None, None

    if recent is None or recent.empty:
        return None, None, None

    row = recent.iloc[0]
    raw_date = row.get("measurement_date")
    try:
        measured_on = pd.to_datetime(raw_date).date()
    except Exception:
        measured_on = None

    try:
        value = float(row.get("value"))
    except (TypeError, ValueError):
        value = None

    source = str(row.get("source") or "").replace("_", " ").title() or None
    return measured_on, value, source


def _readiness_sentence(
    *,
    snapshot: dict[str, Any],
    withings_status: str,
    apple_status: str,
    wrist_date: date | None,
) -> tuple[str, str]:
    actions: list[str] = []

    if apple_status != "current":
        actions.append("let Apple Health finish syncing")
    if withings_status != "current":
        actions.append("sync Withings")

    if wrist_date is None:
        actions.append("enter a wrist-temperature reading")
    else:
        age_days = (date.today() - wrist_date).days
        if age_days > 0:
            actions.append(
                "enter today’s wrist temperature"
                if age_days == 1
                else f"update wrist temperature (last entry was {age_days} days ago)"
            )

    checkin_done = bool(snapshot.get("today_checkin_done", False))
    lumen_done = bool(snapshot.get("lumen_entered", False))
    if not checkin_done:
        actions.append("complete today’s check-in")
    if not lumen_done:
        actions.append("add today’s Lumen reading")

    if not actions:
        return (
            "success",
            "Phoenix has everything it needs for today’s assessment. No updates are required.",
        )

    if len(actions) == 1:
        action_text = actions[0]
    else:
        action_text = ", ".join(actions[:-1]) + f", and {actions[-1]}"

    return (
        "warning",
        f"Phoenix can assess today, but the picture will be stronger once you {action_text}.",
    )


snapshot = build_morning_snapshot() or {}
withings_latest = get_latest_measurement_time("withings")
apple_latest = get_latest_measurement_time("apple_health")
withings_freshness = build_withings_freshness(withings_latest) or {}
apple_freshness = build_apple_health_freshness(apple_latest) or {}
latest_wrist_date, latest_wrist_value, latest_wrist_source = _latest_wrist_temperature()

left, right = st.columns([2.25, 1], gap="large")

with left:
    with st.container(border=True):
        st.markdown("### Today’s data readiness")

        readiness_level, readiness_message = _readiness_sentence(
            snapshot=snapshot,
            withings_status=str(withings_freshness.get("status", "missing")),
            apple_status=str(apple_freshness.get("status", "missing")),
            wrist_date=latest_wrist_date,
        )
        getattr(st, readiness_level)(
            readiness_message,
            icon="✅" if readiness_level == "success" else "⚠️",
        )

        confidence = int(snapshot.get("snapshot_percent", 0) or 0)
        if confidence >= 90:
            confidence_label = "High"
        elif confidence >= 70:
            confidence_label = "Moderate"
        else:
            confidence_label = "Limited"
        st.markdown(f"**Assessment confidence: {confidence_label} · {confidence}%**")

        source_col1, source_col2 = st.columns(2)
        with source_col1:
            if withings_is_connected():
                _render_status(
                    "Withings",
                    _status_icon(str(withings_freshness.get("status", "missing"))),
                    "Current" if withings_freshness.get("status") == "current" else "Update recommended",
                    _format_updated(withings_latest),
                )
                if st.button("🔄 Sync Withings now", key="phoenix_top_sync_withings"):
                    with st.spinner("Syncing Withings data..."):
                        sync_withings_once_per_session(st, force=True)
                    st.success("Withings sync complete.")
                    st.rerun()
            else:
                _render_status("Withings", "🔴", "Not connected")
                st.link_button("Connect Withings", build_authorization_url())

        with source_col2:
            _render_status(
                "Apple Health",
                _status_icon(str(apple_freshness.get("status", "missing"))),
                "Current" if apple_freshness.get("status") == "current" else "Waiting for newer data",
                _format_updated(apple_latest),
            )

        check_col1, check_col2 = st.columns(2)
        with check_col1:
            _render_status(
                "Morning check-in",
                "🟢" if snapshot.get("today_checkin_done", False) else "🟡",
                "Complete" if snapshot.get("today_checkin_done", False) else "Still needed",
            )
        with check_col2:
            _render_status(
                "Lumen",
                "🟢" if snapshot.get("lumen_entered", False) else "🟡",
                "Entered" if snapshot.get("lumen_entered", False) else "Still needed",
            )

    with st.container(border=True):
        st.markdown("### 🌡️ Wrist temperature")

        if latest_wrist_date is None:
            st.warning("No wrist-temperature reading is stored yet.")
        else:
            age_days = (date.today() - latest_wrist_date).days
            source_text = f" · {latest_wrist_source}" if latest_wrist_source else ""
            if age_days == 0:
                st.success(
                    f"Today’s reading is recorded: {latest_wrist_value:.2f} °C{source_text}."
                )
            elif age_days == 1:
                st.warning(
                    f"The latest reading is from yesterday: {latest_wrist_value:.2f} °C{source_text}."
                )
            else:
                st.warning(
                    f"Wrist temperature has not been updated for {age_days} days. "
                    f"The latest reading was {latest_wrist_value:.2f} °C{source_text}."
                )

        temp_col1, temp_col2 = st.columns([1, 1])
        with temp_col1:
            wrist_temp_date = st.date_input(
                "Measurement date",
                value=date.today(),
                max_value=date.today(),
                key="phoenix_top_wrist_temp_date",
            )

        existing_temp = get_manual_wrist_temperature_for_date(wrist_temp_date)
        default_temp = float(existing_temp["value"]) if existing_temp else 36.50

        with temp_col2:
            wrist_temperature = st.number_input(
                "Wrist temperature (°C)",
                min_value=30.00,
                max_value=45.00,
                value=default_temp,
                step=0.01,
                format="%.2f",
                key=f"phoenix_top_wrist_temp_value_{wrist_temp_date.isoformat()}",
            )

        save_label = "Update reading" if existing_temp else "Save today’s reading"
        if st.button(
            f"💾 {save_label}",
            key="phoenix_top_save_wrist_temperature",
            type="primary" if not existing_temp else "secondary",
        ):
            save_manual_wrist_temperature(
                measurement_date=wrist_temp_date,
                temperature=wrist_temperature,
            )
            st.success(
                f"Wrist temperature saved for {wrist_temp_date.strftime('%d %B %Y')}: "
                f"{wrist_temperature:.2f} °C"
            )
            st.rerun()

with right:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
    else:
        st.markdown("# 🔥 PHOENIX")
        st.caption("Health · Performance · Intelligence")

st.subheader("Today’s Phoenix briefing")
with st.container(border=True):
    st.markdown("### ❤️ Health")
    st.write(today_health_story())
    st.page_link("pages/Phoenix_Health.py", label="Open Health", icon="❤️")

perf_good, perf_watch, perf_bottom = performance_story()
with st.container(border=True):
    st.markdown("### 🚴 Performance")
    st.write(perf_good)
    st.markdown(f"**Worth watching:** {perf_watch}")
    st.markdown(f"**Phoenix’s view:** {perf_bottom}")
    st.page_link("pages/Phoenix_Performance.py", label="Open Performance", icon="🚴")

with st.expander("Recent context Phoenix is using"):
    st.write(timeline_story())
    st.write(health_trends_story(90))

st.divider()
st.caption("Your existing Today inputs and dashboard continue below.")

# The redesigned Today page already handles these controls at the top.
st.session_state["phoenix_today_handles_wrist_temp"] = True
st.session_state["phoenix_today_handles_data_readiness"] = True

if ORIGINAL_TODAY.exists():
    runpy.run_path(str(ORIGINAL_TODAY), run_name="__phoenix_today__")
else:
    st.error("Phoenix could not find app.py in the project root.")
