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

import os
import json

from PyQt5.QtCore import Qt, QDateTime, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QGroupBox,
    QSpinBox, QPushButton, QScrollArea, QStackedWidget, QFrame
)

from ui.schedule_section import ScheduleSection, LightScheduleSection
from ui.style import COLOR_HEADER_BLUE, COLOR_HEADER_BLUE_DARK, COLOR_ON_GREEN, COLOR_ALARM_RED, COLOR_TEXT_DARK

# SUA: file luu nguong moi truong (nhiet do/do am) ra dia, cung thu muc goc
# du an (ngang hang voi main.py) - giong dung cach zone_config.json /
# pig_color_ids.json da lam - de KHONG BI MAT khi tat/mo lai app. Truoc day
# self.env_values chi khoi tao tu ENV_ROWS (hang cung trong code) moi lan mo
# app, nen moi lan sua xong roi tat app la mat het, phai cai lai tu dau.
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_CONFIG_PATH = os.path.join(_BASE_DIR, "env_config.json")

# SUA: THEM MOI - file luu LICH HOAT DONG (cho an/tam/rua chuong/den) ra dia,
# cung co che voi env_config.json o tren. Truoc day 4 loai lich chi khoi tao
# tu default_rows CUNG trong code (vd [(6,0,100),(12,0,100),(18,0,100)]) moi
# lan mo app - nen moi lan sua lich xong roi tat app la MAT HET, tro ve dung
# 3 dong mac dinh cu, y het loai loi da gap voi nguong moi truong truoc day.
SCHEDULE_CONFIG_PATH = os.path.join(_BASE_DIR, "schedule_config.json")


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
    # SUA: dung lai dung "cong thuc" hien thi gia tri chung cua ca app (nen
    # kem #fbf8ec + vien tan #b9b28e + chu navy dam) thay vi 1 to mau xam
    # rieng (#eef0ef) chi co o tab SETTING - de o gia tri o day nhin giong
    # het o gia tri nhiet do/do am ben tab HOME.
    lbl.setStyleSheet(
        f"background:#fbf8ec; border:1px solid #b9b28e; border-radius:0px; "
        f"padding:3px; font-weight:700; color:{COLOR_TEXT_DARK};"
    )
    return lbl


# Cấu hình hiển thị cho từng loại lịch trong màn hình Tổng quan
SCHEDULE_CATEGORIES = [
    # key,        icon,   tiêu đề,        đơn vị,   màu chủ đạo, màu nền nhạt
    ("cho_an",    "🍽️",  "Cho ăn",       "gram",   "#1857a4",  "#e9fbe9"),
    ("tam",       "🚿",   "Tắm",          "giây",   "#1857a4",  "#e9fbe9"),
    ("rua_chuong","🧹",   "Rửa chuồng",   "giây",   "#1857a4",  "#e9fbe9"),
]


def build_schedule_card(icon, title, unit, color, bg, rows):
    """Dựng 1 thẻ (card) hiển thị lịch cho 1 loại hoạt động, đẹp hơn hẳn so với
    kiểu liệt kê chữ đơn giản trước đây — mỗi mốc giờ là 1 "chip" màu + dòng
    riêng biệt, có viền và màu nền theo từng loại hoạt động."""
    card = QFrame()
    card.setStyleSheet(
        f"QFrame {{ background:{bg}; border:1px solid {color}; border-radius:0px; }}"
    )
    lay = QVBoxLayout(card)
    lay.setContentsMargins(14, 12, 14, 14)
    lay.setSpacing(8)

    header = QLabel(f"{icon}  {title.upper()}")
    header.setStyleSheet(
        f"font-weight:800; font-size:16px; color:{color}; background:transparent; border:none;"
    )
    lay.addWidget(header)

    if not rows:
        empty = QLabel("Chưa có lịch nào được cài đặt")
        empty.setStyleSheet("color:#999; font-size:14px; font-style:italic; background:transparent; border:none;")
        lay.addWidget(empty)
    else:
        for r in sorted(rows, key=lambda x: (x["gio"], x["phut"])):
            row_frame = QFrame()
            row_frame.setStyleSheet(
                "QFrame { background:white; border:1px solid #d8d2b8; border-radius:0px; }"
            )
            row_lay = QHBoxLayout(row_frame)
            row_lay.setContentsMargins(10, 6, 10, 6)
            row_lay.setSpacing(10)

            time_chip = QLabel(f"{r['gio']:02d}:{r['phut']:02d}")
            time_chip.setFixedWidth(58)
            time_chip.setAlignment(Qt.AlignCenter)
            time_chip.setStyleSheet(
                f"background:{color}; color:white; border-radius:0px; "
                f"font-weight:800; font-size:15px; padding:4px 0;"
            )
            row_lay.addWidget(time_chip)

            arrow = QLabel("→")
            arrow.setStyleSheet(f"color:{color}; font-weight:700; background:transparent; border:none;")
            row_lay.addWidget(arrow)

            value_lbl = QLabel(f"{r['value']} {unit}")
            value_lbl.setStyleSheet(f"font-weight:700; font-size:15px; color:{COLOR_TEXT_DARK}; background:transparent; border:none;")
            row_lay.addWidget(value_lbl)

            row_lay.addStretch(1)
            lay.addWidget(row_frame)

    lay.addStretch(1)
    return card


def build_light_schedule_card(rows):
    """Dựng card riêng cho lịch ĐÈN — mỗi dòng là 1 khung [giờ bật -> giờ tắt],
    khác định dạng dữ liệu với build_schedule_card (không có 'value' đơn lẻ)."""
    color, bg = "#1857a4", "#e9f0fb"
    card = QFrame()
    card.setStyleSheet(f"QFrame {{ background:{bg}; border:1px solid {color}; border-radius:0px; }}")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(14, 12, 14, 14)
    lay.setSpacing(8)

    header = QLabel("💡  CHIẾU SÁNG (ĐÈN)")
    header.setStyleSheet(f"font-weight:800; font-size:16px; color:{color}; background:transparent; border:none;")
    lay.addWidget(header)

    if not rows:
        empty = QLabel("Chưa có lịch nào được cài đặt")
        empty.setStyleSheet("color:#999; font-size:14px; font-style:italic; background:transparent; border:none;")
        lay.addWidget(empty)
    else:
        for r in sorted(rows, key=lambda x: (x["gio_bat"], x["phut_bat"])):
            row_frame = QFrame()
            row_frame.setStyleSheet("QFrame { background:white; border:1px solid #d8d2b8; border-radius:0px; }")
            row_lay = QHBoxLayout(row_frame)
            row_lay.setContentsMargins(10, 6, 10, 6)
            row_lay.setSpacing(8)

            on_chip = QLabel(f"{r['gio_bat']:02d}:{r['phut_bat']:02d}")
            on_chip.setFixedWidth(58)
            on_chip.setAlignment(Qt.AlignCenter)
            on_chip.setStyleSheet(f"background:{color}; color:white; border-radius:0px; font-weight:800; font-size:15px; padding:4px 0;")
            row_lay.addWidget(on_chip)

            arrow = QLabel("BẬT  →")
            arrow.setStyleSheet(f"color:{color}; font-weight:700; background:transparent; border:none; font-size:14px;")
            row_lay.addWidget(arrow)

            off_chip = QLabel(f"{r['gio_tat']:02d}:{r['phut_tat']:02d}")
            off_chip.setFixedWidth(58)
            off_chip.setAlignment(Qt.AlignCenter)
            off_chip.setStyleSheet("background:#999; color:white; border-radius:0px; font-weight:800; font-size:15px; padding:4px 0;")
            row_lay.addWidget(off_chip)

            arrow2 = QLabel("TẮT")
            arrow2.setStyleSheet("color:#999; font-weight:700; background:transparent; border:none; font-size:14px;")
            row_lay.addWidget(arrow2)

            row_lay.addStretch(1)
            lay.addWidget(row_frame)

    lay.addStretch(1)
    return card


class SettingTab(QWidget):
    # Phat ra khi nguoi dung bam BACK va LUU THANH CONG (khong bi trung
    # gio/loi validate) - main.py se noi vao ScheduleSyncer de gui xuong
    # ESP32 qua V16 (schedule_saved) / V17 (env_saved).
    schedule_saved = pyqtSignal()
    env_saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # dữ liệu nguồn chung, dùng cho cả trang Tổng quan lẫn trang Chỉnh sửa
        self.env_values = {key: default for (_, default, _, key, _, _) in ENV_ROWS}
        # SUA: doc lai gia tri da luu tu lan truoc (neu co file) - ghi de len
        # default cung o tren, de khong bi mat cau hinh khi mo lai app.
        self._load_env_from_file()

        self.env_spinboxes = {}     # dùng ở trang chỉnh sửa
        self.env_overview_labels = {}  # dùng ở trang tổng quan (readonly)

        # SUA: doc lai lich hoat dong da luu tu lan truoc (neu co file), dung
        # o buoc khoi tao 4 khoi ScheduleSection/LightScheduleSection ben duoi.
        self._saved_schedule = self._load_schedule_from_file()

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
        root = QVBoxLayout(content)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # ================= HÀNG 1: Môi trường (gộp theo thiết bị) + nút Set =================
        row1 = QHBoxLayout()
        row1.setSpacing(16)
        root.addLayout(row1)

        gb_temp = QGroupBox("🌡️ HỆ THỐNG NHIỆT ĐỘ")
        tl = QVBoxLayout(gb_temp)
        tl.addLayout(self._paired_threshold_row(
            "ĐÈN SƯỞI", "BẬT <", "sued_on_temp", "°C", "TẮT >", "sued_off_temp", "°C"))
        tl.addLayout(self._paired_threshold_row(
            "QUẠT", "BẬT >", "quat_on_temp", "°C", "TẮT <", "quat_off_temp", "°C"))
        tl.addStretch(1)
        row1.addWidget(gb_temp, 2)

        gb_humi = QGroupBox("💧 HỆ THỐNG ĐỘ ẨM")
        hl = QVBoxLayout(gb_humi)
        hl.addLayout(self._paired_threshold_row(
            "HÚT ẨM", "BẬT >", "hutam_on", "%", "TẮT <", "hutam_off", "%"))
        hl.addLayout(self._paired_threshold_row(
            "PHUN SƯƠNG", "BẬT <", "phunsuong_on", "%", "TẮT >", "phunsuong_off", "%"))
        hl.addStretch(1)
        row1.addWidget(gb_humi, 2)

        gb_actions = QGroupBox("🛠️ LƯU CẤU HÌNH")
        al = QVBoxLayout(gb_actions)

        btn_env = QPushButton("🌡️\nSET MÔI TRƯỜNG")
        btn_env.setFixedHeight(70)
        btn_env.setStyleSheet(
            f"background:#e9fbe9; border:2px solid {COLOR_ON_GREEN}; border-radius:0px; "
            f"font-weight:700; color:#1c6b2c; font-size:15px;"
        )
        btn_env.clicked.connect(self._goto_edit_env)
        al.addWidget(btn_env)

        btn_sched = QPushButton("➡️\nSET LỊCH")
        btn_sched.setFixedHeight(70)
        btn_sched.setStyleSheet(
            f"background:#e9f0fb; border:2px solid {COLOR_HEADER_BLUE}; border-radius:0px; "
            f"font-weight:700; color:{COLOR_HEADER_BLUE_DARK}; font-size:15px;"
        )
        btn_sched.clicked.connect(self._goto_edit_schedule)
        al.addWidget(btn_sched)

        al.addStretch(1)
        row1.addWidget(gb_actions, 1)

        # ================= HÀNG 2: Lịch hoạt động — 4 cột ngang =================
        gb_sched = QGroupBox("🗓️ LỊCH HOẠT ĐỘNG (đã cài đặt)")
        sl = QVBoxLayout(gb_sched)
        sl.setContentsMargins(10, 14, 10, 10)
        self.schedule_cards_container = QHBoxLayout()
        self.schedule_cards_container.setSpacing(12)
        sl.addLayout(self.schedule_cards_container)
        root.addWidget(gb_sched, 1)

        self._refresh_schedule_summary()
        return page

    def _paired_threshold_row(self, device_label, on_cmp, on_key, on_unit, off_cmp, off_key, off_unit):
        """Dựng 1 dòng kiểu ảnh tham khảo: 'Tên thiết bị: Bật <cmp> [ giá trị ]
        đơn_vị  |  Tắt <cmp> [ giá trị ] đơn_vị' — gộp Bật/Tắt của CÙNG 1
        thiết bị vào chung 1 dòng, dễ đọc hơn hẳn so với liệt kê 8 dòng rời rạc."""
        row = QHBoxLayout()
        lbl_name = QLabel(f"{device_label}:")
        lbl_name.setStyleSheet("font-weight:700;")
        lbl_name.setFixedWidth(95)
        row.addWidget(lbl_name)

        row.addWidget(QLabel(on_cmp))
        box_on = readonly_value_box(str(self.env_values[on_key]))
        self.env_overview_labels[on_key] = box_on
        row.addWidget(box_on)
        row.addWidget(QLabel(on_unit))

        sep = QLabel("   |   ")
        sep.setStyleSheet("color:#bbb;")
        row.addWidget(sep)

        row.addWidget(QLabel(off_cmp))
        box_off = readonly_value_box(str(self.env_values[off_key]))
        self.env_overview_labels[off_key] = box_off
        row.addWidget(box_off)
        row.addWidget(QLabel(off_unit))

        row.addStretch(1)
        return row

    def _refresh_overview_env_labels(self):
        for key, box in self.env_overview_labels.items():
            box.setText(str(self.env_values[key]))

    # ---------------------------------------------------- luu/doc file (moi)
    def _load_env_from_file(self):
        """Doc lai nguong moi truong da luu tu lan truoc (neu co file). Neu
        file chua ton tai (lan dau chay app) hoac loi doc, giu nguyen default
        tu ENV_ROWS - khong lam crash app."""
        if not os.path.exists(ENV_CONFIG_PATH):
            return
        try:
            with open(ENV_CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            valid_keys = {key for (_, _, _, key, _, _) in ENV_ROWS}
            for key, value in saved.items():
                if key in valid_keys:
                    self.env_values[key] = value
        except Exception as e:
            print(f"[SettingTab] Khong the doc {ENV_CONFIG_PATH}: {e}")

    def _save_env_to_file(self):
        """Ghi nguong moi truong hien tai ra file JSON - goi ngay sau khi
        nguoi dung bam BACK va luu thanh cong o trang chinh sua moi truong."""
        try:
            with open(ENV_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.env_values, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SettingTab] Khong the luu {ENV_CONFIG_PATH}: {e}")

    # ------------------------------------------------- luu/doc file lich (moi)
    def _load_schedule_from_file(self):
        """Doc lai LICH HOAT DONG da luu tu lan truoc (neu co file). Tra ve
        dict {"cho_an":[...], "tam":[...], "rua_chuong":[...], "den":[...]}
        dung dinh dang get_all_schedules(), hoac {} neu chua co file/loi doc."""
        if not os.path.exists(SCHEDULE_CONFIG_PATH):
            return {}
        try:
            with open(SCHEDULE_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[SettingTab] Khong the doc {SCHEDULE_CONFIG_PATH}: {e}")
            return {}

    def _save_schedule_to_file(self):
        """Ghi toan bo lich hien tai (ca 4 loai) ra file JSON - goi ngay sau
        khi nguoi dung bam BACK va luu thanh cong o trang chinh sua lich
        (khong co xung dot trung gio/chong lan)."""
        try:
            with open(SCHEDULE_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.get_all_schedules(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SettingTab] Khong the luu {SCHEDULE_CONFIG_PATH}: {e}")

    @staticmethod
    def _rows_to_tuples(saved_rows, keys, fallback):
        """Doi list[dict] (dinh dang luu trong file/get_schedule()) thanh
        list[tuple] (dinh dang ScheduleSection/LightScheduleSection can de
        khoi tao qua default_rows). Neu du lieu rong/hong, dung fallback."""
        if not saved_rows:
            return fallback
        try:
            return [tuple(row[k] for k in keys) for row in saved_rows]
        except (KeyError, TypeError) as e:
            print(f"[SettingTab] Du lieu lich luu bi loi dinh dang, dung mac dinh: {e}")
            return fallback

    def _refresh_schedule_summary(self):
        # xóa hết card cũ trước khi dựng lại (tránh chồng chất mỗi lần refresh)
        while self.schedule_cards_container.count():
            item = self.schedule_cards_container.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        data_map = {
            "cho_an": self.sec_feed.get_schedule() if hasattr(self, "sec_feed") else [],
            "tam": self.sec_tam.get_schedule() if hasattr(self, "sec_tam") else [],
            "rua_chuong": self.sec_rua.get_schedule() if hasattr(self, "sec_rua") else [],
        }

        for key, icon, title, unit, color, bg in SCHEDULE_CATEGORIES:
            card = build_schedule_card(icon, title, unit, color, bg, data_map[key])
            self.schedule_cards_container.addWidget(card)

        # Đèn dùng định dạng dữ liệu khác (giờ bật/giờ tắt) nên dùng card riêng
        den_rows = self.sec_den.get_schedule() if hasattr(self, "sec_den") else []
        self.schedule_cards_container.addWidget(build_light_schedule_card(den_rows))

    # ==================================================================
    # TRANG 1 — CHỈNH SỬA MÔI TRƯỜNG + ĐỘNG CƠ (có nút BACK)
    # ==================================================================
    def _build_edit_env_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)

        header = QHBoxLayout()
        title = QLabel("CHỈNH SỬA: MÔI TRƯỜNG + ĐỘNG CƠ")
        title.setStyleSheet(f"font-weight:700; color:{COLOR_HEADER_BLUE}; font-size:18px;")
        header.addWidget(title)
        header.addStretch(1)
        btn_back = QPushButton("⬅ BACK")
        btn_back.setStyleSheet(
            f"background:{COLOR_HEADER_BLUE}; color:white; font-weight:700; border-radius:0px; padding:6px 16px;"
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
        note.setStyleSheet("color:#555; font-size:14px; padding-top:10px;")
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
        self._save_env_to_file()  # SUA: ghi ra dia ngay, khong con bi mat khi tat/mo lai app
        self.stack.setCurrentIndex(0)
        self.env_saved.emit()

    # ==================================================================
    # TRANG 2 — CHỈNH SỬA LỊCH HOẠT ĐỘNG (có nút BACK)
    # ==================================================================
    def _build_edit_schedule_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)

        header = QHBoxLayout()
        title = QLabel("CHỈNH SỬA: LỊCH HOẠT ĐỘNG")
        title.setStyleSheet(f"font-weight:700; color:{COLOR_HEADER_BLUE}; font-size:18px;")
        header.addWidget(title)
        header.addStretch(1)
        btn_back = QPushButton("⬅ BACK")
        btn_back.setStyleSheet(
            f"background:{COLOR_HEADER_BLUE}; color:white; font-weight:700; border-radius:0px; padding:6px 16px;"
        )
        btn_back.clicked.connect(self._back_from_edit_schedule)
        header.addWidget(btn_back)
        outer.addLayout(header)

        self.lbl_schedule_page_warning = QLabel("")
        self.lbl_schedule_page_warning.setWordWrap(True)
        self.lbl_schedule_page_warning.setStyleSheet(
            f"background:#fdeaea; border:1px solid {COLOR_ALARM_RED}; border-radius:0px; "
            f"color:#a52020; font-weight:700; padding:8px; font-size:15px;"
        )
        self.lbl_schedule_page_warning.hide()
        outer.addWidget(self.lbl_schedule_page_warning)

        row = QHBoxLayout()
        outer.addLayout(row)

        # Cho ăn: theo GRAM (đúng với hệ cân cám loadcell + động cơ bước)
        # SUA: uu tien dung du lieu da luu tu lan truoc (self._saved_schedule),
        # chi roi ve default cung nay neu chua tung luu gi / file loi.
        self.sec_feed = ScheduleSection(
            "Cho ăn", "Khối lượng", "gram", (0, 2000),
            default_rows=self._rows_to_tuples(
                self._saved_schedule.get("cho_an"), ("gio", "phut", "value"),
                fallback=[(6, 0, 100), (12, 0, 100), (18, 0, 100)]
            )
        )
        row.addWidget(self.sec_feed)

        # Tắm: theo GIÂY (bơm 12V chạy theo thời gian) — is_duration_based=True
        # để kiểm tra CHỒNG LẤN khoảng thời gian thực sự (không chỉ trùng mốc)
        self.sec_tam = ScheduleSection(
            "Tắm", "Thời gian chạy", "giây", (0, 600),
            default_rows=self._rows_to_tuples(
                self._saved_schedule.get("tam"), ("gio", "phut", "value"),
                fallback=[(8, 0, 80), (14, 0, 80)]
            ),
            is_duration_based=True,
        )
        row.addWidget(self.sec_tam)

        # Rửa chuồng: theo GIÂY (bơm sàn 5V chạy theo thời gian) — tương tự Tắm
        self.sec_rua = ScheduleSection(
            "Rửa chuồng", "Thời gian chạy", "giây", (0, 600),
            default_rows=self._rows_to_tuples(
                self._saved_schedule.get("rua_chuong"), ("gio", "phut", "value"),
                fallback=[(7, 0, 200), (19, 0, 200)]
            ),
            is_duration_based=True,
        )
        row.addWidget(self.sec_rua)

        # Đèn: theo cặp GIỜ BẬT / GIỜ TẮT (không có thời lượng như 3 loại trên)
        self.sec_den = LightScheduleSection(
            default_rows=self._rows_to_tuples(
                self._saved_schedule.get("den"), ("gio_bat", "phut_bat", "gio_tat", "phut_tat"),
                fallback=[(18, 0, 22, 0)]
            )
        )
        row.addWidget(self.sec_den)

        return page

    def _goto_edit_schedule(self):
        self.lbl_schedule_page_warning.hide()
        self.stack.setCurrentIndex(2)

    def _back_from_edit_schedule(self):
        # kiểm tra trùng giờ ở cả 4 loại lịch trước khi cho phép rời trang
        dup_feed = self.sec_feed.has_duplicates()
        dup_tam = self.sec_tam.has_duplicates()
        dup_rua = self.sec_rua.has_duplicates()
        dup_den = self.sec_den.has_duplicates()

        if dup_feed or dup_tam or dup_rua or dup_den:
            loai_trung = []
            if dup_feed:
                loai_trung.append("Cho ăn")
            if dup_tam:
                loai_trung.append("Tắm")
            if dup_rua:
                loai_trung.append("Rửa chuồng")
            if dup_den:
                loai_trung.append("Đèn")
            self.lbl_schedule_page_warning.setText(
                "⚠️ Không thể lưu: mục [" + ", ".join(loai_trung) + "] đang có mốc giờ bị "
                "trùng nhau (tô đỏ bên dưới). Vui lòng sửa lại giờ khác nhau cho từng dòng "
                "trước khi quay lại."
            )
            self.lbl_schedule_page_warning.show()
            return  # KHÔNG rời trang, giữ nguyên ở màn hình chỉnh sửa

        self.lbl_schedule_page_warning.hide()
        self._refresh_schedule_summary()
        self._save_schedule_to_file()  # SUA: ghi ra dia ngay, khong con bi mat khi tat/mo lai app
        self.stack.setCurrentIndex(0)
        self.schedule_saved.emit()

    # ------------------------------------------------------------------
    def get_env_values(self):
        return dict(self.env_values)

    def get_all_schedules(self):
        return {
            "cho_an": self.sec_feed.get_schedule(),
            "tam": self.sec_tam.get_schedule(),
            "rua_chuong": self.sec_rua.get_schedule(),
            "den": self.sec_den.get_schedule(),
        }