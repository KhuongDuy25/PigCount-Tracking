# -*- coding: utf-8 -*-
"""
schedule_section.py — Khối quản lý lịch cho 1 loại hoạt động (Cho ăn / Tắm / Rửa chuồng).
Tách riêng thành widget dùng chung để nhúng trực tiếp vào tab SETTING (không
còn mở qua QDialog/cửa sổ riêng nữa).

Bổ sung: LOGIC CHỐNG TRÙNG GIỜ trong cùng 1 loại hoạt động —
  - Khi thêm dòng mới, tự tìm giờ:phút trống gần nhất thay vì luôn mặc định 6:00
    (tránh tạo ra trùng ngay khi vừa thêm).
  - Khi người dùng tự sửa giờ/phút, nếu trùng với 1 dòng khác đã có, dòng đó
    được TÔ ĐỎ VIỀN + hiện dòng cảnh báo ngay dưới bảng.
  - Cung cấp `has_duplicates()` để màn hình cha (SettingTab) kiểm tra trước khi
    cho phép rời khỏi trang chỉnh sửa (bấm BACK) — không cho lưu lịch bị trùng.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QVBoxLayout, QGroupBox, QTableWidget, QPushButton, QSpinBox, QHeaderView, QLabel
)

DUPLICATE_STYLE = "QSpinBox { border: 2px solid #d13c3c; background: #fdeaea; }"
NORMAL_STYLE = "QSpinBox { border: 1px solid #b9b28e; background: white; }"


class ScheduleSection(QGroupBox):
    """Một khối quản lý lịch cho 1 loại hoạt động (Cho ăn / Tắm / Rửa chuồng)."""

    def __init__(self, title, value_label, value_unit, value_range, default_rows):
        super().__init__(title)
        self.value_label = value_label
        self.value_unit = value_unit
        self.value_range = value_range  # (lo, hi)
        self._build_ui()
        for gio, phut, val in default_rows:
            self._add_row(gio, phut, val)
        self._check_duplicates()

    def _build_ui(self):
        root = QVBoxLayout(self)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Giờ", "Phút", f"{self.value_label} ({self.value_unit})", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setFixedHeight(300)
        root.addWidget(self.table)

        btn_add = QPushButton(f"+ Thêm lịch {self.title().lower()}")
        btn_add.clicked.connect(self._add_row_auto_time)
        root.addWidget(btn_add)

        self.lbl_warning = QLabel("")
        self.lbl_warning.setWordWrap(True)
        self.lbl_warning.setStyleSheet("color:#d13c3c; font-weight:700; font-size:11px; padding-top:4px;")
        root.addWidget(self.lbl_warning)

    # ------------------------------------------------------- thêm dòng
    def _find_free_time(self):
        """Tìm giờ:phút (bước 1 giờ, phút=0) chưa bị dùng trong bảng hiện tại,
        bắt đầu dò từ 6:00 rồi vòng qua 0-23h, để dòng mới thêm KHÔNG bị trùng ngay."""
        used = {(self.table.cellWidget(r, 0).value(), self.table.cellWidget(r, 1).value())
                for r in range(self.table.rowCount())}
        for offset in range(24):
            gio = (6 + offset) % 24
            if (gio, 0) not in used:
                return gio, 0
        return 6, 0  # trường hợp cực hiếm: đủ 24 dòng khác giờ, đành trùng

    def _add_row_auto_time(self):
        gio, phut = self._find_free_time()
        self._add_row(gio, phut, self.value_range[0])
        self._check_duplicates()

    def _add_row(self, gio=6, phut=0, val=None):
        row = self.table.rowCount()
        self.table.insertRow(row)

        sp_gio = QSpinBox()
        sp_gio.setRange(0, 23)
        sp_gio.setValue(gio)
        sp_gio.setAlignment(Qt.AlignCenter)
        sp_gio.valueChanged.connect(self._check_duplicates)
        self.table.setCellWidget(row, 0, sp_gio)

        sp_phut = QSpinBox()
        sp_phut.setRange(0, 59)
        sp_phut.setValue(phut)
        sp_phut.setAlignment(Qt.AlignCenter)
        sp_phut.valueChanged.connect(self._check_duplicates)
        self.table.setCellWidget(row, 1, sp_phut)

        sp_val = QSpinBox()
        lo, hi = self.value_range
        sp_val.setRange(lo, hi)
        sp_val.setValue(val if val is not None else lo)
        sp_val.setAlignment(Qt.AlignCenter)
        self.table.setCellWidget(row, 2, sp_val)

        btn_del = QPushButton("Xóa")
        btn_del.setStyleSheet("background:#d13c3c; color:white; border-radius:4px;")
        btn_del.clicked.connect(lambda: self._delete_row_by_widget(btn_del))
        self.table.setCellWidget(row, 3, btn_del)

    def _delete_row_by_widget(self, widget):
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 3) is widget:
                self.table.removeRow(row)
                break
        self._check_duplicates()

    # ------------------------------------------------------- chống trùng giờ
    def _check_duplicates(self):
        """Quét toàn bộ dòng, tìm các cặp (giờ, phút) bị trùng nhau, tô đỏ các
        ô liên quan và hiện dòng cảnh báo. Trả về True nếu có ít nhất 1 cặp trùng."""
        n = self.table.rowCount()
        time_pairs = []
        for r in range(n):
            sp_gio = self.table.cellWidget(r, 0)
            sp_phut = self.table.cellWidget(r, 1)
            if sp_gio is None or sp_phut is None:
                continue
            time_pairs.append((sp_gio.value(), sp_phut.value()))

        # đếm số lần xuất hiện mỗi mốc giờ
        counts = {}
        for t in time_pairs:
            counts[t] = counts.get(t, 0) + 1
        duplicated_times = {t for t, c in counts.items() if c > 1}

        has_dup = len(duplicated_times) > 0
        for r in range(n):
            sp_gio = self.table.cellWidget(r, 0)
            sp_phut = self.table.cellWidget(r, 1)
            if sp_gio is None or sp_phut is None:
                continue
            t = (sp_gio.value(), sp_phut.value())
            style = DUPLICATE_STYLE if t in duplicated_times else NORMAL_STYLE
            sp_gio.setStyleSheet(style)
            sp_phut.setStyleSheet(style)

        if has_dup:
            times_text = ", ".join(f"{g:02d}:{p:02d}" for g, p in sorted(duplicated_times))
            self.lbl_warning.setText(f"⚠️ Trùng giờ: {times_text} — vui lòng chỉnh lại trước khi lưu.")
        else:
            self.lbl_warning.setText("")

        return has_dup

    def has_duplicates(self):
        """Cho màn hình cha (SettingTab) gọi để kiểm tra trước khi cho phép rời trang."""
        return self._check_duplicates()

    def get_schedule(self):
        """Trả về list dict [{giờ, phút, giá trị}, ...] cho toàn bộ dòng hiện có."""
        result = []
        for row in range(self.table.rowCount()):
            gio = self.table.cellWidget(row, 0).value()
            phut = self.table.cellWidget(row, 1).value()
            val = self.table.cellWidget(row, 2).value()
            result.append({"gio": gio, "phut": phut, "value": val})
        return result