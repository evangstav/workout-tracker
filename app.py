# app.py
# Streamlit 4-Week Strength & Conditioning Tracker
# Mobile-friendly with full functionality

import streamlit as st
import pandas as pd
import sqlite3
from datetime import date
import hashlib  # For password hashing

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
DB_NAME = "workout_tracker.db"


def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


def _add_column_if_not_exists(cursor, table_name, column_name, column_type_with_constraints):
    """Helper to add a column to a table if it doesn't already exist."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    if column_name not in columns:
        try:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type_with_constraints}")
        except sqlite3.OperationalError as e:
            # This check is for "duplicate column name", which might occur in rare scenarios
            # even after the "if column_name not in columns" check.
            if f"duplicate column name: {column_name}" not in str(e):  # pragma: no cover
                raise

def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    # Users table
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    )""")

    # Create or alter resistance table
    c.execute("""CREATE TABLE IF NOT EXISTS resistance(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT,
        week INTEGER,
        day TEXT,
        exercise TEXT,
        set_number INTEGER,
        target TEXT,
        actual_weight REAL,
        actual_reps INTEGER,
        rir INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    _add_column_if_not_exists(c, "resistance", "set_number", "INTEGER DEFAULT 1")
    _add_column_if_not_exists(c, "resistance", "user_id", "INTEGER")

    # Mobility table
    c.execute("""CREATE TABLE IF NOT EXISTS mobility(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT,
        prep_done INTEGER,
        joint_flow_done INTEGER,
        animal_circuit_done INTEGER,
        cuff_finisher_done INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")
    _add_column_if_not_exists(c, "mobility", "user_id", "INTEGER")
                
    # Cardio table
    c.execute("""CREATE TABLE IF NOT EXISTS cardio(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT,
        type TEXT,
        duration_min INTEGER,
        avg_hr INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")
    _add_column_if_not_exists(c, "cardio", "user_id", "INTEGER")

    # --- Data Migration: Assign existing orphan records to the first user ---
    c.execute("SELECT id FROM users ORDER BY id LIMIT 1")
    first_user = c.fetchone()

    if first_user:
        first_user_id = first_user["id"]
        tables_to_migrate = ["resistance", "mobility", "cardio"]
        for table_name in tables_to_migrate:
            # Check if user_id column exists before trying to update it
            # This is a safeguard, as previous code should have added it.
            cols = [
                row[1]
                for row in c.execute(f"PRAGMA table_info({table_name})").fetchall()
            ]
            if "user_id" in cols:
                c.execute(
                    f"UPDATE {table_name} SET user_id = ? WHERE user_id IS NULL",
                    (first_user_id,),
                )

    conn.commit()
    conn.close()


init_db()  # Initialize database and tables on app startup


# --- Authentication Helpers ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(stored_password_hash, provided_password):
    return stored_password_hash == hash_password(provided_password)


def create_user_in_db(username, password):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, hash_password(password)),
        )
        conn.commit()
        user_id = c.lastrowid
        return user_id
    except sqlite3.IntegrityError:  # Username already exists
        return None
    finally:
        conn.close()


def get_user_from_db(username):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    return user


# --- Session State Initialization ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None

# --- Program Definitions ---
# (This remains global as it's program structure, not user data)
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
# Note: The global 'conn' object is removed. Connections are now managed per function.

def _save_form_data(insert_query, data_payload, success_message, is_many=False):
    """Helper to save form data to the database."""
    if st.session_state.user_id is None:  # General check for logged-in user
        st.error("User not logged in. Cannot save data.")  # pragma: no cover
        return

    # For batch inserts, data_payload is a list. If it's empty, no action.
    if is_many and not data_payload:
        st.warning("No data to save.") # Typically for resistance sets
        return
    
    # For single inserts, data_payload is a tuple.
    # An empty tuple would cause c.execute to fail, which is caught by try-except.

    conn = get_db_connection()
    c = conn.cursor()
    try:
        if is_many:
            c.executemany(insert_query, data_payload)
        else:
            c.execute(insert_query, data_payload)
        conn.commit()
        st.success(success_message)
        st.cache_data.clear()  # Clear cache after saving new data
    except sqlite3.Error as e:  # pragma: no cover
        st.error(f"Database error: {e}")
    finally:
        conn.close()

@st.cache_data  # Cache will be specific to user_id due to it being an argument
def load_table(name, user_id):
    conn = get_db_connection()
    # Ensure user_id is not None before querying
    if user_id is None:
        conn.close()
        return pd.DataFrame()  # Return empty DataFrame if no user_id
    df = pd.read_sql_query(
        f"SELECT * FROM {name} WHERE user_id = ? ORDER BY date DESC",
        conn,
        params=(user_id,),
    )
    conn.close()
    return df


@st.cache_data  # Cache will be specific to user_id
def fetch_last(exercise, set_num, user_id):
    conn = get_db_connection()
    # Ensure user_id is not None
    if user_id is None:
        conn.close()
        return None, None, None
    df = pd.read_sql_query(
        "SELECT actual_weight, actual_reps, rir FROM resistance WHERE exercise=? AND set_number=? AND user_id = ? ORDER BY date DESC LIMIT 1",
        conn,
        params=(exercise, set_num, user_id),
    )
    conn.close()
    if not df.empty:
        r = df.iloc[0]
        return float(r["actual_weight"]), int(r["actual_reps"]), int(r["rir"])
    return None, None, None


# --- Login/Signup UI ---
def show_login_signup_forms():
    st.sidebar.title("User Account")
    form_choice = st.sidebar.radio(
        "Choose Action", ["Login", "Sign Up"], key="auth_choice"
    )

    if form_choice == "Login":
        with st.sidebar.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            login_button = st.form_submit_button("Login")

            if login_button:
                user = get_user_from_db(username)
                if user and verify_password(user["password_hash"], password):
                    st.session_state.logged_in = True
                    st.session_state.user_id = user["id"]
                    st.session_state.username = user["username"]
                    st.cache_data.clear()  # Clear cache on login
                    st.rerun()
                else:
                    st.sidebar.error("Invalid username or password")

    elif form_choice == "Sign Up":
        with st.sidebar.form("signup_form"):
            new_username = st.text_input("Choose Username", key="signup_username")
            new_password = st.text_input(
                "Choose Password (min 4 chars)", type="password", key="signup_password"
            )
            confirm_password = st.text_input(
                "Confirm Password", type="password", key="signup_confirm_password"
            )
            signup_button = st.form_submit_button("Sign Up")

            if signup_button:
                if not new_username or not new_password:
                    st.sidebar.error("Username and password cannot be empty.")
                elif new_password == confirm_password:
                    if len(new_password) >= 4:
                        user_id = create_user_in_db(new_username, new_password)
                        if user_id:
                            st.sidebar.success("Account created! Please login.")
                        else:
                            st.sidebar.error(
                                "Username already exists or database error."
                            )
                    else:
                        st.sidebar.error("Password should be at least 4 characters.")
                else:
                    st.sidebar.error("Passwords do not match.")


# --- Main Application Logic ---
if not st.session_state.get("logged_in", False):  # Use .get for safety
    show_login_signup_forms()
    st.info("Please log in or sign up using the sidebar to access the app.")
else:
    st.sidebar.markdown(f"Logged in as **{st.session_state.username}**")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.cache_data.clear()  # Clear cache on logout
        st.rerun()

    # --- Main Application with Tabs (only if logged in) ---
    tabs = st.tabs(["Guide", "Resistance", "Mobility", "Cardio", "Logs"])

    # Guide Tab (No user-specific data, can remain as is)
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
    current_user_id = st.session_state.user_id  # Get current user's ID
    for i in range(1, sets + 1):
        with st.expander(f"Set {i}"):
            if repeat:
                w0, r0, i0 = fetch_last(ex, i, current_user_id)
            else:
                w0, r0, i0 = pw, pr, pi
            maxw = float(150)
            aw = st.slider(
                "Weight (kg)", 0.0, maxw, float(w0 or 0), step=0.5, key=f"res_w_{i}"
            )
            ar = st.slider("Reps", 1, 20, int(r0 or 6), key=f"res_r_{i}")
            rir = st.slider("RIR", 0, 5, int(i0 or 3), key=f"res_i_{i}")
            pw, pr, pi = aw, ar, rir
            # Add user_id to the entry
            entries.append((current_user_id, d, week, day, ex, i, target, aw, ar, rir))
    if st.button("Save Resistance"):
        # The 'if not entries' check is specific and remains here.
        # The user login check is handled by _save_form_data.
        if not entries:  # pragma: no cover
            st.warning("No sets to save.")
        else:
            _save_form_data(
                insert_query="INSERT INTO resistance(user_id,date,week,day,exercise,set_number,target,actual_weight,actual_reps,rir) VALUES(?,?,?,?,?,?,?,?,?,?)",
                data_payload=entries,
                success_message="Saved Resistance",
                is_many=True
            )

# Mobility Tab
with tabs[2]:
    st.header("🤸 Mobility")
    d = st.date_input("Date", date.today(), key="mob_date")
    p = st.checkbox("Prep (Box breathing, Cat/Cow, CARs)")
    j = st.checkbox("Joint Flow (WGS, Down-Dog↔Cobra, Lizard, Pigeon)")
    a = st.checkbox("Animal Circuit (Beast, Ape, Scorpion, Crab, Side Kick)")
    cf = st.checkbox("Cuff Finisher (Band ER, Prone Y)")
    if st.button("Save Mobility"):
        current_user_id = st.session_state.user_id # Needed to construct data_payload
        # User login check is handled by _save_form_data.
        data_payload = (current_user_id, d, int(p), int(j), int(a), int(cf))
        _save_form_data(
            insert_query="INSERT INTO mobility(user_id,date,prep_done,joint_flow_done,animal_circuit_done,cuff_finisher_done) VALUES(?,?,?,?,?,?)",
            data_payload=data_payload,
            success_message="Saved Mobility"
        )

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
        current_user_id = st.session_state.user_id # Needed to construct data_payload
        # User login check is handled by _save_form_data.
        data_payload = (current_user_id, d, t, dur, hr)
        _save_form_data(
            insert_query="INSERT INTO cardio(user_id,date,type,duration_min,avg_hr) VALUES(?,?,?,?,?)",
            data_payload=data_payload,
            success_message="Saved Cardio"
        )

# Logs Tab
with tabs[4]:
    st.header("📊 Logs")
    current_user_id = st.session_state.user_id
    if current_user_id is None:  # pragma: no cover
        st.warning("Please log in to see your logs.")
    else:
        st.subheader("Resistance")
        st.dataframe(load_table("resistance", current_user_id))
        st.subheader("Mobility")
        st.dataframe(load_table("mobility", current_user_id))
        st.subheader("Cardio")
        st.dataframe(load_table("cardio", current_user_id))

        st.subheader("Progress Charts")
        df_resistance = load_table("resistance", current_user_id)
        if not df_resistance.empty:
            for lift in df_resistance["exercise"].unique():
                ddf = df_resistance[
                    df_resistance["exercise"] == lift
                ].copy()  # Use .copy() to avoid SettingWithCopyWarning
                ddf["date"] = pd.to_datetime(ddf["date"])
                # Ensure data is sorted by date for charting max weight over time
                chart_data = (
                    ddf.sort_values(by="date")
                    .groupby(pd.Grouper(key="date", freq="D"))["actual_weight"]
                    .max()
                    .fillna(0)
                )
                if not chart_data.empty:
                    st.markdown(f"**{lift} - Max Weight Over Time**")
                    st.line_chart(chart_data, use_container_width=True, height=200)
        else:
            st.write("No resistance data yet to display charts.")
