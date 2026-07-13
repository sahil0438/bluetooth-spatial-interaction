import sys
import json
import time
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSplitter, QFrame, QApplication, QComboBox,
    QGraphicsDropShadowEffect, QProgressBar, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QSize
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QLinearGradient, QPen

# Import custom widgets
from ui.widgets.rssi_graph import RSSIGraph
from ui.widgets.status_panel import StatusPanel
from ui.widgets.session_stats import SessionStats
from ui.log_reader import LogReader
from ui.demo_mode import DemoModeRunner


# ─── Target Device Card ────────────────────────────────────────────────────
class DeviceCard(QFrame):
    """Shows target device information: name, address, signal bar, distance."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("deviceCard")
        self.setStyleSheet("""
            QFrame#deviceCard {
                background-color: rgba(22, 27, 34, 220);
                border: 1px solid rgba(48, 54, 61, 180);
                border-radius: 12px;
                padding: 14px;
            }
        """)
        self.setMinimumHeight(150)
        self.setMaximumHeight(180)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor("#58a6ff"))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Header
        hdr = QLabel("TARGET DEVICE")
        hdr.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        hdr.setStyleSheet("color: #8b949e; letter-spacing: 1.5px;")
        layout.addWidget(hdr)

        # Device name + status dot
        name_row = QHBoxLayout()
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #f85149; font-size: 14px;")
        self.device_name = QLabel("Nothing Phone (2a)")
        self.device_name.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.device_name.setStyleSheet("color: #e6edf3;")
        name_row.addWidget(self.status_dot)
        name_row.addSpacing(6)
        name_row.addWidget(self.device_name)
        name_row.addStretch()
        layout.addLayout(name_row)

        # Address
        self.device_address = QLabel("Address: Scanning...")
        self.device_address.setFont(QFont("Consolas", 9))
        self.device_address.setStyleSheet("color: #8b949e;")
        layout.addWidget(self.device_address)

        # Signal strength bar
        sig_row = QHBoxLayout()
        sig_row.setSpacing(8)
        sig_lbl = QLabel("Signal")
        sig_lbl.setFont(QFont("Segoe UI", 9))
        sig_lbl.setStyleSheet("color: #8b949e;")
        self.signal_bar = QProgressBar()
        self.signal_bar.setRange(0, 100)
        self.signal_bar.setValue(0)
        self.signal_bar.setTextVisible(False)
        self.signal_bar.setFixedHeight(8)
        self.signal_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(13, 17, 23, 200);
                border: 1px solid #21262d;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #f85149;
                border-radius: 4px;
            }
        """)
        self.signal_value = QLabel("— dBm")
        self.signal_value.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.signal_value.setStyleSheet("color: #f85149;")
        self.signal_value.setFixedWidth(75)
        self.signal_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        sig_row.addWidget(sig_lbl)
        sig_row.addWidget(self.signal_bar, 1)
        sig_row.addWidget(self.signal_value)
        layout.addLayout(sig_row)

        # Distance estimate + status
        bottom_row = QHBoxLayout()
        self.distance_label = QLabel("Distance: —")
        self.distance_label.setFont(QFont("Segoe UI", 9))
        self.distance_label.setStyleSheet("color: #8b949e;")
        self.status_label = QLabel("Scanning...")
        self.status_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.status_label.setStyleSheet("color: #d29922;")
        bottom_row.addWidget(self.distance_label)
        bottom_row.addStretch()
        bottom_row.addWidget(self.status_label)
        layout.addLayout(bottom_row)

    def update_rssi(self, rssi):
        """Update signal bar and distance estimate from RSSI."""
        if rssi <= -115:
            # Absent
            self.signal_bar.setValue(0)
            self.signal_value.setText("— dBm")
            self.signal_value.setStyleSheet("color: #f85149;")
            self.distance_label.setText("Distance: —")
            self.status_label.setText("Not Detected")
            self.status_label.setStyleSheet("color: #f85149; font-weight: bold;")
            self.status_dot.setStyleSheet("color: #f85149; font-size: 14px;")
            self._set_bar_color("#f85149")
        else:
            # Map RSSI (-100 to -30) to percentage (0-100)
            pct = max(0, min(100, int(((rssi + 100) / 70) * 100)))
            self.signal_bar.setValue(pct)
            self.signal_value.setText(f"{rssi:.0f} dBm")

            # Distance estimate (rough log-distance model)
            # d = 10 ^ ((TxPower - RSSI) / (10 * n))
            # Using TxPower=-45, n=2.5
            try:
                import math
                dist = 10 ** ((-45 - rssi) / 25)
                if dist < 1:
                    dist_str = f"{dist * 100:.0f} cm"
                else:
                    dist_str = f"{dist:.1f} m"
                self.distance_label.setText(f"Distance: ~{dist_str}")
            except Exception:
                self.distance_label.setText("Distance: —")

            # Color based on signal strength
            if rssi >= -45:
                color = "#3fb950"
                status = "Excellent"
            elif rssi >= -60:
                color = "#58a6ff"
                status = "Good"
            elif rssi >= -75:
                color = "#d29922"
                status = "Fair"
            else:
                color = "#f85149"
                status = "Weak"

            self.signal_value.setStyleSheet(f"color: {color};")
            self.status_label.setText(status)
            self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.status_dot.setStyleSheet(f"color: {color}; font-size: 14px;")
            self._set_bar_color(color)

    def _set_bar_color(self, color):
        self.signal_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(13, 17, 23, 200);
                border: 1px solid #21262d;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
        """)

    def set_device_info(self, name, address=None):
        self.device_name.setText(name)
        if address:
            self.device_address.setText(f"Address: {address}")
        else:
            self.device_address.setText("Address: Scanning...")


# ─── Main Dashboard Window ─────────────────────────────────────────────────

MAIN_STYLESHEET = """
    QMainWindow {
        background-color: #0d1117;
    }
    QWidget#topBar {
        background-color: rgba(22, 27, 34, 240);
        border-bottom: 1px solid #21262d;
    }
    QLabel {
        color: #e6edf3;
        font-family: 'Segoe UI', Arial, sans-serif;
    }
    QPushButton {
        background-color: rgba(48, 54, 61, 200);
        color: #e6edf3;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 6px 14px;
        font-size: 11px;
        font-weight: bold;
        font-family: 'Segoe UI', Arial, sans-serif;
    }
    QPushButton:hover {
        background-color: rgba(48, 54, 61, 255);
        border: 1px solid #58a6ff;
    }
    QPushButton:pressed {
        background-color: rgba(33, 38, 45, 255);
    }
    QPushButton#stopBtn {
        background-color: rgba(248, 81, 73, 0.15);
        color: #f85149;
        border: 1px solid rgba(248, 81, 73, 0.4);
    }
    QPushButton#stopBtn:hover {
        background-color: rgba(248, 81, 73, 0.25);
        border: 1px solid #f85149;
    }
    QPushButton#demoBtn {
        background-color: rgba(63, 185, 80, 0.15);
        color: #3fb950;
        border: 1px solid rgba(63, 185, 80, 0.4);
    }
    QPushButton#demoBtn:hover {
        background-color: rgba(63, 185, 80, 0.25);
        border: 1px solid #3fb950;
    }
    QComboBox {
        background-color: rgba(22, 27, 34, 240);
        color: #e6edf3;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 5px 10px;
        font-size: 11px;
        font-family: 'Segoe UI', Arial, sans-serif;
        min-width: 200px;
    }
    QComboBox:hover {
        border: 1px solid #58a6ff;
    }
    QComboBox::drop-down {
        border: none;
        width: 24px;
    }
    QComboBox::down-arrow {
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid #8b949e;
        margin-right: 8px;
    }
    QComboBox QAbstractItemView {
        background-color: #161b22;
        color: #e6edf3;
        border: 1px solid #30363d;
        selection-background-color: rgba(88, 166, 255, 0.2);
        selection-color: #58a6ff;
        outline: none;
        padding: 4px;
    }
    QSplitter::handle {
        background-color: #21262d;
    }
    QSplitter::handle:hover {
        background-color: #58a6ff;
    }
"""


class MainWindow(QMainWindow):
    def __init__(self, is_demo_only=False):
        super().__init__()
        self.is_demo_only = is_demo_only

        # Setup absolute paths
        self.root_dir = Path(__file__).resolve().parent.parent
        self.target_change_file = self.root_dir / "logs" / "target_change.json"

        # Current target
        self.current_target_name = "Nothing Phone (2a)"
        self.current_target_address = None

        # Track discovered devices for dropdown
        self._device_list = []  # list of {name, address, rssi}
        self._last_filtered_rssi = -127.0

        self.setWindowTitle("Bluetooth Spatial Interaction System")
        self.setMinimumSize(1050, 700)

        self.setStyleSheet(MAIN_STYLESHEET)
        self.init_ui()

        # Session timer
        self.start_time = time.time()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_session_timer)
        self.timer.start(1000)

        # Live indicator pulse
        self.pulse_state = True
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self.pulse_live_indicator)
        self.pulse_timer.start(800)

        # Threads
        self.demo_runner = None
        self.log_reader = LogReader(self.root_dir)

        # Connect signals
        self.log_reader.rssi_updated.connect(self.on_rssi_updated)
        self.log_reader.spatial_state_changed.connect(self.on_spatial_changed)
        self.log_reader.gesture_detected.connect(self.on_gesture_detected)
        self.log_reader.action_executed.connect(self.on_action_executed)
        self.log_reader.context_changed.connect(self.on_context_changed)
        self.log_reader.session_updated.connect(self.on_session_updated)
        self.log_reader.devices_updated.connect(self.on_devices_updated)

        self.log_reader.start()

        if self.is_demo_only:
            self.start_demo_mode()

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ─── TOP BAR ──────────────────────────────────────────────
        top_bar = QWidget()
        top_bar.setObjectName("topBar")
        top_bar.setFixedHeight(56)
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(16, 0, 16, 0)
        top_bar_layout.setSpacing(0)

        # Left: Live dot + Title
        left_section = QHBoxLayout()
        left_section.setSpacing(8)

        self.lbl_live = QLabel("●")
        self.lbl_live.setFont(QFont("Segoe UI", 12))
        self.lbl_live.setStyleSheet("color: #3fb950;")
        self.lbl_live.setFixedWidth(18)

        self.lbl_mode = QLabel("LIVE")
        self.lbl_mode.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_mode.setStyleSheet("""
            color: #3fb950;
            background-color: rgba(63,185,80,0.12);
            border: 1px solid rgba(63,185,80,0.3);
            border-radius: 4px;
            padding: 2px 8px;
        """)

        self.lbl_title = QLabel("BT Spatial System")
        self.lbl_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #e6edf3;")

        left_section.addWidget(self.lbl_live)
        left_section.addWidget(self.lbl_mode)
        left_section.addSpacing(12)
        left_section.addWidget(self.lbl_title)

        # Center: Device selector
        center_section = QHBoxLayout()
        center_section.setSpacing(8)

        device_label = QLabel("Target:")
        device_label.setFont(QFont("Segoe UI", 10))
        device_label.setStyleSheet("color: #8b949e;")

        self.device_combo = QComboBox()
        self.device_combo.setEditable(True)
        self.device_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.device_combo.addItem("Nothing Phone (2a)")
        self.device_combo.setCurrentText("Nothing Phone (2a)")
        self.device_combo.setMinimumWidth(250)
        self.device_combo.setMaximumWidth(350)
        self.device_combo.currentTextChanged.connect(self.on_device_selection_changed)

        center_section.addWidget(device_label)
        center_section.addWidget(self.device_combo)

        # Right: Timer + buttons
        right_section = QHBoxLayout()
        right_section.setSpacing(10)

        self.lbl_timer = QLabel("00:00:00")
        self.lbl_timer.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        self.lbl_timer.setStyleSheet("color: #58a6ff;")

        self.btn_demo = QPushButton("▶ Demo")
        self.btn_demo.setObjectName("demoBtn")
        self.btn_demo.clicked.connect(self.toggle_demo_mode)

        self.btn_stop = QPushButton("■ Stop")
        self.btn_stop.setObjectName("stopBtn")
        self.btn_stop.clicked.connect(self.stop_system)

        right_section.addWidget(self.lbl_timer)
        right_section.addSpacing(6)
        right_section.addWidget(self.btn_demo)
        right_section.addWidget(self.btn_stop)

        top_bar_layout.addLayout(left_section)
        top_bar_layout.addStretch()
        top_bar_layout.addLayout(center_section)
        top_bar_layout.addStretch()
        top_bar_layout.addLayout(right_section)

        main_layout.addWidget(top_bar)

        # ─── CONTENT AREA ─────────────────────────────────────────
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)

        # Top splitter: Graph (left) + Status (right)
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.setHandleWidth(3)

        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter.setHandleWidth(3)

        # Left: RSSI Graph
        self.rssi_graph = RSSIGraph()
        h_splitter.addWidget(self.rssi_graph)

        # Right: Device Card + Status Panel (stacked)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.device_card = DeviceCard()
        right_layout.addWidget(self.device_card)

        # Scroll Area for status panel to prevent squishing
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(13, 17, 23, 100);
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(48, 54, 61, 200);
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(88, 166, 255, 150);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)

        self.status_panel = StatusPanel()
        scroll_area.setWidget(self.status_panel)
        right_layout.addWidget(scroll_area, 1)

        h_splitter.addWidget(right_panel)
        h_splitter.setSizes([580, 420])
        h_splitter.setCollapsible(0, False)
        h_splitter.setCollapsible(1, False)

        v_splitter.addWidget(h_splitter)

        # Bottom: Session Stats
        self.session_stats = SessionStats()
        v_splitter.addWidget(self.session_stats)
        v_splitter.setSizes([400, 260])
        v_splitter.setCollapsible(0, False)
        v_splitter.setCollapsible(1, False)

        content_layout.addWidget(v_splitter)
        main_layout.addWidget(content_widget)

        self.setCentralWidget(main_widget)

    # ─── Session Timer ─────────────────────────────────────────────
    def update_session_timer(self):
        elapsed = int(time.time() - self.start_time)
        hrs = elapsed // 3600
        mins = (elapsed % 3600) // 60
        secs = elapsed % 60
        self.lbl_timer.setText(f"{hrs:02d}:{mins:02d}:{secs:02d}")

    # ─── Live Pulse ────────────────────────────────────────────────
    def pulse_live_indicator(self):
        self.pulse_state = not self.pulse_state
        if self.pulse_state:
            self.lbl_live.setStyleSheet("color: #3fb950;")
        else:
            self.lbl_live.setStyleSheet("color: rgba(63,185,80,0.3);")

    # ─── Device Selection ──────────────────────────────────────────
    def on_device_selection_changed(self, text):
        """User selected a different device from the dropdown."""
        if not text or text == self.current_target_name:
            return

        self.current_target_name = text

        # Find address for this device
        address = None
        for dev in self._device_list:
            if dev.get("name") == text:
                address = dev.get("address")
                break
        self.current_target_address = address

        # Update device card
        self.device_card.set_device_info(text, address)

        # Write target change file for the backend to pick up
        try:
            change_data = {
                "target_name": text,
                "target_address": address,
                "timestamp": time.time(),
            }
            with open(self.target_change_file, "w", encoding="utf-8") as f:
                json.dump(change_data, f)
            print(f"[DASHBOARD] Target changed to: {text}" +
                  (f" ({address})" if address else ""))
        except Exception as e:
            print(f"[DASHBOARD] Failed to write target change: {e}")

    @pyqtSlot(list)
    def on_devices_updated(self, devices):
        """Update the device dropdown with discovered devices."""
        self._device_list = devices

        # Update nearby count in session stats
        self.session_stats.update_nearby_count(len(devices))

        # Remember current selection
        current = self.device_combo.currentText()

        # Block signals to prevent re-triggering on_device_selection_changed
        self.device_combo.blockSignals(True)
        self.device_combo.clear()

        # Always include the default device at the top
        self.device_combo.addItem("Nothing Phone (2a)")

        # Add discovered named devices (excluding if already the default)
        seen = {"Nothing Phone (2a)"}
        for dev in devices:
            name = dev.get("name", "")
            if name and name not in seen:
                rssi = dev.get("rssi", -127)
                self.device_combo.addItem(f"{name}  ({rssi} dBm)")
                seen.add(name)

        # Restore selection
        # Try to find exact match first
        idx = self.device_combo.findText(current)
        if idx >= 0:
            self.device_combo.setCurrentIndex(idx)
        else:
            # Try to match by device name prefix (without the RSSI suffix)
            for i in range(self.device_combo.count()):
                item_text = self.device_combo.itemText(i)
                if item_text.startswith(current.split("  (")[0]):
                    self.device_combo.setCurrentIndex(i)
                    break

        self.device_combo.blockSignals(False)

        # Update device card address if we found the current target
        for dev in devices:
            if dev.get("name") == self.current_target_name:
                self.device_card.set_device_info(
                    self.current_target_name, dev.get("address"))
                break

    # ─── Demo Mode ─────────────────────────────────────────────────
    def toggle_demo_mode(self):
        if self.demo_runner and self.demo_runner.isRunning():
            self.stop_demo_mode()
        else:
            self.start_demo_mode()

    def start_demo_mode(self):
        self.btn_demo.setText("■ Stop Demo")
        self.btn_demo.setStyleSheet("""
            background-color: rgba(248, 81, 73, 0.15);
            color: #f85149;
            border: 1px solid rgba(248, 81, 73, 0.4);
            border-radius: 6px;
            padding: 6px 14px;
            font-weight: bold;
        """)
        self.lbl_mode.setText("DEMO")
        self.lbl_mode.setStyleSheet("""
            color: #d29922;
            background-color: rgba(210,153,34,0.12);
            border: 1px solid rgba(210,153,34,0.3);
            border-radius: 4px;
            padding: 2px 8px;
            font-weight: bold;
        """)
        self.lbl_live.setStyleSheet("color: #d29922;")

        if self.demo_runner:
            self.demo_runner.stop()
        self.demo_runner = DemoModeRunner(self.root_dir)
        self.demo_runner.start()

    def stop_demo_mode(self):
        self.btn_demo.setText("▶ Demo")
        self.btn_demo.setObjectName("demoBtn")
        self.btn_demo.setStyleSheet("")
        self.lbl_mode.setText("LIVE")
        self.lbl_mode.setStyleSheet("""
            color: #3fb950;
            background-color: rgba(63,185,80,0.12);
            border: 1px solid rgba(63,185,80,0.3);
            border-radius: 4px;
            padding: 2px 8px;
            font-weight: bold;
        """)
        self.lbl_live.setStyleSheet("color: #3fb950;")
        if self.demo_runner:
            self.demo_runner.stop()
            self.demo_runner = None

    def stop_system(self):
        if self.demo_runner:
            self.demo_runner.stop()
        if self.log_reader:
            self.log_reader.stop()
        print("\n[DASHBOARD] Stop button pressed. Initiating graceful shutdown...")
        QApplication.quit()

    def closeEvent(self, event):
        if self.demo_runner:
            self.demo_runner.stop()
        if self.log_reader:
            self.log_reader.stop()
        event.accept()

    # ─── Live Signal Handlers ──────────────────────────────────────
    @pyqtSlot(float, float, float)
    def on_rssi_updated(self, raw, filtered, timestamp):
        self.rssi_graph.add_point(raw, filtered, timestamp)
        self._last_filtered_rssi = filtered
        self.device_card.update_rssi(filtered)

    @pyqtSlot(str, float, float)
    def on_spatial_changed(self, state, confidence, timestamp):
        self.status_panel.update_state(state, confidence)

    @pyqtSlot(str, float, float)
    def on_gesture_detected(self, gesture, confidence, timestamp):
        self.status_panel.update_gesture(gesture, confidence)
        self.session_stats.increment_gesture(gesture)

    @pyqtSlot(str, str, str, float)
    def on_action_executed(self, action, result, details, timestamp):
        self.status_panel.update_action(action, result, details)

    @pyqtSlot(str, str, float)
    def on_context_changed(self, context, reason, timestamp):
        self.status_panel.update_context(context)

    @pyqtSlot(dict)
    def on_session_updated(self, summary_dict):
        durations = summary_dict.get("context_durations", {})
        total_dur = summary_dict.get("total_duration", 0.0)
        self.session_stats.update_context_time(durations, total_dur)

        gest_counts = summary_dict.get("gesture_counts", {})
        self.session_stats.set_gesture_counts(
            gest_counts.get("ROTATION", 0),
            gest_counts.get("SLOW_DEPARTURE", 0),
            gest_counts.get("DOUBLE_APPROACH", 0)
        )

        actions = summary_dict.get("total_actions", 0)
        blocks = summary_dict.get("total_safety_blocks", 0)
        self.session_stats.update_system_counts(actions, blocks)

        vol = summary_dict.get("current_volume", 50)
        self.session_stats.update_volume(vol)
