"""
app.py  –  Smart Parking Web Application  (Zone-Based Dashboard)
─────────────────────────────────────────────────────────────────────────────
Main Streamlit dashboard — reads LIVE zone data from parking.db.

WHAT'S NEW in this version:
  ✅ Zone-based cards (Zone A, Zone B, ...) instead of individual slot cards
  ✅ Each card shows: parked count, capacity, occupancy bar, status badge
  ✅ 4-column responsive grid
  ✅ Top stats row: Total Capacity, Total Parked, Total Available, Overall %
  ✅ Auto-refresh every N seconds reading from parking_zones table

How it works:
  1. init_zones_db() + seed_zones() ensure the DB is ready on startup.
  2. load_zones_from_db() reads parking_zones table every refresh cycle.
  3. Each zone card is rendered with its live count + occupancy bar.
  4. time.sleep(N) + st.rerun() creates the auto-refresh loop.

Run:
    streamlit run app.py
─────────────────────────────────────────────────────────────────────────────
"""

import time
from datetime import datetime
import streamlit as st

# ── Database imports ───────────────────────────────────────────────────────────
from parking_db import (
    init_parking_db,
    init_zones_db,
    seed_slots,
    sync_zones_from_config,
    get_all_zones,
    get_zone_stats,
    ZONE_STATUS_AVAILABLE,
    ZONE_STATUS_FILLING,
    ZONE_STATUS_FULL,
)

# ── Constants ──────────────────────────────────────────────────────────────────
GRID_COLUMNS    = 4     # Zone cards per row
REFRESH_SECONDS = 5     # Default auto-refresh interval


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 ─ PAGE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Smart Parking System",
    page_icon="🅿️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 ─ CUSTOM CSS
# ══════════════════════════════════════════════════════════════════════════════

def apply_styles() -> None:
    """Injects all custom CSS for the zone-based dashboard."""
    st.markdown("""
    <style>

    /* ── Google Font ─────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .stApp {
        background-color: #080f1e;
        color: #e2e8f0;
    }

    /* ── Header Banner ───────────────────────────────────────── */
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

    /* ── Summary Stats Cards ─────────────────────────────────── */
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

    /* ── Overall Occupancy Bar ───────────────────────────────── */
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

    /* ── Section Label ───────────────────────────────────────── */
    .section-label {
        font-size: 0.70rem;
        font-weight: 700;
        color: #334155;
        text-transform: uppercase;
        letter-spacing: 2.5px;
        margin: 20px 0 14px;
    }

    /* ── Zone Cards ──────────────────────────────────────────── */
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

    /* ── Sidebar ─────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background-color: #090f1d !important;
        border-right: 1px solid #1a2f52;
    }

    /* ── Footer ──────────────────────────────────────────────── */
    .footer {
        text-align: center;
        color: #1e293b;
        font-size: 0.74rem;
        margin-top: 40px;
        padding-top: 18px;
        border-top: 1px solid #0f1e35;
    }

    </style>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 ─ DATABASE LOADER
# ══════════════════════════════════════════════════════════════════════════════

def load_zones_from_db() -> list:
    """
    Reads all zone rows from parking_zones table and returns them
    as a list of dicts, ready for the UI rendering functions.

    Each returned dict contains:
      zone_id      (str)  : 'Zone A', 'Zone B', etc.
      capacity     (int)  : Total spaces in this zone.
      parked_count (int)  : Vehicles currently detected.
      available    (int)  : capacity - parked_count.
      occ_pct      (float): Occupancy percentage (0.0 to 100.0).
      status       (str)  : 'available' | 'filling' | 'full'
      last_updated (str)  : Timestamp of last detection sync.

    Returns:
        list of dicts — one per zone, ordered by zone_id.
    """
    return get_all_zones()


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 ─ SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

def render_sidebar(zone_stats: dict) -> tuple:
    """
    Renders the sidebar with live DB counts + user controls.

    Parameters:
        zone_stats (dict): Output of get_zone_stats() — aggregate counts.

    Returns:
        tuple: (refresh_interval, auto_refresh)
    """
    with st.sidebar:
        st.markdown("## ⚙️ Controls")
        st.divider()

        # Live DB aggregate counts
        st.markdown("### 📊 Zone Summary")
        st.markdown(f"""
        <div style="background:#0a1628;border:1px solid #1a3058;border-radius:14px;padding:14px 16px;">
            <div style="display:flex;justify-content:space-between;padding:5px 0;font-size:0.82rem;border-bottom:1px solid #0d1f3c;">
                <span style="color:#4a6080;font-weight:600;">🏢 Total Capacity</span>
                <span style="color:#93c5fd;font-weight:700;">{zone_stats.get('total_capacity', 0)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:5px 0;font-size:0.82rem;border-bottom:1px solid #0d1f3c;">
                <span style="color:#4a6080;font-weight:600;">🚗 Total Parked</span>
                <span style="color:#f87171;font-weight:700;">{zone_stats.get('total_parked', 0)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:5px 0;font-size:0.82rem;border-bottom:1px solid #0d1f3c;">
                <span style="color:#4a6080;font-weight:600;">✅ Available</span>
                <span style="color:#4ade80;font-weight:700;">{zone_stats.get('total_available', 0)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:5px 0;font-size:0.82rem;border-bottom:1px solid #0d1f3c;">
                <span style="color:#4a6080;font-weight:600;">🟢 Avail Zones</span>
                <span style="color:#4ade80;font-weight:700;">{zone_stats.get('zones_available', 0)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:5px 0;font-size:0.82rem;border-bottom:1px solid #0d1f3c;">
                <span style="color:#4a6080;font-weight:600;">🟡 Filling Zones</span>
                <span style="color:#fbbf24;font-weight:700;">{zone_stats.get('zones_filling', 0)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:5px 0;font-size:0.82rem;">
                <span style="color:#4a6080;font-weight:600;">🔴 Full Zones</span>
                <span style="color:#f87171;font-weight:700;">{zone_stats.get('zones_full', 0)}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        refresh_interval = st.slider(
            label="⏱️ Refresh Every (seconds)",
            min_value=2, max_value=30, value=REFRESH_SECONDS, step=1,
            help="How often the dashboard re-queries parking.db for fresh zone data.",
        )

        auto_refresh = st.toggle("🔄 Auto Refresh", value=True)

        st.divider()
        st.markdown("### 🗺️ Legend")
        st.markdown("🟢 **Green**  — Available (< 60% full)")
        st.markdown("🟡 **Yellow** — Filling  (60–84% full)")
        st.markdown("🔴 **Red**    — Full     (≥ 85% full)")

        st.divider()
        st.markdown("### ℹ️ Mode")
        st.success(
            "**Live Zone Mode** ✅\n\n"
            "Zone counts read from `parking_zones` table.\n\n"
            "Run `detection_engine.py` in a separate terminal "
            "to push real-time AI counts here.",
            icon="🤖",
        )

        st.divider()
        st.markdown("### 🗄️ Data Source")
        st.code("parking.db → parking_zones", language="text")
        st.caption(f"Last read: {datetime.now().strftime('%I:%M:%S %p')}")

    return refresh_interval, auto_refresh


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 ─ HEADER
# ══════════════════════════════════════════════════════════════════════════════

def render_header() -> None:
    """Renders the top banner with live timestamp and LIVE badge."""
    timestamp = datetime.now().strftime("%d %b %Y  •  %I:%M:%S %p")
    st.markdown(f"""
    <div class="header-container">
        <div class="header-title">🅿️ Smart Parking System</div>
        <div class="header-subtitle">AI-Based Zone Detection & Navigation Dashboard</div>
        <div class="header-badge">🟢 LIVE — Zone-Based Mode &nbsp;•&nbsp; {timestamp}</div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 ─ SUMMARY STATS ROW
# ══════════════════════════════════════════════════════════════════════════════

def render_summary_stats(zone_stats: dict) -> None:
    """
    Renders 4 top-level stats cards: Capacity, Parked, Available, Overall %.

    Parameters:
        zone_stats (dict): Output of get_zone_stats() — aggregate numbers.
    """
    total_cap   = zone_stats.get("total_capacity",  0)
    total_park  = zone_stats.get("total_parked",    0)
    total_avail = zone_stats.get("total_available", 0)
    overall_pct = zone_stats.get("overall_pct",     0.0)

    # Colour for overall occupancy %
    if overall_pct >= 85:
        rate_color = "#f87171"   # red
    elif overall_pct >= 60:
        rate_color = "#fbbf24"   # yellow
    else:
        rate_color = "#4ade80"   # green

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="stats-card">
            <div class="stats-icon">🏢</div>
            <div class="stats-value" style="color:#60a5fa;">{total_cap}</div>
            <div class="stats-label">Total Capacity</div>
        </div>""", unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="stats-card">
            <div class="stats-icon">✅</div>
            <div class="stats-value" style="color:#4ade80;">{total_avail}</div>
            <div class="stats-label">Available</div>
        </div>""", unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="stats-card">
            <div class="stats-icon">🚗</div>
            <div class="stats-value" style="color:#f87171;">{total_park}</div>
            <div class="stats-label">Total Parked</div>
        </div>""", unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="stats-card">
            <div class="stats-icon">📊</div>
            <div class="stats-value" style="color:{rate_color};">{overall_pct:.1f}%</div>
            <div class="stats-label">Occupancy Rate</div>
        </div>""", unsafe_allow_html=True)

    # Overall occupancy bar
    st.markdown(f"""
    <div class="occ-bar-bg">
        <div class="occ-bar-fill"
             style="width:{min(overall_pct, 100):.1f}%; background:{rate_color};"></div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 ─ ZONE GRID
# ══════════════════════════════════════════════════════════════════════════════

def render_zone_grid(zones: list) -> None:
    """
    Renders the main zone grid in a 4-column layout.

    Each zone card displays:
      - Zone name (e.g. "Zone A")
      - Parked count / Capacity  (e.g. "8 / 10")
      - Occupancy percentage mini-bar
      - Status badge: 🟢 AVAILABLE | 🟡 FILLING | 🔴 FULL
      - Available spaces text

    Card colour reflects status:
      Green card  → available   (< 60% full)
      Yellow card → filling     (60–84% full)
      Red card    → full        (≥ 85% full)

    Parameters:
        zones (list): Output of load_zones_from_db() — list of zone dicts.
    """
    if not zones:
        st.warning("⚠️ No zones found in parking.db. "
                   "Run `python detection_engine.py --source camera` to populate zones, "
                   "or check that `seed_zones()` ran correctly.")
        return

    st.markdown(
        '<div class="section-label">🗺️ Zone-by-Zone Parking Overview — Live from parking.db</div>',
        unsafe_allow_html=True
    )

    # Split zones into rows of GRID_COLUMNS
    rows = [zones[i : i + GRID_COLUMNS] for i in range(0, len(zones), GRID_COLUMNS)]

    for row in rows:
        cols = st.columns(GRID_COLUMNS)

        for col_widget, zone in zip(cols, row):
            status    = zone.get("status", ZONE_STATUS_AVAILABLE)
            capacity  = zone.get("capacity",     0)
            parked    = zone.get("parked_count", 0)
            available = zone.get("available",    0)
            occ_pct   = zone.get("occ_pct",     0.0)
            zone_id   = zone.get("zone_id", "Zone ?")

            # ── Choose card CSS class ──────────────────────────────────────────
            if status == ZONE_STATUS_FULL:
                card_css   = "zone-full"
                badge_css  = "badge-full"
                badge_text = "🔴 FULL"
                count_color= "#f87171"   # red
                bar_color  = "#ef4444"
            elif status == ZONE_STATUS_FILLING:
                card_css   = "zone-filling"
                badge_css  = "badge-filling"
                badge_text = "🟡 FILLING"
                count_color= "#fbbf24"   # yellow
                bar_color  = "#f59e0b"
            else:   # available
                card_css   = "zone-available"
                badge_css  = "badge-available"
                badge_text = "🟢 AVAILABLE"
                count_color= "#4ade80"   # green
                bar_color  = "#22c55e"

            # Occupancy bar width (clamped 0–100%)
            bar_width = min(max(occ_pct, 0.0), 100.0)

            # Compute plural suffix OUTSIDE the f-string to avoid quote conflicts
            spaces_word = "spaces" if available != 1 else "space"

            card_html = (
                f'<div class="zone-card {card_css}">'
                f'<div class="zone-name">&#x1F17F;&#xFE0F; {zone_id}</div>'
                f'<div class="zone-count" style="color:{count_color};">{parked}</div>'
                f'<div class="zone-count-label">of {capacity} parked</div>'
                f'<div class="zone-bar-bg">'
                f'<div class="zone-bar-fill" style="width:{bar_width:.1f}%; background:{bar_color};"></div>'
                f'</div>'
                f'<div style="font-size:0.75rem; color:#94a3b8; margin-bottom:8px;">{occ_pct:.1f}% full</div>'
                f'<span class="zone-badge {badge_css}">{badge_text}</span>'
                f'<div class="zone-avail">{available} {spaces_word} free</div>'
                f'</div>'
            )

            with col_widget:
                st.markdown(card_html, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8 ─ ZONE DATA TABLE
# ══════════════════════════════════════════════════════════════════════════════

def render_zone_table(zones: list) -> None:
    """
    Shows an expandable table with raw zone data from parking.db.
    Useful for viva demos — proves the data comes from SQLite.

    Parameters:
        zones (list): Output of load_zones_from_db().
    """
    with st.expander("📋 View Raw Zone Data (Live from parking.db)", expanded=False):

        def status_label(s):
            if s == ZONE_STATUS_FULL:    return "🔴 Full"
            if s == ZONE_STATUS_FILLING: return "🟡 Filling"
            return "🟢 Available"

        table_data = {
            "Zone"      : [z["zone_id"]                  for z in zones],
            "Parked"    : [z["parked_count"]              for z in zones],
            "Capacity"  : [z["capacity"]                  for z in zones],
            "Available" : [z["available"]                 for z in zones],
            "Occ %"     : [f"{z['occ_pct']:.1f}%"        for z in zones],
            "Status"    : [status_label(z["status"])      for z in zones],
            "Updated"   : [z["last_updated"]              for z in zones],
        }
        st.dataframe(table_data, use_container_width=True, hide_index=True)
        st.caption(
            f"📁 Source: parking.db → parking_zones  •  "
            f"{len(zones)} zone(s)  •  "
            f"Read at {datetime.now().strftime('%I:%M:%S %p')}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 9 ─ FOOTER
# ══════════════════════════════════════════════════════════════════════════════

def render_footer() -> None:
    """Renders a minimal footer."""
    st.markdown("""
    <div class="footer">
        🅿️ Smart Parking System &nbsp;|&nbsp;
        Zone-Based AI Mode &nbsp;|&nbsp;
        Python · Streamlit · OpenCV · YOLOv8 · SQLite
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 10 ─ MAIN  (Orchestrator)
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """
    Entry point — assembles the full Zone-Based dashboard.

    Execution order on every refresh cycle:
      1.  Inject CSS.
      2.  Ensure parking.db tables exist (non-destructive).
      3.  Seed zones from ZONE_CONFIG if table is empty.
      4.  Fetch aggregate zone stats (for sidebar + summary row).
      5.  Render sidebar (returns refresh settings).
      6.  Render header.
      7.  Render summary stats row (4 metric cards).
      8.  Load all zone rows from parking.db.
      9.  Render zone cards grid (4 columns, colour-coded).
      10. Render raw data table (expandable).
      11. Render footer.
      12. Auto-refresh: sleep N seconds → st.rerun().
    """

    # ── Step 1: CSS ─────────────────────────────────────────────────────────────
    apply_styles()

    # ── Step 2 & 3: Ensure DB tables + sync zones from config ───────────────────
    # init_parking_db() / init_zones_db() use CREATE TABLE IF NOT EXISTS → safe.
    # sync_zones_from_config() WIPES parking_zones and re-inserts from ZONE_CONFIG
    # so the dashboard always reflects the exact zones in slot_config.py.
    init_parking_db()
    init_zones_db()
    seed_slots(total_rows=3, cols=4)
    sync_zones_from_config()   # <-- always syncs with slot_config.ZONE_CONFIG

    # ── Step 4: Fetch aggregate zone stats ──────────────────────────────────────
    zone_stats = get_zone_stats()

    # ── Step 5: Sidebar ─────────────────────────────────────────────────────────
    refresh_interval, auto_refresh = render_sidebar(zone_stats)

    # ── Step 6: Header ──────────────────────────────────────────────────────────
    render_header()
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 7: Summary stats row ───────────────────────────────────────────────
    render_summary_stats(zone_stats)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 8: Load zone rows from parking.db ──────────────────────────────────
    # get_all_zones() runs:
    #   SELECT zone_id, capacity, parked_count, available, occ_pct, status, last_updated
    #   FROM   parking_zones
    #   ORDER  BY zone_id ASC
    zones = load_zones_from_db()

    # ── Step 9: Zone card grid ──────────────────────────────────────────────────
    render_zone_grid(zones)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 10: Raw data table ─────────────────────────────────────────────────
    render_zone_table(zones)

    # ── Step 11: Footer ─────────────────────────────────────────────────────────
    render_footer()

    # ── Step 12: Auto-refresh loop ──────────────────────────────────────────────
    # How it works:
    #   a. time.sleep(N)  → pause the script for N seconds
    #   b. st.rerun()     → Streamlit restarts the script from line 1
    #   c. On restart, get_all_zones() re-queries parking.db
    #   d. If detection_engine.py updated zone counts during the sleep,
    #      the new values appear on screen immediately.
    #
    # This creates a smooth live update loop with ZERO CPU waste during sleep.
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SCRIPT GUARD
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()
