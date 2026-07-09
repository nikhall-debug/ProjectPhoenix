import json
import sqlite3
from datetime import datetime, timezone, timedelta

import pandas as pd


DB_FILE = "phoenix.db"

APPLE_REFERENCE_DATE = datetime(2001, 1, 1, tzinfo=timezone.utc)


def init_workout_tables():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS training_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_id TEXT,
            source TEXT NOT NULL,
            session_type TEXT NOT NULL,
            title TEXT,
            routine_id TEXT,
            description TEXT,
            session_date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            duration_minutes REAL,
            raw_data TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source, external_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS training_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            exercise_name TEXT NOT NULL,
            exercise_order INTEGER,
            sets_count INTEGER,
            total_reps REAL,
            total_volume_kg REAL,
            max_weight_kg REAL,
            duration_seconds REAL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES training_sessions(id)
        )
    """)

    conn.commit()
    conn.close()


def normalise_datetime(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        converted = APPLE_REFERENCE_DATE + timedelta(seconds=float(value))
        return converted.isoformat()

    if isinstance(value, str):
        cleaned = value.strip()

        for fmt in (
            "%Y-%m-%d %H:%M:%S %z",
            "%Y-%m-%d %H:%M:%S.%f %z",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
        ):
            try:
                parsed = datetime.strptime(cleaned, fmt)

                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)

                return parsed.isoformat()
            except ValueError:
                pass

        try:
            parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))

            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)

            return parsed.isoformat()
        except ValueError:
            return None

    return None


def calculate_duration_minutes(start_time, end_time):
    if not start_time or not end_time:
        return None

    start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

    duration = end - start
    return round(duration.total_seconds() / 60, 1)


def calculate_end_time(start_time, duration_seconds):
    if not start_time or duration_seconds is None:
        return None

    start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    end = start + timedelta(seconds=float(duration_seconds))

    return end.isoformat()


def session_exists_near_time(session_type, start_time, duration_minutes, source_to_ignore=None, tolerance_minutes=10):
    if not start_time:
        return False

    target_start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    if source_to_ignore:
        cur.execute("""
            SELECT source, start_time, duration_minutes
            FROM training_sessions
            WHERE session_type = ?
              AND source != ?
              AND start_time IS NOT NULL
        """, (session_type, source_to_ignore))
    else:
        cur.execute("""
            SELECT source, start_time, duration_minutes
            FROM training_sessions
            WHERE session_type = ?
              AND start_time IS NOT NULL
        """, (session_type,))

    rows = cur.fetchall()
    conn.close()

    for _, existing_start_time, existing_duration in rows:
        try:
            existing_start = datetime.fromisoformat(existing_start_time.replace("Z", "+00:00"))
        except ValueError:
            continue

        start_diff = abs((target_start - existing_start).total_seconds()) / 60

        duration_match = True
        if duration_minutes is not None and existing_duration is not None:
            duration_match = abs(float(duration_minutes) - float(existing_duration)) <= tolerance_minutes

        if start_diff <= tolerance_minutes and duration_match:
            return True

    return False


def delete_lower_priority_sessions_near_time(
    *,
    session_type,
    start_time,
    duration_minutes,
    source,
    tolerance_minutes=10,
):
    if not start_time:
        return 0

    target_start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, start_time, duration_minutes
        FROM training_sessions
        WHERE session_type = ?
          AND source = ?
          AND start_time IS NOT NULL
    """, (session_type, source))

    rows = cur.fetchall()
    ids_to_delete = []

    for session_id, existing_start_time, existing_duration in rows:
        try:
            existing_start = datetime.fromisoformat(existing_start_time.replace("Z", "+00:00"))
        except ValueError:
            continue

        start_diff = abs((target_start - existing_start).total_seconds()) / 60

        duration_match = True
        if duration_minutes is not None and existing_duration is not None:
            duration_match = abs(float(duration_minutes) - float(existing_duration)) <= tolerance_minutes

        if start_diff <= tolerance_minutes and duration_match:
            ids_to_delete.append(session_id)

    for session_id in ids_to_delete:
        cur.execute("DELETE FROM training_exercises WHERE session_id = ?", (session_id,))
        cur.execute("DELETE FROM training_sessions WHERE id = ?", (session_id,))

    conn.commit()
    conn.close()

    return len(ids_to_delete)


def summarise_hevy_exercise(exercise):
    sets = exercise.get("sets", [])

    sets_count = len(sets)
    total_reps = 0
    total_volume_kg = 0
    max_weight_kg = 0
    duration_seconds = 0

    for workout_set in sets:
        reps = workout_set.get("reps") or 0
        weight = workout_set.get("weight_kg") or 0
        set_duration = workout_set.get("duration_seconds") or 0

        total_reps += reps
        total_volume_kg += weight * reps
        max_weight_kg = max(max_weight_kg, weight)
        duration_seconds += set_duration

    return {
        "exercise_name": exercise.get("title"),
        "exercise_order": exercise.get("index"),
        "sets_count": sets_count,
        "total_reps": total_reps,
        "total_volume_kg": total_volume_kg,
        "max_weight_kg": max_weight_kg,
        "duration_seconds": duration_seconds,
        "notes": exercise.get("notes"),
    }


def save_training_session_from_hevy(hevy_workout):
    init_workout_tables()

    external_id = hevy_workout.get("id")
    source = "Hevy"
    session_type = "Strength"

    start_time = normalise_datetime(hevy_workout.get("start_time"))
    end_time = normalise_datetime(hevy_workout.get("end_time"))
    duration_minutes = calculate_duration_minutes(start_time, end_time)

    session_date = start_time[:10] if start_time else datetime.now().date().isoformat()

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO training_sessions (
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        external_id,
        source,
        session_type,
        hevy_workout.get("title"),
        hevy_workout.get("routine_id"),
        hevy_workout.get("description"),
        session_date,
        start_time,
        end_time,
        duration_minutes,
        json.dumps(hevy_workout),
    ))

    if cur.rowcount == 0:
        conn.close()
        return {
            "imported": False,
            "reason": "duplicate",
            "external_id": external_id,
        }

    session_id = cur.lastrowid

    for exercise in hevy_workout.get("exercises", []):
        summary = summarise_hevy_exercise(exercise)

        cur.execute("""
            INSERT INTO training_exercises (
                session_id,
                exercise_name,
                exercise_order,
                sets_count,
                total_reps,
                total_volume_kg,
                max_weight_kg,
                duration_seconds,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            summary["exercise_name"],
            summary["exercise_order"],
            summary["sets_count"],
            summary["total_reps"],
            summary["total_volume_kg"],
            summary["max_weight_kg"],
            summary["duration_seconds"],
            summary["notes"],
        ))

    conn.commit()
    conn.close()

    return {
        "imported": True,
        "external_id": external_id,
        "session_id": session_id,
    }


def save_training_sessions_from_hevy_response(hevy_response):
    workouts = hevy_response.get("workouts", [])

    imported = 0
    duplicates = 0

    for workout in workouts:
        result = save_training_session_from_hevy(workout)

        if result["imported"]:
            imported += 1
        else:
            duplicates += 1

    return {
        "imported": imported,
        "duplicates": duplicates,
        "total_seen": len(workouts),
    }


def map_apple_workout_type(name):
    if not name:
        return "Other"

    cleaned = name.lower()

    if "cycling" in cleaned or "bike" in cleaned:
        return "Cycling"

    if "strength" in cleaned:
        return "Strength"

    if "walk" in cleaned:
        return "Walking"

    if "hike" in cleaned:
        return "Hiking"

    if "run" in cleaned:
        return "Running"

    if "yoga" in cleaned or "mobility" in cleaned:
        return "Mobility"

    return "Other"


def save_training_session_from_apple_workout(apple_workout):
    init_workout_tables()

    external_id = apple_workout.get("id")
    source = "Apple Health"

    title = apple_workout.get("name") or "Apple Workout"
    session_type = map_apple_workout_type(title)

    start_time = normalise_datetime(apple_workout.get("start"))
    end_time = normalise_datetime(apple_workout.get("end"))

    duration_seconds = apple_workout.get("duration")
    duration_minutes = round(float(duration_seconds) / 60, 1) if duration_seconds is not None else None

    if duration_minutes is None:
        duration_minutes = calculate_duration_minutes(start_time, end_time)

    session_date = start_time[:10] if start_time else datetime.now().date().isoformat()

    if session_type == "Strength":
        if session_exists_near_time("Strength", start_time, duration_minutes, source_to_ignore="Apple Health"):
            return {
                "imported": False,
                "reason": "duplicate_specialist_source",
                "external_id": external_id,
            }

    if session_type == "Cycling":
        if session_exists_near_time("Cycling", start_time, duration_minutes, source_to_ignore="Apple Health"):
            return {
                "imported": False,
                "reason": "duplicate_specialist_source",
                "external_id": external_id,
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, external_id) DO UPDATE SET
            session_type = excluded.session_type,
            title = excluded.title,
            session_date = excluded.session_date,
            start_time = excluded.start_time,
            end_time = excluded.end_time,
            duration_minutes = excluded.duration_minutes,
            raw_data = excluded.raw_data,
            updated_at = CURRENT_TIMESTAMP
    """, (
        external_id,
        source,
        session_type,
        title,
        None,
        None,
        session_date,
        start_time,
        end_time,
        duration_minutes,
        json.dumps(apple_workout),
    ))

    conn.commit()
    conn.close()

    return {
        "imported": True,
        "external_id": external_id,
    }


def is_xert_cycling_activity(activity):
    summary = activity.get("summary", {})

    activity_type = (summary.get("activity_type") or "").lower()
    sport = (summary.get("sport") or "").lower()

    if "cycling" in activity_type or "cycling" in sport:
        return True

    return False


def save_training_session_from_xert_activity(xert_activity):
    init_workout_tables()

    if not is_xert_cycling_activity(xert_activity):
        return {
            "imported": False,
            "reason": "not_cycling",
            "external_id": xert_activity.get("path"),
        }

    external_id = xert_activity.get("path")
    source = "Xert"
    session_type = "Cycling"

    title = xert_activity.get("name") or "Xert Ride"
    description = xert_activity.get("description")

    summary = xert_activity.get("summary", {})

    start_date = summary.get("start_date", {})
    start_time = normalise_datetime(start_date.get("date"))

    progression = summary.get("progression", {})
    if progression.get("start_date"):
        start_time = normalise_datetime(progression.get("start_date"))

    if summary.get("timestamp") and start_time is None:
        start_time = normalise_datetime(summary.get("timestamp"))

    duration_seconds = summary.get("duration")

    if duration_seconds is None:

        duration_seconds = summary.get("total_timer_time") or summary.get("total_elapsed_time")

    duration_minutes = round(float(duration_seconds) / 60, 1) if duration_seconds is not None else None

    end_time = calculate_end_time(start_time, duration_seconds)

    session_date = start_time[:10] if start_time else datetime.now().date().isoformat()

    removed_apple_duplicates = delete_lower_priority_sessions_near_time(

        session_type="Cycling",

        start_time=start_time,

        duration_minutes=duration_minutes,

        source="Apple Health",

    )

    conn = sqlite3.connect(DB_FILE)

    cur = conn.cursor()

    cur.execute("""

        INSERT OR IGNORE INTO training_sessions (

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

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

    """, (

        external_id,

        source,

        session_type,

        title,

        None,

        description,

        session_date,

        start_time,

        end_time,

        duration_minutes,

        json.dumps(xert_activity),

    ))

    imported = cur.rowcount == 1

    conn.commit()

    conn.close()

    if not imported:

        return {

            "imported": False,

            "reason": "duplicate_xert_id",

            "external_id": external_id,

            "removed_apple_duplicates": removed_apple_duplicates,

        }

    return {

        "imported": True,

        "external_id": external_id,

        "removed_apple_duplicates": removed_apple_duplicates,

    }


def load_training_sessions(limit=50):
    init_workout_tables()

    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        """
        SELECT *
        FROM training_sessions
        ORDER BY session_date DESC, start_time DESC
        LIMIT ?
        """,
        conn,
        params=(limit,),
    )

    conn.close()
    return df


def load_training_exercises_for_session(session_id):
    init_workout_tables()

    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        """
        SELECT *
        FROM training_exercises
        WHERE session_id = ?
        ORDER BY exercise_order ASC
        """,
        conn,
        params=(session_id,),
    )

    conn.close()
    return df


def get_latest_training_session(session_type=None):
    init_workout_tables()

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    if session_type:
        cur.execute("""
            SELECT *
            FROM training_sessions
            WHERE session_type = ?
            ORDER BY session_date DESC, start_time DESC
            LIMIT 1
        """, (session_type,))
    else:
        cur.execute("""
            SELECT *
            FROM training_sessions
            ORDER BY session_date DESC, start_time DESC
            LIMIT 1
        """)

    result = cur.fetchone()
    columns = [description[0] for description in cur.description] if cur.description else []

    conn.close()

    if result is None:
        return None

    return dict(zip(columns, result))


def get_latest_strength_session():
    return get_latest_training_session("Strength")


def get_latest_cycling_session():
    return get_latest_training_session("Cycling")