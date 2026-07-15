"""
parking_db.py  –  Parking Slots Database Handler (Module 3)
─────────────────────────────────────────────────────────────────────────────
This file manages ALL database operations for the parking slot system.

It is an upgraded version of database.py with:
  - Three slot statuses: 'available', 'occupied', 'reserved'
  - Vehicle number tracking for occupied slots
  - A seeder that creates realistic simulated data on first run
  - Stat aggregation (counts per status)
  - A randomizer for live simulation without AI

WHY a separate file from database.py?
  The original database.py uses only 0/1 (binary status).
  Module 3 needs a third state (reserved) and richer queries.
  Keeping them separate avoids breaking earlier work.
─────────────────────────────────────────────────────────────────────────────
"""

import sqlite3
import random
from datetime import datetime

# ── Constants ─────────────────────────────────────────────────────────────────
PARKING_DB_PATH = "parking.db"       # Separate DB file for parking slots
GRID_ROWS       = "ABCDE"            # Supported row labels (up to 5 rows = 20 slots)
GRID_COLS       = 4                  # Slots per row

# Valid status values — using strings instead of 0/1 for readability
STATUS_AVAILABLE = "available"
STATUS_OCCUPIED  = "occupied"
STATUS_RESERVED  = "reserved"

# Simulated vehicle numbers (used for seeding occupied slots)
FAKE_VEHICLES = [
    "MH01AB1234", "DL4CAF0001", "KA02XY9999", "TN09CD5678",
    "GJ05EF3456", "UP32GH7890", "RJ14IJ2345", "HR26KL6789",
    "MH12MN3456", "MP09OP7890", "AP28QR4567", "TS07ST8901",
    "WB20UV5678", "PB10WX9012", "CG07YZ3456", "BR01AA6789",
    "OR02BB0123", "JK01CC4567", "HP34DD8901", "UK07EE2345",
]


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 1 ─ init_parking_db
# ══════════════════════════════════════════════════════════════════════════════

def init_parking_db(db_path: str = PARKING_DB_PATH) -> None:
    """
    Creates the 'parking_slots' table in the database if it does not exist.

    Table columns:
    ┌────────────────┬──────────────────────────────────────────────────────────┐
    │ Column         │ Description                                              │
    ├────────────────┼──────────────────────────────────────────────────────────┤
    │ slot_id        │ Primary key. Unique label like 'A1', 'B3'. (TEXT)       │
    │ slot_row       │ Row letter: 'A', 'B', 'C'... Used for grouping. (TEXT)  │
    │ slot_number    │ Column position: 1, 2, 3, 4. (INTEGER)                  │
    │ status         │ 'available' | 'occupied' | 'reserved'. (TEXT)           │
    │ vehicle_number │ Vehicle plate if occupied, NULL otherwise. (TEXT)        │
    │ last_updated   │ Timestamp of last status change. (TEXT)                 │
    └────────────────┴──────────────────────────────────────────────────────────┘

    Parameters:
        db_path (str): Path to the SQLite database file.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
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


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 2 ─ seed_slots
# ══════════════════════════════════════════════════════════════════════════════

def seed_slots(
    total_rows: int = 3,
    cols: int = GRID_COLS,
    db_path: str = PARKING_DB_PATH
) -> None:
    """
    Populates the parking_slots table with simulated slot data.

    This function runs only if the table is EMPTY (no existing slots).
    It creates a realistic mix of statuses:
      - ~50% available  (green)
      - ~35% occupied   (red)   with a fake vehicle number
      - ~15% reserved   (grey)

    Parameters:
        total_rows (int): Number of parking rows (A, B, C ...).
        cols       (int): Number of slots per row.
        db_path    (str): Path to the database file.

    Example for total_rows=3, cols=4:
        Creates 12 slots: A1, A2, A3, A4, B1, B2, B3, B4, C1, C2, C3, C4
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if slots already exist — don't overwrite on every app restart
    cursor.execute("SELECT COUNT(*) FROM parking_slots")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return   # Already seeded — skip

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    vehicle_pool = FAKE_VEHICLES.copy()
    random.shuffle(vehicle_pool)

    rows_to_insert = []
    vehicle_index  = 0

    for row_idx in range(total_rows):
        row_letter = GRID_ROWS[row_idx]   # 0→'A', 1→'B', 2→'C'

        for col_num in range(1, cols + 1):
            slot_id = f"{row_letter}{col_num}"   # e.g. 'A1', 'B3'

            # Weighted random status assignment
            # random.choices picks one item from the list based on weights.
            # weights=[50, 35, 15] means: 50% available, 35% occupied, 15% reserved
            status = random.choices(
                population=[STATUS_AVAILABLE, STATUS_OCCUPIED, STATUS_RESERVED],
                weights=[50, 35, 15],
                k=1
            )[0]

            # Assign a fake vehicle number if the slot is occupied
            vehicle_number = None
            if status == STATUS_OCCUPIED:
                vehicle_number = vehicle_pool[vehicle_index % len(vehicle_pool)]
                vehicle_index += 1

            rows_to_insert.append((
                slot_id, row_letter, col_num, status, vehicle_number, timestamp
            ))

    # executemany inserts all rows in a single efficient database call
    cursor.executemany("""
        INSERT OR IGNORE INTO parking_slots
            (slot_id, slot_row, slot_number, status, vehicle_number, last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
    """, rows_to_insert)

    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 3 ─ get_all_slots
# ══════════════════════════════════════════════════════════════════════════════

def get_all_slots(db_path: str = PARKING_DB_PATH) -> list:
    """
    Retrieves all parking slots ordered by row then column number.

    Returns:
        list of dicts: One dict per slot.

        Example:
        [
            {
                'slot_id'       : 'A1',
                'slot_row'      : 'A',
                'slot_number'   : 1,
                'status'        : 'available',
                'vehicle_number': None,
                'last_updated'  : '2026-07-08 11:30:00'
            },
            ...
        ]
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row   # Makes rows accessible like dicts
    cursor = conn.cursor()

    cursor.execute("""
        SELECT slot_id, slot_row, slot_number, status, vehicle_number, last_updated
        FROM parking_slots
        ORDER BY slot_row ASC, slot_number ASC
    """)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 4 ─ get_slots_by_status
# ══════════════════════════════════════════════════════════════════════════════

def get_slots_by_status(status: str, db_path: str = PARKING_DB_PATH) -> list:
    """
    Returns only the slots that match a specific status.
    Used by the dashboard's filter feature.

    Parameters:
        status  (str): One of 'available', 'occupied', 'reserved'.
        db_path (str): Path to the database file.

    Returns:
        list of dicts: Filtered slot records.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT slot_id, slot_row, slot_number, status, vehicle_number, last_updated
        FROM parking_slots
        WHERE status = ?
        ORDER BY slot_row ASC, slot_number ASC
    """, (status,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 5 ─ get_stats
# ══════════════════════════════════════════════════════════════════════════════

def get_stats(db_path: str = PARKING_DB_PATH) -> dict:
    """
    Returns a summary count of slots grouped by status.
    Used to render the stats cards at the top of the dashboard.

    Parameters:
        db_path (str): Path to the database file.

    Returns:
        dict: Counts for each status plus the total.

        Example:
        {
            'total'    : 12,
            'available': 6,
            'occupied' : 4,
            'reserved' : 2
        }
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # GROUP BY groups rows with the same status together.
    # COUNT(*) counts how many rows are in each group.
    cursor.execute("""
        SELECT status, COUNT(*) AS count
        FROM parking_slots
        GROUP BY status
    """)

    rows = cursor.fetchall()
    conn.close()

    # Build a dictionary with default 0 for any status that has no rows
    stats = {
        STATUS_AVAILABLE: 0,
        STATUS_OCCUPIED : 0,
        STATUS_RESERVED : 0,
    }

    for row in rows:
        status, count = row
        stats[status]  = count

    stats["total"] = sum(stats.values())
    return stats


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 6 ─ update_slot_status
# ══════════════════════════════════════════════════════════════════════════════

def update_slot_status(
    slot_id: str,
    new_status: str,
    vehicle_number: str = None,
    db_path: str = PARKING_DB_PATH
) -> bool:
    """
    Updates the status (and optional vehicle number) of a specific slot.
    Called in Phase 3 when the AI detector reports a slot change.

    Parameters:
        slot_id        (str): The slot to update (e.g., 'B2').
        new_status     (str): New status: 'available', 'occupied', 'reserved'.
        vehicle_number (str): Vehicle plate if status is 'occupied'. None otherwise.
        db_path        (str): Path to the database file.

    Returns:
        bool: True if successful, False if slot_id was not found.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE parking_slots
        SET status = ?, vehicle_number = ?, last_updated = ?
        WHERE slot_id = ?
    """, (new_status, vehicle_number, timestamp, slot_id))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 7 ─ randomize_slots
# ══════════════════════════════════════════════════════════════════════════════

def randomize_slots(db_path: str = PARKING_DB_PATH) -> None:
    """
    Re-randomizes the status of ALL slots to simulate changing conditions.

    This is used by the dashboard's 'Simulate Change' button.
    In Module 4, this function will be replaced by real YOLOv8 detection output.

    Parameters:
        db_path (str): Path to the database file.
    """
    all_slots    = get_all_slots(db_path)
    timestamp    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    vehicle_pool = FAKE_VEHICLES.copy()
    random.shuffle(vehicle_pool)
    vehicle_idx  = 0

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for slot in all_slots:
        new_status = random.choices(
            population=[STATUS_AVAILABLE, STATUS_OCCUPIED, STATUS_RESERVED],
            weights=[50, 35, 15],
            k=1
        )[0]

        vehicle_number = None
        if new_status == STATUS_OCCUPIED:
            vehicle_number = vehicle_pool[vehicle_idx % len(vehicle_pool)]
            vehicle_idx += 1

        cursor.execute("""
            UPDATE parking_slots
            SET status = ?, vehicle_number = ?, last_updated = ?
            WHERE slot_id = ?
        """, (new_status, vehicle_number, timestamp, slot["slot_id"]))

    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# SELF-TEST BLOCK
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import os

    TEST_DB = "test_parking.db"

    print("─" * 50)
    print("  parking_db.py  –  Self Test")
    print("─" * 50)

    print("\n[1] Initialising database...")
    init_parking_db(TEST_DB)

    print("[2] Seeding 12 slots (3 rows × 4 cols)...")
    seed_slots(total_rows=3, cols=4, db_path=TEST_DB)

    print("[3] Fetching all slots:")
    for s in get_all_slots(TEST_DB):
        veh = f"  [{s['vehicle_number']}]" if s["vehicle_number"] else ""
        print(f"    {s['slot_id']}  →  {s['status']:10}{veh}")

    print("\n[4] Stats:")
    stats = get_stats(TEST_DB)
    for k, v in stats.items():
        print(f"    {k:12} : {v}")

    print("\n[5] Updating slot A1 to 'reserved'...")
    update_slot_status("A1", STATUS_RESERVED, db_path=TEST_DB)
    print(f"    A1 → {get_slots_by_status(STATUS_RESERVED, TEST_DB)}")

    print("\n[6] Randomizing all slots...")
    randomize_slots(TEST_DB)
    stats2 = get_stats(TEST_DB)
    print(f"    New stats: {stats2}")

    os.remove(TEST_DB)
    print("\n✓ Test DB cleaned up. All tests passed!")
