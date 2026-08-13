"""
ai_detector.py  –  AI Vehicle Detection Pipeline (Module 4 – Updated)
─────────────────────────────────────────────────────────────────────────────
This file is the CORE AI engine for the Smart Parking System.

WHAT CHANGED (from original):
  ✅ Uses best.pt  (custom-trained YOLOv8) instead of yolov8n.pt
  ✅ Supports VIDEO files (mp4, avi, mkv) and WEBCAM feeds
  ✅ Processes frames in real-time with FPS control
  ✅ Directly writes slot statuses to parking.db after each frame
  ✅ Can run independently via detection_engine.py (background process)

Responsibilities:
  1. Load the custom YOLOv8 model (best.pt).
  2. Accept input from: uploaded image, video file, or webcam.
  3. Run vehicle detection on each frame.
  4. Calculate overlap ratio (Intersection Area / Slot Area).
  5. Mark each slot as 'occupied' or 'available'.
  6. Annotate frames with coloured slot overlays + vehicle boxes.
  7. Sync results directly to parking.db (SQLite).

KEY CONCEPT — Overlap Ratio:
  ┌─────────────────────────────────────────────────────────────┐
  │  Overlap Ratio = Intersection Area / Slot Area              │
  │  If Overlap Ratio ≥ threshold (0.15) → OCCUPIED  🔴        │
  │  If Overlap Ratio < threshold (0.15) → AVAILABLE 🟢        │
  └─────────────────────────────────────────────────────────────┘
─────────────────────────────────────────────────────────────────────────────
"""

import os
import cv2
import time
import numpy as np
from datetime import datetime
from ultralytics import YOLO

# Import our slot configuration
from slot_config import (
    get_all_absolute_coords,
    OVERLAP_THRESHOLD,
    YOLO_CONFIDENCE,
    MODEL_PATH,
)

# Import database functions for direct sync
from parking_db import (
    init_parking_db,
    update_slot_status,
    get_stats,
    STATUS_AVAILABLE,
    STATUS_OCCUPIED,
)


# ── COCO class IDs for vehicles ───────────────────────────────────────────────
# If your custom model (best.pt) uses DIFFERENT class IDs, update this dict.
# To find your model's class IDs, run: print(model.names)
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

# ── Status strings (must match parking_db.py) ─────────────────────────────────
_STATUS_AVAILABLE = "available"
_STATUS_OCCUPIED  = "occupied"

# ── Annotation colours (OpenCV uses BGR, not RGB) ──────────────────────────────
COLOR_AVAILABLE = (34, 197, 94)    # Green  — available slot
COLOR_OCCUPIED  = (59,  50, 220)   # Red    — occupied slot
COLOR_VEHICLE   = (0,  210, 255)   # Yellow — detected vehicle box

# Fill overlay transparency
FILL_ALPHA = 0.25


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 1 ─ load_yolo_model
# ══════════════════════════════════════════════════════════════════════════════

def load_yolo_model(model_path: str = MODEL_PATH) -> YOLO:
    """
    Loads the YOLOv8 model from disk.

    Priority:
      1. Try loading best.pt (your custom-trained model).
      2. If best.pt is missing, fall back to yolov8n.pt (auto-downloads).

    WHY a separate function?
      Loading the model is slow (~2 seconds). ai_app.py caches it with
      @st.cache_resource so it loads only ONCE per session.

    Parameters:
        model_path (str): Path to the .pt weights file.

    Returns:
        YOLO: A ready-to-use YOLO model object.
    """
    # Check if the requested model file exists
    if not os.path.exists(model_path):
        fallback = "yolov8n.pt"
        print(f"[WARN] Model '{model_path}' not found. Falling back to '{fallback}'.")
        print(f"[WARN] Place your custom model at: {os.path.abspath(model_path)}")
        model_path = fallback

    print(f"[INFO] Loading model  : {os.path.abspath(model_path)}")
    model = YOLO(model_path)

    # Print class ID → name table so you can verify your model's labels
    print(f"[INFO] Confidence     : {YOLO_CONFIDENCE}")
    print(f"[INFO] Classes ({len(model.names)}):")
    for cls_id, cls_name in sorted(model.names.items()):
        print(f"         [{cls_id:>3}]  {cls_name}")
    print("[INFO] Model ready. ✅")
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
      np.frombuffer() + cv2.imdecode() solves this.

    Parameters:
        image_bytes (bytes): Raw bytes from an uploaded image file.

    Returns:
        numpy.ndarray: A BGR image array of shape (height, width, 3).
                       Returns None if the bytes are invalid.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        print("[ERROR] Could not decode image bytes. Invalid or corrupted file.")
    return image


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 3 ─ detect_vehicles
# ══════════════════════════════════════════════════════════════════════════════

def detect_vehicles(image: np.ndarray, model: YOLO) -> list:
    """
    Runs YOLOv8 inference on a single frame and returns vehicle detections.

    For a PRETRAINED COCO model, we filter to classes 2, 3, 5, 7.
    For a CUSTOM model (best.pt), all detected classes are treated as vehicles
    if VEHICLE_CLASSES is empty or if your model only has vehicle classes.

    Parameters:
        image (numpy.ndarray): BGR image/frame.
        model (YOLO): Loaded YOLO model.

    Returns:
        list of dicts: Each dict has 'class_name', 'confidence', 'box'.
    """
    results = model(image, verbose=False)
    detections = []

    for box in results[0].boxes:
        class_id   = int(box.cls[0])
        confidence = float(box.conf[0])

        # Skip low-confidence detections
        if confidence < YOLO_CONFIDENCE:
            continue

        # Get the class name from the model's own class map
        class_name = model.names.get(class_id, f"class_{class_id}")

        # If using COCO pretrained model, filter to vehicle classes only.
        # If using custom model, accept ALL detections (your model was
        # trained specifically on vehicles, so all classes are relevant).
        if VEHICLE_CLASSES and class_id not in VEHICLE_CLASSES:
            continue

        x1, y1, x2, y2 = box.xyxy[0]

        detections.append({
            "class_name" : class_name,
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
      1. Find the overlapping rectangle between the two boxes.
      2. Calculate its area (Intersection Area).
      3. Divide by the slot's total area.

    If no overlap → returns 0.0.
    If vehicle fills the slot perfectly → returns 1.0.

    Parameters:
        vehicle_box (list): [x1, y1, x2, y2] of detected vehicle in pixels.
        slot_box    (list): [x1, y1, x2, y2] of parking slot in pixels.

    Returns:
        float: Overlap ratio between 0.0 and 1.0.
    """
    vx1, vy1, vx2, vy2 = vehicle_box
    sx1, sy1, sx2, sy2 = slot_box

    # Step 1: Intersection rectangle
    ix1 = max(vx1, sx1)
    iy1 = max(vy1, sy1)
    ix2 = min(vx2, sx2)
    iy2 = min(vy2, sy2)

    # Step 2: No overlap check
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    # Step 3: Intersection area
    intersection_area = (ix2 - ix1) * (iy2 - iy1)

    # Step 4: Slot area
    slot_area = (sx2 - sx1) * (sy2 - sy1)
    if slot_area <= 0:
        return 0.0

    # Step 5: Ratio
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

    For each slot, loops through ALL detected vehicles and finds the one
    with the highest overlap. If that overlap ≥ threshold → OCCUPIED.

    Parameters:
        detections      (list): Output of detect_vehicles().
        abs_slot_coords (dict): Output of get_all_absolute_coords().
        threshold       (float): Minimum overlap ratio to mark occupied.

    Returns:
        dict: Maps slot_id → result dict with status, overlap, vehicle info.
    """
    slot_results = {}

    for slot_id, slot_box in abs_slot_coords.items():
        best_overlap    = 0.0
        best_vehicle    = None
        best_confidence = None

        for det in detections:
            overlap = calculate_overlap_ratio(det["box"], slot_box)
            if overlap > best_overlap:
                best_overlap    = overlap
                best_vehicle    = det["class_name"]
                best_confidence = det["confidence"]

        status = _STATUS_OCCUPIED if best_overlap >= threshold else _STATUS_AVAILABLE

        slot_results[slot_id] = {
            "status"          : status,
            "overlap_ratio"   : round(best_overlap, 3),
            "matched_vehicle" : best_vehicle,
            "confidence"      : best_confidence,
        }

    return slot_results


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 6 ─ sync_results_to_db
# ══════════════════════════════════════════════════════════════════════════════

def sync_results_to_db(slot_results: dict) -> dict:
    """
    Writes AI detection results directly into parking.db (SQLite).

    This function is called:
      - After processing an uploaded image (via ai_app.py)
      - After processing each video frame (via detection_engine.py)
      - Automatically by the background engine (no Streamlit needed)

    For each slot, it calls update_slot_status() from parking_db.py.
    Only 'available' and 'occupied' are written. 'reserved' is untouched.

    Parameters:
        slot_results (dict): Output of check_all_slots().

    Returns:
        dict: Summary — {'updated': N, 'failed': [], 'timestamp': '...'}
    """
    # Ensure the parking table exists before writing
    init_parking_db()

    updated = 0
    failed  = []

    for slot_id, result in slot_results.items():
        new_status = result["status"]
        vehicle_no = result.get("matched_vehicle") if new_status == _STATUS_OCCUPIED else None

        success = update_slot_status(
            slot_id        = slot_id,
            new_status     = new_status,
            vehicle_number = vehicle_no,
        )

        if success:
            updated += 1
        else:
            failed.append(slot_id)

    return {
        "updated"  : updated,
        "failed"   : failed,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 7 ─ annotate_image
# ══════════════════════════════════════════════════════════════════════════════

def annotate_image(
    image: np.ndarray,
    slot_results: dict,
    abs_slot_coords: dict,
    detections: list
) -> np.ndarray:
    """
    Draws all visual annotations onto a COPY of the image/frame.

    Draws:
      1. Semi-transparent coloured fills on slot regions (green/red).
      2. Solid border rectangles around each slot.
      3. Slot ID labels with status icons.
      4. Yellow/cyan bounding boxes on detected vehicles.

    Parameters:
        image           (np.ndarray): Original BGR image/frame.
        slot_results    (dict): Output of check_all_slots().
        abs_slot_coords (dict): Absolute pixel slot coordinates.
        detections      (list): Detected vehicle list.

    Returns:
        numpy.ndarray: Annotated image (does NOT modify the original).
    """
    annotated = image.copy()
    h, w = image.shape[:2]

    # ── Step 1: Semi-transparent slot fills ────────────────────────────────────
    overlay = annotated.copy()

    for slot_id, result in slot_results.items():
        box = abs_slot_coords[slot_id]
        x1, y1, x2, y2 = box
        color = COLOR_AVAILABLE if result["status"] == _STATUS_AVAILABLE else COLOR_OCCUPIED
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, thickness=-1)

    cv2.addWeighted(overlay, FILL_ALPHA, annotated, 1 - FILL_ALPHA, 0, annotated)

    # ── Step 2: Solid borders + slot labels ───────────────────────────────────
    for slot_id, result in slot_results.items():
        box = abs_slot_coords[slot_id]
        x1, y1, x2, y2 = box

        color = COLOR_AVAILABLE if result["status"] == _STATUS_AVAILABLE else COLOR_OCCUPIED
        status_icon = "OK" if result["status"] == _STATUS_AVAILABLE else "X"

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness=2)

        # Slot label
        label      = f" {slot_id} {status_icon} "
        font       = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.45, min(w, h) / 1600)
        thickness  = 1

        (tw, th_t), _ = cv2.getTextSize(label, font, font_scale, thickness)
        label_y = y1 + th_t + 6

        cv2.rectangle(annotated, (x1 + 2, y1 + 2), (x1 + tw + 6, y1 + th_t + 10),
                      (10, 10, 10), -1)
        cv2.putText(annotated, label, (x1 + 4, label_y), font,
                    font_scale, color, thickness, cv2.LINE_AA)

    # ── Step 3: Vehicle bounding boxes ────────────────────────────────────────
    for det in detections:
        vx1, vy1, vx2, vy2 = det["box"]
        cv2.rectangle(annotated, (vx1, vy1), (vx2, vy2), COLOR_VEHICLE, thickness=2)

        v_label      = f"{det['class_name']} {det['confidence']:.0%}"
        font_scale_v = max(0.4, min(w, h) / 1800)

        (vw, vh), _ = cv2.getTextSize(v_label, cv2.FONT_HERSHEY_SIMPLEX, font_scale_v, 1)
        cv2.rectangle(annotated, (vx1, vy1 - vh - 8), (vx1 + vw + 6, vy1),
                      COLOR_VEHICLE, -1)
        cv2.putText(annotated, v_label, (vx1 + 3, vy1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale_v,
                    (0, 0, 0), 1, cv2.LINE_AA)

    return annotated


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 8 ─ run_detection_pipeline  (IMAGE — used by ai_app.py)
# ══════════════════════════════════════════════════════════════════════════════

def run_detection_pipeline(image_bytes: bytes, model: YOLO) -> tuple:
    """
    MASTER FUNCTION for single-image detection.

    Called by ai_app.py when the user uploads a parking lot image.

    Pipeline:
      1. bytes → OpenCV image
      2. Convert slot coords to pixels
      3. Run YOLO detection
      4. Check slot overlaps
      5. Annotate image

    Parameters:
        image_bytes (bytes): Raw bytes from Streamlit's file_uploader.
        model       (YOLO): Loaded YOLO model.

    Returns:
        tuple: (original_image, annotated_image, slot_results, detections)
               or (None, None, None, None) if decoding fails.
    """
    image = bytes_to_image(image_bytes)
    if image is None:
        return None, None, None, None

    h, w = image.shape[:2]
    print(f"[INFO] Image decoded. Size: {w}×{h} px")

    abs_slot_coords = get_all_absolute_coords(w, h)
    print(f"[INFO] Loaded {len(abs_slot_coords)} slot regions.")

    detections = detect_vehicles(image, model)
    print(f"[INFO] Detected {len(detections)} vehicle(s).")

    slot_results = check_all_slots(detections, abs_slot_coords)
    occupied  = sum(1 for r in slot_results.values() if r["status"] == _STATUS_OCCUPIED)
    available = sum(1 for r in slot_results.values() if r["status"] == _STATUS_AVAILABLE)
    print(f"[INFO] Results → Occupied: {occupied}, Available: {available}")

    annotated_image = annotate_image(image, slot_results, abs_slot_coords, detections)

    return image, annotated_image, slot_results, detections


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 9 ─ process_frame  (SINGLE FRAME — used by video/camera engine)
# ══════════════════════════════════════════════════════════════════════════════

def process_frame(
    frame: np.ndarray,
    model: YOLO,
    auto_sync: bool = True
) -> tuple:
    """
    Processes a single video/camera frame through the full pipeline.

    This function is the building block for video processing.
    It runs detection + overlap check + DB sync on ONE frame.

    Parameters:
        frame     (np.ndarray): A single BGR frame from a video or camera.
        model     (YOLO): Loaded YOLO model.
        auto_sync (bool): If True, immediately writes results to parking.db.

    Returns:
        tuple: (annotated_frame, slot_results, detections, sync_summary)
               sync_summary is None if auto_sync is False.
    """
    h, w = frame.shape[:2]

    # Convert relative slot coords → absolute pixel coords for this frame size
    abs_slot_coords = get_all_absolute_coords(w, h)

    # Detect vehicles in this frame
    detections = detect_vehicles(frame, model)

    # Check overlap of each slot with detected vehicles
    slot_results = check_all_slots(detections, abs_slot_coords)

    # Annotate the frame
    annotated = annotate_image(frame, slot_results, abs_slot_coords, detections)

    # Auto-sync to SQLite database
    sync_summary = None
    if auto_sync:
        sync_summary = sync_results_to_db(slot_results)

    return annotated, slot_results, detections, sync_summary


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 10 ─ process_video  (VIDEO FILE)
# ══════════════════════════════════════════════════════════════════════════════

def process_video(
    video_path: str,
    model: YOLO,
    process_every_n: int = 5,
    show_window: bool = True,
    auto_sync: bool = True,
    output_path: str = None
) -> dict:
    """
    Processes a video file frame-by-frame for vehicle detection.

    WHY process_every_n?
      Videos have 24-30 frames per second. Running YOLO on EVERY frame
      is too slow on most laptops. By skipping frames (e.g. every 5th),
      we get near-real-time performance while still detecting changes.

    Parameters:
        video_path      (str) : Path to the video file (mp4, avi, mkv).
        model           (YOLO): Loaded YOLO model.
        process_every_n (int) : Process 1 frame every N frames (skip the rest).
        show_window     (bool): If True, show a live OpenCV window.
        auto_sync       (bool): If True, sync results to parking.db each processed frame.
        output_path     (str) : If provided, save the annotated video to this path.

    Returns:
        dict: Summary of the video processing session.
    """
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"[ERROR] Cannot open video: {video_path}")
        return {"status": "error", "message": f"Cannot open: {video_path}"}

    # Read video properties
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps          = cap.get(cv2.CAP_PROP_FPS) or 30
    width        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height       = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"[INFO] Video: {video_path}")
    print(f"[INFO] Resolution: {width}×{height}, FPS: {fps:.1f}, Frames: {total_frames}")

    # Optional: video writer for saving annotated output
    writer = None
    if output_path:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        print(f"[INFO] Saving annotated video to: {output_path}")

    frame_count   = 0
    processed     = 0
    last_results  = None
    start_time    = time.time()

    print(f"[INFO] Processing every {process_every_n}th frame. Press 'q' to stop.\n")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break   # End of video

        frame_count += 1

        # Only run detection on every Nth frame
        if frame_count % process_every_n == 0:
            annotated, slot_results, detections, sync_summary = process_frame(
                frame, model, auto_sync=auto_sync
            )
            last_results = slot_results
            processed   += 1

            # Print progress every processed frame
            occupied  = sum(1 for r in slot_results.values() if r["status"] == _STATUS_OCCUPIED)
            available = sum(1 for r in slot_results.values() if r["status"] == _STATUS_AVAILABLE)
            elapsed   = time.time() - start_time
            print(f"  Frame {frame_count:>5}/{total_frames}  |  "
                  f"Vehicles: {len(detections)}  |  "
                  f"Occupied: {occupied}  Available: {available}  |  "
                  f"Time: {elapsed:.1f}s", end="\r")
        else:
            # For skipped frames, use the last annotated version or raw frame
            annotated = frame

        # Save to output video
        if writer:
            writer.write(annotated)

        # Display live window
        if show_window:
            cv2.imshow("Smart Parking – AI Detection", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("\n[INFO] Stopped by user (pressed 'q').")
                break

    # Cleanup
    cap.release()
    if writer:
        writer.release()
    if show_window:
        cv2.destroyAllWindows()

    elapsed = time.time() - start_time
    summary = {
        "status"          : "completed",
        "video_path"      : video_path,
        "total_frames"    : frame_count,
        "processed_frames": processed,
        "elapsed_seconds" : round(elapsed, 2),
        "last_results"    : last_results,
    }

    print(f"\n\n[INFO] Done. Processed {processed} frames in {elapsed:.1f}s.")
    return summary


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 11 ─ process_camera  (WEBCAM / IP CAMERA)
# ══════════════════════════════════════════════════════════════════════════════

def process_camera(
    camera_id: int = 0,
    model: YOLO = None,
    process_every_n: int = 10,
    show_window: bool = True,
    auto_sync: bool = True,
    max_seconds: int = 0
) -> dict:
    """
    Processes a live camera feed for real-time vehicle detection.

    This function runs in an INFINITE LOOP until:
      - The user presses 'q' in the OpenCV window.
      - max_seconds is reached (if set > 0).
      - The camera disconnects.

    Parameters:
        camera_id       (int) : Camera index (0 = default webcam, 1 = second camera).
                                 Or a string URL for an IP camera stream.
        model           (YOLO): Loaded YOLO model.
        process_every_n (int) : Process 1 frame every N frames.
        show_window     (bool): If True, show a live OpenCV window.
        auto_sync       (bool): If True, sync to parking.db on each processed frame.
        max_seconds     (int) : Stop after N seconds. 0 = run forever.

    Returns:
        dict: Summary of the camera session.
    """
    if model is None:
        model = load_yolo_model()

    cap = cv2.VideoCapture(camera_id)

    if not cap.isOpened():
        print(f"[ERROR] Cannot open camera: {camera_id}")
        return {"status": "error", "message": f"Cannot open camera: {camera_id}"}

    print(f"[INFO] Camera {camera_id} opened. Press 'q' to stop.")
    if max_seconds > 0:
        print(f"[INFO] Auto-stop after {max_seconds} seconds.")

    frame_count  = 0
    processed    = 0
    last_results = None
    start_time   = time.time()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("[WARN] Camera frame read failed. Retrying...")
            time.sleep(0.5)
            continue

        frame_count += 1

        if frame_count % process_every_n == 0:
            annotated, slot_results, detections, sync_summary = process_frame(
                frame, model, auto_sync=auto_sync
            )
            last_results = slot_results
            processed   += 1

            occupied  = sum(1 for r in slot_results.values() if r["status"] == _STATUS_OCCUPIED)
            available = sum(1 for r in slot_results.values() if r["status"] == _STATUS_AVAILABLE)
            elapsed   = time.time() - start_time
            print(f"  Frame {frame_count:>6}  |  "
                  f"Vehicles: {len(detections)}  |  "
                  f"Occupied: {occupied}  Available: {available}  |  "
                  f"Time: {elapsed:.1f}s", end="\r")
        else:
            annotated = frame

        if show_window:
            cv2.imshow("Smart Parking – Live Camera Feed", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("\n[INFO] Stopped by user.")
                break

        # Time limit check
        if max_seconds > 0 and (time.time() - start_time) >= max_seconds:
            print(f"\n[INFO] Reached {max_seconds}s time limit.")
            break

    cap.release()
    if show_window:
        cv2.destroyAllWindows()

    elapsed = time.time() - start_time
    return {
        "status"          : "completed",
        "camera_id"       : camera_id,
        "total_frames"    : frame_count,
        "processed_frames": processed,
        "elapsed_seconds" : round(elapsed, 2),
        "last_results"    : last_results,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SELF-TEST BLOCK
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    print("═" * 60)
    print("  ai_detector.py  –  Self Test (Updated)")
    print("═" * 60)

    print("\n[1] Testing calculate_overlap_ratio()...")

    # Same box → 100% overlap
    ratio = calculate_overlap_ratio([100, 100, 300, 250], [100, 100, 300, 250])
    print(f"    Same box     → {ratio:.2f}  (expected: 1.00)")

    # No overlap
    ratio2 = calculate_overlap_ratio([400, 400, 600, 600], [100, 100, 300, 250])
    print(f"    No overlap   → {ratio2:.2f}  (expected: 0.00)")

    # Half overlap
    ratio3 = calculate_overlap_ratio([100, 100, 200, 250], [100, 100, 300, 250])
    print(f"    Half overlap → {ratio3:.2f}  (expected: ~0.50)")

    print("\n[2] Testing load_yolo_model()...")
    model = load_yolo_model()
    print("    ✓ Model loaded.")

    # Check command-line arguments for image/video/camera testing
    if len(sys.argv) >= 2:
        source = sys.argv[1]

        if source.lower() == "camera":
            # python ai_detector.py camera
            print(f"\n[3] Starting CAMERA feed...")
            result = process_camera(camera_id=0, model=model, max_seconds=30)
            print(f"\n    Summary: {result}")

        elif source.lower().endswith((".mp4", ".avi", ".mkv", ".mov")):
            # python ai_detector.py video.mp4
            print(f"\n[3] Processing VIDEO: {source}")
            result = process_video(source, model, process_every_n=5, output_path="ai_output.mp4")
            print(f"\n    Summary: {result}")

        else:
            # python ai_detector.py image.jpg
            print(f"\n[3] Processing IMAGE: {source}")
            with open(source, "rb") as f:
                img_bytes = f.read()

            orig, annot, results, dets = run_detection_pipeline(img_bytes, model)

            if results:
                print("\n  Slot Results:")
                for sid, r in sorted(results.items()):
                    print(f"    {sid}: {r['status']:10}  overlap={r['overlap_ratio']}")

                # Auto-sync to DB
                sync = sync_results_to_db(results)
                print(f"\n  DB Sync: {sync}")

                cv2.imwrite("ai_output.jpg", annot)
                print("  ✓ Saved annotated image: ai_output.jpg")
    else:
        print("\n[3] No input provided. Usage:")
        print("    python ai_detector.py image.jpg      → process image")
        print("    python ai_detector.py video.mp4      → process video")
        print("    python ai_detector.py camera          → webcam feed")

    print("\n✅ All tests complete!")
