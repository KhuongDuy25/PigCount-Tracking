# -*- coding: utf-8 -*-
"""
main.py — Phần mềm giám sát & điều khiển TRANG TRẠI THÔNG MINH
================================================================
Mô phỏng lại giao diện màn hình HMI (WeinView) gốc với 6 tab điều hướng:
  HOME | SCREEN | MANUAL | SETTING | ALARM | CHART

- HOME:    dashboard tổng quan (nhiệt độ, độ ẩm, lịch trình, thống kê,
           trạng thái hệ thống, tổng quan vận hành) + camera giám sát máng
           ăn, vẽ vùng (zone), YOLO tracking + gán ID theo màu lưng.
- SCREEN:  giữ nguyên bố cục màn hình giám sát cảm biến / đèn báo / thiết bị.
- MANUAL:  giữ nguyên lưới nút bật/tắt thiết bị bằng tay.
- SETTING: giữ nguyên cấu hình môi trường, động cơ cho ăn, lịch hoạt động, chiếu sáng.
- ALARM:   nhận cảnh báo THẬT từ ESP32 qua V18 (polling) + kết quả đồng bộ
           lịch/ngưỡng - không còn demo cố định.
- CHART:   biểu đồ nhiệt độ/độ ẩm.

Cách chạy:
    pip install PyQt5 opencv-python numpy matplotlib ultralytics requests
    python main.py
"""

import sys
from PyQt5.QtCore import Qt, QTimer, QDateTime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QButtonGroup
)

from ui.style import APP_STYLESHEET
from ui.home_tab import HomeTab
from ui.manual_tab import ManualTab
from ui.setting_tab import SettingTab
from ui.alarm_tab import AlarmTab
from ui.chart_tab import ChartTab

import config
from blynk_client import BlynkClient, BlynkPoller
from local_client import LocalClient
from connection_manager import ConnectionManager
from scheduler import ScheduleSyncer
from feed_coordinator import FeedCoordinator


# SUA: BO icon emoji (truoc day moi item la (ten, icon)) - theo dinh
# huong giao dien "khong icon, chi chu + mau", nut nav gio CHI CON chu.
NAV_ITEMS = ["HOME", "MANUAL", "SETTING", "ALARM", "CHART"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HỆ THỐNG TRANG TRẠI THÔNG MINH")
        self.resize(1200, 720)

        central = QWidget()
        central.setObjectName("centralArea")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---------------- HEADER ----------------
        header = QWidget()
        header.setObjectName("headerBar")
        header.setFixedHeight(48)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)

        title = QLabel("HỆ THỐNG TRANG TRẠI THÔNG MINH")
        title.setObjectName("headerTitle")
        hl.addWidget(title)
        hl.addStretch(1)

        self.lbl_clock = QLabel()
        self.lbl_clock.setObjectName("headerClock")
        hl.addWidget(self.lbl_clock)
        root.addWidget(header)

        # ---------------- KẾT NỐI BLYNK CLOUD + LOCAL (LAN) + SCHEDULER ----------------
        # SUA: THEM MOI - gio co 2 nguon dieu khien:
        #   - self.cloud_client (BlynkClient): qua Internet, nhu truoc day.
        #   - self.local_client (LocalClient): qua LAN/mDNS, goi thang Web
        #     Server local tren ESP32 (chi ho tro 13 Vpin cua tab MANUAL).
        # self.blynk_client (ConnectionManager) BOC CA 2, giu dung ten bien
        # "blynk_client" + dung chu ky ham nhu cu de cac cho khac (ManualTab,
        # FeedCoordinator, BlynkPoller) KHONG PHAI SUA GI - chi doi doi
        # tuong duoc truyen vao. Nguoi dung chon Cloud/Local qua cong tac
        # tren tab MANUAL (xem SourceSwitch trong ui/manual_tab.py).
        self.cloud_client = BlynkClient(config.BLYNK_AUTH_TOKEN, timeout=config.BLYNK_HTTP_TIMEOUT)
        self.local_client = LocalClient(config.LOCAL_SERVER_HOST, timeout=config.LOCAL_HTTP_TIMEOUT)
        self.blynk_client = ConnectionManager(self.cloud_client, self.local_client, mode="cloud")

        # FeedCoordinator: dùng CHUNG cho cả nút "CHO ĂN" bấm tay (tab MANUAL)
        # lẫn nút "CHO ĂN NGAY" trong khu vực khẩn cấp - đảm bảo không bao
        # giờ có 2 lệnh cho ăn chạy chồng nhau, và khối lượng luôn được xác
        # nhận thật trước khi bấm xả (xem feed_coordinator.py). Lịch tự động
        # (V16) do chính ESP32 tự kích hoạt, không đi qua FeedCoordinator.
        # Dùng self.blynk_client (ConnectionManager) để Cho ăn nhanh cũng
        # hoạt động được qua Local khi người dùng chọn - V4/V6 nằm trong
        # danh sách pin mà Web Server local hỗ trợ.
        self.feed_coordinator = FeedCoordinator(self.blynk_client)

        # ---------------- STACK NỘI DUNG ----------------
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.home_tab = HomeTab()
        # SUA: THEM MOI - truyen them connection_manager=self.blynk_client
        # TUONG MINH (du ManualTab co the tu suy ra qua duck-typing) de tab
        # MANUAL ve duoc cong tac chon nguon Cloud/Local (SourceSwitch).
        self.manual_tab = ManualTab(
            blynk_client=self.blynk_client,
            feed_coordinator=self.feed_coordinator,
            connection_manager=self.blynk_client,
        )
        self.setting_tab = SettingTab()
        self.alarm_tab = AlarmTab()
        self.chart_tab = ChartTab()

        for w in (self.home_tab, self.manual_tab,
                  self.setting_tab, self.alarm_tab, self.chart_tab):
            self.stack.addWidget(w)

        # ScheduleSyncer: KHONG con tu dem gio o phia Python nua (cach cu phu
        # thuoc may tinh phai luon bat). Gio chi dong goi lich/nguong moi
        # truong tu SettingTab thanh JSON, gui XUONG ESP32 qua V16/V17 moi
        # khi nguoi dung sua xong (bam BACK) - ESP32 tu luu NVS + tu chay
        # bang NTP, doc lap hoan toan voi Python (xem scheduler.py).
        # SUA: THEM MOI - Lich hen gio (V16) / Nguong moi truong (V17) BAT
        # BUOC di THANG qua Cloud (self.cloud_client), KHONG qua
        # ConnectionManager - vi Web Server local KHONG co route cho 2 pin
        # nay (ESP32 chi doc duoc qua BLYNK_WRITE khi Cloud gui xuong). Neu
        # dung self.blynk_client o day, luc nguoi dung dang chon "Local" o
        # tab MANUAL thi luu Lich/Nguong se AM THAM that bai ma khong ro
        # ly do - nen co y giu rieng bien nay, khong phu thuoc lua chon
        # Cloud/Local cua nguoi dung.
        self.scheduler = ScheduleSyncer(
            setting_tab=self.setting_tab,
            blynk_client=self.cloud_client,
        )
        self.scheduler.sync_status.connect(self._on_schedule_fired)
        self.setting_tab.schedule_saved.connect(self.scheduler.push_schedule)
        self.setting_tab.env_saved.connect(self.scheduler.push_env)
        self.home_tab.attach_scheduler(self.scheduler)

        # ---------------- ĐỒNG BỘ 2 CHIỀU (BlynkPoller) ----------------
        # Truoc day chi co 1 chieu Python -> Blynk (bam nut Python thi ESP32
        # doi). Gio them chieu nguoc lai: bam nut tren app MOBILE (hoac AUTO
        # tu dieu khien tren firmware) cung se lam giao dien Python cap nhat
        # dung theo, khong bi "noi doi" hien thi sai trang thai thuc te.
        self._last_alarm_msg = None  # SUA: THEM MOI - theo doi noi dung V18 lan truoc de chi ghi khi THAY DOI
        self._dang_canh_bao_manual_vuot_nguong = False  # SUA: THEM MOI - co edge-trigger cho canh bao MANUAL+vuot nguong
        # SUA: THEM MOI - dem so canh bao CHUA XEM, de hien "ALARM (3)" +
        # doi mau do tren nut nav ngay ca khi dang o tab khac - khong con
        # phai bam vao tab ALARM moi biet co canh bao moi.
        self._so_canh_bao_chua_xem = 0
        # SUA: THEM MOI - Poller dung self.blynk_client (ConnectionManager),
        # KHONG phai self.cloud_client truc tiep - de khi nguoi dung chuyen
        # sang "Local" o tab MANUAL, vong polling nay TU DONG doi theo (doc
        # qua LAN thay vi Cloud) ma khong can khoi tao lai Poller. Cac pin
        # Local khong ho tro (cam bien V0-V3, canh bao V18) se tra ve None -
        # xem ghi chu trong connection_manager.py.
        # SUA: THEM MOI - truyen them cloud_client=self.cloud_client (RIENG,
        # KHAC voi self.blynk_client la ConnectionManager) - de Poller LUON
        # LUON kiem tra dung trang thai CLOUD THAT SU cua ESP32 (hien thi o
        # tab HOME), BAT KE nguoi dung dang chon Local hay Cloud de dieu
        # khien o tab MANUAL. Neu khong co dong nay, luc dang o Local thi
        # tab HOME se hien "ESP32 online" chi vi con LAN, du that ra ESP32
        # da mat Internet/Cloud tu lau - gay hieu nham dung nhu ban da hoi.
        self.blynk_poller = BlynkPoller(
            self.blynk_client,
            interval_sec=config.BLYNK_POLL_INTERVAL_SEC,
            cloud_client=self.cloud_client,
        )
        self.blynk_poller.data_updated.connect(self.home_tab.update_from_blynk)
        self.blynk_poller.data_updated.connect(self.manual_tab.sync_from_blynk)
        self.blynk_poller.data_updated.connect(self.chart_tab.update_from_blynk)
        # SUA: THEM MOI - noi them setting_tab/alarm_tab de thanh trang
        # thai mong (ThinStatusBar) cua 2 tab nay cung duoc cap nhat nhiet
        # do/do am/trang thai Cloud - truoc day 2 tab nay KHONG nhan duoc
        # data_updated nen thanh trang thai se dung im mai o "--".
        self.blynk_poller.data_updated.connect(self.setting_tab.update_from_blynk)
        self.blynk_poller.data_updated.connect(self.alarm_tab.update_from_blynk)
        # SUA: THEM MOI - nối tọa độ từ camera (tab HOME) sang tab CHART để vẽ
        # heatmap/đường đi di chuyển thật của từng ID lợn.
        self.home_tab.camera_widget.position_updated.connect(self.chart_tab.record_positions)
        self.blynk_poller.data_updated.connect(self._on_blynk_alarm)
        self.blynk_poller.start()

        # SUA: THEM MOI - dong bo nhan "NGUON" tren THANH TRANG THAI MONG
        # cua CA 4 tab khong tu cam connection_manager (Home/Setting/Alarm/
        # Chart) - ManualTab da tu lam viec nay rieng (co SourceSwitch can
        # connection_manager that su), 4 tab con lai chi can hien THEO
        # DUNG mode hien tai, khong can tu doi duoc.
        def _dong_bo_nguon_cho_thin_status(mode):
            for tab in (self.home_tab, self.setting_tab, self.alarm_tab, self.chart_tab):
                thin = getattr(tab, "thin_status", None)
                if thin is not None:
                    thin.set_source(mode)

        self.blynk_client.on_mode_changed(_dong_bo_nguon_cho_thin_status)
        _dong_bo_nguon_cho_thin_status(self.blynk_client.mode)  # trang thai ban dau luc moi mo app

        # SUA: THEM MOI - luc mo app, goi 1 LAN DUY NHAT Historical Data API
        # de lay du lieu nhiet do/do am TU DAU NGAY den gio, tranh bieu do
        # bi "rong" tu dau (BlynkPoller o tren chi doc duoc GIA TRI HIEN
        # TAI, khong co lich su). Xem chart_tab.load_history_from_blynk().
        # SUA: THEM MOI - lich su (Historical Data API) CHI Cloud co, dung
        # thang self.cloud_client thay vi self.blynk_client (ConnectionManager)
        # de KHONG phu thuoc lua chon Cloud/Local hien tai cua nguoi dung
        # (ConnectionManager.get_history() cung tu dong forward ve Cloud roi,
        # nhung ghi ro o day cho de doc/de bao tri hon).
        self.chart_tab.load_history_from_blynk(self.cloud_client)

        # ---------------- BOTTOM NAV BAR ----------------
        nav = QWidget()
        nav.setObjectName("navBar")
        nav.setFixedHeight(56)
        nav_lay = QHBoxLayout(nav)
        nav_lay.setContentsMargins(0, 0, 0, 0)
        nav_lay.setSpacing(0)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for idx, name in enumerate(NAV_ITEMS):
            btn = QPushButton(name)
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.setMinimumWidth(100)
            self.nav_group.addButton(btn, idx)
            nav_lay.addWidget(btn)
        self.nav_group.button(0).setChecked(True)
        self.nav_group.idClicked.connect(self.stack.setCurrentIndex)
        root.addWidget(nav)

        # SUA: THEM MOI - chart_tab chi doc lai CSV vi tri + ve lai heatmap/
        # duong di khi NGUOI DUNG DANG THUC SU DUNG o tab CHART (tranh doc
        # dia + ve matplotlib vo ich khi dang o tab khac). Xem
        # ChartTab.set_active().
        self.stack.currentChanged.connect(self._on_tab_changed)

        # ---------------- ĐỒNG HỒ ----------------
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

    def _update_clock(self):
        now = QDateTime.currentDateTime()
        self.lbl_clock.setText(now.toString("MM-dd-yyyy ddd hh:mm:ss").upper())

    def _ghi_canh_bao(self, noi_dung, trang_thai):
        """SUA: THEM MOI - diem ghi canh bao TAP TRUNG DUY NHAT, thay cho
        goi thang self.alarm_tab.record_event() rai rac o nhieu noi. Ngoai
        viec ghi vao bang ALARM, con TANG bo dem "chua xem" va cap nhat
        ngay hieu "ALARM (N)" mau do tren thanh dieu huong - de nguoi dung
        biet co canh bao moi MA KHONG CAN dang o tab ALARM."""
        self.alarm_tab.record_event(noi_dung, trang_thai=trang_thai)
        self._so_canh_bao_chua_xem += 1
        self._noi_dung_canh_bao_gan_nhat = noi_dung
        self._cap_nhat_bao_hieu_alarm()

    def _cap_nhat_bao_hieu_alarm(self):
        btn_alarm = self.nav_group.button(NAV_ITEMS.index("ALARM"))
        if self._so_canh_bao_chua_xem > 0:
            btn_alarm.setText(f"ALARM ({self._so_canh_bao_chua_xem})")
            btn_alarm.setStyleSheet(
                "background:#d13c3c; color:white; font-weight:700; border:none; border-right:1px solid #a92e2e;"
            )
            # SUA: THEM MOI - hien NOI DUNG canh bao gan nhat qua tooltip
            # (re chuot vao nut ALARM la thay), de nguoi dung biet DUOC MOT
            # PHAN noi dung ngay ca khi dang o tab khac, khong chi biet "co
            # N cai moi" ma khong biet la gi.
            btn_alarm.setToolTip(self._noi_dung_canh_bao_gan_nhat or "")
        else:
            btn_alarm.setText("ALARM")
            btn_alarm.setStyleSheet("")  # tro ve dung style mac dinh #navButton trong QSS chung
            btn_alarm.setToolTip("")

    def _on_schedule_fired(self, message):
        # SUA: ngoai in console, gio ghi luon vao bang ALARM that (day cung la
        # 1 nguon su kien that su - ket qua day lich/nguong xuong ESP32).
        print(message)
        self._ghi_canh_bao(message, trang_thai="Đồng bộ")

    def _on_blynk_alarm(self, data):
        """SUA: THEM MOI - moi khi BlynkPoller doc duoc noi dung V18 (canh bao
        gan nhat tu guiCanhBaoAnToan() ben firmware) KHAC voi lan doc truoc,
        ghi 1 dong moi that su vao bang ALARM. Nho vay TOAN BO cac loai canh
        bao firmware da xay (DHT11 loi, ESP32 tu reset, bom het gio, mat
        UART...) deu hien len duoc, khong chi 3 su kien suy luan rieng le."""
        msg = data.get("alarm")
        if msg and msg != self._last_alarm_msg:
            self._last_alarm_msg = msg
            self._ghi_canh_bao(msg, trang_thai="Từ ESP32")

        # SUA: THEM MOI - canh bao "dang MANUAL + moi truong vuot nguong",
        # nhung theo dung kieu STATE-BASED ALARM (chi bao 1 LAN khi BAT DAU
        # roi vao tinh huong nguy hiem, KHONG nhac lai lien tuc moi 3 giay)
        # - tranh "nuisance alarm"/alarm fatigue da ban truoc. KHONG canh bao
        # vo dieu kien chi vi dang MANUAL (rat nhieu luc dang MANUAL de sua
        # chua binh thuong, moi truong van an toan thi khong can bao dong).
        self._kiem_tra_canh_bao_manual_vuot_nguong(data)

    def _kiem_tra_canh_bao_manual_vuot_nguong(self, data):
        mode = data.get("mode")
        temp = data.get("temp")
        humi = data.get("humi")
        if mode is None or temp is None or humi is None:
            return
        try:
            dang_manual = (int(mode) == 0)  # V5=0 la MANUAL, V5=1 la AUTO (dung quy uoc firmware/manual_tab.py)
            temp = float(temp)
            humi = float(humi)
        except (TypeError, ValueError):
            return

        if not dang_manual:
            # Da roi MANUAL (chuyen ve AUTO) - reset co, de lan MANUAL tiep
            # theo (neu co) van duoc coi la tinh huong MOI, khong bi "ket".
            self._dang_canh_bao_manual_vuot_nguong = False
            return

        env = self.setting_tab.get_env_values()
        ly_do = []
        if temp >= env.get("quat_on_temp", 999):
            ly_do.append(f"nhiệt độ {temp:.1f}°C quá cao (ngưỡng bật quạt {env['quat_on_temp']}°C)")
        elif temp <= env.get("sued_on_temp", -999):
            ly_do.append(f"nhiệt độ {temp:.1f}°C quá thấp (ngưỡng bật sưởi {env['sued_on_temp']}°C)")
        if humi >= env.get("hutam_on", 999):
            ly_do.append(f"độ ẩm {humi:.0f}% quá cao (ngưỡng bật hút ẩm {env['hutam_on']}%)")
        elif humi <= env.get("phunsuong_on", -999):
            ly_do.append(f"độ ẩm {humi:.0f}% quá thấp (ngưỡng bật phun sương {env['phunsuong_on']}%)")

        if ly_do:
            if not self._dang_canh_bao_manual_vuot_nguong:
                # SUA: chi ghi DUNG 1 LAN luc BAT DAU roi vao tinh huong nguy
                # hiem (canh len) - lan poll tiep theo (3s sau) van con nguy
                # hiem thi KHONG ghi lai nua, tranh spam bang ALARM.
                self._dang_canh_bao_manual_vuot_nguong = True
                noi_dung = (
                    "Đang ở chế độ MANUAL và " + "; ".join(ly_do) +
                    " — thiết bị tự động sẽ KHÔNG tự phản ứng, cần xử lý tay ngay."
                )
                self._ghi_canh_bao(noi_dung, trang_thai="Cảnh báo MANUAL")
        else:
            # Moi truong da tro lai an toan - reset co de lan vuot nguong TIEP
            # THEO (neu co) van duoc bao lai, khong bi "ket" o trang thai da bao.
            self._dang_canh_bao_manual_vuot_nguong = False

    def _on_tab_changed(self, idx):
        self.chart_tab.set_active(self.stack.widget(idx) is self.chart_tab)
        # SUA: THEM MOI - nguoi dung VUA MO tab ALARM -> coi nhu da xem het,
        # tat ngay hieu "ALARM (N)" mau do tren thanh dieu huong.
        if self.stack.widget(idx) is self.alarm_tab and self._so_canh_bao_chua_xem > 0:
            self._so_canh_bao_chua_xem = 0
            self._cap_nhat_bao_hieu_alarm()

    def closeEvent(self, event):
        self.blynk_poller.stop()
        self.chart_tab.shutdown()  # dong file CSV vi tri dang ghi cho gon gang
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()