"""
auth_app.py  –  Streamlit Authentication UI
─────────────────────────────────────────────────────────────────────────────
This file is the MAIN ENTRY POINT for the Smart Parking Authentication System.

It renders three different pages based on the user's state:
  Page 1 → Login Page         (when the user is not logged in)
  Page 2 → Registration Page  (when the user clicks "Create Account")
  Page 3 → Dashboard          (after successful login)

It uses Streamlit's session_state to remember whether a user is logged in.
session_state is like a temporary memory that persists across page reruns.

Run with:
  streamlit run auth_app.py
─────────────────────────────────────────────────────────────────────────────
"""

import streamlit as st
from datetime import datetime

# Import our authentication logic
from auth import register_user, login_user, logout_user


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 ─ PAGE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
# Must be the FIRST Streamlit call in the script.

st.set_page_config(
    page_title="Smart Parking – Login",
    page_icon="🅿️",
    layout="centered",       # "centered" is better for forms than "wide"
    initial_sidebar_state="collapsed",
)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 ─ CUSTOM CSS
# ══════════════════════════════════════════════════════════════════════════════

def apply_styles() -> None:
    """
    Injects custom CSS for the entire authentication UI.
    Uses a dark, modern design with glass-morphism card effects.
    """
    st.markdown("""
    <style>

    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

    /* ── Global ─────────────────────────────────────────────────── */
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .stApp {
        background: radial-gradient(ellipse at top left, #0d1f3c 0%, #0b1120 60%, #050c1a 100%);
        min-height: 100vh;
    }

    /* ── Hide Streamlit default decorations ─────────────────────── */
    #MainMenu, footer, header { visibility: hidden; }

    /* ── Auth Card (wraps the form) ─────────────────────────────── */
    .auth-card {
        background: rgba(15, 28, 54, 0.85);
        border: 1px solid rgba(99, 179, 255, 0.12);
        border-radius: 24px;
        padding: 40px 36px;
        backdrop-filter: blur(16px);
        box-shadow: 0 24px 64px rgba(0, 0, 0, 0.6);
        margin: 0 auto;
    }

    /* ── Logo / Brand ───────────────────────────────────────────── */
    .brand-logo {
        font-size: 3.2rem;
        margin-bottom: 4px;
        display: block;
        text-align: center;
    }
    .brand-title {
        font-size: 1.7rem;
        font-weight: 800;
        color: #f0f6ff;
        text-align: center;
        margin: 0;
        letter-spacing: -0.3px;
    }
    .brand-subtitle {
        font-size: 0.82rem;
        color: #4a6080;
        text-align: center;
        margin-top: 5px;
        margin-bottom: 28px;
    }

    /* ── Section divider with label ─────────────────────────────── */
    .form-section-label {
        font-size: 0.68rem;
        font-weight: 700;
        color: #3b6ea5;
        text-transform: uppercase;
        letter-spacing: 2px;
        margin: 18px 0 8px;
    }

    /* ── Custom Streamlit input overrides ───────────────────────── */
    [data-testid="stTextInput"] input,
    [data-testid="stTextInput"] input:focus {
        background-color: #0d1829 !important;
        border: 1px solid #1a3058 !important;
        border-radius: 10px !important;
        color: #e2eaf5 !important;
        font-size: 0.9rem !important;
        padding: 10px 14px !important;
        transition: border-color 0.2s ease;
    }
    [data-testid="stTextInput"] input:focus {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12) !important;
    }

    /* ── Primary Button ─────────────────────────────────────────── */
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #1d4ed8, #3b82f6);
        color: #ffffff;
        border: none;
        border-radius: 12px;
        padding: 13px 0;
        font-size: 0.95rem;
        font-weight: 700;
        letter-spacing: 0.3px;
        cursor: pointer;
        transition: all 0.2s ease;
        box-shadow: 0 4px 20px rgba(59, 130, 246, 0.35);
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #1e40af, #2563eb);
        transform: translateY(-2px);
        box-shadow: 0 8px 28px rgba(59, 130, 246, 0.45);
    }
    .stButton > button:active { transform: translateY(0); }

    /* ── Toggle link row ────────────────────────────────────────── */
    .toggle-row {
        text-align: center;
        margin-top: 20px;
        font-size: 0.85rem;
        color: #4a6080;
    }

    /* ── Success / Error banners ────────────────────────────────── */
    .banner-success {
        background: rgba(22, 101, 52, 0.3);
        border: 1px solid #16a34a55;
        border-radius: 12px;
        padding: 12px 16px;
        color: #4ade80;
        font-size: 0.88rem;
        font-weight: 500;
        margin-bottom: 16px;
    }
    .banner-error {
        background: rgba(127, 29, 29, 0.3);
        border: 1px solid #dc262655;
        border-radius: 12px;
        padding: 12px 16px;
        color: #f87171;
        font-size: 0.88rem;
        font-weight: 500;
        margin-bottom: 16px;
    }

    /* ── Dashboard ──────────────────────────────────────────────── */
    .dash-header {
        background: linear-gradient(135deg, #0f2444, #0b1120);
        border: 1px solid #1e40af33;
        border-radius: 20px;
        padding: 30px 28px;
        margin-bottom: 24px;
        text-align: center;
    }
    .dash-welcome {
        font-size: 1.9rem;
        font-weight: 800;
        color: #f0f6ff;
        margin: 0;
    }
    .dash-subtitle {
        color: #4a6080;
        font-size: 0.88rem;
        margin-top: 4px;
    }

    .info-card {
        background: #0e1c33;
        border: 1px solid #1a3058;
        border-radius: 16px;
        padding: 22px 20px;
        margin-bottom: 14px;
    }
    .info-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 9px 0;
        border-bottom: 1px solid #132040;
        font-size: 0.88rem;
    }
    .info-row:last-child { border-bottom: none; }
    .info-label { color: #4a6080; font-weight: 600; }
    .info-value { color: #c8daf5; font-weight: 500; }

    .nav-card {
        background: #0e1c33;
        border: 1px solid #1a3058;
        border-radius: 16px;
        padding: 22px 20px;
        text-align: center;
        transition: border-color 0.2s;
    }
    .nav-card:hover { border-color: #3b82f6; }
    .nav-icon  { font-size: 2.2rem; margin-bottom: 8px; }
    .nav-title { font-size: 0.95rem; font-weight: 700; color: #c8daf5; }
    .nav-desc  { font-size: 0.78rem; color: #4a6080; margin-top: 4px; }

    .logout-btn > button {
        background: linear-gradient(135deg, #7f1d1d, #dc2626) !important;
        box-shadow: 0 4px 20px rgba(220, 38, 38, 0.3) !important;
    }
    .logout-btn > button:hover {
        background: linear-gradient(135deg, #991b1b, #ef4444) !important;
    }

    </style>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 ─ SESSION STATE INITIALISATION
# ══════════════════════════════════════════════════════════════════════════════

def init_session_state() -> None:
    """
    Sets up Streamlit's session_state variables with default values.

    session_state is Streamlit's way of remembering information between
    page reruns. Every time a user clicks a button or changes an input,
    Streamlit reruns the entire script. session_state preserves variables.

    Variables we use:
        logged_in (bool): Whether the user is currently authenticated.
        user      (dict): The logged-in user's data (name, email, etc.).
        page      (str) : Current page — "login" or "register".
    """
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if "user" not in st.session_state:
        st.session_state.user = None

    if "page" not in st.session_state:
        st.session_state.page = "login"   # Default landing page


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 ─ LOGIN PAGE
# ══════════════════════════════════════════════════════════════════════════════

def show_login_page() -> None:
    """
    Renders the Login form.

    Fields:
      - Email
      - Password

    On submit:
      - Calls login_user() from auth.py
      - If successful, sets session_state.logged_in = True and stores user data
      - Calls st.rerun() to immediately redirect to the dashboard
    """
    # ── Brand header ─────────────────────────────────────────────────────────
    st.markdown("""
    <div class="auth-card">
        <span class="brand-logo">🅿️</span>
        <p class="brand-title">Smart Parking</p>
        <p class="brand-subtitle">Sign in to access your parking dashboard</p>
    """, unsafe_allow_html=True)

    # ── Login form ────────────────────────────────────────────────────────────
    # st.form() groups inputs together so Streamlit only reruns when the
    # form is submitted, not on every keystroke.
    with st.form(key="login_form", clear_on_submit=False):

        st.markdown('<div class="form-section-label">Account Credentials</div>',
                    unsafe_allow_html=True)

        email = st.text_input(
            label="Email Address",
            placeholder="you@example.com",
        )

        password = st.text_input(
            label="Password",
            placeholder="Enter your password",
            type="password",   # Hides the characters
        )

        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button("Sign In →", use_container_width=True)

    # ── Handle form submission ─────────────────────────────────────────────────
    if submitted:
        ok, result = login_user(email, password)

        if ok:
            # Store user data and set logged_in flag
            st.session_state.logged_in = True
            st.session_state.user      = result
            st.rerun()   # Restart script → main() detects logged_in → shows dashboard
        else:
            # Show error banner (result is the error message string on failure)
            st.markdown(f'<div class="banner-error">⚠️ {result}</div>',
                        unsafe_allow_html=True)

    # ── Toggle to Registration ─────────────────────────────────────────────────
    st.markdown('<div class="toggle-row">Don\'t have an account?</div>',
                unsafe_allow_html=True)

    if st.button("Create New Account", key="go_register", use_container_width=True):
        st.session_state.page = "register"
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)   # Close auth-card


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 ─ REGISTRATION PAGE
# ══════════════════════════════════════════════════════════════════════════════

def show_register_page() -> None:
    """
    Renders the Registration form.

    Fields:
      - Full Name
      - Email
      - Mobile Number
      - Vehicle Number
      - Password
      - Confirm Password

    On submit:
      - Calls register_user() from auth.py (which runs all validations)
      - Shows success or error message
      - On success, switches back to login page after a brief message
    """
    st.markdown("""
    <div class="auth-card">
        <span class="brand-logo">🅿️</span>
        <p class="brand-title">Create Account</p>
        <p class="brand-subtitle">Register to access the Smart Parking System</p>
    """, unsafe_allow_html=True)

    # ── Registration form ─────────────────────────────────────────────────────
    with st.form(key="register_form", clear_on_submit=False):

        # ── Personal Information ───────────────────────────────────────────────
        st.markdown('<div class="form-section-label">👤 Personal Information</div>',
                    unsafe_allow_html=True)

        full_name = st.text_input(
            label="Full Name",
            placeholder="Mohd Faiz",
        )

        email = st.text_input(
            label="Email Address",
            placeholder="faiz@example.com",
        )

        mobile = st.text_input(
            label="Mobile Number",
            placeholder="9876543210  (10 digits, no spaces)",
            max_chars=10,
        )

        # ── Vehicle Information ───────────────────────────────────────────────
        st.markdown('<div class="form-section-label">🚗 Vehicle Information</div>',
                    unsafe_allow_html=True)

        vehicle_number = st.text_input(
            label="Vehicle Registration Number",
            placeholder="MH01AB1234",
            help="Standard Indian format: e.g., MH01AB1234 or DL4CAF0001",
        )

        # ── Password ──────────────────────────────────────────────────────────
        st.markdown('<div class="form-section-label">🔒 Security</div>',
                    unsafe_allow_html=True)

        # Two-column layout for password fields
        col1, col2 = st.columns(2)
        with col1:
            password = st.text_input(
                label="Password",
                placeholder="Min 8 chars, A-Z, 0-9, !@#",
                type="password",
                help="Must have uppercase, digit, and special character.",
            )
        with col2:
            confirm_password = st.text_input(
                label="Confirm Password",
                placeholder="Repeat password",
                type="password",
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # Terms acknowledgment (simple checkbox)
        agree = st.checkbox("I agree to the Terms & Conditions")

        submitted = st.form_submit_button("Create My Account →", use_container_width=True)

    # ── Handle form submission ─────────────────────────────────────────────────
    if submitted:
        if not agree:
            st.markdown(
                '<div class="banner-error">⚠️ Please accept the Terms & Conditions to continue.</div>',
                unsafe_allow_html=True
            )
        else:
            ok, msg = register_user(
                full_name=full_name,
                email=email,
                mobile=mobile,
                vehicle_number=vehicle_number,
                password=password,
                confirm_password=confirm_password,
            )

            if ok:
                st.markdown(
                    f'<div class="banner-success">✅ {msg}</div>',
                    unsafe_allow_html=True
                )
                st.success("Redirecting to login page...")
                # Switch to login page after a moment so user sees the success message
                import time
                time.sleep(1.5)
                st.session_state.page = "login"
                st.rerun()
            else:
                st.markdown(
                    f'<div class="banner-error">⚠️ {msg}</div>',
                    unsafe_allow_html=True
                )

    # ── Toggle back to Login ───────────────────────────────────────────────────
    st.markdown('<div class="toggle-row">Already have an account?</div>',
                unsafe_allow_html=True)

    if st.button("Back to Sign In", key="go_login", use_container_width=True):
        st.session_state.page = "login"
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)   # Close auth-card


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 ─ DASHBOARD PAGE
# ══════════════════════════════════════════════════════════════════════════════

def show_dashboard() -> None:
    """
    Renders the post-login dashboard.

    Displayed only when session_state.logged_in is True.

    Shows:
      - Personalised welcome banner with the user's name
      - Profile information card (email, mobile, vehicle, joined date)
      - Navigation cards (Parking Monitor, My Bookings — placeholders for now)
      - Logout button
    """
    user = st.session_state.user   # The user dict from the database

    # ── Welcome banner ────────────────────────────────────────────────────────
    first_name = user["full_name"].split()[0]
    timestamp  = datetime.now().strftime("%d %b %Y  •  %I:%M %p")

    st.markdown(f"""
    <div class="dash-header">
        <p class="dash-welcome">👋 Welcome back, {first_name}!</p>
        <p class="dash-subtitle">{timestamp}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Layout: profile card on left, navigation on right ────────────────────
    col_profile, col_nav = st.columns([1.1, 1], gap="large")

    with col_profile:
        st.markdown("##### 🪪 Your Profile")
        st.markdown(f"""
        <div class="info-card">
            <div class="info-row">
                <span class="info-label">Full Name</span>
                <span class="info-value">{user['full_name']}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Email</span>
                <span class="info-value">{user['email']}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Mobile</span>
                <span class="info-value">{user['mobile']}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Vehicle No.</span>
                <span class="info-value">{user['vehicle_number']}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Member Since</span>
                <span class="info-value">{user['created_at'][:10]}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_nav:
        st.markdown("##### 🧭 Navigation")

        # Navigation card 1 — Parking Monitor
        st.markdown("""
        <div class="nav-card">
            <div class="nav-icon">🅿️</div>
            <div class="nav-title">Parking Monitor</div>
            <div class="nav-desc">View real-time parking slot availability</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Navigation card 2 — AI Detection (coming in Module 3)
        st.markdown("""
        <div class="nav-card">
            <div class="nav-icon">🤖</div>
            <div class="nav-title">AI Detection</div>
            <div class="nav-desc">YOLOv8 vehicle detection — coming in Module 3</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.divider()

    # ── Logout button ─────────────────────────────────────────────────────────
    # Wrapped in a div with class "logout-btn" to apply red CSS override
    st.markdown('<div class="logout-btn">', unsafe_allow_html=True)

    _, center_col, _ = st.columns([1, 1.5, 1])
    with center_col:
        if st.button("🚪 Sign Out", key="logout_btn", use_container_width=True):
            logout_user(st.session_state)   # Clears session_state
            st.rerun()                       # Restart → main() shows login page

    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 ─ MAIN  (Orchestrator)
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """
    Entry point — decides which page to display based on session state.

    Decision tree:
    ┌─────────────────────────────────────────────────────────┐
    │  Is user logged in? (session_state.logged_in == True)   │
    │         YES → show_dashboard()                          │
    │         NO  → which page is selected?                   │
    │               "login"    → show_login_page()            │
    │               "register" → show_register_page()         │
    └─────────────────────────────────────────────────────────┘
    """
    # Step 1: Apply CSS
    apply_styles()

    # Step 2: Set up session_state variables (safe to call every run)
    init_session_state()

    # Step 3: Route to the correct page
    if st.session_state.logged_in:
        show_dashboard()
    else:
        if st.session_state.page == "register":
            show_register_page()
        else:
            show_login_page()


# ══════════════════════════════════════════════════════════════════════════════
# SCRIPT GUARD
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()
