from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
LOGO_PATH = ROOT / "assets" / "phoenix_logo.png"


def render_brand_header(*, compact: bool = False) -> None:
    """Render the Phoenix brand without changing any existing page logic."""
    if LOGO_PATH.exists():
        width = 250 if compact else 330
        left, centre, right = st.columns([1, 1.15, 1])
        with centre:
            st.image(str(LOGO_PATH), width=width)
    else:
        st.markdown("# 🔥 PHOENIX")
        st.caption("Health · Performance · Intelligence")


def render_section_card(
    title: str,
    body: str,
    *,
    icon: str,
    target: str,
    label: str,
) -> None:
    with st.container(border=True):
        st.subheader(f"{icon} {title}")
        st.write(body)
        st.page_link(target, label=label, icon=icon, use_container_width=True)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def build_data_readiness_message() -> tuple[str, str]:
    """Return (level, sentence) using Phoenix's existing snapshot where possible.

    This deliberately fails softly. It will never stop the Today page loading if a
    data source, column, or engine changes later.
    """
    try:
        from snapshot import build_morning_snapshot

        snapshot = build_morning_snapshot() or {}
    except Exception:
        return (
            "info",
            "Phoenix could not check source freshness automatically, but the rest of today's page is still available.",
        )

    checks = {
        "Apple Health": ["hrv", "resting_hr", "sleep", "sleep_hours", "blood_oxygen"],
        "Withings": ["weight", "body_fat", "muscle", "pwv"],
    }

    source_available: dict[str, bool] = {}
    for source, keys in checks.items():
        source_available[source] = any(
            key in snapshot and not _is_missing(snapshot.get(key)) for key in keys
        )

    missing = [name for name, available in source_available.items() if not available]

    if not missing:
        return (
            "success",
            "Phoenix has current Apple Health and Withings inputs for today's assessment. No update is needed right now.",
        )

    if len(missing) == 1:
        return (
            "warning",
            f"Update {missing[0]} to give Phoenix the strongest possible assessment for today.",
        )

    return (
        "warning",
        "Update Apple Health and Withings to give Phoenix the strongest possible assessment for today.",
    )


def render_data_readiness() -> None:
    level, message = build_data_readiness_message()
    renderer = getattr(st, level, st.info)
    renderer(message, icon="🔄" if level == "warning" else "✅")


def first_text(values: Iterable[Any], fallback: str) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback
