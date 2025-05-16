# app.py
# Streamlit 4-Week Strength & Conditioning Tracker
# Mobile-friendly with full functionality

import streamlit as st
import pandas as pd
import sqlite3
from datetime import date

# --- Page Config & Styles ---
st.set_page_config(
    page_title="4-Week Program Tracker",
    layout="wide",
    initial_sidebar_state="collapsed",
)
# CSS tweaks for mobile
st.markdown(
    """
<style>
/* Touch targets */
div[data-testid="stExpander"] > .stExpanderHeader {
    padding: 12px 8px !important;
}
button {
    padding: 12px !important;
    width: 100% !important;
}
input, .stSlider > div {
    padding: 8px 4px !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# --- Database Setup & Migration ---
conn = sqlite3.connect("workout_tracker.db", check_same_thread=False)
c = conn.cursor()
# Create or alter resistance table
c.execute("""CREATE TABLE IF NOT EXISTS resistance(
    id INTEGER PRIMARY KEY,
    date TEXT,
    week INTEGER,
    day TEXT,
    exercise TEXT,
    set_number INTEGER,
    target TEXT,
    actual_weight REAL,
    actual_reps INTEGER,
    rir INTEGER
)""")
# Ensure set_number column exists
cols = [row[1] for row in c.execute("PRAGMA table_info(resistance)").fetchall()]
if "set_number" not in cols:
    c.execute("ALTER TABLE resistance ADD COLUMN set_number INTEGER DEFAULT 1")
# Mobility table
c.execute("""CREATE TABLE IF NOT EXISTS mobility(
    id INTEGER PRIMARY KEY,
    date TEXT,
    prep_done INTEGER,
    joint_flow_done INTEGER,
    animal_circuit_done INTEGER,
    cuff_finisher_done INTEGER
)""")
# Cardio table
c.execute("""CREATE TABLE IF NOT EXISTS cardio(
    id INTEGER PRIMARY KEY,
    date TEXT,
    type TEXT,
    duration_min INTEGER,
    avg_hr INTEGER
)""")
conn.commit()

# --- Program Definitions ---
weekly_resistance = {
    "Monday": [
        {"exercise": "Back-squat", "target": "1×4 @88% + 3×6 @78%"},
        {"exercise": "Hip-thrust", "target": "4×8"},
    ],
    "Tuesday": [
        {"exercise": "Bench Press", "target": "1×4 @88% + 3×6 @78%"},
        {"exercise": "Overhead Press", "target": "3×6"},
        {"exercise": "Dips", "target": "3×10"},
    ],
    "Thursday AM": [
        {"exercise": "Deadlift", "target": "1×3 @90% + 3×6 @80%"},
        {"exercise": "Romanian Deadlift", "target": "3×8"},
    ],
    "Friday": [
        {"exercise": "Weighted Pull-up", "target": "3×6–8"},
        {"exercise": "Chest-supported Row", "target": "3×10"},
    ],
}


# --- Helpers ---
@st.cache_data
def load_table(name):
    return pd.read_sql_query(f"SELECT * FROM {name} ORDER BY date DESC", conn)


@st.cache_data
def fetch_last(exercise, set_num):
    df = pd.read_sql_query(
        "SELECT actual_weight, actual_reps, rir FROM resistance WHERE exercise=? AND set_number=? ORDER BY date DESC LIMIT 1",
        conn,
        params=(exercise, set_num),
    )
    if not df.empty:
        r = df.iloc[0]
        return float(r["actual_weight"]), int(r["actual_reps"]), int(r["rir"])
    return None, None, None


# --- Main Application with Tabs ---
tabs = st.tabs(["Guide", "Resistance", "Mobility", "Cardio", "Logs"])

# Guide Tab
with tabs[0]:
    st.header("📖 4-Week Program Guide")
    with st.expander("1. Resistance Framework", True):
        st.markdown(
            """
**Max-strength:** ≥85% 1RM · 1–5 reps · 5–10 sets/ex · 2–5 min rest

**Hypertrophy:** 60–80% 1RM · 6–12 reps · 10–20 sets/muscle · 1–2 min rest

_Tweaks:_ add 87–90% top set + increase accessory volume to 12–16 weekly sets.
"""
        )
    with st.expander("2. Weekly Template"):
        st.table(
            pd.DataFrame(
                [
                    ["Mon", "Back-squat; Hip-thrust", "Mini-band"],
                    ["Tue", "Bench; OHP; Dips", "Shoulder ER"],
                    ["Wed", "Mobility Flow", "Dynamic only"],
                    ["Thu AM", "Deadlift; RDL", ""],
                    ["Thu PM", "HIIT 4×4", "VO₂-max"],
                    ["Fri", "Pull-up; Row", "Cuff"],
                    ["Sat", "Zone-2 Run", ""],
                    ["Sun", "Rest + Mobility", ""],
                ],
                columns=["Day", "Main Work", "Notes"],
            )
        )
    with st.expander("3. Warm-up & Failure Rules"):
        st.markdown(
            """
- Dynamic only; 1–2 ramp sets.
- Skip static pre-lift.
- Stop 3–4 reps shy on compounds.
"""
        )
    with st.expander("4. Cardio Tweaks"):
        st.markdown(
            """
- **HIIT:** 4×4 or 10-min @90% HRₘₐₓ
- **Endurance:** ≥60min Z2
"""
        )
    with st.expander("5. Mobility Flow"):
        st.markdown("Prep, Joint, Animal, Cuff circuits as outlined.")
    with st.expander("6. Nutrition & Rationale"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                "**Protein:** 1.6–2.2 g/kg/day<br>**Creatine:** 3–5 g/day<br>**Omega-3:** load 3 g EPA+2 g DHA → 2 g/day",
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                "**Energy:** 10–15% deficit<br>**Sleep:** 7–9 h/night<br>**Why:** top sets + volume hit strength & hypertrophy",
                unsafe_allow_html=True,
            )

# Resistance Tab
with tabs[1]:
    st.header("🏋️ Resistance")
    c1, c2 = st.columns(2)
    with c1:
        d = st.date_input("Date", date.today())
        week = st.selectbox("Week", [1, 2, 3, 4])
        day = st.selectbox("Day", list(weekly_resistance.keys()))
        ex = st.selectbox("Exercise", [e["exercise"] for e in weekly_resistance[day]])
    with c2:
        target = next(
            e["target"] for e in weekly_resistance[day] if e["exercise"] == ex
        )
        repeat = st.checkbox("Repeat last session")
        sets = st.number_input("# Sets", 1, 10, 3)
    entries = []
    pw, pr, pi = None, None, None
    for i in range(1, sets + 1):
        with st.expander(f"Set {i}"):
            if repeat:
                w0, r0, i0 = fetch_last(ex, i)
            else:
                w0, r0, i0 = pw, pr, pi
            maxw = float(150)
            aw = st.slider(
                "Weight (kg)", 0.0, maxw, float(w0 or 0), step=0.5, key=f"res_w_{i}"
            )
            ar = st.slider("Reps", 1, 20, int(r0 or 6), key=f"res_r_{i}")
            rir = st.slider("RIR", 0, 5, int(i0 or 3), key=f"res_i_{i}")
            pw, pr, pi = aw, ar, rir
            entries.append((d, week, day, ex, i, target, aw, ar, rir))
    if st.button("Save Resistance"):
        c.executemany(
            "INSERT INTO resistance(date,week,day,exercise,set_number,target,actual_weight,actual_reps,rir) VALUES(?,?,?,?,?,?,?,?,?)",
            entries,
        )
        conn.commit()
        st.success("Saved Resistance")

# Mobility Tab
with tabs[2]:
    st.header("🤸 Mobility")
    d = st.date_input("Date", date.today(), key="mob_date")
    p = st.checkbox("Prep (Box breathing, Cat/Cow, CARs)")
    j = st.checkbox("Joint Flow (WGS, Down-Dog↔Cobra, Lizard, Pigeon)")
    a = st.checkbox("Animal Circuit (Beast, Ape, Scorpion, Crab, Side Kick)")
    cf = st.checkbox("Cuff Finisher (Band ER, Prone Y)")
    if st.button("Save Mobility"):
        c.execute(
            "INSERT INTO mobility(date,prep_done,joint_flow_done,animal_circuit_done,cuff_finisher_done) VALUES(?,?,?,?,?)",
            (d, int(p), int(j), int(a), int(cf)),
        )
        conn.commit()
        st.success("Saved Mobility")

# Cardio Tab
with tabs[3]:
    st.header("🏃 Cardio")
    d = st.date_input("Date", date.today(), key="car_date")
    t = st.selectbox(
        "Type", ["HIIT (4×4)", "10-min HIIT", "Zone-2 Run", "Other"], key="car_type"
    )
    dcol, hcol = st.columns(2)
    dur = dcol.number_input("Duration (min)", 1, 180, 30, key="car_dur")
    hr = hcol.number_input("Avg HR (bpm)", 30, 220, 120, key="car_hr")
    if st.button("Save Cardio"):
        c.execute(
            "INSERT INTO cardio(date,type,duration_min,avg_hr) VALUES(?,?,?,?)",
            (d, t, dur, hr),
        )
        conn.commit()
        st.success("Saved Cardio")

# Logs Tab
with tabs[4]:
    st.header("📊 Logs")
    st.subheader("Resistance")
    st.dataframe(load_table("resistance"))
    st.subheader("Mobility")
    st.dataframe(load_table("mobility"))
    st.subheader("Cardio")
    st.dataframe(load_table("cardio"))
    st.subheader("Progress Charts")
    df = load_table("resistance")
    for lift in df["exercise"].unique():
        ddf = df[df["exercise"] == lift]
        ddf["date"] = pd.to_datetime(ddf["date"])
        chart = ddf.groupby("date")["actual_weight"].max().sort_index()
        st.line_chart(chart, use_container_width=True, height=200)
