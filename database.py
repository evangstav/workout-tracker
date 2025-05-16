import sqlite3
import hashlib

# --- Database Setup & Migration ---
DB_NAME = "workout_tracker.db"


def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


def _add_column_if_not_exists(
    cursor, table_name, column_name, column_type_with_constraints
):
    """Helper to add a column to a table if it doesn't already exist."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    if column_name not in columns:
        try:
            cursor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type_with_constraints}"
            )
        except sqlite3.OperationalError as e:
            # This check is for "duplicate column name", which might occur in rare scenarios
            # even after the "if column_name not in columns" check.
            if f"duplicate column name: {column_name}" not in str(
                e
            ):  # pragma: no cover
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

    # User Metrics table
    c.execute("""CREATE TABLE IF NOT EXISTS user_metrics(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        height_cm REAL,
        weight_kg REAL,
        sex TEXT,
        age INTEGER,
        body_fat_percentage REAL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    # User 1RM table
    c.execute("""CREATE TABLE IF NOT EXISTS user_1rm(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        exercise TEXT NOT NULL,
        one_rep_max REAL NOT NULL,
        date TEXT NOT NULL, -- Date the 1RM was achieved or recorded
        UNIQUE(user_id, exercise, date), -- Ensure unique 1RM per user, exercise, and date
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

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


def save_or_update_1rm(user_id, exercise, one_rep_max, rm_date):
    """Saves or updates a 1RM for a given user, exercise, and date.
    If a record for the exact user, exercise, and date exists, it updates it.
    Otherwise, it inserts a new record.
    """
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Try to update first if a record for that specific date exists
        c.execute("""
            UPDATE user_1rm SET one_rep_max = ?
            WHERE user_id = ? AND exercise = ? AND date = ?
        """, (one_rep_max, user_id, exercise, rm_date))

        if c.rowcount == 0: # No record for that date, so insert
            c.execute("""
                INSERT INTO user_1rm (user_id, exercise, one_rep_max, date)
                VALUES (?, ?, ?, ?)
            """, (user_id, exercise, one_rep_max, rm_date))
        conn.commit()
        return True
    except sqlite3.Error: # pragma: no cover
        # Could be IntegrityError if UNIQUE constraint is violated by a different path,
        # or other errors.
        return False
    finally:
        conn.close()


def get_latest_1rm(user_id, exercise):
    """Fetches the most recent 1RM for a given user and exercise."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT one_rep_max, date FROM user_1rm
        WHERE user_id = ? AND exercise = ?
        ORDER BY date DESC
        LIMIT 1
    """, (user_id, exercise))
    result = c.fetchone()
    conn.close()
    return result # Returns a Row object (e.g., result['one_rep_max']) or None


def get_user_from_db(username):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    return user


def update_user_password(user_id, new_password):
    """Updates the password_hash for a given user_id."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(new_password), user_id),
        )
        conn.commit()
        return True
    except sqlite3.Error:  # pragma: no cover
        # Could be various errors, though less likely for a simple update by ID
        return False
    finally:
        conn.close()
