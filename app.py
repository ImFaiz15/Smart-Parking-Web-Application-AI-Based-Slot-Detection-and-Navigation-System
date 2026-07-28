"""
app.py  –  Smart Parking Web Application  (Phase 3 — SQLite Live Mode)
─────────────────────────────────────────────────────────────────────────────
Main Streamlit dashboard — Phase 3: reads LIVE slot data from parking.db.

How Phase 3 works:
  1. On every refresh, load_slots_from_db() queries parking.db.
  2. The DB is updated in real time by detection_engine.py (background).
  3. st.rerun() re-runs this script every N seconds (auto-refresh loop).
  4. The dashboard always shows the latest slot states from the database.

Run this file with:
    streamlit run app.py
─────────────────────────────────────────────────────────────────────────────
"""

import time
from datetime import datetime
import streamlit as st

# ── Phase 3: Import database functions from parking_db.py ─────────────────────
# init_parking_db() → creates the table if it doesn't exist (safe always)
# seed_slots()      → inserts 12 default slots only if table is empty
# get_all_slots()   → SELECT * FROM parking_slots → list of dicts
# get_stats()       → {total, available, occupied, reserved} counts
from parking_db import (
    init_parking_db,
    seed_slots,
    get_all_slots,
    get_stats,
    STATUS_AVAILABLE,
    STATUS_OCCUPIED,
    STATUS_RESERVED,
)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 ─ PAGE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
# st.set_page_config() MUST be the very first Streamlit call in the script.
# It controls the browser tab title, the favicon icon, and the page layout.
# layout="wide" makes the content span the full browser width.
st.set_page_config(
    page_title="Smart Parking System",
    page_icon="🅿️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 ─ CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
# Keeping all magic numbers in one place makes the code easier to tweak.
# In Phase 2 these will be moved to config/settings.py.

GRID_COLUMNS    = 4    # How many slot cards per row in the grid
REFRESH_SECONDS = 5    # Default auto-refresh interval in seconds


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 ─ CUSTOM CSS
# ══════════════════════════════════════════════════════════════════════════════
# Streamlit has limited built-in styling. We inject raw CSS using
# st.markdown(..., unsafe_allow_html=True) to control colors, fonts,
# card styles, and hover animations beyond what Streamlit normally allows.

def apply_styles() -> None:
    """Injects custom CSS into the Streamlit page for premium styling."""
    st.markdown("""
    <style>

    /* ── Google Font Import ─────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

    /* ── Global Reset ───────────────────────────────────────────── */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .stApp {
        background-color: #0b1120;
        color: #f1f5f9;
    }

    /* ── Page Header Banner ─────────────────────────────────────── */
    .header-container {
        background: linear-gradient(135deg, #0f2444 0%, #0b1120 100%);
        border: 1px solid #1e40af44;
        border-radius: 20px;
        padding: 32px 24px;
        text-align: center;
        margin-bottom: 8px;
    }
    .header-title {
        font-size: 2.6rem;
        font-weight: 900;
        color: #f1f5f9;
        letter-spacing: -0.5px;
        margin: 0;
    }
    .header-subtitle {
        color: #64748b;
        font-size: 1rem;
        margin-top: 6px;
        font-weight: 500;
    }
    .header-badge {
        display: inline-block;
        background: #172554;
        color: #93c5fd;
        padding: 5px 18px;
        border-radius: 99px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-top: 14px;
        letter-spacing: 0.4px;
        border: 1px solid #1e40af55;
    }

    /* ── Stats Cards ─────────────────────────────────────────────── */
    .stats-card {
        background: #131f35;
        border: 1px solid #1e293b;
        border-radius: 16px;
        padding: 24px 16px;
        text-align: center;
        box-shadow: 0 6px 24px rgba(0,0,0,0.5);
    }
    .stats-icon  { font-size: 30px; margin-bottom: 4px; }
    .stats-value { font-size: 2.6rem; font-weight: 900; margin: 6px 0 4px; line-height: 1; }
    .stats-label {
        font-size: 0.7rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-weight: 600;
    }

    /* ── Slot Cards ──────────────────────────────────────────────── */
    .slot-card {
        border-radius: 14px;
        padding: 20px 8px;
        text-align: center;
        margin-bottom: 10px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.4);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        cursor: default;
    }
    .slot-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    }
    .slot-available {
        background: linear-gradient(145deg, #14532d, #16a34a);
        border: 1px solid #22c55e44;
    }
    .slot-occupied {
        background: linear-gradient(145deg, #7f1d1d, #dc2626);
        border: 1px solid #f8717144;
    }
    /* Phase 3: Reserved slot — dark grey/slate */
    .slot-reserved {
        background: linear-gradient(145deg, #0f172a, #1e293b);
        border: 1px solid #33415544;
    }
    .slot-id {
        font-size: 1.2rem;
        font-weight: 800;
        color: #ffffff;
        margin-bottom: 6px;
    }
    .slot-status-text {
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.8px;
        opacity: 0.88;
        color: #ffffff;
    }
    .slot-vehicle-num {
        font-size: 0.6rem;
        color: #ffffff99;
        margin-top: 4px;
        font-family: monospace;
        font-weight: 600;
    }

    /* ── Section Label ───────────────────────────────────────────── */
    .section-label {
        font-size: 0.72rem;
        font-weight: 700;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 2px;
        margin-bottom: 16px;
        margin-top: 4px;
    }

    /* ── Progress Bar (occupancy) ────────────────────────────────── */
    .occ-bar-bg {
        background: #1e293b;
        border-radius: 99px;
        height: 10px;
        margin-top: 16px;
        overflow: hidden;
    }
    .occ-bar-fill {
        height: 10px;
        border-radius: 99px;
        transition: width 0.4s ease;
    }

    /* ── Footer ──────────────────────────────────────────────────── */
    .footer {
        text-align: center;
        color: #1e293b;
        font-size: 0.76rem;
        margin-top: 36px;
        padding-top: 16px;
        border-top: 1px solid #1a2540;
    }

    /* ── Sidebar Overrides ───────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background-color: #0d1829 !important;
    }

    </style>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 ─ DATABASE DATA LOADER  (Phase 3 — replaces generate_slots)
# ══════════════════════════════════════════════════════════════════════════════
# Phase 3 replaces the random simulation with real data from parking.db.
#
# load_slots_from_db() calls get_all_slots() which runs:
#   SELECT * FROM parking_slots ORDER BY slot_row, slot_number
# and returns a list of dicts from the database.
#
# We then convert each DB row into the format the UI cards expect:
#   DB dict  →  {'slot_id': 'A1', 'status': 'occupied', 'vehicle_number': 'MH01AB'}
#   UI dict  →  {'id': 'A1', 'occupied': True, 'reserved': False, 'vehicle': 'MH01AB'}

def load_slots_from_db() -> list:
    """
    Reads ALL parking slot statuses from parking.db and converts them
    into the dictionary format expected by the UI rendering functions.

    WHY a conversion step?
      The database stores status as TEXT strings:
        'available', 'occupied', 'reserved'
      The original UI functions use boolean flags (occupied: True/False).
      This function bridges the two formats cleanly.

    Returns:
        list of dicts, each with:
          'id'       (str)  : Slot label, e.g. 'A1', 'B3'
          'status'   (str)  : Raw DB status: 'available'|'occupied'|'reserved'
          'occupied' (bool) : True only if status == 'occupied'
          'reserved' (bool) : True only if status == 'reserved'
          'vehicle'  (str)  : Vehicle number plate, or empty string

    Example:
        [
            {'id': 'A1', 'status': 'occupied',  'occupied': True,  'reserved': False, 'vehicle': 'MH01AB1234'},
            {'id': 'A2', 'status': 'available', 'occupied': False, 'reserved': False, 'vehicle': ''},
            {'id': 'A3', 'status': 'reserved',  'occupied': False, 'reserved': True,  'vehicle': ''},
        ]
    """
    # Step 1: Fetch raw rows from SQLite (each row is a dict from parking_db.py)
    raw_slots = get_all_slots()

    # Step 2: Convert DB format → UI format
    ui_slots = []
    for s in raw_slots:
        status = s.get("status", STATUS_AVAILABLE)
        ui_slots.append({
            "id"      : s["slot_id"],
            "status"  : status,
            "occupied": status == STATUS_OCCUPIED,   # True only if occupied
            "reserved": status == STATUS_RESERVED,   # True only if reserved
            "vehicle" : s.get("vehicle_number") or "",
        })

    return ui_slots


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 ─ SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
# The sidebar holds user controls so they don't clutter the main dashboard.
# Streamlit's slider and toggle widgets return their current value every
# time the user interacts — the whole script re-runs automatically.

def render_sidebar(stats: dict) -> tuple:
    """
    Renders the sidebar with interactive controls and live DB stats.

    Parameters:
        stats (dict): Live counts from get_stats() — used to show breakdown.

    Returns:
        refresh_interval (int)  : Auto-refresh delay in seconds.
        auto_refresh     (bool) : Whether auto-refresh is enabled.
    """
    with st.sidebar:
        st.markdown("## ⚙️ Controls")
        st.divider()

        # Phase 3: Show live database breakdown at the top of the sidebar
        st.markdown("### 📊 Live DB Counts")
        st.markdown(f"""
        <div style="background:#0e1c33;border:1px solid #1a3058;border-radius:12px;padding:14px 16px;">
            <div style="display:flex;justify-content:space-between;padding:5px 0;font-size:0.82rem;border-bottom:1px solid #0d1f3c;">
                <span style="color:#4a6080;font-weight:600;">🟢 Available</span>
                <span style="color:#4ade80;font-weight:700;">{stats.get('available', 0)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:5px 0;font-size:0.82rem;border-bottom:1px solid #0d1f3c;">
                <span style="color:#4a6080;font-weight:600;">🔴 Occupied</span>
                <span style="color:#f87171;font-weight:700;">{stats.get('occupied', 0)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:5px 0;font-size:0.82rem;border-bottom:1px solid #0d1f3c;">
                <span style="color:#4a6080;font-weight:600;">⚫ Reserved</span>
                <span style="color:#94a3b8;font-weight:700;">{stats.get('reserved', 0)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:5px 0;font-size:0.82rem;">
                <span style="color:#4a6080;font-weight:600;">🏢 Total</span>
                <span style="color:#c8daf5;font-weight:700;">{stats.get('total', 0)}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        refresh_interval = st.slider(
            label="⏱️ Refresh Every (seconds)",
            min_value=2,
            max_value=30,
            value=REFRESH_SECONDS,
            step=1,
            help="How often the dashboard re-queries parking.db for fresh slot data.",
        )

        auto_refresh = st.toggle("🔄 Auto Refresh", value=True)

        st.divider()
        st.markdown("### 🗺️ Legend")
        st.markdown("🟢 **Green**  — Available")
        st.markdown("🔴 **Red**    — Occupied")
        st.markdown("⚫ **Grey**   — Reserved")

        st.divider()
        st.markdown("### ℹ️ Mode")
        st.success(
            "**Live Database Mode** ✅\n\n"
            "Slot data is read directly from `parking.db`.\n\n"
            "Run `detection_engine.py` in a separate terminal "
            "to push real-time AI detection results here.",
            icon="🤖",
        )

        st.divider()
        st.markdown("### 🗄️ Data Source")
        st.code("parking.db  →  parking_slots", language="text")
        st.caption(f"Last read: {datetime.now().strftime('%I:%M:%S %p')}")

    return refresh_interval, auto_refresh


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 ─ HEADER
# ══════════════════════════════════════════════════════════════════════════════
# Pure HTML rendered inside Streamlit.
# The timestamp updates on every refresh to give a "live" feeling.

def render_header() -> None:
    """Renders the top banner with title, subtitle, and live timestamp."""
    timestamp = datetime.now().strftime("%d %b %Y  •  %I:%M:%S %p")
    st.markdown(f"""
    <div class="header-container">
        <div class="header-title">🅿️ Smart Parking System</div>
        <div class="header-subtitle">AI-Based Slot Detection &amp; Navigation Dashboard</div>
        <div class="header-badge">🟢 LIVE — SQLite Database Mode &nbsp;•&nbsp; {timestamp}</div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 ─ STATS CARDS
# ══════════════════════════════════════════════════════════════════════════════
# Four metric cards shown in a horizontal row.
# We calculate the values from the slots list — no hardcoding.

def render_stats(slots: list) -> None:
    """
    Renders 4 summary stat cards using LIVE data from parking.db.

    Phase 3 change:
      Now counts 'reserved' slots separately instead of treating
      everything as occupied vs available.

    Stats shown:
      ● Total Slots    (blue)
      ● Available      (green)
      ● Occupied       (red)
      ● Occupancy Rate (color-coded: green → yellow → red)

    Parameters:
        slots (list): The list of UI slot dicts from load_slots_from_db().
                      Each dict has 'occupied' (bool) and 'reserved' (bool).
    """
    total     = len(slots)
    occupied  = sum(1 for s in slots if s["occupied"])    # status == 'occupied'
    reserved  = sum(1 for s in slots if s["reserved"])    # status == 'reserved'
    available = total - occupied - reserved                 # everything else

    # Occupancy rate counts only genuinely occupied (not reserved) slots
    rate = round((occupied / total) * 100) if total > 0 else 0

    # Pick a color for the occupancy rate: green < 50%, yellow < 75%, red ≥ 75%
    if rate >= 75:
        rate_color = "#f87171"   # red
    elif rate >= 50:
        rate_color = "#fbbf24"   # yellow
    else:
        rate_color = "#4ade80"   # green

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="stats-card">
            <div class="stats-icon">🏢</div>
            <div class="stats-value" style="color:#60a5fa;">{total}</div>
            <div class="stats-label">Total Slots</div>
        </div>""", unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="stats-card">
            <div class="stats-icon">✅</div>
            <div class="stats-value" style="color:#4ade80;">{available}</div>
            <div class="stats-label">Available</div>
        </div>""", unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="stats-card">
            <div class="stats-icon">🚗</div>
            <div class="stats-value" style="color:#f87171;">{occupied}</div>
            <div class="stats-label">Occupied</div>
        </div>""", unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="stats-card">
            <div class="stats-icon">📊</div>
            <div class="stats-value" style="color:{rate_color};">{rate}%</div>
            <div class="stats-label">Occupancy Rate</div>
        </div>""", unsafe_allow_html=True)

    # Occupancy progress bar
    st.markdown(f"""
    <div class="occ-bar-bg">
        <div class="occ-bar-fill"
             style="width:{rate}%; background:{rate_color};"></div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8 ─ PARKING GRID
# ══════════════════════════════════════════════════════════════════════════════
# The main visual: a grid of colored cards, one per slot.
# We split the flat list into rows of GRID_COLUMNS using list slicing,
# then use st.columns() to place cards side by side.

def render_grid(slots: list) -> None:
    """
    Renders the parking bay grid with LIVE data from parking.db.

    Phase 3 changes:
      - Handles three statuses from DB: available, occupied, reserved.
      - Shows vehicle number plate on occupied cards (if available in DB).
      - Adds a 'drive lane' divider between rows for a realistic layout.

    Card colours:
      🟢 Green  → available  (slot is free)
      🔴 Red    → occupied   (vehicle detected / parked)
      ⚫ Grey   → reserved   (pre-booked / blocked)

    Parameters:
        slots (list): The list of UI slot dicts from load_slots_from_db().
                      Each dict has 'status', 'occupied', 'reserved', 'vehicle'.
    """
    st.markdown('<div class="section-label">🗺️ Parking Bay Overview — Live from parking.db</div>',
                unsafe_allow_html=True)

    # Split flat list into rows of GRID_COLUMNS each
    # e.g. 12 slots → [[A1,A2,A3,A4], [B1,B2,B3,B4], [C1,C2,C3,C4]]
    rows = [slots[i : i + GRID_COLUMNS] for i in range(0, len(slots), GRID_COLUMNS)]

    for row_idx, row in enumerate(rows):
        # Add a visual drive lane divider between rows (not before first row)
        if row_idx > 0:
            st.markdown(
                '<div style="background:#080f1e;border-top:1px dashed #1a3058;'
                'border-bottom:1px dashed #1a3058;text-align:center;padding:5px 0;'
                'font-size:0.62rem;color:#1e3a5f;font-weight:700;letter-spacing:3px;'
                'margin:6px 0;">─── 🚗 DRIVE LANE ───</div>',
                unsafe_allow_html=True,
            )

        cols = st.columns(GRID_COLUMNS)
        for col_widget, slot in zip(cols, row):

            # ── Determine card colour, icon, and label based on DB status ──────
            if slot["occupied"]:
                css   = "slot-occupied"
                icon  = "🔴"
                label = "OCCUPIED"
                # Show vehicle number if present in the database
                vehicle_html = (
                    f'<div class="slot-vehicle-num">🚗 {slot["vehicle"]}</div>'
                    if slot["vehicle"] else ""
                )
            elif slot["reserved"]:
                css   = "slot-reserved"
                icon  = "⚫"
                label = "RESERVED"
                vehicle_html = '<div class="slot-vehicle-num">🔒 PRE-BOOKED</div>'
            else:   # available
                css   = "slot-available"
                icon  = "🟢"
                label = "AVAILABLE"
                vehicle_html = ""

            with col_widget:
                st.markdown(f"""
                <div class="slot-card {css}">
                    <div style="font-size:1.4rem;">{icon}</div>
                    <div class="slot-id">🅿 {slot["id"]}</div>
                    <div class="slot-status-text">{label}</div>
                    {vehicle_html}
                </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 9 ─ SLOT TABLE
# ══════════════════════════════════════════════════════════════════════════════
# A collapsible data table listing every slot and its status.
# Useful for a quick textual overview and easy to explain in a viva.

def render_table(slots: list) -> None:
    """
    Shows an expandable table with all slot data — live from parking.db.

    Phase 3 change:
      Now includes a 'Vehicle No.' column and handles 'reserved' status.
      The caption shows the DB file name and last-read timestamp,
      proving to the viva examiner that data comes from SQLite.

    Parameters:
        slots (list): The list of UI slot dicts from load_slots_from_db().
    """
    with st.expander("📋 View Raw Slot Data (Live from parking.db)", expanded=False):

        def status_label(s):
            if s["occupied"]: return "🔴 Occupied"
            if s["reserved"]: return "⚫ Reserved"
            return "🟢 Available"

        table_data = {
            "Slot ID"    : [s["id"]           for s in slots],
            "Status"     : [status_label(s)    for s in slots],
            "Vehicle No.": [s["vehicle"] or "—" for s in slots],
        }
        st.dataframe(
            table_data,
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            f"📁 Source: parking.db → parking_slots table  •  "
            f"{len(slots)} slot(s)  •  "
            f"Read at {datetime.now().strftime('%I:%M:%S %p')}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 10 ─ FOOTER
# ══════════════════════════════════════════════════════════════════════════════

def render_footer() -> None:
    """Renders a minimal footer at the bottom of the page."""
    st.markdown("""
    <div class="footer">
        🅿️ Smart Parking System &nbsp;|&nbsp;
        Phase 3 — Live SQLite Mode &nbsp;|&nbsp;
        Python · Streamlit · OpenCV · YOLOv8 · SQLite
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 11 ─ MAIN  (Orchestrator)
# ══════════════════════════════════════════════════════════════════════════════
# main() calls every render function in the correct order.
# Think of it as the "director" — it doesn't do any work itself,
# it just decides WHAT to show and WHEN.
#
# Auto-refresh works like this:
#   1. time.sleep(N) pauses the script for N seconds.
#   2. st.rerun() tells Streamlit to restart the script from the top.
#   3. The restart calls generate_slots() again → new random data → UI updates.
#   In Phase 2, step 3 will query the database instead of using random data.

def main() -> None:
    """
    Entry point — assembles the full Phase 3 live dashboard.

    Phase 3 execution order:
      1.  Inject CSS styles.
      2.  Ensure parking.db + parking_slots table exist (safe, non-destructive).
      3.  Seed 12 default slots IF the table is empty (first run only).
      4.  Fetch live stats from the DB (for the sidebar breakdown panel).
      5.  Render sidebar (returns refresh settings).
      6.  Render header.
      7.  Load ALL slots from parking.db → convert to UI format.
      8.  Render stats cards + occupancy bar.
      9.  Render parking grid (colour-coded by live DB status).
      10. Render raw data table (proves data comes from SQLite).
      11. Render footer.
      12. Auto-refresh: sleep N seconds → st.rerun() → go back to step 2.
    """

    # ── Step 1: CSS ────────────────────────────────────────────────────────────
    apply_styles()

    # ── Step 2 & 3: Ensure DB is ready, seed if empty ─────────────────────────
    # init_parking_db() uses CREATE TABLE IF NOT EXISTS → completely safe to call
    # on every refresh. It will NEVER overwrite or reset existing data.
    # seed_slots() checks if rows already exist before inserting — also safe.
    init_parking_db()
    seed_slots(total_rows=3, cols=4)

    # ── Step 4: Fetch live stats (needed by sidebar) ────────────────────────────
    # get_stats() runs: SELECT status, COUNT(*) FROM parking_slots GROUP BY status
    stats = get_stats()

    # ── Step 5: Sidebar ────────────────────────────────────────────────────────
    refresh_interval, auto_refresh = render_sidebar(stats)

    # ── Step 6: Header ────────────────────────────────────────────────────────
    render_header()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 7: Load LIVE slot data from parking.db ────────────────────────────
    # This is the CORE Phase 3 change.
    # get_all_slots() runs: SELECT * FROM parking_slots ORDER BY slot_row, slot_number
    # load_slots_from_db() converts DB dicts → UI dicts (adds 'occupied', 'reserved' booleans)
    slots = load_slots_from_db()

    # ── Step 8: Stats row ──────────────────────────────────────────────────────
    render_stats(slots)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 9: Parking grid ───────────────────────────────────────────────────
    render_grid(slots)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 10: Raw data table (collapsible) ──────────────────────────────────
    render_table(slots)

    # ── Step 11: Footer ────────────────────────────────────────────────────────
    render_footer()

    # ── Step 12: Auto-refresh ─────────────────────────────────────────────────
    # How it works:
    #   a. time.sleep(N)  → pause the script for N seconds
    #   b. st.rerun()     → Streamlit restarts the script from line 1
    #   c. On restart, load_slots_from_db() re-queries parking.db
    #   d. If detection_engine.py updated the DB during the sleep,
    #      the new statuses will appear on screen immediately.
    #
    # This creates a smooth live update loop with zero CPU waste during sleep.
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SCRIPT GUARD
# ══════════════════════════════════════════════════════════════════════════════
# This ensures main() only runs when the file is executed directly
# (via `streamlit run app.py`), not when imported as a module.
if __name__ == "__main__":
    main()
