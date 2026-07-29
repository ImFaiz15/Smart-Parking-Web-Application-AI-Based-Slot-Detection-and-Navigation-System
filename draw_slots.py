"""
draw_slots.py  –  Interactive Parking Zone Drawing Tool
─────────────────────────────────────────────────────────────────────────────
This script lets you draw parking zones directly on your parking lot image
using your mouse. After drawing, it saves the zone coordinates and capacity
into slot_config.py automatically.

HOW TO USE:
  1. Run:  python draw_slots.py
  2. An OpenCV window opens with your parking lot image.
  3. Click and drag to draw a rectangle around a parking zone.
  4. After releasing the mouse:
       - Terminal asks: "Zone Name?" → type e.g. "Zone A", press Enter
       - Terminal asks: "Capacity?" → type e.g. 10, press Enter
  5. Repeat for every zone you want to define.
  6. Press  S  to SAVE all zones to slot_config.py.
  7. Press  R  to UNDO the last drawn zone.
  8. Press  Q  to QUIT without saving.

KEYBOARD SHORTCUTS:
  S  →  Save zones to slot_config.py
  R  →  Remove (undo) the last zone
  Q  →  Quit
  C  →  Clear all zones (start fresh)

OUTPUT:
  Updates ZONE_CONFIG inside slot_config.py with relative coordinates.
  Example entry:
      "Zone A": {
          "coords"  : [0.02, 0.05, 0.48, 0.45],
          "capacity": 10,
      }
─────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import cv2
import numpy as np

# ── Configuration ─────────────────────────────────────────────────────────────
DEFAULT_IMAGE   = "my_parking.jpg"     # Default image to draw on
CANVAS_WIDTH    = 1280                 # Max display width (image is scaled to fit)
CANVAS_HEIGHT   = 720                  # Max display height
OUTPUT_FILE     = "slot_config.py"     # Where zones are saved
WINDOW_NAME     = "Smart Parking — Zone Drawer"

# Zone box colours (BGR format for OpenCV)
COLORS = [
    (0,   200, 100),   # Green
    (0,   140, 255),   # Orange
    (255, 80,  80),    # Blue
    (80,  80,  255),   # Red-blue
    (255, 200, 0),     # Cyan
    (180, 0,   255),   # Purple
    (0,   255, 220),   # Yellow-green
    (100, 100, 255),   # Pink
]


# ── Global state (shared between mouse callback and main loop) ─────────────────
state = {
    "drawing"   : False,    # True while mouse button is held down
    "start_pt"  : (0, 0),   # Mouse press position
    "end_pt"    : (0, 0),   # Mouse release position
    "zones"     : [],       # List of completed zone dicts
    "base_image": None,     # Original image (never drawn on — used to redraw)
    "img_w"     : 1,        # Actual pixel width of the loaded image
    "img_h"     : 1,        # Actual pixel height of the loaded image
    "pending"   : False,    # True when a rectangle has been drawn but not named yet
}


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 1 ─ load_image
# ══════════════════════════════════════════════════════════════════════════════

def load_image(path: str) -> np.ndarray:
    """
    Loads the parking lot image.
    If the file is not found, creates a blank grey canvas so you can
    still draw zones without a real image.

    Parameters:
        path (str): Path to the image file.

    Returns:
        numpy.ndarray: BGR image.
    """
    if os.path.exists(path):
        img = cv2.imread(path)
        if img is not None:
            print(f"[INFO] Loaded image: {path}  ({img.shape[1]}×{img.shape[0]} px)")
            return img
        else:
            print(f"[WARN] Could not decode {path}. Using blank canvas.")
    else:
        print(f"[WARN] '{path}' not found. Using blank grey canvas.")
        print(f"[HINT] Place your parking lot image as '{path}' in the project folder.")

    # Create a blank grey canvas with grid lines for reference
    canvas = np.full((720, 1280, 3), 45, dtype=np.uint8)

    # Draw faint grid lines
    for x in range(0, 1280, 128):
        cv2.line(canvas, (x, 0), (x, 720), (70, 70, 70), 1)
    for y in range(0, 720, 72):
        cv2.line(canvas, (0, y), (1280, y), (70, 70, 70), 1)

    # Centre label
    cv2.putText(canvas, "Parking Lot Image Not Found",
                (340, 340), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (150, 150, 150), 2)
    cv2.putText(canvas, f"Place '{path}' in project root, then re-run",
                (260, 390), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (120, 120, 120), 1)

    return canvas


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 2 ─ scale_image
# ══════════════════════════════════════════════════════════════════════════════

def scale_image(img: np.ndarray) -> tuple:
    """
    Scales the image to fit within CANVAS_WIDTH × CANVAS_HEIGHT.
    Returns the scaled image AND the scale factor (used to convert
    pixel coordinates back to relative fractions).

    Parameters:
        img (np.ndarray): Original BGR image.

    Returns:
        tuple: (scaled_image, scale_x, scale_y)
               scale_x = original_width  / display_width
               scale_y = original_height / display_height
    """
    h, w = img.shape[:2]
    scale = min(CANVAS_WIDTH / w, CANVAS_HEIGHT / h)

    if scale < 1.0:
        new_w = int(w * scale)
        new_h = int(h * scale)
        scaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    else:
        scaled = img.copy()
        new_w, new_h = w, h

    # scale_x converts display pixels → original pixels
    # We then divide by original size to get relative fractions
    scale_x = w / new_w
    scale_y = h / new_h

    return scaled, scale_x, scale_y


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 3 ─ draw_all_zones
# ══════════════════════════════════════════════════════════════════════════════

def draw_all_zones(base: np.ndarray, zones: list, temp_box: tuple = None) -> np.ndarray:
    """
    Redraws the image from scratch with all completed zones + an optional
    live (in-progress) rectangle being drawn by the user.

    WHY redraw from scratch?
      If we draw on the same image repeatedly, old rectangles accumulate.
      Instead, we always start from the clean base_image and redraw everything.

    Parameters:
        base     (np.ndarray) : The original unmodified image.
        zones    (list)       : List of completed zone dicts.
        temp_box (tuple|None) : (x1, y1, x2, y2) of the box currently being drawn.

    Returns:
        numpy.ndarray: Annotated display image.
    """
    display = base.copy()

    # Draw completed zones
    for i, zone in enumerate(zones):
        color = COLORS[i % len(COLORS)]
        x1, y1, x2, y2 = zone["display_box"]

        # Semi-transparent fill
        overlay = display.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
        cv2.addWeighted(overlay, 0.20, display, 0.80, 0, display)

        # Solid border
        cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)

        # Zone label background + text
        label    = f" {zone['name']}  [{zone['capacity']} spaces] "
        font     = cv2.FONT_HERSHEY_SIMPLEX
        fs       = 0.55
        (tw, th_l), _ = cv2.getTextSize(label, font, fs, 1)

        # Dark pill behind text
        cv2.rectangle(display,
                      (x1 + 4, y1 + 4),
                      (x1 + tw + 10, y1 + th_l + 14),
                      (10, 10, 10), -1)
        cv2.putText(display, label,
                    (x1 + 7, y1 + th_l + 8),
                    font, fs, color, 1, cv2.LINE_AA)

    # Draw in-progress box (while dragging)
    if temp_box:
        tx1, ty1, tx2, ty2 = temp_box
        cv2.rectangle(display, (tx1, ty1), (tx2, ty2), (255, 255, 255), 1)

    # HUD (top-left info panel)
    hud_lines = [
        f"Zones defined: {len(zones)}",
        "S = Save to slot_config.py",
        "R = Undo last zone",
        "C = Clear all",
        "Q = Quit",
    ]
    for j, line in enumerate(hud_lines):
        y_pos = 22 + j * 22
        cv2.putText(display, line, (10, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)

    return display


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 4 ─ mouse_callback
# ══════════════════════════════════════════════════════════════════════════════

def mouse_callback(event, x, y, flags, param):
    """
    OpenCV mouse event handler.

    Called automatically by OpenCV whenever the user clicks,
    drags, or releases the mouse inside the image window.

    Events handled:
      LBUTTONDOWN  →  Record start point, set drawing=True
      MOUSEMOVE    →  While drawing, update end_pt + redisplay live rectangle
      LBUTTONUP    →  Record end point, set drawing=False, mark as pending
    """
    if event == cv2.EVENT_LBUTTONDOWN:
        state["drawing"]  = True
        state["start_pt"] = (x, y)
        state["end_pt"]   = (x, y)

    elif event == cv2.EVENT_MOUSEMOVE and state["drawing"]:
        state["end_pt"] = (x, y)
        # Live redraw to show the rectangle as user drags
        temp_box = (
            min(state["start_pt"][0], x),
            min(state["start_pt"][1], y),
            max(state["start_pt"][0], x),
            max(state["start_pt"][1], y),
        )
        display = draw_all_zones(state["base_image"], state["zones"], temp_box)
        cv2.imshow(WINDOW_NAME, display)

    elif event == cv2.EVENT_LBUTTONUP:
        state["drawing"] = False
        state["end_pt"]  = (x, y)

        # Ignore tiny accidental clicks (less than 20×20 px)
        dx = abs(state["end_pt"][0] - state["start_pt"][0])
        dy = abs(state["end_pt"][1] - state["start_pt"][1])
        if dx > 20 and dy > 20:
            state["pending"] = True   # Signal main loop to prompt for name/capacity


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 5 ─ prompt_zone_info
# ══════════════════════════════════════════════════════════════════════════════

def prompt_zone_info(existing_names: list) -> tuple:
    """
    Asks the user in the terminal for the zone name and capacity.

    WHY terminal input?
      OpenCV windows don't support text input boxes.
      We print a prompt in the terminal and use Python's input() function.

    Parameters:
        existing_names (list): Already-used zone names (to prevent duplicates).

    Returns:
        tuple: (zone_name, capacity)  or (None, None) if user cancels.
    """
    print("\n" + "─" * 45)
    print(f"  New zone rectangle drawn! ({len(existing_names) + 1} zone(s) so far)")
    print("─" * 45)

    # Zone name
    while True:
        name = input("  Zone Name  (e.g. Zone A, VIP, Level 1): ").strip()
        if not name:
            print("  [WARN] Name cannot be empty. Try again.")
            continue
        if name in existing_names:
            print(f"  [WARN] '{name}' already exists. Use a different name.")
            continue
        break

    # Capacity
    while True:
        cap_str = input("  Capacity   (total spaces in this zone): ").strip()
        try:
            capacity = int(cap_str)
            if capacity < 1:
                print("  [WARN] Capacity must be at least 1.")
                continue
            break
        except ValueError:
            print("  [WARN] Please enter a whole number (e.g. 10).")

    print(f"  ✓ Zone '{name}' with capacity {capacity} added.\n")
    return name, capacity


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 6 ─ save_zones_to_config
# ══════════════════════════════════════════════════════════════════════════════

def save_zones_to_config(zones: list, img_w: int, img_h: int) -> bool:
    """
    Writes the drawn zones into slot_config.py as the ZONE_CONFIG dict.

    HOW it works:
      1. Reads the current slot_config.py content.
      2. If a ZONE_CONFIG block already exists, replaces it.
      3. If not, appends the ZONE_CONFIG block at the end.
      4. Converts display pixel coordinates → relative fractions
         using the original image dimensions.

    Parameters:
        zones  (list): List of zone dicts with 'name', 'capacity', 'display_box'.
        img_w  (int) : Original image width in pixels.
        img_h  (int) : Original image height in pixels.

    Returns:
        bool: True if saved successfully.
    """
    if not zones:
        print("[WARN] No zones to save.")
        return False

    # Build the ZONE_CONFIG block as a string
    lines = [
        "\n\n# ══════════════════════════════════════════════════════════════════════════════",
        "# ZONE_CONFIG — Generated by draw_slots.py",
        "# Each zone has relative coords [x1, y1, x2, y2] (0.0 to 1.0) + capacity.",
        "# Re-run draw_slots.py to update these values.",
        "# ══════════════════════════════════════════════════════════════════════════════",
        "",
        "ZONE_CONFIG: dict = {",
    ]

    for zone in zones:
        x1d, y1d, x2d, y2d = zone["display_box"]
        scale_x = zone["scale_x"]
        scale_y = zone["scale_y"]

        # Convert display coords → original image coords → relative fractions
        x1_rel = round((x1d * scale_x) / img_w, 4)
        y1_rel = round((y1d * scale_y) / img_h, 4)
        x2_rel = round((x2d * scale_x) / img_w, 4)
        y2_rel = round((y2d * scale_y) / img_h, 4)

        # Clamp to 0.0–1.0 just in case
        x1_rel = max(0.0, min(1.0, x1_rel))
        y1_rel = max(0.0, min(1.0, y1_rel))
        x2_rel = max(0.0, min(1.0, x2_rel))
        y2_rel = max(0.0, min(1.0, y2_rel))

        lines.append(f'    "{zone["name"]}": {{')
        lines.append(f'        "coords"  : [{x1_rel}, {y1_rel}, {x2_rel}, {y2_rel}],')
        lines.append(f'        "capacity": {zone["capacity"]},')
        lines.append(f'    }},')

    lines.append("}")

    lines.extend([
        "",
        "",
        "def list_zone_ids() -> list:",
        '    """Returns sorted list of all zone names from ZONE_CONFIG."""',
        "    return sorted(ZONE_CONFIG.keys())",
        "",
        "",
        "def get_zone_absolute_coords(zone_id: str, image_width: int, image_height: int) -> list:",
        '    """Converts relative zone coords → absolute pixel coords."""',
        "    if zone_id not in ZONE_CONFIG:",
        "        return None",
        "    x1f, y1f, x2f, y2f = ZONE_CONFIG[zone_id][\"coords\"]",
        "    return [",
        "        int(x1f * image_width),",
        "        int(y1f * image_height),",
        "        int(x2f * image_width),",
        "        int(y2f * image_height),",
        "    ]",
        "",
        "",
        "def get_all_zone_absolute_coords(image_width: int, image_height: int) -> dict:",
        '    """Returns all zone IDs mapped to absolute pixel coords."""',
        "    return {",
        "        zid: get_zone_absolute_coords(zid, image_width, image_height)",
        "        for zid in ZONE_CONFIG",
        "    }",
    ])

    new_zone_block = "\n".join(lines)

    # Read existing slot_config.py
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""

    # Remove any existing ZONE_CONFIG block
    marker = "\n\n# ══════════════════════════════════════════════════════════════════════════════\n# ZONE_CONFIG"
    if marker in content:
        content = content[: content.index(marker)]

    # Remove trailing whitespace
    content = content.rstrip()

    # Append the new block
    new_content = content + new_zone_block + "\n"

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"\n[SAVED] {len(zones)} zone(s) written to {OUTPUT_FILE}")
    for z in zones:
        print(f"  → '{z['name']}' (capacity {z['capacity']})")
    return True


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """
    Main loop — opens the OpenCV window and handles all user interactions.
    """
    print("═" * 55)
    print("  Smart Parking — Zone Drawing Tool")
    print("═" * 55)
    print(f"  Loading image: {DEFAULT_IMAGE}")
    print("  Controls:")
    print("    Click + Drag  →  Draw a zone rectangle")
    print("    S             →  Save zones to slot_config.py")
    print("    R             →  Undo last zone")
    print("    C             →  Clear all zones")
    print("    Q             →  Quit without saving")
    print("═" * 55 + "\n")

    # Load and scale the parking image
    original = load_image(DEFAULT_IMAGE)
    state["img_w"] = original.shape[1]
    state["img_h"] = original.shape[0]

    scaled, scale_x, scale_y = scale_image(original)
    state["base_image"] = scaled

    # Create window and attach mouse handler
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, scaled.shape[1], scaled.shape[0])
    cv2.setMouseCallback(WINDOW_NAME, mouse_callback)

    print("[READY] OpenCV window opened. Draw your first zone now.\n")

    while True:
        # ── Handle pending rectangle (drawn but not named yet) ─────────────────
        if state["pending"]:
            state["pending"] = False

            x1 = min(state["start_pt"][0], state["end_pt"][0])
            y1 = min(state["start_pt"][1], state["end_pt"][1])
            x2 = max(state["start_pt"][0], state["end_pt"][0])
            y2 = max(state["start_pt"][1], state["end_pt"][1])

            existing_names = [z["name"] for z in state["zones"]]
            name, capacity = prompt_zone_info(existing_names)

            state["zones"].append({
                "name"       : name,
                "capacity"   : capacity,
                "display_box": (x1, y1, x2, y2),
                "scale_x"    : scale_x,
                "scale_y"    : scale_y,
            })

        # ── Render current state ───────────────────────────────────────────────
        display = draw_all_zones(state["base_image"], state["zones"])
        cv2.imshow(WINDOW_NAME, display)

        # ── Key handling ───────────────────────────────────────────────────────
        key = cv2.waitKey(30) & 0xFF

        if key == ord("q") or key == ord("Q") or key == 27:
            # ESC or Q = quit
            print("\n[QUIT] Exiting without saving.")
            break

        elif key == ord("s") or key == ord("S"):
            # S = save
            if not state["zones"]:
                print("[WARN] No zones drawn yet. Draw at least one zone first.")
            else:
                save_zones_to_config(state["zones"], state["img_w"], state["img_h"])
                print("\n[DONE] Zones saved! You can now run detection_engine.py.")
                break

        elif key == ord("r") or key == ord("R"):
            # R = undo last zone
            if state["zones"]:
                removed = state["zones"].pop()
                print(f"[UNDO] Removed zone: '{removed['name']}'")
            else:
                print("[INFO] No zones to undo.")

        elif key == ord("c") or key == ord("C"):
            # C = clear all
            state["zones"].clear()
            print("[CLEAR] All zones removed.")

    cv2.destroyAllWindows()
    print("\n✅ draw_slots.py finished.")


if __name__ == "__main__":
    main()
