import sqlite3
from datetime import date, datetime

import pandas as pd
import streamlit as st


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
            fat_burn_percentage INTEGER,
            carb_burn_percentage INTEGER,
            energy INTEGER,
            mood INTEGER,
            soreness INTEGER,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_checkin(checkin_date, lumen_score, fat_burn_percentage, carb_burn_percentage, energy, mood, soreness, notes):
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
        fat_burn_percentage,
        carb_burn_percentage,
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


init_db()

st.set_page_config(page_title="Project Phoenix", page_icon="🔥", layout="wide")

st.title("🔥 Project Phoenix")
st.subheader("Personal Health & Performance Intelligence")

st.divider()

st.header("30-second daily check-in")

col1, col2, col3 = st.columns(3)

with col1:
    checkin_date = st.date_input("Date", date.today())
    lumen_score = st.selectbox("Morning Lumen score", [1, 2, 3, 4, 5], index=2)
    fat_burn_percent = st.slider(
    "Fat burning %",
    min_value=0,
    max_value=100,
    value=65,
    help="Carbs are calculated automatically.")

carb_burn_percent = 100 - fat_burn_percent

st.caption(f"Estimated fuel mix: {fat_burn_percent}% fat / {carb_burn_percent}% carbs")

with col2:
    energy = st.slider("Energy", 1, 10, 5)
    mood = st.slider("Mood / motivation", 1, 10, 5)

with col3:
    soreness = st.slider("Soreness / pain", 1, 10, 3)
    notes = st.text_area("Notes", placeholder="Optional...")

if st.button("Save check-in"):
    save_checkin(checkin_date, lumen_score, fat_burn_percent, carb_burn_percent, energy, mood, soreness, notes)
    st.success("Check-in saved to Phoenix database 🔥")

st.divider()

st.header("Phoenix Daily Brief")

if energy >= 7 and soreness <= 4:
    st.success("Today looks like a good low-risk day. Gentle activity is fine.")
elif soreness >= 7:
    st.warning("High soreness/pain. Recovery focus today.")
else:
    st.info("Steady recovery day. Walk, eat protein, hydrate, sleep.")

st.divider()

st.header("Recent check-ins")

df = load_checkins()

if not df.empty:
    st.dataframe(df, use_container_width=True)
else:
    st.caption("No check-ins saved yet.")

st.caption("Version 0.4-alpha with local database")