# -*- coding: utf-8 -*-
"""
home_tab.py — Tab HOME
Bố cục tổng quan (nhiệt độ, độ ẩm, lịch trình tiếp theo, thống kê, trạng
thái hệ thống, tổng quan vận hành) + khu vực camera giám sát máng ăn, vẽ
vùng (zone) và nhận diện ID theo màu lưng con vật (kết hợp YOLO tracking).
"""

import time
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
        self._last_data_time = None
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
        self.lbl_temp = value_label("--")
        gl.addWidget(self.lbl_temp, 0, 1)
        gl.addWidget(QLabel("°C"), 0, 2)

        gl.addWidget(QLabel("💧 Độ ẩm"), 1, 0)
        self.lbl_humi = value_label("--")
        gl.addWidget(self.lbl_humi, 1, 1)
        gl.addWidget(QLabel("%"), 1, 2)

        gl.addWidget(QLabel("🌾 Cám tồn"), 2, 0)
        self.lbl_cam = value_label("--")
        gl.addWidget(self.lbl_cam, 2, 1)
        gl.addWidget(QLabel("g"), 2, 2)

        gl.addWidget(QLabel("🚰 Mực nước"), 3, 0)
        self.lbl_water = value_label("--")
        gl.addWidget(self.lbl_water, 3, 1)
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

        # ---- Camera giám sát máng ăn: vẽ vùng + YOLO tracking + ID theo màu lưng ----
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
        self.lbl_mode = QLabel("--")
        self.lbl_mode.setStyleSheet("color:#2fae4e; font-weight:700;")
        ol.addWidget(self.lbl_mode, 0, 1)

        ol.addWidget(QLabel("Chu trình"), 1, 0)
        lbl_cycle = QLabel("Chờ lệnh")
        ol.addWidget(lbl_cycle, 1, 1)

        ol.addWidget(QLabel("Trạng thái"), 2, 0)
        self.lbl_state = QLabel("Chưa kết nối")
        self.lbl_state.setStyleSheet("color:#9a9a9a; font-weight:700;")
        ol.addWidget(self.lbl_state, 2, 1)
        right.addWidget(gb_over)

        right.addStretch(1)

    # ------------------------------------------------------------------
    def update_from_blynk(self, data: dict):
        """Nhận dict từ BlynkPoller.data_updated (xem blynk_client.py) mỗi
        chu kỳ polling, cập nhật các label hiển thị dữ liệu THẬT thay vì
        số liệu tĩnh. Gọi 1 lần mỗi lần poller đọc xong, nên không cần
        tính toán gì phức tạp ở đây - chỉ gán trực tiếp."""
        temp = data.get("temp")
        humi = data.get("humi")
        cam = data.get("cam")
        water = data.get("water")
        mode = data.get("mode")

        if temp is not None:
            self.lbl_temp.setText(str(temp))
        if humi is not None:
            self.lbl_humi.setText(str(humi))
        if cam is not None:
            self.lbl_cam.setText(str(cam))
        if water is not None:
            try:
                self.lbl_water.setText("Đầy" if int(float(water)) == 1 else "Cạn")
            except (ValueError, TypeError):
                self.lbl_water.setText("--")

        if mode is not None:
            try:
                is_auto = int(float(mode)) == 1
                self.lbl_mode.setText("AUTO (tự động)" if is_auto else "MANUAL (tay)")
            except (ValueError, TypeError):
                pass

        self.dot_system.set_on(True)
        self.lbl_state.setText("Bình thường")
        self.lbl_state.setStyleSheet("color:#2fae4e; font-weight:700;")
        self._last_data_time = time.time()

    # ------------------------------------------------------------------
    def _tick(self):
        # Neu qua lau khong nhan duoc du lieu tu BlynkPoller (mat mang, ESP32
        # offline...), bao trang thai "mat ket noi" thay vi tiep tuc hien
        # thi so lieu cu nhu the van con dung - tranh hieu nham.
        if self._last_data_time is None:
            return
        if time.time() - self._last_data_time > 15:
            self.dot_system.set_on(False)
            self.lbl_state.setText("⚠️ Mất kết nối dữ liệu")
            self.lbl_state.setStyleSheet("color:#c0392b; font-weight:700;")
