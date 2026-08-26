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
    QGroupBox, QSpinBox, QFrame, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
import time

from ui.thin_status_bar import ThinStatusBar

# SUA: bo het mau cam/do rieng le cua rieng tab MANUAL - dung lai dung 2 mau
# da co san trong bang mau chung (xanh la ON + do bao dong), de dong bo voi
# HomeTab/AlarmTab/... thay vi tab nay tu bay ra 1 bo mau rieng.
CELL_BG = "#fbf8ec"      # giong het o cam bien / o Co cau chap hanh ben HomeTab

# (tên hiển thị, virtual_pin, la_nut_xung, luon_tu_do_bat_ke_mode, nhan_nut_xung)
# SUA: bo "CHO AN" khoi luoi nay vi TRUNG chuc nang voi khu "Cho an nhanh"
# da co san o tren dau tab (EmergencyPanel) - thay bang nut xac nhan V19
# "Mo khoa bom nuoc", dung de nguoi dung bao he thong da kiem tra/sua xong
# su co bom mang nuoc (xem BLYNK_WRITE(V19) trong firmware).
# SUA: BO HAN truong icon (truoc day la phan tu dau tien cua tuple, vd
# "🌀") - theo dinh huong giao dien "khong icon, chi chu + mau" de tranh
# emoji mau me kieu app do AI tao nhanh, chuyen sang phong cach HMI cong
# nghiep gon gang chi dung chu + mau sac.
DEVICES = [
    ("QUẠT THỔI (vào chuồng)", "V7", False, False, None),
    ("QUẠT HÚT (ra chuồng)", "V8", False, False, None),
    ("ĐÈN", "V9", False, True, None),
    ("MỞ KHÓA BƠM NƯỚC", "V19", True, True, "XÁC NHẬN ĐÃ SỬA"),
    ("SƯỞI", "V10", False, False, None),
    ("TẮM", "V13", False, True, None),
    ("RỬA CHUỒNG", "V12", False, True, None),
    # SUA: THEM MOI - doi ten tu "CAP NUOC UONG" -> "BOM MANG" de KHOP
    # DUNG voi ten dung o ACTUATOR_ROWS ben ui/home_tab.py cho cung 1 pin
    # V11 - truoc day 2 tab goi khac ten cho cung 1 thiet bi.
    ("BƠM MÁNG", "V11", False, False, None),
    ("PHUN SƯƠNG", "V14", False, False, None),
]


class DeviceToggle(QVBoxLayout):
    """1 ô thiết bị trong lưới MANUAL: tên + nút bật/tắt (hoặc nút xung)."""

    def __init__(self, name, pin, is_pulse, always_free, blynk_client,
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

        # SUA: THEM MOI - chong RACE giua optimistic update (UI bat NGAY
        # luc bam) va vong POLL NEN (BlynkPoller, doc lai moi 3s DOC LAP,
        # khong biet gi ve viec vua bam). Neu vong doc do BAT DAU TRUOC
        # khi lenh ghi kip co hieu luc (de xay ra o Local vi phai xep hang
        # qua Lock), no se doc ve gia tri CU -> sync_from_remote() DE UI
        # VE SAI trong 1 nhip, roi vong poll KE TIEP moi doc dung -> nguoi
        # dung thay nut "nhay" ON->OFF->ON dù thiet bi that KHONG doi (dung
        # nhu da gap). Luu lai gia tri VUA GHI + han "an toan" (grace) -
        # trong luc nay, NEU du lieu poll ve KHAC voi gia tri vua ghi thi
        # COI LA CU, BO QUA (khong de UI); het han ma van khac thi moi tin.
        self._pending_write_value = None   # None = khong co lenh ghi nao dang cho xac nhan
        self._pending_write_until = 0.0    # thoi diem (time.time()) het han grace
        self._PENDING_GRACE_SEC = 6.0      # > 1 chu ky poll (3s) + du du cho Local xep hang Lock

        # SUA: BO lbl_icon (icon emoji size lon) - tang font ten thiet bi
        # len 1 chut de bu lai khoang trong, giu vai tro "tieu de" chinh
        # cua o thiet bi, dung CHU IN HOA + dam theo dinh huong cong nghiep.
        lbl_name = QLabel(name.upper())
        lbl_name.setAlignment(Qt.AlignCenter)
        lbl_name.setWordWrap(True)
        lbl_name.setStyleSheet("font-weight:700; font-size:15px; letter-spacing:0.5px;")
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

    def _set_status(self, text, role=""):
        """Dat chu trang thai + mau (role) - thay cho kieu cu ghep icon
        emoji truoc chuoi (vd '⚠️ ...', '✅ ...'). role: 'status-ok'
        (xanh la), 'status-error' (do), 'status-warning' (cam), hoac ''
        (mac dinh, mau xam trung tinh)."""
        self.lbl_status.setProperty("role", role)
        self.lbl_status.setText(text.upper() if text else "")
        self.lbl_status.style().unpolish(self.lbl_status)
        self.lbl_status.style().polish(self.lbl_status)

    def set_locked(self, locked):
        """locked=True khi thiết bị này KHÔNG được nằm trong nhóm always_free
        và hệ thống đang ở AUTO -> khóa mờ nút, không cho bấm."""
        if self.always_free:
            self.btn.setEnabled(True)
            self._set_status("")
            return
        self.btn.setEnabled(not locked)
        self._set_status("Đang khóa (AUTO tự điều khiển)" if locked else "", "status-warning")

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
                self._set_status("Đang cho ăn...")
            elif self.lbl_status.text() == "ĐANG CHO ĂN...":
                self._set_status("Đã xong", "status-ok")
            return

        try:
            checked = int(float(value)) == 1
        except (ValueError, TypeError):
            return

        # SUA: THEM MOI - dang trong "grace period" sau 1 lenh ghi tay?
        if time.time() < self._pending_write_until:
            if checked == self._pending_write_value:
                # Du lieu poll VE DUNG voi cai vua ghi -> xac nhan xong,
                # tat grace som (khong can cho het 6s nua).
                self._pending_write_until = 0.0
            else:
                # Du lieu poll VE KHAC voi cai vua ghi -> RAT CO THE la du
                # lieu CU (doc truoc khi lenh ghi kip co hieu luc) - BO QUA,
                # KHONG de UI nhay sai trong luc cho xac nhan that.
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
        self._set_status("Đồng bộ từ xa")

    def _toggle(self, checked):
        value = 1 if checked else 0
        self.btn.setText("ON" if checked else "OFF")
        self.btn.setProperty("role", "toggleOn" if checked else "toggleOff")
        self.btn.style().unpolish(self.btn)
        self.btn.style().polish(self.btn)

        # SUA: THEM MOI - ghi nhan "vua ghi gia tri gi" + mo grace period,
        # de sync_from_remote() biet duong bo qua du lieu poll CU trong vai
        # giay toi (xem giai thich o __init__).
        self._pending_write_value = checked
        self._pending_write_until = time.time() + self._PENDING_GRACE_SEC

        self._set_status("Đang gửi lệnh...")
        if self.blynk_client is None:
            self._set_status("Chưa kết nối Blynk", "status-warning")
            return

        def on_done(ok):
            self._set_status("Đã gửi" if ok else "Gửi lỗi (kiểm tra mạng/token)",
                              "status-ok" if ok else "status-error")

        self.blynk_client.set_pin_async(self.pin, value, callback=on_done)

    def _pulse(self):
        """Nút dạng xung. Riêng V6 (Cho ăn) dùng chung FeedCoordinator với
        scheduler để không bao giờ bấm đè lên đúng lúc lịch tự động đang
        giữa chừng ghi V4 (xem feed_coordinator.py). Các nút xung khác (vd
        V19 - xác nhận đã sửa bơm nước) chỉ cần gửi thẳng giá trị 1, giống
        hệt cách nút Dừng khẩn cấp (V15) đang làm."""
        self._set_status("Đang gửi lệnh...")

        if self.pin == "V6":
            if self.feed_coordinator is None:
                self._set_status("Chưa khởi tạo FeedCoordinator", "status-warning")
                return

            def on_done_feed(ok, message):
                self._set_status(message, "status-ok" if ok else "status-error")

            self.feed_coordinator.trigger_feed_now_async(source_label="Bấm tay", on_status=on_done_feed)
            return

        if self.blynk_client is None:
            self._set_status("Chưa kết nối Blynk", "status-warning")
            return

        def on_done(ok):
            self._set_status("Đã gửi xác nhận" if ok else "Gửi lỗi (kiểm tra mạng/token)",
                              "status-ok" if ok else "status-error")

        self.blynk_client.set_pin_async(self.pin, 1, callback=on_done)


class EmergencyPanel(QGroupBox):
    """Khu vực nổi bật riêng, tách khỏi lưới 9 thiết bị thông thường - khớp
    với 2 nút tương đương trên app MOBILE (Blynk): 'Cho ăn ngay với X gram'
    (ghi V4 rồi xác nhận + bấm V6 qua FeedCoordinator) và 'DỪNG NGAY' (V15,
    dừng khẩn cấp giữa chừng lúc đang xả cám - xem thiết kế khóa V6/V15
    trong ChipChinh_ESP32S3.ino)."""

    def __init__(self, blynk_client, feed_coordinator, parent=None):
        super().__init__("CHO ĂN NHANH / DỪNG KHẨN CẤP", parent)
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

        lbl_stop_hint = QLabel("CHỈ DỪNG ĐƯỢC KHI ĐANG XẢ CÁM")
        lbl_stop_hint.setStyleSheet("color:#888; font-size:12px; font-weight:600;")
        lbl_stop_hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_top.addWidget(lbl_stop_hint, 1)
        
        root.addLayout(row_top)

        # --- HÀNG 2: 2 Nút bấm chính (căn bằng chiều cao & bo góc) ---
        row_btns = QHBoxLayout()
        row_btns.setSpacing(15)

        self.btn_feed_now = QPushButton("CHO ĂN NGAY")
        self.btn_feed_now.setFixedHeight(50)
        # SUA: THEM MOI - dung role="btnSuccess" chuan (xem ui/style.py)
        # thay vi tu che stylesheet rieng - dam bao dong nhat voi moi nut
        # "hanh dong tich cuc" khac trong toan app.
        self.btn_feed_now.setProperty("role", "btnSuccess")
        self.btn_feed_now.clicked.connect(self._on_feed_now)
        row_btns.addWidget(self.btn_feed_now, 1)

        self.btn_stop = QPushButton("DỪNG NGAY")
        self.btn_stop.setFixedHeight(50)
        # SUA: THEM MOI - dung role="btnDanger" chuan thay vi tu che.
        self.btn_stop.setProperty("role", "btnDanger")
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

    @staticmethod
    def _set_status_label(lbl, text, role=""):
        lbl.setProperty("role", role)
        lbl.setText(text.upper() if text else "")
        lbl.style().unpolish(lbl)
        lbl.style().polish(lbl)

    def _on_feed_now(self):
        gram = self.spin_gram.value()
        self._set_status_label(self.lbl_feed_status, "Đang gửi...")
        if self.feed_coordinator is None:
            self._set_status_label(self.lbl_feed_status, "Chưa khởi tạo FeedCoordinator", "status-warning")
            return

        def on_status(ok, message):
            self._set_status_label(self.lbl_feed_status, message, "status-ok" if ok else "status-error")

        self.feed_coordinator.trigger_feed_async(gram, source_label="Cho ăn nhanh (Manual)", on_status=on_status)

    def _on_stop(self):
        self._set_status_label(self.lbl_stop_status, "Đang gửi lệnh dừng...")
        if self.blynk_client is None:
            self._set_status_label(self.lbl_stop_status, "Chưa kết nối Blynk", "status-warning")
            return

        def on_done(ok):
            self._set_status_label(
                self.lbl_stop_status,
                "Đã gửi lệnh dừng khẩn cấp (V15)" if ok else "Gửi lỗi",
                "status-ok" if ok else "status-error",
            )

        self.blynk_client.set_pin_async("V15", 1, callback=on_done)


class SourceSwitch(QVBoxLayout):
    """Công tắc chọn NGUỒN điều khiển: CLOUD (Blynk, qua Internet) hoặc
    LOCAL (Web Server trên ESP32, qua LAN/mDNS - hoạt động cả khi MẤT
    Internet miễn còn WiFi/LAN). Đây là lựa chọn THỦ CÔNG của người dùng,
    KHÔNG tự động fallback - đổi qua connection_manager.set_mode(), mọi
    nút bấm khác trong tab (DeviceToggle, ModeSwitch AUTO/MANUAL,
    EmergencyPanel) đi qua CÙNG 1 blynk_client (ConnectionManager) nên tự
    động dùng đúng nguồn đang chọn mà không cần biết gì thêm.

    LƯU Ý: Local KHÔNG hỗ trợ cảm biến (V0-V3), Lịch hẹn/Ngưỡng (V16/V17),
    log cảnh báo (V18) - các tab khác (HOME cảm biến, ALARM, CHART, phần
    Lịch/Ngưỡng trong SETTING) sẽ KHÔNG cập nhật khi đang ở Local, đây là
    điều cần cảnh báo rõ cho người dùng ngay trên UI.

    SUA: DOI TU nut toggle (QPushButton) SANG QComboBox (dropdown) - theo
    dung bo cuc moi nguoi dung yeu cau (nhan tren, o chon ben duoi, dat
    canh EmergencyPanel thanh 2 cot thay vi choan het chieu ngang nhu
    truoc)."""

    def __init__(self, connection_manager):
        super().__init__()
        self.cm = connection_manager
        self.setSpacing(4)

        lbl_title = QLabel("NGUỒN ĐIỀU KHIỂN:")
        lbl_title.setStyleSheet("font-weight:700; font-size:13px; color:#555;")
        self.addWidget(lbl_title)

        self.combo_source = QComboBox()
        self.combo_source.addItem("CLOUD (INTERNET)", userData="cloud")
        self.combo_source.addItem("LOCAL (LAN)", userData="local")
        self.combo_source.setFixedHeight(34)
        self.combo_source.currentIndexChanged.connect(self._on_combo_changed)
        self.addWidget(self.combo_source)

        self.lbl_status = QLabel(
            "Đang dùng Cloud - Lịch hẹn/Ngưỡng/Cảm biến/Cảnh báo hoạt động đầy đủ."
        )
        self.lbl_status.setStyleSheet("color:#888; font-size:12px;")
        self.lbl_status.setWordWrap(True)
        self.addWidget(self.lbl_status)

        if self.cm is not None:
            self.cm.on_mode_changed(self._on_cm_mode_changed)

    def _on_combo_changed(self, index):
        mode = self.combo_source.itemData(index)

        if self.cm is None:
            self.lbl_status.setProperty("role", "status-warning")
            self.lbl_status.setText("CHƯA CÓ KẾT NỐI NÀO ĐƯỢC CẤU HÌNH")
            self.lbl_status.style().unpolish(self.lbl_status)
            self.lbl_status.style().polish(self.lbl_status)
            return

        self.cm.set_mode(mode)
        if mode == "local":
            self.lbl_status.setProperty("role", "status-warning")
            self.lbl_status.setText(
                "Đang dùng LOCAL (LAN) - chỉ điều khiển thiết bị hoạt động; "
                "Cảm biến/Lịch hẹn/Ngưỡng/Cảnh báo sẽ KHÔNG cập nhật cho tới khi chuyển lại Cloud."
            )
        else:
            self.lbl_status.setProperty("role", "")
            self.lbl_status.setText("Đang dùng Cloud - Lịch hẹn/Ngưỡng/Cảm biến/Cảnh báo hoạt động đầy đủ.")
        self.lbl_status.style().unpolish(self.lbl_status)
        self.lbl_status.style().polish(self.lbl_status)

    def _on_cm_mode_changed(self, mode):
        # Phòng trường hợp mode bị đổi từ nơi khác ngoài chính combo này -
        # chỉ cập nhật giao diện, KHÔNG gọi lại set_mode() (tránh vòng lặp).
        idx = self.combo_source.findData(mode)
        if idx == -1 or self.combo_source.currentIndex() == idx:
            return
        self.combo_source.blockSignals(True)
        self.combo_source.setCurrentIndex(idx)
        self.combo_source.blockSignals(False)


class ModeSwitchSignal(QObject):
    mode_changed = pyqtSignal(bool)  # True = đang AUTO


class ModeSwitch(QVBoxLayout):
    """Công tắc Chế độ AUTO/MANUAL — ghi xuống V5, khớp BLYNK_WRITE(V5)
    trong firmware.

    SUA: DOI TU nut toggle SANG QComboBox - dong bo kieu voi SourceSwitch,
    ca 2 dat canh nhau trong 1 khung ben phai EmergencyPanel."""

    def __init__(self, blynk_client):
        super().__init__()
        self.blynk_client = blynk_client
        self.signals = ModeSwitchSignal()
        self.setSpacing(4)

        lbl_title = QLabel("CHẾ ĐỘ HỆ THỐNG:")
        lbl_title.setStyleSheet("font-weight:700; font-size:13px; color:#555;")
        self.addWidget(lbl_title)

        self.combo_mode = QComboBox()
        self.combo_mode.addItem("MANUAL (TAY)", userData=0)
        self.combo_mode.addItem("AUTO (TỰ ĐỘNG)", userData=1)
        self.combo_mode.setFixedHeight(34)
        self.combo_mode.currentIndexChanged.connect(self._on_combo_changed)
        self.addWidget(self.combo_mode)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#888; font-size:12px;")
        self.addWidget(self.lbl_status)

    def _on_combo_changed(self, index):
        value = self.combo_mode.itemData(index)
        checked = value == 1

        self.signals.mode_changed.emit(checked)  # checked=True nghĩa là đang AUTO

        if self.blynk_client is None:
            self.lbl_status.setProperty("role", "status-warning")
            self.lbl_status.setText("CHƯA KẾT NỐI BLYNK")
            self.lbl_status.style().unpolish(self.lbl_status)
            self.lbl_status.style().polish(self.lbl_status)
            return

        def on_done(ok):
            self.lbl_status.setProperty("role", "status-ok" if ok else "status-error")
            self.lbl_status.setText("ĐÃ CHUYỂN CHẾ ĐỘ" if ok else "GỬI LỖI")
            self.lbl_status.style().unpolish(self.lbl_status)
            self.lbl_status.style().polish(self.lbl_status)

        self.blynk_client.set_pin_async("V5", value, callback=on_done)

    def sync_from_remote(self, value):
        """Cập nhật combo AUTO/MANUAL theo giá trị ĐỌC ĐƯỢC từ Blynk (do
        app mobile bấm) - KHÔNG gửi lại V5, chỉ đổi giao diện + báo cho
        ManualTab qua signal để khóa/mở khóa đúng các nút liên quan."""
        try:
            is_auto = int(float(value)) == 1
        except (ValueError, TypeError):
            return

        idx = 1 if is_auto else 0
        if self.combo_mode.currentIndex() == idx:
            return

        self.combo_mode.blockSignals(True)
        self.combo_mode.setCurrentIndex(idx)
        self.combo_mode.blockSignals(False)
        self.lbl_status.setText("Đồng bộ...")
        self.signals.mode_changed.emit(is_auto)


class ManualTab(QWidget):
    def __init__(self, blynk_client=None, feed_coordinator=None,
                 connection_manager=None, parent=None):
        super().__init__(parent)
        # SUA: THEM MOI - blynk_client o day GIO LA ConnectionManager (boc
        # ca Cloud lan Local), truyen thang xuong DeviceToggle/ModeSwitch/
        # EmergencyPanel nhu cu (chung khong can biet gi thay doi, van goi
        # set_pin_async()/get_pin() nhu truoc). connection_manager la THAM
        # SO RIENG chi de dung cho SourceSwitch (goi set_mode()/
        # on_mode_changed()) - mac dinh lay LUON blynk_client neu no co san
        # 2 ham nay (duck-typing), tranh phai truyen 2 lan cung 1 doi tuong
        # o main.py.
        self.blynk_client = blynk_client
        self.feed_coordinator = feed_coordinator
        if connection_manager is not None:
            self.connection_manager = connection_manager
        elif hasattr(blynk_client, "set_mode") and hasattr(blynk_client, "on_mode_changed"):
            self.connection_manager = blynk_client
        else:
            self.connection_manager = None
        self._build_ui()
        # SUA: THEM MOI - dong bo nhan "NGUON" tren thanh trang thai mong
        # theo dung mode hien tai cua ConnectionManager, va tu cap nhat moi
        # khi mode doi (Observer, giong cach SourceSwitch da lam).
        if self.connection_manager is not None:
            self.thin_status.set_source(self.connection_manager.mode)
            self.connection_manager.on_mode_changed(self.thin_status.set_source)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # SUA: THEM MOI - thanh trang thai mong, lap lai o MOI tab (xem
        # ui/thin_status_bar.py) - dat NGAY DAU, TRUOC ca noi dung chinh,
        # de nguoi dung luon thay duoc nhiet do/do am/nguon dang chon/
        # trang thai Cloud du dang o tab nao.
        self.thin_status = ThinStatusBar()
        root.addWidget(self.thin_status)

        content = QVBoxLayout()
        content.setContentsMargins(20, 16, 20, 20)
        root.addLayout(content)

        # SUA: BO CUC LAI theo yeu cau - 2 COT ngang thay vi 3 khoi xep
        # chong doc nhu truoc: TRAI la EmergencyPanel (Cho an nhanh/Dung
        # khan cap, da la 1 QGroupBox rieng), PHAI la 1 khung gom 2 combo
        # (Nguon dieu khien + Che do he thong) xep doc trong do.
        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        self.emergency_panel = EmergencyPanel(self.blynk_client, self.feed_coordinator)
        top_row.addWidget(self.emergency_panel, 3)

        gb_config = QGroupBox()
        config_lay = QVBoxLayout(gb_config)
        config_lay.setSpacing(14)

        self.source_switch = SourceSwitch(self.connection_manager)
        config_lay.addLayout(self.source_switch)

        self.mode_switch = ModeSwitch(self.blynk_client)
        self.mode_switch.signals.mode_changed.connect(self._on_mode_changed)
        config_lay.addLayout(self.mode_switch)
        config_lay.addStretch(1)

        top_row.addWidget(gb_config, 2)
        content.addLayout(top_row)

        note = QLabel(
            "Khi đang AUTO: chỉ Đèn / Tắm / Rửa chuồng / Mở khóa bơm nước bấm tay "
            "được (4 mục này AUTO không tự điều khiển; riêng Cho ăn luôn dùng qua khu "
            "'Cho ăn nhanh' phía trên). Các thiết bị còn lại (Quạt thổi, Quạt hút, "
            "Sưởi, Bơm máng nước, Phun sương) sẽ tự khóa mờ vì đang do AUTO điều khiển "
            "theo cảm biến. Chuyển sang MANUAL để mở khóa toàn bộ."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#555; font-size:14px; padding:2px 0 10px 0;")
        content.addWidget(note)

        grid = QGridLayout()
        grid.setSpacing(18)

        # SUA: gom luoi thiet bi vao 1 khung (QGroupBox) rieng cho gon gang,
        # thay vi tha noi truc tiep tren tab - dung tinh than "gom vao khung
        # chuyen dung" theo yeu cau.
        gb_devices = QGroupBox("Điều khiển thiết bị")
        gb_devices_lay = QVBoxLayout(gb_devices)
        gb_devices_lay.addLayout(grid)
        content.addWidget(gb_devices)

        self.toggles = {}
        for i, (name, pin, is_pulse, always_free, pulse_label) in enumerate(DEVICES):
            r, c = divmod(i, 3)
            toggle = DeviceToggle(name, pin, is_pulse, always_free,
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
        content.addStretch(1)

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
        # SUA: THEM MOI - cap nhat thanh trang thai mong (nhiet do/do am/
        # trang thai Cloud) - lap lai dung o day nhu moi tab khac.
        self.thin_status.update_from_blynk(data)

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