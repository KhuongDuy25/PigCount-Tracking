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
  5. THÊM MỚI - "THỨ TRONG TUẦN": mỗi dòng lịch giờ có thêm 1 nút chọn
     "áp dụng vào thứ nào" (mặc định = cả 7 ngày, tức chạy hàng ngày như
     hành vi cũ, để không phá vỡ lịch đã lưu từ trước khi có tính năng
     này). HAI DÒNG CHỈ ĐƯỢC COI LÀ CHỒNG LẤN NẾU CẢ GIỜ LẪN THỨ ĐỀU GIAO
     NHAU - ví dụ Cho ăn 08:00 (Hàng ngày) và Cho ăn 08:00 (chỉ Chủ nhật)
     vẫn được coi là XUNG ĐỘT (vì Chủ nhật thuộc "hàng ngày"), nhưng Tắm
     08:00-08:02 (T2-T6) và Tắm 08:00-08:02 (T7, CN) thì KHÔNG xung đột vì
     không ngày nào trùng nhau.
  6. THÊM MỚI - "KHOẢNG CÁCH TỐI THIỂU GIỮA 2 LẦN" (chỉ áp dụng cho loại
     KHÔNG có thời lượng chạy thật, tức Cho ăn): trước đây 2 dòng Cho ăn
     chỉ bị chặn khi TRÙNG ĐÚNG 1 phút - nghĩa là 2 mốc cách nhau 1 phút
     (vd 13:24 và 13:25) vẫn được coi là hợp lệ, dù đợt xả cám trước có
     thể CHƯA CHẠY XONG. Giờ có thêm 1 ô "Cách nhau tối thiểu" (mặc định 5
     phút, người dùng tự chỉnh trong SETTING) - 2 mốc cách nhau ÍT HƠN số
     phút này (và có chung ít nhất 1 thứ) sẽ bị báo lỗi, dùng LẠI đúng
     logic chồng lấn khoảng thời gian (intervals_overlap()) như Tắm/Rửa
     chuồng, chỉ khác là thời lượng dùng chung 1 giá trị cấu hình thay vì
     mỗi dòng 1 giá trị riêng. Đặt về 0 phút để quay lại kiểu chặn "trùng
     đúng phút" như cũ (không bắt buộc phải có khoảng cách).

  `has_duplicates()` (giữ nguyên tên hàm để không phải sửa lại chỗ gọi ở
  SettingTab) giờ trả về True nếu có BẤT KỲ xung đột nào ở trên (chồng lấn
  HOẶC giờ bật = giờ tắt HOẶC chưa chọn ngày áp dụng nào) - SettingTab dùng
  kết quả này để CHẶN NÚT BACK, không cho lưu lịch cho tới khi người dùng
  sửa hết xung đột.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QTableWidget, QPushButton, QSpinBox, QHeaderView, QLabel,
    QMenu, QWidgetAction, QCheckBox, QWidget, QGridLayout
)

DUPLICATE_STYLE = "QSpinBox { border: 2px solid #d13c3c; background: #fdeaea; }"
NORMAL_STYLE = "QSpinBox { border: 1px solid #b9b28e; background: white; }"
DAY_BTN_DUPLICATE_STYLE = (
    "QPushButton { border: 2px solid #d13c3c; background: #fdeaea; padding: 4px 6px; }"
)
DAY_BTN_NORMAL_STYLE = (
    "QPushButton { border: 1px solid #b9b28e; background: white; padding: 4px 6px; }"
)

SECONDS_PER_DAY = 86400

# ---------------------------------------------------------------- THỨ TRONG TUẦN
# Quy ước GIỐNG với scheduler.py (ALL_WEEKDAYS = [1..7]): 1=Thứ 2 ... 7=Chủ nhật.
WEEKDAY_LABELS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
ALL_DAYS = list(range(1, 8))
WEEKDAY_PRESET = [1, 2, 3, 4, 5]   # Thứ 2 - Thứ 6
WEEKEND_PRESET = [6, 7]            # Thứ 7, Chủ nhật


def format_days(days):
    """Đổi 1 tập hợp thứ ({1..7}) thành chuỗi hiển thị ngắn gọn trên nút bấm."""
    days_set = set(days)
    if not days_set:
        return "Chưa chọn ngày"
    if days_set == set(ALL_DAYS):
        return "Hàng ngày"
    if days_set == set(WEEKDAY_PRESET):
        return "T2 - T6"
    if days_set == set(WEEKEND_PRESET):
        return "T7, CN"
    return ", ".join(WEEKDAY_LABELS[d - 1] for d in sorted(days_set))


def days_overlap(days_a, days_b):
    """True nếu 2 tập hợp thứ có ÍT NHẤT 1 ngày chung nhau."""
    return bool(set(days_a) & set(days_b))


class DayPickerButton(QPushButton):
    """Nút bấm mở popup chọn 'thứ trong tuần' áp dụng cho 1 dòng lịch.
    Mặc định chọn cả 7 ngày (= chạy hàng ngày, giữ nguyên hành vi cũ cho
    các lịch đã lưu từ trước khi có tính năng này).

    Dùng QMenu chứa 1 QWidgetAction bọc các QCheckBox thay vì QAction
    thường - để bấm tick từng thứ KHÔNG làm menu tự đóng lại (khác hành vi
    mặc định của QAction), cho phép chọn nhiều thứ liên tiếp trong 1 lần mở."""

    def __init__(self, days=None, on_change=None):
        super().__init__()
        self.selected_days = set(days) if days else set(ALL_DAYS)
        self.on_change = on_change
        self.setStyleSheet(DAY_BTN_NORMAL_STYLE)
        self._refresh_text()
        self.clicked.connect(self._open_menu)

    def _refresh_text(self):
        self.setText(format_days(self.selected_days))

    def _notify_change(self):
        self._refresh_text()
        if self.on_change:
            self.on_change()

    def _open_menu(self):
        menu = QMenu(self)

        def apply_preset(days):
            self.selected_days = set(days)
            self._notify_change()
            menu.close()

        act_all = menu.addAction("Hàng ngày")
        act_all.triggered.connect(lambda: apply_preset(ALL_DAYS))
        act_wd = menu.addAction("Thứ 2 - Thứ 6")
        act_wd.triggered.connect(lambda: apply_preset(WEEKDAY_PRESET))
        act_we = menu.addAction("Cuối tuần (T7, CN)")
        act_we.triggered.connect(lambda: apply_preset(WEEKEND_PRESET))
        menu.addSeparator()

        # 7 checkbox chọn riêng lẻ từng thứ, gom vào 1 QWidgetAction.
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(10, 6, 10, 6)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        for i, label in enumerate(WEEKDAY_LABELS):
            day = i + 1
            cb = QCheckBox(label)
            cb.setChecked(day in self.selected_days)
            cb.stateChanged.connect(lambda state, d=day: self._toggle_day(d, state))
            grid.addWidget(cb, i // 4, i % 4)

        widget_action = QWidgetAction(menu)
        widget_action.setDefaultWidget(container)
        menu.addAction(widget_action)

        menu.addSeparator()
        act_done = menu.addAction("Xong")
        act_done.triggered.connect(menu.close)

        menu.exec_(self.mapToGlobal(self.rect().bottomLeft()))

    def _toggle_day(self, day, state):
        if state:
            self.selected_days.add(day)
        else:
            self.selected_days.discard(day)
        self._notify_change()

    def get_days(self):
        return sorted(self.selected_days)

    def set_error_style(self, is_error):
        self.setStyleSheet(DAY_BTN_DUPLICATE_STYLE if is_error else DAY_BTN_NORMAL_STYLE)


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
    nguyên kiểu kiểm tra TRÙNG ĐÚNG 1 MỐC giờ:phút như trước.

    Mỗi dòng còn có 1 DayPickerButton chọn "thứ trong tuần" áp dụng (mặc
    định = Hàng ngày). 2 dòng CHỈ bị coi là chồng lấn nếu vừa trùng/chồng
    giờ VỪA có ít nhất 1 ngày chung nhau (xem days_overlap())."""

    def __init__(self, title, value_label, value_unit, value_range, default_rows,
                 is_duration_based=False, min_gap_minutes=5):
        super().__init__(title)
        self.value_label = value_label
        self.value_unit = value_unit
        self.value_range = value_range  # (lo, hi)
        self.is_duration_based = is_duration_based
        # SUA: THEM MOI - "khoang cach toi thieu giua 2 lan" (chi dung cho
        # loai KHONG co thoi luong that su, vd Cho an - vi Tam/Rua chuong
        # da tu bao ve bang chinh thoi luong chay that cua tung dong roi).
        # Truoc day cac dong loai nay chi bi chan khi TRUNG DUNG 1 phut,
        # nen 2 dong cach nhau 1 phut (vd 13:24 va 13:25) van duoc coi la
        # hop le du lan xa cam truoc co the chua chay xong.
        self.default_min_gap_minutes = min_gap_minutes
        self._build_ui()
        for row_data in default_rows:
            # Cho phep truyen tuple 3 phan tu (gio, phut, val) - hanh vi cu,
            # hoac 4 phan tu (gio, phut, val, thu) - khi da co du lieu ngay.
            if len(row_data) == 4:
                gio, phut, val, thu = row_data
            else:
                gio, phut, val = row_data
                thu = None
            self._add_row(gio, phut, val, thu)
        self._check_duplicates()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # SUA: THEM MOI - o cai dat "khoang cach toi thieu giua 2 lan" chi
        # hien voi loai KHONG duration_based (Cho an) - Tam/Rua chuong da
        # co "thoi luong chay" rieng cho tung dong nen khong can o nay.
        if not self.is_duration_based:
            gap_row = QHBoxLayout()
            gap_lbl = QLabel("Cách nhau tối thiểu giữa 2 lần:")
            gap_lbl.setStyleSheet("font-weight:600;")
            gap_row.addWidget(gap_lbl)

            self.sp_min_gap = QSpinBox()
            self.sp_min_gap.setRange(0, 180)
            self.sp_min_gap.setValue(self.default_min_gap_minutes)
            self.sp_min_gap.setSuffix(" phút")
            self.sp_min_gap.setAlignment(Qt.AlignCenter)
            self.sp_min_gap.valueChanged.connect(self._check_duplicates)
            gap_row.addWidget(self.sp_min_gap)
            gap_row.addStretch(1)
            root.addLayout(gap_row)
        else:
            self.sp_min_gap = None

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Giờ", "Phút", f"{self.value_label} ({self.value_unit})", "Thứ", ""]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
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
        bắt đầu dò từ 6:00 rồi vòng qua 0-23h, để dòng mới thêm KHÔNG bị trùng ngay.
        (Chỉ xét theo giờ:phút, không xét thứ - vì đây chỉ là gợi ý ban đầu,
        người dùng vẫn có thể chỉnh lại thứ sau khi thêm dòng.)"""
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

    def _add_row(self, gio=6, phut=0, val=None, thu=None):
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

        btn_thu = DayPickerButton(days=thu, on_change=self._check_duplicates)
        self.table.setCellWidget(row, 3, btn_thu)

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

    # ------------------------------------------------------- chống trùng/chồng lấn giờ + thứ
    def _check_duplicates(self):
        """Cho ăn (is_duration_based=False): kiểm tra TRÙNG ĐÚNG 1 MỐC như cũ.
        Tắm/Rửa chuồng (is_duration_based=True): kiểm tra CHỒNG LẤN KHOẢNG
        THỜI GIAN thực sự [giờ:phút, giờ:phút + thời_lượng_giây), chính xác
        tới giây - phát hiện được cả trường hợp 2 mốc KHÁC PHÚT nhưng vẫn
        đè lên nhau (vd 08:00 chạy 80s và 08:01 chạy 80s).

        THÊM MỚI: 2 dòng chỉ thực sự xung đột nếu VỪA trùng/chồng giờ VỪA
        có ít nhất 1 THỨ chung nhau (days_overlap()). Ngoài ra, dòng nào
        CHƯA chọn thứ nào cả cũng bị coi là lỗi (lịch không bao giờ chạy)."""
        n = self.table.rowCount()
        rows = []
        for r in range(n):
            sp_gio = self.table.cellWidget(r, 0)
            sp_phut = self.table.cellWidget(r, 1)
            sp_val = self.table.cellWidget(r, 2)
            btn_thu = self.table.cellWidget(r, 3)
            if sp_gio is None or sp_phut is None or btn_thu is None:
                continue
            rows.append((r, sp_gio, sp_phut, sp_val, btn_thu))

        bad_rows = set()   # index vào `rows` bị lỗi (chồng lấn hoặc thời lượng = 0 hoặc thiếu thứ)
        messages = []

        # -- Lỗi riêng: chưa chọn ngày nào --
        for i, (r, sp_gio, sp_phut, sp_val, btn_thu) in enumerate(rows):
            if not btn_thu.get_days():
                bad_rows.add(i)
                messages.append(f"{sp_gio.value():02d}:{sp_phut.value():02d} chưa chọn thứ áp dụng")

        if self.is_duration_based:
            intervals = []
            for i, (r, sp_gio, sp_phut, sp_val, btn_thu) in enumerate(rows):
                start = sp_gio.value() * 3600 + sp_phut.value() * 60
                duration = sp_val.value()
                if duration <= 0:
                    bad_rows.add(i)
                    messages.append(f"{sp_gio.value():02d}:{sp_phut.value():02d} có thời gian chạy = 0")
                    continue
                intervals.append((i, start, start + duration, btn_thu.get_days()))

            for a in range(len(intervals)):
                ia, sa, ea, days_a = intervals[a]
                for b in range(a + 1, len(intervals)):
                    ib, sb, eb, days_b = intervals[b]
                    if not days_overlap(days_a, days_b):
                        continue  # khac ngay hoan toan -> khong xung dot du gio co chong nhau
                    if intervals_overlap(sa, ea, sb, eb):
                        bad_rows.add(ia)
                        bad_rows.add(ib)
                        _, gio_a, phut_a, _, thu_a = rows[ia]
                        _, gio_b, phut_b, _, thu_b = rows[ib]
                        messages.append(
                            f"{gio_a.value():02d}:{phut_a.value():02d} (đến {format_hms(ea)}, {thu_a.text()}) "
                            f"chồng lấn {gio_b.value():02d}:{phut_b.value():02d} (đến {format_hms(eb)}, {thu_b.text()})"
                        )
        else:
            # SUA: THEM MOI - chan gia tri = 0 (vd Cho an dat 0 gram thi vo
            # nghia, khong nen cho luu). Truoc day chi Tam/Rua chuong moi
            # chan "thoi luong = 0", con loai khong-duration nhu Cho an lai
            # chua he kiem tra dieu nay.
            for i, (r, sp_gio, sp_phut, sp_val, btn_thu) in enumerate(rows):
                if sp_val is not None and sp_val.value() <= 0:
                    bad_rows.add(i)
                    messages.append(
                        f"{sp_gio.value():02d}:{sp_phut.value():02d} có "
                        f"{self.value_label.lower()} = 0 {self.value_unit}"
                    )

            min_gap_minutes = self.sp_min_gap.value() if self.sp_min_gap is not None else 0
            min_gap_sec = min_gap_minutes * 60

            if min_gap_sec <= 0:
                # Nguoi dung dat khoang cach toi thieu = 0 -> chi con chan
                # dung 1 moc TRUNG HET gio:phut (hanh vi cu, giu lai de
                # khong ep buoc phai co khoang cach neu ho thuc su khong muon).
                times = []
                for i, (r, sp_gio, sp_phut, sp_val, btn_thu) in enumerate(rows):
                    times.append((i, sp_gio.value(), sp_phut.value(), btn_thu.get_days()))

                for a in range(len(times)):
                    ia, gio_a, phut_a, days_a = times[a]
                    for b in range(a + 1, len(times)):
                        ib, gio_b, phut_b, days_b = times[b]
                        if (gio_a, phut_a) != (gio_b, phut_b):
                            continue
                        if not days_overlap(days_a, days_b):
                            continue  # cung gio nhung khac ngay hoan toan -> khong trung thuc su
                        bad_rows.add(ia)
                        bad_rows.add(ib)
                        thu_a_btn = rows[ia][4]
                        thu_b_btn = rows[ib][4]
                        messages.append(
                            f"{gio_a:02d}:{phut_a:02d} bị trùng giữa 2 dòng "
                            f"({thu_a_btn.text()} và {thu_b_btn.text()})"
                        )
            else:
                # THEM MOI: coi moi moc gio la 1 khoang [gio:phut, gio:phut +
                # khoang_cach_toi_thieu) - dung lai CHINH XAC logic chong lan
                # (intervals_overlap/_normalize_interval) da dung cho Tam/Rua
                # chuong, de phat hien dung ca truong hop vat qua nua dem.
                # 2 moc cach nhau CANG IT hon khoang_cach_toi_thieu se lam 2
                # khoang nay chong len nhau -> bi bao loi.
                intervals = []
                for i, (r, sp_gio, sp_phut, sp_val, btn_thu) in enumerate(rows):
                    start = sp_gio.value() * 3600 + sp_phut.value() * 60
                    intervals.append((i, start, start + min_gap_sec, btn_thu.get_days()))

                for a in range(len(intervals)):
                    ia, sa, ea, days_a = intervals[a]
                    for b in range(a + 1, len(intervals)):
                        ib, sb, eb, days_b = intervals[b]
                        if not days_overlap(days_a, days_b):
                            continue
                        if intervals_overlap(sa, ea, sb, eb):
                            bad_rows.add(ia)
                            bad_rows.add(ib)
                            _, gio_a, phut_a, _, thu_a = rows[ia]
                            _, gio_b, phut_b, _, thu_b = rows[ib]
                            messages.append(
                                f"{gio_a.value():02d}:{phut_a.value():02d} và "
                                f"{gio_b.value():02d}:{phut_b.value():02d} cách nhau chưa đủ "
                                f"{min_gap_minutes} phút tối thiểu ({thu_a.text()} / {thu_b.text()})"
                            )

        has_dup = len(bad_rows) > 0
        for i, (r, sp_gio, sp_phut, sp_val, btn_thu) in enumerate(rows):
            style = DUPLICATE_STYLE if i in bad_rows else NORMAL_STYLE
            sp_gio.setStyleSheet(style)
            sp_phut.setStyleSheet(style)
            # SUA: truoc day o "gia tri" (sp_val) chi duoc to do khi
            # is_duration_based=True (Tam/Rua chuong). Gio Cho an cung co
            # loi rieng (gia tri = 0) nen cung can to do o day khi bi loi.
            if sp_val is not None:
                sp_val.setStyleSheet(style if i in bad_rows else NORMAL_STYLE)
            btn_thu.set_error_style(i in bad_rows)

        if has_dup:
            self.lbl_warning.setText("; ".join(messages) + " — vui lòng chỉnh lại trước khi lưu.")
        else:
            self.lbl_warning.setText("")

        return has_dup

    def has_duplicates(self):
        """Cho màn hình cha (SettingTab) gọi để kiểm tra trước khi cho phép rời trang."""
        return self._check_duplicates()

    def get_min_gap_minutes(self):
        """Cho SettingTab đọc giá trị 'khoảng cách tối thiểu' hiện tại để lưu
        ra file. Trả về 0 với các loại có is_duration_based=True (Tắm/Rửa
        chuồng - không có ô này vì đã tự bảo vệ bằng thời lượng chạy thật)."""
        return self.sp_min_gap.value() if self.sp_min_gap is not None else 0

    def get_schedule(self):
        """Trả về list dict [{giờ, phút, giá trị, thu}, ...] cho toàn bộ dòng hiện có.
        "thu" là list các số 1..7 (1=Thứ 2 ... 7=Chủ nhật, giống quy ước
        ALL_WEEKDAYS trong scheduler.py)."""
        result = []
        for row in range(self.table.rowCount()):
            gio = self.table.cellWidget(row, 0).value()
            phut = self.table.cellWidget(row, 1).value()
            val = self.table.cellWidget(row, 2).value()
            thu = self.table.cellWidget(row, 3).get_days()
            result.append({"gio": gio, "phut": phut, "value": val, "thu": thu})
        return result


class LightScheduleSection(QGroupBox):
    """Khối quản lý lịch CHIẾU SÁNG — khác với ScheduleSection ở chỗ đèn không
    có 'thời gian chạy' (duration) mà có 1 cặp GIỜ BẬT + GIỜ TẮT cho mỗi dòng
    (vd bật 18:00, tắt 22:00). Có thể thêm nhiều dòng nếu cần bật/tắt nhiều
    khung giờ trong ngày (vd thêm 1 khung buổi sáng sớm).

    Mỗi dòng cũng có 1 DayPickerButton chọn "thứ trong tuần" áp dụng, cùng
    quy ước và cách chống chồng lấn như ScheduleSection (xem days_overlap())."""

    def __init__(self, default_rows):
        super().__init__("Chiếu sáng (Đèn)")
        self._build_ui()
        for row_data in default_rows:
            # Cho phep tuple 4 phan tu (gio_bat, phut_bat, gio_tat, phut_tat)
            # - hanh vi cu, hoac 5 phan tu (+ thu) - khi da co du lieu ngay.
            if len(row_data) == 5:
                gio_bat, phut_bat, gio_tat, phut_tat, thu = row_data
            else:
                gio_bat, phut_bat, gio_tat, phut_tat = row_data
                thu = None
            self._add_row(gio_bat, phut_bat, gio_tat, phut_tat, thu)
        self._check_duplicates()

    def _build_ui(self):
        root = QVBoxLayout(self)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Giờ bật", "Phút bật", "Giờ tắt", "Phút tắt", "Thứ", ""]
        )
        for col in range(4):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
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

    def _add_row(self, gio_bat=18, phut_bat=0, gio_tat=22, phut_tat=0, thu=None):
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

        btn_thu = DayPickerButton(days=thu, on_change=self._check_duplicates)
        self.table.setCellWidget(row, 4, btn_thu)

        btn_del = QPushButton("Xóa")
        btn_del.setStyleSheet("background:#d13c3c; color:white; border-radius:0px;")
        btn_del.clicked.connect(lambda: self._delete_row_by_widget(btn_del))
        self.table.setCellWidget(row, 5, btn_del)

    def _delete_row_by_widget(self, widget):
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 5) is widget:
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
        là HỢP LỆ (không chồng lấn thật).

        THÊM MỚI: 2 dòng chỉ xung đột nếu VỪA chồng khoảng giờ VỪA có ít
        nhất 1 THỨ chung nhau; dòng chưa chọn thứ nào cũng bị coi là lỗi."""
        n = self.table.rowCount()
        rows = []
        for r in range(n):
            sp_gb = self.table.cellWidget(r, 0)
            sp_pb = self.table.cellWidget(r, 1)
            sp_gt = self.table.cellWidget(r, 2)
            sp_pt = self.table.cellWidget(r, 3)
            btn_thu = self.table.cellWidget(r, 4)
            if None in (sp_gb, sp_pb, sp_gt, sp_pt, btn_thu):
                continue
            rows.append((r, sp_gb, sp_pb, sp_gt, sp_pt, btn_thu))

        bad_rows = set()
        messages = []
        intervals = []

        for i, (r, sp_gb, sp_pb, sp_gt, sp_pt, btn_thu) in enumerate(rows):
            if not btn_thu.get_days():
                bad_rows.add(i)
                messages.append(f"{sp_gb.value():02d}:{sp_pb.value():02d} chưa chọn thứ áp dụng")

            start = sp_gb.value() * 3600 + sp_pb.value() * 60
            end = sp_gt.value() * 3600 + sp_pt.value() * 60
            if start == end:
                bad_rows.add(i)
                messages.append(f"{sp_gb.value():02d}:{sp_pb.value():02d} có giờ bật = giờ tắt")
                continue
            intervals.append((i, start, end, btn_thu.get_days()))

        for a in range(len(intervals)):
            ia, sa, ea, days_a = intervals[a]
            for b in range(a + 1, len(intervals)):
                ib, sb, eb, days_b = intervals[b]
                if not days_overlap(days_a, days_b):
                    continue  # khac ngay hoan toan -> khong xung dot
                if intervals_overlap(sa, ea, sb, eb):
                    bad_rows.add(ia)
                    bad_rows.add(ib)
                    _, gb_a, pb_a, gt_a, pt_a, thu_a = rows[ia]
                    _, gb_b, pb_b, gt_b, pt_b, thu_b = rows[ib]
                    messages.append(
                        f"{gb_a.value():02d}:{pb_a.value():02d}-{gt_a.value():02d}:{pt_a.value():02d} "
                        f"({thu_a.text()}) chồng lấn "
                        f"{gb_b.value():02d}:{pb_b.value():02d}-{gt_b.value():02d}:{pt_b.value():02d} "
                        f"({thu_b.text()})"
                    )

        has_dup = len(bad_rows) > 0
        for i, (r, sp_gb, sp_pb, sp_gt, sp_pt, btn_thu) in enumerate(rows):
            style = DUPLICATE_STYLE if i in bad_rows else NORMAL_STYLE
            sp_gb.setStyleSheet(style)
            sp_pb.setStyleSheet(style)
            sp_gt.setStyleSheet(style)
            sp_pt.setStyleSheet(style)
            btn_thu.set_error_style(i in bad_rows)

        if has_dup:
            self.lbl_warning.setText("; ".join(messages) + " — vui lòng chỉnh lại trước khi lưu.")
        else:
            self.lbl_warning.setText("")

        return has_dup

    def has_duplicates(self):
        return self._check_duplicates()

    def get_schedule(self):
        """Trả về list dict [{gio_bat, phut_bat, gio_tat, phut_tat, thu}, ...]."""
        result = []
        for row in range(self.table.rowCount()):
            result.append({
                "gio_bat": self.table.cellWidget(row, 0).value(),
                "phut_bat": self.table.cellWidget(row, 1).value(),
                "gio_tat": self.table.cellWidget(row, 2).value(),
                "phut_tat": self.table.cellWidget(row, 3).value(),
                "thu": self.table.cellWidget(row, 4).get_days(),
            })
        return result