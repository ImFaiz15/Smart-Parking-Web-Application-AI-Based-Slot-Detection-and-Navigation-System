# -*- coding: utf-8 -*-
"""
app.py - Smart Parking Web Application (Multi-Page Dashboard)
=============================================================================
3-Section Layout: Left Navigation Sidebar | Center Dashboard | Right Panel

Pages:
  - Dashboard:     Live zone cards, metrics, digital twin slot map
  - Check History: Recent zone occupancy logs from parking.db
  - Reserve Slot:  Demo form to reserve a parking slot
  - 360 View:      AI annotated output frame (zone_output.jpg)
  - Contact Us:    Helpdesk contact info and support details

Run:
    streamlit run app.py
=============================================================================
"""

import os
import time
import sqlite3
from datetime import datetime
from pathlib import Path
import streamlit as st

# -- Database imports --------------------------------------------------------
from parking_db import (
    init_parking_db,
    init_zones_db,
    ensure_zones_exist,
    get_all_zones,
    get_zone_stats,
    ZONE_STATUS_AVAILABLE,
    ZONE_STATUS_FILLING,
    ZONE_STATUS_FULL,
)

# -- Auth imports ------------------------------------------------------------
from auth import register_user, login_user, logout_user
from auth_db import init_users_db

# -- Constants ---------------------------------------------------------------
GRID_COLUMNS    = 4
REFRESH_SECONDS = 2
DB_PATH         = "parking.db"

# =============================================================================
# SECTION 1 - PAGE CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="Smart Parking System",
    page_icon="\U0001f17f\ufe0f",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# SECTION 2 - CUSTOM CSS
# =============================================================================

def apply_styles() -> None:
    """Injects all custom CSS for the zone-based dashboard."""
    st.markdown("""
    <style>

    /* -- Google Font ------------------------------------------------- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .stApp {
        background-color: #080f1e;
        color: #e2e8f0;
    }

    /* -- Header Banner ----------------------------------------------- */
    .header-container {
        background: linear-gradient(135deg, #0f2444 0%, #080f1e 100%);
        border: 1px solid #1e40af33;
        border-radius: 20px;
        padding: 28px 24px;
        text-align: center;
        margin-bottom: 4px;
    }
    .header-title {
        font-size: 2.4rem;
        font-weight: 900;
        color: #f1f5f9;
        letter-spacing: -0.5px;
        margin: 0;
    }
    .header-subtitle {
        color: #64748b;
        font-size: 0.95rem;
        margin-top: 6px;
        font-weight: 500;
    }
    .header-badge {
        display: inline-block;
        background: #0c2340;
        color: #93c5fd;
        padding: 5px 20px;
        border-radius: 99px;
        font-size: 0.75rem;
        font-weight: 700;
        margin-top: 14px;
        letter-spacing: 0.5px;
        border: 1px solid #1e40af44;
    }

    /* -- Summary Stats Cards ----------------------------------------- */
    .stats-card {
        background: #0e1829;
        border: 1px solid #1a2f52;
        border-radius: 16px;
        padding: 22px 16px;
        text-align: center;
        box-shadow: 0 6px 24px rgba(0,0,0,0.5);
    }
    .stats-icon  { font-size: 28px; margin-bottom: 4px; }
    .stats-value {
        font-size: 2.4rem;
        font-weight: 900;
        margin: 6px 0 4px;
        line-height: 1;
    }
    .stats-label {
        font-size: 0.68rem;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-weight: 700;
    }

    /* -- Overall Occupancy Bar --------------------------------------- */
    .occ-bar-bg {
        background: #1a2f52;
        border-radius: 99px;
        height: 8px;
        margin-top: 14px;
        overflow: hidden;
    }
    .occ-bar-fill {
        height: 8px;
        border-radius: 99px;
        transition: width 0.5s ease;
    }

    /* -- Section Label ----------------------------------------------- */
    .section-label {
        font-size: 0.70rem;
        font-weight: 700;
        color: #334155;
        text-transform: uppercase;
        letter-spacing: 2.5px;
        margin: 20px 0 14px;
    }

    /* -- Zone Cards -------------------------------------------------- */
    .zone-card {
        border-radius: 18px;
        padding: 22px 16px 18px;
        text-align: center;
        margin-bottom: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.45);
        transition: transform 0.18s ease, box-shadow 0.18s ease;
        position: relative;
        overflow: hidden;
    }
    .zone-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 30px rgba(0,0,0,0.55);
    }

    /* Status-based card backgrounds */
    .zone-available {
        background: linear-gradient(155deg, #0a2318 0%, #052e16 100%);
        border: 1px solid #166534aa;
    }
    .zone-filling {
        background: linear-gradient(155deg, #1a1400 0%, #2d1f00 100%);
        border: 1px solid #a16207aa;
    }
    .zone-full {
        background: linear-gradient(155deg, #1f0505 0%, #3b0000 100%);
        border: 1px solid #991b1baa;
    }

    /* Card inner elements */
    .zone-name {
        font-size: 1.05rem;
        font-weight: 800;
        color: #e2e8f0;
        margin-bottom: 12px;
        letter-spacing: 0.3px;
    }
    .zone-count {
        font-size: 2.2rem;
        font-weight: 900;
        line-height: 1;
        margin: 4px 0 2px;
    }
    .zone-count-label {
        font-size: 0.65rem;
        color: #94a3b8;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 14px;
    }

    /* Capacity mini progress bar inside zone card */
    .zone-bar-bg {
        background: rgba(255,255,255,0.08);
        border-radius: 99px;
        height: 7px;
        margin: 10px 4px 12px;
        overflow: hidden;
    }
    .zone-bar-fill {
        height: 7px;
        border-radius: 99px;
    }

    /* Status badge pill */
    .zone-badge {
        display: inline-block;
        padding: 3px 14px;
        border-radius: 99px;
        font-size: 0.62rem;
        font-weight: 700;
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-top: 4px;
    }
    .badge-available { background: #14532d55; color: #4ade80; border: 1px solid #16a34a66; }
    .badge-filling   { background: #78350f55; color: #fbbf24; border: 1px solid #d9770066; }
    .badge-full      { background: #7f1d1d55; color: #f87171; border: 1px solid #dc262666; }

    /* Available spaces count */
    .zone-avail {
        font-size: 0.72rem;
        color: #64748b;
        margin-top: 6px;
        font-weight: 500;
    }

    /* -- Sidebar ----------------------------------------------------- */
    [data-testid="stSidebar"] {
        background-color: #090f1d !important;
        border-right: 1px solid #1a2f52;
    }

    /* -- Right Panel Cards ------------------------------------------- */
    .panel-card {
        background: #0e1829;
        border: 1px solid #1a2f52;
        border-radius: 16px;
        padding: 20px 16px;
        margin-bottom: 16px;
    }
    .panel-card-header {
        font-size: 0.85rem;
        font-weight: 700;
        color: #e2e8f0;
        margin-bottom: 12px;
        letter-spacing: 0.3px;
    }

    /* -- Contact Cards ----------------------------------------------- */
    .contact-card {
        background: #0e1829;
        border: 1px solid #1a2f52;
        border-radius: 16px;
        padding: 24px 18px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
    }
    .contact-icon { font-size: 2rem; margin-bottom: 8px; }
    .contact-title {
        font-size: 1rem;
        font-weight: 700;
        color: #e2e8f0;
        margin-bottom: 6px;
    }
    .contact-detail {
        font-size: 0.82rem;
        color: #94a3b8;
        line-height: 1.5;
    }

    /* -- Footer ------------------------------------------------------ */
    .footer {
        text-align: center;
        color: #1e293b;
        font-size: 0.74rem;
        margin-top: 40px;
        padding-top: 18px;
        border-top: 1px solid #0f1e35;
    }

    /* -- Auth Portal ------------------------------------------------- */
    .auth-container {
        max-width: 480px;
        margin: 60px auto 40px auto;
        padding: 36px 32px;
        background: linear-gradient(145deg, #0e1829 0%, #0a1628 100%);
        border: 1px solid #1a2f52;
        border-radius: 20px;
        box-shadow: 0 8px 40px rgba(0,0,0,0.6);
    }
    .auth-header {
        text-align: center;
        margin-bottom: 28px;
    }
    .auth-header h1 {
        font-size: 1.8rem;
        font-weight: 900;
        color: #f1f5f9;
        margin: 0 0 6px 0;
    }
    .auth-header p {
        font-size: 0.85rem;
        color: #64748b;
        margin: 0;
    }
    .auth-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent 0%, #1e40af55 50%, transparent 100%);
        margin: 18px 0;
    }

    </style>
    """, unsafe_allow_html=True)


# =============================================================================
# SECTION 3 - DATABASE LOADER
# =============================================================================

def load_zones_from_db() -> list:
    """Reads all zone rows from parking_zones and returns as list of dicts."""
    return get_all_zones()


# =============================================================================
# SECTION 4 - NAVIGATION SIDEBAR
# =============================================================================

NAV_ITEMS = [
    ("dashboard", "Dashboard"),
    ("history",   "Check History"),
    ("reserve",   "Reserve Slot"),
    ("360view",   "360 View"),
    ("contact",   "Contact Us"),
]


def render_navigation_sidebar(zone_stats: dict) -> tuple:
    """
    Renders the left sidebar with:
      - IoT SPS brand header
      - 5 navigation buttons (stateful page switching)
      - Zone summary stats card
      - Refresh controls (slider + toggle)

    Returns:
        tuple: (refresh_interval, auto_refresh)
    """
    with st.sidebar:
        # -- Brand header
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #0c2340 0%, #0a1628 100%);
            border: 1px solid #1e40af44;
            border-radius: 16px;
            padding: 18px 14px;
            text-align: center;
            margin-bottom: 12px;
        ">
          <div style="font-size: 1.6rem; font-weight: 900; color: #f1f5f9; letter-spacing: -0.5px;">
            &#x1F697; IoT SPS
          </div>
          <div style="font-size: 0.68rem; color: #64748b; font-weight: 500; margin-top: 4px;
                      letter-spacing: 1.5px; text-transform: uppercase;">
            Smart Parking System
          </div>
        </div>
        """, unsafe_allow_html=True)

        # -- User info + Logout
        user = st.session_state.get("user")
        if user:
            user_name = user.get("full_name", "User")
            st.markdown(f"""
            <div style="background:#0a1628; border:1px solid #1a3058; border-radius:12px;
                        padding:12px 14px; margin-bottom:8px; text-align:center;">
              <div style="font-size:0.72rem; color:#64748b; margin-bottom:4px;">Logged in as</div>
              <div style="font-size:0.92rem; font-weight:700; color:#93c5fd;">{user_name}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Logout", key="btn_sidebar_logout",
                         use_container_width=True, type="secondary"):
                logout_user(st.session_state)
                st.session_state["authenticated"] = False
                st.session_state["user"] = None
                st.session_state["page"] = "dashboard"
                st.rerun()

        st.markdown("---")

        # -- Navigation buttons
        current_page = st.session_state.get("page", "dashboard")

        for page_key, label in NAV_ITEMS:
            btn_type = "primary" if current_page == page_key else "secondary"
            if st.button(label, key=f"nav_{page_key}",
                         use_container_width=True, type=btn_type):
                st.session_state["page"] = page_key
                st.rerun()

        st.markdown("---")

        # -- Zone Summary stats card
        st.markdown(f"""
                <span style="color:#4a6080;font-weight:600;">Total Capacity</span>
                <span style="color:#93c5fd;font-weight:700;">{zone_stats.get('total_capacity', 0)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:5px 0;font-size:0.82rem;border-bottom:1px solid #0d1f3c;">
                <span style="color:#4a6080;font-weight:600;">Total Parked</span>
                <span style="color:#f87171;font-weight:700;">{zone_stats.get('total_parked', 0)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:5px 0;font-size:0.82rem;border-bottom:1px solid #0d1f3c;">
                <span style="color:#4a6080;font-weight:600;">Available</span>
                <span style="color:#4ade80;font-weight:700;">{zone_stats.get('total_available', 0)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:5px 0;font-size:0.82rem;border-bottom:1px solid #0d1f3c;">
                <span style="color:#4a6080;font-weight:600;">Avail Zones</span>
                <span style="color:#4ade80;font-weight:700;">{zone_stats.get('zones_available', 0)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:5px 0;font-size:0.82rem;border-bottom:1px solid #0d1f3c;">
                <span style="color:#4a6080;font-weight:600;">Filling Zones</span>
                <span style="color:#fbbf24;font-weight:700;">{zone_stats.get('zones_filling', 0)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:5px 0;font-size:0.82rem;">
                <span style="color:#4a6080;font-weight:600;">Full Zones</span>
                <span style="color:#f87171;font-weight:700;">{zone_stats.get('zones_full', 0)}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # -- Refresh controls
        refresh_interval = st.slider(
            label="Refresh Every (seconds)",
            min_value=2, max_value=30, value=REFRESH_SECONDS, step=1,
            help="How often the dashboard re-queries parking.db.",
        )
        auto_refresh = st.toggle("Auto Refresh", value=True)

        st.markdown("---")
        st.markdown("""
        <div style="font-size:0.65rem; color:#334155; text-align:center; letter-spacing:1px;">
            ZONE-BASED AI MODE
        </div>
        """, unsafe_allow_html=True)

    return refresh_interval, auto_refresh


# =============================================================================
# SECTION 5 - HEADER
# =============================================================================

def render_header() -> None:
    """Renders the top banner with live timestamp and LIVE badge."""
    timestamp = datetime.now().strftime("%d %b %Y  %I:%M:%S %p")
    st.markdown(f"""
    <div class="header-container">
        <div class="header-title">&#x1F17F;&#xFE0F; Smart Parking System</div>
        <div class="header-subtitle">AI-Based Zone Detection &amp; Navigation Dashboard</div>
        <div class="header-badge">&#x1F7E2; LIVE - Zone-Based Mode &nbsp;&bull;&nbsp; {timestamp}</div>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# SECTION 6 - SUMMARY STATS ROW
# =============================================================================

def render_summary_stats(zone_stats: dict) -> None:
    """Renders 4 top-level stats cards: Capacity, Available, Parked, Occupancy %."""
    total_cap   = zone_stats.get("total_capacity",  0)
    total_park  = zone_stats.get("total_parked",    0)
    total_avail = zone_stats.get("total_available", 0)
    overall_pct = zone_stats.get("overall_pct",     0.0)

    if overall_pct >= 85:
        rate_color = "#f87171"
    elif overall_pct >= 60:
        rate_color = "#fbbf24"
    else:
        rate_color = "#4ade80"

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="stats-card">
            <div class="stats-icon">&#x1F3E2;</div>
            <div class="stats-value" style="color:#60a5fa;">{total_cap}</div>
            <div class="stats-label">Total Capacity</div>
        </div>""", unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="stats-card">
            <div class="stats-icon">&#x2705;</div>
            <div class="stats-value" style="color:#4ade80;">{total_avail}</div>
            <div class="stats-label">Available</div>
        </div>""", unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="stats-card">
            <div class="stats-icon">&#x1F697;</div>
            <div class="stats-value" style="color:#f87171;">{total_park}</div>
            <div class="stats-label">Total Parked</div>
        </div>""", unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="stats-card">
            <div class="stats-icon">&#x1F4CA;</div>
            <div class="stats-value" style="color:{rate_color};">{overall_pct:.1f}%</div>
            <div class="stats-label">Occupancy Rate</div>
        </div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div class="occ-bar-bg">
        <div class="occ-bar-fill"
             style="width:{min(overall_pct, 100):.1f}%; background:{rate_color};"></div>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# SECTION 7 - DIGITAL TWIN ZONE MODAL + ZONE GRID
# =============================================================================

@st.dialog("Zone Digital Map", width="large")
def show_digital_zone_map(zone: dict) -> None:
    """
    Digital Twin 2D Parking Slot Map modal.
    Generates individual slot cards for every space in the zone.
    Occupied slots = dark red with car icon.
    Empty slots = dark green with parking icon.
    """
    zone_id   = zone.get("zone_id",     "?")
    capacity  = int(zone.get("capacity",    0))
    parked    = int(zone.get("parked_count", 0))
    available = int(zone.get("available",   0))
    occ_pct   = zone.get("occ_pct",    0.0)
    status    = zone.get("status",      ZONE_STATUS_AVAILABLE)
    updated   = zone.get("last_updated", "--")

    if status == ZONE_STATUS_FULL:
        bar_color   = "#ef4444"
        status_pill = "&#x1F534; FULL"
    elif status == ZONE_STATUS_FILLING:
        bar_color   = "#f59e0b"
        status_pill = "&#x1F7E1; FILLING"
    else:
        bar_color   = "#22c55e"
        status_pill = "&#x1F7E2; AVAILABLE"

    bar_w = min(max(occ_pct, 0.0), 100.0)

    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 18px 22px;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 18px;
        flex-wrap: wrap;
    ">
      <div style="font-size:1.25rem; font-weight:700; color:#f1f5f9; flex:1; min-width:160px;">
        &#x1F4CD; Zone {zone_id} &mdash; Digital Map
      </div>
      <div style="display:flex; gap:12px; flex-wrap:wrap; align-items:center;">
        <span style="background:#1e293b; border:1px solid #475569; border-radius:20px;
                     padding:4px 14px; font-size:0.82rem; color:#94a3b8;">
          {capacity} Total
        </span>
        <span style="background:#3f1414; border:1px solid #ef4444; border-radius:20px;
                     padding:4px 14px; font-size:0.82rem; color:#fca5a5; font-weight:600;">
          &#x1F698; {parked} Parked
        </span>
        <span style="background:#0f381e; border:1px solid #22c55e; border-radius:20px;
                     padding:4px 14px; font-size:0.82rem; color:#86efac; font-weight:600;">
          &#x1F7E2; {available} Free
        </span>
        <span style="background:#0f172a; border:1px solid {bar_color}; border-radius:20px;
                     padding:4px 14px; font-size:0.82rem; color:{bar_color}; font-weight:700;">
          {status_pill}
        </span>
      </div>
    </div>

    <div style="margin-bottom:6px;">
      <div style="background:#1e293b; border-radius:6px; height:8px; overflow:hidden;">
        <div style="width:{bar_w:.1f}%; height:100%; background:{bar_color};
                    border-radius:6px; transition:width 0.4s ease;"></div>
      </div>
      <div style="font-size:0.72rem; color:#64748b; margin-top:4px; text-align:right;">
        {occ_pct:.1f}% occupied &nbsp;|&nbsp; &#x1F552; {updated}
      </div>
    </div>
    """, unsafe_allow_html=True)

    if capacity == 0:
        st.info("No capacity data available for this zone.")
        return

    slot_cards_html = []
    for slot_num in range(1, capacity + 1):
        is_occupied = slot_num <= parked

        if is_occupied:
            bg        = "#3f1414"
            border    = "#ef4444"
            glow      = "0 0 10px rgba(239,68,68,0.45)"
            icon      = "&#x1F698;"
            badge_bg  = "#7f1d1d"
            badge_col = "#fca5a5"
            badge_txt = "OCCUPIED"
            num_col   = "#f87171"
        else:
            bg        = "#0f381e"
            border    = "#22c55e"
            glow      = "0 0 10px rgba(34,197,94,0.35)"
            icon      = "&#x1F17F;&#xFE0F;"
            badge_bg  = "#14532d"
            badge_col = "#86efac"
            badge_txt = "EMPTY"
            num_col   = "#4ade80"

        slot_cards_html.append(f"""
        <div style="
            background:{bg};
            border:1.5px solid {border};
            box-shadow:{glow};
            border-radius:10px;
            padding:12px 8px 10px 8px;
            display:flex;
            flex-direction:column;
            align-items:center;
            gap:5px;
            transition:transform 0.2s ease;
        ">
          <div style="font-size:1.45rem; line-height:1;">{icon}</div>
          <div style="font-size:0.72rem; font-weight:700; color:{num_col};
                      letter-spacing:0.04em;">#{slot_num}</div>
          <div style="
              background:{badge_bg};
              color:{badge_col};
              font-size:0.58rem;
              font-weight:800;
              letter-spacing:0.06em;
              border-radius:10px;
              padding:2px 7px;
          ">{badge_txt}</div>
        </div>""")

    grid_html = (
        '<div style="'
        'display:grid;'
        'grid-template-columns:repeat(4, 1fr);'
        'gap:10px;'
        'margin-top:16px;'
        'max-height:420px;'
        'overflow-y:auto;'
        'padding-right:4px;'
        '">'
        + "".join(slot_cards_html)
        + "</div>"
    )

    st.markdown(grid_html, unsafe_allow_html=True)

    st.markdown("""
    <div style="display:flex; gap:16px; margin-top:14px; font-size:0.75rem;
                color:#64748b; justify-content:flex-end;">
      <span>&#x1F698; &nbsp;Occupied slot</span>
      <span>&#x1F17F;&#xFE0F; &nbsp;Empty slot</span>
    </div>
    """, unsafe_allow_html=True)


def render_zone_grid(zones: list) -> None:
    """
    Renders the 4-column zone card grid.
    Each card has a View Map button that opens the Digital Twin modal.
    """
    if not zones:
        st.info("No zone data found in parking.db. Run detection_engine.py first.")
        return

    st.markdown(
        '<div class="section-label">&#x1F5FA;&#xFE0F; Zone-by-Zone Parking Overview &mdash; Live from parking.db</div>',
        unsafe_allow_html=True,
    )

    rows = [zones[i : i + GRID_COLUMNS] for i in range(0, len(zones), GRID_COLUMNS)]

    for row in rows:
        cols = st.columns(GRID_COLUMNS)

        for col_widget, zone in zip(cols, row):
            status    = zone.get("status",        ZONE_STATUS_AVAILABLE)
            capacity  = zone.get("capacity",      0)
            parked    = zone.get("parked_count",  0)
            available = zone.get("available",     0)
            occ_pct   = zone.get("occ_pct",       0.0)
            zone_id   = zone.get("zone_id",       "Zone ?")

            if status == ZONE_STATUS_FULL:
                card_css    = "zone-full"
                badge_css   = "badge-full"
                badge_text  = "&#x1F534; FULL"
                count_color = "#f87171"
                bar_color   = "#ef4444"
            elif status == ZONE_STATUS_FILLING:
                card_css    = "zone-filling"
                badge_css   = "badge-filling"
                badge_text  = "&#x1F7E1; FILLING"
                count_color = "#fbbf24"
                bar_color   = "#f59e0b"
            else:
                card_css    = "zone-available"
                badge_css   = "badge-available"
                badge_text  = "&#x1F7E2; AVAILABLE"
                count_color = "#4ade80"
                bar_color   = "#22c55e"

            bar_width   = min(max(occ_pct, 0.0), 100.0)
            spaces_word = "spaces" if available != 1 else "space"

            card_html = (
                f'<div class="zone-card {card_css}">'
                f'<div class="zone-name">&#x1F17F;&#xFE0F; {zone_id}</div>'
                f'<div class="zone-count" style="color:{count_color};">{parked}</div>'
                f'<div class="zone-count-label">OF {capacity} PARKED</div>'
                f'<div class="zone-bar-bg">'
                f'<div class="zone-bar-fill" style="width:{bar_width:.1f}%; background:{bar_color};"></div>'
                f'</div>'
                f'<div style="font-size:0.75rem; color:#94a3b8; margin-bottom:8px;">{occ_pct:.1f}% occupied</div>'
                f'<span class="zone-badge {badge_css}">{badge_text}</span>'
                f'<div class="zone-avail">{available} {spaces_word} free</div>'
                f'</div>'
            )

            with col_widget:
                st.markdown(card_html, unsafe_allow_html=True)
                if st.button("View Map", key=f"view_{zone_id}",
                             use_container_width=True):
                    show_digital_zone_map(zone)


# =============================================================================
# SECTION 8 - RIGHT PANEL (Auth + Feedback)
# =============================================================================

def render_right_panel() -> None:
    """
    Renders the Feedback card in the right column.
    Auth is now handled by the full-screen auth portal.
    """
    user = st.session_state.get("user")
    if user:
        user_name = user.get("full_name", "User")
        user_email = user.get("email", "")
        st.markdown(f"""
        <div class="panel-card">
          <div class="panel-card-header">&#x1F464; Logged In</div>
          <div style="font-size:0.9rem; color:#93c5fd; font-weight:600;">{user_name}</div>
          <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">{user_email}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- Feedback Card ----
    st.markdown("""
    <div class="panel-card">
      <div class="panel-card-header">&#x1F4AC; Feedback</div>
    </div>
    """, unsafe_allow_html=True)

    fb_subject = st.text_input("Subject", key="fb_subject",
                               placeholder="Issue or suggestion")
    fb_message = st.text_area("Message", key="fb_message",
                              placeholder="Tell us more...", height=100)

    if st.button("Submit Feedback", key="btn_feedback",
                 use_container_width=True):
        if fb_subject and fb_message:
            st.toast("Thank you for your feedback!")
        else:
            st.warning("Please fill in both subject and message.")


# =============================================================================
# SECTION 9 - PAGE: CHECK HISTORY
# =============================================================================

def render_page_history() -> None:
    """Displays recent zone occupancy data from parking.db."""
    st.markdown("""
    <div class="header-container" style="padding:18px 24px;">
        <div class="header-title" style="font-size:1.6rem;">&#x1F552; Parking History Log</div>
        <div class="header-subtitle">Recent zone occupancy snapshots from parking.db</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT zone_id, capacity, parked_count, available,
                   occ_pct, status, last_updated
            FROM   parking_zones
            ORDER  BY last_updated DESC
        """)
        rows = cursor.fetchall()
        conn.close()

        if rows:
            import pandas as pd
            df = pd.DataFrame([dict(r) for r in rows])
            df.columns = ["Zone", "Capacity", "Parked", "Available",
                          "Occ %", "Status", "Last Updated"]
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Read at {datetime.now().strftime('%I:%M:%S %p')} "
                       f"| {len(rows)} zone(s) from parking.db")
        else:
            st.info("No history data available. Run detection_engine.py first.")

    except Exception as e:
        st.error(f"Database error: {e}")


# =============================================================================
# SECTION 10 - PAGE: RESERVE SLOT
# =============================================================================

def render_page_reserve() -> None:
    """Demo reservation form allowing users to pick a zone and slot."""
    st.markdown("""
    <div class="header-container" style="padding:18px 24px;">
        <div class="header-title" style="font-size:1.6rem;">&#x1F4C5; Reserve a Parking Slot</div>
        <div class="header-subtitle">Select a zone and slot number to reserve</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    zones = load_zones_from_db()

    if not zones:
        st.info("No zones available. Run detection_engine.py to populate zones.")
        return

    zone_ids = [z["zone_id"] for z in zones]
    zone_cap_map = {z["zone_id"]: z.get("capacity", 1) for z in zones}

    col_form, col_info = st.columns([2, 1])

    with col_form:
        with st.form("reserve_form"):
            selected_zone = st.selectbox("Select Zone", zone_ids)

            max_slots = zone_cap_map.get(selected_zone, 1)
            slot_number = st.number_input(
                "Slot Number", min_value=1, max_value=max_slots,
                value=1, step=1,
                help=f"Zone {selected_zone} has {max_slots} slots."
            )

            vehicle_plate = st.text_input(
                "Vehicle Number Plate",
                placeholder="e.g. MH01AB1234"
            )

            submitted = st.form_submit_button(
                "Reserve Slot", use_container_width=True, type="primary"
            )

            if submitted:
                if vehicle_plate:
                    st.success(
                        f"Slot #{slot_number} in Zone {selected_zone} "
                        f"reserved for vehicle **{vehicle_plate.upper()}**!"
                    )
                    st.balloons()
                else:
                    st.warning("Please enter a vehicle number plate.")

    with col_info:
        st.markdown("""
        <div class="panel-card">
          <div class="panel-card-header">&#x2139;&#xFE0F; Demo Mode</div>
          <div style="font-size:0.82rem; color:#94a3b8; line-height:1.6;">
            This is a demonstration feature.<br><br>
            In a production system, this form would write
            the reservation to <code>parking.db</code> and
            update the slot status in real-time.
          </div>
        </div>
        """, unsafe_allow_html=True)


# =============================================================================
# SECTION 11 - PAGE: 360 VIEW
# =============================================================================

def render_page_360() -> None:
    """Displays the AI-annotated output frame (zone_output.jpg)."""
    st.markdown("""
    <div class="header-container" style="padding:18px 24px;">
        <div class="header-title" style="font-size:1.6rem;">&#x1F441;&#xFE0F; 360 View - AI Annotated Output</div>
        <div class="header-subtitle">Live annotated frame from detection engine</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    output_path = Path("zone_output.jpg")

    if output_path.exists():
        st.image(
            str(output_path),
            caption="zone_output.jpg - Annotated by detection_engine.py",
            use_container_width=True,
        )
        file_time = datetime.fromtimestamp(output_path.stat().st_mtime)
        st.caption(f"File last modified: {file_time.strftime('%d %b %Y %I:%M:%S %p')}")
    else:
        st.info(
            "No annotated output found. "
            "Run `python detection_engine.py --source my_parking.jpg` "
            "to generate zone_output.jpg."
        )

    if st.button("Refresh View", key="btn_refresh_360", use_container_width=False):
        st.rerun()


# =============================================================================
# SECTION 12 - PAGE: CONTACT US
# =============================================================================

def render_page_contact() -> None:
    """Displays helpdesk contact info, support email, and location."""
    st.markdown("""
    <div class="header-container" style="padding:18px 24px;">
        <div class="header-title" style="font-size:1.6rem;">&#x2709;&#xFE0F; Contact Us</div>
        <div class="header-subtitle">Smart Parking Support &amp; Assistance</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("""
        <div class="contact-card">
            <div class="contact-icon">&#x1F4DE;</div>
            <div class="contact-title">Emergency Helpline</div>
            <div class="contact-detail">
                +91-1800-XXX-XXXX<br>
                Available 24/7<br>
                Toll-Free Number
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
        <div class="contact-card">
            <div class="contact-icon">&#x1F4E7;</div>
            <div class="contact-title">Email Support</div>
            <div class="contact-detail">
                support@smartparking.io<br>
                Response within 24hrs<br>
                Mon - Sat, 9AM - 6PM
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown("""
        <div class="contact-card">
            <div class="contact-icon">&#x1F4CD;</div>
            <div class="contact-title">Location</div>
            <div class="contact-detail">
                Smart Parking HQ<br>
                Tech Park, Bangalore<br>
                Karnataka, India
            </div>
        </div>
        """, unsafe_allow_html=True)


# =============================================================================
# SECTION 13 - FOOTER
# =============================================================================

def render_footer() -> None:
    """Renders a minimal footer."""
    st.markdown("""
    <div class="footer">
        &#x1F17F;&#xFE0F; Smart Parking System &nbsp;|&nbsp;
        Zone-Based AI Mode &nbsp;|&nbsp;
        Python &middot; Streamlit &middot; OpenCV &middot; YOLOv8 &middot; SQLite
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# SECTION 14 - AUTH PORTAL (Full-screen Login / Sign Up)
# =============================================================================

def render_auth_portal() -> None:
    """
    Full-screen authentication portal displayed when user is NOT logged in.
    Two tabs: Login and Sign Up. Uses auth.py for validation and hashing.
    """
    st.markdown("""
    <div class="auth-container">
      <div class="auth-header">
        <h1>&#x1F697; Smart Parking AI Portal</h1>
        <p>Sign in to access the IoT Parking Dashboard</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Center the form using columns
    spacer_l, form_col, spacer_r = st.columns([1.2, 2, 1.2])

    with form_col:
        auth_mode = st.session_state.get("auth_mode", "login")

        # Tab-style toggle buttons
        col_login_tab, col_signup_tab = st.columns(2)
        with col_login_tab:
            if st.button("Login", key="portal_tab_login",
                         use_container_width=True,
                         type="primary" if auth_mode == "login" else "secondary"):
                st.session_state["auth_mode"] = "login"
                st.rerun()
        with col_signup_tab:
            if st.button("Sign Up", key="portal_tab_signup",
                         use_container_width=True,
                         type="primary" if auth_mode == "signup" else "secondary"):
                st.session_state["auth_mode"] = "signup"
                st.rerun()

        st.markdown('<div class="auth-divider"></div>', unsafe_allow_html=True)

        if auth_mode == "signup":
            # ---- SIGN UP FORM ----
            with st.form("signup_form"):
                full_name = st.text_input("Full Name", placeholder="e.g. Mohd Faiz")
                email     = st.text_input("Email Address", placeholder="you@example.com")
                mobile    = st.text_input("Mobile Number", placeholder="9876543210")
                vehicle   = st.text_input("Vehicle Number", placeholder="MH01AB1234")
                password  = st.text_input("Password", type="password",
                                          placeholder="Min 8 chars, 1 uppercase, 1 digit, 1 special")
                confirm   = st.text_input("Confirm Password", type="password",
                                          placeholder="Re-enter password")

                submitted = st.form_submit_button("Create Account",
                                                  use_container_width=True,
                                                  type="primary")
                if submitted:
                    ok, msg = register_user(
                        full_name, email, mobile, vehicle, password, confirm
                    )
                    if ok:
                        st.toast(msg)
                        # Auto-login after successful registration
                        from auth_db import get_user_by_email
                        user = get_user_by_email(email)
                        if user:
                            st.session_state["authenticated"] = True
                            st.session_state["user"] = dict(user)
                        st.rerun()
                    else:
                        st.error(msg)

        else:
            # ---- LOGIN FORM ----
            with st.form("login_form"):
                email    = st.text_input("Email Address", placeholder="you@example.com")
                password = st.text_input("Password", type="password",
                                         placeholder="Enter your password")

                submitted = st.form_submit_button("Login",
                                                  use_container_width=True,
                                                  type="primary")
                if submitted:
                    ok, result = login_user(email, password)
                    if ok:
                        st.session_state["authenticated"] = True
                        st.session_state["user"] = dict(result)
                        st.toast(f"Welcome back, {result['full_name']}!")
                        st.rerun()
                    else:
                        st.error(result)

        st.markdown('<div class="auth-divider"></div>', unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align:center; font-size:0.72rem; color:#475569;">
          Secure SHA-256 password hashing &nbsp;|&nbsp; Data stored in users.db
        </div>
        """, unsafe_allow_html=True)


# =============================================================================
# SECTION 15 - MAIN (Orchestrator)
# =============================================================================

def main() -> None:
    """
    Entry point - handles auth gating and multi-page dashboard routing.

    Flow:
      1. Inject CSS + ensure DB tables exist
      2. If NOT authenticated -> show Auth Portal (no sidebar, no data)
      3. If authenticated -> show full dashboard with sidebar navigation
    """

    # -- Step 1: CSS
    apply_styles()

    # -- Step 2: Ensure ALL DB tables exist (non-destructive)
    init_users_db()       # users table in users.db
    init_parking_db()     # parking_slots table in parking.db
    init_zones_db()       # parking_zones table in parking.db
    ensure_zones_exist()  # seed zones from config if empty

    # -- Step 3: Session state defaults
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("page", "dashboard")
    st.session_state.setdefault("auth_mode", "login")

    # -- Step 4: AUTH GATE
    if not st.session_state["authenticated"]:
        render_auth_portal()
        render_footer()
        return   # <-- STOP HERE. No sidebar, no dashboard.

    # ========================================================================
    # AUTHENTICATED ZONE - Full dashboard below this line
    # ========================================================================

    # -- Step 5: Fetch aggregate zone stats
    zone_stats = get_zone_stats()

    # -- Step 6: Navigation sidebar (with user info + logout)
    refresh_interval, auto_refresh = render_navigation_sidebar(zone_stats)

    # -- Step 7: Route to active page
    page = st.session_state["page"]

    if page == "dashboard":
        col_main, col_right = st.columns([3.2, 1.2])

        with col_main:
            render_header()
            st.markdown("<br>", unsafe_allow_html=True)
            render_summary_stats(zone_stats)
            st.markdown("<br>", unsafe_allow_html=True)
            zones = load_zones_from_db()
            render_zone_grid(zones)

        with col_right:
            render_right_panel()

    elif page == "history":
        render_page_history()

    elif page == "reserve":
        render_page_reserve()

    elif page == "360view":
        render_page_360()

    elif page == "contact":
        render_page_contact()

    # -- Step 8: Footer (all pages)
    render_footer()

    # -- Step 9: Auto-refresh (dashboard only)
    if auto_refresh and page == "dashboard":
        time.sleep(refresh_interval)
        st.rerun()


# =============================================================================
# SCRIPT GUARD
# =============================================================================
if __name__ == "__main__":
    main()
