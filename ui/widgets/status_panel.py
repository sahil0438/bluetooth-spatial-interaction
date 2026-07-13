import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, pyqtProperty
from PyQt6.QtGui import QColor, QFont


# ─── Reusable glassmorphism card ────────────────────────────────────────────
class GlassCard(QFrame):
    """A dark glass-style card with subtle glow border."""
    def __init__(self, accent_color="#58a6ff", parent=None):
        super().__init__(parent)
        self.setObjectName("glassCard")
        self._accent = accent_color
        self.setStyleSheet(f"""
            QFrame#glassCard {{
                background-color: rgba(22, 27, 34, 220);
                border: 1px solid rgba(48, 54, 61, 180);
                border-radius: 10px;
                padding: 12px;
            }}
        """)
        # Subtle glow shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(accent_color))
        self.setGraphicsEffect(shadow)


def _make_progress_bar(color="#58a6ff", height=8):
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(0)
    bar.setTextVisible(False)
    bar.setFixedHeight(height)
    bar.setStyleSheet(f"""
        QProgressBar {{
            background-color: rgba(13, 17, 23, 200);
            border: 1px solid #21262d;
            border-radius: {height // 2}px;
        }}
        QProgressBar::chunk {{
            background-color: {color};
            border-radius: {height // 2}px;
        }}
    """)
    return bar


class StatusPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.init_ui()

        # Keep track of timestamps for relative time calculations
        self.state_time = time.time()
        self.gesture_time = None
        self.action_time = None
        self.context_start_time = time.time()

        # Periodic timer to update relative time labels
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_relative_times)
        self.timer.start(500)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.setStyleSheet("""
            QLabel { color: #e6edf3; font-family: 'Segoe UI', Arial, sans-serif; }
        """)

        # ── 1. SPATIAL STATE CARD ──────────────────────────────────
        spatial_card = GlassCard("#3fb950")
        spatial_card.setMinimumHeight(105)
        spatial_layout = QVBoxLayout(spatial_card)
        spatial_layout.setContentsMargins(14, 10, 14, 10)
        spatial_layout.setSpacing(6)

        hdr1 = QLabel("SPATIAL STATE")
        hdr1.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        hdr1.setStyleSheet("color: #8b949e; letter-spacing: 1.5px;")
        spatial_layout.addWidget(hdr1)

        state_row = QHBoxLayout()
        self.state_icon_label = QLabel("○")
        self.state_icon_label.setStyleSheet("font-size: 22px; color: #f85149;")
        self.state_label = QLabel("ABSENT")
        self.state_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.state_label.setStyleSheet("color: #f85149;")
        state_row.addWidget(self.state_icon_label)
        state_row.addSpacing(6)
        state_row.addWidget(self.state_label)
        state_row.addStretch()

        self.state_time_label = QLabel("0s")
        self.state_time_label.setFont(QFont("Consolas", 10))
        self.state_time_label.setStyleSheet("color: #8b949e;")
        state_row.addWidget(self.state_time_label)
        spatial_layout.addLayout(state_row)

        # Confidence bar
        conf_row = QHBoxLayout()
        conf_lbl = QLabel("Confidence")
        conf_lbl.setFont(QFont("Segoe UI", 8))
        conf_lbl.setStyleSheet("color: #8b949e;")
        self.state_conf = _make_progress_bar("#3fb950", 6)
        self.state_conf_pct = QLabel("0%")
        self.state_conf_pct.setFont(QFont("Consolas", 8))
        self.state_conf_pct.setStyleSheet("color: #8b949e;")
        self.state_conf_pct.setFixedWidth(35)
        self.state_conf_pct.setAlignment(Qt.AlignmentFlag.AlignRight)
        conf_row.addWidget(conf_lbl)
        conf_row.addSpacing(6)
        conf_row.addWidget(self.state_conf, 1)
        conf_row.addWidget(self.state_conf_pct)
        spatial_layout.addLayout(conf_row)

        layout.addWidget(spatial_card)

        # ── 2. CONTEXT CARD ────────────────────────────────────────
        context_card = GlassCard("#58a6ff")
        context_card.setMinimumHeight(85)
        context_layout = QVBoxLayout(context_card)
        context_layout.setContentsMargins(14, 10, 14, 10)
        context_layout.setSpacing(6)

        hdr2 = QLabel("CONTEXT ENGINE")
        hdr2.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        hdr2.setStyleSheet("color: #8b949e; letter-spacing: 1.5px;")
        context_layout.addWidget(hdr2)

        ctx_row = QHBoxLayout()
        self.context_badge = QLabel("WORK_MODE")
        self.context_badge.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.context_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.context_badge.setFixedHeight(32)
        self._update_context_badge_style("WORK_MODE")

        self.context_time_active = QLabel("00:00:00")
        self.context_time_active.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
        self.context_time_active.setStyleSheet("color: #58a6ff;")

        ctx_row.addWidget(self.context_badge)
        ctx_row.addStretch()
        ctx_row.addWidget(self.context_time_active)
        context_layout.addLayout(ctx_row)
        layout.addWidget(context_card)

        # ── 3. LAST GESTURE CARD ────────────────────────────────────
        gesture_card = GlassCard("#d29922")
        gesture_card.setMinimumHeight(105)
        gest_layout = QVBoxLayout(gesture_card)
        gest_layout.setContentsMargins(14, 10, 14, 10)
        gest_layout.setSpacing(6)

        hdr3 = QLabel("LAST GESTURE")
        hdr3.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        hdr3.setStyleSheet("color: #8b949e; letter-spacing: 1.5px;")
        gest_layout.addWidget(hdr3)

        gest_row = QHBoxLayout()
        self.gesture_label = QLabel("—")
        self.gesture_label.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self.gesture_label.setStyleSheet("color: #d29922;")

        self.gesture_time_label = QLabel("")
        self.gesture_time_label.setFont(QFont("Consolas", 9))
        self.gesture_time_label.setStyleSheet("color: #8b949e;")

        gest_row.addWidget(self.gesture_label)
        gest_row.addStretch()
        gest_row.addWidget(self.gesture_time_label)
        gest_layout.addLayout(gest_row)

        # Confidence bar
        gest_conf_row = QHBoxLayout()
        gest_conf_lbl = QLabel("Confidence")
        gest_conf_lbl.setFont(QFont("Segoe UI", 8))
        gest_conf_lbl.setStyleSheet("color: #8b949e;")
        self.gesture_conf = _make_progress_bar("#d29922", 6)
        self.gesture_conf_pct = QLabel("")
        self.gesture_conf_pct.setFont(QFont("Consolas", 8))
        self.gesture_conf_pct.setStyleSheet("color: #8b949e;")
        self.gesture_conf_pct.setFixedWidth(35)
        self.gesture_conf_pct.setAlignment(Qt.AlignmentFlag.AlignRight)
        gest_conf_row.addWidget(gest_conf_lbl)
        gest_conf_row.addSpacing(6)
        gest_conf_row.addWidget(self.gesture_conf, 1)
        gest_conf_row.addWidget(self.gesture_conf_pct)
        gest_layout.addLayout(gest_conf_row)
        layout.addWidget(gesture_card)

        # ── 4. LAST ACTION CARD ────────────────────────────────────
        action_card = GlassCard("#bc8cff")
        action_card.setMinimumHeight(125)
        act_layout = QVBoxLayout(action_card)
        act_layout.setContentsMargins(14, 10, 14, 10)
        act_layout.setSpacing(6)

        hdr4 = QLabel("LAST ACTION")
        hdr4.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        hdr4.setStyleSheet("color: #8b949e; letter-spacing: 1.5px;")
        act_layout.addWidget(hdr4)

        act_row = QHBoxLayout()
        self.action_label = QLabel("—")
        self.action_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.action_label.setStyleSheet("color: #bc8cff;")

        self.action_result_badge = QLabel("")
        self.action_result_badge.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.action_result_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.action_time_label = QLabel("")
        self.action_time_label.setFont(QFont("Consolas", 9))
        self.action_time_label.setStyleSheet("color: #8b949e;")

        act_row.addWidget(self.action_label)
        act_row.addSpacing(6)
        act_row.addWidget(self.action_result_badge)
        act_row.addStretch()
        act_row.addWidget(self.action_time_label)
        act_layout.addLayout(act_row)

        self.action_details = QLabel("No actions executed yet.")
        self.action_details.setFont(QFont("Segoe UI", 9))
        self.action_details.setStyleSheet("color: #8b949e;")
        self.action_details.setWordWrap(True)
        act_layout.addWidget(self.action_details)
        layout.addWidget(action_card)

        layout.addStretch()

    # ── Public update methods ──────────────────────────────────────

    def update_state(self, state, confidence):
        self.state_label.setText(state)
        pct = int(confidence * 100) if confidence <= 1.0 else int(confidence)
        self.state_conf.setValue(pct)
        self.state_conf_pct.setText(f"{pct}%")
        self.state_time = time.time()

        # Color-coded state icons & labels
        state_styles = {
            "APPROACHING":    ("→→", "#3fb950"),
            "DEPARTING":      ("←←", "#d29922"),
            "PRESENT_STABLE": ("●",  "#3fb950"),
            "RAPID_APPROACH": ("⚡", "#d29922"),
            "ABSENT":         ("○",  "#f85149"),
        }
        icon, color = state_styles.get(state, ("○", "#f85149"))
        self.state_icon_label.setText(icon)
        self.state_icon_label.setStyleSheet(f"font-size: 22px; color: {color};")
        self.state_label.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: bold;")

        # Update confidence bar color
        self.state_conf.setStyleSheet(f"""
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

    def update_context(self, context):
        self.context_badge.setText(context)
        self._update_context_badge_style(context)
        self.context_start_time = time.time()

    def _update_context_badge_style(self, context):
        styles = {
            "WORK_MODE":         ("rgba(88,166,255,0.15)", "#58a6ff", "#58a6ff"),
            "AWAY_MODE":         ("rgba(139,148,158,0.15)", "#8b949e", "#8b949e"),
            "PRESENTATION_MODE": ("rgba(188,140,255,0.15)", "#bc8cff", "#bc8cff"),
            "FOCUS_MODE":        ("rgba(63,185,80,0.15)",  "#3fb950", "#3fb950"),
        }
        bg, fg, border = styles.get(context, ("rgba(139,148,158,0.15)", "#8b949e", "#8b949e"))
        self.context_badge.setStyleSheet(f"""
            background-color: {bg};
            color: {fg};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 4px 14px;
            font-weight: bold;
        """)

    def update_gesture(self, gesture, confidence):
        icons = {
            "ROTATION": "↻ ROTATION",
            "SLOW_DEPARTURE": "↗ SLOW DEPARTURE",
            "DOUBLE_APPROACH": "⇊ DOUBLE APPROACH",
        }
        display_name = icons.get(gesture, gesture)
        self.gesture_label.setText(display_name)
        pct = int(confidence * 100) if confidence <= 1.0 else int(confidence)
        self.gesture_conf.setValue(pct)
        self.gesture_conf_pct.setText(f"{pct}%")
        self.gesture_time = time.time()

        # Flash effect
        self.gesture_label.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: bold;")
        QTimer.singleShot(400, lambda: self.gesture_label.setStyleSheet(
            "color: #d29922; font-size: 15px; font-weight: bold;"))

    def update_action(self, action, result, details):
        self.action_label.setText(action)
        self.action_time = time.time()
        self.action_details.setText(details)

        if result.upper() == "SUCCESS" or result == "✓":
            self.action_result_badge.setText("✓ SUCCESS")
            self.action_result_badge.setStyleSheet("""
                background-color: rgba(63,185,80,0.15);
                color: #3fb950; border: 1px solid #3fb950;
                border-radius: 4px; padding: 2px 8px;
            """)
        else:
            self.action_result_badge.setText("✗ BLOCKED")
            self.action_result_badge.setStyleSheet("""
                background-color: rgba(248,81,73,0.15);
                color: #f85149; border: 1px solid #f85149;
                border-radius: 4px; padding: 2px 8px;
            """)

    def update_relative_times(self):
        now = time.time()

        # State relative time
        diff_state = int(now - self.state_time)
        if diff_state < 60:
            self.state_time_label.setText(f"{diff_state}s")
        else:
            self.state_time_label.setText(f"{diff_state // 60}m {diff_state % 60}s")

        # Context active time
        diff_ctx = int(now - self.context_start_time)
        hrs = diff_ctx // 3600
        mins = (diff_ctx % 3600) // 60
        secs = diff_ctx % 60
        self.context_time_active.setText(f"{hrs:02d}:{mins:02d}:{secs:02d}")

        # Gesture relative time
        if self.gesture_time:
            diff_gest = int(now - self.gesture_time)
            self.gesture_time_label.setText(f"{diff_gest}s ago")
        else:
            self.gesture_time_label.setText("")

        # Action relative time
        if self.action_time:
            diff_act = int(now - self.action_time)
            self.action_time_label.setText(f"{diff_act}s ago")
        else:
            self.action_time_label.setText("")
