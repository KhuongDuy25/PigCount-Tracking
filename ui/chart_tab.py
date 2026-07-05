# -*- coding: utf-8 -*-
"""
chart_tab.py — Tab CHART
Hiển thị biểu đồ nhiệt độ / độ ẩm theo thời gian (dữ liệu demo).
Mục "Bản đồ nhiệt / đường đi di chuyển của lợn" được để RIÊNG như một khu
vực placeholder, sẽ nâng cấp sau (theo yêu cầu của người dùng) khi có dữ
liệu tọa độ thực tế từ hệ thống camera + AI theo dõi (tracking).
"""

import random
from collections import deque

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class ChartTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.temp_history = deque(maxlen=60)
        self.humi_history = deque(maxlen=60)
        self._build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_chart)
        self.timer.start(2000)

    def _build_ui(self):
        root = QHBoxLayout(self)

        # -------- biểu đồ nhiệt độ / độ ẩm theo thời gian --------
        gb_chart = QGroupBox("Biểu đồ Nhiệt độ / Độ ẩm theo thời gian")
        cl = QVBoxLayout(gb_chart)
        self.figure = Figure(figsize=(5, 4))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        cl.addWidget(self.canvas)
        root.addWidget(gb_chart, 2)

        # -------- placeholder: bản đồ nhiệt / đường đi lợn (nâng cấp sau) --------
        gb_heat = QGroupBox("Bản đồ nhiệt & đường đi di chuyển của lợn (sẽ nâng cấp sau)")
        hl = QVBoxLayout(gb_heat)
        note = QLabel(
            "🚧 Tính năng đang chờ nâng cấp.\n\n"
            "Khi hệ thống camera + AI theo dõi (tracking theo ID màu lưng ở tab HOME)\n"
            "thu thập đủ dữ liệu tọa độ di chuyển, khu vực này sẽ hiển thị:\n"
            "  • Heatmap khu vực lợn hay tập trung (máng ăn, máng nước, khu nằm...)\n"
            "  • Đường đi (trajectory) của từng ID lợn theo thời gian thực\n"
            "  • So sánh mức độ hoạt động giữa các cá thể\n\n"
            "Hiện tại đây chỉ là khung giao diện (placeholder)."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "background:white; border:1px dashed #b9b28e; border-radius:6px; padding:14px;"
        )
        hl.addWidget(note)
        root.addWidget(gb_heat, 1)

    def _update_chart(self):
        # Dữ liệu demo (thay bằng dữ liệu thật khi tích hợp cảm biến/PLC)
        last_temp = self.temp_history[-1] if self.temp_history else 30.0
        last_humi = self.humi_history[-1] if self.humi_history else 60.0
        self.temp_history.append(last_temp + random.uniform(-0.3, 0.3))
        self.humi_history.append(last_humi + random.uniform(-0.5, 0.5))

        self.ax.clear()
        self.ax.plot(list(self.temp_history), label="Nhiệt độ (°C)", color="#d13c3c")
        self.ax.plot(list(self.humi_history), label="Độ ẩm (%)", color="#1857a4")
        self.ax.legend(loc="upper right", fontsize=8)
        self.ax.set_ylim(0, 100)
        self.ax.set_xlabel("Thời gian (mẫu gần nhất)")
        self.figure.tight_layout()
        self.canvas.draw()
