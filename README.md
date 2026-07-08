# 🅿️ Smart Parking Web Application
### AI-Based Slot Detection and Navigation System

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-red?logo=streamlit)](https://streamlit.io)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.9+-green?logo=opencv)](https://opencv.org)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-purple)](https://ultralytics.com)
[![SQLite](https://img.shields.io/badge/Database-SQLite-blue?logo=sqlite)](https://sqlite.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 📌 Project Overview

A beginner-friendly Computer Vision project that uses **YOLOv8** (pretrained object detection model) to automatically detect vehicles in a parking lot video feed and displays real-time parking slot availability on a **Streamlit** web dashboard.

Built as a university B.Tech project, this system demonstrates the intersection of **Artificial Intelligence**, **Computer Vision**, and **Web Development**.

---

## ✨ Key Features

- 🎥 **Video-Based Detection** – Processes parking lot video to detect vehicles
- 🤖 **YOLOv8 AI Detection** – Uses pretrained deep learning model (no custom training needed)
- 🟩 **Live Slot Status** – Green (Available) / Red (Occupied) visual grid
- 📊 **Real-time Dashboard** – Streamlit dashboard with auto-refresh
- 💾 **SQLite Database** – Lightweight, zero-setup data persistence
- 🧩 **Modular Architecture** – Clean separation of concerns across layers

---

## 🏗️ Project Architecture

```
smart-parking/
│
├── app/                          # Web UI (Streamlit)
│   ├── dashboard.py              # Main application entry point
│   ├── components/
│   │   ├── slot_grid.py          # Parking grid visual component
│   │   └── stats_card.py         # Metrics cards component
│   └── assets/
│       └── style.css             # Custom theming
│
├── detection/                    # Computer Vision core
│   ├── detector.py               # YOLOv8 inference engine
│   ├── slot_manager.py           # Slot occupancy logic
│   └── video_processor.py        # Frame extraction & pipeline
│
├── database/                     # Data persistence
│   ├── db_handler.py             # All SQLite operations
│   └── schema.sql                # Database schema
│
├── config/
│   └── settings.py               # Global configuration constants
│
├── data/
│   ├── videos/                   # Parking lot footage
│   └── images/                   # Layout reference images
│
├── models/                       # YOLO weights (auto-downloaded)
│
├── tests/                        # Unit tests
├── notebooks/                    # Jupyter exploration notebooks
├── scripts/                      # Setup & utility scripts
└── docs/                         # Diagrams, screenshots
```

---

## 🔄 System Flow

```
Video File → Frame Extraction → YOLOv8 Detection
     ↓                                ↓
Slot Coordinates            Detected Bounding Boxes
     └──────────── IoU Check ────────────┘
                       ↓
              Slot Status (Occupied/Available)
                       ↓
              SQLite Database Update
                       ↓
              Streamlit Dashboard Refresh
```

---

## 🛠️ Technology Stack

| Technology | Version | Role |
|---|---|---|
| Python | 3.10+ | Core language |
| Streamlit | 1.35+ | Web dashboard framework |
| OpenCV | 4.9+ | Video/image processing |
| Ultralytics (YOLOv8) | 8.x | Vehicle detection AI |
| SQLite3 | Built-in | Database |
| NumPy | 1.26+ | Array operations |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- VS Code (recommended)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/smart-parking.git
cd smart-parking
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Add Your Parking Video

Place a parking lot video in `data/videos/` and update the path in `config/settings.py`.

> 💡 **Tip**: You can download sample parking lot videos from YouTube or use your phone camera.

### 5. Initialize the Database

```bash
python scripts/seed_database.py
```

### 6. Define Parking Slot Coordinates

```bash
python scripts/setup_slots.py
```

### 7. Run the Dashboard

```bash
streamlit run app/dashboard.py
```

Open your browser at `http://localhost:8501` 🎉

---

## 📸 Screenshots

> *(Add screenshots here after building the dashboard)*

---

## 📚 How It Works

### 1. Vehicle Detection (YOLOv8)
YOLOv8 is a state-of-the-art object detection model pretrained on the **COCO dataset**, which includes 80 object classes — including `car`, `truck`, and `bus`. We use this model "as-is" without any custom training.

### 2. Slot Occupancy Check
Each parking slot is defined as a rectangular region (bounding box) on the video frame. After detection, we calculate the **Intersection over Union (IoU)** between each slot rectangle and each detected vehicle. If IoU exceeds a threshold (e.g., 0.3), the slot is marked **Occupied**.

### 3. Database Update
After every processed frame, the slot statuses are written to a **SQLite** database table. This decouples the detection pipeline from the UI.

### 4. Streamlit Dashboard
The dashboard reads slot statuses from the SQLite DB and renders them as a color-coded grid. Streamlit's `st.rerun()` is used to auto-refresh the page every few seconds.

---

## 🧪 Running Tests

```bash
python -m pytest tests/ -v
```

---

## 📋 Dependencies (`requirements.txt`)

```
streamlit>=1.35.0
opencv-python>=4.9.0
ultralytics>=8.0.0
numpy>=1.26.0
pytest>=7.0.0
```

---

## 🗂️ Development Roadmap

- [x] Project architecture design
- [ ] Database schema and handler
- [ ] YOLOv8 detection module
- [ ] Slot occupancy logic
- [ ] Video processing pipeline
- [ ] Streamlit dashboard
- [ ] Unit tests
- [ ] Documentation and demo

---

## 🎓 Academic Information

| Field | Details |
|---|---|
| Project Type | B.Tech CSE Mini Project |
| Domain | Computer Vision + Web Development |
| Technique | Object Detection (YOLOv8) |
| Dataset | COCO (pretrained weights) |
| Difficulty | Beginner–Intermediate |

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

---

## 📄 License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgements

- [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics) for the detection model
- [Streamlit](https://streamlit.io) for the incredible Python dashboard framework
- [OpenCV](https://opencv.org) for computer vision utilities
