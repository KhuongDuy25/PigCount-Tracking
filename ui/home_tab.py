# -*- coding: utf-8 -*-
"""
home_tab.py — Tab HOME
Giữ nguyên bố cục tổng quan như ảnh gốc (nhiệt độ, độ ẩm, lịch trình tiếp theo,
thống kê, trạng thái hệ thống, tổng quan vận hành) và BỔ SUNG khu vực camera
giám sát máng ăn + vẽ vùng (zone) + nhận diện ID lợn theo màu lưng.
"""

from PyQt5.QtCore import Qt, QTimer, QDateTime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QGroupBox, QFrame
)

from ui.camera_zone import CameraZoneWidget


def value_label(text):
    lbl = QLabel(text)
    lbl.setProperty("role", "value")
    return lbl


class StatusDot(QLabel):
    def __init__(self, on=False):
        super().__init__()
        self.set_on(on)
        self.setFixedSize(22, 22)

    def set_on(self, on):
        color = "#2fae4e" if on else "#9a9a9a"
        self.setStyleSheet(f"background:{color}; border-radius:11px; border:1px solid #555;")


class HomeTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QHBoxLayout(self)

        # ================= CỘT TRÁI: cảm biến + lịch trình =================
        left = QVBoxLayout()
        root.addLayout(left, 2)

        gb_sensor = QGroupBox("Cảm biến môi trường")
        gl = QGridLayout(gb_sensor)
        gl.addWidget(QLabel("🌡️ Nhiệt độ"), 0, 0)
        self.lbl_temp = value_label("31.4")
        gl.addWidget(self.lbl_temp, 0, 1)
        gl.addWidget(QLabel("°C"), 0, 2)

        gl.addWidget(QLabel("💧 Độ ẩm"), 1, 0)
        self.lbl_humi = value_label("59.2")
        gl.addWidget(self.lbl_humi, 1, 1)
        gl.addWidget(QLabel("%"), 1, 2)

        gl.addWidget(QLabel("🌤️ Nhiệt độ ngoài trời"), 2, 0)
        self.lbl_out_temp = value_label("18")
        gl.addWidget(self.lbl_out_temp, 2, 1)
        gl.addWidget(QLabel("°C"), 2, 2)
        left.addWidget(gb_sensor)

        gb_next = QGroupBox("Lịch trình tiếp theo")
        nl = QGridLayout(gb_next)
        nl.addWidget(QLabel("🚿 Tắm"), 0, 0)
        nl.addWidget(value_label("8 : 0"), 0, 1)
        nl.addWidget(QLabel("🧹 Vệ sinh"), 1, 0)
        nl.addWidget(value_label("19 : 0"), 1, 1)
        left.addWidget(gb_next)

        gb_stat = QGroupBox("Thống kê hôm nay")
        sl = QGridLayout(gb_stat)
        sl.addWidget(QLabel("🚿 Lần tắm"), 0, 0)
        sl.addWidget(value_label("2"), 0, 1)
        sl.addWidget(QLabel("🧹 Lần vệ sinh"), 1, 0)
        sl.addWidget(value_label("2"), 1, 1)
        left.addWidget(gb_stat)

        left.addStretch(1)

        # ================= GIỮA: hình trại + camera/zone (MỚI) =================
        mid = QVBoxLayout()
        root.addLayout(mid, 5)

        gb_farm = QGroupBox("Tổng quan trại")
        farm_lay = QVBoxLayout(gb_farm)
        farm_img = QLabel("🏠  TRẠI CHĂN NUÔI THÔNG MINH  🌾")
        farm_img.setAlignment(Qt.AlignCenter)
        farm_img.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #bfe3f7, stop:1 #eaf6cf);"
            "border-radius:8px; padding:20px; font-size:16px; font-weight:700; color:#1857a4;"
        )
        farm_lay.addWidget(farm_img)
        mid.addWidget(gb_farm)

        # ---- KHU VỰC MỚI: camera giám sát máng ăn + vẽ vùng + ID lợn ----
        gb_cam = QGroupBox("Giám sát máng ăn (Camera + Zone + Nhận diện ID theo màu lưng)")
        cam_lay = QVBoxLayout(gb_cam)
        self.camera_widget = CameraZoneWidget()
        cam_lay.addWidget(self.camera_widget)
        mid.addWidget(gb_cam, 1)

        # ================= CỘT PHẢI: trạng thái hệ thống =================
        right = QVBoxLayout()
        root.addLayout(right, 2)

        gb_sys = QGroupBox("Hệ thống")
        sysl = QHBoxLayout(gb_sys)
        self.dot_system = StatusDot(on=True)
        sysl.addWidget(self.dot_system)
        lbl_sys = QLabel("Hệ thống đang chạy")
        sysl.addWidget(lbl_sys)
        sysl.addStretch(1)
        right.addWidget(gb_sys)

        gb_over = QGroupBox("Tổng quan vận hành")
        ol = QGridLayout(gb_over)
        ol.addWidget(QLabel("Chế độ hiện tại"), 0, 0)
        lbl_mode = QLabel("MANUAL")
        lbl_mode.setStyleSheet("color:#2fae4e; font-weight:700;")
        ol.addWidget(lbl_mode, 0, 1)

        ol.addWidget(QLabel("Chu trình"), 1, 0)
        lbl_cycle = QLabel("Chờ lệnh")
        ol.addWidget(lbl_cycle, 1, 1)

        ol.addWidget(QLabel("Trạng thái"), 2, 0)
        lbl_state = QLabel("Bình thường")
        lbl_state.setStyleSheet("color:#2fae4e; font-weight:700;")
        ol.addWidget(lbl_state, 2, 1)
        right.addWidget(gb_over)

        right.addStretch(1)

    # ------------------------------------------------------------------
    def _tick(self):
        # Chỗ này để dành cho việc gắn dữ liệu thật (đọc từ PLC / Blynk / Serial...)
        # Hiện tại chỉ là placeholder không đổi giá trị để không gây hiểu nhầm là dữ liệu thật.
        pass
