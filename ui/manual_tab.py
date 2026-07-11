# -*- coding: utf-8 -*-
"""
manual_tab.py — Tab MANUAL (ĐÃ NỐI BLYNK CLOUD)

Bảng khóa theo chế độ (đúng theo firmware ESP32 hiện tại):
  - MANUAL (V5=0): TẤT CẢ 9 thiết bị bấm tay được, không ngoại lệ.
  - AUTO (V5=1)  : CHỈ 4 thiết bị dưới đây bấm tay được (vì vòng lặp AUTO
    không hề đụng tới chúng): Đèn (V9), Cho ăn (V6), Bơm tắm (V13),
    Bơm rửa sàn (V12). 5 thiết bị còn lại (Quạt thổi V7, Quạt hút V8,
    Sưởi V10, Bơm máng nước V11, Phun sương V14) bị KHÓA MỜ khi AUTO vì
    vòng lặp AUTO thực sự đang tự điều khiển chúng theo cảm biến.

GHI CHÚ GPIO (đối chiếu đúng firmware, PIN_QUAT1=GPIO5, PIN_QUAT2=GPIO6):
  - V7 -> PIN_QUAT1 -> GPIO5 -> Quạt THỔI vào chuồng
  - V8 -> PIN_QUAT2 -> GPIO6 -> Quạt HÚT ra chuồng
"""

from PyQt5.QtWidgets import (
    QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject

# (icon, tên hiển thị, virtual_pin, la_nut_xung, luon_tu_do_bat_ke_mode)
DEVICES = [
    ("🌀", "QUẠT THỔI (vào chuồng)", "V7", False, False),
    ("🌀", "QUẠT HÚT (ra chuồng)", "V8", False, False),
    ("💡", "ĐÈN", "V9", False, True),
    ("🍽️", "CHO ĂN", "V6", True, True),
    ("🔥", "SƯỞI", "V10", False, False),
    ("🚿", "TẮM", "V13", False, True),
    ("🧽", "RỬA CHUỒNG", "V12", False, True),
    ("🚰", "CẤP NƯỚC UỐNG", "V11", False, False),
    ("💦", "PHUN SƯƠNG", "V14", False, False),
]


class DeviceToggle(QVBoxLayout):
    """1 ô thiết bị trong lưới MANUAL: icon + tên + nút bật/tắt (hoặc nút xung)."""

    def __init__(self, icon_text, name, pin, is_pulse, always_free, blynk_client, feed_coordinator=None):
        super().__init__()
        self.pin = pin
        self.is_pulse = is_pulse
        self.always_free = always_free
        self.blynk_client = blynk_client
        self.feed_coordinator = feed_coordinator

        lbl_icon = QLabel(icon_text)
        lbl_icon.setAlignment(Qt.AlignCenter)
        lbl_icon.setStyleSheet("font-size:26px;")
        self.addWidget(lbl_icon)

        lbl_name = QLabel(name)
        lbl_name.setAlignment(Qt.AlignCenter)
        lbl_name.setStyleSheet("font-weight:700; font-size:12px;")
        self.addWidget(lbl_name)

        self.btn = QPushButton("XẢ CÁM NGAY" if is_pulse else "OFF")
        self.btn.setFixedHeight(38)
        if not is_pulse:
            self.btn.setCheckable(True)
            self.btn.setProperty("role", "toggleOff")
            self.btn.clicked.connect(self._toggle)
        else:
            self.btn.setProperty("role", "toggleOff")
            self.btn.clicked.connect(self._pulse)
        self.addWidget(self.btn)

        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("color:#888; font-size:10px;")
        self.addWidget(self.lbl_status)

    def set_locked(self, locked):
        """locked=True khi thiết bị này KHÔNG được nằm trong nhóm always_free
        và hệ thống đang ở AUTO -> khóa mờ nút, không cho bấm."""
        if self.always_free:
            self.btn.setEnabled(True)
            self.lbl_status.setText("")
            return
        self.btn.setEnabled(not locked)
        self.lbl_status.setText("🔒 Đang khóa (AUTO tự điều khiển)" if locked else "")

    def sync_from_remote(self, value):
        """Cập nhật trạng thái nút theo giá trị ĐỌC ĐƯỢC từ Blynk Cloud (do
        app mobile bấm, hoặc do AUTO tự điều khiển) - CHỈ cập nhật giao
        diện, KHÔNG gọi set_pin_async() lại, để tránh vòng lặp ghi-đọc-ghi
        vô nghĩa (và tốn API call). Dùng block_signals để đổi setChecked()
        mà không kích hoạt lại _toggle()."""
        if self.is_pulse:
            # V6 (Cho ăn) là nút xung, dùng khóa dangChoAn riêng bên firmware.
            # value=1 nghĩa la dang xa cam - hien thi trang thai, khong doi nut.
            try:
                dang_cho_an = int(float(value)) == 1
            except (ValueError, TypeError):
                dang_cho_an = False
            self.btn.setEnabled(not dang_cho_an)
            if dang_cho_an:
                self.lbl_status.setText("🍽️ Đang cho ăn...")
            elif self.lbl_status.text() == "🍽️ Đang cho ăn...":
                self.lbl_status.setText("✅ Đã xong")
            return

        try:
            checked = int(float(value)) == 1
        except (ValueError, TypeError):
            return

        if self.btn.isChecked() == checked:
            return  # Da dung roi, khong can dong bo lai (tranh nhap nhay UI)

        self.btn.blockSignals(True)
        self.btn.setChecked(checked)
        self.btn.setText("ON" if checked else "OFF")
        self.btn.setProperty("role", "toggleOn" if checked else "toggleOff")
        self.btn.style().unpolish(self.btn)
        self.btn.style().polish(self.btn)
        self.btn.blockSignals(False)
        self.lbl_status.setText("🔄 Đồng bộ từ xa")

    def _toggle(self, checked):
        value = 1 if checked else 0
        self.btn.setText("ON" if checked else "OFF")
        self.btn.setProperty("role", "toggleOn" if checked else "toggleOff")
        self.btn.style().unpolish(self.btn)
        self.btn.style().polish(self.btn)

        self.lbl_status.setText("Đang gửi lệnh...")
        if self.blynk_client is None:
            self.lbl_status.setText("⚠️ Chưa kết nối Blynk")
            return

        def on_done(ok):
            self.lbl_status.setText("✅ Đã gửi" if ok else "❌ Gửi lỗi (kiểm tra mạng/token)")

        self.blynk_client.set_pin_async(self.pin, value, callback=on_done)

    def _pulse(self):
        """Nút dạng xung (Cho ăn -> V6): dùng chung FeedCoordinator với
        scheduler để không bao giờ bấm đè lên đúng lúc lịch tự động đang
        giữa chừng ghi V4 (xem feed_coordinator.py)."""
        self.lbl_status.setText("Đang gửi lệnh...")
        if self.feed_coordinator is None:
            self.lbl_status.setText("⚠️ Chưa khởi tạo FeedCoordinator")
            return

        def on_done(ok, message):
            self.lbl_status.setText(message)

        self.feed_coordinator.trigger_feed_now_async(source_label="Bấm tay", on_status=on_done)


class ModeSwitchSignal(QObject):
    mode_changed = pyqtSignal(bool)  # True = đang AUTO


class ModeSwitch(QHBoxLayout):
    """Công tắc Chế độ AUTO/MANUAL — ghi xuống V5, khớp BLYNK_WRITE(V5) trong firmware."""

    def __init__(self, blynk_client):
        super().__init__()
        self.blynk_client = blynk_client
        self.signals = ModeSwitchSignal()

        self.addWidget(QLabel("Chế độ hệ thống:"))
        self.btn_mode = QPushButton("MANUAL (tay)")
        self.btn_mode.setCheckable(True)
        self.btn_mode.setFixedHeight(34)
        self.btn_mode.setProperty("role", "toggleOff")
        self.btn_mode.clicked.connect(self._toggle_mode)
        self.addWidget(self.btn_mode)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#888; font-size:11px;")
        self.addWidget(self.lbl_status)
        self.addStretch(1)

    def _toggle_mode(self, checked):
        value = 1 if checked else 0
        self.btn_mode.setText("AUTO (tự động)" if checked else "MANUAL (tay)")
        self.btn_mode.setProperty("role", "toggleOn" if checked else "toggleOff")
        self.btn_mode.style().unpolish(self.btn_mode)
        self.btn_mode.style().polish(self.btn_mode)

        self.signals.mode_changed.emit(checked)  # checked=True nghĩa là đang AUTO

        if self.blynk_client is None:
            self.lbl_status.setText("⚠️ Chưa kết nối Blynk")
            return

        def on_done(ok):
            self.lbl_status.setText("✅ Đã chuyển chế độ" if ok else "❌ Gửi lỗi")

        self.blynk_client.set_pin_async("V5", value, callback=on_done)

    def sync_from_remote(self, value):
        """Cập nhật công tắc AUTO/MANUAL theo giá trị ĐỌC ĐƯỢC từ Blynk (do
        app mobile bấm) - KHÔNG gửi lại V5, chỉ đổi giao diện + báo cho
        ManualTab qua signal để khóa/mở khóa đúng các nút liên quan."""
        try:
            is_auto = int(float(value)) == 1
        except (ValueError, TypeError):
            return

        if self.btn_mode.isChecked() == is_auto:
            return

        self.btn_mode.blockSignals(True)
        self.btn_mode.setChecked(is_auto)
        self.btn_mode.setText("AUTO (tự động)" if is_auto else "MANUAL (tay)")
        self.btn_mode.setProperty("role", "toggleOn" if is_auto else "toggleOff")
        self.btn_mode.style().unpolish(self.btn_mode)
        self.btn_mode.style().polish(self.btn_mode)
        self.btn_mode.blockSignals(False)
        self.lbl_status.setText("🔄 Đồng bộ từ xa")
        self.signals.mode_changed.emit(is_auto)


class ManualTab(QWidget):
    def __init__(self, blynk_client=None, feed_coordinator=None, parent=None):
        super().__init__(parent)
        self.blynk_client = blynk_client
        self.feed_coordinator = feed_coordinator
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 20)

        self.mode_switch = ModeSwitch(self.blynk_client)
        self.mode_switch.signals.mode_changed.connect(self._on_mode_changed)
        root.addLayout(self.mode_switch)

        note = QLabel(
            "ℹ️ Khi đang AUTO: chỉ Đèn / Cho ăn / Tắm / Rửa chuồng bấm tay được "
            "(4 thiết bị này AUTO không tự điều khiển). Các thiết bị còn lại "
            "(Quạt thổi, Quạt hút, Sưởi, Bơm máng nước, Phun sương) sẽ tự khóa "
            "mờ vì đang do AUTO điều khiển theo cảm biến. Chuyển sang MANUAL để "
            "mở khóa toàn bộ."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#555; font-size:11px; padding:2px 0 10px 0;")
        root.addWidget(note)

        grid = QGridLayout()
        grid.setSpacing(18)
        root.addLayout(grid)

        self.toggles = {}
        for i, (icon, name, pin, is_pulse, always_free) in enumerate(DEVICES):
            r, c = divmod(i, 3)
            toggle = DeviceToggle(icon, name, pin, is_pulse, always_free, self.blynk_client, self.feed_coordinator)
            self.toggles[name] = toggle
            grid.addLayout(toggle, r, c)

        # trạng thái ban đầu: đang MANUAL -> không khóa gì cả
        self._on_mode_changed(False)

    def _on_mode_changed(self, is_auto):
        for toggle in self.toggles.values():
            toggle.set_locked(is_auto)

    def sync_from_blynk(self, data: dict):
        """Goi tu main.py moi khi BlynkPoller doc xong 1 chu ky (xem
        blynk_client.py). Day la CHIEU DONG BO NGUOC: khi bam nut tren app
        MOBILE (hoac AUTO tu dieu khien), giao dien Python cung phai doi
        theo, khong chi 1 chieu Python -> Blynk nhu truoc day."""
        mode = data.get("mode")
        if mode is not None:
            self.mode_switch.sync_from_remote(mode)

        devices = data.get("devices", {})
        for name, toggle in self.toggles.items():
            val = devices.get(toggle.pin)
            if val is not None:
                toggle.sync_from_remote(val)
