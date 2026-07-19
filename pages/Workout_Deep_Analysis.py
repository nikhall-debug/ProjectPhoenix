from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from integrations.xert import fetch_and_stage_xert_activities
from workout_deep_analysis import (
    apple_timeline_from_raw,
    match_score,
    merge_timelines,
    metric_label,
    parse_datetime,
    parse_fit_file,
    summary_from_merged,
    xert_summary_from_raw,
    xert_timeline_from_raw,
)
from workout_intelligent_summary import (
    build_intelligent_workout_summary,
    build_route_aware_tab_insights,
)
from workout_staging import (
    finalise_pending_session,
    get_pending_session,
    init_workout_staging_tables,
    friendly_pending_status,
    load_analysed_pending_sessions,
    load_source_files_for_pending,
    load_unanalysed_pending_sessions,
    save_source_file,
)


st.set_page_config(
    page_title="Workout Deep Analysis",
    page_icon="🔬",
    layout="wide",
)

init_workout_staging_tables()

st.title("🔬 Workout Deep Analysis")
st.caption(
    "Review every workout still needing analysis, attach supplementary files, "
    "or reopen an older completed workout whenever you like."
)


def render_tab_guidance(
    domain_insights: dict,
    domain: str,
) -> None:
    insight = domain_insights.get(domain) or {}
    good = insight.get("good") or {}
    watch = insight.get("watch")
    evidence = insight.get("evidence") or []

    if good:
        st.success(
            f"**What looks good — {good.get('title', '')}**\n\n"
            f"{good.get('body', '')}"
        )

    if watch:
        st.warning(
            f"**Worth watching — {watch.get('title', '')}**\n\n"
            f"{watch.get('body', '')}"
        )
    else:
        st.caption(
            "Phoenix did not identify a separate concern in this domain after "
            "accounting for workload, elevation, descents and recovery phases."
        )

    if evidence:
        st.caption("Route context: " + " · ".join(evidence))


def render_chart(df: pd.DataFrame, metrics: list[str], title: str) -> None:
    usable = [m for m in metrics if m in df and df[m].notna().any()]
    if not usable:
        st.info("No data are available for this graph yet.")
        return

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for index, metric in enumerate(usable):
        fig.add_trace(
            go.Scatter(
                x=df["elapsed_minutes"],
                y=df[metric],
                mode="lines",
                name=metric_label(metric),
                connectgaps=False,
            ),
            secondary_y=index > 0,
        )

    fig.update_layout(
        title=title,
        height=430,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.05),
        margin=dict(l=20, r=20, t=80, b=20),
    )
    fig.update_xaxes(title_text="Elapsed time (minutes)")
    fig.update_yaxes(title_text=metric_label(usable[0]), secondary_y=False)
    if len(usable) > 1:
        fig.update_yaxes(title_text="Additional metrics", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)


def _normalise_for_signature(value: Any) -> bytes:
    """Produce stable bytes for cache invalidation without parsing the data."""
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8", errors="replace")
    try:
        return json.dumps(value, sort_keys=True, default=str).encode("utf-8")
    except (TypeError, ValueError):
        return repr(value).encode("utf-8", errors="replace")


def _analysis_signature(pending: dict, stored_files: pd.DataFrame) -> str:
    """
    Invalidate the cached analysis only when the selected workout or one of its
    attached files has genuinely changed.
    """
    digest = hashlib.sha256()
    for key in (
        "id",
        "status",
        "start_time",
        "end_time",
        "primary_source",
        "xert_raw_data",
        "apple_raw_data",
    ):
        digest.update(key.encode("utf-8"))
        digest.update(_normalise_for_signature(pending.get(key)))

    if not stored_files.empty:
        for _, row in stored_files.sort_values(
            by=["source_type", "original_filename"]
        ).iterrows():
            path = Path(row["stored_path"])
            digest.update(_normalise_for_signature(row.get("source_type")))
            digest.update(_normalise_for_signature(row.get("original_filename")))
            digest.update(_normalise_for_signature(str(path)))
            try:
                stat = path.stat()
                digest.update(str(stat.st_size).encode("ascii"))
                digest.update(str(stat.st_mtime_ns).encode("ascii"))
            except OSError:
                digest.update(b"missing")

    return digest.hexdigest()


@st.cache_data(show_spinner="Preparing workout analysis…", max_entries=20)
def _build_analysis_bundle(
    pending_id: int,
    signature: str,
) -> dict[str, Any]:
    """
    Heavy analysis path.

    Streamlit re-runs the script for every widget interaction. Caching this
    bundle prevents FIT files, Xert/Apple timelines, merged data and coaching
    interpretation from being rebuilt unless the workout inputs changed.
    """
    del signature  # Used solely as the cache-invalidation key.

    pending = get_pending_session(pending_id)
    workout_start = parse_datetime(pending["start_time"])
    workout_end = parse_datetime(pending["end_time"])
    if workout_start is None or workout_end is None:
        raise ValueError("This staged workout does not have valid start and end times.")

    parsed_sources = []
    stored_files = load_source_files_for_pending(pending_id)
    for _, file_row in stored_files.iterrows():
        path = Path(file_row["stored_path"])
        if not path.exists():
            continue
        try:
            parsed_sources.append(
                (
                    file_row["source_type"],
                    parse_fit_file(
                        path.read_bytes(),
                        file_row["original_filename"],
                    ),
                )
            )
        except Exception:
            # A damaged supplementary file should not prevent the base workout
            # from opening.
            continue

    xert_df = xert_timeline_from_raw(pending.get("xert_raw_data"))
    apple_df = apple_timeline_from_raw(
        pending.get("apple_raw_data"),
        pending["start_time"],
        pending["end_time"],
    )
    merged = merge_timelines(
        workout_start,
        workout_end,
        xert_df,
        apple_df,
        parsed_sources,
    )
    xert_summary = xert_summary_from_raw(pending.get("xert_raw_data"))
    summary = summary_from_merged(merged)

    intelligent_summary = build_intelligent_workout_summary(
        pending=pending,
        merged=merged,
        summary=summary,
        xert_summary=xert_summary,
    )
    domain_insights = build_route_aware_tab_insights(
        merged=merged,
        summary=summary,
        coach_summary=intelligent_summary,
    )

    return {
        "pending": pending,
        "workout_start": workout_start,
        "workout_end": workout_end,
        "stored_files": stored_files,
        "xert_df": xert_df,
        "merged": merged,
        "xert_summary": xert_summary,
        "summary": summary,
        "intelligent_summary": intelligent_summary,
        "domain_insights": domain_insights,
    }


sync_col, info_col = st.columns([1, 2])
with sync_col:
    if st.button("Sync Xert workouts", use_container_width=True):
        with st.spinner("Checking Xert for cycling workouts…"):
            result = fetch_and_stage_xert_activities(days=60, limit=10)
        if result.get("error"):
            st.error(result["error"])
        else:
            _build_analysis_bundle.clear()
            st.success(
                f"Xert sync complete: {result['staged']} newly staged, "
                f"{result['updated']} matched to existing pending workouts; "
                f"{result.get('detailed', 0)} detailed Xert activities loaded."
            )
            st.rerun()

with info_col:
    st.info(
        "Apple workouts enter this queue when the normal Apple Health sync runs. "
        "Neither Apple nor Xert is finalised until you approve it here."
    )

pending_df = load_unanalysed_pending_sessions()

st.subheader(f"Needs analysis ({len(pending_df)})")
selected_id = None

if pending_df.empty:
    st.success("Nothing is currently waiting for analysis.")
else:
    pending_lookup = pending_df.set_index("id").to_dict("index")
    options = [int(value) for value in pending_df["id"].tolist()]
    selected_id = st.radio(
        "Workout requiring analysis",
        options,
        format_func=lambda pending_id: (
            f"{pending_lookup[pending_id]['session_date']} · "
            f"{pending_lookup[pending_id]['session_type']} · "
            f"{float(pending_lookup[pending_id]['duration_minutes'] or 0):.1f} min · "
            f"{friendly_pending_status(pending_lookup[pending_id]['status'])}"
        ),
        label_visibility="collapsed",
    )

browse_completed = st.toggle(
    "Browse analysed workouts",
    value=pending_df.empty,
    help=(
        "Completed-workout filters are loaded only while this is open, which "
        "keeps the normal pending-workout view faster."
    ),
)

if browse_completed:
    filter_cols = st.columns([1, 2, 1])
    completed_type = filter_cols[0].selectbox(
        "Workout type",
        ["All", "Cycling", "Walking", "Strength", "Other"],
        key="completed_type",
    )
    completed_search = filter_cols[1].text_input(
        "Search title",
        placeholder="e.g. Lanzarote",
        key="completed_search",
    )
    completed_limit = filter_cols[2].selectbox(
        "Show",
        [20, 50, 100, 250],
        index=1,
        key="completed_limit",
    )

    completed_df = load_analysed_pending_sessions(
        limit=completed_limit,
        session_type=completed_type,
        title_query=completed_search,
    )

    if completed_df.empty:
        st.caption("No analysed workouts match these filters.")
    else:
        completed_lookup = completed_df.set_index("id").to_dict("index")
        completed_options = [int(value) for value in completed_df["id"].tolist()]
        completed_choice = st.selectbox(
            "Previously analysed workout",
            completed_options,
            index=None,
            placeholder="Choose a completed workout to reopen",
            format_func=lambda pending_id: (
                f"{completed_lookup[pending_id]['session_date']} · "
                f"{completed_lookup[pending_id]['title'] or completed_lookup[pending_id]['session_type']} · "
                f"{float(completed_lookup[pending_id]['duration_minutes'] or 0):.1f} min"
            ),
            label_visibility="collapsed",
        )
        if completed_choice is not None:
            selected_id = int(completed_choice)

if selected_id is None:
    st.info("Select a workout above to begin.")
    st.stop()

pending = get_pending_session(selected_id)
workout_start = parse_datetime(pending["start_time"])
workout_end = parse_datetime(pending["end_time"])

if workout_start is None or workout_end is None:
    st.error("This staged workout does not have valid start and end times.")
    st.stop()

st.divider()
st.subheader(pending.get("title") or pending["session_type"])

upload_left, upload_right = st.columns(2)
with upload_left:
    tyme_upload = st.file_uploader(
        "Tymewear FIT",
        type=["fit"],
        key=f"tyme_{selected_id}",
    )
with upload_right:
    wahoo_upload = st.file_uploader(
        "Wahoo FIT — CORE temperature only",
        type=["fit"],
        key=f"wahoo_{selected_id}",
        help=(
            "Phoenix ignores Wahoo power, HR, cadence and speed; "
            "only temperature fields are used."
        ),
    )

for source_type, upload in (("Tymewear", tyme_upload), ("Wahoo", wahoo_upload)):
    if upload is None:
        continue

    file_bytes = upload.getvalue()
    upload_marker = hashlib.sha256(file_bytes).hexdigest()
    state_key = f"processed_upload_{selected_id}_{source_type}"

    # File uploaders retain their value across reruns. This guard prevents the
    # same FIT file being parsed and saved repeatedly when another widget moves.
    if st.session_state.get(state_key) == upload_marker:
        continue

    try:
        parsed = parse_fit_file(file_bytes, upload.name)
    except Exception as exc:
        st.error(f"Could not read {source_type}: {exc}")
        st.session_state[state_key] = upload_marker
        continue

    score = match_score(workout_start, workout_end, parsed)
    result = save_source_file(
        pending_session_id=selected_id,
        source_type=source_type,
        filename=upload.name,
        file_bytes=file_bytes,
        start_time=parsed.start.isoformat() if parsed.start else None,
        end_time=parsed.end.isoformat() if parsed.end else None,
        duration_seconds=parsed.duration_seconds,
        match_score=score,
        available_metrics=parsed.metrics,
    )
    st.session_state[state_key] = upload_marker

    if result["saved"]:
        _build_analysis_bundle.clear()
        st.success(f"{source_type} file attached ({score:.0%} timeline match).")
    else:
        st.info(f"{source_type} file is already attached.")

    with st.expander(f"{source_type} FIT diagnostics"):
        st.write(f"Device: {parsed.device_name or 'Not identified'}")
        st.write(f"Timeline match: {score:.0%}")
        st.write("Detected metrics:", ", ".join(parsed.metrics) or "None")
        st.code(", ".join(parsed.raw_fields) or "No FIT fields detected")

    if result["saved"]:
        st.rerun()

stored_files = load_source_files_for_pending(selected_id)
signature = _analysis_signature(pending, stored_files)

try:
    bundle = _build_analysis_bundle(selected_id, signature)
except Exception as exc:
    st.error(f"Phoenix could not prepare this workout: {exc}")
    st.stop()

pending = bundle["pending"]
xert_df = bundle["xert_df"]
merged = bundle["merged"]
xert_summary = bundle["xert_summary"]
summary = bundle["summary"]
intelligent_summary = bundle["intelligent_summary"]
domain_insights = bundle["domain_insights"]

if pending.get("primary_source") == "Xert":
    if xert_df.empty:
        st.warning(
            "Xert supplied the workout summary, but Phoenix could not find a "
            "detailed Xert timeline in the response. Try Sync Xert workouts again."
        )
    else:
        st.success(f"Detailed Xert timeline loaded: {len(xert_df):,} samples.")

top_metrics = st.columns(4)
top_metrics[0].metric(
    "Duration",
    f"{float(pending['duration_minutes'] or 0):.1f} min",
)
top_metrics[1].metric(
    "Distance",
    f"{summary['total_distance_km']:.1f} km"
    if "total_distance_km" in summary
    else "—",
)
top_metrics[2].metric(
    "Average speed",
    f"{summary['avg_speed_kmh']:.1f} km/h"
    if "avg_speed_kmh" in summary
    else "—",
)
top_metrics[3].metric(
    "Average power",
    f"{summary['avg_power']:.0f} W"
    if "avg_power" in summary
    else "—",
)

bottom_metrics = st.columns(4)
bottom_metrics[0].metric(
    "Average HR",
    f"{summary['avg_heart_rate']:.0f} bpm"
    if "avg_heart_rate" in summary
    else "—",
)
bottom_metrics[1].metric(
    "Average breathing",
    f"{summary['avg_breathing_rate']:.1f}/min"
    if "avg_breathing_rate" in summary
    else "—",
)
bottom_metrics[2].metric(
    "Max CORE",
    f"{summary['max_core_temperature_c']:.2f} °C"
    if "max_core_temperature_c" in summary
    else "—",
)
bottom_metrics[3].metric(
    "Elevation gain",
    f"{summary['elevation_gain_m']:.0f} m"
    if "elevation_gain_m" in summary
    else "—",
)

if xert_summary:
    with st.expander("Xert workout summary", expanded=False):
        useful_xert = {
            key: value
            for key, value in xert_summary.items()
            if key
            in {
                "focus",
                "specificity",
                "difficulty",
                "xss",
                "distance",
                "elevation_gain",
                "duration",
                "avg_power",
                "max_power",
            }
            and value not in (None, "", [], {})
        }
        st.json(useful_xert or xert_summary)

st.subheader("Phoenix Coach")
st.caption(
    f"Interpreted in the context of {pending['session_date']} · "
    f"{intelligent_summary['confidence_label']} confidence "
    f"({intelligent_summary['confidence']}%)"
)

coach_sections = [
    ("🎯", intelligent_summary["goal_assessment"]),
    ("🔍", intelligent_summary["phoenix_noticed"]),
    ("📈", intelligent_summary["bigger_picture"]),
    ("➡️", intelligent_summary["next_step"]),
    ("🔭", intelligent_summary["looking_ahead"]),
]

for icon, section in coach_sections:
    st.markdown(f"### {icon} {section['title']}")
    st.write(section["body"])

if intelligent_summary.get("watchouts"):
    st.warning(
        "Worth watching: " + "; ".join(intelligent_summary["watchouts"])
    )
elif intelligent_summary.get("positives"):
    st.success(
        "What went well: " + "; ".join(intelligent_summary["positives"])
    )

if st.toggle("Show why Phoenix reached this interpretation", value=False):
    st.markdown("**Timeline signals**")
    st.json(intelligent_summary.get("signals") or {})
    st.markdown("**Route-aware events**")
    st.json(domain_insights.get("_analysis") or {})
    personal_baseline = (
        intelligent_summary.get("context", {}).get("personal_baseline") or {}
    )
    if personal_baseline:
        st.markdown("**Personal comparison set**")
        st.write(
            f"{personal_baseline.get('sample_size', 0)} previously analysed "
            "workouts of the same type were available before this session."
        )
        st.json(personal_baseline.get("medians") or {})
    st.markdown("**Historical context**")
    st.json(intelligent_summary["context"])

st.subheader("Explore the evidence")

view_labels = {
    "Overview": (
        "overview",
        ["speed_kmh", "power", "heart_rate", "breathing_rate"],
        "Workout overview",
    ),
    "Respiration": (
        "respiration",
        ["breathing_rate", "minute_ventilation", "tidal_volume"],
        "Respiratory response",
    ),
    "Cardiovascular": (
        "cardiovascular",
        ["heart_rate", "power", "speed_kmh", "cadence"],
        "Cardiovascular response",
    ),
    "Thermal": (
        "thermal",
        ["core_temperature_c", "heart_rate", "breathing_rate"],
        "Thermal response",
    ),
    "Efficiency": (
        "efficiency",
        [
            "speed_kmh",
            "power",
            "heart_rate",
            "breathing_rate",
            "minute_ventilation",
        ],
        "Efficiency and drift",
    ),
    "Elevation": (
        "elevation",
        ["altitude_m", "speed_kmh", "heart_rate"],
        "Elevation response",
    ),
    "Route": ("route", [], "Route"),
}

selected_view = st.radio(
    "Evidence view",
    list(view_labels),
    horizontal=True,
    label_visibility="collapsed",
    key=f"evidence_view_{selected_id}",
)
domain, metrics, chart_title = view_labels[selected_view]
render_tab_guidance(domain_insights, domain)

if selected_view == "Route":
    route_columns = [
        column
        for column in ("latitude", "longitude")
        if column in merged
    ]
    route = merged[route_columns].copy()
    if {"latitude", "longitude"}.issubset(route.columns):
        route["latitude"] = pd.to_numeric(route["latitude"], errors="coerce")
        route["longitude"] = pd.to_numeric(route["longitude"], errors="coerce")
        route = route.dropna()
        route = route[
            route["latitude"].between(-90, 90)
            & route["longitude"].between(-180, 180)
        ]
        if not route.empty:
            st.map(
                route.rename(
                    columns={"latitude": "lat", "longitude": "lon"}
                )
            )
        else:
            st.info("No usable route coordinates are available for this workout.")
    else:
        st.info("No route coordinates are available for this workout.")
else:
    render_chart(merged, metrics, chart_title)

if st.toggle("Build a custom graph", value=False):
    numeric_metrics = [
        column
        for column in merged.select_dtypes(include="number").columns
        if column != "elapsed_minutes" and merged[column].notna().any()
    ]
    chosen = st.multiselect(
        "Metrics",
        numeric_metrics,
        default=numeric_metrics[:3],
        format_func=metric_label,
    )
    if chosen:
        render_chart(merged, chosen[:5], "Custom workout graph")

st.divider()

if pending["status"] == "analysed":
    st.success(
        f"This workout is analysed and saved as training session "
        f"{pending['final_session_id']}. You can revisit its interpretation at any time."
    )
else:
    if st.button(
        "Merge, save graphs and finalise workout",
        type="primary",
        use_container_width=True,
    ):
        graph_config = {
            "available_metrics": [
                column
                for column in merged.columns
                if column not in {"timestamp", "elapsed_minutes"}
                and merged[column].notna().any()
            ],
            "default_tabs": [
                "Overview",
                "Respiration",
                "Cardiovascular",
                "Thermal",
                "Efficiency",
                "Elevation",
            ],
        }

        summary_to_save = dict(summary)
        summary_to_save["intelligent_summary"] = intelligent_summary

        result = finalise_pending_session(
            pending_id=selected_id,
            merged_timeline=merged,
            summary=summary_to_save,
            graph_config=graph_config,
        )
        _build_analysis_bundle.clear()
        st.success(
            f"Workout finalised as Phoenix training session "
            f"{result['session_id']}."
        )
        st.rerun()
