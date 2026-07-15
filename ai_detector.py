"""
ai_detector.py  –  AI Vehicle Detection Pipeline (Module 4)
─────────────────────────────────────────────────────────────────────────────
This file is the CORE of Module 4. It contains all the AI + Computer Vision
logic that decides which parking slots are occupied.

Responsibilities:
  1. Load the YOLOv8 pretrained model.
  2. Read and preprocess an uploaded image.
  3. Run vehicle detection using YOLOv8.
  4. For each parking slot, calculate the overlap between the slot region
     and any detected vehicle bounding box.
  5. Mark each slot as 'occupied' or 'available' based on overlap ratio.
  6. Draw annotated results onto the image for visual output.

KEY CONCEPT — Overlap Ratio:
  ┌─────────────────────────────────────────────────────────────┐
  │                                                             │
  │  Slot Box  ┌──────────────────┐                            │
  │            │    Slot Area     │                            │
  │            │   ┌─────────────┼────────┐ ← Vehicle Box     │
  │            │   │ Intersection│        │                    │
  │            │   │    Area     │        │                    │
  │            └───┼─────────────┘        │                    │
  │                └────────────────────  │                    │
  │                                                             │
  │  Overlap Ratio = Intersection Area / Slot Area              │
  │  If Overlap Ratio > threshold (e.g. 0.15) → OCCUPIED        │
  │                                                             │
  └─────────────────────────────────────────────────────────────┘

WHY Overlap Ratio instead of standard IoU?
  Standard IoU = Intersection / Union (penalises large vehicles).
  Overlap Ratio = Intersection / Slot Area answers the more useful question:
  "What fraction of THIS SLOT is covered by a vehicle?"
  A vehicle covering 15% of a slot is enough to call it occupied.
─────────────────────────────────────────────────────────────────────────────
"""

import cv2
import numpy as np
from ultralytics import YOLO

# Import our slot configuration
from slot_config import (
    get_all_absolute_coords,
    OVERLAP_THRESHOLD,
    YOLO_CONFIDENCE,
    MODEL_PATH,
)

# ── COCO class IDs for vehicles (same as detector.py) ─────────────────────────
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

# ── Status strings (must match parking_db.py) ─────────────────────────────────
STATUS_AVAILABLE = "available"
STATUS_OCCUPIED  = "occupied"

# ── Annotation colours (OpenCV uses BGR, not RGB) ──────────────────────────────
# Slot rectangle colours
COLOR_AVAILABLE = (34, 197, 94)    # Green  — available slot border
COLOR_OCCUPIED  = (59,  50, 220)   # Red    — occupied slot border  (BGR: R=220)
COLOR_VEHICLE   = (0,  210, 255)   # Yellow — detected vehicle box

# Fill overlay transparency (0.0 = invisible, 1.0 = fully opaque)
FILL_ALPHA = 0.25


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 1 ─ load_yolo_model
# ══════════════════════════════════════════════════════════════════════════════

def load_yolo_model(model_path: str = MODEL_PATH) -> YOLO:
    """
    Loads the YOLOv8 pretrained model from disk.

    On the first run, Ultralytics auto-downloads the weights from the internet
    (~6 MB for yolov8n.pt) and saves them locally for future use.

    WHY a separate function?
      Loading the model is slow (~2 seconds). By putting it here, ai_app.py
      can cache it with @st.cache_resource so it loads only ONCE per session.

    Parameters:
        model_path (str): Path to the .pt weights file. Default is 'yolov8n.pt'.

    Returns:
        YOLO: A ready-to-use YOLO model object.
    """
    print(f"[INFO] Loading YOLOv8 model: {model_path}")
    model = YOLO(model_path)
    print("[INFO] Model ready.")
    return model


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 2 ─ bytes_to_image
# ══════════════════════════════════════════════════════════════════════════════

def bytes_to_image(image_bytes: bytes) -> np.ndarray:
    """
    Converts raw image bytes (from a Streamlit file uploader) into an
    OpenCV NumPy array.

    WHY not use cv2.imread()?
      Streamlit's st.file_uploader() returns bytes in memory, not a file path.
      cv2.imread() only works with file paths.
      np.frombuffer() + cv2.imdecode() solves this — they work with in-memory bytes.

    Parameters:
        image_bytes (bytes): Raw bytes from an uploaded image file.

    Returns:
        numpy.ndarray: A BGR image array of shape (height, width, 3).
                       Returns None if the bytes are invalid.
    """
    # Step 1: Interpret the bytes as a 1-D NumPy array of unsigned 8-bit integers
    nparr = np.frombuffer(image_bytes, np.uint8)

    # Step 2: Decode the NumPy byte array into a full colour image
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        print("[ERROR] Could not decode image bytes. Invalid or corrupted file.")
    return image


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 3 ─ detect_vehicles
# ══════════════════════════════════════════════════════════════════════════════

def detect_vehicles(image: np.ndarray, model: YOLO) -> list:
    """
    Runs YOLOv8 inference on the image and returns only vehicle detections.

    YOLOv8 detects all 80 COCO classes. We filter to keep only:
      Class  2 → car
      Class  3 → motorcycle
      Class  5 → bus
      Class  7 → truck

    Parameters:
        image (numpy.ndarray): BGR image from bytes_to_image().
        model (YOLO): Loaded YOLO model from load_yolo_model().

    Returns:
        list of dicts: Each dict represents one detected vehicle.

        Example:
        [
            {
                "class_name" : "car",
                "confidence" : 0.87,
                "box"        : [120, 45, 310, 200]   ← [x1, y1, x2, y2] in pixels
            },
            ...
        ]
    """
    # Run the model — verbose=False suppresses per-frame console output
    results = model(image, verbose=False)

    detections = []

    # results[0].boxes contains all detected bounding boxes for the first image
    for box in results[0].boxes:
        class_id = int(box.cls[0])

        # Skip non-vehicle classes
        if class_id not in VEHICLE_CLASSES:
            continue

        confidence = float(box.conf[0])

        # Skip low-confidence detections
        if confidence < YOLO_CONFIDENCE:
            continue

        # Extract pixel coordinates
        x1, y1, x2, y2 = box.xyxy[0]

        detections.append({
            "class_name" : VEHICLE_CLASSES[class_id],
            "confidence" : round(confidence, 3),
            "box"        : [int(x1), int(y1), int(x2), int(y2)],
        })

    return detections


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 4 ─ calculate_overlap_ratio
# ══════════════════════════════════════════════════════════════════════════════

def calculate_overlap_ratio(vehicle_box: list, slot_box: list) -> float:
    """
    Calculates what fraction of the SLOT is covered by the VEHICLE.

    Formula:
        overlap_ratio = intersection_area / slot_area

    Step-by-step:
      1. Find the overlapping rectangle between the vehicle box and the slot box.
      2. Calculate its area (Intersection Area).
      3. Divide by the slot's total area.

    If the boxes do not overlap at all → returns 0.0.
    If the vehicle perfectly fills the slot → returns 1.0.

    Parameters:
        vehicle_box (list): [x1, y1, x2, y2] of detected vehicle in pixels.
        slot_box    (list): [x1, y1, x2, y2] of parking slot in pixels.

    Returns:
        float: Overlap ratio between 0.0 and 1.0.
    """
    # Unpack coordinates for clarity
    vx1, vy1, vx2, vy2 = vehicle_box
    sx1, sy1, sx2, sy2 = slot_box

    # ── Step 1: Find the intersection rectangle ────────────────────────────────
    # The overlapping region's top-left is the MAXIMUM of both top-lefts.
    # The overlapping region's bottom-right is the MINIMUM of both bottom-rights.
    ix1 = max(vx1, sx1)   # left  edge of intersection
    iy1 = max(vy1, sy1)   # top   edge of intersection
    ix2 = min(vx2, sx2)   # right edge of intersection
    iy2 = min(vy2, sy2)   # bottom edge of intersection

    # ── Step 2: Check if there actually IS an intersection ────────────────────
    # If ix2 <= ix1 or iy2 <= iy1, the rectangles don't overlap.
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    # ── Step 3: Calculate intersection area ───────────────────────────────────
    intersection_area = (ix2 - ix1) * (iy2 - iy1)

    # ── Step 4: Calculate slot area ───────────────────────────────────────────
    slot_area = (sx2 - sx1) * (sy2 - sy1)

    if slot_area <= 0:
        return 0.0

    # ── Step 5: Compute ratio ─────────────────────────────────────────────────
    return intersection_area / slot_area


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 5 ─ check_all_slots
# ══════════════════════════════════════════════════════════════════════════════

def check_all_slots(
    detections: list,
    abs_slot_coords: dict,
    threshold: float = OVERLAP_THRESHOLD
) -> dict:
    """
    Checks every parking slot against all detected vehicles.

    For each slot, it loops through ALL detected vehicles and calculates
    the overlap ratio. If ANY vehicle overlaps the slot above the threshold,
    the slot is marked 'occupied'. Otherwise it stays 'available'.

    Parameters:
        detections      (list): Output of detect_vehicles() — list of vehicle dicts.
        abs_slot_coords (dict): Output of get_all_absolute_coords() — slot pixel boxes.
        threshold       (float): Minimum overlap ratio to mark a slot as occupied.

    Returns:
        dict: Maps slot_id → result dict.

        Example:
        {
            "A1": {
                "status"          : "occupied",
                "overlap_ratio"   : 0.42,
                "matched_vehicle" : "car",
                "confidence"      : 0.87
            },
            "A2": {
                "status"          : "available",
                "overlap_ratio"   : 0.0,
                "matched_vehicle" : None,
                "confidence"      : None
            },
            ...
        }
    """
    slot_results = {}

    for slot_id, slot_box in abs_slot_coords.items():

        # Track the best-matching vehicle for this slot
        best_overlap    = 0.0
        best_vehicle    = None
        best_confidence = None

        # Compare this slot against every detected vehicle
        for det in detections:
            overlap = calculate_overlap_ratio(det["box"], slot_box)

            # Keep track of the vehicle with the highest overlap for this slot
            if overlap > best_overlap:
                best_overlap    = overlap
                best_vehicle    = det["class_name"]
                best_confidence = det["confidence"]

        # Decide status based on whether best overlap exceeds threshold
        status = STATUS_OCCUPIED if best_overlap >= threshold else STATUS_AVAILABLE

        slot_results[slot_id] = {
            "status"          : status,
            "overlap_ratio"   : round(best_overlap, 3),
            "matched_vehicle" : best_vehicle,
            "confidence"      : best_confidence,
        }

    return slot_results


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 6 ─ annotate_image
# ══════════════════════════════════════════════════════════════════════════════

def annotate_image(
    image: np.ndarray,
    slot_results: dict,
    abs_slot_coords: dict,
    detections: list
) -> np.ndarray:
    """
    Draws all visual annotations onto a COPY of the image.

    Draws:
      1. Slot rectangles:
           - Semi-transparent green fill + green border → Available
           - Semi-transparent red fill   + red border   → Occupied
           - Slot ID label (e.g. 'A1') inside the rectangle

      2. Detected vehicle bounding boxes:
           - Yellow/cyan border with class name and confidence label

    Parameters:
        image           (np.ndarray): Original BGR image.
        slot_results    (dict): Output of check_all_slots().
        abs_slot_coords (dict): Absolute pixel slot coordinates.
        detections      (list): Detected vehicle list from detect_vehicles().

    Returns:
        numpy.ndarray: Annotated image (does NOT modify the original).
    """
    # Work on a copy to preserve the original image
    annotated = image.copy()
    h, w = image.shape[:2]

    # ── Step 1: Draw slot rectangles ──────────────────────────────────────────
    # We use an overlay for semi-transparent fills.
    # cv2.addWeighted blends the filled overlay with the original image.
    overlay = annotated.copy()

    for slot_id, result in slot_results.items():
        box = abs_slot_coords[slot_id]
        x1, y1, x2, y2 = box

        # Choose colour based on status
        color = COLOR_AVAILABLE if result["status"] == STATUS_AVAILABLE else COLOR_OCCUPIED

        # Draw filled semi-transparent rectangle on the overlay
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, thickness=-1)

    # Blend overlay with the annotated image (FILL_ALPHA controls transparency)
    cv2.addWeighted(overlay, FILL_ALPHA, annotated, 1 - FILL_ALPHA, 0, annotated)

    # Now draw solid borders and text labels on top of the blended image
    for slot_id, result in slot_results.items():
        box = abs_slot_coords[slot_id]
        x1, y1, x2, y2 = box

        color  = COLOR_AVAILABLE if result["status"] == STATUS_AVAILABLE else COLOR_OCCUPIED
        status_icon = "✓" if result["status"] == STATUS_AVAILABLE else "✗"

        # Solid border rectangle (thickness=2)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness=2)

        # ── Slot ID label background ───────────────────────────────────────────
        label      = f" {slot_id} {status_icon} "
        font       = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.45, min(w, h) / 1600)   # Scale font with image size
        thickness  = 1

        (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)
        label_y = y1 + th + 6

        # Dark background pill for the text (improves readability)
        cv2.rectangle(annotated, (x1 + 2, y1 + 2), (x1 + tw + 6, y1 + th + 10),
                      (10, 10, 10), -1)

        # Draw the slot ID text
        cv2.putText(annotated, label, (x1 + 4, label_y), font,
                    font_scale, color, thickness, cv2.LINE_AA)

    # ── Step 2: Draw detected vehicle boxes ───────────────────────────────────
    for det in detections:
        vx1, vy1, vx2, vy2 = det["box"]

        # Yellow/cyan border for the detected vehicle
        cv2.rectangle(annotated, (vx1, vy1), (vx2, vy2), COLOR_VEHICLE, thickness=2)

        # Vehicle label: "car 87%"
        v_label = f"{det['class_name']} {det['confidence']:.0%}"
        font_scale_v = max(0.4, min(w, h) / 1800)

        (vw, vh), _ = cv2.getTextSize(v_label, cv2.FONT_HERSHEY_SIMPLEX, font_scale_v, 1)

        # Label background
        cv2.rectangle(annotated, (vx1, vy1 - vh - 8), (vx1 + vw + 6, vy1),
                      COLOR_VEHICLE, -1)

        # Label text (dark text on yellow background)
        cv2.putText(annotated, v_label, (vx1 + 3, vy1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale_v,
                    (0, 0, 0), 1, cv2.LINE_AA)

    return annotated


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 7 ─ run_detection_pipeline
# ══════════════════════════════════════════════════════════════════════════════

def run_detection_pipeline(image_bytes: bytes, model: YOLO) -> tuple:
    """
    MASTER FUNCTION — runs the complete detection pipeline in one call.

    This is the single function called by ai_app.py. It internally:
      1. Converts bytes → OpenCV image.
      2. Reads image dimensions.
      3. Converts relative slot coords → absolute pixel coords.
      4. Runs YOLOv8 vehicle detection.
      5. Checks all slot overlaps.
      6. Draws annotated output.

    Parameters:
        image_bytes (bytes): Raw bytes from Streamlit's st.file_uploader().
        model       (YOLO): Loaded YOLO model from load_yolo_model().

    Returns:
        tuple of 4 items:
          original_image  (numpy.ndarray) : The raw unmodified BGR image.
          annotated_image (numpy.ndarray) : Image with all annotations drawn.
          slot_results    (dict)          : Per-slot detection results.
          detections      (list)          : Raw list of detected vehicles.

        Returns (None, None, None, None) if image decoding fails.
    """
    # ── Step 1: Decode image bytes ────────────────────────────────────────────
    image = bytes_to_image(image_bytes)
    if image is None:
        return None, None, None, None

    h, w = image.shape[:2]
    print(f"[INFO] Image decoded. Size: {w}×{h} px")

    # ── Step 2: Convert relative slot coordinates to absolute pixels ──────────
    abs_slot_coords = get_all_absolute_coords(w, h)
    print(f"[INFO] Loaded {len(abs_slot_coords)} slot coordinate regions.")

    # ── Step 3: Run YOLO vehicle detection ────────────────────────────────────
    detections = detect_vehicles(image, model)
    print(f"[INFO] Detected {len(detections)} vehicle(s).")

    # ── Step 4: Check slot occupancy ──────────────────────────────────────────
    slot_results = check_all_slots(detections, abs_slot_coords)
    occupied_count  = sum(1 for r in slot_results.values() if r["status"] == STATUS_OCCUPIED)
    available_count = sum(1 for r in slot_results.values() if r["status"] == STATUS_AVAILABLE)
    print(f"[INFO] Results → Occupied: {occupied_count}, Available: {available_count}")

    # ── Step 5: Draw annotations ──────────────────────────────────────────────
    annotated_image = annotate_image(image, slot_results, abs_slot_coords, detections)

    return image, annotated_image, slot_results, detections


# ══════════════════════════════════════════════════════════════════════════════
# SELF-TEST BLOCK
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    print("─" * 55)
    print("  ai_detector.py  –  Self Test")
    print("─" * 55)

    print("\n[1] Testing calculate_overlap_ratio()...")

    # Test case: vehicle exactly inside slot → overlap = 1.0
    slot    = [100, 100, 300, 250]
    vehicle = [100, 100, 300, 250]   # Same box → 100% overlap
    ratio   = calculate_overlap_ratio(vehicle, slot)
    print(f"    Same box  → overlap = {ratio:.2f}  (expected: 1.00)")

    # Test case: no overlap
    vehicle2 = [400, 400, 600, 600]
    ratio2   = calculate_overlap_ratio(vehicle2, slot)
    print(f"    No overlap → overlap = {ratio2:.2f}  (expected: 0.00)")

    # Test case: partial overlap (vehicle covers half the slot)
    vehicle3 = [100, 100, 200, 250]   # Left half of the slot
    ratio3   = calculate_overlap_ratio(vehicle3, slot)
    print(f"    Half overlap → overlap = {ratio3:.2f}  (expected: ~0.50)")

    print("\n[2] Testing load_yolo_model()...")
    model = load_yolo_model()
    print("    ✓ Model loaded successfully.")

    if len(sys.argv) >= 2:
        print(f"\n[3] Testing full pipeline on: {sys.argv[1]}")
        with open(sys.argv[1], "rb") as f:
            img_bytes = f.read()

        orig, annot, results, dets = run_detection_pipeline(img_bytes, model)

        if results:
            print("\n  Slot Results:")
            for sid, r in sorted(results.items()):
                print(f"    {sid}: {r['status']:10}  overlap={r['overlap_ratio']}")

            out_path = "ai_output.jpg"
            import cv2 as _cv2
            _cv2.imwrite(out_path, annot)
            print(f"\n  ✓ Annotated image saved to '{out_path}'")
    else:
        print("\n[3] No image provided. Run with:")
        print("    python ai_detector.py path/to/parking_image.jpg")

    print("\nAll tests complete!")
