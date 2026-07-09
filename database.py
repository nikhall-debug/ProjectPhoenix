import sqlite3
from datetime import datetime

import pandas as pd


DB_FILE = "phoenix.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checkin_date TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            lumen_score INTEGER,
            fat_burn_percent INTEGER,
            carb_burn_percent INTEGER,
            energy INTEGER,
            mood INTEGER,
            soreness INTEGER,
            notes TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS health_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            metric_type TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT,
            measured_at TEXT NOT NULL,
            raw_type INTEGER,
            raw_data TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source, metric_type, measured_at)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS coach_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_date TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            recommendation TEXT,
            response TEXT NOT NULL,
            reason TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS coach_plan_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            override_date TEXT,
            original_training_type TEXT,
            selected_plan TEXT,
            extra_context TEXT,
            final_training_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS xert_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fetched_at TEXT NOT NULL,
            status TEXT,
            source TEXT,
            ftp REAL,
            ltp REAL,
            hie REAL,
            pp REAL,
            tl_low REAL,
            tl_high REAL,
            tl_peak REAL,
            tl_total REAL,
            target_xss_low REAL,
            target_xss_high REAL,
            target_xss_peak REAL,
            target_xss_total REAL,
            wotd_type TEXT,
            raw_data TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workout_date TEXT NOT NULL,
            workout_type TEXT NOT NULL,
            subtype TEXT,
            source TEXT NOT NULL,
            duration_minutes REAL,
            rpe INTEGER,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def save_checkin(checkin_date, lumen_score, fat_burn_percent, carb_burn_percent, energy, mood, soreness, notes):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO daily_checkins
        (checkin_date, timestamp, lumen_score, fat_burn_percent, carb_burn_percent, energy, mood, soreness, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(checkin_date),
        datetime.now().isoformat(timespec="seconds"),
        lumen_score,
        fat_burn_percent,
        carb_burn_percent,
        energy,
        mood,
        soreness,
        notes,
    ))

    conn.commit()
    conn.close()


def save_health_measurement(source, metric_type, value, unit, measured_at, raw_type=None, raw_data=None):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO health_measurements
        (source, metric_type, value, unit, measured_at, raw_type, raw_data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        source,
        metric_type,
        value,
        unit,
        measured_at,
        raw_type,
        raw_data,
    ))

    inserted = cur.rowcount

    conn.commit()
    conn.close()

    return inserted == 1


def save_coach_feedback(feedback_date, recommendation, response, reason):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO coach_feedback
        (feedback_date, timestamp, recommendation, response, reason)
        VALUES (?, ?, ?, ?, ?)
    """, (
        str(feedback_date),
        datetime.now().isoformat(timespec="seconds"),
        recommendation,
        response,
        reason,
    ))

    conn.commit()
    conn.close()


def save_coach_plan_override(
    override_date,
    original_training_type,
    selected_plan,
    extra_context,
    final_training_type,
):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO coach_plan_overrides
        (
            override_date,
            original_training_type,
            selected_plan,
            extra_context,
            final_training_type
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        override_date.isoformat(),
        original_training_type,
        selected_plan,
        extra_context,
        final_training_type,
    ))

    conn.commit()
    conn.close()


def save_xert_status_record(status_response):
    import json

    today = datetime.now().date().isoformat()

    cleaned_raw = dict(status_response)
    cleaned_raw.pop("weight", None)

    signature = status_response.get("signature", {})
    tl = status_response.get("tl", {})
    target_xss = status_response.get("targetXSS", {})
    wotd = status_response.get("wotd", {})

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM xert_status
        WHERE DATE(fetched_at) = ?
    """, (today,))

    cur.execute("""
        INSERT INTO xert_status
        (
            fetched_at,
            status,
            source,
            ftp,
            ltp,
            hie,
            pp,
            tl_low,
            tl_high,
            tl_peak,
            tl_total,
            target_xss_low,
            target_xss_high,
            target_xss_peak,
            target_xss_total,
            wotd_type,
            raw_data
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(timespec="seconds"),
        status_response.get("status"),
        status_response.get("source"),
        signature.get("ftp"),
        signature.get("ltp"),
        signature.get("hie"),
        signature.get("pp"),
        tl.get("low"),
        tl.get("high"),
        tl.get("peak"),
        tl.get("total"),
        target_xss.get("low"),
        target_xss.get("high"),
        target_xss.get("peak"),
        target_xss.get("total"),
        wotd.get("type"),
        json.dumps(cleaned_raw),
    ))

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------
# Workouts
# ---------------------------------------------------------------------

def save_workout(
    workout_date,
    workout_type,
    subtype,
    source,
    duration_minutes,
    rpe,
    notes,
):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO workouts
        (
            workout_date,
            workout_type,
            subtype,
            source,
            duration_minutes,
            rpe,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        str(workout_date),
        workout_type,
        subtype,
        source,
        duration_minutes,
        rpe,
        notes,
    ))

    conn.commit()
    conn.close()


def load_workouts():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT * FROM workouts ORDER BY workout_date DESC, created_at DESC",
        conn,
    )
    conn.close()
    return df


def get_latest_workout(workout_type=None):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    if workout_type is None:
        cur.execute("""
            SELECT *
            FROM workouts
            ORDER BY workout_date DESC, created_at DESC
            LIMIT 1
        """)
    else:
        cur.execute("""
            SELECT *
            FROM workouts
            WHERE workout_type = ?
            ORDER BY workout_date DESC, created_at DESC
            LIMIT 1
        """, (workout_type,))

    result = cur.fetchone()
    columns = [description[0] for description in cur.description] if cur.description else []

    conn.close()

    if result is None:
        return None

    return dict(zip(columns, result))


def get_workouts_for_date(workout_date):
    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        """
        SELECT *
        FROM workouts
        WHERE workout_date = ?
        ORDER BY created_at DESC
        """,
        conn,
        params=(str(workout_date),),
    )

    conn.close()
    return df


# ---------------------------------------------------------------------
# Measurements and check-ins
# ---------------------------------------------------------------------

def get_latest_measurement_time(source):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT MAX(measured_at)
        FROM health_measurements
        WHERE source = ?
    """, (source,))

    result = cur.fetchone()[0]

    conn.close()

    if result is None:
        return None

    return result


def get_latest_metric(source, metric_type):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT value, unit, measured_at
        FROM health_measurements
        WHERE source = ? AND metric_type = ?
        ORDER BY measured_at DESC
        LIMIT 1
    """, (source, metric_type))

    result = cur.fetchone()
    conn.close()

    if result is None:
        return None

    return {
        "value": result[0],
        "unit": result[1],
        "measured_at": result[2],
    }


def get_latest_health_metric(metric_type):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            metric_type,
            value,
            unit,
            measured_at,
            source
        FROM health_measurements
        WHERE metric_type = ?
        ORDER BY measured_at DESC
        LIMIT 1
    """, (metric_type,))

    result = cur.fetchone()
    conn.close()

    if result is None:
        return None

    return {
        "metric_type": result[0],
        "value": result[1],
        "unit": result[2],
        "measured_at": result[3],
        "source": result[4],
    }


def get_metric_values_since(metric_type, days=30):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cutoff = datetime.now() - pd.Timedelta(days=days)

    cur.execute("""
        SELECT
            value,
            unit,
            measured_at,
            source
        FROM health_measurements
        WHERE metric_type = ?
          AND measured_at >= ?
        ORDER BY measured_at DESC
    """, (
        metric_type,
        cutoff.isoformat(),
    ))

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "value": row[0],
            "unit": row[1],
            "measured_at": row[2],
            "source": row[3],
        }
        for row in rows
    ]


def has_checkin_for_date(checkin_date):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM daily_checkins
        WHERE checkin_date = ?
    """, (str(checkin_date),))

    count = cur.fetchone()[0]

    conn.close()
    return count > 0


def get_latest_checkin():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            checkin_date,
            timestamp,
            lumen_score,
            fat_burn_percent,
            carb_burn_percent,
            energy,
            mood,
            soreness,
            notes
        FROM daily_checkins
        ORDER BY checkin_date DESC, timestamp DESC
        LIMIT 1
    """)

    result = cur.fetchone()
    conn.close()

    if result is None:
        return None

    return {
        "checkin_date": result[0],
        "timestamp": result[1],
        "lumen_score": result[2],
        "fat_burn_percent": result[3],
        "carb_burn_percent": result[4],
        "energy": result[5],
        "mood": result[6],
        "soreness": result[7],
        "notes": result[8],
    }


def get_checkin_for_date(checkin_date):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            checkin_date,
            timestamp,
            lumen_score,
            fat_burn_percent,
            carb_burn_percent,
            energy,
            mood,
            soreness,
            notes
        FROM daily_checkins
        WHERE checkin_date = ?
        ORDER BY timestamp DESC
        LIMIT 1
    """, (str(checkin_date),))

    result = cur.fetchone()
    conn.close()

    if result is None:
        return None

    return {
        "checkin_date": result[0],
        "timestamp": result[1],
        "lumen_score": result[2],
        "fat_burn_percent": result[3],
        "carb_burn_percent": result[4],
        "energy": result[5],
        "mood": result[6],
        "soreness": result[7],
        "notes": result[8],
    }


def load_checkins():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT * FROM daily_checkins ORDER BY checkin_date DESC, timestamp DESC",
        conn,
    )
    conn.close()
    return df


def load_health_measurements():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT * FROM health_measurements ORDER BY measured_at DESC",
        conn,
    )
    conn.close()
    return df


def load_coach_feedback():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT * FROM coach_feedback ORDER BY feedback_date DESC, timestamp DESC",
        conn,
    )
    conn.close()
    return df


def load_coach_plan_overrides():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT * FROM coach_plan_overrides ORDER BY override_date DESC, created_at DESC",
        conn,
    )
    conn.close()
    return df


def load_xert_status_history():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT * FROM xert_status ORDER BY fetched_at DESC",
        conn,
    )
    conn.close()
    return df


def get_latest_xert_status():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM xert_status
        ORDER BY fetched_at DESC
        LIMIT 1
    """)

    result = cur.fetchone()
    columns = [description[0] for description in cur.description] if cur.description else []
    conn.close()

    if result is None:
        return None

    return dict(zip(columns, result))


def get_metric_values_for_date(metric_type, target_date):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    date_string = str(target_date)

    cur.execute("""
        SELECT
            value,
            unit,
            measured_at,
            source
        FROM health_measurements
        WHERE metric_type = ?
          AND DATE(measured_at) = ?
        ORDER BY measured_at ASC
    """, (
        metric_type,
        date_string,
    ))

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "value": row[0],
            "unit": row[1],
            "measured_at": row[2],
            "source": row[3],
        }
        for row in rows
    ]