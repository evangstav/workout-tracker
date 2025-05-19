import streamlit as st
import pandas as pd
import sqlite3 # For sqlite3.Error in _save_form_data
from datetime import date
import re # For parsing target strings
from typing import List, Tuple, Dict, Any, Optional, Union

# Imports from project modules that were previously in app.py for these functions
from database import (
    get_db_connection,
    save_or_update_1rm,
    get_latest_1rm,
    save_or_update_nutrition_log,
    get_nutrition_log_by_date,
    get_user_from_db,
    verify_password,
    update_user_password,
    # Added delete functions
    delete_resistance_set_from_db,
    delete_nutrition_log_from_db,
    delete_1rm_from_db,
)
from ai_utils import extract_meal_data, DaySummary

# --- Helper functions moved from app.py ---

def get_target_params_for_set(
    target_string: str, current_set_num: int
) -> Tuple[Optional[int], Optional[int]]:
    """
    Parses the target string (e.g., "1x4 @88% + 3x6-8 @78%") for a specific set number.
    Returns a tuple (percentage, reps_value).
    reps_value is an int if a specific number or first number of a range is found.
    Returns (None, None) if not found or not applicable for either.
    """
    segments = target_string.split("+")
    processed_sets_count = 0
    for segment in segments:
        segment = segment.strip()
        # Pattern for "NxR @P%" - R can be a number or range (e.g., 6-8, 6–8)
        match_with_percentage = re.match(r"(\d+)×([\d–-]+)\s*@(\d+)%", segment)
        # Pattern for "NxR" (no percentage) - R can be a number or range
        match_without_percentage = re.match(r"(\d+)×([\d–-]+)", segment)

        num_sets_in_segment = 0
        reps_str_in_segment = None
        percentage_in_segment = None

        if match_with_percentage:
            num_sets_in_segment = int(match_with_percentage.group(1))
            reps_str_in_segment = match_with_percentage.group(2)
            percentage_in_segment = int(match_with_percentage.group(3))
        elif match_without_percentage:
            num_sets_in_segment = int(match_without_percentage.group(1))
            reps_str_in_segment = match_without_percentage.group(2)
        else:
            continue  # Segment format not recognized

        if (
            current_set_num > processed_sets_count
            and current_set_num <= processed_sets_count + num_sets_in_segment
        ):
            reps_val = None
            if reps_str_in_segment:
                try:
                    reps_val = int(reps_str_in_segment)
                except ValueError:
                    # Try parsing first number of a range like "6-8" or "6–8"
                    if "–" in reps_str_in_segment:  # en-dash
                        try:
                            reps_val = int(reps_str_in_segment.split("–")[0])
                        except ValueError:  # pragma: no cover
                            pass  # Keep reps_val as None
                    elif "-" in reps_str_in_segment:  # hyphen
                        try:
                            reps_val = int(reps_str_in_segment.split("-")[0])
                        except ValueError:  # pragma: no cover
                            pass  # Keep reps_val as None
            return percentage_in_segment, reps_val

        processed_sets_count += num_sets_in_segment
    return None, None  # No specific parameters found for this set number


def _save_form_data(
    insert_query: str,
    data_payload: Union[Tuple[Any, ...], List[Tuple[Any, ...]]],
    success_message: str,
    is_many: bool = False,
) -> None:
    """Helper to save form data to the database."""
    if st.session_state.user_id is None:  # General check for logged-in user
        st.error("User not logged in. Cannot save data.")  # pragma: no cover
        return

    # For batch inserts, data_payload is a list. If it's empty, no action.
    if is_many and not data_payload:
        st.warning("No data to save.")  # Typically for resistance sets
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
def load_table(name: str, user_id: Optional[int]) -> pd.DataFrame:
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
def fetch_last(
    exercise: str, set_num: int, user_id: Optional[int]
) -> Tuple[Optional[float], Optional[int], Optional[int]]:
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


# --- Tab Rendering Functions ---

def render_guide_tab():
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

def render_resistance_tab(weekly_resistance: Dict[str, List[Dict[str, str]]]):
    st.header("🏋️ Resistance")
    c1, c2 = st.columns(2)
    with c1:
        d = st.date_input("Date", date.today())
        week = st.selectbox("Week", [1, 2, 3, 4])
        day = st.selectbox("Day", list(weekly_resistance.keys()))
        ex = st.selectbox(
            "Exercise", [e["exercise"] for e in weekly_resistance[day]]
        )
    with c2:
        target = next(
            e["target"] for e in weekly_resistance[day] if e["exercise"] == ex
        )
        repeat = st.checkbox("Repeat last session")
        sets = st.number_input("# Sets", 1, 10, 3)
    entries = []
    pw, pr, pi = None, None, None  # Previous set's weight, reps, RIR
    current_user_id = st.session_state.user_id
    SLIDER_STEP = 0.5  # Define slider step for weight
    MAX_WEIGHT_SLIDER = 150.0  # Max weight for slider

    for i in range(1, sets + 1):  # For each set
        w0, r0, i0 = None, None, None  # Default values for current set's sliders

        if repeat:
            # If repeating last session, fetch data for this specific set number
            w0_db, r0_db, i0_db = fetch_last(ex, i, current_user_id)
            w0, r0, i0 = w0_db, r0_db, i0_db
        else:
            # Not repeating: try to calculate from 1RM or use previous set's values
            one_rm_data = get_latest_1rm(current_user_id, ex)
            target_percentage, target_reps_prog = get_target_params_for_set(
                target, i
            )

            # Initialize with previous set's values (or None if first set)
            w0_prev, r0_prev, i0_prev = pw, pr, pi
            w0, r0, i0 = w0_prev, r0_prev, i0_prev

            if one_rm_data and target_percentage is not None:
                one_rm_value = one_rm_data["one_rep_max"]
                calculated_w = (target_percentage / 100.0) * one_rm_value
                w0 = (
                    round(calculated_w / SLIDER_STEP) * SLIDER_STEP
                )  # Use calculated weight

                if target_reps_prog is not None:
                    r0 = target_reps_prog  # Use reps from program if available
                # If target_reps_prog is None, r0 remains r0_prev (from previous set or None)
                # i0 remains i0_prev (from previous set or None)
            # If no 1RM or no target_percentage, w0, r0, i0 remain as previous set's values

        with st.expander(f"Set {i}"):
            # Use (w0 or 0) for weight, (r0 or 6) for reps, (i0 or 3) for RIR as slider defaults
            aw = st.slider(
                "Weight (kg)",
                0.0,
                MAX_WEIGHT_SLIDER,
                float(w0 if w0 is not None else 0),
                step=SLIDER_STEP,
                key=f"res_w_{i}",
            )
            ar = st.slider(
                "Reps", 1, 20, int(r0 if r0 is not None else 6), key=f"res_r_{i}"
            )
            rir = st.slider(
                "RIR", 0, 5, int(i0 if i0 is not None else 3), key=f"res_i_{i}"
            )

            pw, pr, pi = (
                aw,
                ar,
                rir,
            )  # Update previous set's values for the next iteration
            # Add user_id to the entry
            entries.append(
                (current_user_id, d, week, day, ex, i, target, aw, ar, rir)
            )
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
                is_many=True,
            )

def render_mobility_tab():
    st.header("🤸 Mobility")
    d = st.date_input("Date", date.today(), key="mob_date")
    p = st.checkbox("Prep (Box breathing, Cat/Cow, CARs)")
    j = st.checkbox("Joint Flow (WGS, Down-Dog↔Cobra, Lizard, Pigeon)")
    a = st.checkbox("Animal Circuit (Beast, Ape, Scorpion, Crab, Side Kick)")
    cf = st.checkbox("Cuff Finisher (Band ER, Prone Y)")
    if st.button("Save Mobility"):
        current_user_id = (
            st.session_state.user_id
        )  # Needed to construct data_payload
        # User login check is handled by _save_form_data.
        data_payload = (current_user_id, d, int(p), int(j), int(a), int(cf))
        _save_form_data(
            insert_query="INSERT INTO mobility(user_id,date,prep_done,joint_flow_done,animal_circuit_done,cuff_finisher_done) VALUES(?,?,?,?,?,?)",
            data_payload=data_payload,
            success_message="Saved Mobility",
        )

def render_cardio_tab():
    st.header("🏃 Cardio")
    d = st.date_input("Date", date.today(), key="car_date")
    t = st.selectbox(
        "Type", ["HIIT (4×4)", "10-min HIIT", "Zone-2 Run", "Other"], key="car_type"
    )
    dcol, hcol = st.columns(2)
    dur = dcol.number_input("Duration (min)", 1, 180, 30, key="car_dur")
    hr = hcol.number_input("Avg HR (bpm)", 30, 220, 120, key="car_hr")
    if st.button("Save Cardio"):
        current_user_id = (
            st.session_state.user_id
        )  # Needed to construct data_payload
        # User login check is handled by _save_form_data.
        data_payload = (current_user_id, d, t, dur, hr)
        _save_form_data(
            insert_query="INSERT INTO cardio(user_id,date,type,duration_min,avg_hr) VALUES(?,?,?,?,?)",
            data_payload=data_payload,
            success_message="Saved Cardio",
        )

def render_nutrition_tab(OPENAI_API_KEY: Optional[str]):
    st.header("🥗 Nutrition Log")
    current_user_id = st.session_state.user_id
    if current_user_id is None:  # pragma: no cover
        st.warning("Please log in to manage nutrition logs.")
    else:

        def clear_analysis_callback():
            st.session_state.analyzed_nutrition_content = None

        log_date_nutrition = st.date_input(
            "Select date for meal log",
            date.today(),
            key="nutrition_log_date",
            on_change=clear_analysis_callback,
        )
        log_date_str_nutrition = log_date_nutrition.isoformat()

        existing_log_nutrition = get_nutrition_log_by_date(
            current_user_id, log_date_str_nutrition
        )

        # If existing log has stored nutritional info and no fresh analysis is in session state,
        # populate session state to display stored metrics.
        if (
            existing_log_nutrition
            and existing_log_nutrition["total_calories"] is not None
            and existing_log_nutrition["total_protein_g"] is not None
            and st.session_state.analyzed_nutrition_content is None
        ):
            try:
                db_summary = DaySummary(
                    total_calories=existing_log_nutrition["total_calories"],
                    total_protein_g=existing_log_nutrition["total_protein_g"],
                    items=[],  # Items are not stored in DB, only totals. AI re-analysis populates items.
                )
                st.session_state.analyzed_nutrition_content = db_summary
            except Exception as e:  # pragma: no cover
                print(f"Error creating DaySummary from DB data for display: {e}")
                # analyzed_nutrition_content remains None, so no metrics shown initially

        default_description_nutrition = (
            existing_log_nutrition["meal_description"]
            if existing_log_nutrition
            else ""
        )

        meal_description_nutrition = st.text_area(
            "Log your meals for the day (e.g., Breakfast: Oats with berries; Lunch: Chicken salad; Dinner: Salmon with roasted vegetables):",
            value=default_description_nutrition,
            height=250,
            key="nutrition_meal_description",
        )

        if OPENAI_API_KEY:
            if st.button(
                "Analyze Current Meal Text with AI", key="analyze_nutrition_button"
            ):
                text_to_analyze = st.session_state.nutrition_meal_description
                # extract_meal_data now handles empty/whitespace-only strings
                with st.spinner("Analyzing meals..."):
                    st.session_state.analyzed_nutrition_content = extract_meal_data(
                        text_to_analyze
                    )
        else:
            st.info("OpenAI API Key not configured. AI analysis features disabled.")

        if st.button("Save Meal Log", key="save_nutrition_log"):
            calories_to_save = None
            protein_to_save = None
            current_analysis = st.session_state.get("analyzed_nutrition_content")
            if current_analysis and isinstance(current_analysis, DaySummary):
                if hasattr(current_analysis, "total_calories"):
                    calories_to_save = current_analysis.total_calories
                if hasattr(current_analysis, "total_protein_g"):
                    protein_to_save = current_analysis.total_protein_g

            if save_or_update_nutrition_log(
                current_user_id,
                log_date_str_nutrition,
                meal_description_nutrition,
                total_calories=calories_to_save,
                total_protein_g=protein_to_save,
            ):
                st.success("Meal log saved successfully.")
                st.cache_data.clear()  # Clear cache to refresh logs and current view
                if OPENAI_API_KEY:
                    # Always call extract_meal_data, it handles empty strings
                    with st.spinner("Analyzing saved meals..."):
                        st.session_state.analyzed_nutrition_content = (
                            extract_meal_data(meal_description_nutrition)
                        )
                else:
                    # Clear analysis if API key not present
                    st.session_state.analyzed_nutrition_content = None
                st.rerun()
            else:  # pragma: no cover
                st.error("Failed to save meal log. Database error.")

        analyzed_content = st.session_state.get("analyzed_nutrition_content")
        print(analyzed_content)  # Debugging line to check the content
        if analyzed_content is not None and isinstance(
            analyzed_content, DaySummary
        ):
            st.subheader("AI Extracted Meal Details")
            if hasattr(analyzed_content, "total_calories") and hasattr(
                analyzed_content, "total_protein_g"
            ):
                st.metric(
                    label="Total Estimated Calories",
                    value=f"{analyzed_content.total_calories} kcal",
                )
                st.metric(
                    label="Total Estimated Protein",
                    value=f"{analyzed_content.total_protein_g} g",
                )

            # Display the full JSON (model dump) for transparency or if totals are missing
            st.json(
                analyzed_content.model_dump()
            )  # Use model_dump() for Pydantic object

            if not analyzed_content.items:  # Access items attribute directly
                st.caption(
                    "No specific food items were extracted, or no details found in the text."
                )
        elif (
            analyzed_content is not None
        ):  # It's not None, but not DaySummary (e.g. old format dict)
            st.subheader("AI Extracted Meal Details")  # pragma: no cover
            st.json(analyzed_content)  # Display as is
            st.caption(
                "Displayed data may be in an older format or could not be fully processed."
            )

        st.divider()
        st.subheader("Meal Log History")
        df_nutrition_logs = load_table("nutrition_log", current_user_id) # Includes 'id'
        if not df_nutrition_logs.empty:
            # Sort by date before displaying
            df_nutrition_logs_sorted = df_nutrition_logs.sort_values(by="date", ascending=False)

            # Prepare columns for display
            cols_to_display = ["date", "meal_description", "total_calories", "total_protein_g", "updated_at", "Action"]
            header_cols = st.columns(len(cols_to_display))
            for col, header in zip(header_cols, cols_to_display):
                col.markdown(f"**{header}**")

            for index, row in df_nutrition_logs_sorted.iterrows():
                col1, col2, col3, col4, col5, col6 = st.columns(len(cols_to_display))
                col1.text(pd.to_datetime(row["date"]).strftime("%Y-%m-%d"))
                col2.text(row["meal_description"])
                col3.text(str(row["total_calories"]) if pd.notna(row["total_calories"]) else "N/A")
                col4.text(str(row["total_protein_g"]) if pd.notna(row["total_protein_g"]) else "N/A")
                col5.text(pd.to_datetime(row["updated_at"]).strftime("%Y-%m-%d %H:%M"))

                button_key_nutrition = f"delete_nutrition_{row['id']}" if 'id' in row and pd.notna(row['id']) else f"delete_nutrition_invalid_id_{index}"
                if col6.button("Delete", key=button_key_nutrition):
                    if 'id' in row and pd.notna(row['id']):
                        if delete_nutrition_log_from_db(int(row['id']), current_user_id):
                            st.success(f"Nutrition log for {pd.to_datetime(row['date']).strftime('%Y-%m-%d')} deleted.")
                            st.cache_data.clear()
                            st.rerun()
                        else: # pragma: no cover
                            st.error("Failed to delete nutrition log.")
                    else: # pragma: no cover
                        st.error("Cannot delete: Log entry ID is missing or invalid.")
                st.markdown("---") 
        else:
            st.write("No meal logs recorded yet.")

def render_profile_tab():
    st.header("👤 User Profile & Metrics")
    current_user_id = st.session_state.user_id

    # Load latest metrics for default values in the form
    latest_metrics_df = load_table("user_metrics", current_user_id)
    latest_entry = {}
    if not latest_metrics_df.empty:
        # load_table sorts by date DESC, so iloc[0] is the latest
        latest_entry = latest_metrics_df.iloc[0].to_dict()

    with st.form("user_metrics_form"):
        st.markdown("#### Record New Metrics")
        metric_date = st.date_input(
            "Record Date", date.today(), key="profile_metric_date"
        )

        col1, col2 = st.columns(2)
        with col1:
            height = st.number_input(
                "Height (cm)",
                min_value=50.0,
                max_value=250.0,
                value=latest_entry.get("height_cm"),  # Uses min_value if None
                step=0.1,
                format="%.1f",
                key="profile_height",
                help="Enter your current height.",
            )
            weight = st.number_input(
                "Weight (kg)",
                min_value=20.0,
                max_value=300.0,
                value=latest_entry.get("weight_kg"),  # Uses min_value if None
                step=0.1,
                format="%.1f",
                key="profile_weight",
                help="Enter your current weight.",
            )
            age = st.number_input(
                "Age (years)",
                min_value=1,
                max_value=120,
                value=latest_entry.get("age"),  # Uses min_value if None
                step=1,
                key="profile_age",
                help="Enter your current age.",
            )
        with col2:
            sex_options = ["Not specified", "Male", "Female", "Other"]
            current_sex = latest_entry.get("sex", "Not specified")
            sex_index = (
                sex_options.index(current_sex) if current_sex in sex_options else 0
            )
            sex = st.selectbox(
                "Sex",
                options=sex_options,
                index=sex_index,
                key="profile_sex",
                help="Select your sex.",
            )
            body_fat = st.number_input(
                "Body Fat (%)",
                min_value=1.0,
                max_value=70.0,
                value=latest_entry.get(
                    "body_fat_percentage"
                ),  # Uses min_value if None
                step=0.1,
                format="%.1f",
                key="profile_body_fat",
                help="Enter your body fat percentage.",
            )

        submitted = st.form_submit_button("Save Metrics")

        if submitted:
            sex_to_save = sex if sex != "Not specified" else None
            data_payload = (
                current_user_id,
                metric_date,
                height,  # Direct value from number_input
                weight,  # Direct value from number_input
                sex_to_save,
                age,  # Direct value from number_input
                body_fat,  # Direct value from number_input
            )
            _save_form_data(
                insert_query="INSERT INTO user_metrics (user_id, date, height_cm, weight_kg, sex, age, body_fat_percentage) VALUES (?, ?, ?, ?, ?, ?, ?)",
                data_payload=data_payload,
                success_message="Saved User Metrics",
            )
            # After saving, data will be reloaded by Streamlit's flow or cache clearing

    st.divider()
    st.subheader("Latest Recorded Metrics")
    # Re-fetch to display the absolute latest, including any just saved
    current_metrics_to_display_df = load_table("user_metrics", current_user_id)
    if not current_metrics_to_display_df.empty:
        display_latest = current_metrics_to_display_df.iloc[
            0
        ]  # Already sorted by date DESC
        st.write(
            f"**Date:** {pd.to_datetime(display_latest['date']).strftime('%Y-%m-%d')}"
        )
        if pd.notna(display_latest["height_cm"]):
            st.write(f"**Height:** {display_latest['height_cm']:.1f} cm")
        if pd.notna(display_latest["weight_kg"]):
            st.write(f"**Weight:** {display_latest['weight_kg']:.1f} kg")
        if pd.notna(display_latest["age"]):
            st.write(
                f"**Age:** {display_latest['age']}"
            )  # Assuming age is stored as int
        if pd.notna(display_latest["sex"]):
            st.write(f"**Sex:** {display_latest['sex']}")
        if pd.notna(display_latest["body_fat_percentage"]):
            st.write(f"**Body Fat:** {display_latest['body_fat_percentage']:.1f}%")
    else:
        st.write("No metrics recorded yet.")

    st.divider()
    st.subheader("Metrics History")
    all_metrics_df = load_table("user_metrics", current_user_id)
    if not all_metrics_df.empty:
        display_df = all_metrics_df.copy()
        display_df["date"] = pd.to_datetime(display_df["date"]).dt.strftime(
            "%Y-%m-%d"
        )
        cols_to_display = [
            "date",
            "height_cm",
            "weight_kg",
            "age",
            "sex",
            "body_fat_percentage",
        ]
        existing_cols_to_display = [
            col for col in cols_to_display if col in display_df.columns
        ]
        st.dataframe(
            display_df[existing_cols_to_display].sort_values(
                by="date", ascending=False
            ),
            use_container_width=True,
        )

        st.subheader("Progress Charts")
        # Chart for Weight
        if (
            "weight_kg" in all_metrics_df.columns
            and all_metrics_df["weight_kg"].notna().any()
        ):
            weight_chart_data = all_metrics_df[["date", "weight_kg"]].copy()
            weight_chart_data["date"] = pd.to_datetime(weight_chart_data["date"])
            weight_chart_data = weight_chart_data.dropna(subset=["weight_kg"])
            weight_chart_data = weight_chart_data.sort_values(by="date").set_index(
                "date"
            )
            if not weight_chart_data.empty:
                st.markdown("**Weight (kg) Over Time**")
                st.line_chart(
                    weight_chart_data["weight_kg"],
                    use_container_width=True,
                    height=200,
                )

        # Chart for Body Fat
        if (
            "body_fat_percentage" in all_metrics_df.columns
            and all_metrics_df["body_fat_percentage"].notna().any()
        ):
            bf_chart_data = all_metrics_df[["date", "body_fat_percentage"]].copy()
            bf_chart_data["date"] = pd.to_datetime(bf_chart_data["date"])
            bf_chart_data = bf_chart_data.dropna(subset=["body_fat_percentage"])
            bf_chart_data = bf_chart_data.sort_values(by="date").set_index("date")
            if not bf_chart_data.empty:
                st.markdown("**Body Fat (%) Over Time**")
                st.line_chart(
                    bf_chart_data["body_fat_percentage"],
                    use_container_width=True,
                    height=200,
                )
    else:
        st.write("No metrics data yet to display history or charts.")

    st.divider()
    st.subheader("Change Password")
    with st.form("change_password_form"):
        current_password = st.text_input(
            "Current Password", type="password", key="profile_current_password"
        )
        new_password = st.text_input(
            "New Password (min 4 chars)",
            type="password",
            key="profile_new_password",
        )
        confirm_new_password = st.text_input(
            "Confirm New Password",
            type="password",
            key="profile_confirm_new_password",
        )
        change_password_submitted = st.form_submit_button("Change Password")

        if change_password_submitted:
            user = get_user_from_db(
                st.session_state.username
            )  # Fetch current user details
            if user and verify_password(user["password_hash"], current_password):
                if new_password == confirm_new_password:
                    if len(new_password) >= 4:
                        if update_user_password(
                            st.session_state.user_id, new_password
                        ):
                            st.success("Password updated successfully.")
                        else:  # pragma: no cover
                            st.error("Failed to update password. Database error.")
                    else:
                        st.error("New password must be at least 4 characters long.")
                else:
                    st.error("New passwords do not match.")
            else:
                st.error("Incorrect current password.")

    st.divider()
    st.subheader("Log 1 Rep Max (1RM)")
    # Define key exercises for 1RM logging
    # These could also be dynamically sourced or expanded
    one_rm_exercises = ["Back-squat", "Bench Press", "Deadlift", "Overhead Press"]

    with st.form("log_1rm_form"):
        rm_exercise = st.selectbox(
            "Exercise for 1RM", options=one_rm_exercises, key="profile_1rm_exercise"
        )
        rm_weight = st.number_input(
            "1RM Weight (kg)",
            min_value=0.0,
            step=0.5,
            format="%.1f",
            key="profile_1rm_weight",
        )
        rm_date = st.date_input(
            "Date Achieved/Recorded", date.today(), key="profile_1rm_date"
        )
        log_1rm_submitted = st.form_submit_button("Save 1RM")

        if log_1rm_submitted:
            if rm_exercise and rm_weight > 0:
                if save_or_update_1rm(
                    current_user_id, rm_exercise, rm_weight, rm_date.isoformat()
                ):
                    st.success(f"1RM for {rm_exercise} saved successfully.")
                    st.cache_data.clear()  # Clear cache to reflect new 1RM data if displayed elsewhere
                else:  # pragma: no cover
                    st.error("Failed to save 1RM. Database error.")
            else:
                st.error("Please select an exercise and enter a valid 1RM weight.")

    st.divider()
    st.subheader("Latest Logged 1RMs (Summary per Exercise)")
    latest_1rms_data_display = []
    for ex_name in one_rm_exercises:
        latest_rm_record = get_latest_1rm(current_user_id, ex_name) # Assumes this returns id, one_rep_max, date
        if latest_rm_record and 'id' in latest_rm_record: # Check if 'id' is present
            latest_1rms_data_display.append({
                "id": latest_rm_record["id"], 
                "Exercise": ex_name,
                "1RM (kg)": latest_rm_record["one_rep_max"],
                "Date": pd.to_datetime(latest_rm_record["date"]).strftime("%Y-%m-%d"),
            })
        elif latest_rm_record: # pragma: no cover # Fallback if id is somehow missing but record exists
            st.warning(f"1RM record for {ex_name} is missing an ID, delete unavailable for this summary entry.")
            latest_1rms_data_display.append({
                "id": None, # Explicitly set id to None
                "Exercise": ex_name,
                "1RM (kg)": latest_rm_record["one_rep_max"],
                "Date": pd.to_datetime(latest_rm_record["date"]).strftime("%Y-%m-%d"),
            })


    if latest_1rms_data_display:
        headers = ["Exercise", "1RM (kg)", "Date", "Action"]
        header_cols = st.columns(len(headers))
        for col, header_name in zip(header_cols, headers):
            col.markdown(f"**{header_name}**")

        for record in latest_1rms_data_display:
            col1, col2, col3, col4 = st.columns(len(headers))
            col1.text(record["Exercise"])
            col2.text(f"{record['1RM (kg)']:.1f}" if pd.notna(record['1RM (kg)']) else "N/A")
            col3.text(record["Date"])
            
            button_key_latest_1rm = f"delete_latest_1rm_{record['id']}" if record['id'] is not None else f"delete_latest_1rm_invalid_id_{record['Exercise']}"
            if record['id'] is not None: # Only show delete button if ID is valid
                if col4.button("Delete", key=button_key_latest_1rm):
                    if delete_1rm_from_db(int(record['id']), current_user_id):
                        st.success(f"1RM record for {record['Exercise']} on {record['Date']} deleted.")
                        st.cache_data.clear()
                        st.rerun()
                    else: # pragma: no cover
                        st.error("Failed to delete 1RM record from summary.")
            else:
                col4.text("N/A") # No action if no ID
            st.markdown("---")
    else:
        st.write("No 1RMs logged yet for the summary display.")

    st.divider()
    st.subheader("All Logged 1RMs")
    all_1rms_df = load_table("user_1rm", current_user_id) # Includes 'id'
    if not all_1rms_df.empty:
        all_1rms_df_sorted = all_1rms_df.sort_values(by=["exercise", "date"], ascending=[True, False])
        
        all_headers = ["Exercise", "1RM (kg)", "Date", "Action"]
        all_header_cols = st.columns(len(all_headers))
        for col, header_name in zip(all_header_cols, all_headers):
            col.markdown(f"**{header_name}**")

        for index, row in all_1rms_df_sorted.iterrows():
            col1, col2, col3, col4 = st.columns(len(all_headers))
            col1.text(row["exercise"])
            col2.text(f"{row['one_rep_max']:.1f}" if pd.notna(row['one_rep_max']) else "N/A")
            col3.text(pd.to_datetime(row["date"]).strftime("%Y-%m-%d"))
            
            button_key_all_1rm = f"delete_all_1rm_{row['id']}" if 'id' in row and pd.notna(row['id']) else f"delete_all_1rm_invalid_id_{index}"
            if 'id' in row and pd.notna(row['id']):
                if col4.button("Delete", key=button_key_all_1rm):
                    if delete_1rm_from_db(int(row['id']), current_user_id):
                        st.success(f"1RM record for {row['exercise']} on {pd.to_datetime(row['date']).strftime('%Y-%m-%d')} deleted.")
                        st.cache_data.clear()
                        st.rerun()
                    else: # pragma: no cover
                        st.error("Failed to delete 1RM record from all logs.")
            else: # pragma: no cover
                col4.text("N/A") # No action if no ID
            st.markdown("---")
    else:
        st.write("No 1RMs recorded in total yet.")

def render_logs_tab():
    st.header("📊 Logs")
    current_user_id = st.session_state.user_id
    if current_user_id is None:  # pragma: no cover
        st.warning("Please log in to see your logs.")
    else:
        st.subheader("Resistance")
        df_resistance_logs = load_table("resistance", current_user_id) # Includes 'id' by default from load_table

        # --- Start of Diagnostic Info ---
        st.write("--- Resistance Log Diagnostics ---")
        if current_user_id is None: # pragma: no cover
            st.write("Current User ID is None. Cannot load logs.")
        else:
            st.write(f"Current User ID: {current_user_id}")
        
        if df_resistance_logs is None: # pragma: no cover
            st.write("df_resistance_logs is None (load_table might have failed unexpectedly).")
        else:
            st.write(f"Shape of df_resistance_logs: {df_resistance_logs.shape}")
            st.write(f"Columns in df_resistance_logs: {df_resistance_logs.columns.tolist()}")
            if 'id' not in df_resistance_logs.columns and not df_resistance_logs.empty: # pragma: no cover
                st.error("Critical: 'id' column is missing from df_resistance_logs!")
        # --- End of Diagnostic Info ---

        if not df_resistance_logs.empty:
            st.write(f"Found {len(df_resistance_logs)} resistance log(s) to display.") # Diagnostic
            # Define columns to display for resistance logs, adding "Action"
            resistance_cols_to_display = [
                "date", "week", "day", "exercise", "set_number", 
                "target", "actual_weight", "actual_reps", "rir", "Action"
            ]
            # Display headers
            header_cols_resistance = st.columns(len(resistance_cols_to_display))
            for col, header in zip(header_cols_resistance, resistance_cols_to_display):
                col.markdown(f"**{header}**")

            # Iterate and display each resistance log entry with a delete button
            # Sort by date descending before display
            df_resistance_logs_sorted = df_resistance_logs.sort_values(by="date", ascending=False)
            for index, row in df_resistance_logs_sorted.iterrows():
                st.write(f"Processing resistance row with ID: {row.get('id', 'ID_NOT_FOUND')}") # Diagnostic for ID
                data_cols = st.columns(len(resistance_cols_to_display))
                
                data_cols[0].text(pd.to_datetime(row["date"]).strftime("%Y-%m-%d"))
                data_cols[1].text(str(row["week"]) if pd.notna(row["week"]) else "N/A")
                data_cols[2].text(str(row["day"]) if pd.notna(row["day"]) else "N/A")
                data_cols[3].text(str(row["exercise"]) if pd.notna(row["exercise"]) else "N/A")
                data_cols[4].text(str(row["set_number"]) if pd.notna(row["set_number"]) else "N/A")
                data_cols[5].text(str(row["target"]) if pd.notna(row["target"]) else "N/A")
                data_cols[6].text(f"{row['actual_weight']:.1f}" if pd.notna(row['actual_weight']) else "N/A")
                data_cols[7].text(str(int(row["actual_reps"])) if pd.notna(row["actual_reps"]) else "N/A")
                data_cols[8].text(str(int(row["rir"])) if pd.notna(row["rir"]) else "N/A")
                
                button_key = f"delete_resistance_{row['id']}" if 'id' in row and pd.notna(row['id']) else f"delete_resistance_invalid_id_{index}"

                if data_cols[9].button("Delete", key=button_key):
                    if 'id' in row and pd.notna(row['id']):
                        if delete_resistance_set_from_db(int(row['id']), current_user_id):
                            st.success(f"Resistance set {row['id']} deleted.")
                            st.cache_data.clear()
                            st.rerun()
                        else: # pragma: no cover
                            st.error("Failed to delete resistance set.")
                    else: # pragma: no cover
                        st.error("Cannot delete: Log entry ID is missing or invalid.")
                st.markdown("---") 
        else:
            st.write("No resistance logs recorded yet for this user.")

        st.subheader("Mobility")
        st.dataframe(load_table("mobility", current_user_id)) # No delete for these yet
        st.subheader("Cardio")
        st.dataframe(load_table("cardio", current_user_id)) # No delete for these yet

        st.subheader("Progress Charts (Resistance)")
        # df_resistance is already loaded as df_resistance_logs
        if not df_resistance_logs.empty:
            # Use df_resistance_logs for charts
            unique_exercises = df_resistance_logs["exercise"].unique()

            for lift in unique_exercises:
                with st.expander(f"Charts for {lift}"):
                    # Filter data for the current exercise
                    exercise_df = df_resistance_logs[
                        df_resistance_logs["exercise"] == lift
                    ].copy()
            unique_exercises = df_resistance["exercise"].unique()

            for lift in unique_exercises:
                with st.expander(f"Charts for {lift}"):
                    # Filter data for the current exercise
                    exercise_df = df_resistance[
                        df_resistance["exercise"] == lift
                    ].copy()
                    exercise_df["date"] = pd.to_datetime(exercise_df["date"])

                    # Max Weight Over Time chart
                    chart_data_max_weight = (
                        exercise_df.sort_values(by="date")
                        .groupby(pd.Grouper(key="date", freq="D"))["actual_weight"]
                        .max()
                        .fillna(0)
                    )
                    if not chart_data_max_weight.empty:
                        st.markdown(f"**Max Weight Over Time**")
                        st.line_chart(
                            chart_data_max_weight,
                            use_container_width=True,
                            height=200,
                        )
                    else:  # pragma: no cover
                        st.write("No max weight data to display for this exercise.")

                    # Total Volume (Weight * Reps) Over Time chart
                    exercise_df["volume"] = (
                        exercise_df["actual_weight"] * exercise_df["actual_reps"]
                    )
                    chart_data_volume = (
                        exercise_df.sort_values(by="date")
                        .groupby(pd.Grouper(key="date", freq="D"))["volume"]
                        .sum()
                        .fillna(0)
                    )
                    if not chart_data_volume.empty:
                        st.markdown(f"**Total Volume (kg*reps) Over Time**")
                        st.line_chart(
                            chart_data_volume, use_container_width=True, height=200
                        )
                    else:  # pragma: no cover
                        st.write("No volume data to display for this exercise.")

                    # If the current exercise is "Weighted Pull-up", add the total reps chart
                    pullup_exercise_name = "Weighted Pull-up"
                    if lift == pullup_exercise_name:
                        st.markdown("---")  # Visual separator within the expander
                        st.markdown(f"**Total Reps Over Time**")
                        # Data for pull-up reps (already filtered as exercise_df)
                        chart_data_pullup_reps = (
                            exercise_df.sort_values(by="date")
                            .groupby(pd.Grouper(key="date", freq="D"))[
                                "actual_reps"
                            ]
                            .sum()
                            .fillna(0)
                        )
                        if not chart_data_pullup_reps.empty:
                            st.line_chart(
                                chart_data_pullup_reps,
                                use_container_width=True,
                                height=200,
                            )
                        else:  # pragma: no cover
                            st.write(
                                f"No reps data to display for {pullup_exercise_name}."
                            )
        else:
            st.write("No resistance data yet to display charts.")
