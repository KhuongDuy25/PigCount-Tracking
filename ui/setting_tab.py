# -*- coding: utf-8 -*-
"""
setting_tab.py — Tab SETTING (mô hình Tổng quan <-> Chỉnh sửa, giống HMI gốc)

Đúng như 2 ảnh chụp màn hình gốc:
  - Ảnh 1 (TỔNG QUAN): hiển thị toàn bộ giá trị đã cài đặt, CHỈ XEM
    (không sửa được tại đây), có 2 nút bấm:
       "SET MÔI TRƯỜNG + ĐỘNG CƠ"  -> sang màn hình chỉnh sửa môi trường
       "SET LỊCH HOẠT ĐỘNG"        -> sang màn hình chỉnh sửa lịch
  - Ảnh 2 (CHỈNH SỬA): các ô lúc này mới sửa được, có nút "BACK" ở góc
    trên bên phải để quay lại màn hình Tổng quan.

Toàn bộ 3 màn hình (Tổng quan / Sửa môi trường / Sửa lịch) đều nằm trong
CÙNG 1 tab SETTING, chuyển qua lại bằng QStackedWidget nội bộ — không mở
cửa sổ (QDialog) hay rời khỏi tab SETTING bao giờ.
"""

from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QGroupBox,
    QSpinBox, QPushButton, QScrollArea, QStackedWidget, QFrame
)

from ui.schedule_section import ScheduleSection


# Định nghĩa các ngưỡng môi trường: (nhãn, mặc định, đơn vị, key, min, max)
ENV_ROWS = [
    ("Bật sưởi khi nhiệt độ thấp hơn", 28, "°C", "sued_on_temp", -20, 60),
    ("Tắt sưởi khi nhiệt độ cao hơn", 30, "°C", "sued_off_temp", -20, 60),
    ("Bật quạt khi nhiệt độ cao hơn", 32, "°C", "quat_on_temp", -20, 60),
    ("Tắt quạt khi nhiệt độ thấp hơn", 30, "°C", "quat_off_temp", -20, 60),
    ("Bật hút ẩm khi độ ẩm cao hơn", 75, "%", "hutam_on", 0, 100),
    ("Tắt hút ẩm khi độ ẩm thấp hơn", 65, "%", "hutam_off", 0, 100),
    ("Bật phun sương khi độ ẩm thấp hơn", 55, "%", "phunsuong_on", 0, 100),
    ("Tắt phun sương khi độ ẩm cao hơn", 65, "%", "phunsuong_off", 0, 100),
]


def readonly_value_box(text):
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setFixedWidth(65)
    lbl.setStyleSheet(
        "background:#eef0ef; border:1px solid #b9b28e; border-radius:4px; "
        "padding:3px; font-weight:700; color:#444;"
    )
    return lbl


class SettingTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # dữ liệu nguồn chung, dùng cho cả trang Tổng quan lẫn trang Chỉnh sửa
        self.env_values = {key: default for (_, default, _, key, _, _) in ENV_ROWS}

        self.env_spinboxes = {}     # dùng ở trang chỉnh sửa
        self.env_overview_labels = {}  # dùng ở trang tổng quan (readonly)

        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        # Xây trang lịch TRƯỚC để có sec_feed/sec_tam/sec_rua, rồi mới xây
        # trang Tổng quan (trang này cần đọc dữ liệu lịch để hiển thị tóm tắt).
        self.page_edit_schedule = self._build_edit_schedule_page()
        self.page_overview = self._build_overview_page()
        self.page_edit_env = self._build_edit_env_page()

        self.stack.addWidget(self.page_overview)       # index 0
        self.stack.addWidget(self.page_edit_env)        # index 1
        self.stack.addWidget(self.page_edit_schedule)    # index 2
        self.stack.setCurrentIndex(0)

    # ==================================================================
    # TRANG 0 — TỔNG QUAN (chỉ xem, không sửa được)
    # ==================================================================
    def _build_overview_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        root = QHBoxLayout(content)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # ---- cột trái: môi trường (readonly) ----
        gb_env = QGroupBox("🌡️ MÔI TRƯỜNG (đã cài đặt)")
        gl = QGridLayout(gb_env)
        for i, (label, default, unit, key, lo, hi) in enumerate(ENV_ROWS):
            gl.addWidget(QLabel(label), i, 0)
            box = readonly_value_box(str(default))
            self.env_overview_labels[key] = box
            gl.addWidget(box, i, 1)
            gl.addWidget(QLabel(unit), i, 2)
        root.addWidget(gb_env, 2)

        # ---- cột giữa: lịch hoạt động (tóm tắt, readonly) ----
        gb_sched = QGroupBox("🗓️ LỊCH HOẠT ĐỘNG (đã cài đặt)")
        sl = QVBoxLayout(gb_sched)
        self.lbl_schedule_summary = QLabel()
        self.lbl_schedule_summary.setWordWrap(True)
        self.lbl_schedule_summary.setStyleSheet(
            "background:#eef0ef; border:1px solid #b9b28e; border-radius:4px; padding:10px;"
        )
        sl.addWidget(self.lbl_schedule_summary)
        root.addWidget(gb_sched, 3)

        # ---- cột phải: 2 nút chuyển sang trang chỉnh sửa ----
        gb_actions = QGroupBox("Thao tác")
        al = QVBoxLayout(gb_actions)

        btn_env = QPushButton("➡️\nSET MÔI TRƯỜNG + ĐỘNG CƠ")
        btn_env.setFixedHeight(90)
        btn_env.setStyleSheet(
            "background:#e9fbe9; border:2px solid #2fae4e; border-radius:8px; "
            "font-weight:700; color:#1c6b2c; font-size:12px;"
        )
        btn_env.clicked.connect(self._goto_edit_env)
        al.addWidget(btn_env)

        btn_sched = QPushButton("➡️\nSET LỊCH HOẠT ĐỘNG")
        btn_sched.setFixedHeight(90)
        btn_sched.setStyleSheet(
            "background:#e9f0fb; border:2px solid #1857a4; border-radius:8px; "
            "font-weight:700; color:#123f7c; font-size:12px;"
        )
        btn_sched.clicked.connect(self._goto_edit_schedule)
        al.addWidget(btn_sched)

        al.addStretch(1)
        root.addWidget(gb_actions, 1)

        self._refresh_schedule_summary()
        return page

    def _refresh_overview_env_labels(self):
        for key, box in self.env_overview_labels.items():
            box.setText(str(self.env_values[key]))

    def _refresh_schedule_summary(self):
        def fmt(rows, unit):
            if not rows:
                return "  (chưa có lịch)"
            return "\n".join(
                f"  • {r['gio']:02d}:{r['phut']:02d} — {r['value']} {unit}" for r in rows
            )

        feed = self.sec_feed.get_schedule() if hasattr(self, "sec_feed") else []
        tam = self.sec_tam.get_schedule() if hasattr(self, "sec_tam") else []
        rua = self.sec_rua.get_schedule() if hasattr(self, "sec_rua") else []

        text = (
            f"🍽️ Cho ăn:\n{fmt(feed, 'gram')}\n\n"
            f"🚿 Tắm:\n{fmt(tam, 'giây')}\n\n"
            f"🧹 Rửa chuồng:\n{fmt(rua, 'giây')}"
        )
        self.lbl_schedule_summary.setText(text)

    # ==================================================================
    # TRANG 1 — CHỈNH SỬA MÔI TRƯỜNG + ĐỘNG CƠ (có nút BACK)
    # ==================================================================
    def _build_edit_env_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)

        header = QHBoxLayout()
        title = QLabel("CHỈNH SỬA: MÔI TRƯỜNG + ĐỘNG CƠ")
        title.setStyleSheet("font-weight:700; color:#1857a4; font-size:15px;")
        header.addWidget(title)
        header.addStretch(1)
        btn_back = QPushButton("⬅ BACK")
        btn_back.setStyleSheet(
            "background:#1857a4; color:white; font-weight:700; border-radius:6px; padding:6px 16px;"
        )
        btn_back.clicked.connect(self._back_from_edit_env)
        header.addWidget(btn_back)
        outer.addLayout(header)

        gb = QGroupBox("Ngưỡng môi trường (áp dụng ở chế độ AUTO)")
        gl = QGridLayout(gb)
        half = (len(ENV_ROWS) + 1) // 2
        for i, (label, default, unit, key, lo, hi) in enumerate(ENV_ROWS):
            col_offset = 0 if i < half else 3
            row_idx = i if i < half else i - half
            gl.addWidget(QLabel(label), row_idx, col_offset)
            sp = QSpinBox()
            sp.setRange(lo, hi)
            sp.setValue(self.env_values[key])
            sp.setFixedWidth(65)
            sp.setAlignment(Qt.AlignCenter)
            self.env_spinboxes[key] = sp
            gl.addWidget(sp, row_idx, col_offset + 1)
            gl.addWidget(QLabel(unit), row_idx, col_offset + 2)

        note = QLabel(
            "Ghi chú: các ngưỡng này chỉ áp dụng khi hệ thống đang ở chế độ AUTO. "
            "Ở chế độ MANUAL, người dùng tự bật/tắt từng thiết bị ở tab MANUAL."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#555; font-size:11px; padding-top:10px;")
        gl.addWidget(note, half, 0, 1, 6)
        outer.addWidget(gb)
        outer.addStretch(1)
        return page

    def _goto_edit_env(self):
        # đồng bộ giá trị hiện có vào các ô chỉnh sửa trước khi hiển thị
        for key, sp in self.env_spinboxes.items():
            sp.setValue(self.env_values[key])
        self.stack.setCurrentIndex(1)

    def _back_from_edit_env(self):
        # lưu giá trị vừa sửa lại vào dữ liệu chung + cập nhật màn hình tổng quan
        for key, sp in self.env_spinboxes.items():
            self.env_values[key] = sp.value()
        self._refresh_overview_env_labels()
        self.stack.setCurrentIndex(0)

    # ==================================================================
    # TRANG 2 — CHỈNH SỬA LỊCH HOẠT ĐỘNG (có nút BACK)
    # ==================================================================
    def _build_edit_schedule_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)

        header = QHBoxLayout()
        title = QLabel("CHỈNH SỬA: LỊCH HOẠT ĐỘNG")
        title.setStyleSheet("font-weight:700; color:#1857a4; font-size:15px;")
        header.addWidget(title)
        header.addStretch(1)
        btn_back = QPushButton("⬅ BACK")
        btn_back.setStyleSheet(
            "background:#1857a4; color:white; font-weight:700; border-radius:6px; padding:6px 16px;"
        )
        btn_back.clicked.connect(self._back_from_edit_schedule)
        header.addWidget(btn_back)
        outer.addLayout(header)

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

        return page

    def _goto_edit_schedule(self):
        self.stack.setCurrentIndex(2)

    def _back_from_edit_schedule(self):
        self._refresh_schedule_summary()
        self.stack.setCurrentIndex(0)

    # ------------------------------------------------------------------
    def get_env_values(self):
        return dict(self.env_values)

    def get_all_schedules(self):
        return {
            "cho_an": self.sec_feed.get_schedule(),
            "tam": self.sec_tam.get_schedule(),
            "rua_chuong": self.sec_rua.get_schedule(),
        }
