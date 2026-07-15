"""
ai_app.py  –  AI-Powered Parking Detection Dashboard (Module 4)
─────────────────────────────────────────────────────────────────────────────
This is the Streamlit UI for Module 4.

User journey:
  Step 1 → Upload a parking lot image.
  Step 2 → Click "Run AI Detection".
  Step 3 → View original vs annotated image side by side.
  Step 4 → See per-slot results (status, overlap, vehicle type).
  Step 5 → Click "Sync to Database" to write results to SQLite.
  Step 6 → Open parking_app.py to see the dashboard updated.

What this file does NOT do:
  - It does NOT modify parking_db.py, ai_detector.py, or slot_config.py.
  - It does NOT affect any other module.

Run with:
  streamlit run ai_app.py
─────────────────────────────────────────────────────────────────────────────
"""

import cv2
import numpy as np
import streamlit as st
from datetime import datetime

# Import our pipeline and database functions
from ai_detector import load_yolo_model, run_detection_pipeline
from parking_db  import update_slot_status, get_stats, STATUS_AVAILABLE, STATUS_OCCUPIED
from slot_config import OVERLAP_THRESHOLD, YOLO_CONFIDENCE, MODEL_PATH


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 ─ PAGE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Smart Parking – AI Detection",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 ─ MODEL LOADING (CACHED)
# ══════════════════════════════════════════════════════════════════════════════
# @st.cache_resource is a Streamlit decorator that runs the function ONCE
# and stores its result in memory for the entire session.
#
# WHY cache the model?
#   Loading YOLOv8 takes ~2-3 seconds. Without caching, it would reload
#   every time the user clicks a button or changes an input — very slow.
#   With caching, it loads once and is reused for every detection.

@st.cache_resource(show_spinner="🤖 Loading YOLOv8 model...")
def load_model_cached():
    """
    Loads and caches the YOLOv8 model for the entire Streamlit session.
    Called once on app start. All subsequent detections reuse this model.

    Returns:
        YOLO: The loaded YOLOv8 model object.
    """
    return load_yolo_model(MODEL_PATH)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 ─ CUSTOM CSS
# ══════════════════════════════════════════════════════════════════════════════

def apply_styles() -> None:
    """Injects premium dark-theme CSS consistent with other app modules."""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp {
        background: radial-gradient(ellipse at top, #0a1628 0%, #080f1e 60%, #040810 100%);
    }
    #MainMenu, footer, header { visibility: hidden; }

    /* ── Page Header ────────────────────────────────────────────── */
    .ai-header {
        background: linear-gradient(135deg, #0f1f3d 0%, #080f1e 100%);
        border: 1px solid rgba(139,92,246,0.2);
        border-radius: 20px;
        padding: 28px 32px;
        margin-bottom: 24px;
    }
    .ai-title    { font-size: 2rem; font-weight: 900; color: #f0f6ff; margin: 0; letter-spacing: -0.3px; }
    .ai-subtitle { font-size: 0.85rem; color: #4a6080; margin-top: 4px; }
    .ai-badge {
        display: inline-block;
        background: #1e0f3a;
        border: 1px solid #7c3aed44;
        color: #a78bfa;
        padding: 4px 14px;
        border-radius: 99px;
        font-size: 0.72rem;
        font-weight: 700;
        margin-top: 12px;
        letter-spacing: 0.5px;
    }

    /* ── Step Cards ──────────────────────────────────────────────── */
    .step-card {
        background: #0a1628;
        border: 1px solid #1a3058;
        border-radius: 14px;
        padding: 18px 16px;
        text-align: center;
        margin-bottom: 10px;
        transition: border-color 0.2s;
    }
    .step-card.active { border-color: #7c3aed88; }
    .step-num  { font-size: 1.6rem; font-weight: 900; color: #7c3aed; }
    .step-label{ font-size: 0.72rem; color: #4a6080; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px; margin-top: 4px; }

    /* ── Image Panel ─────────────────────────────────────────────── */
    .img-panel {
        background: #080f1e;
        border: 1px solid #1a3058;
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .img-label {
        font-size: 0.7rem; font-weight: 700; color: #3b6ea5;
        text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 10px;
    }

    /* ── Result Table ────────────────────────────────────────────── */
    .result-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 9px 14px;
        border-radius: 10px;
        margin-bottom: 5px;
        font-size: 0.83rem;
        font-weight: 600;
    }
    .result-available { background: #052e16; border: 1px solid #16a34a33; }
    .result-occupied  { background: #450a0a; border: 1px solid #dc262633; }
    .result-label     { color: #c8daf5; }
    .result-status-av { color: #4ade80; }
    .result-status-oc { color: #f87171; }
    .result-meta      { color: #4a6080; font-size: 0.72rem; }

    /* ── Stat pills ───────────────────────────────────────────────── */
    .stat-pill {
        display: inline-block;
        padding: 6px 18px;
        border-radius: 99px;
        font-size: 0.82rem;
        font-weight: 700;
        margin: 4px;
    }
    .pill-total    { background: #0c2044; color: #60a5fa; border: 1px solid #1e40af44; }
    .pill-available{ background: #052e16; color: #4ade80; border: 1px solid #16a34a44; }
    .pill-occupied { background: #450a0a; color: #f87171; border: 1px solid #dc262644; }

    /* ── Buttons ─────────────────────────────────────────────────── */
    .stButton > button {
        background: linear-gradient(135deg, #5b21b6, #7c3aed);
        color: #fff; border: none; border-radius: 12px;
        padding: 12px 0; font-size: 0.92rem; font-weight: 700;
        width: 100%; transition: all 0.2s ease;
        box-shadow: 0 4px 16px rgba(124,58,237,0.35);
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #4c1d95, #6d28d9);
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(124,58,237,0.45);
    }

    /* ── Sync button override ────────────────────────────────────── */
    .sync-btn > div > button {
        background: linear-gradient(135deg, #065f46, #059669) !important;
        box-shadow: 0 4px 16px rgba(5,150,105,0.35) !important;
    }
    .sync-btn > div > button:hover {
        background: linear-gradient(135deg, #064e3b, #047857) !important;
    }

    /* ── Sidebar ─────────────────────────────────────────────────── */
    [data-testid="stSidebar"] { background: #060d1b !important; }

    /* ── Info card ───────────────────────────────────────────────── */
    .info-section {
        background: #0a1628;
        border: 1px solid #1a3058;
        border-radius: 14px;
        padding: 16px 18px;
        margin-bottom: 12px;
    }
    .info-row-small {
        display: flex; justify-content: space-between;
        padding: 6px 0; border-bottom: 1px solid #0d1f3c;
        font-size: 0.8rem;
    }
    .info-row-small:last-child { border-bottom: none; }
    .info-k { color: #4a6080; font-weight: 600; }
    .info-v { color: #c8daf5; font-weight: 500; font-family: monospace; font-size: 0.78rem; }

    /* ── Footer ──────────────────────────────────────────────────── */
    .footer {
        text-align: center; color: #1a3058; font-size: 0.72rem;
        margin-top: 32px; padding-top: 14px; border-top: 1px solid #0e1c33;
    }
    </style>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 ─ SESSION STATE INITIALISATION
# ══════════════════════════════════════════════════════════════════════════════

def init_session_state() -> None:
    """
    Initialises Streamlit session_state variables with default values.

    WHY session_state?
      Streamlit reruns the entire script every time the user interacts.
      session_state persists variables across reruns within the same session.

    Variables:
        detection_done     (bool)          : True after "Run AI Detection" is clicked.
        original_image     (numpy.ndarray) : The raw uploaded image.
        annotated_image    (numpy.ndarray) : Annotated image with all drawings.
        slot_results       (dict)          : Per-slot detection results.
        raw_detections     (list)          : Raw YOLO vehicle detections.
        db_synced          (bool)          : True after "Sync to Database" is clicked.
    """
    defaults = {
        "detection_done"  : False,
        "original_image"  : None,
        "annotated_image" : None,
        "slot_results"    : None,
        "raw_detections"  : None,
        "db_synced"       : False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 ─ HEADER
# ══════════════════════════════════════════════════════════════════════════════

def render_header() -> None:
    """Renders the purple-accented AI module page header."""
    now = datetime.now().strftime("%d %b %Y  •  %I:%M:%S %p")
    st.markdown(f"""
    <div class="ai-header">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
            <div>
                <p class="ai-title">🤖 AI Vehicle Detection</p>
                <p class="ai-subtitle">YOLOv8 + OpenCV — Module 4  •  Smart Parking System</p>
                <span class="ai-badge">⚡ YOLOv8n PRETRAINED &nbsp;•&nbsp; {now}</span>
            </div>
            <div style="text-align:right; font-size:3.2rem;">🔍</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 ─ STEP INDICATOR
# ══════════════════════════════════════════════════════════════════════════════

def render_steps(active_step: int) -> None:
    """
    Displays a 4-step visual workflow indicator.

    Highlights the currently active step in purple.

    Parameters:
        active_step (int): The current step number (1 to 4).
    """
    steps = ["Upload Image", "Run Detection", "View Results", "Sync Database"]
    cols  = st.columns(4)

    for i, (col, label) in enumerate(zip(cols, steps)):
        step_num  = i + 1
        is_active = (step_num == active_step)
        css_class = "step-card active" if is_active else "step-card"

        with col:
            st.markdown(f"""
            <div class="{css_class}">
                <div class="step-num">{step_num}</div>
                <div class="step-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 ─ UPLOAD SECTION
# ══════════════════════════════════════════════════════════════════════════════

def render_upload_section(model) -> None:
    """
    Renders the file upload area and the "Run AI Detection" button.

    Workflow inside this function:
      1. Show st.file_uploader() for JPG/PNG images.
      2. When a file is uploaded, show a preview + "Run AI Detection" button.
      3. When the button is clicked:
           a. Read the uploaded file as bytes.
           b. Call run_detection_pipeline() from ai_detector.py.
           c. Store results in session_state.
           d. Set detection_done = True.

    Parameters:
        model: The cached YOLO model from load_model_cached().
    """
    st.markdown("#### 📂 Upload Parking Lot Image")
    st.caption(
        "Upload a top-down or angled photo of a parking lot. "
        "The AI will detect vehicles and determine which slots are occupied."
    )

    uploaded_file = st.file_uploader(
        label="Choose an image file",
        type=["jpg", "jpeg", "png"],
        label_visibility="collapsed",
        help="Supported formats: JPG, JPEG, PNG",
    )

    if uploaded_file is None:
        # Show a placeholder prompt when nothing is uploaded
        st.markdown("""
        <div style="
            background:#080f1e; border:2px dashed #1a3058; border-radius:16px;
            padding:40px 20px; text-align:center; color:#4a6080;
        ">
            <div style="font-size:2.5rem; margin-bottom:10px;">📷</div>
            <div style="font-size:0.9rem; font-weight:600;">
                Drag & drop or click "Browse files" above to upload a parking lot image.
            </div>
            <div style="font-size:0.75rem; margin-top:8px; color:#243554;">
                Tip: Use a clear top-down or slightly angled view for best results.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── File uploaded — show preview + button ─────────────────────────────────
    image_bytes = uploaded_file.read()

    # Convert bytes to numpy for preview (BGR → RGB for Streamlit display)
    nparr       = np.frombuffer(image_bytes, np.uint8)
    preview_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    preview_rgb = cv2.cvtColor(preview_img, cv2.COLOR_BGR2RGB)

    h_px, w_px = preview_img.shape[:2]
    st.image(preview_rgb, caption=f"📷 Uploaded: {uploaded_file.name}  ({w_px}×{h_px} px)",
             use_column_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("🔍 Run AI Detection", use_container_width=True):
        with st.spinner("⚙️ Running YOLOv8 detection..."):
            orig, annot, results, dets = run_detection_pipeline(image_bytes, model)

        if orig is None:
            st.error("❌ Could not process the image. Please upload a valid JPG or PNG file.")
            return

        # ── Store results in session_state ─────────────────────────────────────
        st.session_state.detection_done  = True
        st.session_state.original_image  = orig
        st.session_state.annotated_image = annot
        st.session_state.slot_results    = results
        st.session_state.raw_detections  = dets
        st.session_state.db_synced       = False   # Reset sync status on new detection

        st.success(f"✅ Detection complete! Found **{len(dets)} vehicle(s)** in the image.")
        st.rerun()   # Rerun to render the results section


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8 ─ RESULTS SECTION
# ══════════════════════════════════════════════════════════════════════════════

def render_results() -> None:
    """
    Renders the detection results — displayed ONLY after detection runs.

    Shows:
      1. Side-by-side comparison: Original image vs Annotated image.
      2. Summary stats (total vehicles detected, occupied/available count).
      3. Per-slot result cards (with overlap %, vehicle type, status).
    """
    slot_results = st.session_state.slot_results
    detections   = st.session_state.raw_detections
    orig_bgr     = st.session_state.original_image
    annot_bgr    = st.session_state.annotated_image

    # Convert BGR (OpenCV) → RGB (Streamlit/Pillow expects RGB)
    orig_rgb  = cv2.cvtColor(orig_bgr,  cv2.COLOR_BGR2RGB)
    annot_rgb = cv2.cvtColor(annot_bgr, cv2.COLOR_BGR2RGB)

    st.divider()
    st.markdown("#### 🖼️ Detection Results")

    # ── Side-by-side image comparison ─────────────────────────────────────────
    col_orig, col_annot = st.columns(2)

    with col_orig:
        st.markdown('<div class="img-label">📷 Original Image</div>', unsafe_allow_html=True)
        st.image(orig_rgb, use_column_width=True)

    with col_annot:
        st.markdown('<div class="img-label">🤖 AI Annotated Output</div>', unsafe_allow_html=True)
        st.image(annot_rgb, use_column_width=True)
        st.caption(
            "🟢 Green = Available slot  |  "
            "🔴 Red = Occupied slot  |  "
            "🟡 Yellow = Detected vehicle box"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Summary Stats ──────────────────────────────────────────────────────────
    occupied_count  = sum(1 for r in slot_results.values() if r["status"] == STATUS_OCCUPIED)
    available_count = sum(1 for r in slot_results.values() if r["status"] == STATUS_AVAILABLE)
    total_slots     = len(slot_results)

    st.markdown(f"""
    <div style="margin-bottom:20px;">
        <span class="stat-pill pill-total">🏢 {total_slots} Slots Analysed</span>
        <span class="stat-pill pill-available">✅ {available_count} Available</span>
        <span class="stat-pill pill-occupied">🚗 {occupied_count} Occupied</span>
        <span class="stat-pill pill-total" style="color:#fbbf24; border-color:#d9770644;">
            🔎 {len(detections)} Vehicle(s) Detected
        </span>
    </div>
    """, unsafe_allow_html=True)

    # ── Per-slot result cards ──────────────────────────────────────────────────
    st.markdown("#### 📋 Slot-by-Slot Breakdown")
    st.caption(f"Overlap threshold: **{OVERLAP_THRESHOLD*100:.0f}%** — "
               "a slot is marked occupied if a vehicle covers this much of its area.")

    # Display in 3 columns for compact layout
    slot_ids  = sorted(slot_results.keys())
    grid_cols = st.columns(3)

    for idx, slot_id in enumerate(slot_ids):
        result    = slot_results[slot_id]
        is_occ    = result["status"] == STATUS_OCCUPIED
        css_class = "result-occupied" if is_occ else "result-available"
        sta_class = "result-status-oc" if is_occ else "result-status-av"
        status_txt = "🔴 OCCUPIED" if is_occ else "🟢 AVAILABLE"

        # Build meta line (vehicle type and overlap %)
        if is_occ and result["matched_vehicle"]:
            meta = f"{result['matched_vehicle']} • overlap {result['overlap_ratio']*100:.0f}%"
        else:
            meta = f"overlap {result['overlap_ratio']*100:.0f}%"

        col = grid_cols[idx % 3]
        with col:
            st.markdown(f"""
            <div class="result-row {css_class}">
                <div>
                    <span class="result-label" style="font-size:1rem; font-weight:800;">🅿 {slot_id}</span>
                    <div class="result-meta">{meta}</div>
                </div>
                <span class="{sta_class}">{status_txt}</span>
            </div>
            """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 9 ─ DATABASE SYNC SECTION
# ══════════════════════════════════════════════════════════════════════════════

def render_db_sync() -> None:
    """
    Renders the "Sync to Database" button and handles DB updates.

    When clicked:
      - Iterates over all slot_results from session_state.
      - Calls update_slot_status() from parking_db.py for each slot.
      - Sets only 'available' or 'occupied' (reserved slots are left unchanged).
      - Shows a success summary.

    IMPORTANT: This function writes to parking.db (SQLite).
    After syncing, open parking_app.py to see the updated dashboard.
    """
    slot_results = st.session_state.slot_results

    st.divider()
    st.markdown("#### 💾 Sync Results to Database")

    if st.session_state.db_synced:
        # Already synced — show confirmation
        st.success(
            "✅ Results have been written to **parking.db** (SQLite).  \n"
            "Open `parking_app.py` to see the updated parking dashboard."
        )

        # Show post-sync stats from the live database
        live_stats = get_stats()
        st.markdown(f"""
        <div style="margin-top:8px;">
            <span class="stat-pill pill-available">✅ DB Available: {live_stats['available']}</span>
            <span class="stat-pill pill-occupied">🚗 DB Occupied: {live_stats['occupied']}</span>
            <span class="stat-pill pill-total">⚫ DB Reserved: {live_stats['reserved']}</span>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Show sync button ───────────────────────────────────────────────────────
    st.caption(
        "Click to write AI detection results to `parking.db`.  \n"
        "This updates Available and Occupied slots only. Reserved slots are not touched."
    )

    st.markdown('<div class="sync-btn">', unsafe_allow_html=True)

    if st.button("💾 Sync Detection Results to SQLite Database", use_container_width=True):
        updated_count = 0
        errors        = []

        # Iterate through every slot result and update the database
        for slot_id, result in slot_results.items():
            new_status = result["status"]          # 'available' or 'occupied'
            vehicle_no = result.get("matched_vehicle")   # None if available

            # update_slot_status() is imported from parking_db.py
            success = update_slot_status(
                slot_id        = slot_id,
                new_status     = new_status,
                vehicle_number = vehicle_no if new_status == STATUS_OCCUPIED else None,
            )

            if success:
                updated_count += 1
            else:
                # This happens if the slot_id doesn't exist in the DB yet
                errors.append(slot_id)

        st.session_state.db_synced = True

        if errors:
            st.warning(
                f"✅ {updated_count} slot(s) updated.  \n"
                f"⚠️ Slots not found in DB (add them via parking_db.py): {errors}  \n"
                "Tip: Run `python parking_db.py` first to seed the database."
            )
        else:
            st.success(f"✅ {updated_count} slot(s) successfully written to **parking.db**!")

        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 10 ─ SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

def render_sidebar() -> None:
    """
    Renders the informational sidebar with:
      - Model configuration details
      - How-it-works explanation
      - Detection tips
    """
    with st.sidebar:
        st.markdown("## 🤖 Module 4 — AI Detection")
        st.divider()

        # ── Model info ─────────────────────────────────────────────────────────
        st.markdown("### ⚙️ Configuration")
        st.markdown(f"""
        <div class="info-section">
            <div class="info-row-small">
                <span class="info-k">Model</span>
                <span class="info-v">YOLOv8n (Nano)</span>
            </div>
            <div class="info-row-small">
                <span class="info-k">Dataset</span>
                <span class="info-v">COCO Pretrained</span>
            </div>
            <div class="info-row-small">
                <span class="info-k">Confidence</span>
                <span class="info-v">{YOLO_CONFIDENCE*100:.0f}% minimum</span>
            </div>
            <div class="info-row-small">
                <span class="info-k">Overlap Threshold</span>
                <span class="info-v">{OVERLAP_THRESHOLD*100:.0f}% of slot area</span>
            </div>
            <div class="info-row-small">
                <span class="info-k">DB File</span>
                <span class="info-v">parking.db</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ── How it works ───────────────────────────────────────────────────────
        st.markdown("### 💡 How It Works")
        steps_html = [
            ("1️⃣", "Upload a parking lot image."),
            ("2️⃣", "YOLOv8 scans the image and draws bounding boxes around cars, trucks, buses."),
            ("3️⃣", "Each predefined slot region (from slot_config.py) is compared against detected vehicle boxes."),
            ("4️⃣", "If a vehicle covers ≥15% of a slot → OCCUPIED. Otherwise → AVAILABLE."),
            ("5️⃣", "Results are written to SQLite. Parking dashboard updates."),
        ]
        for icon, text in steps_html:
            st.markdown(
                f"<div style='font-size:0.8rem; color:#c8daf5; padding:6px 0; "
                f"border-bottom:1px solid #0e1c33;'>{icon} {text}</div>",
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Tips ───────────────────────────────────────────────────────────────
        st.markdown("### 📸 Image Tips")
        st.info(
            "**Best results with:**\n\n"
            "• Top-down or slightly angled view\n"
            "• Clear daylight lighting\n"
            "• Vehicles clearly visible\n"
            "• Minimum 640×480 resolution\n\n"
            "**Adjust** `slot_config.py` if the slot grid doesn't match your image.",
            icon="💡",
        )

        st.divider()
        st.markdown("### 🔗 Other Modules")
        st.markdown("📊 [Parking Dashboard](http://localhost:8502) → `parking_app.py`")
        st.markdown("🔐 [Auth System](http://localhost:8503) → `auth_app.py`")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 11 ─ FOOTER
# ══════════════════════════════════════════════════════════════════════════════

def render_footer() -> None:
    """Renders the bottom footer."""
    st.markdown("""
    <div class="footer">
        🤖 Smart Parking System &nbsp;|&nbsp;
        Module 4 – AI Vehicle Detection &nbsp;|&nbsp;
        YOLOv8 + OpenCV + SQLite
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 12 ─ MAIN  (Orchestrator)
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """
    Entry point — assembles the full AI detection page.

    Decision logic:
      - Always render: CSS, session_state, header, sidebar.
      - If detection NOT done → show Step 1 indicator + upload section.
      - If detection IS done  → show Step 3 indicator + results + sync button.
    """
    # ── Setup ──────────────────────────────────────────────────────────────────
    apply_styles()
    init_session_state()
    render_sidebar()
    render_header()

    # ── Load YOLOv8 model (cached — only loads once per session) ───────────────
    model = load_model_cached()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Route to correct view based on detection state ─────────────────────────
    if not st.session_state.detection_done:
        # STEP 1 → Upload
        render_steps(active_step=1)
        st.markdown("<br>", unsafe_allow_html=True)
        render_upload_section(model)

    else:
        # STEP 3 → Results + Sync
        render_steps(active_step=3)
        render_results()
        render_db_sync()

        # ── Reset button ───────────────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("↩️ Upload New Image", use_container_width=False):
            # Clear all detection results from session_state
            st.session_state.detection_done  = False
            st.session_state.original_image  = None
            st.session_state.annotated_image = None
            st.session_state.slot_results    = None
            st.session_state.raw_detections  = None
            st.session_state.db_synced       = False
            st.rerun()

    # ── Footer ─────────────────────────────────────────────────────────────────
    render_footer()


# ══════════════════════════════════════════════════════════════════════════════
# SCRIPT GUARD
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()
