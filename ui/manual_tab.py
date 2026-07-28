# -*- coding: utf-8 -*-
"""
manual_tab.py — Tab MANUAL (ĐÃ NỐI BLYNK CLOUD)

Bảng khóa theo chế độ (đúng theo firmware ESP32 hiện tại):
  - MANUAL (V5=0): TẤT CẢ thiết bị trong lưới bấm tay được, không ngoại lệ.
  - AUTO (V5=1)  : CHỈ 4 mục dưới đây bấm tay được (vì vòng lặp AUTO
    không hề đụng tới chúng): Đèn (V9), Mở khóa bơm nước (V19), Bơm tắm
    (V13), Bơm rửa sàn (V12). 5 thiết bị còn lại (Quạt thổi V7, Quạt hút
    V8, Sưởi V10, Bơm máng nước V11, Phun sương V14) bị KHÓA MỜ khi AUTO
    vì vòng lặp AUTO thực sự đang tự điều khiển chúng theo cảm biến.
    (Cho ăn - V6 - không còn nằm trong lưới này nữa vì trùng chức năng với
    khu "Cho ăn nhanh" ở trên đầu tab; V6 luôn bấm được ở cả 2 chế độ qua
    khu vực đó.)

GHI CHÚ GPIO (đối chiếu đúng firmware, PIN_QUAT1=GPIO5, PIN_QUAT2=GPIO6):
  - V7 -> PIN_QUAT1 -> GPIO5 -> Quạt THỔI vào chuồng
  - V8 -> PIN_QUAT2 -> GPIO6 -> Quạt HÚT ra chuồng
"""

from PyQt5.QtWidgets import (
    QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QSpinBox, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject

from ui.style import COLOR_ON_GREEN, COLOR_ALARM_RED

# SUA: bo het mau cam/do rieng le cua rieng tab MANUAL - dung lai dung 2 mau
# da co san trong bang mau chung (xanh la ON + do bao dong), de dong bo voi
# HomeTab/AlarmTab/... thay vi tab nay tu bay ra 1 bo mau rieng.
CELL_BG = "#fbf8ec"      # giong het o cam bien / o Co cau chap hanh ben HomeTab

# (icon, tên hiển thị, virtual_pin, la_nut_xung, luon_tu_do_bat_ke_mode, nhan_nut_xung)
# SUA: bo "CHO AN" khoi luoi nay vi TRUNG chuc nang voi khu "Cho an nhanh"
# da co san o tren dau tab (EmergencyPanel) - thay bang nut xac nhan V19
# "Mo khoa bom nuoc", dung de nguoi dung bao he thong da kiem tra/sua xong
# su co bom mang nuoc (xem BLYNK_WRITE(V19) trong firmware).
DEVICES = [
    ("🌀", "QUẠT THỔI (vào chuồng)", "V7", False, False, None),
    ("🌀", "QUẠT HÚT (ra chuồng)", "V8", False, False, None),
    ("💡", "ĐÈN", "V9", False, True, None),
    ("🔓", "MỞ KHÓA BƠM NƯỚC", "V19", True, True, "XÁC NHẬN ĐÃ SỬA"),
    ("🔥", "SƯỞI", "V10", False, False, None),
    ("🚿", "TẮM", "V13", False, True, None),
    ("🧽", "RỬA CHUỒNG", "V12", False, True, None),
    ("🚰", "CẤP NƯỚC UỐNG", "V11", False, False, None),
    ("💦", "PHUN SƯƠNG", "V14", False, False, None),
]


class DeviceToggle(QVBoxLayout):
    """1 ô thiết bị trong lưới MANUAL: icon + tên + nút bật/tắt (hoặc nút xung)."""

    def __init__(self, icon_text, name, pin, is_pulse, always_free, blynk_client,
                 feed_coordinator=None, pulse_label=None):
        super().__init__()
        self.pin = pin
        self.is_pulse = is_pulse
        self.always_free = always_free
        self.blynk_client = blynk_client
        self.feed_coordinator = feed_coordinator
        # SUA: truoc day chu nut xung bi hardcode cung "XA CAM NGAY" cho MOI
        # thiet bi kieu xung - gio moi thiet bi xung co the tu dat nhan rieng
        # (vd V19 dung "XAC NHAN DA SUA"), mac dinh ve "XA CAM NGAY" neu
        # khong truyen (giu tuong thich nguoc).
        self.pulse_label = pulse_label or "XẢ CÁM NGAY"
        self.setContentsMargins(10, 10, 10, 10)
        self.setSpacing(6)

        lbl_icon = QLabel(icon_text)
        lbl_icon.setAlignment(Qt.AlignCenter)
        lbl_icon.setStyleSheet("font-size:29px;")
        self.addWidget(lbl_icon)

        lbl_name = QLabel(name)
        lbl_name.setAlignment(Qt.AlignCenter)
        lbl_name.setStyleSheet("font-weight:700; font-size:15px;")
        self.addWidget(lbl_name)

        self.btn = QPushButton(self.pulse_label if is_pulse else "OFF")
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
        self.lbl_status.setStyleSheet("color:#888; font-size:13px;")
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
            self.lbl_status.setText(" Đã gửi" if ok else "❌ Gửi lỗi (kiểm tra mạng/token)")

        self.blynk_client.set_pin_async(self.pin, value, callback=on_done)

    def _pulse(self):
        """Nút dạng xung. Riêng V6 (Cho ăn) dùng chung FeedCoordinator với
        scheduler để không bao giờ bấm đè lên đúng lúc lịch tự động đang
        giữa chừng ghi V4 (xem feed_coordinator.py). Các nút xung khác (vd
        V19 - xác nhận đã sửa bơm nước) chỉ cần gửi thẳng giá trị 1, giống
        hệt cách nút Dừng khẩn cấp (V15) đang làm."""
        self.lbl_status.setText("Đang gửi lệnh...")

        if self.pin == "V6":
            if self.feed_coordinator is None:
                self.lbl_status.setText("⚠️ Chưa khởi tạo FeedCoordinator")
                return

            def on_done_feed(ok, message):
                self.lbl_status.setText(message)

            self.feed_coordinator.trigger_feed_now_async(source_label="Bấm tay", on_status=on_done_feed)
            return

        if self.blynk_client is None:
            self.lbl_status.setText("⚠️ Chưa kết nối Blynk")
            return

        def on_done(ok):
            self.lbl_status.setText("✅ Đã gửi xác nhận" if ok else "❌ Gửi lỗi (kiểm tra mạng/token)")

        self.blynk_client.set_pin_async(self.pin, 1, callback=on_done)


class EmergencyPanel(QGroupBox):
    """Khu vực nổi bật riêng, tách khỏi lưới 9 thiết bị thông thường - khớp
    với 2 nút tương đương trên app MOBILE (Blynk): 'Cho ăn ngay với X gram'
    (ghi V4 rồi xác nhận + bấm V6 qua FeedCoordinator) và 'DỪNG NGAY' (V15,
    dừng khẩn cấp giữa chừng lúc đang xả cám - xem thiết kế khóa V6/V15
    trong ChipChinh_ESP32S3.ino)."""

    def __init__(self, blynk_client, feed_coordinator, parent=None):
        super().__init__("⚡ Cho ăn nhanh / Dừng khẩn cấp", parent)
        self.blynk_client = blynk_client
        self.feed_coordinator = feed_coordinator
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # --- HÀNG 1: Khối lượng (trái) & Lời nhắc (phải) ---
        row_top = QHBoxLayout()
        row_top.setSpacing(15)
        
        col_left_top = QHBoxLayout()
        lbl_gram = QLabel("Khối lượng:")
        lbl_gram.setStyleSheet("font-weight: bold; font-size: 14px;")
        col_left_top.addWidget(lbl_gram)
        self.spin_gram = QSpinBox()
        self.spin_gram.setRange(1, 500)
        self.spin_gram.setValue(100)
        self.spin_gram.setSuffix(" g")
        self.spin_gram.setFixedWidth(100)
        self.spin_gram.setStyleSheet("font-size: 14px; padding: 4px;")
        col_left_top.addWidget(self.spin_gram)
        col_left_top.addStretch()
        row_top.addLayout(col_left_top, 1)

        lbl_stop_hint = QLabel("⚠️ Chỉ dừng được khi đang xả cám")
        lbl_stop_hint.setStyleSheet("color:#888; font-size:13px;")
        lbl_stop_hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_top.addWidget(lbl_stop_hint, 1)
        
        root.addLayout(row_top)

        # --- HÀNG 2: 2 Nút bấm chính (căn bằng chiều cao & bo góc) ---
        row_btns = QHBoxLayout()
        row_btns.setSpacing(15)

        self.btn_feed_now = QPushButton("🍽️ CHO ĂN NGAY")
        self.btn_feed_now.setFixedHeight(50)
        self.btn_feed_now.setStyleSheet(
            f"background:{COLOR_ON_GREEN}; color:white; font-weight:800; "
            f"border-radius:6px; font-size:15px; border:1px solid #218a3c;"
        )
        self.btn_feed_now.clicked.connect(self._on_feed_now)
        row_btns.addWidget(self.btn_feed_now, 1)

        self.btn_stop = QPushButton("🛑 DỪNG NGAY")
        self.btn_stop.setFixedHeight(50)
        self.btn_stop.setStyleSheet(
            f"background:{COLOR_ALARM_RED}; color:white; font-weight:900; "
            f"font-size:15px; border-radius:6px; border:1px solid #a92e2e;"
        )
        self.btn_stop.clicked.connect(self._on_stop)
        row_btns.addWidget(self.btn_stop, 1)

        root.addLayout(row_btns)

        # --- HÀNG 3: Trạng thái báo về (trái & phải) ---
        row_status = QHBoxLayout()
        row_status.setSpacing(15)
        
        self.lbl_feed_status = QLabel("")
        self.lbl_feed_status.setStyleSheet("color:#555; font-size:13px;")
        self.lbl_feed_status.setWordWrap(True)
        row_status.addWidget(self.lbl_feed_status, 1)

        self.lbl_stop_status = QLabel("")
        self.lbl_stop_status.setStyleSheet("color:#555; font-size:13px;")
        self.lbl_stop_status.setWordWrap(True)
        self.lbl_stop_status.setAlignment(Qt.AlignRight)
        row_status.addWidget(self.lbl_stop_status, 1)

        root.addLayout(row_status)

    def _on_feed_now(self):
        gram = self.spin_gram.value()
        self.lbl_feed_status.setText("Đang gửi...")
        if self.feed_coordinator is None:
            self.lbl_feed_status.setText("⚠️ Chưa khởi tạo FeedCoordinator")
            return

        def on_status(ok, message):
            self.lbl_feed_status.setText(message)

        self.feed_coordinator.trigger_feed_async(gram, source_label="Cho ăn nhanh (Manual)", on_status=on_status)

    def _on_stop(self):
        self.lbl_stop_status.setText("Đang gửi lệnh dừng...")
        if self.blynk_client is None:
            self.lbl_stop_status.setText("⚠️ Chưa kết nối Blynk")
            return

        def on_done(ok):
            self.lbl_stop_status.setText("✅ Đã gửi lệnh dừng khẩn cấp (V15)" if ok else "❌ Gửi lỗi")

        self.blynk_client.set_pin_async("V15", 1, callback=on_done)


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
        self.lbl_status.setStyleSheet("color:#888; font-size:14px;")
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
        self.lbl_status.setText("Đồng bộ...")
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

        self.emergency_panel = EmergencyPanel(self.blynk_client, self.feed_coordinator)
        root.addWidget(self.emergency_panel)

        note = QLabel(
            "ℹ️ Khi đang AUTO: chỉ Đèn / Tắm / Rửa chuồng / Mở khóa bơm nước bấm tay "
            "được (4 mục này AUTO không tự điều khiển; riêng Cho ăn luôn dùng qua khu "
            "'Cho ăn nhanh' phía trên). Các thiết bị còn lại (Quạt thổi, Quạt hút, "
            "Sưởi, Bơm máng nước, Phun sương) sẽ tự khóa mờ vì đang do AUTO điều khiển "
            "theo cảm biến. Chuyển sang MANUAL để mở khóa toàn bộ."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#555; font-size:14px; padding:2px 0 10px 0;")
        root.addWidget(note)

        grid = QGridLayout()
        grid.setSpacing(18)

        # SUA: gom luoi thiet bi vao 1 khung (QGroupBox) rieng cho gon gang,
        # thay vi tha noi truc tiep tren tab - dung tinh than "gom vao khung
        # chuyen dung" theo yeu cau.
        gb_devices = QGroupBox("Điều khiển thiết bị")
        gb_devices_lay = QVBoxLayout(gb_devices)
        gb_devices_lay.addLayout(grid)
        root.addWidget(gb_devices)

        self.toggles = {}
        for i, (icon, name, pin, is_pulse, always_free, pulse_label) in enumerate(DEVICES):
            r, c = divmod(i, 3)
            toggle = DeviceToggle(icon, name, pin, is_pulse, always_free,
                                   self.blynk_client, self.feed_coordinator, pulse_label)
            self.toggles[name] = toggle
            # Boc trong 1 khung nho de tach o ro rang, khit gon thay vi tha
            # noi cac widget ngay tren luoi chung.
            cell = QFrame()
            # SUA: bo border rieng cua tung o - da nam trong QGroupBox co
            # border roi, ve them 1 lop border quanh moi o gay ra hieu ung
            # "khung long khung" thua thai. Chi giu mau nen de phan biet o,
            # dung y het kieu the "Co cau chap hanh" ben HomeTab.
            cell.setStyleSheet(f"QFrame {{ background:{CELL_BG}; border:none; }}")
            cell.setLayout(toggle)
            grid.addWidget(cell, r, c)

        # SUA: chan KHONG cho luoi 9 thiet bi (toan la nut bam, khong phai
        # bang/do thi) bi keo gian het phan khong gian con lai cua tab - day
        # la loai "hang dieu khien" theo dung nguyen tac chi cho Treeview/
        # do thi duoc gian, con lai phai giu nguyen kich thuoc tu nhien.
        root.addStretch(1)

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

        v6 = devices.get("V6")
        if v6 is not None:
            try:
                dang_cho_an = int(float(v6)) == 1
            except (ValueError, TypeError):
                dang_cho_an = False
            self.emergency_panel.btn_feed_now.setEnabled(not dang_cho_an)