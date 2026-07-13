<p align="center">
  <h1 align="center">🔵 Bluetooth Spatial Interaction System</h1>
  <p align="center">
    <strong>An Invisible User Interface powered by BLE RSSI Signal Processing & Machine Learning</strong>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.10+-blue?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+"/>
    <img src="https://img.shields.io/badge/platform-Windows-0078D6?style=flat-square&logo=windows&logoColor=white" alt="Windows"/>
    <img src="https://img.shields.io/badge/UI-PyQt6-41CD52?style=flat-square&logo=qt&logoColor=white" alt="PyQt6"/>
    <img src="https://img.shields.io/badge/ML-scikit--learn-F7931E?style=flat-square&logo=scikit-learn&logoColor=white" alt="scikit-learn"/>
    <img src="https://img.shields.io/badge/BLE-Bleak-8B5CF6?style=flat-square" alt="Bleak"/>
  </p>
</p>

---

## 📖 Overview

This system detects a user's **position, movement, and hand gestures** relative to a laptop using only the **Bluetooth Low Energy (BLE) RSSI signal** from their smartphone — no cameras, GPS, or wearable sensors required.

The filtered RSSI stream drives a 7-phase pipeline that goes from raw radio scanning all the way to **executing real OS-level actions** (volume control, screen lock, wake, slide navigation, Do Not Disturb toggle) based on recognized spatial gestures, all visualized through a real-time PyQt6 dashboard.

### ✨ Key Features

- **Zero external hardware** — works with any BLE-capable laptop and smartphone
- **Real-time spatial detection** — tracks whether the user is approaching, present, departing, or absent
- **ML-powered gesture recognition** — classifies 4 gesture types from RSSI patterns using a trained Random Forest model (99.2% test accuracy)
- **Context-aware action mapping** — the same gesture triggers different actions depending on the current context (Work, Focus, Presentation, Away)
- **OS-level automation** — executes real Windows actions: volume control via `pycaw`, screen lock, wake, arrow-key slides, and Focus Assist DND toggle
- **Safety guard** — blocks unsafe actions (e.g., lock screen when user is nearby) and enforces cooldowns
- **Live PyQt6 dashboard** — dark-themed real-time UI with RSSI graph, spatial state, gesture/action feed, and session statistics
- **Demo simulation mode** — full 90-second walkthrough without needing a live BLE device

---

## 🏗️ Architecture

The system is organized into **7 sequential phases**, each building on the output of the previous one:

```
Phase 1          Phase 2              Phase 3              Phase 4
BLE Scanner  →  Signal Pipeline  →  Spatial Detection  →  Gesture Recognition
(Bleak)         (MA + Kalman)        (State Machine)       (Random Forest ML)
    │                │                     │                      │
    ▼                ▼                     ▼                      ▼
raw_scan.jsonl  filtered_scan.jsonl  spatial_events.jsonl  gesture_events.jsonl
                                                                  │
                                          ┌───────────────────────┘
                                          ▼
                                     Phase 5              Phase 6           Phase 7
                                  Context Engine  →  Action Executor  →  PyQt6 Dashboard
                                  (Rule-based)       (OS Automation)     (Real-time UI)
                                       │                    │
                                       ▼                    ▼
                              context_events.jsonl    action_log.jsonl
```

---

## 📁 Project Structure

```
bluetooth/
├── main.py                          # Entry point — orchestrates all phases
├── requirements.txt                 # Python dependencies
├── identify_phone.py                # Utility to find target device MAC address
├── find_phone.py                    # BLE device discovery helper
├── scan_test.py                     # Quick BLE scan test
├── classic_scan_test.py             # Bluetooth Classic scan test
├── project_memory.txt               # Development notes & parameter reference
│
├── scanner/                         # Phase 1: BLE Scanner
│   └── ble_scanner.py               #   Real-time BLE advertisement scanner (Bleak)
│
├── signal_processing/               # Phase 2: Signal Pipeline
│   ├── device_filter.py             #   Filters raw log for target device + watchdog
│   ├── moving_average.py            #   Moving average smoother (window=5)
│   ├── kalman_filter.py             #   1D Kalman filter (Q=0.008, R=2.0)
│   ├── signal_pipeline.py           #   Orchestrates filter chain
│   └── terminal_visualizer.py       #   Terminal ASCII signal display
│
├── gesture_engine/                  # Phases 3 & 4: Spatial + Gesture
│   ├── calibrator.py                #   One-time RSSI baseline calibration (10s)
│   ├── spatial_detector.py          #   Trend analysis & spatial state proposer
│   ├── state_machine.py             #   State graph with anti-flicker (2s hold)
│   ├── feature_extractor.py         #   13-feature extraction from RSSI windows
│   ├── gesture_recogniser.py        #   Real-time gesture classification loop
│   ├── train_model.py               #   Model training (RandomForest vs SVM)
│   ├── evaluate_model.py            #   Detailed model evaluation & metrics
│   └── test_spatial.py              #   Phase 3 unit tests
│
├── context_engine/                  # Phase 5: Context Awareness
│   ├── contexts.py                  #   Context definitions & priority rules
│   ├── context_detector.py          #   Rule-based context evaluation
│   ├── action_resolver.py           #   Gesture → action lookup (12 mappings)
│   ├── context_pipeline.py          #   Real-time context evaluation loop
│   ├── session_tracker.py           #   Session statistics & auto-save
│   └── test_context.py              #   Context engine tests
│
├── automation/                      # Phase 6: Action Execution
│   ├── action_executor.py           #   Central executor dispatcher
│   ├── safety_guard.py              #   Pre-execution safety checks
│   ├── volume_executor.py           #   Master volume control (pycaw)
│   ├── lock_executor.py             #   Screen lock (ctypes)
│   ├── wake_executor.py             #   Screen wake (mouse + pyautogui)
│   ├── slide_executor.py            #   Slide navigation (arrow keys)
│   ├── dnd_executor.py              #   Do Not Disturb / Focus Assist toggle
│   └── test_automation.py           #   Automation tests
│
├── ui/                              # Phase 7: PyQt6 Dashboard
│   ├── dashboard.py                 #   Main window with dark theme
│   ├── log_reader.py                #   Background log file tailer (QThread)
│   ├── demo_mode.py                 #   90-second simulation generator
│   ├── test_pyqt6.py                #   PyQt6 installation test
│   └── widgets/
│       ├── rssi_graph.py            #   Live RSSI line graph (raw + filtered)
│       ├── status_panel.py          #   Spatial state, gesture & action cards
│       └── session_stats.py         #   Context time, gesture counts, volume
│
├── data_collection/                 # Training Data
│   ├── collect_gestures.py          #   Interactive data collection tool
│   ├── generate_synthetic_data.py   #   Synthetic training data generator
│   └── gesture_data.csv             #   Collected gesture samples (600 total)
│
├── models/                          # Trained ML Models
│   ├── gesture_model.pkl            #   Random Forest classifier
│   ├── scaler.pkl                   #   Feature scaler
│   └── model_info.json              #   Model metadata & accuracy
│
└── logs/                            # Runtime Logs (auto-generated)
    ├── raw_scan.jsonl                #   Raw BLE advertisements
    ├── filtered_scan.jsonl           #   Filtered RSSI readings
    ├── spatial_events.jsonl          #   Spatial state transitions
    ├── gesture_events.jsonl          #   Confirmed gesture events
    ├── context_events.jsonl          #   Context changes
    ├── action_log.jsonl              #   Executed actions
    ├── safety_blocks.jsonl           #   Blocked unsafe actions
    ├── calibration.json              #   Saved calibration data
    └── session_summary.json          #   Session statistics
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Windows 10/11** (required for OS automation actions)
- **Bluetooth adapter** on the laptop (built-in or USB dongle)
- **BLE-capable smartphone** (the target device to track)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/sahil0438/bluetooth-spatial-interaction.git
   cd bluetooth-spatial-interaction
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### BLE Beacon Setup (Recommended)

For best results, install a BLE beacon app on your phone to increase the BLE advertising frequency:

1. Install **LightBlue** (available on [iOS](https://apps.apple.com/app/lightblue/id557428110) / [Android](https://play.google.com/store/apps/details?id=com.punchthrough.lightblueexplorer))
2. Create a new **Virtual Peripheral** in the app
3. Set the advertising interval to the **minimum** (e.g., 100–200ms)
4. Set a recognizable **beacon name**
5. Start advertising
6. Use `--target-name "YOUR_BEACON_NAME"` when launching the system

> **Why?** A phone's default BLE advertisements are controlled by the OS power manager and typically broadcast every 5–6 seconds. A beacon app broadcasts much faster (10x–50x), giving the gesture engine significantly more RSSI data to work with.

---

## 💻 Usage

### Live Mode (Full System)

Start all 7 phases with the PyQt6 dashboard:

```bash
python main.py --target-name "Nothing Phone (2a)"
```

With a specific MAC address:

```bash
python main.py --target-name "Nothing Phone (2a)" --target-address "28:D2:5E:D7:C0:4B"
```

### Demo Mode (Simulation)

Run the dashboard with a simulated 90-second workflow — no BLE device needed:

```bash
python main.py --demo
```

### Identify Your Device

Find your phone's BLE name and MAC address:

```bash
python identify_phone.py
```

---

## 🧠 How It Works

### Phase 1 — BLE Scanner

Uses the [Bleak](https://github.com/hbldh/bleak) library to passively scan for BLE advertisements. Every detected packet (device name, MAC address, RSSI, manufacturer data) is logged to `raw_scan.jsonl`. A live terminal table shows all nearby devices with the target highlighted.

### Phase 2 — Signal Pipeline

Raw RSSI values are inherently noisy. The pipeline applies two sequential filters:

| Filter | Purpose | Parameters |
|---|---|---|
| **Moving Average** | Removes high-frequency spikes | Window size = 5 |
| **1D Kalman Filter** | Smooths remaining noise while tracking real trends | Q = 0.008, R = 2.0 |

A **device watchdog** raises a `device_lost` event if the target is not seen for more than 5 seconds.

### Phase 3 — Spatial Detection

A sliding window of the last 10 filtered RSSI readings is analyzed using **linear regression** (`numpy.polyfit`) to determine the signal trend:

| State | Condition |
|---|---|
| **APPROACHING** | Slope > +1.5 dBm/s, RSSI > −80 dBm |
| **PRESENT_STABLE** | Slope stable, RSSI between −40 and −80 dBm, variation ≤ 10 dBm |
| **DEPARTING** | Slope < −1.5 dBm/s |
| **RAPID_APPROACH** | RSSI increases > 20 dBm within 2 seconds |
| **ABSENT** | RSSI < −100 dBm, device lost, or > 10s timeout |

A **state machine** enforces valid transitions (`ABSENT → APPROACHING → PRESENT_STABLE → DEPARTING → ABSENT`) with a 2-second anti-flicker hold time.

### Phase 4 — Gesture Recognition (ML)

**13 features** are extracted from a rolling window of 8 filtered RSSI readings:

```
mean_rssi, std_rssi, slope, min_rssi, max_rssi, rssi_range,
dip_count, dip_depth, recovery_strength, crossing_rate,
first_half_mean, second_half_mean, momentum
```

A **Random Forest** classifier (100 trees, 99.2% test accuracy) recognizes 4 gesture types:

| Gesture | Pattern | Duration |
|---|---|---|
| 🔄 **ROTATION** | Dip-recover wave ×2 | ~4s |
| 🚶 **SLOW_DEPARTURE** | Gradual RSSI decline | ~5s |
| ✋ **DOUBLE_APPROACH** | Approach → pause → approach | ~4s |
| 💤 **IDLE** | Stable signal, no motion | continuous |

Gestures require **triple confirmation** (3 consecutive matching predictions at ≥70% confidence) and have a 2-second cooldown between firings.

### Phase 5 — Context Awareness

A rule-based engine determines the current **context** and maps gestures to appropriate actions:

| Context | Trigger | ROTATION → | SLOW_DEPARTURE → | DOUBLE_APPROACH → |
|---|---|---|---|---|
| **WORK_MODE** | Present during 08:00–22:00 | Volume Adjust | Lock Screen (3s delay) | Wake Screen |
| **FOCUS_MODE** | Present >10min + no gestures >5min | Toggle DND | Lock Screen (instant) | Exit Focus |
| **PRESENTATION_MODE** | Double Approach ×2 within 10s | Next Slide | Previous Slide | Exit Presentation |
| **AWAY_MODE** | Absent >30s | — | — | Wake Screen |

### Phase 6 — Action Execution

Translates context decisions into **real Windows OS actions**:

| Action | Implementation |
|---|---|
| **Volume Control** | `pycaw` — Windows Core Audio API |
| **Lock Screen** | `ctypes.windll.user32.LockWorkStation()` |
| **Wake Screen** | Mouse move + Shift key via `pyautogui` |
| **Slide Navigation** | Arrow keys via `pyautogui` |
| **DND Toggle** | Windows Focus Assist via registry |

A **Safety Guard** blocks actions when confidence is below 70%, enforces 1.5s cooldowns, and warns before locking the screen when the user is nearby (RSSI ≥ −60 dBm).

### Phase 7 — PyQt6 Dashboard

A polished dark-themed real-time dashboard showing:

- **Live RSSI graph** with raw and filtered traces
- **Target device card** with signal strength bar and distance estimate
- **Spatial state** indicator with confidence and trend
- **Gesture & action feed** with live updates
- **Context display** showing current mode and duration
- **Session statistics** — gesture counts, action counts, context time distribution, volume level

---

## 🏋️ Training Your Own Model

### Collect Real Gesture Data

While `main.py` is running in one terminal, open a second terminal:

```bash
python -m data_collection.collect_gestures
```

Follow the interactive prompts to record each gesture type. The tool captures real BLE readings during a 4-second window and interpolates them to 8 evenly-spaced values. Aim for **50+ samples per gesture** (200+ total).

### Generate Synthetic Data

To supplement real data with synthetic samples:

```bash
python -m data_collection.generate_synthetic_data
```

### Train the Model

```bash
python -m gesture_engine.train_model
```

This compares **Random Forest** (100 trees) vs **SVM** (RBF kernel) and saves the better-performing model automatically.

### Evaluate the Model

```bash
python -m gesture_engine.evaluate_model
```

Outputs detailed metrics: accuracy, confusion matrix, per-class precision/recall/F1, and feature importances.

---

## 🧪 Testing

```bash
# Phase 3 — Spatial detection unit tests
python -m gesture_engine.test_spatial

# Phase 5 — Context engine tests
python -m context_engine.test_context

# Phase 6 — Automation tests (--skip-lock to avoid locking your screen)
python -m automation.test_automation --skip-lock

# Phase 7 — Verify PyQt6 installation
python ui/test_pyqt6.py
```

---

## ⚙️ Configuration

Key parameters are defined as constants at the top of each module:

| Parameter | File | Default | Description |
|---|---|---|---|
| `DEVICE_TIMEOUT` | `ble_scanner.py` | 30s | Remove device from table after silence |
| `DISPLAY_REFRESH` | `ble_scanner.py` | 0.3s | Terminal table refresh rate |
| Moving Average window | `moving_average.py` | 5 | Smoothing window size |
| Kalman Q | `kalman_filter.py` | 0.008 | Process noise covariance |
| Kalman R | `kalman_filter.py` | 2.0 | Measurement noise covariance |
| `BUFFER_SIZE` | `gesture_recogniser.py` | 8 | RSSI readings per gesture window |
| `CONFIDENCE_THRESHOLD` | `gesture_recogniser.py` | 0.70 | Minimum prediction confidence |
| `CONSECUTIVE_REQUIRED` | `gesture_recogniser.py` | 3 | Matching predictions to confirm |
| `COOLDOWN_SECONDS` | `gesture_recogniser.py` | 2.0s | Minimum time between gesture firings |

---

## 📊 Model Performance

The pre-trained model achieves:

| Metric | Value |
|---|---|
| **Test Accuracy** | 99.2% |
| **Model Type** | Random Forest (100 trees) |
| **Training Samples** | 600 (150 per class) |
| **Features** | 13 per sample |
| **Classes** | ROTATION, SLOW_DEPARTURE, DOUBLE_APPROACH, IDLE |

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| BLE Scanning | [Bleak](https://github.com/hbldh/bleak) |
| Signal Processing | NumPy, SciPy |
| Machine Learning | scikit-learn, joblib |
| Desktop UI | PyQt6 |
| Volume Control | [pycaw](https://github.com/AndreMiras/pycaw) (Windows Core Audio) |
| Screen Automation | pyautogui, ctypes |
| Data Format | JSONL (streaming logs), CSV (training data) |

---

## 📝 License

This project is for educational and research purposes.

---

## 🙏 Acknowledgments

- [Bleak](https://github.com/hbldh/bleak) — Cross-platform BLE library for Python
- [pycaw](https://github.com/AndreMiras/pycaw) — Python Core Audio Windows Library
- [scikit-learn](https://scikit-learn.org/) — Machine learning framework
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) — Python bindings for Qt6
