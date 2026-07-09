# -*- coding: utf-8 -*-
"""
main.py — Phần mềm giám sát & điều khiển TRANG TRẠI THÔNG MINH
================================================================
Mô phỏng lại giao diện màn hình HMI (WeinView) gốc với 6 tab điều hướng:
  HOME | SCREEN | MANUAL | SETTING | ALARM | CHART

- HOME:    (CÓ NÂNG CẤP) dashboard tổng quan + camera giám sát máng ăn,
           vẽ vùng (zone) và nhận diện ID lợn theo màu vùng lưng.
- SCREEN:  giữ nguyên bố cục màn hình giám sát cảm biến / đèn báo / thiết bị.
- MANUAL:  giữ nguyên lưới nút bật/tắt thiết bị bằng tay.
- SETTING: giữ nguyên cấu hình môi trường, động cơ cho ăn, lịch hoạt động, chiếu sáng.
- ALARM:   giữ nguyên bảng cảnh báo / lịch sử lỗi.
- CHART:   tab mới, biểu đồ nhiệt độ/độ ẩm + khung placeholder cho bản đồ
           nhiệt/đường đi di chuyển của lợn (sẽ nâng cấp sau).

Cách chạy:
    pip install PyQt5 opencv-python numpy matplotlib
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
from ui.screen_tab import ScreenTab
from ui.manual_tab import ManualTab
from ui.setting_tab import SettingTab
from ui.alarm_tab import AlarmTab
from ui.chart_tab import ChartTab

import config
from blynk_client import BlynkClient
from scheduler import AutoScheduler
from feed_coordinator import FeedCoordinator


NAV_ITEMS = [
    ("HOME", "🏠"),
    ("SCREEN", "🖥️"),
    ("MANUAL", "✋"),
    ("SETTING", "⚙️"),
    ("ALARM", "⚠️"),
    ("CHART", "📊"),
]


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

        # ---------------- KẾT NỐI BLYNK CLOUD + SCHEDULER ----------------
        self.blynk_client = BlynkClient(config.BLYNK_AUTH_TOKEN, timeout=config.BLYNK_HTTP_TIMEOUT)

        # FeedCoordinator: dùng CHUNG cho cả nút "CHO ĂN" bấm tay (tab MANUAL)
        # lẫn lịch cho ăn tự động (AutoScheduler) - đảm bảo không bao giờ có
        # 2 lệnh cho ăn chạy chồng nhau, và khối lượng luôn được xác nhận
        # thật trước khi bấm xả (xem feed_coordinator.py).
        self.feed_coordinator = FeedCoordinator(self.blynk_client)

        # ---------------- STACK NỘI DUNG ----------------
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.home_tab = HomeTab()
        self.screen_tab = ScreenTab()
        self.manual_tab = ManualTab(blynk_client=self.blynk_client, feed_coordinator=self.feed_coordinator)
        self.setting_tab = SettingTab()
        self.alarm_tab = AlarmTab()
        self.chart_tab = ChartTab()

        for w in (self.home_tab, self.screen_tab, self.manual_tab,
                  self.setting_tab, self.alarm_tab, self.chart_tab):
            self.stack.addWidget(w)

        # Scheduler chạy nền: đối chiếu lịch đã cài trong SettingTab với đồng
        # hồ hệ thống, tự động gửi lệnh xuống ESP32 đúng giờ (xem scheduler.py
        # để biết quy tắc xử lý khi trùng với thao tác tay).
        self.auto_scheduler = AutoScheduler(
            setting_tab=self.setting_tab,
            blynk_client=self.blynk_client,
            feed_coordinator=self.feed_coordinator,
            check_interval_sec=config.SCHEDULER_CHECK_INTERVAL_SEC,
        )
        self.auto_scheduler.schedule_fired.connect(self._on_schedule_fired)

        # ---------------- BOTTOM NAV BAR ----------------
        nav = QWidget()
        nav.setObjectName("navBar")
        nav.setFixedHeight(56)
        nav_lay = QHBoxLayout(nav)
        nav_lay.setContentsMargins(0, 0, 0, 0)
        nav_lay.setSpacing(0)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for idx, (name, icon) in enumerate(NAV_ITEMS):
            btn = QPushButton(f"{icon}\n{name}")
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.setMinimumWidth(100)
            self.nav_group.addButton(btn, idx)
            nav_lay.addWidget(btn)
        self.nav_group.button(0).setChecked(True)
        self.nav_group.idClicked.connect(self.stack.setCurrentIndex)
        root.addWidget(nav)

        # ---------------- ĐỒNG HỒ ----------------
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

    def _update_clock(self):
        now = QDateTime.currentDateTime()
        self.lbl_clock.setText(now.toString("MM-dd-yyyy ddd hh:mm:ss").upper())

    def _on_schedule_fired(self, message):
        # Hiện tại chỉ in ra console để theo dõi/debug. Có thể nối thêm vào
        # bảng ALARM hoặc 1 log riêng trong tab CHART nếu muốn xem trực quan.
        print(message)

    def closeEvent(self, event):
        self.auto_scheduler.stop()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
