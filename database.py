import sqlite3
from datetime import datetime

import pandas as pd


DB_FILE = "phoenix.db"


# ---------------------------------------------------------------------
# Database connection helper
# ---------------------------------------------------------------------

def get_db_connection():
    """
    Create a SQLite connection with dictionary-style row access.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------

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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS life_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_date TEXT NOT NULL,
            event_time TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT,
            tags TEXT,
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(
                event_date,
                event_time,
                title,
                category,
                source
            )
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_life_events_date
        ON life_events(event_date)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_life_events_category
        ON life_events(category)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_life_events_source
        ON life_events(source)
    """)

    # -------------------------------------------------------------
    # Life Events migrations
    # -------------------------------------------------------------

    cur.execute("""
        PRAGMA table_info(life_events)
    """)

    life_event_columns = {
        row[1]
        for row in cur.fetchall()
    }

    if "start_date" not in life_event_columns:
        cur.execute("""
            ALTER TABLE life_events
            ADD COLUMN start_date TEXT
        """)

    if "end_date" not in life_event_columns:
        cur.execute("""
            ALTER TABLE life_events
            ADD COLUMN end_date TEXT
        """)

    cur.execute("""
        UPDATE life_events
        SET start_date = event_date
        WHERE start_date IS NULL
           OR start_date = ''
    """)

    cur.execute("""
        UPDATE life_events
        SET end_date = event_date
        WHERE end_date IS NULL
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_life_events_start_date
        ON life_events(start_date)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_life_events_end_date
        ON life_events(end_date)
    """)

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------
# Check-in writes
# ---------------------------------------------------------------------

def save_checkin(
    checkin_date,
    lumen_score,
    fat_burn_percent,
    carb_burn_percent,
    energy,
    mood,
    soreness,
    notes,
):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO daily_checkins
        (
            checkin_date,
            timestamp,
            lumen_score,
            fat_burn_percent,
            carb_burn_percent,
            energy,
            mood,
            soreness,
            notes
        )
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


# ---------------------------------------------------------------------
# Health measurement writes
# ---------------------------------------------------------------------

def save_health_measurement(
    source,
    metric_type,
    value,
    unit,
    measured_at,
    raw_type=None,
    raw_data=None,
):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO health_measurements
        (
            source,
            metric_type,
            value,
            unit,
            measured_at,
            raw_type,
            raw_data
        )
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


def save_manual_wrist_temperature(
    measurement_date,
    temperature,
):
    """
    Save or update one manually entered wrist-temperature value.

    A fixed midday timestamp gives each date one stable manual record.
    Saving the same date again updates the existing value.
    """
    measured_at = f"{measurement_date.isoformat()}T12:00:00"

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO health_measurements
        (
            source,
            metric_type,
            value,
            unit,
            measured_at,
            raw_type,
            raw_data
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, metric_type, measured_at)
        DO UPDATE SET
            value = excluded.value,
            unit = excluded.unit,
            raw_type = excluded.raw_type,
            raw_data = excluded.raw_data,
            created_at = CURRENT_TIMESTAMP
    """, (
        "manual",
        "wrist_temperature",
        float(temperature),
        "°C",
        measured_at,
        None,
        None,
    ))

    conn.commit()
    conn.close()


def get_manual_wrist_temperature_for_date(
    measurement_date,
):
    """
    Return the manually entered wrist temperature for a given date.
    """
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            value,
            unit,
            measured_at,
            source
        FROM health_measurements
        WHERE source = ?
          AND metric_type = ?
          AND DATE(measured_at) = ?
        ORDER BY measured_at DESC
        LIMIT 1
    """, (
        "manual",
        "wrist_temperature",
        str(measurement_date),
    ))

    result = cur.fetchone()

    conn.close()

    if result is None:
        return None

    return {
        "value": result[0],
        "unit": result[1],
        "measured_at": result[2],
        "source": result[3],
    }


def load_recent_wrist_temperatures(
    limit=10,
):
    """
    Load recent manual and automatic wrist-temperature values.
    """
    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        """
        SELECT
            DATE(measured_at) AS measurement_date,
            value,
            unit,
            source,
            measured_at
        FROM health_measurements
        WHERE metric_type IN (
            'wrist_temperature',
            'apple_sleeping_wrist_temperature_c'
        )
        ORDER BY measured_at DESC
        LIMIT ?
        """,
        conn,
        params=(
            int(limit),
        ),
    )

    conn.close()

    return df


# ---------------------------------------------------------------------
# Life event helpers
# ---------------------------------------------------------------------

def _normalise_event_date(
    event_date,
):
    """
    Convert a date-like value to YYYY-MM-DD.
    """
    if hasattr(
        event_date,
        "isoformat",
    ):
        return event_date.isoformat()

    parsed = pd.to_datetime(
        event_date,
        errors="coerce",
    )

    if pd.isna(parsed):
        raise ValueError(
            "A valid event date is required."
        )

    return parsed.date().isoformat()

def _normalise_optional_event_date(
    event_date,
):
    """
    Convert an optional date-like value to YYYY-MM-DD.

    None or an empty value represents an event with no known end date.
    """
    if event_date is None:
        return None

    if isinstance(event_date, str) and not event_date.strip():
        return None

    return _normalise_event_date(
        event_date
    )

def _normalise_event_time(
    event_time,
):
    """
    Convert an optional time value to HH:MM.

    Empty times are stored as an empty string rather than NULL so
    SQLite duplicate protection works consistently.
    """
    if event_time is None:
        return ""

    if hasattr(
        event_time,
        "strftime",
    ):
        return event_time.strftime(
            "%H:%M"
        )

    clean_time = str(
        event_time
    ).strip()

    if not clean_time:
        return ""

    parsed = pd.to_datetime(
        clean_time,
        errors="coerce",
    )

    if pd.isna(parsed):
        raise ValueError(
            "Event time must be a valid time."
        )

    return parsed.strftime(
        "%H:%M"
    )


def _clean_required_text(
    value,
    field_name,
):
    clean_value = str(
        value or ""
    ).strip()

    if not clean_value:
        raise ValueError(
            f"{field_name} is required."
        )

    return clean_value


def _clean_optional_text(
    value,
):
    if value is None:
        return ""

    return str(
        value
    ).strip()


# ---------------------------------------------------------------------
# Life event writes
# ---------------------------------------------------------------------

def save_life_event(
    start_date,
    title,
    category,
    severity,
    description="",
    tags="",
    source="manual",
    event_time=None,
    end_date=None,
):
    """
    Save a new life event.

    A one-day event should have matching start and end dates.
    An ongoing event should have end_date=None.

    Returns:
        True when a new event was inserted.
        False when an identical event already exists.
    """
    clean_start_date = _normalise_event_date(
        start_date
    )

    clean_end_date = _normalise_optional_event_date(
        end_date
    )

    if (
        clean_end_date is not None
        and clean_end_date < clean_start_date
    ):
        raise ValueError(
            "The end date cannot be before the start date."
        )

    clean_event_time = _normalise_event_time(
        event_time
    )

    clean_title = _clean_required_text(
        title,
        "Event title",
    )

    clean_category = _clean_required_text(
        category,
        "Event category",
    )

    clean_severity = _clean_required_text(
        severity,
        "Event severity",
    )

    clean_source = _clean_required_text(
        source,
        "Event source",
    )

    clean_description = _clean_optional_text(
        description
    )

    clean_tags = _clean_optional_text(
        tags
    )

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT id
        FROM life_events
        WHERE start_date = ?
          AND COALESCE(end_date, '') = COALESCE(?, '')
          AND event_time = ?
          AND title = ?
          AND category = ?
          AND source = ?
        LIMIT 1
    """, (
        clean_start_date,
        clean_end_date,
        clean_event_time,
        clean_title,
        clean_category,
        clean_source,
    ))

    existing = cur.fetchone()

    if existing is not None:
        conn.close()
        return False

    cur.execute("""
        INSERT INTO life_events
        (
            event_date,
            start_date,
            end_date,
            event_time,
            title,
            category,
            severity,
            description,
            tags,
            source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        clean_start_date,
        clean_start_date,
        clean_end_date,
        clean_event_time,
        clean_title,
        clean_category,
        clean_severity,
        clean_description,
        clean_tags,
        clean_source,
    ))

    conn.commit()
    conn.close()

    return True


def update_life_event(
    event_id,
    start_date,
    title,
    category,
    severity,
    description="",
    tags="",
    source="manual",
    event_time=None,
    end_date=None,
):
    """
    Update an existing life event.
    """
    clean_start_date = _normalise_event_date(
        start_date
    )

    clean_end_date = _normalise_optional_event_date(
        end_date
    )

    if (
        clean_end_date is not None
        and clean_end_date < clean_start_date
    ):
        raise ValueError(
            "The end date cannot be before the start date."
        )

    clean_event_time = _normalise_event_time(
        event_time
    )

    clean_title = _clean_required_text(
        title,
        "Event title",
    )

    clean_category = _clean_required_text(
        category,
        "Event category",
    )

    clean_severity = _clean_required_text(
        severity,
        "Event severity",
    )

    clean_source = _clean_required_text(
        source,
        "Event source",
    )

    clean_description = _clean_optional_text(
        description
    )

    clean_tags = _clean_optional_text(
        tags
    )

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT id
        FROM life_events
        WHERE start_date = ?
          AND COALESCE(end_date, '') = COALESCE(?, '')
          AND event_time = ?
          AND title = ?
          AND category = ?
          AND source = ?
          AND id != ?
        LIMIT 1
    """, (
        clean_start_date,
        clean_end_date,
        clean_event_time,
        clean_title,
        clean_category,
        clean_source,
        int(event_id),
    ))

    duplicate = cur.fetchone()

    if duplicate is not None:
        conn.close()

        raise ValueError(
            "An identical life event already exists."
        )

    cur.execute("""
        UPDATE life_events
        SET
            event_date = ?,
            start_date = ?,
            end_date = ?,
            event_time = ?,
            title = ?,
            category = ?,
            severity = ?,
            description = ?,
            tags = ?,
            source = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        clean_start_date,
        clean_start_date,
        clean_end_date,
        clean_event_time,
        clean_title,
        clean_category,
        clean_severity,
        clean_description,
        clean_tags,
        clean_source,
        int(event_id),
    ))

    updated = cur.rowcount == 1

    conn.commit()
    conn.close()

    return updated


def delete_life_event(
    event_id,
):
    """
    Delete one life event.

    Returns:
        True when an event was deleted.
        False when the event ID was not found.
    """
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM life_events
        WHERE id = ?
    """, (
        int(event_id),
    ))

    deleted = cur.rowcount == 1

    conn.commit()
    conn.close()

    return deleted


# ---------------------------------------------------------------------
# Life event reads
# ---------------------------------------------------------------------

def get_life_event(
    event_id,
):
    """
    Return one life event as a dictionary.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            event_date,
            start_date,
            end_date,
            event_time,
            title,
            category,
            severity,
            description,
            tags,
            source,
            created_at,
            updated_at
        FROM life_events
        WHERE id = ?
        LIMIT 1
    """, (
        int(event_id),
    ))

    result = cur.fetchone()

    conn.close()

    if result is None:
        return None

    return dict(
        result
    )


def load_life_events():
    """
    Load all life events, newest first.
    """
    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        """
        SELECT
            id,
            event_date,
            start_date,
            end_date,
            event_time,
            title,
            category,
            severity,
            description,
            tags,
            source,
            created_at,
            updated_at
        FROM life_events
        ORDER BY
            start_date DESC,
            CASE
                WHEN event_time = '' THEN '00:00'
                ELSE event_time
            END DESC,
            id DESC
        """,
        conn,
    )

    conn.close()

    return df


def load_life_events_between(
    start_date,
    end_date,
):
    """
    Load events that overlap an inclusive date range.

    This includes events that began before the selected period but
    remained active during it.
    """
    clean_start_date = _normalise_event_date(
        start_date
    )

    clean_end_date = _normalise_event_date(
        end_date
    )

    if clean_start_date > clean_end_date:
        raise ValueError(
            "The start date cannot be after the end date."
        )

    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        """
        SELECT
            id,
            event_date,
            start_date,
            end_date,
            event_time,
            title,
            category,
            severity,
            description,
            tags,
            source,
            created_at,
            updated_at
        FROM life_events
        WHERE start_date <= ?
          AND (
              end_date IS NULL
              OR end_date >= ?
          )
        ORDER BY
            start_date DESC,
            CASE
                WHEN event_time = '' THEN '00:00'
                ELSE event_time
            END DESC,
            id DESC
        """,
        conn,
        params=(
            clean_end_date,
            clean_start_date,
        ),
    )

    conn.close()

    return df


def get_life_events_for_date(
    event_date,
):
    """
    Load all life events for one date.
    """
    clean_event_date = _normalise_event_date(
        event_date
    )

    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        """
        SELECT
            id,
            event_date,
            start_date,
            end_date,
            event_time,
            title,
            category,
            severity,
            description,
            tags,
            source,
            created_at,
            updated_at
        FROM life_events
        WHERE event_date = ?
        ORDER BY
            CASE
                WHEN event_time = '' THEN '00:00'
                ELSE event_time
            END ASC,
            id ASC
        """,
        conn,
        params=(
            clean_event_date,
        ),
    )

    conn.close()

    return df

def load_active_life_events(
    target_date=None,
):
    """
    Load events active on a given date.

    When no date is supplied, today is used.
    """
    if target_date is None:
        target_date = datetime.now().date()

    clean_target_date = _normalise_event_date(
        target_date
    )

    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        """
        SELECT
            id,
            event_date,
            start_date,
            end_date,
            event_time,
            title,
            category,
            severity,
            description,
            tags,
            source,
            created_at,
            updated_at
        FROM life_events
        WHERE start_date <= ?
          AND (
              end_date IS NULL
              OR end_date >= ?
          )
        ORDER BY
            CASE severity
                WHEN 'Critical' THEN 5
                WHEN 'Major' THEN 4
                WHEN 'Moderate' THEN 3
                WHEN 'Minor' THEN 2
                WHEN 'Info' THEN 1
                ELSE 0
            END DESC,
            start_date DESC,
            id DESC
        """,
        conn,
        params=(
            clean_target_date,
            clean_target_date,
        ),
    )

    conn.close()

    return df


def load_recent_life_events(
    days=30,
):
    """
    Load events that started recently or remain active now.
    """
    try:
        clean_days = max(
            int(days),
            1,
        )
    except (TypeError, ValueError):
        clean_days = 30

    today = datetime.now().date()

    cutoff = (
        today
        - pd.Timedelta(
            days=clean_days - 1
        )
    ).date()

    return load_life_events_between(
        start_date=cutoff,
        end_date=today,
    )

# ---------------------------------------------------------------------
# Coach feedback writes
# ---------------------------------------------------------------------

def save_coach_feedback(
    feedback_date,
    recommendation,
    response,
    reason,
):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO coach_feedback
        (
            feedback_date,
            timestamp,
            recommendation,
            response,
            reason
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        str(feedback_date),
        datetime.now().isoformat(
            timespec="seconds"
        ),
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


# ---------------------------------------------------------------------
# Xert writes
# ---------------------------------------------------------------------

def save_xert_status_record(
    status_response,
):
    import json

    today = datetime.now().date().isoformat()

    cleaned_raw = dict(
        status_response
    )

    cleaned_raw.pop(
        "weight",
        None,
    )

    signature = status_response.get(
        "signature",
        {},
    )

    tl = status_response.get(
        "tl",
        {},
    )

    target_xss = status_response.get(
        "targetXSS",
        {},
    )

    wotd = status_response.get(
        "wotd",
        {},
    )

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM xert_status
        WHERE DATE(fetched_at) = ?
    """, (
        today,
    ))

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
        datetime.now().isoformat(
            timespec="seconds"
        ),
        status_response.get(
            "status"
        ),
        status_response.get(
            "source"
        ),
        signature.get(
            "ftp"
        ),
        signature.get(
            "ltp"
        ),
        signature.get(
            "hie"
        ),
        signature.get(
            "pp"
        ),
        tl.get(
            "low"
        ),
        tl.get(
            "high"
        ),
        tl.get(
            "peak"
        ),
        tl.get(
            "total"
        ),
        target_xss.get(
            "low"
        ),
        target_xss.get(
            "high"
        ),
        target_xss.get(
            "peak"
        ),
        target_xss.get(
            "total"
        ),
        wotd.get(
            "type"
        ),
        json.dumps(
            cleaned_raw
        ),
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
        """
        SELECT *
        FROM workouts
        ORDER BY workout_date DESC, created_at DESC
        """,
        conn,
    )

    conn.close()

    return df


def get_latest_workout(
    workout_type=None,
):
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
        """, (
            workout_type,
        ))

    result = cur.fetchone()

    columns = (
        [
            description[0]
            for description in cur.description
        ]
        if cur.description
        else []
    )

    conn.close()

    if result is None:
        return None

    return dict(
        zip(
            columns,
            result,
        )
    )


def get_workouts_for_date(
    workout_date,
):
    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        """
        SELECT *
        FROM workouts
        WHERE workout_date = ?
        ORDER BY created_at DESC
        """,
        conn,
        params=(
            str(workout_date),
        ),
    )

    conn.close()

    return df


# ---------------------------------------------------------------------
# Measurement helpers
# ---------------------------------------------------------------------

def get_latest_measurement_time(
    source,
):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT MAX(measured_at)
        FROM health_measurements
        WHERE source = ?
    """, (
        source,
    ))

    result = cur.fetchone()[0]

    conn.close()

    if result is None:
        return None

    return result


def get_latest_metric(
    source,
    metric_type,
):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            value,
            unit,
            measured_at
        FROM health_measurements
        WHERE source = ?
          AND metric_type = ?
        ORDER BY measured_at DESC
        LIMIT 1
    """, (
        source,
        metric_type,
    ))

    result = cur.fetchone()

    conn.close()

    if result is None:
        return None

    return {
        "value": result[0],
        "unit": result[1],
        "measured_at": result[2],
    }


def get_latest_health_metric(
    metric_type,
):
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
    """, (
        metric_type,
    ))

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


def get_metric_values_since(
    metric_type,
    days=30,
):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cutoff = (
        datetime.now()
        - pd.Timedelta(
            days=days
        )
    )

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


def get_metric_values_for_date(
    metric_type,
    target_date,
):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    date_string = str(
        target_date
    )

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


def load_metric_history(
    metric_type,
):
    """
    Load the complete stored history for one health metric.

    Trend interpretation remains the responsibility of trend_engine.py.
    """
    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        """
        SELECT
            measured_at,
            value,
            unit,
            source
        FROM health_measurements
        WHERE metric_type = ?
        ORDER BY measured_at ASC
        """,
        conn,
        params=(
            metric_type,
        ),
    )

    conn.close()

    return df


# ---------------------------------------------------------------------
# Check-in helpers
# ---------------------------------------------------------------------

def has_checkin_for_date(
    checkin_date,
):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM daily_checkins
        WHERE checkin_date = ?
    """, (
        str(checkin_date),
    ))

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


def get_checkin_for_date(
    checkin_date,
):
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
    """, (
        str(checkin_date),
    ))

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


# ---------------------------------------------------------------------
# Full-table history loaders
# ---------------------------------------------------------------------

def load_checkins():
    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        """
        SELECT *
        FROM daily_checkins
        ORDER BY checkin_date DESC, timestamp DESC
        """,
        conn,
    )

    conn.close()

    return df


def load_health_measurements():
    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        """
        SELECT *
        FROM health_measurements
        ORDER BY measured_at DESC
        """,
        conn,
    )

    conn.close()

    return df


def load_coach_feedback():
    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        """
        SELECT *
        FROM coach_feedback
        ORDER BY feedback_date DESC, timestamp DESC
        """,
        conn,
    )

    conn.close()

    return df


def load_coach_plan_overrides():
    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        """
        SELECT *
        FROM coach_plan_overrides
        ORDER BY override_date DESC, created_at DESC
        """,
        conn,
    )

    conn.close()

    return df


def load_xert_status_history():
    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        """
        SELECT *
        FROM xert_status
        ORDER BY fetched_at DESC
        """,
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

    columns = (
        [
            description[0]
            for description in cur.description
        ]
        if cur.description
        else []
    )

    conn.close()

    if result is None:
        return None

    return dict(
        zip(
            columns,
            result,
        )
    )