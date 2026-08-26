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

import os
import json
import time
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QGroupBox, QFrame
)

from ui.camera_zone import CameraZoneWidget
from ui.thin_status_bar import ThinStatusBar

# SUA: THEM MOI - luu "Thong ke hom nay" ra file JSON, cung quy uoc voi
# alarm_tab.py/setting_tab.py (_BASE_DIR = thu muc goc project). Truoc day
# _stat_counts CHI o trong RAM -> tat app la mat het, phai bam lai tu 0.
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY_STATS_PATH = os.path.join(_BASE_DIR, "daily_stats.json")


# ----------------------------------------------------------------------
def sensor_card(label, unit=""):
    """1 ô cảm biến kiểu hộp: tên nhỏ phía trên, giá trị to phía dưới -
    giống đúng bố cục 4 ô 'Cảm biến môi trường' ở ảnh tham khảo.
    SUA: BO tham so icon (khong con dung emoji) theo dinh huong giao dien
    "khong icon, chi chu + mau" - CHU IN HOA cho ten cam bien, font so
    monospace cho gia tri de cac chu so THANG HANG voi nhau."""
    frame = QFrame()
    frame.setStyleSheet(
        "QFrame { background:#fbf8ec; }"
    )
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(10, 8, 10, 8)
    lay.setSpacing(2)

    top = QHBoxLayout()
    lbl_name = QLabel(label.upper())
    lbl_name.setStyleSheet("font-size:13px; color:#666; font-weight:600; letter-spacing:0.5px;")
    top.addWidget(lbl_name)
    top.addStretch(1)
    lay.addLayout(top)

    row_val = QHBoxLayout()
    lbl_val = QLabel("--")
    lbl_val.setStyleSheet('font-size:25px; font-weight:800; color:#1857a4; font-family:"Consolas", monospace;')
    row_val.addWidget(lbl_val)
    if unit:
        lbl_unit = QLabel(unit)
        lbl_unit.setStyleSheet("color:#888; font-size:15px; padding-left:3px;")
        row_val.addWidget(lbl_unit)
    row_val.addStretch(1)
    lay.addLayout(row_val)

    return frame, lbl_val


def device_status_card(label):
    """1 ô trong khối 'Cơ cấu chấp hành' - tên + trạng thái ON/OFF (CHỈ
    HIỂN THỊ, không phải nút bấm - muốn bật/tắt tay thì sang tab MANUAL).
    SUA: BO tham so icon theo dinh huong "khong icon, chi chu + mau"."""
    frame = QFrame()
    frame.setStyleSheet(
        "QFrame { background:#fbf8ec; }"
    )
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(10, 10, 10, 10)
    lay.setSpacing(4)

    top = QHBoxLayout()
    lbl_name = QLabel(label.upper())
    lbl_name.setStyleSheet("font-weight:700; font-size:14px; letter-spacing:0.5px;")
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


# (nhãn, virtual_pin) — 8 relay, KHÔNG gồm "Cho ăn" (V6 là nút xung,
# không phải trạng thái bật/tắt ổn định nên không hợp để hiện ON/OFF ở đây)
# SUA: BO HAN truong icon (truoc day la phan tu dau tien cua tuple) theo
# dinh huong giao dien "khong icon, chi chu + mau".
# SUA: THEM MOI - dong bo TEN HIEN THI voi DEVICES trong ui/manual_tab.py -
# truoc day HOME goi "Den Suoi"/"Bom San"/"Bom Tam"/"Bom Phun Suong" trong
# khi MANUAL goi "Suoi"/"Rua Chuong"/"Tam"/"Phun Suong" cho CUNG 1 pin,
# khien nguoi dung phai tu suy luan 2 ten co phai la 1 thiet bi khong.
ACTUATOR_ROWS = [
    ("Quạt Thổi", "V7"),
    ("Quạt Hút", "V8"),
    ("Đèn", "V9"),
    ("Sưởi", "V10"),
    ("Bơm Máng", "V11"),
    ("Rửa Chuồng", "V12"),
    ("Tắm", "V13"),
    ("Phun Sương", "V14"),
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
        # SUA: THEM MOI - doc lai thong ke DA LUU tu lan chay truoc (neu
        # dung ngay hom nay), NGAY SAU _build_ui() de co the cap nhat label
        # hien thi luon, khong phai cho toi vong poll dau tien (3s) moi
        # thay so cu hien ra.
        self._doc_thong_ke_da_luu()
        self._hien_thi_thong_ke()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

    def attach_scheduler(self, scheduler):
        self.scheduler = scheduler

    # ------------------------------------------------------------------
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # SUA: THEM MOI - thanh trang thai mong, lap lai o MOI tab (xem
        # ui/thin_status_bar.py) - HOME von da co sidebar chi tiet rieng,
        # nhung van them thanh nay o tren cung de GIU DUNG 1 ngon ngu thi
        # giac dong nhat xuyen suot cac tab, khong rieng gi HOME khac biet.
        self.thin_status = ThinStatusBar()
        outer.addWidget(self.thin_status)

        root = QVBoxLayout()
        root.setContentsMargins(14, 12, 14, 14)
        outer.addLayout(root)

        top_row = QHBoxLayout()
        root.addLayout(top_row, 3)

        # ================= CỘT TRÁI: Cảm biến môi trường + Lịch trình tiếp theo =================
        left = QVBoxLayout()
        top_row.addLayout(left, 2)

        gb_sensor = QGroupBox("Cảm biến môi trường")
        sl = QGridLayout(gb_sensor)
        sl.setSpacing(10)

        card, self.lbl_temp = sensor_card("Nhiệt độ", "°C")
        sl.addWidget(card, 0, 0)
        card, self.lbl_cam = sensor_card("Cám tồn", "g")
        sl.addWidget(card, 0, 1)
        card, self.lbl_humi = sensor_card("Độ ẩm", "%")
        sl.addWidget(card, 1, 0)
        card, self.lbl_water = sensor_card("Mực nước")
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

        # SUA: THEM MOI - dong goi y hanh dong, CHI hien khi ESP32 mat Cloud,
        # nhac nguoi dung qua tab MANUAL chon nguon LOCAL de van dieu khien
        # duoc (thay vi phai tu doan trang thai roi tu di tim).
        self.lbl_hint = QLabel("")
        self.lbl_hint.setStyleSheet("color:#d18b1c; font-size:12px;")
        self.lbl_hint.setWordWrap(True)
        self.lbl_hint.setVisible(False)
        ol.addWidget(self.lbl_hint, 3, 0, 1, 2)
        left.addWidget(gb_over)

        gb_stat = QGroupBox("Thống kê hôm nay")
        stl = QGridLayout(gb_stat)
        stl.addWidget(QLabel("LẦN CHO ĂN"), 0, 0)
        self.lbl_stat_an = QLabel("0")
        self.lbl_stat_an.setStyleSheet('font-weight:700; font-family:"Consolas", monospace;')
        stl.addWidget(self.lbl_stat_an, 0, 1)
        stl.addWidget(QLabel("LẦN TẮM"), 1, 0)
        self.lbl_stat_tam = QLabel("0")
        self.lbl_stat_tam.setStyleSheet('font-weight:700; font-family:"Consolas", monospace;')
        stl.addWidget(self.lbl_stat_tam, 1, 1)
        stl.addWidget(QLabel("LẦN RỬA CHUỒNG"), 2, 0)
        self.lbl_stat_vs = QLabel("0")
        self.lbl_stat_vs.setStyleSheet('font-weight:700; font-family:"Consolas", monospace;')
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
        for i, (name, pin) in enumerate(ACTUATOR_ROWS):
            r, c = divmod(i, 4)
            card, lbl = device_status_card(name)
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
        # SUA: THEM MOI - cap nhat thanh trang thai mong (dong bo voi moi
        # tab khac, xem ui/thin_status_bar.py).
        self.thin_status.update_from_blynk(data)

        temp = data.get("temp")
        humi = data.get("humi")
        cam = data.get("cam")
        water = data.get("water")
        mode = data.get("mode")
        devices = data.get("devices", {})
        device_online = data.get("device_online")

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

        # SUA: BUG THAT tung co san TRUOC KHI sua hom nay - code CU dat
        # "Binh thuong" + lam moi _last_data_time VO DIEU KIEN moi lan ham
        # nay duoc goi, KE CA khi raw du lieu poll ve HOAN TOAN RONG (vd PC
        # mat mang toi Blynk Cloud, get_pins() tra ve {}) - khien co che
        # "MAT KET NOI DU LIEU" (timeout 15s o _tick() ben duoi) THUC TE
        # KHONG BAO GIO kich hoat duoc, vi _last_data_time luon duoc "lam
        # moi gia tao" moi chu ky du poll THAT SU co thanh cong hay khong.
        # Gio CHI coi la "co nhan duoc du lieu that" khi co it nhat 1 trong
        # cac gia tri co ban (temp/humi/mode) khac None.
        co_du_lieu_that = any(v is not None for v in (temp, humi, mode))
        if not co_du_lieu_that:
            self._cap_nhat_thong_ke(devices)
            return  # KHONG cham _last_data_time - de _tick() tu phat hien mat ket noi that su

        # SUA: THEM MOI - dung DUNG trang thai online/offline THAT SU cua
        # ESP32 (tu Blynk isHardwareConnected API), thay vi CHI suy doan
        # qua "co nhan duoc phan hoi khong". Ly do can lam rieng: doc pin
        # (get_pins) van "thanh cong" BINH THUONG du ESP32 da offline tu
        # lau, vi Blynk Cloud tra ve GIA TRI CACHE CUOI CUNG chu khong bao
        # loi - _tick() (dua vao _last_data_time) KHONG the phat hien duoc
        # truong hop nay, vi day la loi o PHIA ESP32 chu khong phai APP mat
        # ket noi toi Blynk Cloud. device_online=None nghia la KHONG hoi
        # duoc rieng cau nay (loi mang luc goi isHardwareConnected) - van
        # coi la binh thuong vi it nhat pin van doc duoc.
        # SUA: THEM MOI - device_online GIO LUON LA trang thai CLOUD THAT SU
        # cua ESP32 (BlynkPoller da doi sang dung cloud_client RIENG, xem
        # blynk_client.py), KHONG con phu thuoc nguon dang chon o tab
        # MANUAL nua. Nghia la: du ban dang dieu khien qua Local, dong nay
        # VAN bao dung neu ESP32 that su da mat Cloud/Internet - day chinh
        # la tin hieu de nguoi dung biet CAN qua tab MANUAL chon Local moi
        # dieu khien duoc (neu chua chon san).
        # SUA: SUA LOI - truoc day dieu kien la "if device_online is False"
        # (chi rieng False), khien gia tri None BI COI NHU True (hien thi
        # "DA KET NOI CLOUD" - XANH - SAI). None xay ra khi CHINH MAY TINH
        # KHONG GOI DUOC toi Blynk Cloud de hoi isHardwareConnected (vd
        # test bang hotspot dien thoai: tat Data la CA may tinh LAN ESP32
        # deu mat Internet cung luc, vi dung chung 1 duong Internet duy
        # nhat) - luc do KHONG PHAN BIET DUOC "ESP32 that su offline" hay
        # "may tinh tu no khong hoi duoc", nhung VOI NGUOI DUNG thi 2
        # truong hop nay CO KET QUA GIONG HET NHAU: Cloud KHONG DUNG DUOC
        # luc nay, BAT KE ly do gi - nen phai coi None GIONG False, KHONG
        # duoc coi la "binh thuong".
        if device_online is not True:
            self.dot_system.set_on(False)
            if device_online is False:
                self.lbl_state.setText("ESP32 MẤT KẾT NỐI CLOUD")
            else:  # None - khong hoi duoc, rat co the may tinh cung dang mat Internet
                self.lbl_state.setText("KHÔNG KIỂM TRA ĐƯỢC CLOUD (có thể máy tính cũng mất Internet)")
            self.lbl_state.setStyleSheet("color:#d13c3c; font-weight:700;")
            self.lbl_hint.setText(
                "→ Vẫn còn WiFi/LAN thì qua tab MANUAL, chọn nguồn LOCAL để tiếp tục điều khiển."
            )
            self.lbl_hint.setVisible(True)
        else:
            self.dot_system.set_on(True)
            self.lbl_state.setText("ESP32 ĐÃ KẾT NỐI CLOUD")
            self.lbl_state.setStyleSheet("color:#2fae4e; font-weight:700;")
            self.lbl_hint.setVisible(False)
        self._last_data_time = time.time()

        self._cap_nhat_thong_ke(devices)

    def _cap_nhat_thong_ke(self, devices: dict):
        today = time.strftime("%Y-%m-%d")
        if self._stat_date != today:
            self._stat_date = today
            self._stat_counts = {"cho_an": 0, "tam": 0, "rua_chuong": 0}
            self._prev_devices = {}

        pin_map = {"V6": "cho_an", "V13": "tam", "V12": "rua_chuong"}
        co_thay_doi = False
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
                co_thay_doi = True
            self._prev_devices[pin] = cur

        self._hien_thi_thong_ke()
        # SUA: THEM MOI - CHI ghi file khi THAT SU co thay doi (tang so dem),
        # tranh ghi o dia lien tuc moi 3s (chu ky poll) mot cach vo ich.
        if co_thay_doi:
            self._luu_thong_ke()

    def _hien_thi_thong_ke(self):
        self.lbl_stat_an.setText(str(self._stat_counts["cho_an"]))
        self.lbl_stat_tam.setText(str(self._stat_counts["tam"]))
        self.lbl_stat_vs.setText(str(self._stat_counts["rua_chuong"]))

    def _doc_thong_ke_da_luu(self):
        """SUA: THEM MOI - doc lai file daily_stats.json (neu co) luc mo
        app. CHI ap dung so dem neu dung NGAY HOM NAY luu (qua ngay moi thi
        thoi diem doi ngay trong _cap_nhat_thong_ke() se tu reset ve 0, day
        la hanh vi DUNG - khong phai bug)."""
        try:
            with open(DAILY_STATS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") == time.strftime("%Y-%m-%d"):
                self._stat_date = data["date"]
                self._stat_counts = {
                    "cho_an": int(data.get("cho_an", 0)),
                    "tam": int(data.get("tam", 0)),
                    "rua_chuong": int(data.get("rua_chuong", 0)),
                }
            # Neu file luu tu ngay KHAC hom nay -> bo qua, giu nguyen mac
            # dinh 0 (_stat_date=None se tu kich hoat reset dung luc o
            # _cap_nhat_thong_ke() khi co du lieu poll dau tien).
        except FileNotFoundError:
            pass  # Chua tung luu lan nao - binh thuong, giu mac dinh 0
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            print(f"[HomeTab] File daily_stats.json bi loi/hong, bo qua: {e}")

    def _luu_thong_ke(self):
        """SUA: THEM MOI - ghi thong ke hien tai xuong dia, de tat/mo lai
        app trong CUNG 1 ngay van giu dung so dem, khong ve 0."""
        try:
            with open(DAILY_STATS_PATH, "w", encoding="utf-8") as f:
                json.dump({"date": self._stat_date, **self._stat_counts}, f, ensure_ascii=False, indent=2)
        except OSError as e:
            print(f"[HomeTab] Khong ghi duoc daily_stats.json: {e}")

    # ------------------------------------------------------------------
    def _tick(self):
        if self.scheduler is not None:
            self.lbl_next_schedule.setText(self.scheduler.next_upcoming())

        if self._last_data_time is None:
            return
        if time.time() - self._last_data_time > 15:
            self.dot_system.set_on(False)
            self.lbl_state.setText("MẤT KẾT NỐI DỮ LIỆU")
            self.lbl_state.setStyleSheet("color:#c0392b; font-weight:700;")
            # SUA: THEM MOI - day la mat ket noi TOI NGUON DANG CHON (co
            # the Cloud hoac Local, tuy nguoi dung dang dieu khien qua dau)
            # - KHAC voi "ESP32 MAT KET NOI CLOUD" (luon cu the la Cloud) o
            # update_from_blynk(), nen an goi y "chuyen sang Local" o day
            # de tranh nham lan (vi neu dang O Local roi ma van mat thi goi
            # y do khong con dung nua).
            self.lbl_hint.setVisible(False)