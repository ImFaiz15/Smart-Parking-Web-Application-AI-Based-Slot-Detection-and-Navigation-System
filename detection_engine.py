"""
detection_engine.py  –  Standalone Background Detection Engine (Zone-Based)
─────────────────────────────────────────────────────────────────────────────
This file runs the AI detection engine as an INDEPENDENT background process.

WHAT'S NEW in this version (Zone-Based):
  ✅ Reads zone bounding boxes from ZONE_CONFIG in slot_config.py
  ✅ Counts how many detected vehicle CENTERS fall inside each zone box
  ✅ Updates parking.db with per-zone parked_count, available, status
  ✅ Runs independently — does NOT block the Streamlit dashboard

WHY count vehicle CENTERS instead of overlap ratio?
  When counting vehicles in a zone (e.g. 8 cars in Zone A):
    - Overlap ratio checks if a vehicle COVERS a zone (slot-by-slot logic)
    - Center-point check answers "is this car PARKED in this zone?"
  The center point of a vehicle's bounding box is a cleaner indicator
  of which zone it belongs to, especially for densely packed lots.

Architecture:
  ┌──────────────────────┐         ┌──────────────────────┐
  │  detection_engine.py │         │  app.py (Dashboard)  │
  │  (Background Python) │──────→ │  reads parking_zones  │
  │  Zone A → 8 parked   │ writes │  auto-refreshes UI    │
  │  Zone B → 3 parked   │  to    │                       │
  │  Zone C → 0 parked   │parking │                       │
  └──────────────────────┘  .db   └──────────────────────┘

Usage:
  python detection_engine.py --source my_parking.jpg
  python detection_engine.py --source parking_video.mp4
  python detection_engine.py --source camera
  python detection_engine.py --source camera --skip 10 --no-window
─────────────────────────────────────────────────────────────────────────────
"""

import argparse
import os
import sys
import time
import cv2
import numpy as np
from datetime import datetime
from ultralytics import YOLO

# Import zone configuration
from slot_config import (
    ZONE_CONFIG,
    MODEL_PATH,
    YOLO_CONFIDENCE,
    YOLO_IOU,
    VEHICLE_CLASS_NAMES,
    get_all_zone_absolute_coords,
    list_zone_ids,
)

# Import database functions
from parking_db import (
    init_parking_db,
    init_zones_db,
    seed_slots,
    ensure_zones_exist,
    update_zone_count,
    get_all_zones,
    get_zone_stats,
)


# ── Annotation colours (BGR) ───────────────────────────────────────────────────
ZONE_COLORS = [
    (0,   200, 100),   # Green
    (0,   140, 255),   # Orange
    (255, 80,  80),    # Blue
    (80,  80,  255),   # Red-blue
    (255, 200, 0),     # Cyan
    (180, 0,   255),   # Purple
]
COLOR_VEHICLE = (0, 210, 255)   # Yellow — detected vehicle box

# Status badge colours
STATUS_COLORS = {
    "available": (34,  197, 94),    # Green
    "filling"  : (234, 179, 8),     # Yellow
    "full"     : (220, 38,  38),    # Red
}


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 1 ─ load_model
# ══════════════════════════════════════════════════════════════════════════════

def load_model(model_path: str = MODEL_PATH) -> YOLO:
    """
    Loads the YOLOv8 model.
    Falls back to 'yolov8n.pt' (auto-downloads) if best.pt is missing.
    Prints class names on load so you can verify labels (e.g. 'car', 'vehicle').
    """
    if not os.path.exists(model_path):
        fallback = "yolov8n.pt"
        print(f"[WARN] '{model_path}' not found. Falling back to '{fallback}'.")
        model_path = fallback

    print(f"[INFO] Loading model  : {os.path.abspath(model_path)}")
    model = YOLO(model_path)
    print(f"[INFO] Confidence     : {YOLO_CONFIDENCE}")
    print(f"[INFO] Classes ({len(model.names)}):")
    for cls_id, cls_name in sorted(model.names.items()):
        print(f"         [{cls_id:>3}]  {cls_name}")
    print("[INFO] Model ready. ✅")
    return model


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 2 ─ detect_vehicles
# ══════════════════════════════════════════════════════════════════════════════

def detect_vehicles(frame: np.ndarray, model: YOLO) -> list:
    """
    Runs YOLOv8 inference on a single frame.

    Improvements vs original:
      - conf=YOLO_CONFIDENCE  : YOLO discards weak detections before returning.
      - iou=YOLO_IOU          : Built-in NMS merges stacked duplicate boxes.
      - class name filter     : If VEHICLE_CLASS_NAMES is set, only those
                                classes are kept (e.g. ['Car']).
        Leave VEHICLE_CLASS_NAMES=[] to accept all classes from best.pt.

    Returns:
        list of dicts:
        [{'box': [x1,y1,x2,y2], 'class_name': 'Car', 'confidence': 0.87}, ...]
    """
    # Let YOLO handle confidence filtering AND NMS in a single call.
    # This is faster and cleaner than post-processing manually.
    results = model(
        frame,
        conf=YOLO_CONFIDENCE,
        iou=YOLO_IOU,
        verbose=False,
    )
    detections = []

    for box in results[0].boxes:
        class_id   = int(box.cls[0])
        confidence = float(box.conf[0])
        class_name = model.names.get(class_id, f"class_{class_id}")

        # Optional class-name filter (e.g. keep only 'Car' from custom model).
        # Skip the check when VEHICLE_CLASS_NAMES is empty (accept all).
        if VEHICLE_CLASS_NAMES and class_name not in VEHICLE_CLASS_NAMES:
            continue

        x1, y1, x2, y2 = box.xyxy[0]
        detections.append({
            "class_name": class_name,
            "confidence": round(confidence, 3),
            "box"       : [int(x1), int(y1), int(x2), int(y2)],
        })

    return detections


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 3 ─ count_vehicles_per_zone
# ══════════════════════════════════════════════════════════════════════════════

def count_vehicles_per_zone(
    detections: list,
    zone_coords: dict,
) -> dict:
    """
    Counts how many detected vehicles have their CENTER POINT inside each zone.

    WHY use center point?
      The center (cx, cy) of a vehicle bounding box tells us WHERE the car is
      parked. If the center is inside Zone A's rectangle, that car is parked
      in Zone A — simple and reliable.

    Algorithm:
      For each detected vehicle:
        1. Compute center: cx = (x1+x2)/2, cy = (y1+y2)/2
        2. For each zone [zx1, zy1, zx2, zy2]:
              if zx1 <= cx <= zx2  AND  zy1 <= cy <= zy2  → count += 1

    Parameters:
        detections   (list): Output of detect_vehicles().
        zone_coords  (dict): {zone_id: [x1,y1,x2,y2]} in absolute pixels.

    Returns:
        dict: {zone_id: count} — number of vehicles in each zone.
              e.g. {'Zone A': 8, 'Zone B': 3, 'Zone C': 0, 'Zone D': 5}
    """
    # Initialise every zone count to 0
    counts = {zone_id: 0 for zone_id in zone_coords}

    for det in detections:
        x1, y1, x2, y2 = det["box"]

        # Vehicle center point
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        # Check which zone this center falls into
        for zone_id, box in zone_coords.items():
            if box is None:
                continue
            zx1, zy1, zx2, zy2 = box
            if zx1 <= cx <= zx2 and zy1 <= cy <= zy2:
                counts[zone_id] += 1
                break   # A vehicle belongs to only one zone

    return counts


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 4 ─ sync_zone_counts_to_db
# ══════════════════════════════════════════════════════════════════════════════

def sync_zone_counts_to_db(zone_counts: dict) -> dict:
    """
    Writes zone vehicle counts to parking.db.

    For each zone, calls update_zone_count() which:
      - Sets parked_count = detected count
      - Recalculates available = capacity - parked_count
      - Recalculates occ_pct
      - Derives status: 'available' | 'filling' | 'full'

    Parameters:
        zone_counts (dict): {zone_id: count} from count_vehicles_per_zone().

    Returns:
        dict: {'updated': N, 'failed': [...], 'timestamp': '...'}
    """
    updated = 0
    failed  = []

    for zone_id, count in zone_counts.items():
        # Pull the authoritative capacity from ZONE_CONFIG so every DB write
        # stays in sync with slot_config.py (even if the DB row is stale).
        zone_cap = ZONE_CONFIG.get(zone_id, {}).get("capacity", None)
        ok = update_zone_count(zone_id, count, zone_capacity=zone_cap)
        if ok:
            updated += 1
        else:
            failed.append(zone_id)

    return {
        "updated"  : updated,
        "failed"   : failed,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 5 ─ annotate_frame
# ══════════════════════════════════════════════════════════════════════════════

def annotate_frame(
    frame: np.ndarray,
    detections: list,
    zone_coords: dict,
    zone_counts: dict,
) -> np.ndarray:
    """
    Draws zone boxes, vehicle boxes, and count labels on the frame.

    Draws:
      1. Semi-transparent zone fills (colour-coded by status)
      2. Zone borders with zone name + count label
      3. Vehicle bounding boxes (yellow)

    Parameters:
        frame       (np.ndarray): Original camera/video frame.
        detections  (list)      : Detected vehicles from detect_vehicles().
        zone_coords (dict)      : Zone pixel coordinates.
        zone_counts (dict)      : Vehicle counts per zone.

    Returns:
        np.ndarray: Annotated frame (original is not modified).
    """
    annotated = frame.copy()

    zone_ids = list(zone_coords.keys())

    # ── Draw zone fills ────────────────────────────────────────────────────────
    overlay = annotated.copy()
    for i, zone_id in enumerate(zone_ids):
        box = zone_coords.get(zone_id)
        if box is None:
            continue
        color = ZONE_COLORS[i % len(ZONE_COLORS)]
        x1, y1, x2, y2 = box
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)

    cv2.addWeighted(overlay, 0.18, annotated, 0.82, 0, annotated)

    # ── Draw zone borders + labels ─────────────────────────────────────────────
    for i, zone_id in enumerate(zone_ids):
        box = zone_coords.get(zone_id)
        if box is None:
            continue

        color   = ZONE_COLORS[i % len(ZONE_COLORS)]
        x1, y1, x2, y2 = box
        count    = zone_counts.get(zone_id, 0)
        capacity = ZONE_CONFIG.get(zone_id, {}).get("capacity", "?")
        label    = f" {zone_id}  {count}/{capacity} "

        # Border
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        # Label background
        font = cv2.FONT_HERSHEY_SIMPLEX
        fs   = 0.6
        (tw, th_l), _ = cv2.getTextSize(label, font, fs, 2)
        cv2.rectangle(annotated, (x1 + 4, y1 + 4), (x1 + tw + 8, y1 + th_l + 14),
                      (10, 10, 10), -1)
        cv2.putText(annotated, label, (x1 + 6, y1 + th_l + 8),
                    font, fs, color, 2, cv2.LINE_AA)

    # ── Draw vehicle boxes ─────────────────────────────────────────────────────
    for det in detections:
        vx1, vy1, vx2, vy2 = det["box"]
        cv2.rectangle(annotated, (vx1, vy1), (vx2, vy2), COLOR_VEHICLE, 2)

        v_label  = f"{det['class_name']} {det['confidence']:.0%}"
        fs_v     = 0.4
        (vw, vh), _ = cv2.getTextSize(v_label, cv2.FONT_HERSHEY_SIMPLEX, fs_v, 1)
        cv2.rectangle(annotated, (vx1, vy1 - vh - 6), (vx1 + vw + 4, vy1),
                      COLOR_VEHICLE, -1)
        cv2.putText(annotated, v_label, (vx1 + 2, vy1 - 3),
                    cv2.FONT_HERSHEY_SIMPLEX, fs_v, (0, 0, 0), 1, cv2.LINE_AA)

    return annotated


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 5b ─ save_zone_crops
# ══════════════════════════════════════════════════════════════════════════════

ZONE_CROPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "zones")

def save_zone_crops(annotated: np.ndarray, zone_coords: dict) -> None:
    """
    Crops each zone's bounding box from the annotated frame and saves it
    as a JPEG image to static/zones/<zone_id>.jpg.

    These images are displayed in the Streamlit modal popup when a user
    clicks 'View Zone' on a zone card.

    Parameters:
        annotated   (np.ndarray): The fully annotated frame (with boxes/labels).
        zone_coords (dict)      : {zone_id: [x1, y1, x2, y2]} in pixels.
    """
    os.makedirs(ZONE_CROPS_DIR, exist_ok=True)

    h, w = annotated.shape[:2]

    for zone_id, box in zone_coords.items():
        if box is None:
            continue
        x1, y1, x2, y2 = box

        # Clamp to frame bounds
        x1c = max(0, x1)
        y1c = max(0, y1)
        x2c = min(w, x2)
        y2c = min(h, y2)

        if x2c <= x1c or y2c <= y1c:
            continue   # degenerate box — skip

        crop = annotated[y1c:y2c, x1c:x2c]
        out  = os.path.join(ZONE_CROPS_DIR, f"{zone_id}.jpg")
        cv2.imwrite(out, crop, [cv2.IMWRITE_JPEG_QUALITY, 88])


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 6 ─ process_frame
# ══════════════════════════════════════════════════════════════════════════════

def process_frame(frame: np.ndarray, model: YOLO, auto_sync: bool = True) -> tuple:
    """
    Processes ONE video/camera frame end-to-end:
      1. Get zone pixel coordinates for this frame size.
      2. Detect vehicles with YOLO.
      3. Count vehicles per zone (center-point method).
      4. Sync counts to parking.db (if auto_sync=True).
      5. Annotate and return the frame.

    Parameters:
        frame     (np.ndarray): BGR frame.
        model     (YOLO)      : Loaded YOLOv8 model.
        auto_sync (bool)      : If True, writes to parking.db after each frame.

    Returns:
        tuple: (annotated_frame, zone_counts, detections, sync_summary)
    """
    h, w = frame.shape[:2]

    # Zone coordinates scaled to this frame's pixel dimensions
    zone_coords = get_all_zone_absolute_coords(w, h)

    # Step 1: Detect all vehicles
    detections = detect_vehicles(frame, model)

    # Step 2: Count per zone
    zone_counts = count_vehicles_per_zone(detections, zone_coords)

    # Step 3: Annotate frame
    annotated = annotate_frame(frame, detections, zone_coords, zone_counts)

    # Step 4: Save per-zone crop images to static/zones/<zone_id>.jpg
    save_zone_crops(annotated, zone_coords)

    # Step 5: Sync to DB
    sync_summary = None
    if auto_sync:
        sync_summary = sync_zone_counts_to_db(zone_counts)

    return annotated, zone_counts, detections, sync_summary


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 7 ─ process_image
# ══════════════════════════════════════════════════════════════════════════════

def process_image(image_path: str, model: YOLO) -> None:
    """
    Detects vehicles in a single image file and syncs counts to DB.
    Saves an annotated output image as 'zone_output.jpg'.
    """
    if not os.path.exists(image_path):
        print(f"[ERROR] File not found: {image_path}")
        return

    frame = cv2.imread(image_path)
    if frame is None:
        print(f"[ERROR] Cannot decode: {image_path}")
        return

    print(f"[INFO] Image: {image_path}  ({frame.shape[1]}×{frame.shape[0]} px)")

    annotated, zone_counts, detections, sync = process_frame(frame, model)

    print(f"\n  Detected {len(detections)} vehicle(s)")
    print(f"  {'Zone':<14} {'Count':>6}")
    print("  " + "─" * 22)
    for zone_id, count in sorted(zone_counts.items()):
        cap = ZONE_CONFIG.get(zone_id, {}).get("capacity", "?")
        print(f"  {zone_id:<14} {count:>4} / {cap}")

    if sync:
        print(f"\n  DB Sync: {sync['updated']} zones updated at {sync['timestamp']}")

    out_path = "zone_output.jpg"
    cv2.imwrite(out_path, annotated)
    print(f"  Annotated image saved: {out_path}")


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 8 ─ process_video
# ══════════════════════════════════════════════════════════════════════════════

def process_video(
    video_path: str,
    model: YOLO,
    process_every_n: int = 5,
    show_window: bool = True,
    output_path: str = None,
) -> dict:
    """
    Processes a video file frame-by-frame, counting vehicles per zone.
    Syncs to parking.db on every processed frame.

    Parameters:
        video_path      (str) : Path to video (.mp4, .avi, etc.)
        model           (YOLO): Loaded model.
        process_every_n (int) : Analyse every Nth frame (skip others for speed).
        show_window     (bool): Show live OpenCV window.
        output_path     (str) : Save annotated video here (optional).
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video: {video_path}")
        return {"status": "error"}

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps          = cap.get(cv2.CAP_PROP_FPS) or 30
    w            = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h            = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[INFO] Video: {video_path}  {w}×{h}  {fps:.0f}fps  {total_frames} frames")

    writer = None
    if output_path:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    frame_count = 0
    processed   = 0
    start_time  = time.time()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        if frame_count % process_every_n == 0:
            annotated, zone_counts, detections, _ = process_frame(frame, model)
            processed += 1

            # Console progress
            total_v = sum(zone_counts.values())
            elapsed = time.time() - start_time
            print(f"  Frame {frame_count:>5}/{total_frames}  |  "
                  f"Vehicles: {len(detections)}  |  "
                  f"Total parked: {total_v}  |  {elapsed:.1f}s", end="\r")
        else:
            annotated = frame

        if writer:
            writer.write(annotated)
        if show_window:
            cv2.imshow("Zone Detection", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    if writer:
        writer.release()
    if show_window:
        cv2.destroyAllWindows()

    elapsed = time.time() - start_time
    print(f"\n[INFO] Done. {processed} frames processed in {elapsed:.1f}s")
    return {"status": "completed", "processed_frames": processed}


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 9 ─ process_camera
# ══════════════════════════════════════════════════════════════════════════════

def process_camera(
    camera_id: int = 0,
    model: YOLO = None,
    process_every_n: int = 10,
    show_window: bool = True,
    max_seconds: int = 0,
) -> dict:
    """
    Processes a live camera feed in real time.
    Counts vehicles per zone and syncs to parking.db every N frames.

    Press Q in the window to stop. Or set max_seconds for auto-stop.
    """
    if model is None:
        model = load_model()

    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open camera {camera_id}")
        return {"status": "error"}

    print(f"[INFO] Camera {camera_id} opened. Press Q to stop.")

    frame_count = 0
    processed   = 0
    start_time  = time.time()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.2)
            continue

        frame_count += 1

        if frame_count % process_every_n == 0:
            annotated, zone_counts, detections, _ = process_frame(frame, model)
            processed += 1

            total_v = sum(zone_counts.values())
            elapsed = time.time() - start_time
            print(f"  Frame {frame_count:>6}  |  "
                  f"Vehicles: {len(detections)}  |  "
                  f"Total parked: {total_v}  |  {elapsed:.1f}s", end="\r")
        else:
            annotated = frame

        if show_window:
            cv2.imshow("Zone Detection — Live Camera", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("\n[INFO] Stopped by user.")
                break

        if max_seconds > 0 and (time.time() - start_time) >= max_seconds:
            print(f"\n[INFO] Auto-stop after {max_seconds}s.")
            break

    cap.release()
    if show_window:
        cv2.destroyAllWindows()

    return {
        "status"          : "completed",
        "processed_frames": processed,
        "elapsed_seconds" : round(time.time() - start_time, 2),
    }


# ══════════════════════════════════════════════════════════════════════════════
# HELPER ─ print_banner / print_zone_status
# ══════════════════════════════════════════════════════════════════════════════

def print_banner(source: str) -> None:
    print()
    print("═" * 62)
    print("  🤖  Smart Parking — Zone-Based Detection Engine")
    print("═" * 62)
    print(f"  Model    : {MODEL_PATH}")
    print(f"  Zones    : {', '.join(list_zone_ids())}")
    print(f"  Source   : {source}")
    print(f"  Started  : {datetime.now().strftime('%d %b %Y  %I:%M:%S %p')}")
    print("═" * 62)


def print_zone_status() -> None:
    zones = get_all_zones()
    stats = get_zone_stats()
    print(f"\n  📊 Zone Status (from parking.db):")
    print(f"  {'Zone':<14} {'Parked':>8} {'Capacity':>10} {'Avail':>7} {'Status'}")
    print("  " + "─" * 52)
    for z in zones:
        print(f"  {z['zone_id']:<14} {z['parked_count']:>8} "
              f"{z['capacity']:>10} {z['available']:>7}   {z['status']}")
    print(f"\n  Overall: {stats['total_parked']}/{stats['total_capacity']} "
          f"parked ({stats['overall_pct']}% full)")
    print()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Smart Parking — Zone-Based Detection Engine",
    )
    parser.add_argument("--source", type=str, required=True,
        help="'camera' | video file (.mp4) | image file (.jpg)")
    parser.add_argument("--skip", type=int, default=None,
        help="Process every N-th frame (default: 5 video, 10 camera)")
    parser.add_argument("--no-window", action="store_true",
        help="Don't show OpenCV display window")
    parser.add_argument("--output", type=str, default=None,
        help="Save annotated video to this file")
    parser.add_argument("--camera-id", type=int, default=0,
        help="Camera index (default: 0)")
    parser.add_argument("--max-time", type=int, default=0,
        help="Stop camera after N seconds (0 = run forever)")

    args = parser.parse_args()
    source      = args.source.strip()
    show_window = not args.no_window

    print_banner(source)

    # ── Ensure database is ready ───────────────────────────────────────────────
    print("  🔧 Initialising database...")
    init_parking_db()
    init_zones_db()
    seed_slots(total_rows=3, cols=4)
    ensure_zones_exist()   # NON-DESTRUCTIVE: adds missing zones, never resets counts
    print_zone_status()

    # ── Load model ─────────────────────────────────────────────────────────────
    print("  🤖 Loading model...")
    model = load_model()
    print()

    # ── Route to source handler ────────────────────────────────────────────────
    if source.lower() == "camera":
        skip = args.skip or 10
        process_camera(args.camera_id, model, skip, show_window, args.max_time)

    elif source.lower().endswith((".mp4", ".avi", ".mkv", ".mov", ".wmv")):
        skip = args.skip or 5
        process_video(source, model, skip, show_window, args.output)

    elif source.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp")):
        process_image(source, model)

    else:
        print(f"[ERROR] Unknown source: {source}")
        sys.exit(1)

    # ── Final status ───────────────────────────────────────────────────────────
    print_zone_status()
    print("═" * 62)
    print("  ✅ Detection engine finished.")
    print("  💡 Open app.py dashboard to see updated zone stats.")
    print("═" * 62)


if __name__ == "__main__":
    main()
