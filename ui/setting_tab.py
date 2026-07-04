# -*- coding: utf-8 -*-
"""
setting_tab.py — Tab SETTING (gộp thành 1 trang duy nhất)
Trước đây bấm 2 nút sẽ MỞ CỬA SỔ RIÊNG (QDialog) để cài Môi trường / Lịch
hoạt động. Theo yêu cầu, giờ TẤT CẢ hiển thị ngay trên cùng 1 tab SETTING
(cuộn dọc nếu dài), không rời khỏi tab khi bấm nút cài đặt/lưu.

Bố cục từ trên xuống:
  1. Ngưỡng môi trường (chế độ AUTO) — nhiệt độ / độ ẩm bật-tắt thiết bị
  2. Lịch cho ăn (gram) — thêm/xóa từng dòng lịch
  3. Lịch tắm (giây)
  4. Lịch rửa chuồng (giây)
  5. Nút "Lưu tất cả cài đặt" — hiển thị trạng thái NGAY TRONG TAB (không popup)
"""

from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QGroupBox,
    QSpinBox, QPushButton, QScrollArea
)

from ui.schedule_section import ScheduleSection


class SettingTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.env_fields = {}
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        root.addWidget(self._build_env_group())
        root.addWidget(self._build_schedule_group())

        # ---------------- thanh lưu chung (không mở cửa sổ nào) ----------------
        save_bar = QHBoxLayout()
        btn_save = QPushButton("💾 LƯU TẤT CẢ CÀI ĐẶT")
        btn_save.setFixedHeight(42)
        btn_save.setStyleSheet(
            "background:#1857a4; color:white; font-weight:700; border-radius:6px; font-size:14px;"
        )
        btn_save.clicked.connect(self._save_all)
        save_bar.addWidget(btn_save)

        self.lbl_save_status = QLabel("")
        self.lbl_save_status.setStyleSheet("color:#2fae4e; font-weight:600; padding-left:10px;")
        save_bar.addWidget(self.lbl_save_status)
        save_bar.addStretch(1)
        root.addLayout(save_bar)

        root.addStretch(1)

    # ------------------------------------------------------- ngưỡng môi trường
    def _build_env_group(self):
        gb = QGroupBox("🌡️ Ngưỡng môi trường (chế độ AUTO — quạt, sưởi, hút ẩm, phun sương)")
        gl = QGridLayout(gb)
        rows = [
            ("Bật sưởi khi nhiệt độ thấp hơn", 28, "°C", "sued_on_temp", -20, 60),
            ("Tắt sưởi khi nhiệt độ cao hơn", 30, "°C", "sued_off_temp", -20, 60),
            ("Bật quạt khi nhiệt độ cao hơn", 32, "°C", "quat_on_temp", -20, 60),
            ("Tắt quạt khi nhiệt độ thấp hơn", 30, "°C", "quat_off_temp", -20, 60),
            ("Bật hút ẩm khi độ ẩm cao hơn", 75, "%", "hutam_on", 0, 100),
            ("Tắt hút ẩm khi độ ẩm thấp hơn", 65, "%", "hutam_off", 0, 100),
            ("Bật phun sương khi độ ẩm thấp hơn", 55, "%", "phunsuong_on", 0, 100),
            ("Tắt phun sương khi độ ẩm cao hơn", 65, "%", "phunsuong_off", 0, 100),
        ]
        # chia 2 cột cho gọn, mỗi cột 4 dòng
        half = (len(rows) + 1) // 2
        for i, (label, default, unit, key, lo, hi) in enumerate(rows):
            col_offset = 0 if i < half else 3
            row_idx = i if i < half else i - half
            gl.addWidget(QLabel(label), row_idx, col_offset)
            sp = QSpinBox()
            sp.setRange(lo, hi)
            sp.setValue(default)
            sp.setFixedWidth(65)
            sp.setAlignment(Qt.AlignCenter)
            self.env_fields[key] = sp
            gl.addWidget(sp, row_idx, col_offset + 1)
            gl.addWidget(QLabel(unit), row_idx, col_offset + 2)

        note = QLabel(
            "Ghi chú: các ngưỡng này chỉ áp dụng khi hệ thống đang ở chế độ AUTO. "
            "Ở chế độ MANUAL, người dùng tự bật/tắt từng thiết bị ở tab MANUAL."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#555; font-size:11px; padding-top:6px;")
        gl.addWidget(note, half, 0, 1, 6)
        return gb

    # ------------------------------------------------------------- lịch hoạt động
    def _build_schedule_group(self):
        gb = QGroupBox("🗓️ Lịch hoạt động")
        outer = QVBoxLayout(gb)

        row = QHBoxLayout()
        outer.addLayout(row)

        # Cho ăn: theo GRAM (đúng với hệ cân cám loadcell + động cơ bước)
        self.sec_feed = ScheduleSection(
            "Cho ăn", "Khối lượng", "gram", (0, 2000),
            default_rows=[(6, 0, 100), (12, 0, 100), (18, 0, 100)]
        )
        row.addWidget(self.sec_feed)

        # Tắm: theo GIÂY (bơm 12V chạy theo thời gian)
        self.sec_tam = ScheduleSection(
            "Tắm", "Thời gian chạy", "giây", (0, 600),
            default_rows=[(8, 0, 80), (14, 0, 80)]
        )
        row.addWidget(self.sec_tam)

        # Rửa chuồng: theo GIÂY (bơm sàn 5V chạy theo thời gian)
        self.sec_rua = ScheduleSection(
            "Rửa chuồng", "Thời gian chạy", "giây", (0, 600),
            default_rows=[(7, 0, 200), (19, 0, 200)]
        )
        row.addWidget(self.sec_rua)

        return gb

    # ------------------------------------------------------------------
    def get_env_values(self):
        """Trả về dict {key: value} cho tất cả các ngưỡng môi trường đã đặt."""
        return {k: sp.value() for k, sp in self.env_fields.items()}

    def get_all_schedules(self):
        return {
            "cho_an": self.sec_feed.get_schedule(),
            "tam": self.sec_tam.get_schedule(),
            "rua_chuong": self.sec_rua.get_schedule(),
        }

    def _save_all(self):
        # Chỗ này để dành gửi toàn bộ cấu hình xuống ESP32 thật (qua Blynk/Serial/MQTT...)
        env = self.get_env_values()
        schedules = self.get_all_schedules()
        now = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.lbl_save_status.setText(f"✅ Đã lưu lúc {now}")
