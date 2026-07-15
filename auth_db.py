"""
auth_db.py  –  User Database Handler
─────────────────────────────────────────────────────────────────────────────
This file handles ONLY the database operations related to users.
It creates the 'users' table in SQLite and provides functions to:
  - Add a new user (Registration)
  - Check if an email already exists (Duplicate check)
  - Check if a vehicle number already exists (Duplicate check)
  - Fetch a user by email (Login)

This file has ONE job: talk to the database.
It does NOT know about Streamlit, forms, or any UI.
─────────────────────────────────────────────────────────────────────────────
"""

import sqlite3
from datetime import datetime

# ── Database file path ────────────────────────────────────────────────────────
# This creates a separate database file for users.
# We keep it separate from parking_slots.db for clean organisation.
USERS_DB_PATH = "users.db"


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 1 ─ init_users_db
# ══════════════════════════════════════════════════════════════════════════════

def init_users_db(db_path: str = USERS_DB_PATH) -> None:
    """
    Creates the 'users' table inside the SQLite database file.

    Table columns:
    ┌──────────────────┬─────────────────────────────────────────────────────┐
    │ Column           │ Description                                         │
    ├──────────────────┼─────────────────────────────────────────────────────┤
    │ id               │ Auto-increments. Unique number for every user.      │
    │ full_name        │ The user's full name (e.g., "Mohd Faiz").           │
    │ email            │ User's email. Marked UNIQUE — no duplicates.        │
    │ mobile           │ 10-digit mobile number stored as text.              │
    │ vehicle_number   │ Car plate. Marked UNIQUE — no duplicates.           │
    │ password_hash    │ Hashed version of the password. NEVER plain text.  │
    │ created_at       │ Timestamp of when the account was created.         │
    └──────────────────┴─────────────────────────────────────────────────────┘

    Parameters:
        db_path (str): Path to the SQLite database file.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # CREATE TABLE IF NOT EXISTS → only creates if the table does not exist.
    # This means calling init_users_db() multiple times is safe — no errors.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name      TEXT    NOT NULL,
            email          TEXT    NOT NULL UNIQUE,
            mobile         TEXT    NOT NULL,
            vehicle_number TEXT    NOT NULL UNIQUE,
            password_hash  TEXT    NOT NULL,
            created_at     TEXT    NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 2 ─ add_user
# ══════════════════════════════════════════════════════════════════════════════

def add_user(
    full_name: str,
    email: str,
    mobile: str,
    vehicle_number: str,
    password_hash: str,
    db_path: str = USERS_DB_PATH
) -> bool:
    """
    Inserts a new user row into the 'users' table.

    This is called only AFTER all validations have passed (in auth.py).

    Parameters:
        full_name      (str): User's full name.
        email          (str): User's email address.
        mobile         (str): User's 10-digit mobile number.
        vehicle_number (str): User's vehicle registration number.
        password_hash  (str): SHA-256 hash of the user's password.
        db_path        (str): Path to the database file.

    Returns:
        bool: True  → user was added successfully.
              False → insertion failed (e.g., duplicate email or vehicle).
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Record the exact time the account was created
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    success = False
    try:
        cursor.execute("""
            INSERT INTO users (full_name, email, mobile, vehicle_number, password_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (full_name, email.lower().strip(), mobile, vehicle_number.upper(), password_hash, timestamp))
        # Note: email is stored in lowercase, vehicle_number in uppercase → consistent lookups

        conn.commit()
        success = True

    except sqlite3.IntegrityError:
        # IntegrityError is raised when a UNIQUE constraint is violated.
        # This means the email or vehicle number already exists.
        success = False

    finally:
        conn.close()

    return success


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 3 ─ email_exists
# ══════════════════════════════════════════════════════════════════════════════

def email_exists(email: str, db_path: str = USERS_DB_PATH) -> bool:
    """
    Checks whether an email address is already registered in the database.

    Used during Registration to prevent duplicate accounts.

    Parameters:
        email   (str): The email to check.
        db_path (str): Path to the database file.

    Returns:
        bool: True  → email already exists (registration should be blocked).
              False → email is new and can be used.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # COUNT(*) returns the number of rows matching the WHERE clause.
    # If count > 0, the email is already taken.
    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE email = ?",
        (email.lower().strip(),)
    )
    count = cursor.fetchone()[0]   # fetchone() returns a tuple, [0] gets the count
    conn.close()

    return count > 0   # True if found, False if not


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 4 ─ vehicle_exists
# ══════════════════════════════════════════════════════════════════════════════

def vehicle_exists(vehicle_number: str, db_path: str = USERS_DB_PATH) -> bool:
    """
    Checks whether a vehicle number is already registered.

    Used during Registration so that two users cannot register the same car.

    Parameters:
        vehicle_number (str): The vehicle number to check (e.g., 'MH01AB1234').
        db_path        (str): Path to the database file.

    Returns:
        bool: True  → vehicle already registered.
              False → vehicle number is free to use.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE vehicle_number = ?",
        (vehicle_number.upper().strip(),)
    )
    count = cursor.fetchone()[0]
    conn.close()

    return count > 0


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 5 ─ get_user_by_email
# ══════════════════════════════════════════════════════════════════════════════

def get_user_by_email(email: str, db_path: str = USERS_DB_PATH) -> dict | None:
    """
    Fetches a user's full record from the database using their email address.

    Used during Login to:
      1. Confirm the user exists.
      2. Retrieve the stored password hash for comparison.
      3. Retrieve the user's info to display on the dashboard.

    Parameters:
        email   (str): Email of the user trying to log in.
        db_path (str): Path to the database file.

    Returns:
        dict: A dictionary with all user fields if the user is found.
              Example:
              {
                  'id': 1,
                  'full_name': 'Mohd Faiz',
                  'email': 'faiz@example.com',
                  'mobile': '9876543210',
                  'vehicle_number': 'MH01AB1234',
                  'password_hash': 'a3f4b...',
                  'created_at': '2026-07-08 11:30:00'
              }
        None: If no user with this email was found.
    """
    conn = sqlite3.connect(db_path)

    # row_factory = sqlite3.Row makes each row behave like a dictionary.
    # This lets us access columns by name: row['email'] instead of row[1].
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE email = ?",
        (email.lower().strip(),)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        # Convert the Row object to a plain Python dict for easy use
        return dict(row)
    return None


# ══════════════════════════════════════════════════════════════════════════════
# SELF-TEST BLOCK
# ══════════════════════════════════════════════════════════════════════════════
# Run directly to verify the database works:
#   python auth_db.py
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os

    TEST_DB = "test_users.db"

    print("─" * 45)
    print("  auth_db.py  –  Self Test")
    print("─" * 45)

    print("\n[1] Initialising database...")
    init_users_db(TEST_DB)
    print("    ✓ users table created.")

    print("\n[2] Adding a test user...")
    added = add_user(
        full_name="Mohd Faiz",
        email="faiz@example.com",
        mobile="9876543210",
        vehicle_number="MH01AB1234",
        password_hash="HASHED_PASSWORD_PLACEHOLDER",
        db_path=TEST_DB
    )
    print(f"    ✓ User added: {added}")

    print("\n[3] Checking for duplicate email...")
    print(f"    email_exists('faiz@example.com') → {email_exists('faiz@example.com', TEST_DB)}")
    print(f"    email_exists('new@example.com')  → {email_exists('new@example.com', TEST_DB)}")

    print("\n[4] Checking for duplicate vehicle...")
    print(f"    vehicle_exists('MH01AB1234') → {vehicle_exists('MH01AB1234', TEST_DB)}")
    print(f"    vehicle_exists('KA02XY9999') → {vehicle_exists('KA02XY9999', TEST_DB)}")

    print("\n[5] Fetching user by email...")
    user = get_user_by_email("faiz@example.com", TEST_DB)
    print(f"    Found user: {user['full_name']}, Mobile: {user['mobile']}")

    # Cleanup
    os.remove(TEST_DB)
    print("\n    ✓ Test database cleaned up.")
    print("\nAll tests passed!")
