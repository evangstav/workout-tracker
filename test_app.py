import unittest
from unittest.mock import patch, MagicMock
import sqlite3
import pandas as pd
from datetime import date

# Before importing app, we need to ensure Streamlit's st object is minimally mocked
# if we want to avoid errors for st.set_page_config, etc., during import.
# However, for testing specific functions, we often mock 'st' more targetedly.
# For now, let's assume app.py can be imported, and we'll mock 'st' within tests.

import app  # This will run app.init_db() with the production DB_NAME once.

class TestAuthFunctions(unittest.TestCase):
    def setUp(self):
        self.original_db_name = app.DB_NAME
        app.DB_NAME = ":memory:"  # Use in-memory SQLite database for tests
        # We need to explicitly call init_db for the in-memory database.
        # init_db itself creates tables.
        conn = app.get_db_connection()
        app.init_db() # Re-initialize DB schema in memory
        conn.close()

    def tearDown(self):
        app.DB_NAME = self.original_db_name

    def test_hash_password(self):
        password = "testpassword"
        hashed = app.hash_password(password)
        self.assertIsInstance(hashed, str)
        self.assertNotEqual(password, hashed)

    def test_verify_password(self):
        password = "testpassword"
        hashed = app.hash_password(password)
        self.assertTrue(app.verify_password(hashed, password))
        self.assertFalse(app.verify_password(hashed, "wrongpassword"))

    def test_create_user_in_db(self):
        # Test successful user creation
        user_id = app.create_user_in_db("testuser", "password123")
        self.assertIsNotNone(user_id)
        self.assertIsInstance(user_id, int)

        # Test duplicate username
        duplicate_user_id = app.create_user_in_db("testuser", "anotherpassword")
        self.assertIsNone(duplicate_user_id)

    def test_get_user_from_db(self):
        app.create_user_in_db("testuser2", "password123")
        
        user = app.get_user_from_db("testuser2")
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "testuser2")

        non_existent_user = app.get_user_from_db("nonexistentuser")
        self.assertIsNone(non_existent_user)


class TestDataFunctions(unittest.TestCase):
    def setUp(self):
        self.original_db_name = app.DB_NAME
        app.DB_NAME = ":memory:"
        app.init_db() # Initialize schema in the in-memory DB

        # Create a test user for data operations
        self.test_user_id = app.create_user_in_db("datauser", "datapass")
        self.assertIsNotNone(self.test_user_id, "Setup failed: Could not create test user")


    def tearDown(self):
        app.DB_NAME = self.original_db_name

    def test_add_column_if_not_exists(self):
        conn = app.get_db_connection()
        c = conn.cursor()
        
        # Test adding a new column
        app._add_column_if_not_exists(c, "users", "email", "TEXT")
        c.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in c.fetchall()]
        self.assertIn("email", columns)

        # Test attempting to add an existing column (should not fail or change schema)
        app._add_column_if_not_exists(c, "users", "email", "TEXT")
        c.execute("PRAGMA table_info(users)")
        columns_after_second_call = [row[1] for row in c.fetchall()]
        self.assertEqual(columns, columns_after_second_call)
        
        conn.close()

    def test_load_table(self):
        # Test loading an empty table
        df_empty = app.load_table("resistance", self.test_user_id)
        self.assertTrue(isinstance(df_empty, pd.DataFrame))
        self.assertTrue(df_empty.empty)

        # Insert some data for the test user
        conn = app.get_db_connection()
        c = conn.cursor()
        today_str = date.today().isoformat()
        c.execute(
            "INSERT INTO resistance (user_id, date, week, day, exercise, set_number, target, actual_weight, actual_reps, rir) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (self.test_user_id, today_str, 1, "Monday", "Squat", 1, "5x5", 100, 5, 2)
        )
        conn.commit()
        conn.close()

        df_with_data = app.load_table("resistance", self.test_user_id)
        self.assertFalse(df_with_data.empty)
        self.assertEqual(len(df_with_data), 1)
        self.assertEqual(df_with_data.iloc[0]["exercise"], "Squat")

        # Test loading for a user with no data
        other_user_id = app.create_user_in_db("otheruser", "pass")
        df_other_user = app.load_table("resistance", other_user_id)
        self.assertTrue(df_other_user.empty)
        
        # Test loading with None user_id
        df_none_user = app.load_table("resistance", None)
        self.assertTrue(df_none_user.empty)


    def test_fetch_last(self):
        # Test fetching when no data exists
        last = app.fetch_last("Squat", 1, self.test_user_id)
        self.assertEqual(last, (None, None, None))

        # Insert data
        conn = app.get_db_connection()
        c = conn.cursor()
        today_str = date.today().isoformat()
        c.execute(
            "INSERT INTO resistance (user_id, date, week, day, exercise, set_number, target, actual_weight, actual_reps, rir) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (self.test_user_id, today_str, 1, "Monday", "Squat", 1, "5x5", 100.0, 5, 2)
        )
        # Insert an older record to ensure the latest is fetched
        older_date_str = (date.today() - pd.Timedelta(days=1)).isoformat()
        c.execute(
            "INSERT INTO resistance (user_id, date, week, day, exercise, set_number, target, actual_weight, actual_reps, rir) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (self.test_user_id, older_date_str, 1, "Monday", "Squat", 1, "5x5", 90.0, 5, 3)
        )
        conn.commit()
        conn.close()

        weight, reps, rir = app.fetch_last("Squat", 1, self.test_user_id)
        self.assertEqual(weight, 100.0)
        self.assertEqual(reps, 5)
        self.assertEqual(rir, 2)
        
        # Test fetching for an exercise that doesn't exist for the user
        last_other_ex = app.fetch_last("Bench", 1, self.test_user_id)
        self.assertEqual(last_other_ex, (None, None, None))

        # Test fetching with None user_id
        last_none_user = app.fetch_last("Squat", 1, None)
        self.assertEqual(last_none_user, (None, None, None))


class TestSaveFormDataFunction(unittest.TestCase):
    def setUp(self):
        self.original_db_name = app.DB_NAME
        app.DB_NAME = ":memory:"
        app.init_db()
        self.test_user_id = app.create_user_in_db("saveuser", "savepass")
        self.assertIsNotNone(self.test_user_id)

        # Mock Streamlit functionalities
        self.mock_st = MagicMock()
        self.mock_st.session_state = {'user_id': self.test_user_id} # Simulate logged-in user
        self.mock_st.cache_data.clear = MagicMock()

        # Patch 'st' in the 'app' module
        self.patcher_st = patch('app.st', self.mock_st)
        self.patcher_st.start()


    def tearDown(self):
        self.patcher_st.stop()
        app.DB_NAME = self.original_db_name

    def test_save_form_data_single_insert(self):
        today_str = date.today().isoformat()
        query = "INSERT INTO mobility(user_id, date, prep_done, joint_flow_done, animal_circuit_done, cuff_finisher_done) VALUES(?,?,?,?,?,?)"
        payload = (self.test_user_id, today_str, 1, 1, 0, 0)
        
        app._save_form_data(query, payload, "Saved Mobility")

        self.mock_st.success.assert_called_with("Saved Mobility")
        self.mock_st.cache_data.clear.assert_called_once()

        # Verify data in DB
        conn = app.get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM mobility WHERE user_id = ?", (self.test_user_id,))
        row = c.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["prep_done"], 1)
        conn.close()

    def test_save_form_data_many_insert(self):
        today_str = date.today().isoformat()
        query = "INSERT INTO resistance(user_id,date,week,day,exercise,set_number,target,actual_weight,actual_reps,rir) VALUES(?,?,?,?,?,?,?,?,?,?)"
        payload = [
            (self.test_user_id, today_str, 1, "Mon", "Squat", 1, "5x5", 100, 5, 2),
            (self.test_user_id, today_str, 1, "Mon", "Squat", 2, "5x5", 100, 5, 1),
        ]
        
        app._save_form_data(query, payload, "Saved Resistance", is_many=True)

        self.mock_st.success.assert_called_with("Saved Resistance")
        self.mock_st.cache_data.clear.assert_called_once()

        conn = app.get_db_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM resistance WHERE user_id = ?", (self.test_user_id,))
        count = c.fetchone()[0]
        self.assertEqual(count, 2)
        conn.close()

    def test_save_form_data_no_user_logged_in(self):
        self.mock_st.session_state['user_id'] = None # Simulate logged-out user
        
        app._save_form_data("QUERY", (), "Success Message")
        
        self.mock_st.error.assert_called_with("User not logged in. Cannot save data.")
        self.mock_st.success.assert_not_called()
        self.mock_st.cache_data.clear.assert_not_called()

    def test_save_form_data_empty_payload_for_many(self):
        app._save_form_data("QUERY", [], "Success Message", is_many=True)

        self.mock_st.warning.assert_called_with("No data to save.")
        self.mock_st.success.assert_not_called()
        self.mock_st.cache_data.clear.assert_not_called()


if __name__ == "__main__":
    unittest.main()
