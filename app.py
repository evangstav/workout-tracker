# app.py
# Streamlit 4-Week Strength & Conditioning Tracker
# Mobile-friendly with full functionality

import os  # For OPENAI_API_KEY
from datetime import date
from typing import Dict, List  # Added import

import streamlit as st

# Project specific imports
from database import (
    create_user_in_db,  # Used in show_login_signup_forms
    get_user_from_db,  # Used in show_login_signup_forms
    init_db,
    verify_password,  # Used in show_login_signup_forms
)

# Tab rendering functions are now in ui_tabs.py
from ui_tabs import (
    render_cardio_tab,
    render_guide_tab,
    render_logs_tab,
    render_mobility_tab,
    render_nutrition_tab,
    render_profile_tab,
    render_resistance_tab,
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Used by render_nutrition_tab

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
# All DB related functions (get_db_connection, init_db, etc.) and DB_NAME
# are now imported from database.py

init_db()  # Initialize database and tables on app startup


# --- Authentication Helpers ---
# hash_password, verify_password, create_user_in_db, get_user_from_db
# are now imported from database.py


# --- Session State Initialization ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None
if "analyzed_nutrition_content" not in st.session_state:
    st.session_state.analyzed_nutrition_content = None

# --- Program Definitions ---
# (This remains global as it's program structure, not user data)
weekly_resistance: Dict[str, List[Dict[str, str]]] = {
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
# Helper functions like get_target_params_for_set, _save_form_data, load_table, fetch_last
# have been moved to ui_tabs.py as they are primarily used by the tab rendering logic.


# --- Login/Signup UI ---
# This remains in app.py as it's part of the core app structure before tabs are shown.
def show_login_signup_forms() -> None:
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
# Tab rendering functions are now imported from ui_tabs.py

if not st.session_state.get("logged_in", False):  # Use .get for safety
    show_login_signup_forms()
    st.title("Welcome to the 4-Week Program Tracker!")
    st.markdown(
        "Please log in or sign up using the sidebar to access your personalized workout tracking."
    )
else:
    st.sidebar.markdown(f"Logged in as **{st.session_state.username}**")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.cache_data.clear()  # Clear cache on logout
        st.rerun()

    # --- Main Application with Tabs (only if logged in) ---
    tabs = st.tabs(
        ["Guide", "Resistance", "Mobility", "Cardio", "Nutrition", "Profile", "Logs"]
    )

    # Guide Tab (No user-specific data, can remain as is)
    with tabs[0]:
        render_guide_tab()

    # Resistance Tab
    with tabs[1]:
        render_resistance_tab(weekly_resistance)  # Pass weekly_resistance

    # Mobility Tab
    with tabs[2]:
        render_mobility_tab()

    # Cardio Tab
    with tabs[3]:
        render_cardio_tab()

    # Nutrition Tab (New tab, index 4)
    with tabs[4]:
        render_nutrition_tab(OPENAI_API_KEY)  # Pass OPENAI_API_KEY

    # Profile Tab
    with tabs[5]:  # Index updated from 4 to 5
        render_profile_tab()

    # Logs Tab
    with tabs[6]:  # Index updated from 5 to 6
        render_logs_tab()
