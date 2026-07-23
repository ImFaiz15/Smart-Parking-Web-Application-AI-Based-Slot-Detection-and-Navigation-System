"""
app.py  –  Smart Parking Web Application
─────────────────────────────────────────────────────────────────────────────
Main Streamlit dashboard.

Phase 1  →  Simulation Mode  (no AI, no database yet)
Phase 2  →  Will connect to YOLOv8 detection pipeline
Phase 3  →  Will read live data from SQLite database

Run this file with:
    streamlit run app.py
─────────────────────────────────────────────────────────────────────────────
"""

import time
import random
from datetime import datetime
import streamlit as st


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

TOTAL_SLOTS     = 12   # Default number of parking slots to display
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
# SECTION 4 ─ DATA SIMULATION
# ══════════════════════════════════════════════════════════════════════════════
# This function is the ONLY part that changes in Phase 2.
# Instead of random.choice(), it will read from the SQLite database
# (which is updated by the YOLOv8 detection pipeline).
#
# Each slot is a plain Python dictionary — simple and easy to understand.

def generate_slots(total: int) -> list:
    """
    Simulates parking slot data with random occupancy.

    Parameters:
        total  (int)  : Number of slots to generate.

    Returns:
        list of dicts : Each dict has keys → 'id' and 'occupied'.

    Example output:
        [
            {'id': 'A1', 'occupied': False},
            {'id': 'A2', 'occupied': True},
            ...
        ]
    """
    slots   = []
    letters = "ABCDEFGHIJ"   # Row labels — supports up to 10 rows

    for i in range(total):
        row    = letters[i // GRID_COLUMNS]   # e.g. 0-3 → 'A', 4-7 → 'B'
        col    = (i % GRID_COLUMNS) + 1       # e.g. 1, 2, 3, 4, 1, 2 ...
        slot_id = f"{row}{col}"               # e.g. 'A1', 'A2', 'B1'

        slots.append({
            "id"      : slot_id,
            "occupied": random.choice([True, False]),   # ← replaced by AI in Phase 2
        })

    return slots


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 ─ SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
# The sidebar holds user controls so they don't clutter the main dashboard.
# Streamlit's slider and toggle widgets return their current value every
# time the user interacts — the whole script re-runs automatically.

def render_sidebar() -> tuple:
    """
    Renders the sidebar with interactive controls.

    Returns:
        total_slots      (int)  : Number of slots chosen by the user.
        refresh_interval (int)  : Auto-refresh delay in seconds.
        auto_refresh     (bool) : Whether auto-refresh is enabled.
    """
    with st.sidebar:
        st.markdown("## ⚙️ Controls")
        st.divider()

        total_slots = st.slider(
            label="🅿️ Total Parking Slots",
            min_value=4,
            max_value=24,
            value=TOTAL_SLOTS,
            step=4,
            help="Drag to increase or decrease the number of simulated slots.",
        )

        refresh_interval = st.slider(
            label="⏱️ Refresh Every (seconds)",
            min_value=2,
            max_value=30,
            value=REFRESH_SECONDS,
            step=1,
            help="How often the dashboard reloads and re-randomizes slot data.",
        )

        auto_refresh = st.toggle("🔄 Auto Refresh", value=True)

        st.divider()
        st.markdown("### 🗺️ Legend")
        st.markdown("🟢 **Green** — Slot is free")
        st.markdown("🔴 **Red**   — Vehicle present")

        st.divider()
        st.markdown("### ℹ️ Mode")
        st.info(
            "**Simulation Mode**\n\n"
            "Slot data is randomly generated.\n\n"
            "Phase 2 will plug in live YOLOv8 "
            "detection output here.",
            icon="🤖",
        )

    return total_slots, refresh_interval, auto_refresh


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
        <div class="header-badge">🟡 SIMULATION MODE &nbsp;•&nbsp; {timestamp}</div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 ─ STATS CARDS
# ══════════════════════════════════════════════════════════════════════════════
# Four metric cards shown in a horizontal row.
# We calculate the values from the slots list — no hardcoding.

def render_stats(slots: list) -> None:
    """
    Renders 4 summary cards:
      ● Total Slots
      ● Available
      ● Occupied
      ● Occupancy Rate  (color-coded: green → yellow → red)

    Parameters:
        slots (list): The list of slot dicts from generate_slots().
    """
    total     = len(slots)
    occupied  = sum(1 for s in slots if s["occupied"])
    available = total - occupied
    rate      = round((occupied / total) * 100) if total > 0 else 0

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

    # Occupancy progress bar — visual indicator below the cards
    bar_color = rate_color
    st.markdown(f"""
    <div class="occ-bar-bg">
        <div class="occ-bar-fill"
             style="width:{rate}%; background:{bar_color};"></div>
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
    Renders the parking bay grid.

    Green card  → slot is available.
    Red card    → slot is occupied.

    Parameters:
        slots (list): The list of slot dicts from generate_slots().
    """
    st.markdown('<div class="section-label">🗺️ Parking Bay Overview</div>',
                unsafe_allow_html=True)

    # Split the flat list into sub-lists of GRID_COLUMNS each.
    # Example for 12 slots, 4 cols:
    #   [[A1,A2,A3,A4], [B1,B2,B3,B4], [C1,C2,C3,C4]]
    rows = [slots[i : i + GRID_COLUMNS] for i in range(0, len(slots), GRID_COLUMNS)]

    for row in rows:
        cols = st.columns(GRID_COLUMNS)
        for col_widget, slot in zip(cols, row):
            css   = "slot-occupied"  if slot["occupied"] else "slot-available"
            label = "🔴 OCCUPIED"    if slot["occupied"] else "🟢 AVAILABLE"

            with col_widget:
                st.markdown(f"""
                <div class="slot-card {css}">
                    <div class="slot-id">🅿 {slot["id"]}</div>
                    <div class="slot-status-text">{label}</div>
                </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 9 ─ SLOT TABLE
# ══════════════════════════════════════════════════════════════════════════════
# A collapsible data table listing every slot and its status.
# Useful for a quick textual overview and easy to explain in a viva.

def render_table(slots: list) -> None:
    """
    Shows an expandable table with all slot data.
    Collapsed by default so it doesn't crowd the main view.

    Parameters:
        slots (list): The list of slot dicts from generate_slots().
    """
    with st.expander("📋 View Full Slot Status Table", expanded=False):
        table_data = {
            "Slot ID" : [s["id"] for s in slots],
            "Status"  : ["🔴 Occupied" if s["occupied"] else "🟢 Available"
                         for s in slots],
        }
        st.dataframe(
            table_data,
            use_container_width=True,
            hide_index=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 10 ─ FOOTER
# ══════════════════════════════════════════════════════════════════════════════

def render_footer() -> None:
    """Renders a minimal footer at the bottom of the page."""
    st.markdown("""
    <div class="footer">
        Smart Parking System &nbsp;|&nbsp;
        Simulation Mode &nbsp;|&nbsp;
        Built with 🐍 Python · Streamlit · OpenCV · YOLOv8
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
    """Entry point — assembles the full dashboard."""

    # ── Step 1: Apply CSS ────────────────────────────────────────────
    apply_styles()

    # ── Step 2: Sidebar (returns user settings) ──────────────────────
    total_slots, refresh_interval, auto_refresh = render_sidebar()

    # ── Step 3: Header ───────────────────────────────────────────────
    render_header()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 4: Generate simulated data ──────────────────────────────
    slots = generate_slots(total_slots)

    # ── Step 5: Stats row ────────────────────────────────────────────
    render_stats(slots)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 6: Parking grid ─────────────────────────────────────────
    render_grid(slots)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 7: Data table (collapsible) ─────────────────────────────
    render_table(slots)

    # ── Step 8: Footer ───────────────────────────────────────────────
    render_footer()

    # ── Step 9: Auto-refresh ─────────────────────────────────────────
    # Only runs if the user has toggled auto-refresh ON in the sidebar.
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()   # Restarts the entire script → fresh data → UI updates


# ══════════════════════════════════════════════════════════════════════════════
# SCRIPT GUARD
# ══════════════════════════════════════════════════════════════════════════════
# This ensures main() only runs when the file is executed directly
# (via `streamlit run app.py`), not when imported as a module.
if __name__ == "__main__":
    main()
