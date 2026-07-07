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


def load_checkins():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT * FROM daily_checkins ORDER BY checkin_date DESC, timestamp DESC",
        conn
    )
    conn.close()
    return df


def load_health_measurements():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT * FROM health_measurements ORDER BY measured_at DESC",
        conn
    )
    conn.close()
    return df