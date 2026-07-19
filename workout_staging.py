from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from workout_database import (
    DB_FILE,
    calculate_duration_minutes,
    calculate_end_time,
    init_workout_tables,
    is_xert_cycling_activity,
    map_apple_workout_type,
    normalise_datetime,
)


SOURCE_DIR = Path("data/workout_sources")
CACHE_DIR = Path("data/workout_cache")


def init_workout_staging_tables() -> None:
    init_workout_tables()

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pending_training_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_key TEXT NOT NULL UNIQUE,
            session_type TEXT NOT NULL,
            title TEXT,
            session_date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            duration_minutes REAL,
            status TEXT NOT NULL DEFAULT 'waiting_for_files',
            primary_source TEXT,
            apple_external_id TEXT,
            xert_external_id TEXT,
            apple_raw_data TEXT,
            xert_raw_data TEXT,
            final_session_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(final_session_id) REFERENCES training_sessions(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS workout_source_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pending_session_id INTEGER,
            final_session_id INTEGER,
            source_type TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            file_hash TEXT NOT NULL UNIQUE,
            start_time TEXT,
            end_time TEXT,
            duration_seconds REAL,
            match_score REAL,
            available_metrics TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(pending_session_id) REFERENCES pending_training_sessions(id),
            FOREIGN KEY(final_session_id) REFERENCES training_sessions(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS workout_deep_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL UNIQUE,
            pending_session_id INTEGER,
            summary_json TEXT,
            segments_json TEXT,
            graph_config_json TEXT,
            timeline_cache_path TEXT,
            analysis_version TEXT NOT NULL DEFAULT '1.0',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES training_sessions(id),
            FOREIGN KEY(pending_session_id) REFERENCES pending_training_sessions(id)
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_pending_sessions_start
        ON pending_training_sessions(start_time)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_pending_sessions_status
        ON pending_training_sessions(status)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_source_files_pending
        ON workout_source_files(pending_session_id)
    """)

    conn.commit()
    conn.close()


def _canonical_key(
    session_type: str,
    start_time: Optional[str],
    duration_minutes: Optional[float],
) -> str:
    if start_time:
        try:
            start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            rounded_start = start.replace(second=0, microsecond=0).isoformat()
        except ValueError:
            rounded_start = str(start_time)
    else:
        rounded_start = "unknown"

    rounded_duration = (
        str(int(round(float(duration_minutes) / 5.0) * 5))
        if duration_minutes is not None
        else "unknown"
    )

    return f"{session_type.lower()}|{rounded_start}|{rounded_duration}"


def _find_nearby_pending_session(
    session_type: str,
    start_time: Optional[str],
    duration_minutes: Optional[float],
    tolerance_minutes: float = 10.0,
) -> Optional[int]:
    if not start_time:
        return None

    target_start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, start_time, duration_minutes
        FROM pending_training_sessions
        WHERE session_type = ?
          AND start_time IS NOT NULL
          AND status != 'ignored'
    """, (session_type,))
    rows = cur.fetchall()
    conn.close()

    for pending_id, existing_start, existing_duration in rows:
        try:
            existing_dt = datetime.fromisoformat(existing_start.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue

        start_diff = abs((target_start - existing_dt).total_seconds()) / 60.0
        duration_match = True

        if duration_minutes is not None and existing_duration is not None:
            duration_match = (
                abs(float(duration_minutes) - float(existing_duration))
                <= tolerance_minutes
            )

        if start_diff <= tolerance_minutes and duration_match:
            return int(pending_id)

    return None


def stage_training_session_from_apple_workout(
    apple_workout: Dict[str, Any],
) -> Dict[str, Any]:
    init_workout_staging_tables()

    external_id = apple_workout.get("id")
    title = apple_workout.get("name") or "Apple Workout"
    session_type = map_apple_workout_type(title)

    start_time = normalise_datetime(apple_workout.get("start"))
    end_time = normalise_datetime(apple_workout.get("end"))

    duration_seconds = apple_workout.get("duration")
    duration_minutes = (
        round(float(duration_seconds) / 60.0, 1)
        if duration_seconds is not None
        else calculate_duration_minutes(start_time, end_time)
    )

    session_date = (
        start_time[:10] if start_time else datetime.now().date().isoformat()
    )

    nearby_id = _find_nearby_pending_session(
        session_type,
        start_time,
        duration_minutes,
    )

    canonical_key = _canonical_key(
        session_type,
        start_time,
        duration_minutes,
    )

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    if nearby_id is not None:
        cur.execute("""
            UPDATE pending_training_sessions
            SET
                title = COALESCE(title, ?),
                apple_external_id = ?,
                apple_raw_data = ?,
                primary_source = CASE
                    WHEN primary_source IS NULL OR primary_source = ''
                    THEN 'Apple Health'
                    ELSE primary_source
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            title,
            external_id,
            json.dumps(apple_workout),
            nearby_id,
        ))
        conn.commit()
        conn.close()

        return {
            "staged": False,
            "updated": True,
            "pending_id": nearby_id,
            "reason": "matched_existing_pending_session",
            "external_id": external_id,
        }

    cur.execute("""
        INSERT INTO pending_training_sessions (
            canonical_key,
            session_type,
            title,
            session_date,
            start_time,
            end_time,
            duration_minutes,
            status,
            primary_source,
            apple_external_id,
            apple_raw_data
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'waiting_for_files', 'Apple Health', ?, ?)
        ON CONFLICT(canonical_key) DO UPDATE SET
            title = excluded.title,
            apple_external_id = excluded.apple_external_id,
            apple_raw_data = excluded.apple_raw_data,
            updated_at = CURRENT_TIMESTAMP
    """, (
        canonical_key,
        session_type,
        title,
        session_date,
        start_time,
        end_time,
        duration_minutes,
        external_id,
        json.dumps(apple_workout),
    ))

    pending_id = cur.lastrowid
    if not pending_id:
        cur.execute("""
            SELECT id
            FROM pending_training_sessions
            WHERE canonical_key = ?
        """, (canonical_key,))
        row = cur.fetchone()
        pending_id = row[0] if row else None

    conn.commit()
    conn.close()

    return {
        "staged": True,
        "updated": False,
        "pending_id": pending_id,
        "external_id": external_id,
    }


def _first_value(mapping: Dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def _xert_summary(activity: Dict[str, Any]) -> Dict[str, Any]:
    summary = activity.get("summary")
    return summary if isinstance(summary, dict) else {}


def _xert_start_time(activity: Dict[str, Any]) -> Optional[str]:
    summary = _xert_summary(activity)
    progression = summary.get("progression")
    progression = progression if isinstance(progression, dict) else {}

    candidates = (
        progression.get("start_date"),
        summary.get("timestamp"),
        summary.get("start_time"),
        activity.get("start_time"),
        activity.get("start_date"),
        activity.get("timestamp"),
    )

    start_date = summary.get("start_date")
    if isinstance(start_date, dict):
        candidates = (start_date.get("date"),) + candidates
    elif start_date:
        candidates = (start_date,) + candidates

    for candidate in candidates:
        normalised = normalise_datetime(candidate)
        if normalised:
            return normalised
    return None


def _xert_duration_seconds(activity: Dict[str, Any]) -> Optional[float]:
    summary = _xert_summary(activity)
    value = _first_value(
        summary,
        (
            "duration",
            "total_timer_time",
            "total_elapsed_time",
            "elapsed_time",
            "moving_time",
        ),
    )
    if value is None:
        value = _first_value(
            activity,
            (
                "duration",
                "total_timer_time",
                "total_elapsed_time",
                "elapsed_time",
                "moving_time",
            ),
        )
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def stage_training_session_from_xert_activity(
    xert_activity: Dict[str, Any],
) -> Dict[str, Any]:
    init_workout_staging_tables()

    if not is_xert_cycling_activity(xert_activity):
        return {
            "staged": False,
            "updated": False,
            "reason": "not_cycling",
            "external_id": xert_activity.get("path"),
        }

    external_id = str(
        _first_value(xert_activity, ("path", "activity_id", "id")) or ""
    )
    title = str(
        _first_value(xert_activity, ("name", "title", "activity_name"))
        or "Xert Ride"
    )

    start_time = _xert_start_time(xert_activity)
    duration_seconds = _xert_duration_seconds(xert_activity)
    duration_minutes = (
        round(duration_seconds / 60.0, 1)
        if duration_seconds is not None
        else None
    )
    end_time = calculate_end_time(start_time, duration_seconds)
    session_date = (
        start_time[:10] if start_time else datetime.now().date().isoformat()
    )

    nearby_id = _find_nearby_pending_session(
        "Cycling",
        start_time,
        duration_minutes,
    )
    canonical_key = _canonical_key(
        "Cycling",
        start_time,
        duration_minutes,
    )
    raw_json = json.dumps(xert_activity)

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    if nearby_id is not None:
        cur.execute("""
            UPDATE pending_training_sessions
            SET
                title = ?,
                session_date = ?,
                start_time = COALESCE(?, start_time),
                end_time = COALESCE(?, end_time),
                duration_minutes = COALESCE(?, duration_minutes),
                xert_external_id = ?,
                xert_raw_data = ?,
                primary_source = 'Xert',
                status = CASE
                    WHEN status = 'analysed' THEN status
                    ELSE 'xert_ready'
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            title,
            session_date,
            start_time,
            end_time,
            duration_minutes,
            external_id,
            raw_json,
            nearby_id,
        ))
        conn.commit()
        conn.close()

        return {
            "staged": False,
            "updated": True,
            "pending_id": nearby_id,
            "reason": "matched_existing_pending_session",
            "external_id": external_id,
        }

    cur.execute("""
        INSERT INTO pending_training_sessions (
            canonical_key,
            session_type,
            title,
            session_date,
            start_time,
            end_time,
            duration_minutes,
            status,
            primary_source,
            xert_external_id,
            xert_raw_data
        )
        VALUES (?, 'Cycling', ?, ?, ?, ?, ?, 'xert_ready', 'Xert', ?, ?)
        ON CONFLICT(canonical_key) DO UPDATE SET
            title = excluded.title,
            session_date = excluded.session_date,
            start_time = COALESCE(excluded.start_time, pending_training_sessions.start_time),
            end_time = COALESCE(excluded.end_time, pending_training_sessions.end_time),
            duration_minutes = COALESCE(excluded.duration_minutes, pending_training_sessions.duration_minutes),
            xert_external_id = excluded.xert_external_id,
            xert_raw_data = excluded.xert_raw_data,
            primary_source = 'Xert',
            status = CASE
                WHEN pending_training_sessions.status = 'analysed'
                THEN pending_training_sessions.status
                ELSE 'xert_ready'
            END,
            updated_at = CURRENT_TIMESTAMP
    """, (
        canonical_key,
        title,
        session_date,
        start_time,
        end_time,
        duration_minutes,
        external_id,
        raw_json,
    ))

    pending_id = cur.lastrowid
    if not pending_id:
        cur.execute("""
            SELECT id
            FROM pending_training_sessions
            WHERE canonical_key = ?
        """, (canonical_key,))
        row = cur.fetchone()
        pending_id = row[0] if row else None

    conn.commit()
    conn.close()

    return {
        "staged": True,
        "updated": False,
        "pending_id": pending_id,
        "external_id": external_id,
    }


def load_recent_pending_sessions(limit: int = 5) -> pd.DataFrame:
    init_workout_staging_tables()

    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("""
        SELECT
            p.*,
            (
                SELECT COUNT(*)
                FROM workout_source_files f
                WHERE f.pending_session_id = p.id
            ) AS attached_file_count
        FROM pending_training_sessions p
        WHERE p.status != 'ignored'
        ORDER BY
            COALESCE(p.start_time, p.session_date) DESC,
            p.id DESC
        LIMIT ?
    """, conn, params=(int(limit),))
    conn.close()
    return df



def load_unanalysed_pending_sessions() -> pd.DataFrame:
    """Return every workout still requiring review, regardless of age."""
    init_workout_staging_tables()

    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("""
        SELECT
            p.*,
            (
                SELECT COUNT(*)
                FROM workout_source_files f
                WHERE f.pending_session_id = p.id
            ) AS attached_file_count
        FROM pending_training_sessions p
        WHERE p.status NOT IN ('analysed', 'ignored')
        ORDER BY
            COALESCE(p.start_time, p.session_date) DESC,
            p.id DESC
    """, conn)
    conn.close()
    return df


def load_analysed_pending_sessions(
    limit: int = 100,
    session_type: Optional[str] = None,
    title_query: Optional[str] = None,
) -> pd.DataFrame:
    """Return completed Deep Analysis workouts for browsing and reopening."""
    init_workout_staging_tables()

    clauses = ["p.status = 'analysed'"]
    params: list[Any] = []

    if session_type and session_type != "All":
        clauses.append("p.session_type = ?")
        params.append(session_type)

    if title_query:
        clauses.append("LOWER(COALESCE(p.title, p.session_type)) LIKE ?")
        params.append(f"%{title_query.strip().lower()}%")

    params.append(int(limit))
    where_sql = " AND ".join(clauses)

    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(f"""
        SELECT
            p.*,
            (
                SELECT COUNT(*)
                FROM workout_source_files f
                WHERE f.pending_session_id = p.id
            ) AS attached_file_count
        FROM pending_training_sessions p
        WHERE {where_sql}
        ORDER BY
            COALESCE(p.start_time, p.session_date) DESC,
            p.id DESC
        LIMIT ?
    """, conn, params=tuple(params))
    conn.close()
    return df


def friendly_pending_status(status: Optional[str]) -> str:
    labels = {
        "waiting_for_files": "Needs sensor files",
        "files_attached": "Ready to review",
        "xert_ready": "Ready to review",
        "analysed": "Analysed",
        "ignored": "Ignored",
    }
    return labels.get(str(status or ""), str(status or "Unknown").replace("_", " ").title())


def get_pending_session(pending_id: int) -> Optional[Dict[str, Any]]:
    init_workout_staging_tables()

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT *
        FROM pending_training_sessions
        WHERE id = ?
    """, (int(pending_id),))
    row = cur.fetchone()
    conn.close()

    return dict(row) if row else None


def load_source_files_for_pending(pending_id: int) -> pd.DataFrame:
    init_workout_staging_tables()

    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("""
        SELECT *
        FROM workout_source_files
        WHERE pending_session_id = ?
        ORDER BY created_at ASC
    """, conn, params=(int(pending_id),))
    conn.close()
    return df


def save_source_file(
    *,
    pending_session_id: int,
    source_type: str,
    filename: str,
    file_bytes: bytes,
    start_time: Optional[str],
    end_time: Optional[str],
    duration_seconds: Optional[float],
    match_score: Optional[float],
    available_metrics: list[str],
) -> Dict[str, Any]:
    init_workout_staging_tables()

    file_hash = hashlib.sha256(file_bytes).hexdigest()
    suffix = Path(filename).suffix.lower() or ".fit"
    stored_name = f"{file_hash}{suffix}"
    stored_path = SOURCE_DIR / stored_name

    if not stored_path.exists():
        stored_path.write_bytes(file_bytes)

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO workout_source_files (
            pending_session_id,
            source_type,
            original_filename,
            stored_path,
            file_hash,
            start_time,
            end_time,
            duration_seconds,
            match_score,
            available_metrics
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        int(pending_session_id),
        source_type,
        filename,
        str(stored_path),
        file_hash,
        start_time,
        end_time,
        duration_seconds,
        match_score,
        json.dumps(available_metrics),
    ))

    inserted = cur.rowcount == 1

    cur.execute("""
        UPDATE pending_training_sessions
        SET
            status = 'files_attached',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (int(pending_session_id),))

    conn.commit()
    conn.close()

    return {
        "saved": inserted,
        "file_hash": file_hash,
        "stored_path": str(stored_path),
    }


def finalise_pending_session(
    *,
    pending_id: int,
    merged_timeline: pd.DataFrame,
    summary: Dict[str, Any],
    graph_config: Dict[str, Any],
) -> Dict[str, Any]:
    init_workout_staging_tables()

    pending = get_pending_session(pending_id)
    if pending is None:
        raise ValueError("Pending workout was not found.")

    if pending.get("final_session_id"):
        return {
            "created": False,
            "session_id": pending["final_session_id"],
            "reason": "already_finalised",
        }

    external_id = f"phoenix:{pending['canonical_key']}"
    raw_data = {
        "pending_id": pending_id,
        "apple": json.loads(pending["apple_raw_data"]) if pending.get("apple_raw_data") else None,
        "xert": json.loads(pending["xert_raw_data"]) if pending.get("xert_raw_data") else None,
        "deep_analysis_summary": summary,
    }

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO training_sessions (
            external_id,
            source,
            session_type,
            title,
            routine_id,
            description,
            session_date,
            start_time,
            end_time,
            duration_minutes,
            raw_data
        )
        VALUES (?, 'Phoenix merged', ?, ?, NULL, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, external_id) DO UPDATE SET
            session_type = excluded.session_type,
            title = excluded.title,
            description = excluded.description,
            session_date = excluded.session_date,
            start_time = excluded.start_time,
            end_time = excluded.end_time,
            duration_minutes = excluded.duration_minutes,
            raw_data = excluded.raw_data,
            updated_at = CURRENT_TIMESTAMP
    """, (
        external_id,
        pending["session_type"],
        pending.get("title"),
        "Merged and analysed by Phoenix Workout Deep Analysis.",
        pending["session_date"],
        pending.get("start_time"),
        pending.get("end_time"),
        pending.get("duration_minutes"),
        json.dumps(raw_data),
    ))

    cur.execute("""
        SELECT id
        FROM training_sessions
        WHERE source = 'Phoenix merged'
          AND external_id = ?
    """, (external_id,))
    session_id = int(cur.fetchone()[0])

    cache_path = CACHE_DIR / f"session_{session_id}.parquet"
    try:
        merged_timeline.to_parquet(cache_path, index=False)
    except Exception:
        cache_path = CACHE_DIR / f"session_{session_id}.csv"
        merged_timeline.to_csv(cache_path, index=False)

    cur.execute("""
        INSERT INTO workout_deep_analyses (
            session_id,
            pending_session_id,
            summary_json,
            segments_json,
            graph_config_json,
            timeline_cache_path,
            analysis_version
        )
        VALUES (?, ?, ?, ?, ?, ?, '1.0')
        ON CONFLICT(session_id) DO UPDATE SET
            summary_json = excluded.summary_json,
            segments_json = excluded.segments_json,
            graph_config_json = excluded.graph_config_json,
            timeline_cache_path = excluded.timeline_cache_path,
            analysis_version = excluded.analysis_version,
            updated_at = CURRENT_TIMESTAMP
    """, (
        session_id,
        int(pending_id),
        json.dumps(summary),
        json.dumps([]),
        json.dumps(graph_config),
        str(cache_path),
    ))

    cur.execute("""
        UPDATE workout_source_files
        SET final_session_id = ?
        WHERE pending_session_id = ?
    """, (session_id, int(pending_id)))

    cur.execute("""
        UPDATE pending_training_sessions
        SET
            status = 'analysed',
            final_session_id = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (session_id, int(pending_id)))

    conn.commit()
    conn.close()

    return {
        "created": True,
        "session_id": session_id,
        "timeline_cache_path": str(cache_path),
    }
