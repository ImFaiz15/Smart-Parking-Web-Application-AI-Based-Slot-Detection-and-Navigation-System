"""
backend.py  –  Central Backend Service Layer
─────────────────────────────────────────────────────────────────────────────
This file is the UNIFIED BACKEND of the Smart Parking project.

WHY this file exists:
  Without backend.py, each Streamlit app (auth_app, parking_app, ai_app)
  directly imports from multiple files (auth_db, auth, parking_db, ai_detector).
  This creates messy, tangled imports.

  backend.py acts as a SINGLE ENTRY POINT for all backend operations.
  Now any Streamlit app only needs:
      from backend import Backend
      api = Backend()

  This is called the "Service Layer" pattern — a clean boundary between
  the frontend (Streamlit UI) and the backend (database + AI logic).

Architecture with backend.py:
  ┌────────────────────────────────────────────────────────┐
  │                   FRONTEND (UI Layer)                  │
  │   auth_app.py   │   parking_app.py   │   ai_app.py    │
  └────────┬────────┴──────────┬─────────┴──────┬─────────┘
           │                   │                │
           ▼                   ▼                ▼
  ┌────────────────────────────────────────────────────────┐
  │                backend.py  (Service Layer)             │
  │                                                        │
  │   AuthService ─── register, login, logout              │
  │   ParkingService ─ get slots, stats, update, simulate  │
  │   DetectionService ─ load model, detect, sync to DB    │
  └────────┬───────────────────┬────────────────┬──────────┘
           │                   │                │
           ▼                   ▼                ▼
  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
  │  auth_db.py  │  │ parking_db.py│  │  ai_detector.py  │
  │   auth.py    │  │              │  │  slot_config.py   │
  └──────┬───────┘  └──────┬───────┘  └──────────────────┘
         │                 │
         ▼                 ▼
  ┌─────────────┐  ┌─────────────┐
  │  users.db   │  │ parking.db  │
  └─────────────┘  └─────────────┘

Run this file directly to self-test:
    python backend.py
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime

# ── Import all lower-level modules ────────────────────────────────────────────
# Authentication
from auth_db import init_users_db, get_user_by_email
from auth    import register_user, login_user, logout_user, hash_password, verify_password

# Parking
from parking_db import (
    init_parking_db,
    seed_slots,
    get_all_slots,
    get_slots_by_status,
    get_stats,
    update_slot_status,
    randomize_slots,
    STATUS_AVAILABLE,
    STATUS_OCCUPIED,
    STATUS_RESERVED,
)

# AI Detection
from ai_detector import (
    load_yolo_model,
    run_detection_pipeline,
)
from slot_config import (
    OVERLAP_THRESHOLD,
    YOLO_CONFIDENCE,
    MODEL_PATH,
    list_slot_ids,
)


# ══════════════════════════════════════════════════════════════════════════════
# CLASS 1 ─ AuthService
# ══════════════════════════════════════════════════════════════════════════════

class AuthService:
    """
    Handles all authentication-related operations.

    This class wraps the functions from auth.py and auth_db.py into
    a clean object-oriented interface.

    WHY a class?
      Classes group related functions (called "methods") together.
      Instead of importing 6 separate functions, you just do:
          auth = AuthService()
          auth.register(...)
          auth.login(...)
    """

    def __init__(self):
        """
        Initialises the user database on creation.
        Safe to call multiple times — creates table only if it doesn't exist.
        """
        init_users_db()

    def register(
        self,
        full_name: str,
        email: str,
        mobile: str,
        vehicle_number: str,
        password: str,
        confirm_password: str
    ) -> tuple:
        """
        Registers a new user after running all validations.

        Parameters:
            full_name, email, mobile, vehicle_number, password, confirm_password

        Returns:
            (True, "Success message")  →  registration succeeded
            (False, "Error message")   →  validation failed or duplicate found
        """
        return register_user(
            full_name, email, mobile, vehicle_number, password, confirm_password
        )

    def login(self, email: str, password: str) -> tuple:
        """
        Verifies user credentials.

        Returns:
            (True, user_dict)          →  credentials correct
            (False, "Error message")   →  wrong email or password
        """
        return login_user(email, password)

    def logout(self, session_state) -> None:
        """
        Clears the user session data (sets logged_in=False, user=None).

        Parameters:
            session_state:  Streamlit's st.session_state object.
        """
        logout_user(session_state)

    def get_user(self, email: str) -> dict | None:
        """
        Fetches a user record by email.

        Returns:
            dict with user info if found, None otherwise.
        """
        return get_user_by_email(email)


# ══════════════════════════════════════════════════════════════════════════════
# CLASS 2 ─ ParkingService
# ══════════════════════════════════════════════════════════════════════════════

class ParkingService:
    """
    Handles all parking slot database operations.

    Wraps parking_db.py functions into a clean interface.
    """

    # Make status constants accessible as class attributes
    AVAILABLE = STATUS_AVAILABLE   # "available"
    OCCUPIED  = STATUS_OCCUPIED    # "occupied"
    RESERVED  = STATUS_RESERVED    # "reserved"

    def __init__(self, rows: int = 3, cols: int = 4):
        """
        Initialises the parking database and seeds slots if empty.

        Parameters:
            rows (int): Number of parking rows (A, B, C...).
            cols (int): Slots per row.
        """
        init_parking_db()
        seed_slots(total_rows=rows, cols=cols)

    def get_all(self) -> list:
        """
        Returns all parking slots ordered by row and column.

        Returns:
            list of dicts: [{'slot_id': 'A1', 'status': 'available', ...}, ...]
        """
        return get_all_slots()

    def get_filtered(self, status: str) -> list:
        """
        Returns only slots matching a specific status.

        Parameters:
            status (str): 'available', 'occupied', or 'reserved'.
        """
        return get_slots_by_status(status)

    def get_stats(self) -> dict:
        """
        Returns aggregate counts: total, available, occupied, reserved.

        Returns:
            dict: {'total': 12, 'available': 6, 'occupied': 4, 'reserved': 2}
        """
        return get_stats()

    def update(self, slot_id: str, status: str, vehicle_number: str = None) -> bool:
        """
        Updates a single slot's status.

        Parameters:
            slot_id        (str): e.g. 'A1', 'B3'
            status         (str): 'available', 'occupied', or 'reserved'
            vehicle_number (str): Vehicle plate (only for occupied slots)

        Returns:
            bool: True if the slot was found and updated.
        """
        return update_slot_status(slot_id, status, vehicle_number)

    def simulate(self) -> None:
        """
        Randomly re-assigns statuses to all slots.
        Used by the 'Simulate' button in parking_app.py.
        """
        randomize_slots()

    def get_occupancy_rate(self) -> float:
        """
        Returns the current occupancy percentage (0.0 to 100.0).

        Returns:
            float: e.g. 66.7 means 66.7% of slots are occupied.
        """
        stats = self.get_stats()
        total = stats["total"]
        if total == 0:
            return 0.0
        return round((stats[STATUS_OCCUPIED] / total) * 100, 1)


# ══════════════════════════════════════════════════════════════════════════════
# CLASS 3 ─ DetectionService
# ══════════════════════════════════════════════════════════════════════════════

class DetectionService:
    """
    Handles all AI detection operations.

    Wraps ai_detector.py and slot_config.py into a clean interface.
    """

    def __init__(self):
        """
        Stores config values. Does NOT load the model automatically —
        call load_model() explicitly (so Streamlit can cache it).
        """
        self.model            = None
        self.model_path       = MODEL_PATH
        self.confidence       = YOLO_CONFIDENCE
        self.overlap_threshold = OVERLAP_THRESHOLD

    def load_model(self) -> None:
        """
        Loads the YOLOv8 model into memory.
        Auto-downloads weights (~6 MB) on first run.
        """
        self.model = load_yolo_model(self.model_path)

    def is_model_loaded(self) -> bool:
        """Returns True if the YOLO model has been loaded."""
        return self.model is not None

    def detect(self, image_bytes: bytes) -> tuple:
        """
        Runs the full AI detection pipeline on an uploaded image.

        Parameters:
            image_bytes (bytes): Raw bytes from Streamlit's file_uploader.

        Returns:
            tuple of 4 items:
              original_image  (ndarray) : Raw image
              annotated_image (ndarray) : Image with boxes drawn
              slot_results    (dict)    : Per-slot status + overlap info
              detections      (list)    : Raw YOLO vehicle detections

        Returns (None, None, None, None) if image decoding fails.
        """
        if not self.is_model_loaded():
            self.load_model()

        return run_detection_pipeline(image_bytes, self.model)

    def sync_to_database(self, slot_results: dict) -> dict:
        """
        Writes AI detection results to the SQLite parking database.

        For each slot in slot_results, calls update_slot_status().
        Only writes 'available' and 'occupied' — reserved slots are untouched.

        Parameters:
            slot_results (dict): Output of detect() — per-slot status dict.

        Returns:
            dict: Summary of the sync operation.
                  {'updated': 12, 'failed': [], 'timestamp': '...'}
        """
        updated = 0
        failed  = []

        for slot_id, result in slot_results.items():
            status     = result["status"]
            vehicle_no = result.get("matched_vehicle") if status == STATUS_OCCUPIED else None

            success = update_slot_status(slot_id, status, vehicle_no)
            if success:
                updated += 1
            else:
                failed.append(slot_id)

        return {
            "updated"  : updated,
            "failed"   : failed,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def get_slot_ids(self) -> list:
        """Returns all configured slot IDs from slot_config.py."""
        return list_slot_ids()

    def get_config(self) -> dict:
        """
        Returns the current AI configuration as a dictionary.
        Useful for displaying in the sidebar or debug panels.
        """
        return {
            "model"             : self.model_path,
            "confidence"        : f"{self.confidence * 100:.0f}%",
            "overlap_threshold" : f"{self.overlap_threshold * 100:.0f}%",
            "total_slots"       : len(list_slot_ids()),
            "model_loaded"      : self.is_model_loaded(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# CLASS 4 ─ Backend (Master Class)
# ══════════════════════════════════════════════════════════════════════════════

class Backend:
    """
    MASTER CLASS — single entry point for the entire backend.

    Usage in any Streamlit app:
        from backend import Backend
        api = Backend()

        # Authentication
        api.auth.register(...)
        api.auth.login(...)

        # Parking
        api.parking.get_all()
        api.parking.get_stats()

        # AI Detection
        api.detection.detect(image_bytes)
        api.detection.sync_to_database(results)

    WHY a master class?
      Instead of creating 3 separate service objects, you create ONE.
      Cleaner code. Easier to explain in a viva.
    """

    def __init__(self, parking_rows: int = 3, parking_cols: int = 4):
        """
        Initialises all three service layers.

        Parameters:
            parking_rows (int): Number of parking rows to seed.
            parking_cols (int): Slots per row to seed.
        """
        self.auth      = AuthService()
        self.parking   = ParkingService(rows=parking_rows, cols=parking_cols)
        self.detection = DetectionService()

    def get_system_status(self) -> dict:
        """
        Returns a health check / status summary of the entire backend.
        Useful for a dashboard "system info" panel.

        Returns:
            dict: System status including stats, model info, and timestamp.
        """
        stats = self.parking.get_stats()
        return {
            "status"         : "online",
            "timestamp"      : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "parking_stats"  : stats,
            "occupancy_rate" : self.parking.get_occupancy_rate(),
            "ai_config"      : self.detection.get_config(),
            "total_slots"    : stats["total"],
        }


# ══════════════════════════════════════════════════════════════════════════════
# SELF-TEST BLOCK
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("═" * 60)
    print("  backend.py  –  Smart Parking Backend Self Test")
    print("═" * 60)

    # ── Initialise backend ─────────────────────────────────────────────────────
    api = Backend()
    print("\n✓ Backend initialised (auth + parking + detection)")

    # ── Test 1: System status ──────────────────────────────────────────────────
    print("\n── Test 1: System Status ──────────────────────────")
    status = api.get_system_status()
    print(f"  Status         : {status['status']}")
    print(f"  Timestamp      : {status['timestamp']}")
    print(f"  Total Slots    : {status['total_slots']}")
    print(f"  Occupancy Rate : {status['occupancy_rate']}%")

    # ── Test 2: Parking service ────────────────────────────────────────────────
    print("\n── Test 2: Parking Service ────────────────────────")
    stats = api.parking.get_stats()
    print(f"  Available : {stats['available']}")
    print(f"  Occupied  : {stats['occupied']}")
    print(f"  Reserved  : {stats['reserved']}")
    print(f"  Total     : {stats['total']}")

    all_slots = api.parking.get_all()
    print(f"  Fetched {len(all_slots)} slots from DB")

    # ── Test 3: Auth service ───────────────────────────────────────────────────
    print("\n── Test 3: Auth Service ───────────────────────────")
    ok, msg = api.auth.register(
        full_name="Backend Test",
        email="backendtest@example.com",
        mobile="9123456789",
        vehicle_number="MH99ZZ0001",
        password="TestPass@123",
        confirm_password="TestPass@123",
    )
    print(f"  Register → ok={ok}, msg={msg}")

    ok2, result = api.auth.login("backendtest@example.com", "TestPass@123")
    print(f"  Login    → ok={ok2}, name={result.get('full_name') if ok2 else result}")

    # Cleanup test user
    import sqlite3
    conn = sqlite3.connect("users.db")
    conn.execute("DELETE FROM users WHERE email='backendtest@example.com'")
    conn.commit()
    conn.close()
    print("  ✓ Test user cleaned up")

    # ── Test 4: Detection service config ───────────────────────────────────────
    print("\n── Test 4: Detection Service ──────────────────────")
    config = api.detection.get_config()
    for k, v in config.items():
        print(f"  {k:22}: {v}")

    slot_ids = api.detection.get_slot_ids()
    print(f"  Configured slots: {slot_ids}")

    # ── Test 5: Simulate parking change ────────────────────────────────────────
    print("\n── Test 5: Simulate Parking Change ────────────────")
    api.parking.simulate()
    new_stats = api.parking.get_stats()
    new_rate  = api.parking.get_occupancy_rate()
    print(f"  After simulation → {new_stats}")
    print(f"  Occupancy rate   → {new_rate}%")

    print("\n" + "═" * 60)
    print("  ✅ All backend tests passed!")
    print("═" * 60)
