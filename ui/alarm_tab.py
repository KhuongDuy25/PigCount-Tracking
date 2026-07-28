# -*- coding: utf-8 -*-
"""
alarm_tab.py — Tab ALARM (lưu lịch sử ra file + nút "Đã sửa")
================================================================
- record_event(): thêm 1 cảnh báo mới (từ V18 hoặc từ scheduler), LƯU NGAY
  ra file JSON để không mất khi tắt/mở lại app (trước đây chỉ lưu trong
  RAM của QTableWidget, tắt app là mất trắng).
- Mỗi dòng có nút "✓ Đã sửa" — bấm vào là XÓA HẲN dòng đó khỏi danh sách
  (và khỏi file lưu), coi như lỗi đã được xử lý xong, không cần giữ lại.
- Không có ACK/mức độ nghiêm trọng/âm thanh — giữ đơn giản theo đúng yêu cầu.
"""

import os
import json

from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView
)

MAX_ROWS = 200  # gioi han so dong luu, tranh file phinh to vo han sau nhieu ngay chay

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALARM_HISTORY_PATH = os.path.join(_BASE_DIR, "alarm_history.json")


class AlarmTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries = []  # list[dict]: {"thoi_gian":.., "noi_dung":.., "trang_thai":..}
        self._build_ui()
        self._load_from_file()  # doc lai lich su da luu tu lan truoc (neu co)

    def _build_ui(self):
        root = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("CẢNH BÁO HIỆN TẠI"))
        header.addStretch(1)

        note = QLabel("Tự động cập nhật từ ESP32 (qua V18) — lịch sử được lưu, không mất khi tắt app")
        note.setStyleSheet("color:#888; font-size:11px; font-style:italic;")
        header.addWidget(note)

        self.btn_clear = QPushButton("Xóa tất cả")
        self.btn_clear.clicked.connect(self._clear_all)
        header.addWidget(self.btn_clear)
        root.addLayout(header)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Thời gian", "Nội dung cảnh báo", "Trạng thái", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        root.addWidget(self.table)

    # ------------------------------------------------------------ ghi nhận
    def record_event(self, noi_dung, trang_thai="Mới"):
        """Thêm 1 cảnh báo mới lên ĐẦU danh sách + lưu ngay ra file."""
        if not noi_dung:
            return
        now = QDateTime.currentDateTime().toString("MM-dd-yyyy HH:mm:ss")
        entry = {"thoi_gian": now, "noi_dung": str(noi_dung), "trang_thai": trang_thai}
        self._entries.insert(0, entry)
        self._entries = self._entries[:MAX_ROWS]  # gioi han so luong, bo bot cai cu nhat
        self._rebuild_table()
        self._save_to_file()

    def _clear_all(self):
        self._entries = []
        self._rebuild_table()
        self._save_to_file()

    def _mark_fixed(self, entry_ref):
        """Nguoi dung bam 'Da sua' -> xoa han entry nay khoi danh sach + file."""
        if entry_ref in self._entries:
            self._entries.remove(entry_ref)
        self._rebuild_table()
        self._save_to_file()

    # ------------------------------------------------------------ ve lai bang
    def _rebuild_table(self):
        self.table.setRowCount(0)
        for entry in self._entries:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(entry["thoi_gian"]))
            self.table.setItem(row, 1, QTableWidgetItem(entry["noi_dung"]))
            self.table.setItem(row, 2, QTableWidgetItem(entry["trang_thai"]))

            btn_fixed = QPushButton("✓ Đã sửa")
            btn_fixed.setStyleSheet(
                "background:#2fae4e; color:white; border-radius:4px; padding:3px 8px;"
            )
            # dung dung 'entry' (object hien tai trong vong lap) lam tham chieu,
            # KHONG dung chi so 'row' - vi row se lech ngay khi co dong bi xoa
            btn_fixed.clicked.connect(lambda checked=False, e=entry: self._mark_fixed(e))
            self.table.setCellWidget(row, 3, btn_fixed)

    # ------------------------------------------------------------ luu/doc file
    def _save_to_file(self):
        try:
            with open(ALARM_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[AlarmTab] Khong the luu {ALARM_HISTORY_PATH}: {e}")

    def _load_from_file(self):
        if not os.path.exists(ALARM_HISTORY_PATH):
            return
        try:
            with open(ALARM_HISTORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._entries = data[:MAX_ROWS]
                self._rebuild_table()
        except Exception as e:
            print(f"[AlarmTab] Khong the doc {ALARM_HISTORY_PATH}: {e}")