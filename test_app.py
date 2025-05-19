import os  # For managing temporary test database file
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Before importing app, we need to ensure Streamlit's st object is minimally mocked
# if we want to avoid errors for st.set_page_config, etc., during import.
# However, for testing specific functions, we often mock 'st' more targetedly.
# For now, let's assume app.py can be imported, and we'll mock 'st' within tests.
import app  # Main app structure, init_db might be called from here.
import database  # For direct calls to database functions
import ui_tabs  # For calls to UI helper functions previously in app.py

TEST_DB_FILE = "test_workout_tracker.db"


@pytest.fixture
def test_db(monkeypatch):
    """Fixture to set up and tear down a temporary database for tests."""
    original_db_name = database.DB_NAME  # Get original from database module
    monkeypatch.setattr(
        database, "DB_NAME", TEST_DB_FILE
    )  # Patch DB_NAME in database module

    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)
    # database.init_db will now use the patched database.DB_NAME
    database.init_db()  # Initialize schema in the test DB file

    yield  # Test runs here

    # Teardown: remove test DB and restore original DB name
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)
    monkeypatch.setattr(
        database, "DB_NAME", original_db_name
    )  # Restore DB_NAME in database module


@pytest.fixture
def active_user(test_db):
    """Fixture to create a test user in the test_db."""
    # test_db fixture ensures DB is set up
    user_id = database.create_user_in_db("test_active_user", "password123")
    assert user_id is not None, "Setup failed: Could not create active_user"
    return user_id


@pytest.fixture
def mock_st_environment(monkeypatch, active_user):
    """Fixture to mock Streamlit's 'st' object and session state."""
    # active_user fixture ensures a user exists and db is set up
    mock_st_obj = MagicMock()
    # Simulate logged-in user for most tests using this fixture
    # Make session_state a MagicMock itself to allow attribute access and .get()
    mock_session_state = MagicMock()
    mock_session_state.user_id = active_user
    mock_session_state.username = "test_active_user"
    mock_session_state.logged_in = True  # Default to logged in for this fixture

    # Define a side_effect for .get() to mimic Streamlit's SessionState behavior
    def session_get_side_effect(key, default=None):
        if key == "user_id":
            return mock_session_state.user_id
        if key == "username":
            return mock_session_state.username
        if key == "logged_in":
            return mock_session_state.logged_in
        # Fallback for other keys if needed, though not strictly necessary if only these are used
        return getattr(mock_session_state, key, default)

    mock_session_state.get = MagicMock(side_effect=session_get_side_effect)
    mock_st_obj.session_state = mock_session_state

    mock_st_obj.cache_data.clear = MagicMock()
    mock_st_obj.rerun = MagicMock()
    mock_st_obj.sidebar = MagicMock()
    mock_st_obj.sidebar.title = MagicMock()
    mock_st_obj.sidebar.radio = MagicMock()
    mock_st_obj.sidebar.form = MagicMock()
    mock_st_obj.sidebar.error = MagicMock()
    mock_st_obj.sidebar.success = MagicMock()
    mock_st_obj.info = MagicMock()
    mock_st_obj.tabs = MagicMock()
    mock_st_obj.header = MagicMock()
    mock_st_obj.expander = MagicMock()
    mock_st_obj.markdown = MagicMock()
    mock_st_obj.table = MagicMock()
    mock_st_obj.columns = MagicMock(return_value=(MagicMock(), MagicMock()))
    mock_st_obj.date_input = MagicMock()
    mock_st_obj.selectbox = MagicMock()
    mock_st_obj.checkbox = MagicMock()
    mock_st_obj.number_input = MagicMock()
    mock_st_obj.slider = MagicMock()
    mock_st_obj.button = MagicMock()
    mock_st_obj.warning = MagicMock()
    mock_st_obj.success = MagicMock()
    mock_st_obj.error = MagicMock()
    mock_st_obj.dataframe = MagicMock()
    mock_st_obj.line_chart = MagicMock()
    mock_st_obj.metric = MagicMock()  # For nutrition tab
    mock_st_obj.json = MagicMock()  # For nutrition tab
    mock_st_obj.caption = MagicMock()  # For nutrition tab
    mock_st_obj.text_area = MagicMock()  # For nutrition tab
    mock_st_obj.spinner = MagicMock()  # For nutrition tab
    mock_st_obj.form = MagicMock()  # For profile tab
    mock_st_obj.form_submit_button = MagicMock()  # For profile tab
    mock_st_obj.text_input = MagicMock()  # For profile tab (change password)
    mock_st_obj.divider = MagicMock()  # For profile tab & nutrition tab
    mock_st_obj.subheader = MagicMock()  # For profile tab & nutrition tab

    # Patch 'st' in the ui_tabs module, as that's where it's imported and used by render functions
    patcher_ui_tabs = patch("ui_tabs.st", mock_st_obj)
    patcher_ui_tabs.start()

    # If app.py itself uses st directly (outside of ui_tabs functions), patch it too.
    # For show_login_signup_forms and main app structure.
    patcher_app = patch("app.st", mock_st_obj)
    patcher_app.start()

    yield mock_st_obj

    patcher_ui_tabs.stop()
    patcher_app.stop()


# --- Auth Function Tests ---


def test_hash_password():
    password = "testpassword"
    hashed = database.hash_password(password)
    assert isinstance(hashed, str)
    assert password != hashed


def test_verify_password():
    password = "testpassword"
    hashed = database.hash_password(password)
    assert database.verify_password(hashed, password) is True
    assert database.verify_password(hashed, "wrongpassword") is False


def test_create_user_in_db(test_db):  # Uses test_db fixture
    # Test successful user creation
    user_id = database.create_user_in_db("testuser_auth", "password123")
    assert user_id is not None
    assert isinstance(user_id, int)

    # Test duplicate username
    duplicate_user_id = database.create_user_in_db("testuser_auth", "anotherpassword")
    assert duplicate_user_id is None


def test_get_user_from_db(test_db):  # Uses test_db fixture
    database.create_user_in_db("testuser_get", "password123")

    user = database.get_user_from_db("testuser_get")  # Ensure username matches creation
    assert user is not None
    assert user["username"] == "testuser_get"

    non_existent_user = database.get_user_from_db("nonexistentuser")
    assert non_existent_user is None


def test_update_user_password(test_db):  # Uses test_db fixture
    # Create a user first
    username = "test_update_pass_user"
    original_password = "oldPassword123"
    user_id = database.create_user_in_db(username, original_password)
    assert user_id is not None

    # Update the password
    new_password = "newPassword456"
    update_success = database.update_user_password(
        user_id, new_password
    )  # Call directly from database module
    assert update_success is True

    # Verify the new password works and old one doesn't
    user_after_update = database.get_user_from_db(username)
    assert user_after_update is not None
    assert (
        database.verify_password(user_after_update["password_hash"], new_password)
        is True
    )
    assert (
        database.verify_password(user_after_update["password_hash"], original_password)
        is False
    )

    # Test updating password for a non-existent user_id (should not error, but return False or handle gracefully)
    # The current database.update_user_password doesn't explicitly return False for non-existent user,
    # but the update won't affect any rows. A more robust check might involve checking c.rowcount.
    # For now, we ensure it doesn't crash.
    non_existent_user_id = 99999
    update_fail = database.update_user_password(
        non_existent_user_id, "somePassword"
    )  # Call directly from database module
    assert (
        update_fail is True
    )  # The function returns True if execute/commit don't raise an error.
    # No rows affected is not an error. This is acceptable.


def test_save_or_update_1rm(
    active_user,
):  # Uses active_user fixture (which implies test_db)
    user_id = active_user
    exercise = "Back-squat"
    today_iso = date.today().isoformat()
    tomorrow_iso = (date.today() + pd.Timedelta(days=1)).isoformat()

    # 1. Save a new 1RM
    success_save = database.save_or_update_1rm(user_id, exercise, 100.0, today_iso)
    assert success_save is True
    conn = database.get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT one_rep_max, date FROM user_1rm WHERE user_id = ? AND exercise = ? AND date = ?",
        (user_id, exercise, today_iso),
    )
    result = c.fetchone()
    assert result is not None
    assert result["one_rep_max"] == 100.0
    conn.close()

    # 2. Update an existing 1RM for the same date
    success_update = database.save_or_update_1rm(user_id, exercise, 105.0, today_iso)
    assert success_update is True
    conn = database.get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT one_rep_max FROM user_1rm WHERE user_id = ? AND exercise = ? AND date = ?",
        (user_id, exercise, today_iso),
    )
    result = c.fetchone()
    assert result["one_rep_max"] == 105.0
    # Ensure only one record for that date
    c.execute(
        "SELECT COUNT(*) FROM user_1rm WHERE user_id = ? AND exercise = ? AND date = ?",
        (user_id, exercise, today_iso),
    )
    count = c.fetchone()[0]
    assert count == 1
    conn.close()

    # 3. Save a new 1RM for a different date (should be a new record)
    success_save_new_date = database.save_or_update_1rm(
        user_id, exercise, 110.0, tomorrow_iso
    )
    assert success_save_new_date is True
    conn = database.get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT COUNT(*) FROM user_1rm WHERE user_id = ? AND exercise = ?",
        (user_id, exercise),
    )
    count = c.fetchone()[0]
    assert count == 2  # One for today, one for tomorrow
    conn.close()


def test_get_latest_1rm(active_user):  # Uses active_user fixture
    user_id = active_user
    exercise = "Bench Press"
    today_iso = date.today().isoformat()
    yesterday_iso = (date.today() - pd.Timedelta(days=1)).isoformat()
    day_before_yesterday_iso = (date.today() - pd.Timedelta(days=2)).isoformat()

    # 1. No 1RM logged yet
    latest = database.get_latest_1rm(user_id, exercise)
    assert latest is None

    # 2. Log some 1RMs
    database.save_or_update_1rm(user_id, exercise, 80.0, yesterday_iso)
    database.save_or_update_1rm(user_id, exercise, 75.0, day_before_yesterday_iso)
    database.save_or_update_1rm(user_id, exercise, 82.5, today_iso)  # Most recent

    latest = database.get_latest_1rm(user_id, exercise)
    assert latest is not None
    assert latest["one_rep_max"] == 82.5
    assert latest["date"] == today_iso

    # 3. Check for an exercise with no 1RMs
    latest_other_ex = database.get_latest_1rm(user_id, "Deadlift")
    assert latest_other_ex is None


# --- Data Function Tests ---


def test_add_column_if_not_exists(test_db):  # Uses test_db fixture
    # This test doesn't involve st.cache_data on the function being tested, so no changes needed here.
    conn = database.get_db_connection()
    c = conn.cursor()

    # Test adding a new column
    database._add_column_if_not_exists(
        c, "users", "email", "TEXT"
    )  # Use database._add_column_if_not_exists
    c.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in c.fetchall()]
    assert "email" in columns

    # Test attempting to add an existing column (should not fail or change schema)
    database._add_column_if_not_exists(
        c, "users", "email", "TEXT"
    )  # Use database._add_column_if_not_exists
    c.execute("PRAGMA table_info(users)")
    columns_after_second_call = [row[1] for row in c.fetchall()]
    assert columns == columns_after_second_call

    conn.close()


def test_load_table(
    active_user, monkeypatch
):  # Uses active_user fixture (which implies test_db)
    # Temporarily replace the cached function with its original, undecorated version
    monkeypatch.setattr(ui_tabs, "load_table", ui_tabs.load_table.__wrapped__)

    test_user_id = active_user
    # Test loading an empty table
    df_empty = ui_tabs.load_table("resistance", test_user_id)
    assert isinstance(df_empty, pd.DataFrame)
    assert df_empty.empty is True

    # Insert some data for the test user
    conn = database.get_db_connection()
    c = conn.cursor()
    today_str = date.today().isoformat()
    c.execute(
        "INSERT INTO resistance (user_id, date, week, day, exercise, set_number, target, actual_weight, actual_reps, rir) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (test_user_id, today_str, 1, "Monday", "Squat", 1, "5x5", 100, 5, 2),
    )
    conn.commit()
    conn.close()

    df_with_data = ui_tabs.load_table("resistance", test_user_id)
    assert df_with_data.empty is False
    assert len(df_with_data) == 1
    assert df_with_data.iloc[0]["exercise"] == "Squat"

    # Test loading for another user (who has no data)
    conn_temp = database.get_db_connection()  # Need a connection to create another user
    c_temp = conn_temp.cursor()
    # Manually create another user for this specific test case, as active_user is fixed
    other_user_id = database.create_user_in_db("otherdatauser", "pass")
    assert other_user_id is not None
    conn_temp.close()

    df_other_user = ui_tabs.load_table("resistance", other_user_id)
    assert df_other_user.empty is True

    # Test loading with None user_id
    df_none_user = ui_tabs.load_table("resistance", None)
    assert df_none_user.empty is True


def test_fetch_last(active_user, monkeypatch):  # Uses active_user fixture
    # Temporarily replace the cached function with its original, undecorated version
    monkeypatch.setattr(ui_tabs, "fetch_last", ui_tabs.fetch_last.__wrapped__)

    test_user_id = active_user
    # Test fetching when no data exists
    last = ui_tabs.fetch_last("Squat", 1, test_user_id)
    assert last == (None, None, None)

    # Insert data
    conn = database.get_db_connection()
    c = conn.cursor()
    today_str = date.today().isoformat()
    c.execute(
        "INSERT INTO resistance (user_id, date, week, day, exercise, set_number, target, actual_weight, actual_reps, rir) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (test_user_id, today_str, 1, "Monday", "Squat", 1, "5x5", 100.0, 5, 2),
    )
    # Insert an older record to ensure the latest is fetched
    older_date_str = (date.today() - pd.Timedelta(days=1)).isoformat()
    c.execute(
        "INSERT INTO resistance (user_id, date, week, day, exercise, set_number, target, actual_weight, actual_reps, rir) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (test_user_id, older_date_str, 1, "Monday", "Squat", 1, "5x5", 90.0, 5, 3),
    )
    conn.commit()
    conn.close()

    weight, reps, rir = ui_tabs.fetch_last("Squat", 1, test_user_id)
    assert weight == 100.0
    assert reps == 5
    assert rir == 2

    # Test fetching for an exercise that doesn't exist for the user
    last_other_ex = ui_tabs.fetch_last("Bench", 1, test_user_id)
    assert last_other_ex == (None, None, None)

    # Test fetching with None user_id
    last_none_user = ui_tabs.fetch_last("Squat", 1, None)
    assert last_none_user == (None, None, None)


# --- _save_form_data Function Tests ---


def test_save_form_data_single_insert(mock_st_environment, active_user):
    mock_st = mock_st_environment  # Get the mocked st object
    test_user_id = active_user  # Get the user_id from active_user fixture

    today_str = date.today().isoformat()
    query = "INSERT INTO mobility(user_id, date, prep_done, joint_flow_done, animal_circuit_done, cuff_finisher_done) VALUES(?,?,?,?,?,?)"
    payload = (test_user_id, today_str, 1, 1, 0, 0)

    ui_tabs._save_form_data(query, payload, "Saved Mobility")

    mock_st.success.assert_called_with("Saved Mobility")
    mock_st.cache_data.clear.assert_called_once()

    # Verify data in DB
    conn = database.get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM mobility WHERE user_id = ?", (test_user_id,))
    row = c.fetchone()
    assert row is not None
    assert row["prep_done"] == 1
    conn.close()


def test_save_form_data_many_insert(mock_st_environment, active_user):
    mock_st = mock_st_environment
    test_user_id = active_user

    today_str = date.today().isoformat()
    query = "INSERT INTO resistance(user_id,date,week,day,exercise,set_number,target,actual_weight,actual_reps,rir) VALUES(?,?,?,?,?,?,?,?,?,?)"
    payload = [
        (test_user_id, today_str, 1, "Mon", "Squat", 1, "5x5", 100, 5, 2),
        (test_user_id, today_str, 1, "Mon", "Squat", 2, "5x5", 100, 5, 1),
    ]

    ui_tabs._save_form_data(query, payload, "Saved Resistance", is_many=True)

    mock_st.success.assert_called_with("Saved Resistance")
    mock_st.cache_data.clear.assert_called_once()

    conn = database.get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM resistance WHERE user_id = ?", (test_user_id,))
    count = c.fetchone()[0]
    assert count == 2
    conn.close()


def test_save_form_data_no_user_logged_in(mock_st_environment):
    mock_st = mock_st_environment
    # Configure the session_state mock for this specific test case
    mock_st.session_state.user_id = None
    mock_st.session_state.logged_in = False

    ui_tabs._save_form_data("QUERY", (), "Success Message")

    mock_st.error.assert_called_with("User not logged in. Cannot save data.")
    mock_st.success.assert_not_called()
    mock_st.cache_data.clear.assert_not_called()


def test_save_form_data_empty_payload_for_many(mock_st_environment):
    mock_st = mock_st_environment
    # User is logged in via mock_st_environment fixture

    ui_tabs._save_form_data("QUERY", [], "Success Message", is_many=True)

    mock_st.warning.assert_called_with("No data to save.")
    mock_st.success.assert_not_called()
    mock_st.cache_data.clear.assert_not_called()


# --- AI Utils Function Tests ---
# We need to import the ai_utils module to test its functions
# from ai_utils import DaySummary, extract_meal_data
#
#
# @patch("ai_utils.meal_agent.run_sync")
# def test_extract_meal_data_success(mock_run_sync):
#     # Mock the response from the AI agent
#     # Ensure keys match FoodItem model: meal_type, food_name
#     mock_food_items_data = [
#         {
#             "meal_type": "Breakfast",
#             "food_name": "Oats",
#             "quantity_g": 50,
#             "calories": 150,
#             "protein_g": 5,
#         },
#         {
#             "meal_type": "Lunch",
#             "food_name": "Chicken Salad",
#             "quantity_g": 200,
#             "calories": 300,
#             "protein_g": 30,
#         },
#     ]
#     mock_day_summary_data = {
#         "output": {
#             "items": mock_food_items_data,
#             "total_calories": 450,
#             "total_protein_g": 35,
#         }
#     }
#     mock_run_sync.return_value = DaySummary(**mock_day_summary_data)
#
#     free_text = "Breakfast: Oats 50g. Lunch: Chicken Salad 200g."
#     result: DaySummary = extract_meal_data(
#         free_text
#     )  # extract_meal_data returns DaySummary object
#     print(f"DEBUG: \n{result}")
#     assert isinstance(result, DaySummary)
#     assert result.total_calories == mock_day_summary_data["total_calories"]
#     assert result.total_protein_g == mock_day_summary_data["total_protein_g"]
#     assert [item.output for item in result.items] == mock_food_items_data
#     mock_run_sync.assert_called_once_with(free_text)
#
#
# @patch("ai_utils.meal_agent.run_sync")
# def test_extract_meal_data_empty_items(mock_run_sync):
#     # Mock the AI agent returning no items but valid totals
#     mock_day_summary_data = {"items": [], "total_calories": 0, "total_protein_g": 0}
#     mock_run_sync.return_value = DaySummary(**mock_day_summary_data)
#
#     free_text = "Nothing eaten today."
#     result: DaySummary = extract_meal_data(free_text)
#
#     assert isinstance(result, DaySummary)
#     assert result.total_calories == mock_day_summary_data["total_calories"]
#     assert result.total_protein_g == mock_day_summary_data["total_protein_g"]
#     assert len(result.items) == 0
#     mock_run_sync.assert_called_once_with(free_text)
#
#
# def test_extract_meal_data_empty_input_string():
#     # Test with empty or whitespace-only string, should not call agent
#     # and should return the default empty DaySummary structure.
#     result_empty_str: DaySummary = extract_meal_data("")
#     result_space_str: DaySummary = extract_meal_data("   ")
#
#     assert isinstance(result_empty_str, DaySummary)
#     assert result_empty_str.total_calories == 0
#     assert result_empty_str.total_protein_g == 0
#     assert len(result_empty_str.items) == 0
#
#     assert isinstance(result_space_str, DaySummary)
#     assert result_space_str.total_calories == 0
#     assert result_space_str.total_protein_g == 0
#     assert len(result_space_str.items) == 0
#     # meal_agent.run_sync should not have been called, so no need to mock it here.
#
#
# @patch("ai_utils.meal_agent.run_sync")
# def test_extract_meal_data_agent_failure_or_malformed_response(mock_run_sync):
#     # If the agent fails or returns something that doesn't match ParsedMeals,
#     # Pydantic validation within meal_agent.run_sync or during ParsedMeals instantiation
#     # should raise an error. The function extract_meal_data itself doesn't catch these.
#     # This test verifies that if the agent call fails (e.g., raises an exception),
#     # the exception propagates.
#     mock_run_sync.side_effect = Exception("AI agent failed")
#
#     with pytest.raises(Exception, match="AI agent failed"):
#         extract_meal_data("Some complex meal text that might break the agent")
#

# --- Database Function Tests for Nutrition Log ---


def test_save_and_get_nutrition_log_with_totals(
    active_user,
):  # uses test_db via active_user
    user_id = active_user
    entry_date = date.today().isoformat()
    meal_description = "Breakfast: Cereal, Lunch: Sandwich"
    total_calories = 1200
    total_protein_g = 50

    # Save with totals
    save_success = database.save_or_update_nutrition_log(
        user_id, entry_date, meal_description, total_calories, total_protein_g
    )
    assert save_success is True

    # Get and verify
    log_entry = database.get_nutrition_log_by_date(user_id, entry_date)
    assert log_entry is not None
    assert log_entry["meal_description"] == meal_description
    assert log_entry["total_calories"] == total_calories
    assert log_entry["total_protein_g"] == total_protein_g

    # Update with new totals
    updated_meal_description = "Dinner: Pasta"
    updated_calories = 800
    updated_protein = 30
    update_success = database.save_or_update_nutrition_log(
        user_id, entry_date, updated_meal_description, updated_calories, updated_protein
    )
    assert update_success is True

    log_entry_updated = database.get_nutrition_log_by_date(user_id, entry_date)
    assert log_entry_updated is not None
    assert log_entry_updated["meal_description"] == updated_meal_description
    assert log_entry_updated["total_calories"] == updated_calories
    assert log_entry_updated["total_protein_g"] == updated_protein


def test_save_and_get_nutrition_log_without_totals(active_user):  # uses test_db
    user_id = active_user
    entry_date = (date.today() + pd.Timedelta(days=1)).isoformat()  # Different date
    meal_description = "Snacks: Apple and nuts"

    # Save without totals (should store NULLs)
    save_success = database.save_or_update_nutrition_log(
        user_id,
        entry_date,
        meal_description,  # total_calories and total_protein_g default to None
    )
    assert save_success is True

    log_entry = database.get_nutrition_log_by_date(user_id, entry_date)
    assert log_entry is not None
    assert log_entry["meal_description"] == meal_description
    assert log_entry["total_calories"] is None
    assert log_entry["total_protein_g"] is None

    # Update existing entry that had NULLs, now with totals
    updated_calories = 300
    updated_protein = 10
    update_success_with_totals = database.save_or_update_nutrition_log(
        user_id, entry_date, meal_description, updated_calories, updated_protein
    )
    assert update_success_with_totals is True

    log_entry_now_with_totals = database.get_nutrition_log_by_date(user_id, entry_date)
    assert log_entry_now_with_totals is not None
    assert log_entry_now_with_totals["total_calories"] == updated_calories
    assert log_entry_now_with_totals["total_protein_g"] == updated_protein


def test_get_nutrition_log_non_existent(active_user):  # uses test_db
    user_id = active_user
    non_existent_date = "1999-01-01"
    log_entry = database.get_nutrition_log_by_date(user_id, non_existent_date)
    assert log_entry is None
