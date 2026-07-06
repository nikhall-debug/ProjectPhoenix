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


def load_checkins():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT * FROM daily_checkins ORDER BY checkin_date DESC, timestamp DESC",
        conn
    )
    conn.close()
    return df