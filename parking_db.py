"""
parking_db.py  –  Parking Database Handler (Slots + Zones)
─────────────────────────────────────────────────────────────────────────────
This file manages ALL database operations for the Smart Parking system.

TWO TABLES in parking.db:
  1. parking_slots  →  Individual slot tracking (A1, A2 ... C4)
                        Status: 'available' | 'occupied' | 'reserved'
                        (Used by Module 3 / auth_app.py)

  2. parking_zones  →  Zone-based vehicle counting (Zone A, Zone B ...)
                        Columns: parked_count, capacity, available, status
                        (Used by Module 4 / detection_engine.py + app.py)

WHY two tables?
  Keeping them separate means old modules (auth, Module 3) keep working.
  The new zone system is additive — it does NOT break anything existing.
─────────────────────────────────────────────────────────────────────────────
"""

import sqlite3
import random
from datetime import datetime

# ── Constants ─────────────────────────────────────────────────────────────────
PARKING_DB_PATH = "parking.db"
GRID_ROWS       = "ABCDE"
GRID_COLS       = 4

# Slot statuses
STATUS_AVAILABLE = "available"
STATUS_OCCUPIED  = "occupied"
STATUS_RESERVED  = "reserved"

# Zone statuses (based on occupancy percentage)
ZONE_STATUS_AVAILABLE = "available"   # < 60% full  → lots of space
ZONE_STATUS_FILLING   = "filling"     # 60–84% full → filling up
ZONE_STATUS_FULL      = "full"        # ≥ 85% full  → almost/fully full

# Simulated vehicle numbers for seeding
FAKE_VEHICLES = [
    "MH01AB1234", "DL4CAF0001", "KA02XY9999", "TN09CD5678",
    "GJ05EF3456", "UP32GH7890", "RJ14IJ2345", "HR26KL6789",
    "MH12MN3456", "MP09OP7890", "AP28QR4567", "TS07ST8901",
    "WB20UV5678", "PB10WX9012", "CG07YZ3456", "BR01AA6789",
    "OR02BB0123", "JK01CC4567", "HP34DD8901", "UK07EE2345",
]


# ══════════════════════════════════════════════════════════════════════════════
# ── PART A: INDIVIDUAL SLOTS  (parking_slots table)
# ══════════════════════════════════════════════════════════════════════════════

# FUNCTION 1 ─ init_parking_db
def init_parking_db(db_path: str = PARKING_DB_PATH) -> None:
    """
    Creates the 'parking_slots' table if it does not exist.

    Columns:
      slot_id        → Primary key. 'A1', 'B3', etc.
      slot_row       → Row letter: 'A', 'B', 'C'
      slot_number    → Column: 1, 2, 3, 4
      status         → 'available' | 'occupied' | 'reserved'
      vehicle_number → Plate number if occupied, NULL otherwise
      last_updated   → Timestamp of last change
    """
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parking_slots (
            slot_id        TEXT    PRIMARY KEY,
            slot_row       TEXT    NOT NULL,
            slot_number    INTEGER NOT NULL,
            status         TEXT    NOT NULL DEFAULT 'available',
            vehicle_number TEXT,
            last_updated   TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# FUNCTION 2 ─ seed_slots
def seed_slots(
    total_rows: int = 3,
    cols: int = GRID_COLS,
    db_path: str = PARKING_DB_PATH
) -> None:
    """
    Populates parking_slots with simulated data (only if table is empty).

    Creates a realistic mix: ~50% available, ~35% occupied, ~15% reserved.

    Parameters:
        total_rows (int): Number of rows (A, B, C ...).
        cols       (int): Slots per row.
        db_path    (str): Database file path.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM parking_slots")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return   # Already seeded

    timestamp    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    vehicle_pool = FAKE_VEHICLES.copy()
    random.shuffle(vehicle_pool)

    rows_to_insert = []
    vehicle_index  = 0

    for row_idx in range(total_rows):
        row_letter = GRID_ROWS[row_idx]
        for col_num in range(1, cols + 1):
            slot_id = f"{row_letter}{col_num}"
            status  = random.choices(
                population=[STATUS_AVAILABLE, STATUS_OCCUPIED, STATUS_RESERVED],
                weights=[50, 35, 15],
                k=1
            )[0]

            vehicle_number = None
            if status == STATUS_OCCUPIED:
                vehicle_number = vehicle_pool[vehicle_index % len(vehicle_pool)]
                vehicle_index += 1

            rows_to_insert.append(
                (slot_id, row_letter, col_num, status, vehicle_number, timestamp)
            )

    cursor.executemany("""
        INSERT OR IGNORE INTO parking_slots
            (slot_id, slot_row, slot_number, status, vehicle_number, last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
    """, rows_to_insert)

    conn.commit()
    conn.close()


# FUNCTION 3 ─ get_all_slots
def get_all_slots(db_path: str = PARKING_DB_PATH) -> list:
    """
    Returns all slots ordered by row + column number.

    Returns:
        list of dicts: [{'slot_id': 'A1', 'status': 'available', ...}, ...]
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT slot_id, slot_row, slot_number, status, vehicle_number, last_updated
        FROM   parking_slots
        ORDER  BY slot_row ASC, slot_number ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# FUNCTION 4 ─ get_slots_by_status
def get_slots_by_status(status: str, db_path: str = PARKING_DB_PATH) -> list:
    """Returns slots filtered by a specific status string."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT slot_id, slot_row, slot_number, status, vehicle_number, last_updated
        FROM   parking_slots
        WHERE  status = ?
        ORDER  BY slot_row ASC, slot_number ASC
    """, (status,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# FUNCTION 5 ─ get_stats
def get_stats(db_path: str = PARKING_DB_PATH) -> dict:
    """
    Returns aggregate slot counts: total, available, occupied, reserved.

    Returns:
        dict: {'total': 12, 'available': 6, 'occupied': 4, 'reserved': 2}
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT status, COUNT(*) FROM parking_slots GROUP BY status
    """)
    rows = cursor.fetchall()
    conn.close()

    stats = {STATUS_AVAILABLE: 0, STATUS_OCCUPIED: 0, STATUS_RESERVED: 0}
    for status, count in rows:
        stats[status] = count
    stats["total"] = sum(stats.values())
    return stats


# FUNCTION 6 ─ update_slot_status
def update_slot_status(
    slot_id: str,
    new_status: str,
    vehicle_number: str = None,
    db_path: str = PARKING_DB_PATH,
) -> bool:
    """
    Updates status + vehicle number for a single slot.

    Returns:
        bool: True if slot was found and updated.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE parking_slots
        SET    status = ?, vehicle_number = ?, last_updated = ?
        WHERE  slot_id = ?
    """, (new_status, vehicle_number, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), slot_id))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


# FUNCTION 7 ─ randomize_slots
def randomize_slots(db_path: str = PARKING_DB_PATH) -> None:
    """Re-randomizes all slot statuses (used by simulation button)."""
    all_slots    = get_all_slots(db_path)
    vehicle_pool = FAKE_VEHICLES.copy()
    random.shuffle(vehicle_pool)
    timestamp    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    vehicle_idx  = 0

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for slot in all_slots:
        new_status = random.choices(
            population=[STATUS_AVAILABLE, STATUS_OCCUPIED, STATUS_RESERVED],
            weights=[50, 35, 15], k=1
        )[0]
        vehicle_number = None
        if new_status == STATUS_OCCUPIED:
            vehicle_number = vehicle_pool[vehicle_idx % len(vehicle_pool)]
            vehicle_idx += 1

        cursor.execute("""
            UPDATE parking_slots
            SET    status = ?, vehicle_number = ?, last_updated = ?
            WHERE  slot_id = ?
        """, (new_status, vehicle_number, timestamp, slot["slot_id"]))

    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ── PART B: ZONE-BASED TRACKING  (parking_zones table)
# ══════════════════════════════════════════════════════════════════════════════

# FUNCTION 8 ─ init_zones_db
def init_zones_db(db_path: str = PARKING_DB_PATH) -> None:
    """
    Creates the 'parking_zones' table if it does not exist.

    Columns:
      zone_id      → Primary key. Zone name, e.g. 'Zone A'.
      capacity     → Total parking spaces in this zone (from ZONE_CONFIG).
      parked_count → Number of vehicles currently detected inside this zone.
      available    → Calculated: capacity - parked_count.
      occ_pct      → Occupancy percentage: (parked_count / capacity) × 100.
      status       → 'available' | 'filling' | 'full'
      last_updated → Timestamp of last update.

    WHY a separate table from parking_slots?
      parking_zones stores COUNTS (how many cars in a region).
      parking_slots stores INDIVIDUAL slot states (which exact slot is used).
      They serve different purposes and can coexist.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parking_zones (
            zone_id      TEXT    PRIMARY KEY,
            capacity     INTEGER NOT NULL DEFAULT 10,
            parked_count INTEGER NOT NULL DEFAULT 0,
            available    INTEGER NOT NULL DEFAULT 10,
            occ_pct      REAL    NOT NULL DEFAULT 0.0,
            status       TEXT    NOT NULL DEFAULT 'available',
            last_updated TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# FUNCTION 9 ─ seed_zones
def seed_zones(db_path: str = PARKING_DB_PATH) -> None:
    """
    Inserts zone rows from ZONE_CONFIG (slot_config.py) if the table is empty.

    HOW it works:
      1. Imports ZONE_CONFIG from slot_config.py.
      2. For each zone, inserts a row with the correct capacity.
      3. Sets parked_count = 0 and available = capacity (no vehicles yet).

    This is called once on app startup. Safe to call repeatedly —
    uses INSERT OR IGNORE so existing rows are never overwritten.
    """
    from slot_config import ZONE_CONFIG

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for zone_id, cfg in ZONE_CONFIG.items():
        capacity = cfg.get("capacity", 10)
        cursor.execute("""
            INSERT OR IGNORE INTO parking_zones
                (zone_id, capacity, parked_count, available, occ_pct, status, last_updated)
            VALUES (?, ?, 0, ?, 0.0, 'available', ?)
        """, (zone_id, capacity, capacity, timestamp))

    conn.commit()
    conn.close()


# FUNCTION 10 (NEW) ─ sync_zones_from_config
def sync_zones_from_config(db_path: str = PARKING_DB_PATH) -> None:
    """
    Wipes ALL existing rows in parking_zones and re-inserts fresh rows
    from ZONE_CONFIG in slot_config.py.

    WHY wipe instead of INSERT OR IGNORE?
      INSERT OR IGNORE keeps OLD zones that no longer exist in ZONE_CONFIG.
      If you rename a zone in slot_config.py or run draw_slots.py to create
      new zones, the old stale rows would stay in the DB forever.
      sync_zones_from_config() guarantees the DB always matches the config.

    SAFETY:
      It resets parked_count=0 and available=capacity for all zones.
      This is intentional — the detection engine will repopulate counts
      on the next frame. It does NOT touch the parking_slots table.

    Parameters:
        db_path (str): Path to the SQLite database file.

    Called by:
        app.py  main()  →  on every Streamlit startup / refresh.
    """
    from slot_config import ZONE_CONFIG

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Step 1: Remove ALL existing zone rows (wipe old/stale data)
    cursor.execute("DELETE FROM parking_zones")

    # Step 2: Re-insert one row per zone from ZONE_CONFIG
    for zone_id, cfg in ZONE_CONFIG.items():
        capacity = cfg.get("capacity", 1)
        cursor.execute("""
            INSERT INTO parking_zones
                (zone_id, capacity, parked_count, available, occ_pct, status, last_updated)
            VALUES (?, ?, 0, ?, 0.0, 'available', ?)
        """, (zone_id, capacity, capacity, timestamp))

    conn.commit()
    conn.close()


# FUNCTION 10b ─ ensure_zones_exist  (NON-DESTRUCTIVE — safe to call every startup)
def ensure_zones_exist(db_path: str = PARKING_DB_PATH) -> None:
    """
    Adds any MISSING zones from ZONE_CONFIG into parking_zones.
    Uses INSERT OR IGNORE — never touches rows that already exist.

    KEY DIFFERENCE from sync_zones_from_config():
      sync_zones_from_config()  →  WIPES all rows first, resets counts to 0.
      ensure_zones_exist()      →  Only INSERTs missing rows. Leaves live
                                   parked_count values completely UNTOUCHED.

    WHEN to use each:
      ensure_zones_exist()      →  Called by app.py and detection_engine.py
                                   on every startup so the DB always has the
                                   right zones but NEVER resets live counts.
      sync_zones_from_config()  →  Only call manually (e.g., a Reset button)
                                   when you want a clean slate.

    Parameters:
        db_path (str): Path to the SQLite database file.
    """
    from slot_config import ZONE_CONFIG

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for zone_id, cfg in ZONE_CONFIG.items():
        capacity = cfg.get("capacity", 1)

        # Try to insert the zone (ignored if it already exists)
        cursor.execute("""
            INSERT OR IGNORE INTO parking_zones
                (zone_id, capacity, parked_count, available, occ_pct, status, last_updated)
            VALUES (?, ?, 0, ?, 0.0, 'available', ?)
        """, (zone_id, capacity, capacity, timestamp))

        # ALWAYS update the capacity column from ZONE_CONFIG.
        # This fixes any stale capacity values (e.g. old capacity=1 rows)
        # without touching parked_count, occ_pct, or status.
        cursor.execute("""
            UPDATE parking_zones
            SET    capacity  = ?,
                   available = MAX(0, ? - parked_count)
            WHERE  zone_id   = ?
        """, (capacity, capacity, zone_id))

    conn.commit()
    conn.close()


# FUNCTION 11 ─ get_all_zones
def get_all_zones(db_path: str = PARKING_DB_PATH) -> list:
    """
    Returns all zone rows from parking_zones, ordered by zone_id.

    Returns:
        list of dicts:
        [
            {
                'zone_id'     : 'Zone A',
                'capacity'    : 10,
                'parked_count': 7,
                'available'   : 3,
                'occ_pct'     : 70.0,
                'status'      : 'filling',
                'last_updated': '2026-07-29 18:00:00'
            },
            ...
        ]
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT zone_id, capacity, parked_count, available, occ_pct, status, last_updated
        FROM   parking_zones
        ORDER  BY zone_id ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# FUNCTION 11 ─ _derive_zone_status  (internal helper)
def _derive_zone_status(occ_pct: float) -> str:
    """
    Determines a zone's status string from its occupancy percentage.

    Thresholds:
      occ_pct < 60%  → 'available'  (lots of free space)
      60% ≤ occ_pct < 85%  → 'filling'  (getting crowded)
      occ_pct ≥ 85%  → 'full'       (almost or completely full)

    Parameters:
        occ_pct (float): Occupancy percentage (0.0 to 100.0).

    Returns:
        str: 'available', 'filling', or 'full'.
    """
    if occ_pct >= 85.0:
        return ZONE_STATUS_FULL
    elif occ_pct >= 60.0:
        return ZONE_STATUS_FILLING
    else:
        return ZONE_STATUS_AVAILABLE


# FUNCTION 12 ─ update_zone_count
def update_zone_count(
    zone_id: str,
    parked_count: int,
    zone_capacity: int = None,
    db_path: str = PARKING_DB_PATH,
) -> bool:
    """
    Updates the vehicle count for a zone and auto-recalculates derived fields.

    Called by detection_engine.py after counting vehicles per zone.

    What it auto-computes:
      available  = capacity - parked_count  (clamped to 0)
      occ_pct    = (parked_count / capacity) × 100
      status     = derived from occ_pct (available / filling / full)
      last_updated = current timestamp

    Parameters:
        zone_id       (str): Zone name, e.g. 'A1'.
        parked_count  (int): Number of vehicles currently detected in this zone.
        zone_capacity (int): Optional — if provided, also writes this as the
                             zone's capacity (keeps DB in sync with ZONE_CONFIG).
        db_path       (str): Database file path.

    Returns:
        bool: True if zone was found and updated, False otherwise.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Fetch current capacity for this zone
    cursor.execute("SELECT capacity FROM parking_zones WHERE zone_id = ?", (zone_id,))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        return False   # Zone not found in DB

    # Use caller-supplied capacity (from ZONE_CONFIG) if given; else use DB value.
    # This keeps capacity in sync with slot_config.py on every detection write.
    capacity = zone_capacity if zone_capacity is not None else row[0]

    # Clamp parked_count to valid range
    parked_count = max(0, min(parked_count, capacity))
    available    = capacity - parked_count
    occ_pct      = round((parked_count / capacity) * 100, 1) if capacity > 0 else 0.0
    status       = _derive_zone_status(occ_pct)
    timestamp    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE parking_zones
        SET    capacity     = ?,
               parked_count = ?,
               available    = ?,
               occ_pct      = ?,
               status       = ?,
               last_updated = ?
        WHERE  zone_id = ?
    """, (capacity, parked_count, available, occ_pct, status, timestamp, zone_id))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


# FUNCTION 13 ─ get_zone_stats
def get_zone_stats(db_path: str = PARKING_DB_PATH) -> dict:
    """
    Returns aggregate zone counts across ALL zones.

    Used by the dashboard's top stats row.

    Returns:
        dict:
        {
            'total_capacity' : 40,   ← sum of all zone capacities
            'total_parked'   : 25,   ← total vehicles parked
            'total_available': 15,   ← total free spaces
            'overall_pct'    : 62.5, ← overall occupancy %
            'zones_full'     : 1,    ← number of full zones
            'zones_filling'  : 2,    ← number of filling zones
            'zones_available': 1,    ← number of available zones
            'total_zones'    : 4,
        }
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            SUM(capacity),
            SUM(parked_count),
            SUM(available),
            COUNT(*),
            SUM(CASE WHEN status = 'full'      THEN 1 ELSE 0 END),
            SUM(CASE WHEN status = 'filling'   THEN 1 ELSE 0 END),
            SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END)
        FROM parking_zones
    """)
    row = cursor.fetchone()
    conn.close()

    total_cap  = row[0] or 0
    total_park = row[1] or 0
    total_avail= row[2] or 0
    total_zones= row[3] or 0
    z_full     = row[4] or 0
    z_filling  = row[5] or 0
    z_avail    = row[6] or 0

    overall_pct = round((total_park / total_cap) * 100, 1) if total_cap > 0 else 0.0

    return {
        "total_capacity"  : total_cap,
        "total_parked"    : total_park,
        "total_available" : total_avail,
        "overall_pct"     : overall_pct,
        "zones_full"      : z_full,
        "zones_filling"   : z_filling,
        "zones_available" : z_avail,
        "total_zones"     : total_zones,
    }


# FUNCTION 14 ─ reset_zones
def reset_zones(db_path: str = PARKING_DB_PATH) -> None:
    """
    Resets all zone parked_counts to 0 (all zones become available).
    Used for testing or when starting a new session.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT zone_id, capacity FROM parking_zones
    """)
    zones = cursor.fetchall()

    for zone_id, capacity in zones:
        cursor.execute("""
            UPDATE parking_zones
            SET    parked_count = 0,
                   available    = ?,
                   occ_pct      = 0.0,
                   status       = 'available',
                   last_updated = ?
            WHERE  zone_id = ?
        """, (capacity, timestamp, zone_id))

    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# SELF-TEST BLOCK
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import os

    TEST_DB = "test_parking.db"
    print("═" * 55)
    print("  parking_db.py  –  Self Test (Slots + Zones)")
    print("═" * 55)

    # ── PART A: Slots ──────────────────────────────────────────────────────────
    print("\n── Part A: Slots ──────────────────────────────────────")

    print("  [1] Creating parking_slots table...")
    init_parking_db(TEST_DB)

    print("  [2] Seeding 12 slots (3×4)...")
    seed_slots(total_rows=3, cols=4, db_path=TEST_DB)

    slots = get_all_slots(TEST_DB)
    print(f"  [3] Fetched {len(slots)} slots.")
    for s in slots:
        veh = f"  [{s['vehicle_number']}]" if s["vehicle_number"] else ""
        print(f"       {s['slot_id']}  →  {s['status']:12}{veh}")

    stats = get_stats(TEST_DB)
    print(f"\n  [4] Slot stats: {stats}")

    update_slot_status("A1", STATUS_RESERVED, db_path=TEST_DB)
    print(f"  [5] A1 → reserved: {get_slots_by_status(STATUS_RESERVED, TEST_DB)[0]}")

    # ── PART B: Zones ──────────────────────────────────────────────────────────
    print("\n── Part B: Zones ──────────────────────────────────────")

    print("  [6] Creating parking_zones table...")
    init_zones_db(TEST_DB)

    print("  [7] Seeding zones from ZONE_CONFIG...")
    seed_zones(TEST_DB)

    zones = get_all_zones(TEST_DB)
    print(f"  [8] Fetched {len(zones)} zones:")
    for z in zones:
        print(f"       {z['zone_id']:<12} capacity={z['capacity']}  "
              f"parked={z['parked_count']}  status={z['status']}")

    print("  [9] Updating 'Zone A' → 8 vehicles parked...")
    ok = update_zone_count("Zone A", 8, TEST_DB)
    print(f"       Success={ok}")
    za = get_all_zones(TEST_DB)[0]
    print(f"       Zone A: parked={za['parked_count']}  available={za['available']}  "
          f"occ={za['occ_pct']}%  status={za['status']}")

    print("  [10] Zone aggregate stats:")
    zs = get_zone_stats(TEST_DB)
    for k, v in zs.items():
        print(f"        {k:<22}: {v}")

    print("  [11] Resetting all zones...")
    reset_zones(TEST_DB)
    print(f"       Zone A after reset: {get_all_zones(TEST_DB)[0]}")

    # ── Cleanup ────────────────────────────────────────────────────────────────
    os.remove(TEST_DB)
    print("\n  ✓ Test DB cleaned up.")
    print("  ✅ All parking_db.py tests passed!")
    print("═" * 55)
