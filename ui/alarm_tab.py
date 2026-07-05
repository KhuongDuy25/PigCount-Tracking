# -*- coding: utf-8 -*-
"""
alarm_tab.py — Tab ALARM
Sao chép màn hình "Cảnh báo hiện tại" + "Lịch sử lỗi" (ảnh 1).
Bảng mặc định trống, có nút demo để thêm cảnh báo test và nút xóa.
"""

from PyQt5.QtCore import QDateTime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton
)


class AlarmTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("CẢNH BÁO HIỆN TẠI"))
        header.addStretch(1)
        self.btn_history = QPushButton("Lịch sử lỗi")
        self.btn_history.clicked.connect(self._add_demo_alarm)
        header.addWidget(self.btn_history)
        self.btn_clear = QPushButton("Xóa cảnh báo")
        self.btn_clear.clicked.connect(self._clear_alarms)
        header.addWidget(self.btn_clear)
        root.addLayout(header)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Thời gian", "Mã lỗi", "Nội dung", "Trạng thái"])
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table)

    def _add_demo_alarm(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        now = QDateTime.currentDateTime().toString("MM-dd-yyyy HH:mm:ss")
        demo_values = [now, "E-07", "Bơm máng nước chạy quá thời gian an toàn", "Chưa xử lý"]
        for col, val in enumerate(demo_values):
            self.table.setItem(row, col, QTableWidgetItem(val))

    def _clear_alarms(self):
        self.table.setRowCount(0)
