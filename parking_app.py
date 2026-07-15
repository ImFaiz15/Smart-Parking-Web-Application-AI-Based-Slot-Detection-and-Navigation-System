"""
parking_app.py  –  Smart Parking Dashboard (Module 3)
─────────────────────────────────────────────────────────────────────────────
This is the main Streamlit UI for the Smart Parking Dashboard.

What it does:
  1. On first run, auto-seeds the SQLite database with simulated slot data.
  2. Reads all parking slot data from the SQLite database.
  3. Displays a live-updating parking dashboard with:
       - Stats cards: Total, Available, Occupied, Reserved
       - Occupancy progress bar
       - Visual parking grid (colour-coded cards per slot)
       - Sidebar filters, controls, and slot breakdown
       - Simulate button to randomize slot statuses
       - Auto-refresh toggle

Colour coding:
  🟢  Green  →  Available   (empty slot, can park here)
  🔴  Red    →  Occupied    (vehicle detected / parked)
  ⚫  Grey   →  Reserved    (blocked / pre-booked)

Run with:
  streamlit run parking_app.py
─────────────────────────────────────────────────────────────────────────────
"""

import time
import streamlit as st
from datetime import datetime

# Import all database functions from parking_db.py
from parking_db import (
    init_parking_db,
    seed_slots,
    get_all_slots,
    get_slots_by_status,
    get_stats,
    randomize_slots,
    STATUS_AVAILABLE,
    STATUS_OCCUPIED,
    STATUS_RESERVED,
)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 ─ PAGE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
# Must be the FIRST Streamlit call in the script.

st.set_page_config(
    page_title="Smart Parking – Dashboard",
    page_icon="🅿️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 ─ DATABASE BOOTSTRAP
# ══════════════════════════════════════════════════════════════════════════════
# These two calls run every time Streamlit restarts the script.
# init_parking_db() → safe: uses CREATE TABLE IF NOT EXISTS (no overwrite).
# seed_slots()      → safe: checks if data already exists before inserting.
# This ensures the app always has data to display, even on first run.

init_parking_db()
seed_slots(total_rows=3, cols=4)   # Creates 12 slots across 3 rows (A, B, C)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 ─ CUSTOM CSS
# ══════════════════════════════════════════════════════════════════════════════

def apply_styles() -> None:
    """
    Injects premium dark-theme CSS for the parking dashboard.
    Consistent with the auth_app.py design language.
    """
    st.markdown("""
    <style>

    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

    /* ── Global ─────────────────────────────────────────────────── */
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp {
        background: radial-gradient(ellipse at top, #0d1f3c 0%, #0b1120 60%, #050c1a 100%);
    }
    #MainMenu, footer, header { visibility: hidden; }

    /* ── Page Header ────────────────────────────────────────────── */
    .page-header {
        background: linear-gradient(135deg, #0f2444 0%, #0b1120 100%);
        border: 1px solid rgba(59,130,246,0.15);
        border-radius: 20px;
        padding: 28px 32px;
        margin-bottom: 24px;
    }
    .page-title    { font-size: 2rem; font-weight: 900; color: #f0f6ff; margin: 0; letter-spacing: -0.3px; }
    .page-subtitle { font-size: 0.85rem; color: #4a6080; margin-top: 4px; }
    .page-badge {
        display: inline-block;
        background: #0c2044;
        border: 1px solid #1e40af44;
        color: #60a5fa;
        padding: 4px 14px;
        border-radius: 99px;
        font-size: 0.72rem;
        font-weight: 700;
        margin-top: 12px;
        letter-spacing: 0.5px;
    }

    /* ── Stats Cards ─────────────────────────────────────────────── */
    .stat-card {
        background: #0e1c33;
        border: 1px solid #1a3058;
        border-radius: 16px;
        padding: 22px 16px;
        text-align: center;
        box-shadow: 0 6px 24px rgba(0,0,0,0.5);
        margin-bottom: 8px;
        transition: border-color 0.2s ease;
    }
    .stat-card:hover { border-color: #2563eb44; }
    .stat-icon  { font-size: 26px; }
    .stat-value { font-size: 2.5rem; font-weight: 900; margin: 6px 0 4px; line-height: 1; }
    .stat-label { font-size: 0.68rem; color: #4a6080; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 700; }

    /* ── Occupancy Bar ───────────────────────────────────────────── */
    .occ-wrap  { margin: 6px 0 20px; }
    .occ-label { font-size: 0.72rem; color: #4a6080; font-weight: 600; margin-bottom: 6px; }
    .occ-track { background: #0e1c33; border-radius: 99px; height: 8px; overflow: hidden; border: 1px solid #1a3058; }
    .occ-fill  { height: 8px; border-radius: 99px; transition: width 0.5s ease; }

    /* ── Section Label ───────────────────────────────────────────── */
    .sec-label {
        font-size: 0.68rem; font-weight: 700;
        color: #3b6ea5; text-transform: uppercase;
        letter-spacing: 2px; margin-bottom: 16px; margin-top: 4px;
    }

    /* ── Road Lane Divider ───────────────────────────────────────── */
    .lane {
        background: #0b1829;
        border-top: 1px dashed #1a3058;
        border-bottom: 1px dashed #1a3058;
        text-align: center;
        padding: 6px 0;
        font-size: 0.65rem;
        color: #243554;
        font-weight: 700;
        letter-spacing: 3px;
        margin: 8px 0;
    }

    /* ── Row Label ───────────────────────────────────────────────── */
    .row-label {
        display: inline-block;
        background: #0e1c33;
        border: 1px solid #1a3058;
        color: #3b6ea5;
        font-size: 0.78rem;
        font-weight: 800;
        padding: 4px 10px;
        border-radius: 8px;
        margin-bottom: 10px;
        letter-spacing: 1px;
    }

    /* ── Slot Cards ──────────────────────────────────────────────── */
    .slot-card {
        border-radius: 14px;
        padding: 16px 8px 14px;
        text-align: center;
        margin-bottom: 10px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.5);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        cursor: default;
        min-height: 100px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }
    .slot-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 28px rgba(0,0,0,0.6);
    }

    /* Available: Green */
    .slot-available {
        background: linear-gradient(145deg, #052e16, #14532d);
        border: 1px solid #16a34a44;
    }
    /* Occupied: Red */
    .slot-occupied {
        background: linear-gradient(145deg, #450a0a, #7f1d1d);
        border: 1px solid #dc262644;
    }
    /* Reserved: Dark grey/blue */
    .slot-reserved {
        background: linear-gradient(145deg, #0f172a, #1e293b);
        border: 1px solid #33415544;
    }

    .slot-id    { font-size: 1.1rem; font-weight: 800; color: #ffffff; margin-bottom: 4px; }
    .slot-icon  { font-size: 1.6rem; margin-bottom: 4px; line-height: 1; }
    .slot-status-txt {
        font-size: 0.62rem; font-weight: 700;
        letter-spacing: 0.8px; text-transform: uppercase; color: #ffffffcc;
    }
    .slot-vehicle {
        font-size: 0.6rem; color: #ffffff88;
        margin-top: 4px; font-weight: 600;
        font-family: monospace;
    }

    /* ── Sidebar ─────────────────────────────────────────────────── */
    [data-testid="stSidebar"] { background: #080f1e !important; }

    /* ── Filter Buttons (radio) ──────────────────────────────────── */
    [data-testid="stRadio"] label {
        font-size: 0.82rem !important;
        color: #c8daf5 !important;
    }

    /* ── Simulate Button ─────────────────────────────────────────── */
    .stButton > button {
        background: linear-gradient(135deg, #1d4ed8, #3b82f6);
        color: #fff;
        border: none;
        border-radius: 10px;
        padding: 10px 0;
        font-size: 0.88rem;
        font-weight: 700;
        width: 100%;
        transition: all 0.2s ease;
        box-shadow: 0 4px 16px rgba(59,130,246,0.3);
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #1e40af, #2563eb);
        transform: translateY(-2px);
    }

    /* ── Breakdown table in sidebar ──────────────────────────────── */
    .breakdown-row {
        display: flex; justify-content: space-between;
        padding: 7px 0; border-bottom: 1px solid #0e1c33;
        font-size: 0.82rem;
    }
    .breakdown-row:last-child { border-bottom: none; }
    .bk-label { color: #4a6080; font-weight: 600; }
    .bk-value { color: #c8daf5; font-weight: 700; }

    /* ── Footer ──────────────────────────────────────────────────── */
    .footer {
        text-align: center; color: #1a3058;
        font-size: 0.72rem; margin-top: 32px;
        padding-top: 16px; border-top: 1px solid #0e1c33;
    }

    </style>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 ─ HEADER
# ══════════════════════════════════════════════════════════════════════════════

def render_header() -> None:
    """
    Renders the top banner with the dashboard title and a live timestamp.
    The timestamp updates on every auto-refresh to show the system is live.
    """
    now = datetime.now().strftime("%d %b %Y  •  %I:%M:%S %p")

    st.markdown(f"""
    <div class="page-header">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
            <div>
                <p class="page-title">🅿️ Parking Monitor</p>
                <p class="page-subtitle">Real-time slot availability — Smart Parking System</p>
                <span class="page-badge">🟡 SIMULATION MODE &nbsp;•&nbsp; {now}</span>
            </div>
            <div style="text-align:right;">
                <div style="font-size:3.5rem;">🏢</div>
                <div style="font-size:0.7rem; color:#243554; font-weight:700;">CITY PARKING LOT</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 ─ STATS CARDS
# ══════════════════════════════════════════════════════════════════════════════

def render_stats(stats: dict) -> None:
    """
    Displays 4 summary metric cards in a horizontal row.

    Cards:
      - Total Slots    (blue)
      - Available      (green)
      - Occupied       (red)
      - Reserved       (grey)

    Also displays a colour-coded occupancy progress bar below the cards.

    Parameters:
        stats (dict): Output of get_stats() from parking_db.py.
                      Keys: 'total', 'available', 'occupied', 'reserved'.
    """
    total     = stats["total"]
    available = stats[STATUS_AVAILABLE]
    occupied  = stats[STATUS_OCCUPIED]
    reserved  = stats[STATUS_RESERVED]

    # Occupancy rate = (occupied / total) × 100
    occ_rate  = round((occupied / total) * 100) if total > 0 else 0

    # Pick colour for occupancy bar based on how full the lot is
    if occ_rate >= 80:
        bar_color = "#ef4444"   # Red — nearly full
    elif occ_rate >= 50:
        bar_color = "#f59e0b"   # Amber — getting busy
    else:
        bar_color = "#22c55e"   # Green — plenty of space

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-icon">🏢</div>
            <div class="stat-value" style="color:#60a5fa;">{total}</div>
            <div class="stat-label">Total Slots</div>
        </div>""", unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-icon">✅</div>
            <div class="stat-value" style="color:#4ade80;">{available}</div>
            <div class="stat-label">Available</div>
        </div>""", unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-icon">🚗</div>
            <div class="stat-value" style="color:#f87171;">{occupied}</div>
            <div class="stat-label">Occupied</div>
        </div>""", unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-icon">🔒</div>
            <div class="stat-value" style="color:#94a3b8;">{reserved}</div>
            <div class="stat-label">Reserved</div>
        </div>""", unsafe_allow_html=True)

    # ── Occupancy progress bar ─────────────────────────────────────────────────
    st.markdown(f"""
    <div class="occ-wrap">
        <div class="occ-label">🔆 Occupancy Rate: {occ_rate}%</div>
        <div class="occ-track">
            <div class="occ-fill" style="width:{occ_rate}%; background:{bar_color};"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 ─ PARKING GRID
# ══════════════════════════════════════════════════════════════════════════════

def render_grid(slots: list, cols: int = 4) -> None:
    """
    Renders the visual parking bay grid with colour-coded slot cards.

    Layout:
      Slots are grouped by their 'slot_row' value (A, B, C...).
      Each group is rendered as a horizontal row of cards.
      A "lane" divider is shown between rows to look like a real parking lot.

    Colour coding:
      🟢 Green  → status = 'available'
      🔴 Red    → status = 'occupied'   (shows vehicle plate if available)
      ⚫ Grey   → status = 'reserved'

    Parameters:
        slots (list): List of slot dicts from get_all_slots() or get_slots_by_status().
        cols  (int) : Number of columns in the grid (matches GRID_COLS in parking_db.py).
    """
    if not slots:
        st.info("No slots to display for the selected filter.")
        return

    st.markdown('<div class="sec-label">🗺️ Parking Bay Layout</div>', unsafe_allow_html=True)

    # ── Group slots by row letter ─────────────────────────────────────────────
    # We create a dictionary: {'A': [slot1, slot2...], 'B': [...], ...}
    rows_dict: dict = {}
    for slot in slots:
        row = slot["slot_row"]
        if row not in rows_dict:
            rows_dict[row] = []
        rows_dict[row].append(slot)

    # ── Render each row ───────────────────────────────────────────────────────
    for row_idx, (row_letter, row_slots) in enumerate(rows_dict.items()):

        # Add a "lane" divider between rows (not before the first row)
        if row_idx > 0:
            st.markdown(
                '<div class="lane">─── 🚗 DRIVE LANE ───</div>',
                unsafe_allow_html=True
            )

        # Row label badge
        st.markdown(f'<span class="row-label">ROW {row_letter}</span>', unsafe_allow_html=True)

        # Create `cols` columns — one per parking slot in this row
        grid_cols = st.columns(cols)

        for col_idx, (col_widget, slot) in enumerate(zip(grid_cols, row_slots)):
            with col_widget:
                _render_slot_card(slot)

        # If this row has fewer slots than cols (e.g. filtered view), fill the gap
        # so the layout doesn't collapse awkwardly
        remaining = cols - len(row_slots)
        for _ in range(remaining):
            with grid_cols[cols - remaining]:
                st.empty()


def _render_slot_card(slot: dict) -> None:
    """
    Renders a single parking slot card.

    This is a private helper function (convention: prefix with _ means internal use).
    Called by render_grid() for each individual slot.

    Parameters:
        slot (dict): A slot dictionary from the database.
                     Keys: slot_id, slot_row, slot_number, status, vehicle_number, last_updated.
    """
    status = slot["status"]

    # ── Set CSS class, icon, and label based on status ────────────────────────
    if status == STATUS_AVAILABLE:
        css_class  = "slot-available"
        icon       = "🟢"
        label      = "AVAILABLE"
        vehicle_html = ""

    elif status == STATUS_OCCUPIED:
        css_class  = "slot-occupied"
        icon       = "🔴"
        label      = "OCCUPIED"
        # Show vehicle number if present
        veh = slot.get("vehicle_number") or ""
        vehicle_html = f'<div class="slot-vehicle">🚗 {veh}</div>' if veh else ""

    else:   # reserved
        css_class  = "slot-reserved"
        icon       = "⚫"
        label      = "RESERVED"
        vehicle_html = '<div class="slot-vehicle">🔒 PRE-BOOKED</div>'

    st.markdown(f"""
    <div class="slot-card {css_class}">
        <div class="slot-icon">{icon}</div>
        <div class="slot-id">🅿 {slot['slot_id']}</div>
        <div class="slot-status-txt">{label}</div>
        {vehicle_html}
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 ─ LEGEND
# ══════════════════════════════════════════════════════════════════════════════

def render_legend() -> None:
    """
    Displays a horizontal colour legend below the parking grid.
    Helps users understand what each card colour means at a glance.
    """
    st.markdown("""
    <div style="
        display: flex; gap: 28px; justify-content: center;
        padding: 14px 0; margin-top: 4px;
        border-top: 1px solid #0e1c33; border-bottom: 1px solid #0e1c33;
    ">
        <span style="font-size:0.8rem; color:#4ade80; font-weight:700;">🟢 Available — Park here</span>
        <span style="font-size:0.8rem; color:#f87171; font-weight:700;">🔴 Occupied — Vehicle present</span>
        <span style="font-size:0.8rem; color:#94a3b8; font-weight:700;">⚫ Reserved — Pre-booked</span>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8 ─ SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

def render_sidebar(stats: dict) -> tuple:
    """
    Renders the sidebar with:
      - Slot breakdown panel (how many of each type)
      - Filter selector (All / Available / Occupied / Reserved)
      - Auto-refresh controls
      - Simulate button

    Parameters:
        stats (dict): Live stats dict from get_stats().

    Returns:
        tuple:
          selected_filter  (str) : The status filter chosen by the user.
          auto_refresh     (bool): Whether auto-refresh is enabled.
          refresh_interval (int) : Seconds between refreshes.
    """
    with st.sidebar:
        st.markdown("## ⚙️ Dashboard Controls")
        st.divider()

        # ── Slot Breakdown ─────────────────────────────────────────────────────
        st.markdown("### 📊 Slot Breakdown")
        total     = stats["total"]
        available = stats[STATUS_AVAILABLE]
        occupied  = stats[STATUS_OCCUPIED]
        reserved  = stats[STATUS_RESERVED]

        def pct(n):
            return f"{round(n/total*100)}%" if total > 0 else "0%"

        st.markdown(f"""
        <div style="background:#0e1c33; border:1px solid #1a3058; border-radius:12px; padding:14px 16px;">
            <div class="breakdown-row">
                <span class="bk-label">🟢 Available</span>
                <span class="bk-value">{available} &nbsp;<span style="color:#243554">({pct(available)})</span></span>
            </div>
            <div class="breakdown-row">
                <span class="bk-label">🔴 Occupied</span>
                <span class="bk-value">{occupied} &nbsp;<span style="color:#243554">({pct(occupied)})</span></span>
            </div>
            <div class="breakdown-row">
                <span class="bk-label">⚫ Reserved</span>
                <span class="bk-value">{reserved} &nbsp;<span style="color:#243554">({pct(reserved)})</span></span>
            </div>
            <div class="breakdown-row" style="margin-top:8px; border-top:1px solid #1a3058; padding-top:10px;">
                <span class="bk-label" style="color:#4a6080">🏢 Total</span>
                <span class="bk-value">{total}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ── Filter selector ────────────────────────────────────────────────────
        # st.radio gives a set of mutually exclusive options (like radio buttons).
        # The user picks one and the grid filters accordingly.
        st.markdown("### 🔍 Filter Slots")
        filter_options = {
            "All Slots"          : "all",
            "🟢 Available Only"  : STATUS_AVAILABLE,
            "🔴 Occupied Only"   : STATUS_OCCUPIED,
            "⚫ Reserved Only"   : STATUS_RESERVED,
        }
        selected_label = st.radio(
            label="Show:",
            options=list(filter_options.keys()),
            index=0,
            label_visibility="collapsed",
        )
        selected_filter = filter_options[selected_label]

        st.divider()

        # ── Auto-refresh controls ──────────────────────────────────────────────
        st.markdown("### 🔄 Auto Refresh")
        auto_refresh = st.toggle("Enable Auto Refresh", value=True)

        refresh_interval = st.slider(
            label="Refresh every (seconds)",
            min_value=3,
            max_value=60,
            value=10,
            step=1,
            disabled=not auto_refresh,
        )

        st.divider()

        # ── Simulate button ────────────────────────────────────────────────────
        # When clicked, calls randomize_slots() which re-writes all statuses
        # in the SQLite database, then st.rerun() refreshes the whole dashboard.
        st.markdown("### 🎲 Simulation")
        st.caption("Click to randomly change slot statuses (simulates parking activity).")

        if st.button("🔀 Simulate Parking Change", use_container_width=True):
            randomize_slots()   # Re-randomizes ALL slots in the DB
            st.success("Slots updated!")
            time.sleep(0.5)
            st.rerun()          # Refresh page to show new data

    return selected_filter, auto_refresh, refresh_interval


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 9 ─ SLOT DETAILS EXPANDER
# ══════════════════════════════════════════════════════════════════════════════

def render_slot_table(slots: list) -> None:
    """
    Shows a collapsible table with all slot data in tabular format.

    This is useful during a viva to show the raw database output
    and prove the dashboard is genuinely reading from SQLite.

    Parameters:
        slots (list): The full list of slot dicts currently displayed.
    """
    with st.expander("📋 View Raw Slot Data (from SQLite)", expanded=False):
        if not slots:
            st.info("No slots to display.")
            return

        # Build column arrays for the dataframe
        table_data = {
            "Slot ID"       : [s["slot_id"]        for s in slots],
            "Row"           : [s["slot_row"]        for s in slots],
            "Number"        : [s["slot_number"]     for s in slots],
            "Status"        : [s["status"].upper()  for s in slots],
            "Vehicle No."   : [s["vehicle_number"] or "—" for s in slots],
            "Last Updated"  : [s["last_updated"]    for s in slots],
        }

        st.dataframe(
            table_data,
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            f"📁 Data source: parking.db (SQLite)  •  "
            f"{len(slots)} record(s) shown  •  "
            f"Refreshed at {datetime.now().strftime('%I:%M:%S %p')}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 10 ─ FOOTER
# ══════════════════════════════════════════════════════════════════════════════

def render_footer() -> None:
    """Renders a minimal footer."""
    st.markdown("""
    <div class="footer">
        🅿️ Smart Parking System &nbsp;|&nbsp;
        Module 3 – Parking Dashboard &nbsp;|&nbsp;
        Simulation Mode &nbsp;|&nbsp;
        Built with Python · Streamlit · SQLite
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 11 ─ MAIN  (Orchestrator)
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """
    Entry point — assembles the complete parking dashboard.

    Execution order:
      1.  Apply CSS styles
      2.  Fetch live stats from SQLite
      3.  Render sidebar (returns user selections)
      4.  Determine which slots to display based on filter
      5.  Render header
      6.  Render stats cards + occupancy bar
      7.  Render parking grid
      8.  Render colour legend
      9.  Render raw data table (collapsible)
      10. Render footer
      11. Auto-refresh: wait N seconds then st.rerun()
    """

    # ── Step 1: CSS ────────────────────────────────────────────────────────────
    apply_styles()

    # ── Step 2: Read live stats from SQLite ────────────────────────────────────
    stats = get_stats()

    # ── Step 3: Sidebar (returns user control values) ──────────────────────────
    selected_filter, auto_refresh, refresh_interval = render_sidebar(stats)

    # ── Step 4: Fetch slots based on filter ────────────────────────────────────
    # If "all" is selected, fetch everything.
    # Otherwise, pass the status string to filter the DB query.
    if selected_filter == "all":
        slots = get_all_slots()
    else:
        slots = get_slots_by_status(selected_filter)

    # ── Step 5: Header ─────────────────────────────────────────────────────────
    render_header()

    # ── Step 6: Stats cards ────────────────────────────────────────────────────
    render_stats(stats)

    # ── Step 7: Parking grid ───────────────────────────────────────────────────
    render_grid(slots, cols=4)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 8: Legend ─────────────────────────────────────────────────────────
    render_legend()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 9: Raw data table (collapsible) ───────────────────────────────────
    render_slot_table(slots)

    # ── Step 10: Footer ────────────────────────────────────────────────────────
    render_footer()

    # ── Step 11: Auto-refresh ──────────────────────────────────────────────────
    # Pauses the script for N seconds, then calls st.rerun() which restarts
    # the entire script from the top — re-reading fresh data from SQLite.
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SCRIPT GUARD
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()
