from datetime import date, datetime, time
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import streamlit as st

from database import (
    delete_life_event,
    get_life_event,
    init_db,
    load_life_events,
    load_life_events_between,
    save_life_event,
    update_life_event,
)
from version import PHOENIX_VERSION_LABEL


# ---------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="Timeline · Project Phoenix",
    page_icon="📖",
    layout="wide",
)

init_db()

st.title("📖 Timeline")
st.caption(
    "Record the events that give your health, recovery and training "
    "data real-world context."
)


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

EVENT_CATEGORIES = [
    "Medical",
    "Illness",
    "Recovery",
    "Training",
    "Nutrition",
    "Medication",
    "Sleep",
    "Work",
    "Lifestyle",
    "Travel",
    "Equipment",
    "Milestone",
    "Other",
]

EVENT_SEVERITIES = [
    "Info",
    "Minor",
    "Moderate",
    "Major",
    "Critical",
]

EVENT_SOURCES = [
    "manual",
    "automatic",
    "coach",
    "apple_health",
    "withings",
    "xert",
]

EVENT_DURATION_TYPES = [
    "One-day event",
    "Date range",
    "Ongoing",
]

CATEGORY_ICONS = {
    "Medical": "🏥",
    "Illness": "🤒",
    "Recovery": "🌱",
    "Training": "🚴",
    "Nutrition": "🥗",
    "Medication": "💊",
    "Sleep": "😴",
    "Work": "💼",
    "Lifestyle": "🏠",
    "Travel": "✈️",
    "Equipment": "🛠️",
    "Milestone": "🏆",
    "Other": "📌",
}

SEVERITY_ICONS = {
    "Info": "⚪",
    "Minor": "🔵",
    "Moderate": "🟡",
    "Major": "🟠",
    "Critical": "🔴",
}


# ---------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------

def clean_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def category_icon(category: str) -> str:
    return CATEGORY_ICONS.get(
        category,
        "📌",
    )


def severity_icon(severity: str) -> str:
    return SEVERITY_ICONS.get(
        severity,
        "⚪",
    )


def parse_event_date(
    value: Any,
    default: Optional[date] = None,
) -> date:
    if default is None:
        default = date.today()

    if value is None:
        return default

    try:
        parsed = pd.to_datetime(
            value,
            errors="coerce",
        )

        if pd.isna(parsed):
            return default

        return parsed.date()

    except Exception:
        return default


def parse_optional_event_date(
    value: Any,
) -> Optional[date]:
    clean_value = clean_text(
        value
    )

    if not clean_value:
        return None

    try:
        parsed = pd.to_datetime(
            clean_value,
            errors="coerce",
        )

        if pd.isna(parsed):
            return None

        return parsed.date()

    except Exception:
        return None


def parse_event_time(
    value: Any,
) -> time:
    clean_value = clean_text(
        value
    )

    if not clean_value:
        return time(
            hour=12,
            minute=0,
        )

    try:
        return datetime.strptime(
            clean_value,
            "%H:%M",
        ).time()

    except ValueError:
        return time(
            hour=12,
            minute=0,
        )


def determine_duration_type(
    start_date_value: Any,
    end_date_value: Any,
) -> str:
    start = parse_event_date(
        start_date_value
    )

    end = parse_optional_event_date(
        end_date_value
    )

    if end is None:
        return "Ongoing"

    if end == start:
        return "One-day event"

    return "Date range"


def resolve_event_dates(
    duration_type: str,
    start_date_value: date,
    range_end_date: Optional[date] = None,
) -> Tuple[date, Optional[date]]:
    if duration_type == "One-day event":
        return (
            start_date_value,
            start_date_value,
        )

    if duration_type == "Ongoing":
        return (
            start_date_value,
            None,
        )

    if range_end_date is None:
        raise ValueError(
            "Please select an end date."
        )

    if range_end_date < start_date_value:
        raise ValueError(
            "The end date cannot be before the start date."
        )

    return (
        start_date_value,
        range_end_date,
    )


def format_event_period(
    event: Dict[str, Any],
) -> str:
    start_date_value = (
        event.get("start_date")
        or event.get("event_date")
    )

    end_date_value = event.get(
        "end_date"
    )

    start_date_parsed = parse_event_date(
        start_date_value
    )

    end_date_parsed = parse_optional_event_date(
        end_date_value
    )

    start_text = start_date_parsed.strftime(
        "%d %b %Y"
    )

    if end_date_parsed is None:
        return f"{start_text} – Ongoing"

    if end_date_parsed == start_date_parsed:
        return start_text

    if (
        start_date_parsed.year
        == end_date_parsed.year
    ):
        if (
            start_date_parsed.month
            == end_date_parsed.month
        ):
            return (
                f"{start_date_parsed.strftime('%d')}–"
                f"{end_date_parsed.strftime('%d %b %Y')}"
            )

        return (
            f"{start_date_parsed.strftime('%d %b')} – "
            f"{end_date_parsed.strftime('%d %b %Y')}"
        )

    return (
        f"{start_date_parsed.strftime('%d %b %Y')} – "
        f"{end_date_parsed.strftime('%d %b %Y')}"
    )


def event_option_label(
    event: Dict[str, Any],
) -> str:
    period_text = format_event_period(
        event
    )

    event_time = clean_text(
        event.get("event_time")
    )

    title = clean_text(
        event.get("title")
    )

    category = clean_text(
        event.get("category")
    )

    time_text = (
        f" · {event_time}"
        if event_time
        else ""
    )

    return (
        f"{period_text}{time_text} · "
        f"{category_icon(category)} {title}"
    )


def reset_add_event_form() -> None:
    keys_to_remove = [
        "new_event_duration_type",
        "new_event_start_date",
        "new_event_end_date",
        "new_event_has_time",
        "new_event_time",
        "new_event_title",
        "new_event_category",
        "new_event_severity",
        "new_event_description",
        "new_event_tags",
    ]

    for key in keys_to_remove:
        st.session_state.pop(
            key,
            None,
        )


def display_event_card(
    event: Dict[str, Any],
) -> None:
    event_time = clean_text(
        event.get("event_time")
    )

    title = clean_text(
        event.get("title")
    )

    category = clean_text(
        event.get("category")
    )

    severity = clean_text(
        event.get("severity")
    )

    description = clean_text(
        event.get("description")
    )

    tags = clean_text(
        event.get("tags")
    )

    source = clean_text(
        event.get("source")
    )

    period_text = format_event_period(
        event
    )

    if event_time:
        period_text += f" · {event_time}"

    with st.container(
        border=True
    ):
        heading_col, severity_col = st.columns(
            [4, 1]
        )

        with heading_col:
            st.markdown(
                f"### {category_icon(category)} {title}"
            )

            st.caption(
                f"{period_text} · {category}"
            )

        with severity_col:
            st.write(
                f"**{severity_icon(severity)} {severity}**"
            )

        if description:
            st.write(
                description
            )

        detail_parts = []

        if tags:
            detail_parts.append(
                f"Tags: {tags}"
            )

        if source:
            detail_parts.append(
                f"Source: {source}"
            )

        if detail_parts:
            st.caption(
                " · ".join(
                    detail_parts
                )
            )


# ---------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------

add_tab, timeline_tab, manage_tab = st.tabs(
    [
        "➕ Add Event",
        "📅 Timeline",
        "✏️ Edit or Delete",
    ]
)


# ---------------------------------------------------------------------
# Add event
# ---------------------------------------------------------------------

with add_tab:
    st.subheader(
        "Add a timeline event"
    )

    st.caption(
        "Use a one-day event for a single occurrence, a date range "
        "for a defined period, or ongoing when the event is still active."
    )

    add_col1, add_col2 = st.columns(
        2
    )

    with add_col1:
        new_duration_type = st.radio(
            "Event duration",
            options=EVENT_DURATION_TYPES,
            horizontal=True,
            key="new_event_duration_type",
        )

        new_start_date = st.date_input(
            "Start date",
            value=date.today(),
            max_value=date.today(),
            key="new_event_start_date",
        )

        new_end_date: Optional[date] = None

        if new_duration_type == "Date range":
            new_end_date = st.date_input(
                "End date",
                value=date.today(),
                min_value=new_start_date,
                key="new_event_end_date",
            )

        elif new_duration_type == "Ongoing":
            st.info(
                "This event will remain active until you add an end date."
            )

        new_event_has_time = st.checkbox(
            "Include an event time",
            value=False,
            key="new_event_has_time",
        )

        new_event_time: Optional[time] = None

        if new_event_has_time:
            new_event_time = st.time_input(
                "Event time",
                value=datetime.now().replace(
                    second=0,
                    microsecond=0,
                ).time(),
                step=300,
                key="new_event_time",
            )

        new_event_category = st.selectbox(
            "Category",
            EVENT_CATEGORIES,
            index=0,
            key="new_event_category",
        )

        new_event_severity = st.selectbox(
            "Importance",
            EVENT_SEVERITIES,
            index=2,
            key="new_event_severity",
        )

    with add_col2:
        new_event_title = st.text_input(
            "Event title",
            placeholder="For example: Post-surgery recovery phase",
            key="new_event_title",
        )

        new_event_description = st.text_area(
            "Description",
            placeholder=(
                "Optional details that may help Phoenix understand "
                "the event later..."
            ),
            height=160,
            key="new_event_description",
        )

        new_event_tags = st.text_input(
            "Tags",
            placeholder="surgery, hospital, recovery",
            key="new_event_tags",
        )

        st.caption(
            "Separate tags with commas."
        )

    if st.button(
        "💾 Save event",
        type="primary",
        key="save_new_life_event",
    ):
        if not clean_text(
            new_event_title
        ):
            st.error(
                "Please enter an event title."
            )

        else:
            try:
                resolved_start_date, resolved_end_date = (
                    resolve_event_dates(
                        duration_type=new_duration_type,
                        start_date_value=new_start_date,
                        range_end_date=new_end_date,
                    )
                )

                inserted = save_life_event(
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                    event_time=new_event_time,
                    title=new_event_title,
                    category=new_event_category,
                    severity=new_event_severity,
                    description=new_event_description,
                    tags=new_event_tags,
                    source="manual",
                )

                if inserted:
                    st.success(
                        f"✅ Saved: {new_event_title}"
                    )

                    reset_add_event_form()
                    st.rerun()

                else:
                    st.warning(
                        "An identical event already exists."
                    )

            except ValueError as error:
                st.error(
                    str(error)
                )

            except Exception as error:
                st.error(
                    "Phoenix could not save the event."
                )

                st.exception(
                    error
                )


# ---------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------

with timeline_tab:
    all_events = load_life_events()

    st.subheader(
        "Your timeline"
    )

    if all_events.empty:
        st.info(
            "No timeline events have been recorded yet. "
            "Add your first event in the Add Event tab."
        )

    else:
        all_events = all_events.copy()

        all_events["start_date_parsed"] = pd.to_datetime(
            all_events["start_date"].fillna(
                all_events["event_date"]
            ),
            errors="coerce",
        )

        all_events["end_date_parsed"] = pd.to_datetime(
            all_events["end_date"],
            errors="coerce",
        )

        all_events = all_events.dropna(
            subset=["start_date_parsed"]
        )

        filter_col1, filter_col2, filter_col3 = st.columns(
            3
        )

        earliest_date = (
            all_events["start_date_parsed"]
            .min()
            .date()
        )

        latest_known_date = (
            all_events["end_date_parsed"]
            .dropna()
            .max()
        )

        if pd.isna(
            latest_known_date
        ):
            latest_date = date.today()
        else:
            latest_date = max(
                latest_known_date.date(),
                date.today(),
            )

        with filter_col1:
            timeline_date_range = st.date_input(
                "Date range",
                value=(
                    earliest_date,
                    latest_date,
                ),
                min_value=earliest_date,
                max_value=latest_date,
                key="timeline_date_range",
            )

        with filter_col2:
            available_categories = sorted(
                all_events["category"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            selected_categories = st.multiselect(
                "Categories",
                options=available_categories,
                default=available_categories,
                key="timeline_categories",
            )

        with filter_col3:
            search_text = st.text_input(
                "Search",
                placeholder="Search titles, descriptions or tags",
                key="timeline_search",
            )

        if (
            isinstance(
                timeline_date_range,
                tuple,
            )
            and len(
                timeline_date_range
            ) == 2
        ):
            range_start, range_end = timeline_date_range

        else:
            range_start = timeline_date_range
            range_end = timeline_date_range

        filtered_events = load_life_events_between(
            start_date=range_start,
            end_date=range_end,
        )

        if selected_categories:
            filtered_events = filtered_events[
                filtered_events["category"].isin(
                    selected_categories
                )
            ]
        else:
            filtered_events = filtered_events.iloc[
                0:0
            ]

        clean_search = clean_text(
            search_text
        ).lower()

        if clean_search:
            searchable_text = (
                filtered_events["title"]
                .fillna("")
                .astype(str)
                + " "
                + filtered_events["description"]
                .fillna("")
                .astype(str)
                + " "
                + filtered_events["tags"]
                .fillna("")
                .astype(str)
                + " "
                + filtered_events["category"]
                .fillna("")
                .astype(str)
            ).str.lower()

            filtered_events = filtered_events[
                searchable_text.str.contains(
                    clean_search,
                    regex=False,
                )
            ]

        st.caption(
            f"{len(filtered_events)} event(s) shown"
        )

        if filtered_events.empty:
            st.info(
                "No events match the selected filters."
            )

        else:
            filtered_events = filtered_events.copy()

            filtered_events["start_date_parsed"] = pd.to_datetime(
                filtered_events["start_date"].fillna(
                    filtered_events["event_date"]
                ),
                errors="coerce",
            )

            filtered_events = filtered_events.sort_values(
                [
                    "start_date_parsed",
                    "event_time",
                    "id",
                ],
                ascending=[
                    False,
                    False,
                    False,
                ],
            )

            filtered_events["month_group"] = (
                filtered_events["start_date_parsed"]
                .dt.strftime(
                    "%B %Y"
                )
            )

            for month_name, month_events in filtered_events.groupby(
                "month_group",
                sort=False,
            ):
                st.markdown(
                    f"## {month_name}"
                )

                for _, row in month_events.iterrows():
                    display_event_card(
                        row.to_dict()
                    )


# ---------------------------------------------------------------------
# Edit or delete
# ---------------------------------------------------------------------

with manage_tab:
    st.subheader(
        "Edit or delete an event"
    )

    manage_events = load_life_events()

    if manage_events.empty:
        st.info(
            "There are no events available to edit."
        )

    else:
        event_records = manage_events.to_dict(
            orient="records"
        )

        event_lookup = {
            int(event["id"]): event
            for event in event_records
        }

        selected_event_id = st.selectbox(
            "Choose an event",
            options=list(
                event_lookup.keys()
            ),
            format_func=lambda event_id: event_option_label(
                event_lookup[event_id]
            ),
            key="selected_life_event_id",
        )

        selected_event = get_life_event(
            selected_event_id
        )

        if selected_event is None:
            st.error(
                "That event could not be found."
            )

        else:
            selected_start_date = parse_event_date(
                selected_event.get("start_date")
                or selected_event.get("event_date")
            )

            selected_end_date = parse_optional_event_date(
                selected_event.get("end_date")
            )

            stored_duration_type = determine_duration_type(
                selected_start_date,
                selected_end_date,
            )

            selected_category = clean_text(
                selected_event.get("category")
            )

            selected_severity = clean_text(
                selected_event.get("severity")
            )

            selected_source = clean_text(
                selected_event.get("source")
            )

            category_options = EVENT_CATEGORIES.copy()

            if (
                selected_category
                and selected_category not in category_options
            ):
                category_options.append(
                    selected_category
                )

            severity_options = EVENT_SEVERITIES.copy()

            if (
                selected_severity
                and selected_severity not in severity_options
            ):
                severity_options.append(
                    selected_severity
                )

            source_options = EVENT_SOURCES.copy()

            if (
                selected_source
                and selected_source not in source_options
            ):
                source_options.append(
                    selected_source
                )

            stored_event_time = clean_text(
                selected_event.get("event_time")
            )

            edit_col1, edit_col2 = st.columns(
                2
            )

            with edit_col1:
                edit_duration_type = st.radio(
                    "Event duration",
                    options=EVENT_DURATION_TYPES,
                    index=EVENT_DURATION_TYPES.index(
                        stored_duration_type
                    ),
                    horizontal=True,
                    key=f"edit_duration_type_{selected_event_id}",
                )

                edit_start_date = st.date_input(
                    "Start date",
                    value=selected_start_date,
                    max_value=date.today(),
                    key=f"edit_start_date_{selected_event_id}",
                )

                edit_end_date: Optional[date] = None

                if edit_duration_type == "Date range":
                    default_end_date = (
                        selected_end_date
                        if (
                            selected_end_date is not None
                            and selected_end_date >= edit_start_date
                        )
                        else edit_start_date
                    )

                    edit_end_date = st.date_input(
                        "End date",
                        value=default_end_date,
                        min_value=edit_start_date,
                        key=f"edit_end_date_{selected_event_id}",
                    )

                elif edit_duration_type == "Ongoing":
                    st.info(
                        "This event will remain active until you add an end date."
                    )

                edit_has_time = st.checkbox(
                    "Include an event time",
                    value=bool(
                        stored_event_time
                    ),
                    key=f"edit_has_time_{selected_event_id}",
                )

                edit_event_time: Optional[time] = None

                if edit_has_time:
                    edit_event_time = st.time_input(
                        "Event time",
                        value=parse_event_time(
                            stored_event_time
                        ),
                        step=300,
                        key=f"edit_event_time_{selected_event_id}",
                    )

                edit_category = st.selectbox(
                    "Category",
                    options=category_options,
                    index=category_options.index(
                        selected_category
                    ),
                    key=f"edit_category_{selected_event_id}",
                )

                edit_severity = st.selectbox(
                    "Importance",
                    options=severity_options,
                    index=severity_options.index(
                        selected_severity
                    ),
                    key=f"edit_severity_{selected_event_id}",
                )

            with edit_col2:
                edit_title = st.text_input(
                    "Event title",
                    value=clean_text(
                        selected_event.get(
                            "title"
                        )
                    ),
                    key=f"edit_title_{selected_event_id}",
                )

                edit_description = st.text_area(
                    "Description",
                    value=clean_text(
                        selected_event.get(
                            "description"
                        )
                    ),
                    height=160,
                    key=f"edit_description_{selected_event_id}",
                )

                edit_tags = st.text_input(
                    "Tags",
                    value=clean_text(
                        selected_event.get(
                            "tags"
                        )
                    ),
                    key=f"edit_tags_{selected_event_id}",
                )

                edit_source = st.selectbox(
                    "Source",
                    options=source_options,
                    index=source_options.index(
                        selected_source
                    ),
                    key=f"edit_source_{selected_event_id}",
                )

            action_col1, action_col2 = st.columns(
                2
            )

            with action_col1:
                if st.button(
                    "💾 Save changes",
                    type="primary",
                    key=f"update_event_{selected_event_id}",
                ):
                    if not clean_text(
                        edit_title
                    ):
                        st.error(
                            "Please enter an event title."
                        )

                    else:
                        try:
                            resolved_start_date, resolved_end_date = (
                                resolve_event_dates(
                                    duration_type=edit_duration_type,
                                    start_date_value=edit_start_date,
                                    range_end_date=edit_end_date,
                                )
                            )

                            updated = update_life_event(
                                event_id=selected_event_id,
                                start_date=resolved_start_date,
                                end_date=resolved_end_date,
                                event_time=edit_event_time,
                                title=edit_title,
                                category=edit_category,
                                severity=edit_severity,
                                description=edit_description,
                                tags=edit_tags,
                                source=edit_source,
                            )

                            if updated:
                                st.success(
                                    "✅ Event updated."
                                )
                                st.rerun()

                            else:
                                st.warning(
                                    "No event was updated."
                                )

                        except ValueError as error:
                            st.error(
                                str(error)
                            )

                        except Exception as error:
                            st.error(
                                "Phoenix could not update the event."
                            )

                            st.exception(
                                error
                            )

            with action_col2:
                confirm_delete = st.checkbox(
                    "I understand this permanently deletes the event",
                    key=f"confirm_delete_{selected_event_id}",
                )

                if st.button(
                    "🗑️ Delete event",
                    disabled=not confirm_delete,
                    key=f"delete_event_{selected_event_id}",
                ):
                    deleted = delete_life_event(
                        selected_event_id
                    )

                    if deleted:
                        st.success(
                            "Event deleted."
                        )
                        st.rerun()

                    else:
                        st.warning(
                            "The event could not be found."
                        )


# ---------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------

st.divider()

st.caption(
    f"{PHOENIX_VERSION_LABEL} · "
    "Timeline events provide context for future Phoenix intelligence."
)