# app.py
# Streamlit-based 4-Week Strength & Conditioning Tracker with Pages and Guide

import streamlit as st
import pandas as pd
import sqlite3
from datetime import date

# --- Database & Migration Setup ---
conn = sqlite3.connect("workout_tracker.db", check_same_thread=False)
c = conn.cursor()

# Ensure tables exist
c.execute("""
CREATE TABLE IF NOT EXISTS resistance(
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
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS mobility(
    id INTEGER PRIMARY KEY,
    date TEXT,
    prep_done INTEGER,
    joint_flow_done INTEGER,
    animal_circuit_done INTEGER,
    cuff_finisher_done INTEGER
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS cardio(
    id INTEGER PRIMARY KEY,
    date TEXT,
    type TEXT,
    duration_min INTEGER,
    avg_hr INTEGER
)
""")
conn.commit()

# Program Definitions
weekly_resistance = {
    "Monday": [
        {"exercise": "Back-squat", "target": "1×4 @ 88% 1RM + 3×6 @ 78% 1RM"},
        {"exercise": "Hip-thrust", "target": "4×8"},
    ],
    "Tuesday": [
        {"exercise": "Bench Press", "target": "1×4 @ 88% 1RM + 3×6 @ 78% 1RM"},
        {"exercise": "Overhead Press", "target": "3×6"},
        {"exercise": "Dips", "target": "3×10"},
    ],
    "Thursday AM": [
        {"exercise": "Deadlift", "target": "1×3 @ 90% 1RM + 3×6 @ 80% 1RM"},
        {"exercise": "Romanian Deadlift", "target": "3×8"},
    ],
    "Friday": [
        {"exercise": "Weighted Pull-up", "target": "3×6–8"},
        {"exercise": "Chest-supported Row", "target": "3×10"},
    ],
}


# Helper: load tables
@st.cache_data
def load_table(table):
    return pd.read_sql_query(f"SELECT * FROM {table} ORDER BY date DESC", conn)


# App Layout
st.title("4-Week Strength & Conditioning Program")
page = st.sidebar.radio(
    "Page", ["Guide", "Resistance", "Mobility", "Cardio", "Logs & Charts"]
)

# --- Guide Page ---
if page == "Guide":
    st.header("📖 Program Guide")
    # Framework
    with st.expander("1. Resistance-Training Framework", expanded=True):
        st.markdown(
            """
**Max-strength**

- **Target:** ≥ 85% 1 RM · 1–5 reps  
- **Weekly Hard Sets:** 5–10 sets per exercise  
- **Rest:** 2–5 min

**Hypertrophy/Body-Composition**

- **Target:** 60–80% 1 RM · 6–12 reps  
- **Weekly Hard Sets:** 10–20 sets per muscle  
- **Rest:** 1–2 min
"""
        )
        st.markdown(
            "**Template Tweaks:** adding one top set at 87–90% 1 RM to existing 3×6 @75–82% and raising accessory volume to hit 12–16 weekly sets."
        )
    # Weekly Template
    with st.expander("2. Weekly Template", expanded=False):
        st.table(
            pd.DataFrame(
                [
                    [
                        "Mon",
                        "Back‑squat: 1×4 @88% → 3×6 @78%",
                        "Mini‑band glute activation",
                    ],
                    [
                        "Tue",
                        "Bench: 1×4 @88% → 3×6 @78% · OHP 3×6 · Dips 3×10",
                        "Shoulder ER warm‑up",
                    ],
                    [
                        "Wed",
                        "Mobility Flow (§5)",
                        "Dynamic only; skip static stretching",
                    ],
                    ["Thu AM", "Deadlift: 1×3 @90% → 3×6 @80% · RDL 3×8", ""],
                    ["Thu PM", "HIIT 4×4 @85–95% HRmax (3 min @70%)", "↑VO₂max"],
                    [
                        "Fri",
                        "Pull‑up 3×6–8 · Row 3×10",
                        "Band ER @90° 2×12 + prone Y 2×15",
                    ],
                    ["Sat", "Zone‑2 Run 40–45 min (~70% HRmax)", ""],
                    ["Sun", "Rest + short mobility", ""],
                ],
                columns=["Day", "Main Work", "Notes"],
            )
        )
    # Warm-up & Failure Rules
    with st.expander("3. Warm-up & Failure Rules"):
        st.markdown(
            """
- **Dynamic Warm-ups:** one or two ramp sets per lift.  
- **Static Stretching:** optional, avoid pre-lift.  
- **Failure Rule:** stop 3–4 reps shy on compounds; isolate moves to near failure if desired.
"""
        )
    # Cardio Tweaks
    with st.expander("4. Cardio Tweaks"):
        st.markdown(
            """
| Type       | Prescription                         | Rationale                                   |
|------------|--------------------------------------|---------------------------------------------|
| **HIIT**   | 4×4 or 10 min protocol; 2:1 work-rest| +3.5 mL·kg⁻¹·min⁻¹ VO₂ₘₐₓ vs. sprints         |
| **Endurance**| ≥60 min easy or two 30–45 min bouts | Preserves mitochondria & compliance         |
"""
        )
    # Mobility Flow
    with st.expander("5. Mobility Flow"):
        st.markdown(
            """
**Prep (3 min):** box‑breathing, Cat/Cow ×8, shoulder CARs ×5/side  
**Joint-Flow (10 min):** WGS ×5/side, Down‑Dog↔Cobra ×6, Lizard 30 s/side, Pigeon CR ×3, Deep‑squat stretch 60 s  
**Animal Circuit (3 rnd):** Beast, Ape, Scorpion, Crab, Side Kick‑Through (40 s on/20 s rest)  
**Cuff Finisher:** band ER 2×20 + prone Y 2×15
"""
        )
    # Nutrition & Why
    with st.expander("6. Nutrition & Rationale"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                """
**Protein:** 1.6–2.2 g/kg/day  
**Creatine:** 3–5 g/day  
**Omega‑3:** 3 g EPA +2 g DHA load, then 2 g/day
"""
            )
        with col2:
            st.markdown(
                """
**Energy:** 10–15% kcal deficit for recomp  
**Sleep:** 7–9 h/night  
**Why:** heavier top sets +75–82% volume hit strength & hypertrophy sweet spots
"""
            )

# --- Resistance Page ---
elif page == "Resistance":
    st.header("Log Resistance")
    d = st.date_input("Date", date.today(), key="res_date")
    week = st.selectbox("Week Number", [1, 2, 3, 4], key="res_week")
    day = st.selectbox("Day", list(weekly_resistance.keys()), key="res_day")
    ex_list = [item["exercise"] for item in weekly_resistance[day]]
    exercise = st.selectbox("Exercise", ex_list, key="res_exercise")
    target = next(
        item["target"]
        for item in weekly_resistance[day]
        if item["exercise"] == exercise
    )
    num_sets = st.number_input(
        "# of sets", min_value=1, max_value=10, value=3, key="res_sets"
    )
    entries = []
    for set_num in range(1, num_sets + 1):
        st.markdown(f"**Set {set_num}**")
        aw = st.number_input(
            "Weight (kg)", min_value=0.0, step=0.5, key=f"res_w_{set_num}"
        )
        ar = st.number_input("Reps", min_value=1, max_value=50, key=f"res_r_{set_num}")
        rir = st.slider("RIR", 0, 5, 3, key=f"res_i_{set_num}")
        entries.append((d, week, day, exercise, set_num, target, aw, ar, rir))
    if st.button("Save Resistance"):
        c.executemany(
            "INSERT INTO resistance(date, week, day, exercise, set_number, target, actual_weight, actual_reps, rir) VALUES (?,?,?,?,?,?,?,?,?)",
            entries,
        )
        conn.commit()
        st.success("Resistance logged")

# --- Mobility Page ---
elif page == "Mobility":
    st.header("Mobility Check-In")
    d = st.date_input("Date", date.today(), key="mob_date")
    st.markdown("- **Prep:** Box breathing, Cat/Cow, Shoulder CARs")
    prep = st.checkbox("Completed Prep", key="mob_prep")
    st.markdown("- **Joint Flow:** WGS, Down-Dog ↔ Cobra, Lizard, Pigeon, Deep Squat")
    joint = st.checkbox("Completed Joint Flow", key="mob_joint")
    st.markdown(
        "- **Animal Circuit:** Loaded Beast, Ape Reach, Scorpion, Crab Reach, Side Kick-Through"
    )
    animal = st.checkbox("Completed Animal Circuit", key="mob_animal")
    st.markdown("- **Cuff Finisher:** Band ER, Prone Y")
    cuff = st.checkbox("Completed Cuff Finisher", key="mob_cuff")
    if st.button("Save Mobility Check-In"):
        c.execute(
            "INSERT INTO mobility(date, prep_done, joint_flow_done, animal_circuit_done, cuff_finisher_done) VALUES (?,?,?,?,?)",
            (d, int(prep), int(joint), int(animal), int(cuff)),
        )
        conn.commit()
        st.success("Mobility check-in saved")

# --- Cardio Page ---
elif page == "Cardio":
    st.header("Log Cardio")
    d = st.date_input("Date", date.today(), key="cardio_date")
    ctype = st.selectbox(
        "Type", ["HIIT (4×4)", "10-min HIIT", "Zone-2 Run", "Other"], key="cardio_type"
    )
    duration = st.number_input(
        "Duration (minutes)",
        min_value=1,
        max_value=180,
        value=30,
        step=1,
        key="cardio_dur",
    )
    avg_hr = st.number_input(
        "Average Heart Rate (bpm)",
        min_value=30,
        max_value=220,
        value=120,
        step=1,
        key="cardio_hr",
    )
    if st.button("Save Cardio"):
        c.execute(
            "INSERT INTO cardio(date, type, duration_min, avg_hr) VALUES (?,?,?,?)",
            (d, ctype, duration, avg_hr),
        )
        conn.commit()
        st.success("Cardio logged")

# --- Logs & Charts Page ---
elif page == "Logs & Charts":
    st.header("Resistance Logs")
    df_res = load_table("resistance")
    st.dataframe(df_res)
    st.header("Mobility Logs")
    df_mob = load_table("mobility")
    st.dataframe(df_mob)
    st.header("Cardio Logs")
    df_card = load_table("cardio")
    st.dataframe(df_card)
    st.header("Progress Charts")
    for lift in df_res["exercise"].unique():
        df_l = df_res[df_res["exercise"] == lift]
        if not df_l.empty:
            df_l["date"] = pd.to_datetime(df_l["date"])
            df_plot = df_l.groupby("date")["actual_weight"].max().sort_index()
            st.line_chart(df_plot, height=200, use_container_width=True)
            st.write(f"{lift} max weight over time")
