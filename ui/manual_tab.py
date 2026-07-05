# -*- coding: utf-8 -*-
"""
manual_tab.py — Tab MANUAL
Sao chép lưới 3x3 nút bật/tắt thiết bị bằng tay (ảnh 5).
"""

from PyQt5.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt


class DeviceToggle(QVBoxLayout):
    def __init__(self, icon_text, name):
        super().__init__()
        lbl_icon = QLabel(f"{icon_text}")
        lbl_icon.setAlignment(Qt.AlignCenter)
        lbl_icon.setStyleSheet("font-size:26px;")
        self.addWidget(lbl_icon)

        lbl_name = QLabel(name)
        lbl_name.setAlignment(Qt.AlignCenter)
        lbl_name.setStyleSheet("font-weight:700; font-size:12px;")
        self.addWidget(lbl_name)

        self.btn = QPushButton("OFF")
        self.btn.setCheckable(True)
        self.btn.setFixedHeight(38)
        self.btn.setProperty("role", "toggleOff")
        self.btn.clicked.connect(self._toggle)
        self.addWidget(self.btn)

    def _toggle(self, checked):
        if checked:
            self.btn.setText("ON")
            self.btn.setProperty("role", "toggleOn")
        else:
            self.btn.setText("OFF")
            self.btn.setProperty("role", "toggleOff")
        # buộc Qt áp dụng lại stylesheet theo property mới
        self.btn.style().unpolish(self.btn)
        self.btn.style().polish(self.btn)


class ManualTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QGridLayout(self)
        root.setSpacing(18)
        root.setContentsMargins(30, 30, 30, 30)

        devices = [
            ("🌀", "QUẠT CẤP"), ("🌀", "QUẠT HÚT"), ("💦", "PHUN SƯƠNG"),
            ("🍽️", "CHO ĂN"),   ("🔥", "SƯỞI"),      ("🚿", "TẮM"),
            ("🧽", "RỬA CHUỒNG"), ("💡", "ĐÈN"),     ("🚰", "CẤP NƯỚC UỐNG"),
        ]

        self.toggles = {}
        for i, (icon, name) in enumerate(devices):
            r, c = divmod(i, 3)
            toggle = DeviceToggle(icon, name)
            self.toggles[name] = toggle
            root.addLayout(toggle, r, c)
