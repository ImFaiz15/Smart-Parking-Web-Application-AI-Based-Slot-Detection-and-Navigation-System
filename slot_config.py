"""
slot_config.py  –  Parking Slot Coordinate Configuration (Module 4)
─────────────────────────────────────────────────────────────────────────────
This file defines WHERE each parking slot is located on the image.

WHY is this needed?
  YOLOv8 tells us WHERE vehicles are detected in the image (bounding boxes).
  But it does NOT know which vehicle belongs to which parking slot.
  We need a "map" that says: "Slot A1 is in THIS region of the image."
  ai_detector.py then checks if a detected vehicle overlaps that region.

HOW coordinates work:
  All slot positions are stored as RELATIVE fractions (0.0 to 1.0).
  This means they are a percentage of the image width/height.

  Example:
      "A1": [0.02, 0.05, 0.24, 0.28]
       ↑ x1=2%   ↑ y1=5%   ↑ x2=24%  ↑ y2=28%
       of image width        of image height

  To convert to actual pixel coordinates at runtime:
      x1_px = x1_fraction × image_width
      y1_px = y1_fraction × image_height

  WHY fractions instead of pixels?
    Fractions work on any image resolution.
    Pixels would break if the image is resized.

HOW to adjust for your own parking lot image:
  1. Open your parking lot image in any image viewer.
  2. Note the total width (W) and height (H) in pixels.
  3. For each slot, identify its top-left and bottom-right corners.
  4. Calculate: x1 = corner_x / W,  y1 = corner_y / H
  5. Update the SLOT_COORDINATES dictionary below.
─────────────────────────────────────────────────────────────────────────────
"""

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 ─ THRESHOLDS
# ══════════════════════════════════════════════════════════════════════════════

# Minimum fraction of a slot that must be covered by a vehicle
# for it to be considered OCCUPIED.
#
# Example: OVERLAP_THRESHOLD = 0.15 means:
#   If a vehicle covers ≥ 15% of a slot's area → slot is OCCUPIED
#   If a vehicle covers  < 15% of a slot's area → slot is AVAILABLE
#
# Tune this value based on your image:
#   Lower (0.10) → more sensitive, marks slots occupied more easily
#   Higher (0.25) → less sensitive, needs more overlap to mark occupied
OVERLAP_THRESHOLD = 0.15

# Minimum YOLO confidence score to accept a vehicle detection.
# Detections below this score are ignored (considered noise/false positives).
#   0.35 = YOLO must be at least 35% confident it detected a vehicle.
YOLO_CONFIDENCE = 0.35

# YOLOv8 model file to use.
# 'yolov8n.pt' = Nano (fastest, smallest, good for student projects)
# 'yolov8s.pt' = Small (slightly more accurate, slightly slower)
MODEL_PATH = "yolov8n.pt"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 ─ SLOT COORDINATES
# ══════════════════════════════════════════════════════════════════════════════
#
# Layout (12 slots, 3 rows × 4 columns):
#
#   ┌──────────────────────────────────────────────────────────────┐
#   │  [A1]      [A2]      [A3]      [A4]       ← Row A (top)      │
#   │─────────────── DRIVE LANE ───────────────────────────────────│
#   │  [B1]      [B2]      [B3]      [B4]       ← Row B (middle)   │
#   │─────────────── DRIVE LANE ───────────────────────────────────│
#   │  [C1]      [C2]      [C3]      [C4]       ← Row C (bottom)   │
#   └──────────────────────────────────────────────────────────────┘
#
# Each value is [x1, y1, x2, y2] as fractions of the image dimensions.
# These defaults are set for a standard top-down parking lot view.
# ──────────────────────────────────────────────────────────────────────────────

SLOT_COORDINATES: dict = {

    # ── Row A (top region: y from 5% to 28% of image height) ──────────────────
    "A1": [0.02, 0.05, 0.23, 0.28],
    "A2": [0.27, 0.05, 0.48, 0.28],
    "A3": [0.52, 0.05, 0.73, 0.28],
    "A4": [0.77, 0.05, 0.98, 0.28],

    # ── Row B (middle region: y from 38% to 62% of image height) ──────────────
    "B1": [0.02, 0.38, 0.23, 0.62],
    "B2": [0.27, 0.38, 0.48, 0.62],
    "B3": [0.52, 0.38, 0.73, 0.62],
    "B4": [0.77, 0.38, 0.98, 0.62],

    # ── Row C (bottom region: y from 72% to 95% of image height) ─────────────
    "C1": [0.02, 0.72, 0.23, 0.95],
    "C2": [0.27, 0.72, 0.48, 0.95],
    "C3": [0.52, 0.72, 0.73, 0.95],
    "C4": [0.77, 0.72, 0.98, 0.95],
}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 ─ HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_absolute_coords(slot_id: str, image_width: int, image_height: int) -> list:
    """
    Converts the relative (fraction) slot coordinates to absolute pixel coordinates.

    WHY convert?
      OpenCV draws rectangles using pixel coordinates (integers), not fractions.
      So [0.02, 0.05, 0.23, 0.28] must become [16, 28, 184, 157] (for a 720×560 image).

    Parameters:
        slot_id      (str): Slot label like 'A1', 'B3'.
        image_width  (int): Width  of the image in pixels.
        image_height (int): Height of the image in pixels.

    Returns:
        list: [x1, y1, x2, y2] in absolute pixels, or None if slot_id not found.
    """
    if slot_id not in SLOT_COORDINATES:
        return None

    x1f, y1f, x2f, y2f = SLOT_COORDINATES[slot_id]

    # Multiply fraction by image dimension and round to nearest integer
    return [
        int(x1f * image_width),
        int(y1f * image_height),
        int(x2f * image_width),
        int(y2f * image_height),
    ]


def get_all_absolute_coords(image_width: int, image_height: int) -> dict:
    """
    Returns a dictionary of ALL slot IDs mapped to their absolute pixel coordinates.

    Used by ai_detector.py to iterate over all slots during detection.

    Parameters:
        image_width  (int): Width  of the image in pixels.
        image_height (int): Height of the image in pixels.

    Returns:
        dict: { 'A1': [x1, y1, x2, y2], 'A2': [...], ... }
    """
    return {
        slot_id: get_absolute_coords(slot_id, image_width, image_height)
        for slot_id in SLOT_COORDINATES
    }


def list_slot_ids() -> list:
    """
    Returns a sorted list of all configured slot IDs.

    Returns:
        list: e.g. ['A1', 'A2', 'A3', 'A4', 'B1', ...]
    """
    return sorted(SLOT_COORDINATES.keys())


# ══════════════════════════════════════════════════════════════════════════════
# SELF-TEST BLOCK
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("─" * 55)
    print("  slot_config.py  –  Self Test")
    print("─" * 55)

    # Simulate a 1280 × 720 pixel image
    W, H = 1280, 720

    print(f"\nImage size: {W} × {H} pixels\n")
    print(f"{'Slot ID':<10} {'Relative':<28} {'Absolute (px)'}")
    print("─" * 55)

    for slot_id in list_slot_ids():
        rel  = SLOT_COORDINATES[slot_id]
        abso = get_absolute_coords(slot_id, W, H)
        print(f"  {slot_id:<8} {str(rel):<28} {abso}")

    print(f"\nTotal slots configured: {len(SLOT_COORDINATES)}")
    print(f"Overlap threshold     : {OVERLAP_THRESHOLD} ({OVERLAP_THRESHOLD*100:.0f}%)")
    print(f"YOLO confidence       : {YOLO_CONFIDENCE} ({YOLO_CONFIDENCE*100:.0f}%)")
