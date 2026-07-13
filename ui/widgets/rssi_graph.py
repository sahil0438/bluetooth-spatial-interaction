import sys
import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QLinearGradient, 
    QRadialGradient, QPainterPath, QBrush
)
from PyQt6.QtCore import Qt, QPointF, QRectF


class RSSIGraph(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []  # List of dicts: {"raw": float, "filtered": float, "time": float}
        self.max_points = 120  # 60 seconds at 2Hz (500ms interval)
        self.current_rssi = -127
        self.is_absent = True
        self.is_close = False

        # Premium color palette
        self.bg_color = QColor("#0d1117")
        self.card_bg = QColor("#161b22")
        self.raw_color = QColor(120, 130, 150, 100)
        self.grid_color = QColor("#21262d")
        self.text_color = QColor("#8b949e")
        self.accent_cyan = QColor("#58a6ff")
        self.accent_purple = QColor("#bc8cff")
        self.accent_green = QColor("#3fb950")
        self.accent_orange = QColor("#d29922")
        self.accent_red = QColor("#f85149")
        self.border_color = QColor("#30363d")

        # Set minimum size
        self.setMinimumSize(400, 250)

    def add_point(self, raw, filtered, timestamp):
        self.points.append({"raw": raw, "filtered": filtered, "time": timestamp})
        if len(self.points) > self.max_points:
            self.points.pop(0)

        self.current_rssi = filtered
        self.is_absent = (filtered <= -115)
        self.is_close = (filtered >= -45)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # 1. Draw card background with rounded corners
        card_rect = QRectF(4, 4, width - 8, height - 8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.card_bg))
        painter.drawRoundedRect(card_rect, 12, 12)

        # Subtle border
        painter.setPen(QPen(self.border_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(card_rect, 12, 12)

        # Status-dependent top accent line (gradient)
        accent_rect = QRectF(4, 4, width - 8, 3)
        if self.is_absent:
            accent_grad = QLinearGradient(0, 0, width, 0)
            accent_grad.setColorAt(0, QColor("#f85149"))
            accent_grad.setColorAt(1, QColor("#da3633"))
        elif self.is_close:
            accent_grad = QLinearGradient(0, 0, width, 0)
            accent_grad.setColorAt(0, QColor("#3fb950"))
            accent_grad.setColorAt(1, QColor("#238636"))
        else:
            accent_grad = QLinearGradient(0, 0, width, 0)
            accent_grad.setColorAt(0, QColor("#58a6ff"))
            accent_grad.setColorAt(1, QColor("#bc8cff"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(accent_grad))
        painter.drawRoundedRect(accent_rect, 2, 2)

        # Margins for axis labels
        left_margin = 55
        right_margin = 20
        top_margin = 50
        bottom_margin = 35

        graph_width = width - left_margin - right_margin
        graph_height = height - top_margin - bottom_margin

        if graph_width <= 0 or graph_height <= 0:
            painter.end()
            return

        # RSSI range: -127 to -30
        min_y_val = -127.0
        max_y_val = -30.0
        val_range = max_y_val - min_y_val

        def to_y(val):
            val = max(min_y_val, min(max_y_val, val))
            pct = (val - min_y_val) / val_range
            return top_margin + graph_height - (pct * graph_height)

        # 2. Draw horizontal grid lines (subtle)
        grid_pen = QPen(self.grid_color, 1, Qt.PenStyle.DotLine)
        painter.setFont(QFont("Consolas", 8))
        for val in range(-120, -20, 20):
            y = to_y(val)
            painter.setPen(grid_pen)
            painter.drawLine(int(left_margin), int(y), int(left_margin + graph_width), int(y))
            painter.setPen(QPen(self.text_color, 1))
            painter.drawText(8, int(y) + 4, f"{val}")

        # 3. Draw threshold zones (colored bands)
        zones = [
            (-30, -45, QColor(59, 185, 80, 15), "CLOSE", self.accent_green),
            (-45, -70, QColor(88, 166, 255, 10), "MEDIUM", self.accent_cyan),
            (-70, -100, QColor(210, 153, 34, 10), "FAR", self.accent_orange),
            (-100, -127, QColor(248, 81, 73, 8), "ABSENT", self.accent_red),
        ]
        for top_val, bot_val, fill_color, label, label_color in zones:
            y_top = to_y(top_val)
            y_bot = to_y(bot_val)
            zone_rect = QRectF(left_margin, y_top, graph_width, y_bot - y_top)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(fill_color))
            painter.drawRect(zone_rect)

        # 4. Draw data lines
        if len(self.points) > 1:
            step = graph_width / (self.max_points - 1)
            offset = self.max_points - len(self.points)

            # Build paths
            raw_points = []
            filt_points = []
            for idx, pt in enumerate(self.points):
                x = left_margin + (idx + offset) * step
                raw_points.append(QPointF(x, to_y(pt["raw"])))
                filt_points.append(QPointF(x, to_y(pt["filtered"])))

            # Draw raw RSSI (thin dotted line)
            raw_pen = QPen(self.raw_color, 1.0, Qt.PenStyle.DotLine)
            painter.setPen(raw_pen)
            for i in range(len(raw_points) - 1):
                painter.drawLine(raw_points[i], raw_points[i + 1])

            # Build gradient fill path under filtered line
            fill_path = QPainterPath()
            fill_path.moveTo(QPointF(filt_points[0].x(), top_margin + graph_height))
            for pt in filt_points:
                fill_path.lineTo(pt)
            fill_path.lineTo(QPointF(filt_points[-1].x(), top_margin + graph_height))
            fill_path.closeSubpath()

            # Gradient fill — cyan at top fading to transparent
            fill_grad = QLinearGradient(0, top_margin, 0, top_margin + graph_height)
            fill_grad.setColorAt(0, QColor(88, 166, 255, 60))
            fill_grad.setColorAt(0.5, QColor(88, 166, 255, 20))
            fill_grad.setColorAt(1, QColor(88, 166, 255, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(fill_grad))
            painter.drawPath(fill_path)

            # Draw filtered RSSI line (solid gradient from cyan to purple)
            for i in range(len(filt_points) - 1):
                progress = i / max(len(filt_points) - 1, 1)
                r = int(88 + (188 - 88) * progress)
                g = int(166 + (140 - 166) * progress)
                b = int(255 + (255 - 255) * progress)
                line_color = QColor(r, g, b)
                painter.setPen(QPen(line_color, 2.5, Qt.PenStyle.SolidLine))
                painter.drawLine(filt_points[i], filt_points[i + 1])

            # Glow dot on the latest data point
            last_pt = filt_points[-1]
            # Outer glow
            glow_grad = QRadialGradient(last_pt, 12)
            glow_color = self.accent_green if self.is_close else (
                self.accent_red if self.is_absent else self.accent_cyan
            )
            glow_grad.setColorAt(0, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 120))
            glow_grad.setColorAt(1, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(glow_grad))
            painter.drawEllipse(last_pt, 12, 12)
            # Solid center dot
            painter.setBrush(QBrush(glow_color))
            painter.drawEllipse(last_pt, 4, 4)

        # 5. Axes
        painter.setPen(QPen(self.border_color, 1.5))
        painter.drawLine(left_margin, top_margin, left_margin, int(top_margin + graph_height))
        painter.drawLine(left_margin, int(top_margin + graph_height),
                         int(left_margin + graph_width), int(top_margin + graph_height))

        # X Axis time labels
        painter.setPen(QPen(self.text_color, 1))
        painter.setFont(QFont("Consolas", 7))
        for sec in range(0, 61, 15):
            x = left_margin + graph_width - (sec * (graph_width / 60))
            if x >= left_margin:
                painter.drawLine(int(x), int(top_margin + graph_height),
                                 int(x), int(top_margin + graph_height + 4))
                lbl = "now" if sec == 0 else f"-{sec}s"
                painter.drawText(int(x) - 12, int(top_margin + graph_height + 18), lbl)

        # 6. Title and current RSSI overlay
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.setPen(QPen(self.text_color, 1))
        painter.drawText(int(left_margin + 5), int(top_margin - 22), "RSSI SIGNAL MONITOR")

        # Legend
        painter.setFont(QFont("Segoe UI", 8))
        legend_x = left_margin + 180
        legend_y = top_margin - 22
        # Raw legend
        painter.setPen(QPen(QColor(120, 130, 150), 1, Qt.PenStyle.DotLine))
        painter.drawLine(int(legend_x), int(legend_y - 3), int(legend_x + 20), int(legend_y - 3))
        painter.setPen(QPen(self.text_color, 1))
        painter.drawText(int(legend_x + 24), int(legend_y), "Raw")
        # Filtered legend
        painter.setPen(QPen(self.accent_cyan, 2))
        painter.drawLine(int(legend_x + 55), int(legend_y - 3), int(legend_x + 75), int(legend_y - 3))
        painter.setPen(QPen(self.text_color, 1))
        painter.drawText(int(legend_x + 79), int(legend_y), "Filtered")

        # Big current RSSI value (top right)
        rssi_str = "ABSENT" if self.is_absent else f"{self.current_rssi:.0f} dBm"
        color_map = self.accent_red if self.is_absent else (
            self.accent_green if self.is_close else self.accent_cyan
        )
        painter.setPen(QPen(color_map, 1))
        painter.setFont(QFont("Consolas", 20, QFont.Weight.Bold))
        # Right-align the text
        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(rssi_str)
        painter.drawText(int(width - right_margin - text_w - 10), int(top_margin - 8), rssi_str)

        painter.end()
