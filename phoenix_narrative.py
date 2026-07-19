from __future__ import annotations

from datetime import date
from typing import Any, Iterable
import pandas as pd
import streamlit as st


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _first(values: Iterable[Any], fallback: str = "") -> str:
    for value in values:
        value = _text(value)
        if value:
            return value
    return fallback


def _label_list(items: list[str], limit: int = 4) -> str:
    clean = [str(x).strip() for x in items if str(x).strip()]
    clean = list(dict.fromkeys(clean))[:limit]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    if len(clean) == 2:
        return f"{clean[0]} and {clean[1]}"
    return f"{', '.join(clean[:-1])}, and {clean[-1]}"


def _metric_groups(days: int = 90) -> tuple[list[str], list[str], list[str]]:
    try:
        from trend_engine import build_health_trends
        trends = build_health_trends(days=days) or {}
        metrics = trends.get("metrics", {}) or {}
    except Exception:
        return [], [], []

    good: list[str] = []
    watch: list[str] = []
    stable: list[str] = []
    for metric in metrics.values():
        if not isinstance(metric, dict) or metric.get("current") is None:
            continue
        label = str(metric.get("label") or metric.get("key") or "").strip()
        favorable = str(metric.get("favorable_direction") or "").lower()
        direction = str(metric.get("direction") or "").lower()
        if favorable in {"favorable", "improving", "positive", "good"}:
            good.append(label)
        elif favorable in {"unfavorable", "worsening", "negative", "attention"}:
            watch.append(label)
        elif direction in {"stable", "flat", "unchanged"}:
            stable.append(label)
    return good, watch, stable


def health_trends_story(days: int = 90) -> str:
    good, watch, stable = _metric_groups(days)
    good_text = _label_list(good)
    watch_text = _label_list(watch)
    stable_text = _label_list(stable, 2)

    if good_text and watch_text:
        return (
            f"Most of your longer-term health picture is moving in the right direction. "
            f"The clearest positives are {good_text}. The main things Phoenix would keep "
            f"an eye on are {watch_text}. Nothing here should be judged from one reading, "
            f"but those weaker trends are the ones worth checking on the full Trends page."
        )
    if good_text:
        tail = f" {stable_text} remain broadly steady." if stable_text else ""
        return (
            f"The longer-term picture is encouraging, with {good_text} showing the clearest "
            f"positive direction.{tail} Phoenix is not currently seeing a distinct worsening "
            f"trend, although it will keep checking whether the improvement holds."
        )
    if watch_text:
        return (
            f"The longer-term picture is not fully settled. The specific signals needing the "
            f"closest look are {watch_text}. Phoenix would use the full Trends page to check "
            f"whether these are persistent changes or simply short-term noise."
        )
    return (
        "Phoenix does not yet have enough clearly directional trend data to name reliable "
        "winners and watch-outs. The Trends page shows which measurements need more history."
    )


def timeline_story() -> str:
    try:
        from database import load_life_events
        events = load_life_events()
    except Exception:
        return "Phoenix could not read the timeline just now, so no contextual conclusion has been added."
    if events is None or events.empty:
        return "There are no timeline events yet. Adding medical, recovery, sleep or training events will help Phoenix explain changes rather than merely report them."

    df = events.copy()
    for col in ("start_date", "event_date"):
        if col not in df.columns:
            df[col] = None
    df["_date"] = pd.to_datetime(df["start_date"].fillna(df["event_date"]), errors="coerce")
    df = df.dropna(subset=["_date"]).sort_values("_date", ascending=False)
    if df.empty:
        return "Timeline events exist, but Phoenix could not establish their dates reliably."

    today = pd.Timestamp(date.today())
    ongoing = df.copy()
    if "is_ongoing" in ongoing.columns:
        ongoing = ongoing[ongoing["is_ongoing"].astype(str).str.lower().isin(["1", "true", "yes"])]
    elif "duration_type" in ongoing.columns:
        ongoing = ongoing[ongoing["duration_type"].astype(str).str.lower().eq("ongoing")]
    else:
        ongoing = ongoing.iloc[0:0]

    dominant = ongoing.iloc[0] if not ongoing.empty else df.iloc[0]
    latest = df.iloc[0]

    def describe(row: Any) -> tuple[str, str, str]:
        category = str(row.get("category") or "event").lower()
        title = _first([row.get("title"), row.get("event_title"), row.get("name")], category)
        note = _first([row.get("notes"), row.get("description"), row.get("details")])
        return category, title, note

    category, title, note = describe(dominant)
    start = dominant.get("_date")
    date_text = start.strftime("%d %b %Y") if pd.notna(start) else "recently"
    core = f"The most important context Phoenix currently sees is {title}, recorded from {date_text}."
    if note:
        core += f" {note.rstrip('.')} .".replace(" .", ".")

    if dominant.name != latest.name:
        lcat, ltitle, lnote = describe(latest)
        core += f" The newest separate timeline point is {ltitle}."
        if lcat == "sleep":
            core += " That may colour today's energy or recovery, but it is less important than the ongoing context unless the disruption repeats."
        else:
            core += " Phoenix treats it as useful context, while giving more weight to the ongoing event."
    elif category == "sleep":
        core += " A single disrupted night may affect today's energy, but Phoenix would not treat it as a lasting health change unless it becomes a pattern."
    else:
        core += " Phoenix will keep using this event to interpret nearby changes in recovery, health and training."
    return core


def today_health_story() -> str:
    fallback = "Today's health picture is available, but Phoenix could not build a full interpretation from the current inputs."
    try:
        from athlete_context import build_athlete_context
        from health_intelligence import build_health_intelligence
        from readiness_engine import build_readiness_profile
        from recovery_engine import build_recovery_profile
        from snapshot import build_morning_snapshot
        snapshot = build_morning_snapshot() or {}
        context = build_athlete_context() or {}
        recovery = build_recovery_profile(context) or {}
        readiness = build_readiness_profile(context, recovery) or {}
        health = build_health_intelligence(context=context, snapshot=snapshot, recovery=recovery, readiness=readiness) or {}
        base = _first([health.get("summary"), health.get("interpretation"), recovery.get("summary"), readiness.get("summary")], fallback)
    except Exception:
        return fallback
    good, watch, _ = _metric_groups(30)
    good_text = _label_list(good, 3)
    watch_text = _label_list(watch, 3)
    if good_text:
        base += f" The strongest recent signals are {good_text}."
    if watch_text:
        base += f" The specific areas worth watching are {watch_text}."
    else:
        base += " Phoenix is not currently seeing a clearly worsening short-term health trend."
    return base


def performance_story() -> tuple[str, str, str]:
    good = "Phoenix has not yet identified a clear recent training strength."
    watch = "There is not enough current workout evidence to name a specific weakness confidently."
    bottom = "Open the Coach or Workouts page for the latest available training evidence."
    try:
        from decision_engine import build_daily_decision
        from narrative_engine import build_coach_narrative
        decision = build_daily_decision() or {}
        context = decision.get("context", {}) or {}
        recovery = decision.get("recovery_profile", {}) or {}
        readiness = decision.get("readiness_profile", {}) or {}
        narrative = build_coach_narrative(context, recovery, readiness, decision) or {}
        good = _first([narrative.get("opener"), narrative.get("body")], good)
        watch = _first([narrative.get("coaching_note"), readiness.get("limiting_factor"), decision.get("reason")], watch)
        bottom = _first([readiness.get("training_window"), decision.get("recommendation"), narrative.get("headline")], bottom)
    except Exception:
        pass
    return good, watch, bottom


def render_three_part_brief(title: str, good: str, watch: str, bottom: str) -> None:
    with st.container(border=True):
        st.subheader(title)
        st.markdown(f"**✅ What looks good**  \n{good}")
        st.markdown(f"**⚠️ What needs watching**  \n{watch}")
        st.markdown(f"**🧠 Phoenix's view**  \n{bottom}")


def render_page_brief(page: str) -> None:
    page = page.lower()
    if page == "trends":
        good, watch, _ = _metric_groups(90)
        render_three_part_brief(
            "Phoenix trend briefing",
            f"The clearest improving signals are {_label_list(good) or 'not yet distinct enough to name confidently'}.",
            f"The specific trends needing attention are {_label_list(watch) or 'none currently showing a clear adverse direction'}.",
            health_trends_story(90),
        )
    elif page == "timeline":
        story = timeline_story()
        render_three_part_brief(
            "Phoenix context briefing",
            "The timeline gives Phoenix the real-world explanation behind changes in your measurements.",
            "Recent sleep disruption, illness, surgery or training changes matter only when their timing overlaps the data.",
            story,
        )
    elif page in {"coach", "performance"}:
        render_three_part_brief("Phoenix performance briefing", *performance_story())
    elif page == "workouts":
        try:
            from workout_engine import build_workout_summary
            summary = build_workout_summary() or {}
            good = _first([summary.get("interpretation"), summary.get("summary")], "Phoenix could not yet identify what the latest training day achieved.")
            watch = "Open the latest workout or Deep Analysis to inspect the specific power, heart-rate, cadence and route evidence."
            bottom = "The workout page shows whether the latest training day matched its intended role and what should follow next."
        except Exception:
            good, watch, bottom = performance_story()
        render_three_part_brief("Latest training read", good, watch, bottom)
    elif page == "deep":
        render_three_part_brief(
            "How to read this analysis",
            "Each tab names the strongest evidence after accounting for route, elevation, recovery phases and workload.",
            "Watch-outs are only shown when Phoenix can separate them from normal terrain or pacing effects.",
            "Use the summary first; drill into charts only when you want to inspect the evidence behind the conclusion.",
        )
    elif page == "insights":
        render_three_part_brief("Today's executive briefing", today_health_story(), performance_story()[1], performance_story()[2])
    elif page == "data":
        render_three_part_brief(
            "Data confidence",
            "Fresh Apple Health, Withings and workout inputs give Phoenix a stronger basis for today's conclusions.",
            "Missing or stale sources reduce confidence; raw tables are useful for checking exactly what has arrived.",
            "This is the evidence-maintenance layer. Phoenix's conclusions belong on Today, Health and Performance.",
        )
