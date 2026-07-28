# -*- coding: utf-8 -*-
"""
home_tab.py — Tab HOME (ĐÃ GỘP với SCREEN cũ theo bố cục tham khảo mới)

Bố cục 3 khối theo chiều ngang ở hàng trên (Cảm biến môi trường | Tổng quan
hệ thống (camera) | Lịch trình + Hệ thống vận hành), và 1 hàng dưới cùng
"Cơ cấu chấp hành" hiển thị trạng thái ON/OFF của 8 relay (không gồm "Cho
ăn" vì đó là nút xung, không phải trạng thái bật/tắt ổn định).

ĐÃ BỎ HẲN theo yêu cầu (không tồn tại phần cứng thật):
  - "Cảm biến Limit", "Cảm biến Home" (chỉ có trên HMI công nghiệp gốc,
    hệ thống này chạy động cơ bước vòng hở, không có công tắc hành trình)
  - "EMERGENCY" (không có nút dừng khẩn cấp dạng đèn báo trạng thái ổn định
    — V15 là nút momentary, không có gì để đọc lại/hiển thị đèn báo)

GHI CHÚ: khối "Tổng quan hệ thống" ở giữa vẫn dùng camera + vẽ vùng + YOLO
tracking hiện có (CameraZoneWidget), KHÔNG dựng lại thành bản đồ trại 2D
trừu tượng như ảnh tham khảo (đó sẽ là 1 tính năng lớn riêng - định vị vị
trí con vật lên sơ đồ tọa độ trại, khác với overlay trên khung hình camera
đang có). Nếu bạn thực sự muốn bản đồ 2D riêng, báo lại để làm thêm.
"""

import time
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QGroupBox, QFrame
)

from ui.camera_zone import CameraZoneWidget


# ----------------------------------------------------------------------
def sensor_card(icon, label, unit=""):
    """1 ô cảm biến kiểu hộp bo góc: icon + tên nhỏ phía trên, giá trị to
    phía dưới - giống đúng bố cục 4 ô 'Cảm biến môi trường' ở ảnh tham khảo."""
    frame = QFrame()
    frame.setStyleSheet(
        "QFrame { background:#fbf8ec; }"
    )
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(10, 8, 10, 8)
    lay.setSpacing(2)

    top = QHBoxLayout()
    top.addWidget(QLabel(icon))
    lbl_name = QLabel(label)
    lbl_name.setStyleSheet("font-size:14px; color:#666;")
    top.addWidget(lbl_name)
    top.addStretch(1)
    lay.addLayout(top)

    row_val = QHBoxLayout()
    lbl_val = QLabel("--")
    lbl_val.setStyleSheet("font-size:25px; font-weight:800; color:#1857a4;")
    row_val.addWidget(lbl_val)
    if unit:
        lbl_unit = QLabel(unit)
        lbl_unit.setStyleSheet("color:#888; font-size:15px; padding-left:3px;")
        row_val.addWidget(lbl_unit)
    row_val.addStretch(1)
    lay.addLayout(row_val)

    return frame, lbl_val


def device_status_card(icon, label):
    """1 ô trong khối 'Cơ cấu chấp hành' - icon + tên + trạng thái ON/OFF
    (CHỈ HIỂN THỊ, không phải nút bấm - muốn bật/tắt tay thì sang tab MANUAL)."""
    frame = QFrame()
    frame.setStyleSheet(
        "QFrame { background:#fbf8ec; }"
    )
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(10, 10, 10, 10)
    lay.setSpacing(4)

    top = QHBoxLayout()
    top.addWidget(QLabel(icon))
    lbl_name = QLabel(label)
    lbl_name.setStyleSheet("font-weight:700; font-size:15px;")
    top.addWidget(lbl_name)
    top.addStretch(1)
    lay.addLayout(top)

    lbl_status = QLabel("OFF")
    lbl_status.setAlignment(Qt.AlignCenter)
    lbl_status.setStyleSheet(
        "background:transparent; border:none; "
        "padding:6px; font-weight:800; color:#b23a3a; font-size:16px;"
    )
    lay.addWidget(lbl_status)

    return frame, lbl_status


class StatusDot(QLabel):
    def __init__(self, on=False):
        super().__init__()
        self.set_on(on)
        self.setFixedSize(18, 18)

    def set_on(self, on):
        color = "#2fae4e" if on else "#9a9a9a"
        self.setStyleSheet(f"background:{color}; border-radius:9px; border:1px solid #555;")


# (icon, nhãn, virtual_pin) — 8 relay, KHÔNG gồm "Cho ăn" (V6 là nút xung,
# không phải trạng thái bật/tắt ổn định nên không hợp để hiện ON/OFF ở đây)
ACTUATOR_ROWS = [
    ("🌀", "Quạt Thổi", "V7"),
    ("🌀", "Quạt Hút", "V8"),
    ("💡", "Đèn", "V9"),
    ("🔥", "Đèn Sưởi", "V10"),
    ("🚰", "Bơm Máng", "V11"),
    ("🧽", "Bơm Sàn", "V12"),
    ("🚿", "Bơm Tắm", "V13"),
    ("💦", "Bơm Phun Sương", "V14"),
]


class HomeTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_data_time = None
        self.scheduler = None
        self._prev_devices = {}
        self._stat_date = None
        self._stat_counts = {"cho_an": 0, "tam": 0, "rua_chuong": 0}
        self.device_status_labels = {}  # pin -> QLabel (khối Cơ cấu chấp hành)
        self._build_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

    def attach_scheduler(self, scheduler):
        self.scheduler = scheduler

    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)

        top_row = QHBoxLayout()
        root.addLayout(top_row, 3)

        # ================= CỘT TRÁI: Cảm biến môi trường + Lịch trình tiếp theo =================
        left = QVBoxLayout()
        top_row.addLayout(left, 2)

        gb_sensor = QGroupBox("Cảm biến môi trường")
        sl = QGridLayout(gb_sensor)
        sl.setSpacing(10)

        card, self.lbl_temp = sensor_card("🌡️", "Nhiệt độ", "°C")
        sl.addWidget(card, 0, 0)
        card, self.lbl_cam = sensor_card("🌾", "Cám tồn", "g")
        sl.addWidget(card, 0, 1)
        card, self.lbl_humi = sensor_card("💧", "Độ ẩm", "%")
        sl.addWidget(card, 1, 0)
        card, self.lbl_water = sensor_card("🚰", "Mực nước")
        sl.addWidget(card, 1, 1)
        left.addWidget(gb_sensor)

        gb_next = QGroupBox("Lịch trình tiếp theo")
        nl = QVBoxLayout(gb_next)
        self.lbl_next_schedule = QLabel("Đang tải...")
        self.lbl_next_schedule.setWordWrap(True)
        self.lbl_next_schedule.setStyleSheet("font-weight:700; color:#1857a4; font-size:16px;")
        nl.addWidget(self.lbl_next_schedule)
        note_next = QLabel("")
        note_next.setStyleSheet("color:#999; font-size:13px; font-style:italic;")
        note_next.setWordWrap(True)
        nl.addWidget(note_next)
        left.addWidget(gb_next)

        # ================= CỘT TRÁI (tiếp): Hệ thống vận hành + Thống kê hôm nay =================
        gb_over = QGroupBox("Hệ thống vận hành")
        ol = QGridLayout(gb_over)
        self.dot_system = StatusDot(on=True)
        ol.addWidget(self.dot_system, 0, 0)
        lbl_running = QLabel("Hệ thống đang chạy")
        lbl_running.setStyleSheet("font-weight:700;")
        ol.addWidget(lbl_running, 0, 1)

        ol.addWidget(QLabel("Chế độ hiện tại"), 1, 0)
        self.lbl_mode = QLabel("--")
        self.lbl_mode.setStyleSheet("color:#2fae4e; font-weight:700;")
        ol.addWidget(self.lbl_mode, 1, 1)

        ol.addWidget(QLabel("Trạng thái"), 2, 0)
        self.lbl_state = QLabel("Chưa kết nối")
        self.lbl_state.setStyleSheet("color:#9a9a9a; font-weight:700;")
        ol.addWidget(self.lbl_state, 2, 1)
        left.addWidget(gb_over)

        gb_stat = QGroupBox("Thống kê hôm nay")
        stl = QGridLayout(gb_stat)
        stl.addWidget(QLabel("🍽️ Lần cho ăn"), 0, 0)
        self.lbl_stat_an = QLabel("0")
        self.lbl_stat_an.setStyleSheet("font-weight:700;")
        stl.addWidget(self.lbl_stat_an, 0, 1)
        stl.addWidget(QLabel("🚿 Lần tắm"), 1, 0)
        self.lbl_stat_tam = QLabel("0")
        self.lbl_stat_tam.setStyleSheet("font-weight:700;")
        stl.addWidget(self.lbl_stat_tam, 1, 1)
        stl.addWidget(QLabel("🧽 Lần rửa chuồng"), 2, 0)
        self.lbl_stat_vs = QLabel("0")
        self.lbl_stat_vs.setStyleSheet("font-weight:700;")
        stl.addWidget(self.lbl_stat_vs, 2, 1)
        left.addWidget(gb_stat)

        left.addStretch(1)

        # ================= GIỮA/PHẢI: Tổng quan hệ thống (camera + zone) =================
        gb_mid = QGroupBox("Tổng quan hệ thống")
        mid_lay = QVBoxLayout(gb_mid)
        self.camera_widget = CameraZoneWidget()
        mid_lay.addWidget(self.camera_widget)
        top_row.addWidget(gb_mid, 7)

        # ================= HÀNG DƯỚI: Cơ cấu chấp hành (8 relay, chỉ hiển thị) =================
        gb_act = QGroupBox("Cơ cấu chấp hành")
        act_lay = QGridLayout(gb_act)
        act_lay.setSpacing(12)
        for i, (icon, name, pin) in enumerate(ACTUATOR_ROWS):
            r, c = divmod(i, 4)
            card, lbl = device_status_card(icon, name)
            self.device_status_labels[pin] = lbl
            act_lay.addWidget(card, r, c)
        root.addWidget(gb_act)

    # ------------------------------------------------------------------
    def _set_device_status(self, lbl, on):
        lbl.setText("ON" if on else "OFF")
        color = "#2fae4e" if on else "#b23a3a"
        lbl.setStyleSheet(
            f"background:transparent; border:none; "
            f"padding:6px; font-weight:800; color:{color}; font-size:16px;"
        )

    def update_from_blynk(self, data: dict):
        """Nhận dict từ BlynkPoller.data_updated - gộp chung việc từng tách
        riêng HomeTab (cảm biến/lịch/thống kê) VÀ ScreenTab cũ (trạng thái
        8 relay) vào 1 chỗ duy nhất."""
        temp = data.get("temp")
        humi = data.get("humi")
        cam = data.get("cam")
        water = data.get("water")
        mode = data.get("mode")
        devices = data.get("devices", {})

        if temp is not None:
            self.lbl_temp.setText(str(temp))
        if humi is not None:
            self.lbl_humi.setText(str(humi))
        if cam is not None:
            self.lbl_cam.setText(str(cam))
        if water is not None:
            try:
                self.lbl_water.setText("Đầy" if int(float(water)) == 1 else "cạn")
            except (ValueError, TypeError):
                self.lbl_water.setText("--")

        if mode is not None:
            try:
                is_auto = int(float(mode)) == 1
                self.lbl_mode.setText("AUTO (tự động)" if is_auto else "MANUAL (tay)")
            except (ValueError, TypeError):
                pass

        for pin, lbl in self.device_status_labels.items():
            val = devices.get(pin)
            if val is None:
                continue
            try:
                self._set_device_status(lbl, int(float(val)) == 1)
            except (ValueError, TypeError):
                pass

        self.dot_system.set_on(True)
        self.lbl_state.setText("Bình thường")
        self.lbl_state.setStyleSheet("color:#2fae4e; font-weight:700;")
        self._last_data_time = time.time()

        self._cap_nhat_thong_ke(devices)

    def _cap_nhat_thong_ke(self, devices: dict):
        today = time.strftime("%Y-%m-%d")
        if self._stat_date != today:
            self._stat_date = today
            self._stat_counts = {"cho_an": 0, "tam": 0, "rua_chuong": 0}
            self._prev_devices = {}

        pin_map = {"V6": "cho_an", "V13": "tam", "V12": "rua_chuong"}
        for pin, kind in pin_map.items():
            val = devices.get(pin)
            if val is None:
                continue
            try:
                cur = int(float(val))
            except (ValueError, TypeError):
                continue
            prev = self._prev_devices.get(pin)
            if prev == 1 and cur == 0:
                self._stat_counts[kind] += 1
            self._prev_devices[pin] = cur

        self.lbl_stat_an.setText(str(self._stat_counts["cho_an"]))
        self.lbl_stat_tam.setText(str(self._stat_counts["tam"]))
        self.lbl_stat_vs.setText(str(self._stat_counts["rua_chuong"]))

    # ------------------------------------------------------------------
    def _tick(self):
        if self.scheduler is not None:
            self.lbl_next_schedule.setText(self.scheduler.next_upcoming())

        if self._last_data_time is None:
            return
        if time.time() - self._last_data_time > 15:
            self.dot_system.set_on(False)
            self.lbl_state.setText("⚠️ Mất kết nối dữ liệu")
            self.lbl_state.setStyleSheet("color:#c0392b; font-weight:700;")
