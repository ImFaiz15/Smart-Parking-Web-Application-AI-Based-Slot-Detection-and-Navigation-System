"""
auth.py  –  Authentication Logic & Validators
─────────────────────────────────────────────────────────────────────────────
This file contains the BUSINESS LOGIC for the authentication system.

It handles:
  1. Input validation  (email format, mobile number, password rules)
  2. Password hashing  (never store plain text passwords)
  3. User registration (calls validators, then writes to DB)
  4. User login        (checks credentials against the DB)

This file is the "brain" between the Streamlit UI (auth_app.py) and
the database (auth_db.py). It does NOT render any UI elements.

Flow:
  auth_app.py  →  calls auth.py  →  auth.py calls auth_db.py
─────────────────────────────────────────────────────────────────────────────
"""

import re
import hashlib

# Import our database functions from auth_db.py
from auth_db import (
    init_users_db,
    add_user,
    email_exists,
    vehicle_exists,
    get_user_by_email,
)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 ─ INITIALISE DATABASE ON IMPORT
# ══════════════════════════════════════════════════════════════════════════════
# Calling init_users_db() here means the users table is automatically
# created the moment this module is imported. Safe to call multiple times.
init_users_db()


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 ─ PASSWORD HASHING
# ══════════════════════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    """
    Converts a plain text password into a SHA-256 hash string.

    WHY do we hash passwords?
      Never store plain text passwords in a database.
      If the database is ever leaked, hashed passwords cannot be reversed.
      Hashing is a one-way process: "mypassword" → "a3f4bc9d1..."

    HOW SHA-256 works (simple explanation):
      It takes any text and produces a fixed-length 64-character string.
      The same input always produces the same output.
      Two different inputs almost never produce the same output.

    Parameters:
        password (str): The plain text password entered by the user.

    Returns:
        str: A 64-character hexadecimal hash string.

    Example:
        hash_password("hello123") → "2cf24db..."
    """
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """
    Verifies that a plain text password matches a stored hash.

    We hash the plain password and compare it to the stored hash.
    We never "decrypt" — hashing is irreversible.

    Parameters:
        plain_password (str): Password entered by the user at login.
        stored_hash    (str): The hash retrieved from the database.

    Returns:
        bool: True if the password is correct, False otherwise.
    """
    return hash_password(plain_password) == stored_hash


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 ─ INPUT VALIDATORS
# ══════════════════════════════════════════════════════════════════════════════
# Each validator returns a tuple: (is_valid: bool, message: str)
# This makes it easy for auth_app.py to show the right error message.

def validate_full_name(name: str) -> tuple:
    """
    Validates the user's full name.

    Rules:
      - Cannot be empty or only spaces.
      - Must be at least 3 characters long.
      - Cannot contain numbers or special characters.

    Parameters:
        name (str): The full name entered in the registration form.

    Returns:
        tuple: (True, "OK") on success, or (False, "Error message") on failure.
    """
    name = name.strip()

    if not name:
        return False, "Full name cannot be empty."
    if len(name) < 3:
        return False, "Full name must be at least 3 characters."
    if not re.match(r"^[A-Za-z\s]+$", name):
        return False, "Full name must contain only letters and spaces."

    return True, "OK"


def validate_email(email: str) -> tuple:
    """
    Validates the email address format using a regular expression (regex).

    What is a regex?
      A regex (Regular Expression) is a pattern used to match text.
      The pattern r'^[\w.-]+@[\w.-]+\.\w{2,}$' means:
        - One or more word characters, dots, or hyphens BEFORE the @
        - Followed by @
        - Followed by a domain name (e.g., gmail)
        - Followed by a dot and 2+ characters (e.g., .com, .in)

    Valid examples:   faiz@gmail.com, student@college.in
    Invalid examples: faiz@, @gmail.com, faizgmail.com

    Parameters:
        email (str): The email entered in the form.

    Returns:
        tuple: (True, "OK") or (False, "Error message").
    """
    email = email.strip()

    if not email:
        return False, "Email address cannot be empty."

    pattern = r'^[\w\.\-]+@[\w\.\-]+\.\w{2,}$'
    if not re.match(pattern, email):
        return False, "Please enter a valid email address (e.g., name@gmail.com)."

    return True, "OK"


def validate_mobile(mobile: str) -> tuple:
    """
    Validates the Indian mobile number.

    Rules:
      - Must be exactly 10 digits.
      - Must start with 6, 7, 8, or 9 (Indian mobile numbers).
      - No spaces, dashes, or country code (+91).

    Parameters:
        mobile (str): The mobile number entered in the form.

    Returns:
        tuple: (True, "OK") or (False, "Error message").
    """
    mobile = mobile.strip()

    if not mobile:
        return False, "Mobile number cannot be empty."
    if not mobile.isdigit():
        return False, "Mobile number must contain only digits (no spaces or dashes)."
    if len(mobile) != 10:
        return False, "Mobile number must be exactly 10 digits."
    if mobile[0] not in "6789":
        return False, "Mobile number must start with 6, 7, 8, or 9."

    return True, "OK"


def validate_vehicle_number(vehicle_number: str) -> tuple:
    """
    Validates the Indian vehicle registration number.

    Standard format: 2 letters + 2 digits + 2 letters + 4 digits
    Example: MH01AB1234, KA02XY9999, DL4CAF0001

    Parameters:
        vehicle_number (str): The vehicle number entered in the form.

    Returns:
        tuple: (True, "OK") or (False, "Error message").
    """
    vehicle_number = vehicle_number.strip().upper()

    if not vehicle_number:
        return False, "Vehicle number cannot be empty."

    # Regex pattern for Indian vehicle numbers
    pattern = r'^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$'
    if not re.match(pattern, vehicle_number):
        return False, "Enter a valid vehicle number (e.g., MH01AB1234 or DL4CAF0001)."

    return True, "OK"


def validate_password(password: str) -> tuple:
    """
    Validates the strength of the password.

    Rules:
      - At least 8 characters long.
      - Contains at least one uppercase letter.
      - Contains at least one digit.
      - Contains at least one special character.

    Parameters:
        password (str): The password entered in the form.

    Returns:
        tuple: (True, "OK") or (False, "Error message").
    """
    if not password:
        return False, "Password cannot be empty."
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter (A-Z)."
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one digit (0-9)."
    if not re.search(r'[!@#$%^&*(),.?\":{}|<>]', password):
        return False, "Password must contain at least one special character (!@#$...)."

    return True, "OK"


def validate_passwords_match(password: str, confirm_password: str) -> tuple:
    """
    Checks that the password and confirm password fields are identical.

    Parameters:
        password         (str): The original password.
        confirm_password (str): The confirmation password.

    Returns:
        tuple: (True, "OK") or (False, "Error message").
    """
    if not confirm_password:
        return False, "Please confirm your password."
    if password != confirm_password:
        return False, "Passwords do not match. Please try again."

    return True, "OK"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 ─ REGISTER USER
# ══════════════════════════════════════════════════════════════════════════════

def register_user(
    full_name: str,
    email: str,
    mobile: str,
    vehicle_number: str,
    password: str,
    confirm_password: str
) -> tuple:
    """
    Runs ALL validations and registers a new user in the database.

    This is the main function called by the Streamlit registration form.
    It checks inputs one by one and returns early with an error if any
    validation fails, so the user knows exactly what to fix.

    Validation order:
      1. Full name format check
      2. Email format check
      3. Mobile number check
      4. Vehicle number format check
      5. Password strength check
      6. Password match check
      7. Duplicate email check (database query)
      8. Duplicate vehicle check (database query)
      9. Insert into database

    Parameters:
        full_name       (str): User's full name.
        email           (str): User's email.
        mobile          (str): User's mobile number.
        vehicle_number  (str): User's vehicle registration number.
        password        (str): User's chosen password.
        confirm_password(str): User's repeated password.

    Returns:
        tuple: (True, "Success message") or (False, "Error message").
    """

    # ── Step 1: Validate full name ────────────────────────────────────────────
    ok, msg = validate_full_name(full_name)
    if not ok:
        return False, msg

    # ── Step 2: Validate email format ─────────────────────────────────────────
    ok, msg = validate_email(email)
    if not ok:
        return False, msg

    # ── Step 3: Validate mobile number ────────────────────────────────────────
    ok, msg = validate_mobile(mobile)
    if not ok:
        return False, msg

    # ── Step 4: Validate vehicle number ───────────────────────────────────────
    ok, msg = validate_vehicle_number(vehicle_number)
    if not ok:
        return False, msg

    # ── Step 5: Validate password strength ────────────────────────────────────
    ok, msg = validate_password(password)
    if not ok:
        return False, msg

    # ── Step 6: Check passwords match ─────────────────────────────────────────
    ok, msg = validate_passwords_match(password, confirm_password)
    if not ok:
        return False, msg

    # ── Step 7: Check for duplicate email in database ─────────────────────────
    if email_exists(email):
        return False, "This email address is already registered. Please log in instead."

    # ── Step 8: Check for duplicate vehicle number in database ────────────────
    if vehicle_exists(vehicle_number):
        return False, "This vehicle number is already registered to another account."

    # ── Step 9: All checks passed → hash password and save to database ─────────
    hashed = hash_password(password)
    success = add_user(full_name, email, mobile, vehicle_number, hashed)

    if success:
        return True, f"Account created successfully! Welcome, {full_name.split()[0]}! 🎉"
    else:
        return False, "Registration failed due to a database error. Please try again."


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 ─ LOGIN USER
# ══════════════════════════════════════════════════════════════════════════════

def login_user(email: str, password: str) -> tuple:
    """
    Verifies user credentials and returns the user's data on success.

    Steps:
      1. Check that email and password are not empty.
      2. Fetch the user record from the database by email.
      3. If not found → email is not registered.
      4. If found → compare the entered password with the stored hash.
      5. Return the user dict on success (used to display on dashboard).

    Parameters:
        email    (str): Email entered in the login form.
        password (str): Password entered in the login form.

    Returns:
        tuple:
          (True, user_dict) → login successful. user_dict has all user fields.
          (False, "Error message") → login failed.
    """

    # ── Step 1: Check for empty fields ────────────────────────────────────────
    if not email.strip():
        return False, "Please enter your email address."
    if not password:
        return False, "Please enter your password."

    # ── Step 2: Fetch user from the database ──────────────────────────────────
    user = get_user_by_email(email)

    # ── Step 3: Check if user exists ──────────────────────────────────────────
    if user is None:
        # Intentionally vague message — don't reveal whether email exists
        return False, "Invalid email or password. Please check and try again."

    # ── Step 4: Verify password ───────────────────────────────────────────────
    if not verify_password(password, user["password_hash"]):
        return False, "Invalid email or password. Please check and try again."

    # ── Step 5: Login successful ──────────────────────────────────────────────
    return True, user


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 ─ LOGOUT USER
# ══════════════════════════════════════════════════════════════════════════════

def logout_user(session_state) -> None:
    """
    Clears the user's login session from Streamlit's session state.

    Streamlit's st.session_state is a dictionary-like object that persists
    data across reruns of the app (as long as the browser tab is open).
    Logging out simply means deleting the stored user data from it.

    Parameters:
        session_state: Streamlit's st.session_state object passed in from auth_app.py.
    """
    session_state.logged_in = False
    session_state.user       = None


# ══════════════════════════════════════════════════════════════════════════════
# SELF-TEST BLOCK
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("─" * 50)
    print("  auth.py  –  Validator Self Tests")
    print("─" * 50)

    tests = [
        ("validate_email",   validate_email,   ["faiz@gmail.com", "bad-email", ""]),
        ("validate_mobile",  validate_mobile,  ["9876543210", "123", "1234567890"]),
        ("validate_vehicle", validate_vehicle_number, ["MH01AB1234", "INVALID", ""]),
        ("validate_password",validate_password,["Secure@123", "short", "nouppercase1!"]),
    ]

    for name, func, inputs in tests:
        print(f"\n  [{name}]")
        for val in inputs:
            ok, msg = func(val)
            status = "✓ PASS" if ok else "✗ FAIL"
            print(f"    {status}  input={repr(val):20}  →  {msg}")

    print("\n─" * 50)
    print("  Testing register_user flow...")
    print("─" * 50)
    ok, msg = register_user(
        full_name="Test User",
        email="test@example.com",
        mobile="9123456780",
        vehicle_number="MH01AB9999",
        password="Secret@123",
        confirm_password="Secret@123"
    )
    print(f"\n  register_user → ok={ok}, msg={msg}")

    if ok:
        print("\n  Testing login_user flow...")
        ok2, result = login_user("test@example.com", "Secret@123")
        print(f"  login_user → ok={ok2}, name={result.get('full_name') if ok2 else result}")

        print("\n  Testing wrong password...")
        ok3, result3 = login_user("test@example.com", "wrongpass")
        print(f"  login_user → ok={ok3}, msg={result3}")

        # Cleanup test data
        import sqlite3, os
        conn = sqlite3.connect("users.db")
        conn.execute("DELETE FROM users WHERE email='test@example.com'")
        conn.commit()
        conn.close()
        print("\n  ✓ Test user removed from database.")

    print("\nAll auth.py tests complete!")
