# -*- coding: utf-8 -*-
"""
screen_tab.py — Tab SCREEN
Sao chép nguyên bố cục màn hình giám sát (ảnh 6): Cảm biến / Đèn báo / Trạng thái thiết bị.
"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel, QGroupBox
from PyQt5.QtCore import Qt


def value_box(text):
    lbl = QLabel(text)
    lbl.setProperty("role", "value")
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


def status_box(text, on=False):
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    color = "#2fae4e" if on else "#b23a3a"
    lbl.setStyleSheet(
        f"background:#fbf8ec; border:1px solid #b9b28e; border-radius:4px; "
        f"padding:4px 10px; font-weight:700; color:{color};"
    )
    return lbl


class ScreenTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)

        # ----------------- CẢM BIẾN -----------------
        gb1 = QGroupBox("Cảm biến")
        g1 = QGridLayout(gb1)
        rows = [
            ("🌡️ Nhiệt độ", "31.5", "°C", True),
            ("💧 Độ ẩm", "59.2", "%", True),
            ("Mực nước thấp", "OFF", "", False),
            ("Mực nước cạn", "OFF", "", False),
            ("Cảm biến Limit", "OFF", "", False),
            ("Cảm biến Home", "OFF", "", False),
        ]
        for i, (label, val, unit, is_value) in enumerate(rows):
            g1.addWidget(QLabel(label), i, 0)
            if is_value:
                g1.addWidget(value_box(val), i, 1)
                g1.addWidget(QLabel(unit), i, 2)
            else:
                g1.addWidget(status_box(val, on=False), i, 1, 1, 2)
        root.addWidget(gb1, 1)

        # ----------------- ĐÈN BÁO -----------------
        gb2 = QGroupBox("Đèn báo")
        g2 = QGridLayout(gb2)
        lamp_rows = [
            ("EMERGENCY", False),
            ("HỆ THỐNG RUN", True),
            ("AUTO", False),
            ("MAN", True),
        ]
        for i, (label, on) in enumerate(lamp_rows):
            g2.addWidget(QLabel(label), i, 0)
            g2.addWidget(status_box("ON" if on else "OFF", on=on), i, 1)
        root.addWidget(gb2, 1)

        # ----------------- TRẠNG THÁI THIẾT BỊ -----------------
        gb3 = QGroupBox("Trạng thái thiết bị")
        g3 = QGridLayout(gb3)
        devices = [
            "Quạt thổi", "Quạt hút", "Phun sương",
            "Cho ăn", "Tắm", "Sưởi",
            "Cấp nước uống", "Rửa chuồng", "Đèn",
        ]
        for i, name in enumerate(devices):
            r, c = divmod(i, 3)
            box = QVBoxLayout()
            box.addWidget(QLabel(name))
            box.addWidget(status_box("OFF", on=False))
            g3.addLayout(box, r, c)
        root.addWidget(gb3, 2)
