import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import date
import os  # For managing temporary test database file

# Before importing app, we need to ensure Streamlit's st object is minimally mocked
# if we want to avoid errors for st.set_page_config, etc., during import.
# However, for testing specific functions, we often mock 'st' more targetedly.
# For now, let's assume app.py can be imported, and we'll mock 'st' within tests.

import app  # This will run app.init_db() with the production DB_NAME once.
import database # Import the database module


TEST_DB_FILE = "test_workout_tracker.db"


@pytest.fixture
def test_db(monkeypatch):
    """Fixture to set up and tear down a temporary database for tests."""
    original_db_name = database.DB_NAME # Get original from database module
    monkeypatch.setattr(database, "DB_NAME", TEST_DB_FILE) # Patch DB_NAME in database module

    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)
    # app.init_db is database.init_db, which will now use the patched database.DB_NAME
    app.init_db()  # Initialize schema in the test DB file

    yield  # Test runs here

    # Teardown: remove test DB and restore original DB name
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)
    monkeypatch.setattr(database, "DB_NAME", original_db_name) # Restore DB_NAME in database module


@pytest.fixture
def active_user(test_db):
    """Fixture to create a test user in the test_db."""
    # test_db fixture ensures DB is set up
    user_id = app.create_user_in_db("test_active_user", "password123")
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

    patcher = patch("app.st", mock_st_obj)
    patcher.start()

    yield mock_st_obj

    patcher.stop()


# --- Auth Function Tests ---


def test_hash_password():
    password = "testpassword"
    hashed = app.hash_password(password)
    assert isinstance(hashed, str)
    assert password != hashed


def test_verify_password():
    password = "testpassword"
    hashed = app.hash_password(password)
    assert app.verify_password(hashed, password) is True
    assert app.verify_password(hashed, "wrongpassword") is False


def test_create_user_in_db(test_db):  # Uses test_db fixture
    # Test successful user creation
    user_id = app.create_user_in_db("testuser_auth", "password123")
    assert user_id is not None
    assert isinstance(user_id, int)

    # Test duplicate username
    duplicate_user_id = app.create_user_in_db("testuser_auth", "anotherpassword")
    assert duplicate_user_id is None


def test_get_user_from_db(test_db):  # Uses test_db fixture
    app.create_user_in_db("testuser_get", "password123")

    user = app.get_user_from_db("testuser_get")  # Ensure username matches creation
    assert user is not None
    assert user["username"] == "testuser_get"

    non_existent_user = app.get_user_from_db("nonexistentuser")
    assert non_existent_user is None


def test_update_user_password(test_db): # Uses test_db fixture
    # Create a user first
    username = "test_update_pass_user"
    original_password = "oldPassword123"
    user_id = app.create_user_in_db(username, original_password)
    assert user_id is not None

    # Update the password
    new_password = "newPassword456"
    update_success = database.update_user_password(user_id, new_password) # Call directly from database module
    assert update_success is True

    # Verify the new password works and old one doesn't
    user_after_update = app.get_user_from_db(username)
    assert user_after_update is not None
    assert app.verify_password(user_after_update["password_hash"], new_password) is True
    assert app.verify_password(user_after_update["password_hash"], original_password) is False

    # Test updating password for a non-existent user_id (should not error, but return False or handle gracefully)
    # The current database.update_user_password doesn't explicitly return False for non-existent user,
    # but the update won't affect any rows. A more robust check might involve checking c.rowcount.
    # For now, we ensure it doesn't crash.
    non_existent_user_id = 99999
    update_fail = database.update_user_password(non_existent_user_id, "somePassword") # Call directly from database module
    assert update_fail is True # The function returns True if execute/commit don't raise an error.
                               # No rows affected is not an error. This is acceptable.


# --- Data Function Tests ---


def test_add_column_if_not_exists(test_db):  # Uses test_db fixture
    # This test doesn't involve st.cache_data on the function being tested, so no changes needed here.
    conn = app.get_db_connection()
    c = conn.cursor()

    # Test adding a new column
    database._add_column_if_not_exists(c, "users", "email", "TEXT") # Use database._add_column_if_not_exists
    c.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in c.fetchall()]
    assert "email" in columns

    # Test attempting to add an existing column (should not fail or change schema)
    database._add_column_if_not_exists(c, "users", "email", "TEXT") # Use database._add_column_if_not_exists
    c.execute("PRAGMA table_info(users)")
    columns_after_second_call = [row[1] for row in c.fetchall()]
    assert columns == columns_after_second_call

    conn.close()


def test_load_table(
    active_user, monkeypatch
):  # Uses active_user fixture (which implies test_db)
    # Temporarily replace the cached function with its original, undecorated version
    monkeypatch.setattr(app, "load_table", app.load_table.__wrapped__)

    test_user_id = active_user
    # Test loading an empty table
    df_empty = app.load_table("resistance", test_user_id)
    assert isinstance(df_empty, pd.DataFrame)
    assert df_empty.empty is True

    # Insert some data for the test user
    conn = app.get_db_connection()
    c = conn.cursor()
    today_str = date.today().isoformat()
    c.execute(
        "INSERT INTO resistance (user_id, date, week, day, exercise, set_number, target, actual_weight, actual_reps, rir) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (test_user_id, today_str, 1, "Monday", "Squat", 1, "5x5", 100, 5, 2),
    )
    conn.commit()
    conn.close()

    df_with_data = app.load_table("resistance", test_user_id)
    assert df_with_data.empty is False
    assert len(df_with_data) == 1
    assert df_with_data.iloc[0]["exercise"] == "Squat"

    # Test loading for another user (who has no data)
    conn_temp = app.get_db_connection()  # Need a connection to create another user
    c_temp = conn_temp.cursor()
    # Manually create another user for this specific test case, as active_user is fixed
    other_user_id = app.create_user_in_db("otherdatauser", "pass")
    assert other_user_id is not None
    conn_temp.close()

    df_other_user = app.load_table("resistance", other_user_id)
    assert df_other_user.empty is True

    # Test loading with None user_id
    df_none_user = app.load_table("resistance", None)
    assert df_none_user.empty is True


def test_fetch_last(active_user, monkeypatch):  # Uses active_user fixture
    # Temporarily replace the cached function with its original, undecorated version
    monkeypatch.setattr(app, "fetch_last", app.fetch_last.__wrapped__)

    test_user_id = active_user
    # Test fetching when no data exists
    last = app.fetch_last("Squat", 1, test_user_id)
    assert last == (None, None, None)

    # Insert data
    conn = app.get_db_connection()
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

    weight, reps, rir = app.fetch_last("Squat", 1, test_user_id)
    assert weight == 100.0
    assert reps == 5
    assert rir == 2

    # Test fetching for an exercise that doesn't exist for the user
    last_other_ex = app.fetch_last("Bench", 1, test_user_id)
    assert last_other_ex == (None, None, None)

    # Test fetching with None user_id
    last_none_user = app.fetch_last("Squat", 1, None)
    assert last_none_user == (None, None, None)


# --- _save_form_data Function Tests ---


def test_save_form_data_single_insert(mock_st_environment, active_user):
    mock_st = mock_st_environment  # Get the mocked st object
    test_user_id = active_user  # Get the user_id from active_user fixture

    today_str = date.today().isoformat()
    query = "INSERT INTO mobility(user_id, date, prep_done, joint_flow_done, animal_circuit_done, cuff_finisher_done) VALUES(?,?,?,?,?,?)"
    payload = (test_user_id, today_str, 1, 1, 0, 0)

    app._save_form_data(query, payload, "Saved Mobility")

    mock_st.success.assert_called_with("Saved Mobility")
    mock_st.cache_data.clear.assert_called_once()

    # Verify data in DB
    conn = app.get_db_connection()
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

    app._save_form_data(query, payload, "Saved Resistance", is_many=True)

    mock_st.success.assert_called_with("Saved Resistance")
    mock_st.cache_data.clear.assert_called_once()

    conn = app.get_db_connection()
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

    app._save_form_data("QUERY", (), "Success Message")

    mock_st.error.assert_called_with("User not logged in. Cannot save data.")
    mock_st.success.assert_not_called()
    mock_st.cache_data.clear.assert_not_called()


def test_save_form_data_empty_payload_for_many(mock_st_environment):
    mock_st = mock_st_environment
    # User is logged in via mock_st_environment fixture

    app._save_form_data("QUERY", [], "Success Message", is_many=True)

    mock_st.warning.assert_called_with("No data to save.")
    mock_st.success.assert_not_called()
    mock_st.cache_data.clear.assert_not_called()
