from typing import Any, Dict, List, Optional

import altair as alt
import pandas as pd
import streamlit as st

from database import init_db
from trend_engine import build_health_trends
from version import PHOENIX_VERSION_LABEL


# ---------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="Health Trends · Project Phoenix",
    page_icon="📈",
    layout="wide",
)

init_db()

st.title("📈 Health Trends")
st.caption(
    "Project Phoenix · How your health, wellbeing and performance "
    "are changing over time"
)


# ---------------------------------------------------------------------
# Display configuration
# ---------------------------------------------------------------------

PERIOD_OPTIONS = {
    "30 days": 30,
    "90 days": 90,
    "180 days": 180,
    "365 days": 365,
}

RECOVERY_SIGNAL_KEYS = [
    "hrv",
    "resting_hr",
    "wrist_temperature",
    "sleep_total",
    "sleep_consistency",
    "respiratory_rate",
    "blood_oxygen",
]

RECOVERY_SIGNAL_DESCRIPTIONS = {
    "hrv": (
        "Autonomic recovery relative to your personal baseline."
    ),
    "resting_hr": (
        "Useful for identifying cardiovascular or systemic strain."
    ),
    "wrist_temperature": (
        "Night-time wrist temperature relative to your recent baseline."
    ),
    "sleep_total": (
        "Recent sleep duration compared with your longer baseline."
    ),
    "sleep_consistency": (
        "Variation in sleep duration. Lower variation is more consistent."
    ),
    "respiratory_rate": (
        "Most useful when it moves away from your normal baseline."
    ),
    "blood_oxygen": (
        "Recent oxygen-saturation stability from Apple Health."
    ),
}

GROUP_DISPLAY = [
    {
        "key": "body",
        "title": "⚖️ Body Composition",
        "caption": (
            "Weight, fat mass, lean tissue, muscle, hydration "
            "and long-term body-composition direction."
        ),
    },
    {
        "key": "cardiovascular",
        "title": "❤️ Cardiovascular & Recovery",
        "caption": (
            "Heart rate, HRV, wrist temperature, blood pressure, "
            "pulse-wave velocity, oxygen saturation and respiratory signals."
        ),
    },
    {
        "key": "sleep",
        "title": "😴 Sleep",
        "caption": (
            "Total sleep, sleep stages and sleep-duration consistency "
            "from Apple Health."
        ),
    },
    {
        "key": "metabolism",
        "title": "🔥 Metabolism",
        "caption": (
            "Lumen and estimated fuel-use patterns from your "
            "daily check-ins."
        ),
    },
    {
        "key": "wellbeing",
        "title": "🧠 Subjective Wellbeing",
        "caption": (
            "Energy, mood and soreness trends from your morning check-ins."
        ),
    },
    {
        "key": "activity",
        "title": "🚶 Daily Activity",
        "caption": (
            "Steps, exercise minutes, active energy and walking "
            "or running distance."
        ),
    },
    {
        "key": "performance",
        "title": "🚴 Performance Context",
        "caption": (
            "FTP, lower-threshold power, training load and target XSS "
            "from Xert."
        ),
    },
]


# ---------------------------------------------------------------------
# General formatting helpers
# ---------------------------------------------------------------------

def safe_float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        if value is None:
            return default

        return int(value)

    except (TypeError, ValueError):
        return default


def format_number(
    value: Any,
    decimals: int = 1,
) -> str:
    numeric = safe_float(
        value
    )

    if numeric is None:
        return "—"

    if decimals <= 0:
        return f"{numeric:,.0f}"

    return f"{numeric:,.{decimals}f}"


def format_value_with_unit(
    value: Any,
    unit: str,
    decimals: int,
) -> str:
    numeric = safe_float(
        value
    )

    if numeric is None:
        return "—"

    value_text = format_number(
        numeric,
        decimals,
    )

    clean_unit = str(
        unit or ""
    ).strip()

    if not clean_unit:
        return value_text

    if clean_unit.startswith("/"):
        return f"{value_text}{clean_unit}"

    return f"{value_text} {clean_unit}"


def format_metric_value(
    metric: Dict[str, Any],
) -> str:
    return format_value_with_unit(
        value=metric.get("current"),
        unit=str(
            metric.get("unit")
            or ""
        ),
        decimals=safe_int(
            metric.get("decimals"),
            1,
        ),
    )


def format_metric_average(
    metric: Dict[str, Any],
    field: str,
) -> str:
    return format_value_with_unit(
        value=metric.get(field),
        unit=str(
            metric.get("unit")
            or ""
        ),
        decimals=safe_int(
            metric.get("decimals"),
            1,
        ),
    )


def format_change(
    metric: Dict[str, Any],
) -> Optional[str]:
    change = safe_float(
        metric.get("change")
    )

    if change is None:
        return None

    decimals = safe_int(
        metric.get("decimals"),
        1,
    )

    unit = str(
        metric.get("unit")
        or ""
    ).strip()

    sign = (
        "+"
        if change > 0
        else ""
    )

    value_text = (
        f"{sign}"
        f"{format_number(change, decimals)}"
    )

    if not unit:
        return value_text

    if unit.startswith("/"):
        return f"{value_text}{unit}"

    return f"{value_text} {unit}"


def format_date(
    value: Any,
) -> str:
    if not value:
        return "Unknown date"

    try:
        return pd.to_datetime(
            value
        ).strftime(
            "%d %b %Y"
        )

    except Exception:
        return str(value)


def confidence_percent(
    metric: Dict[str, Any],
) -> int:
    confidence = safe_float(
        metric.get("confidence"),
        0.0,
    )

    if confidence is None:
        return 0

    if confidence <= 1:
        confidence *= 100

    return int(
        round(confidence)
    )


def direction_icon(
    direction: str,
) -> str:
    icons = {
        "increasing": "↗",
        "decreasing": "↘",
        "stable": "→",
        "insufficient_data": "•",
        "no_data": "•",
    }

    return icons.get(
        direction,
        "•",
    )


def favorable_label(
    status: str,
) -> str:
    labels = {
        "improving": "Improving",
        "worsening": "Needs attention",
        "stable": "Stable",
        "contextual": "Context dependent",
        "unknown": "Not enough data",
    }

    return labels.get(
        status,
        "Not enough data",
    )


def favorable_icon(
    status: str,
) -> str:
    icons = {
        "improving": "🟢",
        "worsening": "🟠",
        "stable": "🔵",
        "contextual": "⚪",
        "unknown": "⚪",
    }

    return icons.get(
        status,
        "⚪",
    )


def group_status_icon(
    status: str,
) -> str:
    icons = {
        "improving": "🟢",
        "stable": "🔵",
        "mixed": "🟡",
        "needs_attention": "🟠",
        "contextual": "⚪",
        "no_data": "⚪",
    }

    return icons.get(
        status,
        "⚪",
    )


def overall_status_icon(
    status: str,
) -> str:
    icons = {
        "improving": "🟢",
        "stable": "🔵",
        "mixed": "🟡",
        "needs_attention": "🟠",
        "contextual": "⚪",
        "no_data": "⚪",
    }

    return icons.get(
        status,
        "⚪",
    )


def freshness_text(
    metric: Dict[str, Any],
) -> str:
    age = metric.get(
        "latest_age_days"
    )

    if age is None:
        return "No recent reading"

    age = safe_int(
        age,
        0,
    )

    if age == 0:
        return "Updated today"

    if age == 1:
        return "Updated yesterday"

    return f"Updated {age} days ago"


# ---------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------

def metric_chart_frame(
    metric: Dict[str, Any],
    prefer_smoothed: bool = False,
) -> pd.DataFrame:
    if prefer_smoothed:
        points = (
            metric.get("smoothed_points")
            or metric.get("points")
            or []
        )
    else:
        points = (
            metric.get("points")
            or []
        )

    if not points:
        return pd.DataFrame()

    frame = pd.DataFrame(
        points
    )

    if (
        frame.empty
        or "date" not in frame.columns
        or "value" not in frame.columns
    ):
        return pd.DataFrame()

    frame["date"] = pd.to_datetime(
        frame["date"],
        errors="coerce",
    )

    frame["value"] = pd.to_numeric(
        frame["value"],
        errors="coerce",
    )

    frame = frame.dropna(
        subset=[
            "date",
            "value",
        ]
    )

    if frame.empty:
        return pd.DataFrame()

    frame = frame.sort_values(
        "date"
    )

    return frame.set_index(
        "date"
    )[["value"]]


def chart_y_domain(
    metric: Dict[str, Any],
    chart_data: pd.DataFrame,
) -> Optional[List[float]]:
    """
    Return a focused Y-axis range for metrics that need one.

    Wrist-temperature changes happen across a narrow range. A generic
    zero-based axis flattens the useful movement, so Phoenix calculates
    a padded range around the available temperature values.
    """
    if (
        chart_data is None
        or chart_data.empty
        or metric.get("key") != "wrist_temperature"
    ):
        return None

    minimum = safe_float(
        chart_data["value"].min()
    )

    maximum = safe_float(
        chart_data["value"].max()
    )

    if minimum is None or maximum is None:
        return None

    padding = 0.20
    minimum_span = 1.00

    data_midpoint = (
        minimum + maximum
    ) / 2

    data_span = (
        maximum - minimum
    )

    desired_span = max(
        data_span + padding * 2,
        minimum_span,
    )

    lower_bound = (
        data_midpoint
        - desired_span / 2
    )

    upper_bound = (
        data_midpoint
        + desired_span / 2
    )

    lower_bound = round(
        lower_bound,
        1,
    )

    upper_bound = round(
        upper_bound,
        1,
    )

    if lower_bound == upper_bound:
        lower_bound -= 0.5
        upper_bound += 0.5

    return [
        lower_bound,
        upper_bound,
    ]


def render_chart(
    metric: Dict[str, Any],
    prefer_smoothed: bool = True,
    height: int = 210,
) -> None:
    chart_data = metric_chart_frame(
        metric,
        prefer_smoothed=prefer_smoothed,
    )

    if chart_data.empty:
        st.caption(
            "No chart history is available yet."
        )
        return

    if len(chart_data) == 1:
        st.caption(
            "One reading is available. More history is needed "
            "before a trend line can be drawn."
        )
        return

    plotting_frame = (
        chart_data
        .reset_index()
        .rename(
            columns={
                "date": "Date",
                "value": "Value",
            }
        )
    )

    y_domain = chart_y_domain(
        metric=metric,
        chart_data=chart_data,
    )

    if y_domain is not None:
        y_scale = alt.Scale(
            domain=y_domain,
            zero=False,
            nice=False,
        )
    else:
        y_scale = alt.Scale(
            zero=False,
        )

    decimals = safe_int(
        metric.get("decimals"),
        1,
    )

    unit = str(
        metric.get("unit")
        or ""
    ).strip()

    number_format = (
        f".{max(decimals, 0)}f"
    )

    chart = (
        alt.Chart(
            plotting_frame
        )
        .mark_line(
            point=True,
        )
        .encode(
            x=alt.X(
                "Date:T",
                title=None,
                axis=alt.Axis(
                    format="%d %b",
                    labelAngle=0,
                    labelOverlap=True,
                ),
            ),
            y=alt.Y(
                "Value:Q",
                title=unit or None,
                scale=y_scale,
                axis=alt.Axis(
                    format=number_format,
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "Date:T",
                    title="Date",
                    format="%d %b %Y",
                ),
                alt.Tooltip(
                    "Value:Q",
                    title=metric.get(
                        "label",
                        "Value",
                    ),
                    format=number_format,
                ),
            ],
        )
        .properties(
            height=height,
        )
        .interactive(
            bind_y=False,
        )
    )

    st.altair_chart(
        chart,
        width="stretch",
    )


# ---------------------------------------------------------------------
# Recovery signal interpretation
# ---------------------------------------------------------------------

def recovery_signal_state(
    metric: Dict[str, Any],
) -> str:
    if metric.get("current") is None:
        return "no_data"

    if metric.get(
        "is_stale",
        False,
    ):
        return "stale"

    if not metric.get(
        "has_enough_data",
        False,
    ):
        return "insufficient"

    favorable = metric.get(
        "favorable_direction",
        "unknown",
    )

    if favorable == "improving":
        return "improving"

    if favorable == "worsening":
        return "worsening"

    if favorable == "stable":
        return "stable"

    return "contextual"


def recovery_signal_badge(
    state: str,
) -> str:
    labels = {
        "improving": "🟢 Favourable",
        "stable": "🔵 Stable",
        "worsening": "🟠 Less favourable",
        "contextual": "⚪ Context dependent",
        "stale": "🕒 Out of date",
        "insufficient": "⚪ Building history",
        "no_data": "⚪ No data",
    }

    return labels.get(
        state,
        "⚪ Unknown",
    )


def build_recovery_summary(
    recovery_metrics: List[Dict[str, Any]],
) -> Dict[str, str]:
    available = [
        metric
        for metric in recovery_metrics
        if metric.get("current") is not None
    ]

    if not available:
        return {
            "status": "no_data",
            "headline": "Recovery history is not available yet",
            "summary": (
                "Phoenix needs repeated HRV, resting heart rate, wrist "
                "temperature, sleep, respiratory-rate and blood-oxygen "
                "readings before it can describe your recovery pattern."
            ),
        }

    states = {
        metric.get("key"): recovery_signal_state(
            metric
        )
        for metric in available
    }

    improving = [
        metric
        for metric in available
        if states.get(
            metric.get("key")
        ) == "improving"
    ]

    worsening = [
        metric
        for metric in available
        if states.get(
            metric.get("key")
        ) == "worsening"
    ]

    stable = [
        metric
        for metric in available
        if states.get(
            metric.get("key")
        ) == "stable"
    ]

    contextual = [
        metric
        for metric in available
        if states.get(
            metric.get("key")
        ) == "contextual"
    ]

    stale = [
        metric
        for metric in available
        if states.get(
            metric.get("key")
        ) == "stale"
    ]

    insufficient = [
        metric
        for metric in available
        if states.get(
            metric.get("key")
        ) == "insufficient"
    ]

    if worsening and improving:
        status = "mixed"
        headline = "Recovery signals are mixed"
        summary = (
            f"{len(improving)} recovery signal(s) are moving "
            f"favourably, while {len(worsening)} are moving less "
            "favourably."
        )

    elif worsening:
        status = "needs_attention"
        headline = "Some recovery signals are under pressure"

        names = ", ".join(
            metric.get(
                "label",
                "signal",
            )
            for metric in worsening[:3]
        )

        verb = (
            "is"
            if len(worsening) == 1
            else "are"
        )

        summary = (
            f"{names} {verb} moving in a less favourable direction. "
            "Phoenix should interpret this alongside training load, "
            "sleep, symptoms and recent medical events."
        )

    elif improving:
        status = "improving"
        headline = "Recovery signals are improving"

        names = ", ".join(
            metric.get(
                "label",
                "signal",
            )
            for metric in improving[:3]
        )

        verb = (
            "is"
            if len(improving) == 1
            else "are"
        )

        summary = (
            f"{names} {verb} moving in a favourable direction."
        )

    elif stable:
        status = "stable"
        headline = "Recovery signals are broadly stable"
        summary = (
            f"{len(stable)} recovery signal(s) are close to their "
            "recent baseline, with no meaningful movement detected."
        )

    else:
        status = "contextual"
        headline = "Recovery signals need more context"
        summary = (
            "Recovery data is available, but the current pattern "
            "cannot yet be classified reliably."
        )

    if contextual:
        summary += (
            f" {len(contextual)} signal(s) remain context dependent."
        )

    if insufficient:
        summary += (
            f" {len(insufficient)} signal(s) are still building history."
        )

    if stale:
        summary += (
            f" {len(stale)} signal(s) may be out of date."
        )

    return {
        "status": status,
        "headline": headline,
        "summary": summary,
    }


# ---------------------------------------------------------------------
# Recovery section rendering
# ---------------------------------------------------------------------

def render_recovery_signal_card(
    metric: Dict[str, Any],
) -> None:
    state = recovery_signal_state(
        metric
    )

    label = metric.get(
        "label",
        "Recovery signal",
    )

    key = metric.get(
        "key",
        "",
    )

    with st.container(
        border=True
    ):
        st.caption(
            recovery_signal_badge(
                state
            )
        )

        st.metric(
            label,
            format_metric_value(
                metric
            ),
        )

        values = st.columns(
            2
        )

        with values[0]:
            st.caption(
                "7-day average"
            )
            st.write(
                f"**{format_metric_average(metric, 'average_7d')}**"
            )

        with values[1]:
            st.caption(
                "28-day average"
            )
            st.write(
                f"**{format_metric_average(metric, 'average_28d')}**"
            )

        render_chart(
            metric,
            prefer_smoothed=True,
            height=150,
        )

        description = (
            RECOVERY_SIGNAL_DESCRIPTIONS.get(
                key,
                "",
            )
        )

        if description:
            st.caption(
                description
            )

        coverage = safe_int(
            metric.get("coverage_percent"),
            0,
        )

        st.caption(
            f"{freshness_text(metric)} · "
            f"{coverage}% data coverage · "
            f"{confidence_percent(metric)}% confidence"
        )


def render_recovery_signals(
    trends: Dict[str, Any],
) -> None:
    metrics_by_key = trends.get(
        "metrics",
        {},
    )

    recovery_metrics: List[
        Dict[str, Any]
    ] = []

    for key in RECOVERY_SIGNAL_KEYS:
        metric = metrics_by_key.get(
            key
        )

        if not isinstance(
            metric,
            dict,
        ):
            continue

        recovery_metrics.append(
            metric
        )

    available_recovery_metrics = [
        metric
        for metric in recovery_metrics
        if metric.get("current") is not None
    ]

    recovery_summary = build_recovery_summary(
        available_recovery_metrics
    )

    st.divider()
    st.header(
        "🫀 Recovery Signals"
    )

    st.caption(
        "A combined view of autonomic recovery, cardiovascular strain, "
        "sleep, temperature, breathing and oxygen saturation."
    )

    with st.container(
        border=True
    ):
        left, right = st.columns(
            [3, 1]
        )

        with left:
            status = recovery_summary.get(
                "status",
                "no_data",
            )

            headline = recovery_summary.get(
                "headline",
                "Recovery signals",
            )

            st.markdown(
                f"### {overall_status_icon(status)} "
                f"{headline}"
            )

            st.write(
                recovery_summary.get(
                    "summary",
                    "",
                )
            )

        with right:
            fresh_count = sum(
                1
                for metric in available_recovery_metrics
                if not metric.get(
                    "is_stale",
                    False,
                )
            )

            reliable_count = sum(
                1
                for metric in available_recovery_metrics
                if metric.get(
                    "has_enough_data",
                    False,
                )
            )

            st.metric(
                "Fresh signals",
                (
                    f"{fresh_count}"
                    f"/{len(RECOVERY_SIGNAL_KEYS)}"
                ),
            )

            st.metric(
                "Reliable trends",
                (
                    f"{reliable_count}"
                    f"/{len(RECOVERY_SIGNAL_KEYS)}"
                ),
            )

    if not available_recovery_metrics:
        st.info(
            "Phoenix found the recovery signal definitions, but none "
            "currently contain usable values for the selected period."
        )
        return

    for index in range(
        0,
        len(available_recovery_metrics),
        3,
    ):
        row_metrics = available_recovery_metrics[
            index:index + 3
        ]

        columns = st.columns(
            3
        )

        for column, metric in zip(
            columns,
            row_metrics,
        ):
            with column:
                render_recovery_signal_card(
                    metric
                )


# ---------------------------------------------------------------------
# Standard metric rendering
# ---------------------------------------------------------------------

def render_metric_card(
    metric: Dict[str, Any],
) -> None:
    label = metric.get(
        "label",
        "Metric",
    )

    current = metric.get(
        "current"
    )

    with st.container(
        border=True
    ):
        if current is None:
            st.write(
                f"**{label}**"
            )

            st.metric(
                label,
                "—",
            )

            st.caption(
                metric.get(
                    "summary",
                    "No history is available yet.",
                )
            )
            return

        change_text = format_change(
            metric
        )

        st.metric(
            label,
            format_metric_value(
                metric
            ),
            delta=change_text,
            delta_color="off",
        )

        if metric.get(
            "is_stale",
            False,
        ):
            st.warning(
                freshness_text(
                    metric
                )
            )

        direction = metric.get(
            "direction",
            "insufficient_data",
        )

        favorable = metric.get(
            "favorable_direction",
            "unknown",
        )

        direction_text = (
            f"{direction_icon(direction)} "
            f"{str(direction).replace('_', ' ').title()}"
        )

        status_text = (
            f"{favorable_icon(favorable)} "
            f"{favorable_label(favorable)}"
        )

        c1, c2 = st.columns(
            2
        )

        with c1:
            st.caption(
                "Direction"
            )
            st.write(
                direction_text
            )

        with c2:
            st.caption(
                "Interpretation"
            )
            st.write(
                status_text
            )

        averages = st.columns(
            2
        )

        with averages[0]:
            st.caption(
                "7-day average"
            )
            st.write(
                format_metric_average(
                    metric,
                    "average_7d",
                )
            )

        with averages[1]:
            st.caption(
                "28-day average"
            )
            st.write(
                format_metric_average(
                    metric,
                    "average_28d",
                )
            )

        render_chart(
            metric,
            prefer_smoothed=True,
        )

        st.write(
            metric.get(
                "summary",
                "",
            )
        )

        reading_count = safe_int(
            metric.get("reading_count"),
            0,
        )

        days_covered = safe_int(
            metric.get("days_covered"),
            0,
        )

        coverage = safe_int(
            metric.get("coverage_percent"),
            0,
        )

        confidence = confidence_percent(
            metric
        )

        latest_date = format_date(
            metric.get(
                "current_date"
            )
        )

        st.caption(
            f"{reading_count} daily reading(s) · "
            f"{days_covered} day(s) covered · "
            f"{coverage}% data coverage · "
            f"{confidence}% confidence · "
            f"Latest: {latest_date}"
        )


def render_metric_grid(
    metrics: List[Dict[str, Any]],
) -> None:
    if not metrics:
        st.info(
            "No metrics are configured for this section."
        )
        return

    available = [
        metric
        for metric in metrics
        if metric.get("current") is not None
    ]

    unavailable = [
        metric
        for metric in metrics
        if metric.get("current") is None
    ]

    if not available:
        st.info(
            "No history is available for this section "
            "in the selected period."
        )

    for index in range(
        0,
        len(available),
        2,
    ):
        row_metrics = available[
            index:index + 2
        ]

        columns = st.columns(
            2
        )

        for column, metric in zip(
            columns,
            row_metrics,
        ):
            with column:
                render_metric_card(
                    metric
                )

    if unavailable:
        with st.expander(
            f"Unavailable metrics ({len(unavailable)})"
        ):
            for metric in unavailable:
                st.write(
                    f"• {metric.get('label', 'Metric')}"
                )


# ---------------------------------------------------------------------
# Section rendering
# ---------------------------------------------------------------------

def render_group_section(
    group_key: str,
    title: str,
    caption: str,
    trends: Dict[str, Any],
) -> None:
    metrics = trends.get(
        "groups",
        {},
    ).get(
        group_key,
        [],
    )

    summary = trends.get(
        "group_summaries",
        {},
    ).get(
        group_key,
        {},
    )

    st.divider()
    st.header(
        title
    )
    st.caption(
        caption
    )

    status = summary.get(
        "status",
        "no_data",
    )

    summary_text = summary.get(
        "summary",
        "No trend summary is available.",
    )

    with st.container(
        border=True
    ):
        top_left, top_right = st.columns(
            [3, 1]
        )

        with top_left:
            st.write(
                f"**{group_status_icon(status)} "
                f"{summary.get('label', title)}**"
            )

            st.write(
                summary_text
            )

        with top_right:
            st.metric(
                "Available metrics",
                summary.get(
                    "available_count",
                    0,
                ),
            )

            st.metric(
                "Fresh metrics",
                summary.get(
                    "fresh_count",
                    0,
                ),
            )

        counts = st.columns(
            4
        )

        with counts[0]:
            st.caption(
                "Improving"
            )
            st.write(
                summary.get(
                    "improving_count",
                    0,
                )
            )

        with counts[1]:
            st.caption(
                "Stable"
            )
            st.write(
                summary.get(
                    "stable_count",
                    0,
                )
            )

        with counts[2]:
            st.caption(
                "Needs attention"
            )
            st.write(
                summary.get(
                    "worsening_count",
                    0,
                )
            )

        with counts[3]:
            st.caption(
                "Contextual"
            )
            st.write(
                summary.get(
                    "contextual_count",
                    0,
                )
            )

    render_metric_grid(
        metrics
    )


# ---------------------------------------------------------------------
# Build trend results
# ---------------------------------------------------------------------

period_label = st.segmented_control(
    "Trend period",
    options=list(
        PERIOD_OPTIONS.keys()
    ),
    default="90 days",
)

if period_label is None:
    period_label = "90 days"

selected_days = PERIOD_OPTIONS[
    period_label
]

try:
    trends = build_health_trends(
        days=selected_days
    )

except Exception as error:
    st.error(
        "Phoenix could not build the Health Trends report."
    )

    st.exception(
        error
    )

    st.stop()


# ---------------------------------------------------------------------
# Overall health direction
# ---------------------------------------------------------------------

metric_availability = trends.get(
    "metric_availability_percent",
    trends.get(
        "coverage_percent",
        0,
    ),
)

average_coverage = trends.get(
    "average_data_coverage_percent",
    0,
)

overall = trends.get(
    "overall",
    {},
)

overall_status = overall.get(
    "status",
    "no_data",
)

st.divider()

with st.container(
    border=True
):
    left, middle, right = st.columns(
        [2.2, 1, 1]
    )

    with left:
        st.caption(
            f"Overall direction · Last {selected_days} days"
        )

        st.markdown(
            f"## {overall_status_icon(overall_status)} "
            f"{overall.get('headline', 'Health trends')}"
        )

        st.write(
            overall.get(
                "summary",
                "No overall summary is available.",
            )
        )

    with middle:
        st.metric(
            "Metrics available",
            (
                f"{trends.get('available_metrics', 0)}"
                f"/{trends.get('total_metrics', 0)}"
            ),
        )

        st.metric(
            "Metric availability",
            f"{metric_availability}%",
        )

    with right:
        st.metric(
            "Average data coverage",
            f"{average_coverage}%",
        )

        st.metric(
            "Fresh metrics",
            trends.get(
                "fresh_metrics",
                0,
            ),
        )

    st.caption(
        "Phoenix compares recent averages with previous periods and "
        "your available longer-term baseline. Metric-specific thresholds "
        "prevent small normal fluctuations from being treated as meaningful."
    )


# ---------------------------------------------------------------------
# Recovery overview
# ---------------------------------------------------------------------

render_recovery_signals(
    trends
)


# ---------------------------------------------------------------------
# Quick overview
# ---------------------------------------------------------------------

st.divider()
st.subheader(
    "At a glance"
)

overview_columns = st.columns(
    4
)

with overview_columns[0]:
    st.metric(
        "Tracked health metrics",
        overall.get(
            "available_count",
            0,
        ),
    )

with overview_columns[1]:
    st.metric(
        "Improving",
        overall.get(
            "improving_count",
            0,
        ),
    )

with overview_columns[2]:
    st.metric(
        "Stable",
        overall.get(
            "stable_count",
            0,
        ),
    )

with overview_columns[3]:
    st.metric(
        "Needs attention",
        overall.get(
            "worsening_count",
            0,
        ),
    )


# ---------------------------------------------------------------------
# Health and context sections
# ---------------------------------------------------------------------

for group in GROUP_DISPLAY:
    render_group_section(
        group_key=group["key"],
        title=group["title"],
        caption=group["caption"],
        trends=trends,
    )


# ---------------------------------------------------------------------
# Method and footer
# ---------------------------------------------------------------------

st.divider()

with st.expander(
    "How Phoenix calculates these trends"
):
    st.write(
        "Phoenix first converts stored measurements into one value "
        "per day. Weight and body-composition measurements use the "
        "last reading of the day, while metrics such as HRV, wrist "
        "temperature and resting heart rate use a daily average."
    )

    st.write(
        "The engine calculates recent seven-day averages, 28-day "
        "averages and longer personal baselines where enough history "
        "is available."
    )

    st.write(
        "Each metric has its own meaningful-change threshold. This "
        "prevents small fluctuations such as a few minutes of sleep, "
        "a tiny wrist-temperature change or one millisecond of HRV "
        "from automatically being described as improving or worsening."
    )

    st.write(
        "Sleep consistency is calculated from the rolling seven-day "
        "variation in total sleep duration. A lower value means your "
        "sleep duration has been more consistent."
    )

    st.write(
        "Wrist temperature is most useful as a change relative to your "
        "own baseline rather than as a standalone body-temperature reading."
    )

    st.write(
        "Data freshness and coverage affect confidence. A metric may "
        "have historical data but still be marked as stale if its "
        "latest reading is too old."
    )

    st.write(
        "Trend direction is not the same as a medical judgement. "
        "Recovery signals should be interpreted together and alongside "
        "health history, training load, symptoms and clinical advice."
    )

st.caption(
    f"{PHOENIX_VERSION_LABEL} · "
    f"Health Trends generated from "
    f"{trends.get('available_metrics', 0)} available metric(s)"
)