"""
detection_engine.py  –  Standalone Background Detection Engine
─────────────────────────────────────────────────────────────────────────────
This file runs the AI detection engine as an INDEPENDENT background process.

WHY this file exists:
  Streamlit reruns the ENTIRE script on every user click. If you put
  heavy video processing inside a Streamlit app, it would:
    - Block the UI (user can't click anything)
    - Restart from scratch on every interaction
    - Crash on long-running tasks

  detection_engine.py solves this by running OUTSIDE Streamlit.
  It processes video/camera frames in its own Python process and writes
  results directly to parking.db. The Streamlit dashboard (parking_app.py)
  reads from the same parking.db and auto-refreshes to show live updates.

Architecture:
  ┌──────────────────────┐         ┌──────────────────────┐
  │  detection_engine.py │         │  parking_app.py      │
  │  (Background Python  │──────→ │  (Streamlit Dashboard)│
  │   process — no UI)   │ writes │  reads from parking.db│
  │                      │  to    │  auto-refreshes every │
  │  YOLOv8 → Detect →   │parking │  10 seconds           │
  │  Overlap → Update DB │  .db   │                       │
  └──────────────────────┘         └──────────────────────┘

Usage:
  # Process a VIDEO file:
  python detection_engine.py --source video.mp4

  # Process WEBCAM (camera 0):
  python detection_engine.py --source camera

  # Process a single IMAGE:
  python detection_engine.py --source parking_image.jpg

  # Custom settings:
  python detection_engine.py --source video.mp4 --skip 10 --no-window

Run this in a SEPARATE terminal from Streamlit.
─────────────────────────────────────────────────────────────────────────────
"""

import argparse
import os
import sys
from datetime import datetime

# Import our detection pipeline
from ai_detector import (
    load_yolo_model,
    run_detection_pipeline,
    process_video,
    process_camera,
    sync_results_to_db,
)
from parking_db import init_parking_db, seed_slots, get_stats
from slot_config import MODEL_PATH, OVERLAP_THRESHOLD, YOLO_CONFIDENCE


def print_banner():
    """Prints a startup banner with system info."""
    print()
    print("═" * 62)
    print("  🤖  Smart Parking – AI Detection Engine")
    print("  ─  Standalone Background Process")
    print("═" * 62)
    print(f"  Model          : {MODEL_PATH}")
    print(f"  Confidence     : {YOLO_CONFIDENCE * 100:.0f}%")
    print(f"  Overlap Thresh : {OVERLAP_THRESHOLD * 100:.0f}%")
    print(f"  Started at     : {datetime.now().strftime('%d %b %Y  %I:%M:%S %p')}")
    print("═" * 62)


def print_db_status():
    """Prints the current parking database stats."""
    stats = get_stats()
    print(f"\n  📊 Current DB Status:")
    print(f"     Total: {stats['total']}  |  "
          f"Available: {stats['available']}  |  "
          f"Occupied: {stats['occupied']}  |  "
          f"Reserved: {stats['reserved']}")
    print()


def run_image(source: str, model):
    """Processes a single image file."""
    print(f"\n  📷 Processing image: {source}")

    if not os.path.exists(source):
        print(f"  ❌ File not found: {source}")
        return

    with open(source, "rb") as f:
        image_bytes = f.read()

    orig, annot, slot_results, detections = run_detection_pipeline(image_bytes, model)

    if slot_results is None:
        print("  ❌ Failed to process image.")
        return

    # Print per-slot results
    print(f"\n  🔍 Detected {len(detections)} vehicle(s)")
    print(f"  {'Slot':<8} {'Status':<12} {'Overlap':<10} {'Vehicle'}")
    print("  " + "─" * 45)
    for sid in sorted(slot_results.keys()):
        r = slot_results[sid]
        veh = r["matched_vehicle"] or "—"
        print(f"  {sid:<8} {r['status']:<12} {r['overlap_ratio']:.1%}       {veh}")

    # Sync to database
    sync = sync_results_to_db(slot_results)
    print(f"\n  💾 Database synced: {sync['updated']} slots updated at {sync['timestamp']}")

    if sync["failed"]:
        print(f"  ⚠️  Failed slots (not in DB): {sync['failed']}")
        print("     Tip: Run 'python parking_db.py' to seed the database first.")

    # Save annotated image
    import cv2
    output_name = "ai_output.jpg"
    cv2.imwrite(output_name, annot)
    print(f"  📸 Annotated image saved: {output_name}")


def run_video(source: str, model, skip_frames: int, show_window: bool, output_path: str):
    """Processes a video file."""
    print(f"\n  🎬 Processing video: {source}")
    print(f"     Skip every: {skip_frames} frames  |  Window: {'ON' if show_window else 'OFF'}")

    if not os.path.exists(source):
        print(f"  ❌ File not found: {source}")
        return

    result = process_video(
        video_path      = source,
        model           = model,
        process_every_n = skip_frames,
        show_window     = show_window,
        auto_sync       = True,
        output_path     = output_path,
    )

    print(f"\n  📊 Summary: {result['processed_frames']} frames processed "
          f"in {result['elapsed_seconds']}s")


def run_camera(camera_id, model, skip_frames: int, show_window: bool, max_seconds: int):
    """Processes a live camera feed."""
    print(f"\n  📹 Starting camera: {camera_id}")
    print(f"     Skip every: {skip_frames} frames  |  Window: {'ON' if show_window else 'OFF'}")
    if max_seconds > 0:
        print(f"     Auto-stop after: {max_seconds} seconds")

    result = process_camera(
        camera_id       = camera_id,
        model           = model,
        process_every_n = skip_frames,
        show_window     = show_window,
        auto_sync       = True,
        max_seconds     = max_seconds,
    )

    print(f"\n  📊 Summary: {result['processed_frames']} frames processed "
          f"in {result['elapsed_seconds']}s")


def main():
    """
    Entry point — parses command-line arguments and runs the engine.

    Arguments:
        --source   : 'camera', a video file path, or an image file path.
        --skip     : Process every Nth frame (default: 5 for video, 10 for camera).
        --no-window: Don't show OpenCV display window (useful for headless servers).
        --output   : Save annotated video to this file path.
        --camera-id: Camera index (default 0). Use 1 for second camera.
        --max-time : Stop camera after N seconds (default 0 = run forever).
    """
    parser = argparse.ArgumentParser(
        description="Smart Parking – AI Detection Engine (Background Process)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--source", type=str, required=True,
        help="Input source:\n"
             "  'camera'       → Use webcam\n"
             "  'video.mp4'    → Process a video file\n"
             "  'image.jpg'    → Process a single image\n"
    )
    parser.add_argument(
        "--skip", type=int, default=None,
        help="Process every Nth frame (default: 5 for video, 10 for camera)"
    )
    parser.add_argument(
        "--no-window", action="store_true",
        help="Don't show the OpenCV display window"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Save annotated video to this file (e.g. output.mp4)"
    )
    parser.add_argument(
        "--camera-id", type=int, default=0,
        help="Camera index (default: 0 for built-in webcam)"
    )
    parser.add_argument(
        "--max-time", type=int, default=0,
        help="Stop camera after N seconds (default: 0 = run forever)"
    )

    args = parser.parse_args()

    # ── Startup ────────────────────────────────────────────────────────────────
    print_banner()

    # Ensure parking DB is ready
    print("  🔧 Initialising parking database...")
    init_parking_db()
    seed_slots(total_rows=3, cols=4)
    print_db_status()

    # Load model
    print("  🤖 Loading YOLOv8 model...")
    model = load_yolo_model()
    print()

    # ── Route to correct handler ──────────────────────────────────────────────
    source = args.source.strip()
    show_window = not args.no_window

    if source.lower() == "camera":
        # CAMERA mode
        skip = args.skip if args.skip else 10
        run_camera(args.camera_id, model, skip, show_window, args.max_time)

    elif source.lower().endswith((".mp4", ".avi", ".mkv", ".mov", ".wmv")):
        # VIDEO mode
        skip = args.skip if args.skip else 5
        run_video(source, model, skip, show_window, args.output)

    elif source.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp")):
        # IMAGE mode
        run_image(source, model)

    else:
        print(f"  ❌ Unknown source type: {source}")
        print("     Use: 'camera', a video file (.mp4), or an image file (.jpg)")
        sys.exit(1)

    # ── Final DB status ────────────────────────────────────────────────────────
    print_db_status()
    print("═" * 62)
    print("  ✅ Detection engine finished.")
    print("  💡 Open parking_app.py to see updated results on the dashboard.")
    print("═" * 62)


if __name__ == "__main__":
    main()
