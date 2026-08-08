"""
slot_config.py  –  Parking Slot & Zone Coordinate Configuration (Module 4)
─────────────────────────────────────────────────────────────────────────────
This file defines WHERE each parking slot / zone is located on the image.

SECTION 1  →  Detection thresholds (confidence, overlap)
SECTION 2  →  SLOT_COORDINATES  (individual slot boxes — kept for compatibility)
SECTION 3  →  ZONE_CONFIG       (zone boxes with capacity — used by Phase 4+)
SECTION 4  →  Helper functions for both slots and zones

HOW ZONE coordinates work:
  All positions are stored as RELATIVE fractions (0.0 to 1.0).
  This means they are percentages of the image width/height.

  Example:
      "Zone A": {"coords": [0.02, 0.05, 0.48, 0.45], "capacity": 10}
       x1=2%   y1=5%   x2=48%  y2=45%  of the image

  WHY fractions?
    Fractions work on ANY image resolution.
    Pixels would break if the image is resized or camera changes.

HOW to update ZONE_CONFIG:
  Run:  python draw_slots.py
  Click + drag rectangles on your parking image.
  Enter zone name + capacity. Press S to save.
  draw_slots.py will rewrite the ZONE_CONFIG block below automatically.
─────────────────────────────────────────────────────────────────────────────
"""

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 ─ DETECTION THRESHOLDS
# ══════════════════════════════════════════════════════════════════════════════

# Minimum fraction of a slot that must be covered by a vehicle bounding box
# for it to be considered OCCUPIED. (Used by slot-by-slot detection.)
# Lower  (0.10) → more sensitive  | Higher (0.25) → less sensitive
OVERLAP_THRESHOLD = 0.15

# Minimum YOLO confidence score to accept a vehicle detection.
# Detections below this value are treated as false positives.
YOLO_CONFIDENCE = 0.35

# YOLOv8 model file to use.
# 'best.pt'    = YOUR custom-trained model (in project root)
# 'yolov8n.pt' = Nano pretrained (auto-downloaded as fallback)
MODEL_PATH = "best.pt"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 ─ SLOT_COORDINATES  (kept for backward compatibility)
# ══════════════════════════════════════════════════════════════════════════════
# Layout (12 individual slots, 3 rows × 4 columns):
#
#   ┌──────────────────────────────────────────────────────────────┐
#   │  [A1]      [A2]      [A3]      [A4]       ← Row A (top)      │
#   │─────────────── DRIVE LANE ───────────────────────────────────│
#   │  [B1]      [B2]      [B3]      [B4]       ← Row B (middle)   │
#   │─────────────── DRIVE LANE ───────────────────────────────────│
#   │  [C1]      [C2]      [C3]      [C4]       ← Row C (bottom)   │
#   └──────────────────────────────────────────────────────────────┘
#
# Values: [x1, y1, x2, y2] as fractions of image dimensions (0.0 to 1.0)

SLOT_COORDINATES: dict = {
    # Row A — top region (y: 5% to 28%)
    "A1": [0.02, 0.05, 0.23, 0.28],
    "A2": [0.27, 0.05, 0.48, 0.28],
    "A3": [0.52, 0.05, 0.73, 0.28],
    "A4": [0.77, 0.05, 0.98, 0.28],

    # Row B — middle region (y: 38% to 62%)
    "B1": [0.02, 0.38, 0.23, 0.62],
    "B2": [0.27, 0.38, 0.48, 0.62],
    "B3": [0.52, 0.38, 0.73, 0.62],
    "B4": [0.77, 0.38, 0.98, 0.62],

    # Row C — bottom region (y: 72% to 95%)
    "C1": [0.02, 0.72, 0.23, 0.95],
    "C2": [0.27, 0.72, 0.48, 0.95],
    "C3": [0.52, 0.72, 0.73, 0.95],
    "C4": [0.77, 0.72, 0.98, 0.95],
}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 ─ ZONE_CONFIG  (Zone-based tracking — Phase 4)
# ══════════════════════════════════════════════════════════════════════════════
# These are DEFAULT zones. Run  python draw_slots.py  to replace them
# with zones drawn on YOUR actual parking image.
#
# Each zone covers a REGION of the parking lot.
# The detection engine counts how many vehicles are inside each region.
#
# Format:
#   "Zone Name": {
#       "coords"  : [x1, y1, x2, y2],   ← relative fractions (0.0 to 1.0)
#       "capacity": N,                   ← total parking spaces in this zone
#   }

ZONE_CONFIG: dict = {

    # ── Row A (y: 5% – 28%) ────────────────────────────────────────────────────
    "A1": {"coords": [0.02, 0.05, 0.23, 0.28], "capacity": 1},
    "A2": {"coords": [0.27, 0.05, 0.48, 0.28], "capacity": 1},
    "A3": {"coords": [0.52, 0.05, 0.73, 0.28], "capacity": 1},
    "A4": {"coords": [0.77, 0.05, 0.98, 0.28], "capacity": 1},

    # ── Row B (y: 38% – 62%) ────────────────────────────────────────────────────
    "B1": {"coords": [0.02, 0.38, 0.23, 0.62], "capacity": 1},
    "B2": {"coords": [0.27, 0.38, 0.48, 0.62], "capacity": 1},
    "B3": {"coords": [0.52, 0.38, 0.73, 0.62], "capacity": 1},
    "B4": {"coords": [0.77, 0.38, 0.98, 0.62], "capacity": 1},

    # ── Row C (y: 72% – 95%) ────────────────────────────────────────────────────
    "C1": {"coords": [0.02, 0.72, 0.23, 0.95], "capacity": 1},
    "C2": {"coords": [0.27, 0.72, 0.48, 0.95], "capacity": 1},
    "C3": {"coords": [0.52, 0.72, 0.73, 0.95], "capacity": 1},
    "C4": {"coords": [0.77, 0.72, 0.98, 0.95], "capacity": 1},
}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 ─ HELPER FUNCTIONS (Slots)
# ══════════════════════════════════════════════════════════════════════════════

def get_absolute_coords(slot_id: str, image_width: int, image_height: int) -> list:
    """
    Converts relative slot coordinates → absolute pixel coordinates.

    Parameters:
        slot_id      (str): e.g. 'A1', 'B3'
        image_width  (int): Image width in pixels.
        image_height (int): Image height in pixels.

    Returns:
        list: [x1, y1, x2, y2] in pixels, or None if slot_id not found.
    """
    if slot_id not in SLOT_COORDINATES:
        return None
    x1f, y1f, x2f, y2f = SLOT_COORDINATES[slot_id]
    return [
        int(x1f * image_width),
        int(y1f * image_height),
        int(x2f * image_width),
        int(y2f * image_height),
    ]


def get_all_absolute_coords(image_width: int, image_height: int) -> dict:
    """Returns all slot IDs → absolute pixel coords."""
    return {
        sid: get_absolute_coords(sid, image_width, image_height)
        for sid in SLOT_COORDINATES
    }


def list_slot_ids() -> list:
    """Returns sorted list of all individual slot IDs."""
    return sorted(SLOT_COORDINATES.keys())


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 ─ HELPER FUNCTIONS (Zones)
# ══════════════════════════════════════════════════════════════════════════════

def list_zone_ids() -> list:
    """Returns sorted list of all zone names from ZONE_CONFIG."""
    return sorted(ZONE_CONFIG.keys())


def get_zone_absolute_coords(zone_id: str, image_width: int, image_height: int) -> list:
    """
    Converts relative zone coords → absolute pixel coords.

    Parameters:
        zone_id      (str): Zone name, e.g. 'Zone A'.
        image_width  (int): Image width in pixels.
        image_height (int): Image height in pixels.

    Returns:
        list: [x1, y1, x2, y2] in pixels, or None if zone not found.
    """
    if zone_id not in ZONE_CONFIG:
        return None
    x1f, y1f, x2f, y2f = ZONE_CONFIG[zone_id]["coords"]
    return [
        int(x1f * image_width),
        int(y1f * image_height),
        int(x2f * image_width),
        int(y2f * image_height),
    ]


def get_all_zone_absolute_coords(image_width: int, image_height: int) -> dict:
    """Returns all zone IDs → absolute pixel coords."""
    return {
        zid: get_zone_absolute_coords(zid, image_width, image_height)
        for zid in ZONE_CONFIG
    }


def get_zone_capacity(zone_id: str) -> int:
    """Returns the capacity of a zone, or 0 if not found."""
    return ZONE_CONFIG.get(zone_id, {}).get("capacity", 0)


# ══════════════════════════════════════════════════════════════════════════════
# SELF-TEST BLOCK
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("─" * 60)
    print("  slot_config.py  –  Self Test")
    print("─" * 60)

    W, H = 1280, 720

    print(f"\n  Image size: {W} × {H} px\n")

    print("  ── Individual Slots ──────────────────────────────────")
    print(f"  {'Slot':<8} {'Relative':<32} {'Absolute (px)'}")
    print("  " + "─" * 55)
    for sid in list_slot_ids():
        rel  = SLOT_COORDINATES[sid]
        abso = get_absolute_coords(sid, W, H)
        print(f"  {sid:<8} {str(rel):<32} {abso}")

    print(f"\n  ── Zones ────────────────────────────────────────────")
    print(f"  {'Zone':<12} {'Capacity':<10} {'Relative Coords':<36} {'Absolute (px)'}")
    print("  " + "─" * 70)
    for zid in list_zone_ids():
        cap  = get_zone_capacity(zid)
        rel  = ZONE_CONFIG[zid]["coords"]
        abso = get_zone_absolute_coords(zid, W, H)
        print(f"  {zid:<12} {cap:<10} {str(rel):<36} {abso}")

    print(f"\n  Total slots : {len(SLOT_COORDINATES)}")
    print(f"  Total zones : {len(ZONE_CONFIG)}")
    print(f"  Total zone capacity: {sum(z['capacity'] for z in ZONE_CONFIG.values())}")
    print(f"  YOLO confidence  : {YOLO_CONFIDENCE}")
    print(f"  Overlap threshold: {OVERLAP_THRESHOLD}")
    print(f"  Model path       : {MODEL_PATH}")

# ══════════════════════════════════════════════════════════════════════════════
# ZONE_CONFIG — Generated by draw_slots.py
# Each zone has relative coords [x1, y1, x2, y2] (0.0 to 1.0) + capacity.
# Re-run draw_slots.py to update these values.
# ══════════════════════════════════════════════════════════════════════════════

ZONE_CONFIG: dict = {
    "A1": {
        "coords"  : [0.5164, 0.5917, 0.5491, 0.7056],
        "capacity": 1,
    },
}


def list_zone_ids() -> list:
    """Returns sorted list of all zone names from ZONE_CONFIG."""
    return sorted(ZONE_CONFIG.keys())


def get_zone_absolute_coords(zone_id: str, image_width: int, image_height: int) -> list:
    """Converts relative zone coords → absolute pixel coords."""
    if zone_id not in ZONE_CONFIG:
        return None
    x1f, y1f, x2f, y2f = ZONE_CONFIG[zone_id]["coords"]
    return [
        int(x1f * image_width),
        int(y1f * image_height),
        int(x2f * image_width),
        int(y2f * image_height),
    ]


def get_all_zone_absolute_coords(image_width: int, image_height: int) -> dict:
    """Returns all zone IDs mapped to absolute pixel coords."""
    return {
        zid: get_zone_absolute_coords(zid, image_width, image_height)
        for zid in ZONE_CONFIG
    }
