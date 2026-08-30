# -*- coding: utf-8 -*-
"""
schedule_section.py — Khối quản lý lịch cho 1 loại hoạt động (Cho ăn / Tắm / Rửa chuồng / Đèn).
Tách riêng thành widget dùng chung để nhúng trực tiếp vào tab SETTING (không
còn mở qua QDialog/cửa sổ riêng nữa).

LOGIC CHỐNG CHỒNG LẤN LỊCH (nâng cấp, thay cho kiểu "trùng đúng 1 mốc giờ"
cũ - vốn bỏ lọt rất nhiều trường hợp thực tế nguy hiểm):

  1. TẮM / RỬA CHUỒNG (có thời lượng chạy tính bằng GIÂY): 1 lịch không chỉ
     là 1 ĐIỂM giờ:phút, mà là 1 KHOẢNG [giờ:phút, giờ:phút + thời_lượng).
     Vì thời lượng tính bằng giây trong khi giờ bắt đầu chỉ chọn được theo
     phút, 2 lịch NHÌN THÌ KHÁC GIỜ vẫn có thể chồng lấn thật (ví dụ Tắm
     08:00 chạy 80s kết thúc thật lúc 08:01:20, đè lên lịch Tắm 08:01 bắt
     đầu ngay trong lúc lịch trước còn đang chạy) - nên toàn bộ phép so
     sánh dưới đây làm việc ở ĐƠN VỊ GIÂY, không làm tròn về phút.
  2. ĐÈN (có GIỜ BẬT + GIỜ TẮT riêng): áp dụng đúng logic khoảng [bật, tắt),
     kể cả trường hợp HẸN QUA ĐÊM (giờ tắt nhỏ hơn giờ bật, vd 22:00->06:00)
     - được coi là khoảng vắt qua nửa đêm, không phải lỗi.
  3. GIỜ BẬT = GIỜ TẮT (khoảng thời gian bằng 0) bị chặn RIÊNG, xem là lỗi
     nhập liệu (không phải "chồng lấn"), vì firmware sẽ bật rồi tắt gần
     như ngay lập tức trong cùng 1 chu kỳ kiểm tra, vô nghĩa về mặt vận
     hành.
  4. HAI KHUNG SÁT RANH GIỚI (vd 18:00-19:00 và 19:00-20:00) được COI LÀ
     HỢP LỆ (không chồng lấn) - vì tại đúng 19:00, relay chỉ đơn giản
     chuyển thẳng từ "đang tắt vì khung 1 kết thúc" sang "đang bật vì
     khung 2 bắt đầu", không có xung đột lệnh thực sự nào cả.

  `has_duplicates()` (giữ nguyên tên hàm để không phải sửa lại chỗ gọi ở
  SettingTab) giờ trả về True nếu có BẤT KỲ xung đột nào ở trên (chồng lấn
  HOẶC giờ bật = giờ tắt) - SettingTab dùng kết quả này để CHẶN NÚT BACK,
  không cho lưu lịch cho tới khi người dùng sửa hết xung đột.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QVBoxLayout, QGroupBox, QTableWidget, QPushButton, QSpinBox, QHeaderView, QLabel
)

DUPLICATE_STYLE = "QSpinBox { border: 2px solid #d13c3c; background: #fdeaea; }"
NORMAL_STYLE = "QSpinBox { border: 1px solid #b9b28e; background: white; }"

SECONDS_PER_DAY = 86400


def _normalize_interval(start_sec, end_sec):
    """Chuẩn hóa 1 khoảng [start, end) về dạng các đoạn TUYẾN TÍNH (không
    vắt qua nửa đêm), tách thành 2 đoạn nếu khoảng gốc vắt qua 0h - vì lịch
    lặp lại MỖI NGÀY, phần "tràn" qua nửa đêm phải được coi là đè lên đúng
    đầu ngày hôm sau (và mọi ngày khác, do lặp lại), nên tách thành:
      [start, 86400) và [0, end - 86400)
    Nếu không vắt qua nửa đêm, trả về nguyên 1 đoạn [start, end)."""
    if end_sec > start_sec:
        return [(start_sec, end_sec)]
    # end_sec <= start_sec: vat qua nua dem (da duoc dam bao khong bang
    # nhau boi ham goi truoc do - xem kiem tra do_dai_bang_0 rieng)
    wrapped_end = end_sec + SECONDS_PER_DAY
    return [(start_sec, SECONDS_PER_DAY), (0, wrapped_end - SECONDS_PER_DAY)]


def _segments_overlap(seg_a, seg_b):
    """2 doan tuyen tinh [a1,a2) va [b1,b2) chong lan THAT SU (khong tinh
    cham dung ranh gioi a2==b1) khi va chi khi a1 < b2 VA b1 < a2."""
    a1, a2 = seg_a
    b1, b2 = seg_b
    return a1 < b2 and b1 < a2


def intervals_overlap(a_start, a_end, b_start, b_end):
    """True neu 2 khoang [a_start,a_end) va [b_start,b_end) (theo giay
    trong ngay, co the vat qua nua dem) chong lan THAT SU voi nhau."""
    segs_a = _normalize_interval(a_start, a_end)
    segs_b = _normalize_interval(b_start, b_end)
    return any(_segments_overlap(sa, sb) for sa in segs_a for sb in segs_b)


def format_hms(total_seconds):
    """Format so giay-trong-ngay (co the > 86400 do vat qua nua dem) thanh
    chuoi gio:phut:giay de hien thi canh bao de hieu."""
    total_seconds = total_seconds % SECONDS_PER_DAY
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if s else f"{h:02d}:{m:02d}"


class ScheduleSection(QGroupBox):
    """Một khối quản lý lịch cho 1 loại hoạt động (Cho ăn / Tắm / Rửa chuồng).

    is_duration_based=True (dùng cho Tắm/Rửa chuồng, "value" = thời lượng
    chạy tính bằng GIÂY): kiểm tra CHỒNG LẤN KHOẢNG THỜI GIAN thực sự, chính
    xác tới giây (xem intervals_overlap() ở đầu file).

    is_duration_based=False (mặc định, dùng cho Cho ăn - không có khái niệm
    "thời lượng chạy" đáng tin cậy vì phụ thuộc tốc độ xả cám thực tế): giữ
    nguyên kiểu kiểm tra TRÙNG ĐÚNG 1 MỐC giờ:phút như trước."""

    def __init__(self, title, value_label, value_unit, value_range, default_rows,
                 is_duration_based=False):
        super().__init__(title)
        self.value_label = value_label
        self.value_unit = value_unit
        self.value_range = value_range  # (lo, hi)
        self.is_duration_based = is_duration_based
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
        # SUA: bo setFixedHeight(150) - day la 1 "bang du lieu" (treeview),
        # CHO PHEP no gian lap day khong gian con lai trong khung.
        root.addWidget(self.table, 1)

        btn_add = QPushButton(f"+ Thêm lịch {self.title().lower()}")
        btn_add.clicked.connect(self._add_row_auto_time)
        root.addWidget(btn_add)

        self.lbl_warning = QLabel("")
        self.lbl_warning.setWordWrap(True)
        self.lbl_warning.setStyleSheet("color:#d13c3c; font-weight:700; font-size:14px; padding-top:4px;")
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
        sp_val.valueChanged.connect(self._check_duplicates)  # đổi thời lượng cũng có thể gây/hết chồng lấn
        self.table.setCellWidget(row, 2, sp_val)

        btn_del = QPushButton("Xóa")
        btn_del.setStyleSheet("background:#d13c3c; color:white; border-radius:0px;")
        btn_del.clicked.connect(lambda: self._delete_row_by_widget(btn_del))
        self.table.setCellWidget(row, 3, btn_del)

    def _delete_row_by_widget(self, widget):
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 3) is widget:
                self.table.removeRow(row)
                break
        self._check_duplicates()

    # ------------------------------------------------------- chống trùng/chồng lấn giờ
    def _check_duplicates(self):
        """Cho ăn (is_duration_based=False): kiểm tra TRÙNG ĐÚNG 1 MỐC như cũ.
        Tắm/Rửa chuồng (is_duration_based=True): kiểm tra CHỒNG LẤN KHOẢNG
        THỜI GIAN thực sự [giờ:phút, giờ:phút + thời_lượng_giây), chính xác
        tới giây - phát hiện được cả trường hợp 2 mốc KHÁC PHÚT nhưng vẫn
        đè lên nhau (vd 08:00 chạy 80s và 08:01 chạy 80s)."""
        n = self.table.rowCount()
        rows = []
        for r in range(n):
            sp_gio = self.table.cellWidget(r, 0)
            sp_phut = self.table.cellWidget(r, 1)
            sp_val = self.table.cellWidget(r, 2)
            if sp_gio is None or sp_phut is None:
                continue
            rows.append((r, sp_gio, sp_phut, sp_val))

        bad_rows = set()   # index vào `rows` bị lỗi (chồng lấn hoặc thời lượng = 0)
        messages = []

        if self.is_duration_based:
            intervals = []
            for i, (r, sp_gio, sp_phut, sp_val) in enumerate(rows):
                start = sp_gio.value() * 3600 + sp_phut.value() * 60
                duration = sp_val.value()
                if duration <= 0:
                    bad_rows.add(i)
                    messages.append(f"{sp_gio.value():02d}:{sp_phut.value():02d} có thời gian chạy = 0")
                    continue
                intervals.append((i, start, start + duration))

            for a in range(len(intervals)):
                ia, sa, ea = intervals[a]
                for b in range(a + 1, len(intervals)):
                    ib, sb, eb = intervals[b]
                    if intervals_overlap(sa, ea, sb, eb):
                        bad_rows.add(ia)
                        bad_rows.add(ib)
                        _, gio_a, phut_a, _ = rows[ia]
                        _, gio_b, phut_b, _ = rows[ib]
                        messages.append(
                            f"{gio_a.value():02d}:{phut_a.value():02d} (đến {format_hms(ea)}) "
                            f"chồng lấn {gio_b.value():02d}:{phut_b.value():02d} (đến {format_hms(eb)})"
                        )
        else:
            counts = {}
            for i, (r, sp_gio, sp_phut, sp_val) in enumerate(rows):
                t = (sp_gio.value(), sp_phut.value())
                counts.setdefault(t, []).append(i)
            for t, idxs in counts.items():
                if len(idxs) > 1:
                    bad_rows.update(idxs)
                    messages.append(f"{t[0]:02d}:{t[1]:02d} bị trùng ({len(idxs)} dòng)")

        has_dup = len(bad_rows) > 0
        for i, (r, sp_gio, sp_phut, sp_val) in enumerate(rows):
            style = DUPLICATE_STYLE if i in bad_rows else NORMAL_STYLE
            sp_gio.setStyleSheet(style)
            sp_phut.setStyleSheet(style)
            if sp_val is not None:
                sp_val.setStyleSheet(style if (self.is_duration_based and i in bad_rows) else NORMAL_STYLE)

        if has_dup:
            self.lbl_warning.setText("; ".join(messages) + " — vui lòng chỉnh lại trước khi lưu.")
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


class LightScheduleSection(QGroupBox):
    """Khối quản lý lịch CHIẾU SÁNG — khác với ScheduleSection ở chỗ đèn không
    có 'thời gian chạy' (duration) mà có 1 cặp GIỜ BẬT + GIỜ TẮT cho mỗi dòng
    (vd bật 18:00, tắt 22:00). Có thể thêm nhiều dòng nếu cần bật/tắt nhiều
    khung giờ trong ngày (vd thêm 1 khung buổi sáng sớm)."""

    def __init__(self, default_rows):
        super().__init__("Chiếu sáng (Đèn)")
        self._build_ui()
        for gio_bat, phut_bat, gio_tat, phut_tat in default_rows:
            self._add_row(gio_bat, phut_bat, gio_tat, phut_tat)
        self._check_duplicates()

    def _build_ui(self):
        root = QVBoxLayout(self)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Giờ bật", "Phút bật", "Giờ tắt", "Phút tắt", ""])
        for col in range(4):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        # SUA: bo setFixedHeight(150) - cho phep bang gian lap day khong gian.
        root.addWidget(self.table, 1)

        btn_add = QPushButton("+ Thêm khung giờ chiếu sáng")
        btn_add.clicked.connect(self._add_row_auto_time)
        root.addWidget(btn_add)

        self.lbl_warning = QLabel("")
        self.lbl_warning.setWordWrap(True)
        self.lbl_warning.setStyleSheet("color:#d13c3c; font-weight:700; font-size:14px; padding-top:4px;")
        root.addWidget(self.lbl_warning)

    def _find_free_on_time(self):
        used = {(self.table.cellWidget(r, 0).value(), self.table.cellWidget(r, 1).value())
                for r in range(self.table.rowCount())}
        for offset in range(24):
            gio = (18 + offset) % 24  # đèn thường bật buổi tối, dò bắt đầu từ 18h
            if (gio, 0) not in used:
                return gio, 0
        return 18, 0

    def _add_row_auto_time(self):
        gio_bat, phut_bat = self._find_free_on_time()
        gio_tat = (gio_bat + 3) % 24  # mặc định bật 3 tiếng, có thể sửa lại
        self._add_row(gio_bat, phut_bat, gio_tat, 0)
        self._check_duplicates()

    def _add_row(self, gio_bat=18, phut_bat=0, gio_tat=22, phut_tat=0):
        row = self.table.rowCount()
        self.table.insertRow(row)

        def make_spin(rng, val, on_change):
            sp = QSpinBox()
            sp.setRange(*rng)
            sp.setValue(val)
            sp.setAlignment(Qt.AlignCenter)
            sp.valueChanged.connect(on_change)
            return sp

        self.table.setCellWidget(row, 0, make_spin((0, 23), gio_bat, self._check_duplicates))
        self.table.setCellWidget(row, 1, make_spin((0, 59), phut_bat, self._check_duplicates))
        self.table.setCellWidget(row, 2, make_spin((0, 23), gio_tat, self._check_duplicates))
        self.table.setCellWidget(row, 3, make_spin((0, 59), phut_tat, self._check_duplicates))

        btn_del = QPushButton("Xóa")
        btn_del.setStyleSheet("background:#d13c3c; color:white; border-radius:0px;")
        btn_del.clicked.connect(lambda: self._delete_row_by_widget(btn_del))
        self.table.setCellWidget(row, 4, btn_del)

    def _delete_row_by_widget(self, widget):
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 4) is widget:
                self.table.removeRow(row)
                break
        self._check_duplicates()

    def _check_duplicates(self):
        """Kiểm tra CHỒNG LẤN KHOẢNG [giờ bật, giờ tắt) thực sự giữa các
        dòng - hỗ trợ ĐÚNG cả trường hợp hẹn QUA ĐÊM (giờ tắt < giờ bật, vd
        22:00 -> 06:00, coi là khoảng vắt qua nửa đêm chứ không phải lỗi).
        Riêng trường hợp GIỜ BẬT = GIỜ TẮT (khoảng thời gian bằng 0) bị chặn
        RIÊNG với thông báo rõ ràng, vì đó là lỗi nhập liệu, không phải chồng
        lấn. 2 khung SÁT RANH GIỚI (vd 18:00-19:00 và 19:00-20:00) được coi
        là HỢP LỆ (không chồng lấn thật)."""
        n = self.table.rowCount()
        rows = []
        for r in range(n):
            sp_gb = self.table.cellWidget(r, 0)
            sp_pb = self.table.cellWidget(r, 1)
            sp_gt = self.table.cellWidget(r, 2)
            sp_pt = self.table.cellWidget(r, 3)
            if None in (sp_gb, sp_pb, sp_gt, sp_pt):
                continue
            rows.append((r, sp_gb, sp_pb, sp_gt, sp_pt))

        bad_rows = set()
        messages = []
        intervals = []

        for i, (r, sp_gb, sp_pb, sp_gt, sp_pt) in enumerate(rows):
            start = sp_gb.value() * 3600 + sp_pb.value() * 60
            end = sp_gt.value() * 3600 + sp_pt.value() * 60
            if start == end:
                bad_rows.add(i)
                messages.append(f"{sp_gb.value():02d}:{sp_pb.value():02d} có giờ bật = giờ tắt")
                continue
            intervals.append((i, start, end))

        for a in range(len(intervals)):
            ia, sa, ea = intervals[a]
            for b in range(a + 1, len(intervals)):
                ib, sb, eb = intervals[b]
                if intervals_overlap(sa, ea, sb, eb):
                    bad_rows.add(ia)
                    bad_rows.add(ib)
                    _, gb_a, pb_a, gt_a, pt_a = rows[ia]
                    _, gb_b, pb_b, gt_b, pt_b = rows[ib]
                    messages.append(
                        f"{gb_a.value():02d}:{pb_a.value():02d}-{gt_a.value():02d}:{pt_a.value():02d} "
                        f"chồng lấn {gb_b.value():02d}:{pb_b.value():02d}-{gt_b.value():02d}:{pt_b.value():02d}"
                    )

        has_dup = len(bad_rows) > 0
        for i, (r, sp_gb, sp_pb, sp_gt, sp_pt) in enumerate(rows):
            style = DUPLICATE_STYLE if i in bad_rows else NORMAL_STYLE
            sp_gb.setStyleSheet(style)
            sp_pb.setStyleSheet(style)
            sp_gt.setStyleSheet(style)
            sp_pt.setStyleSheet(style)

        if has_dup:
            self.lbl_warning.setText("; ".join(messages) + " — vui lòng chỉnh lại trước khi lưu.")
        else:
            self.lbl_warning.setText("")

        return has_dup

    def has_duplicates(self):
        return self._check_duplicates()

    def get_schedule(self):
        """Trả về list dict [{gio_bat, phut_bat, gio_tat, phut_tat}, ...]."""
        result = []
        for row in range(self.table.rowCount()):
            result.append({
                "gio_bat": self.table.cellWidget(row, 0).value(),
                "phut_bat": self.table.cellWidget(row, 1).value(),
                "gio_tat": self.table.cellWidget(row, 2).value(),
                "phut_tat": self.table.cellWidget(row, 3).value(),
            })
        return result

