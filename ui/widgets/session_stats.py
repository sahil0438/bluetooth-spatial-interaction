import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QFrame, QGridLayout, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont


class _StatsCard(QFrame):
    """Compact stats card with dark glass styling."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statsCard")
        self.setStyleSheet("""
            QFrame#statsCard {
                background-color: rgba(22, 27, 34, 220);
                border: 1px solid rgba(48, 54, 61, 180);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)


def _make_ctx_bar(color):
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(0)
    bar.setTextVisible(False)
    bar.setFixedHeight(6)
    bar.setStyleSheet(f"""
        QProgressBar {{
            background-color: rgba(13, 17, 23, 200);
            border: 1px solid #21262d;
            border-radius: 3px;
        }}
        QProgressBar::chunk {{
            background-color: {color};
            border-radius: 3px;
        }}
    """)
    return bar


class SessionStats(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.gesture_counts = {"ROTATION": 0, "SLOW_DEPARTURE": 0, "DOUBLE_APPROACH": 0}
        self.actions_count = 0
        self.blocks_count = 0
        self.current_volume = 50
        self.nearby_device_count = 0

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 6, 8, 8)
        main_layout.setSpacing(8)

        self.setStyleSheet("""
            QLabel { color: #e6edf3; font-family: 'Segoe UI', Arial, sans-serif; }
        """)

        # ── 1. CONTEXT TIME DISTRIBUTION ──────────────────────────
        ctx_card = _StatsCard()
        ctx_layout = QVBoxLayout(ctx_card)
        ctx_layout.setContentsMargins(14, 10, 14, 10)
        ctx_layout.setSpacing(6)

        hdr = QLabel("SESSION CONTEXT DISTRIBUTION")
        hdr.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        hdr.setStyleSheet("color: #8b949e; letter-spacing: 1.5px;")
        ctx_layout.addWidget(hdr)

        self.ctx_rows = {}
        contexts = [
            ("WORK_MODE",         "#58a6ff", "💼"),
            ("AWAY_MODE",         "#8b949e", "🚶"),
            ("FOCUS_MODE",        "#3fb950", "🎯"),
            ("PRESENTATION_MODE", "#bc8cff", "📊"),
        ]

        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setColumnMinimumWidth(0, 24)   # icon
        grid.setColumnMinimumWidth(1, 110)  # name
        grid.setColumnStretch(2, 1)         # bar
        grid.setColumnMinimumWidth(3, 55)   # time

        for idx, (ctx_name, color, icon) in enumerate(contexts):
            lbl_icon = QLabel(icon)
            lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

            lbl_name = QLabel(ctx_name.replace("_", " ").title())
            lbl_name.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            lbl_name.setStyleSheet(f"color: {color};")

            bar = _make_ctx_bar(color)

            lbl_time = QLabel("00:00")
            lbl_time.setFont(QFont("Consolas", 9))
            lbl_time.setStyleSheet("color: #8b949e;")
            lbl_time.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            grid.addWidget(lbl_icon, idx, 0)
            grid.addWidget(lbl_name, idx, 1)
            grid.addWidget(bar, idx, 2)
            grid.addWidget(lbl_time, idx, 3)

            self.ctx_rows[ctx_name] = {"bar": bar, "time_lbl": lbl_time}

        ctx_layout.addLayout(grid)
        main_layout.addWidget(ctx_card)

        # ── 2. BOTTOM ROW: Gestures + System Info ──────────────────
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        # --- Gesture counters ---
        gest_card = _StatsCard()
        gest_layout = QVBoxLayout(gest_card)
        gest_layout.setContentsMargins(14, 8, 14, 8)
        gest_layout.setSpacing(4)

        gest_hdr = QLabel("GESTURES")
        gest_hdr.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        gest_hdr.setStyleSheet("color: #8b949e; letter-spacing: 1.5px;")
        gest_layout.addWidget(gest_hdr)

        gest_nums_row = QHBoxLayout()
        gest_nums_row.setSpacing(12)

        self.gest_labels = {}
        gest_defs = [
            ("ROTATION",         "↻",  "#d29922"),
            ("SLOW_DEPARTURE",   "↗",  "#f85149"),
            ("DOUBLE_APPROACH",  "⇊",  "#3fb950"),
        ]

        for gest_key, icon, color in gest_defs:
            cell = QVBoxLayout()
            cell.setSpacing(0)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)

            lbl_icon = QLabel(icon)
            lbl_icon.setFont(QFont("Segoe UI", 14))
            lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_icon.setStyleSheet(f"color: {color};")

            lbl_val = QLabel("0")
            lbl_val.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
            lbl_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_val.setStyleSheet(f"color: {color};")

            lbl_name = QLabel(gest_key.replace("_", " ").title())
            lbl_name.setFont(QFont("Segoe UI", 7))
            lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_name.setStyleSheet("color: #8b949e;")

            cell.addWidget(lbl_icon)
            cell.addWidget(lbl_val)
            cell.addWidget(lbl_name)
            gest_nums_row.addLayout(cell)

            self.gest_labels[gest_key] = lbl_val

        gest_layout.addLayout(gest_nums_row)
        bottom_row.addWidget(gest_card, 2)

        # --- System info card ---
        sys_card = _StatsCard()
        sys_layout = QVBoxLayout(sys_card)
        sys_layout.setContentsMargins(14, 8, 14, 8)
        sys_layout.setSpacing(6)

        sys_hdr = QLabel("SYSTEM")
        sys_hdr.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        sys_hdr.setStyleSheet("color: #8b949e; letter-spacing: 1.5px;")
        sys_layout.addWidget(sys_hdr)

        # Stats grid
        sys_grid = QGridLayout()
        sys_grid.setSpacing(4)

        # Actions
        lbl_act_title = QLabel("Actions")
        lbl_act_title.setFont(QFont("Segoe UI", 8))
        lbl_act_title.setStyleSheet("color: #8b949e;")
        self.lbl_actions = QLabel("0")
        self.lbl_actions.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
        self.lbl_actions.setStyleSheet("color: #3fb950;")
        sys_grid.addWidget(lbl_act_title, 0, 0)
        sys_grid.addWidget(self.lbl_actions, 1, 0)

        # Blocks
        lbl_blk_title = QLabel("Blocks")
        lbl_blk_title.setFont(QFont("Segoe UI", 8))
        lbl_blk_title.setStyleSheet("color: #8b949e;")
        self.lbl_blocks = QLabel("0")
        self.lbl_blocks.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
        self.lbl_blocks.setStyleSheet("color: #f85149;")
        sys_grid.addWidget(lbl_blk_title, 0, 1)
        sys_grid.addWidget(self.lbl_blocks, 1, 1)

        # Nearby Devices
        lbl_dev_title = QLabel("Nearby")
        lbl_dev_title.setFont(QFont("Segoe UI", 8))
        lbl_dev_title.setStyleSheet("color: #8b949e;")
        self.lbl_devices = QLabel("0")
        self.lbl_devices.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
        self.lbl_devices.setStyleSheet("color: #58a6ff;")
        sys_grid.addWidget(lbl_dev_title, 0, 2)
        sys_grid.addWidget(self.lbl_devices, 1, 2)

        sys_layout.addLayout(sys_grid)

        # Volume bar
        vol_row = QHBoxLayout()
        vol_row.setSpacing(6)
        vol_lbl = QLabel("Vol")
        vol_lbl.setFont(QFont("Segoe UI", 8))
        vol_lbl.setStyleSheet("color: #8b949e;")
        self.vol_bar = QProgressBar()
        self.vol_bar.setRange(0, 100)
        self.vol_bar.setValue(50)
        self.vol_bar.setTextVisible(False)
        self.vol_bar.setFixedHeight(6)
        self.vol_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(13, 17, 23, 200);
                border: 1px solid #21262d;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #58a6ff;
                border-radius: 3px;
            }
        """)
        self.vol_pct = QLabel("50%")
        self.vol_pct.setFont(QFont("Consolas", 8))
        self.vol_pct.setStyleSheet("color: #8b949e;")
        vol_row.addWidget(vol_lbl)
        vol_row.addWidget(self.vol_bar, 1)
        vol_row.addWidget(self.vol_pct)
        sys_layout.addLayout(vol_row)

        # Model accuracy
        lbl_model = QLabel("RF Model: 99.17% accuracy")
        lbl_model.setFont(QFont("Segoe UI", 7))
        lbl_model.setStyleSheet("color: #484f58; font-style: italic;")
        sys_layout.addWidget(lbl_model)

        bottom_row.addWidget(sys_card, 3)
        main_layout.addLayout(bottom_row)

    # ── Public API ─────────────────────────────────────────────────

    def increment_gesture(self, gesture):
        if gesture in self.gesture_counts:
            self.gesture_counts[gesture] += 1
            lbl = self.gest_labels[gesture]
            lbl.setText(str(self.gesture_counts[gesture]))

            # Flash highlight
            original = lbl.styleSheet()
            lbl.setStyleSheet("color: #ffffff;")
            QTimer.singleShot(400, lambda: lbl.setStyleSheet(original))

    def set_gesture_counts(self, rotation, departure, approach):
        self.gesture_counts["ROTATION"] = rotation
        self.gesture_counts["SLOW_DEPARTURE"] = departure
        self.gesture_counts["DOUBLE_APPROACH"] = approach

        self.gest_labels["ROTATION"].setText(str(rotation))
        self.gest_labels["SLOW_DEPARTURE"].setText(str(departure))
        self.gest_labels["DOUBLE_APPROACH"].setText(str(approach))

    def update_volume(self, volume):
        self.current_volume = volume
        self.vol_bar.setValue(int(volume))
        self.vol_pct.setText(f"{int(volume)}%")

    def update_system_counts(self, actions, blocks):
        self.actions_count = actions
        self.blocks_count = blocks
        self.lbl_actions.setText(str(actions))
        self.lbl_blocks.setText(str(blocks))

    def update_nearby_count(self, count):
        self.nearby_device_count = count
        self.lbl_devices.setText(str(count))

    def update_context_time(self, context_times, total_time):
        if total_time <= 0:
            return

        for ctx_name, row in self.ctx_rows.items():
            duration = context_times.get(ctx_name, 0.0)
            pct = int((duration / total_time) * 100)
            row["bar"].setValue(pct)

            # Format to MM:SS or HH:MM:SS
            sec = int(duration)
            hrs = sec // 3600
            mins = (sec % 3600) // 60
            secs = sec % 60
            if hrs > 0:
                row["time_lbl"].setText(f"{hrs}:{mins:02d}:{secs:02d}")
            else:
                row["time_lbl"].setText(f"{mins:02d}:{secs:02d}")
