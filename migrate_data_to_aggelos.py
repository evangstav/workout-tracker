import sqlite3
import sys

DB_NAME = "workout_tracker.db"
TARGET_USERNAME = "Aggelos"
TABLES_TO_MIGRATE = ["resistance", "mobility", "cardio"]

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn

def migrate_data():
    conn = get_db_connection()
    c = conn.cursor()

    # 1. Find the target user's ID
    c.execute("SELECT id FROM users WHERE username = ?", (TARGET_USERNAME,))
    user_row = c.fetchone()

    if user_row is None:
        print(f"Error: User '{TARGET_USERNAME}' not found in the database.")
        print("Please ensure the user exists before running this migration script.")
        conn.close()
        sys.exit(1)

    target_user_id = user_row["id"]
    print(f"Found user '{TARGET_USERNAME}' with ID: {target_user_id}.")

    # 2. Update records in each table
    for table_name in TABLES_TO_MIGRATE:
        try:
            # Check if user_id column exists
            c.execute(f"PRAGMA table_info({table_name})")
            columns = [row['name'] for row in c.fetchall()]
            if 'user_id' not in columns:
                print(f"Warning: Table '{table_name}' does not have a 'user_id' column. Skipping.")
                continue

            # Get count of records to be updated
            # This will update ALL records to target_user_id, regardless of their current user_id.
            c.execute(f"SELECT COUNT(*) FROM {table_name}")
            total_records = c.fetchone()[0]
            
            c.execute(f"SELECT COUNT(*) FROM {table_name} WHERE user_id = ?", (target_user_id,))
            already_assigned_count = c.fetchone()[0]

            count_to_update = total_records - already_assigned_count
            
            if count_to_update == 0 and total_records > 0 :
                print(f"All records in table '{table_name}' are already assigned to user '{TARGET_USERNAME}'. Skipping update for this table.")
                continue
            elif total_records == 0:
                print(f"No records found in table '{table_name}'. Skipping.")
                continue
                
            print(f"Updating {count_to_update} records in table '{table_name}' to user_id {target_user_id}...")
            # This query updates ALL rows in the table to the target_user_id.
            c.execute(f"UPDATE {table_name} SET user_id = ?", (target_user_id,))
            conn.commit()
            print(f"Successfully updated records in '{table_name}'.")

        except sqlite3.Error as e:
            print(f"An error occurred while updating table '{table_name}': {e}")
            conn.rollback() # Rollback changes for this table on error
    
    print("\nData migration process finished.")
    conn.close()

if __name__ == "__main__":
    print(f"Starting data migration to user '{TARGET_USERNAME}'...")
    # It's a good practice to backup your database before running migration scripts.
    # input("Press Enter to continue after backing up your database, or Ctrl+C to cancel...")
    migrate_data()
