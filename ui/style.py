# -*- coding: utf-8 -*-
"""
Bảng màu / stylesheet dùng chung cho toàn bộ phần mềm, mô phỏng giao diện
HMI công nghiệp (nền xanh dương - vàng nhạt) theo đúng tinh thần các ảnh
chụp màn hình WeinView gốc.

===========================================================================
HỆ THỐNG THIẾT KẾ (design system) - ĐỌC TRƯỚC KHI THÊM UI MỚI
===========================================================================

1) NĂM CẤP TYPOGRAPHY (chữ) - dùng ĐÚNG 1 trong 5 role dưới đây cho MỌI
   chữ trong app, không tự ý đặt font-size rời rạc ở từng tab:

   - "Tiêu đề chính"  -> objectName="pageTitle" (21px, đậm, xanh đậm).
     Dùng cho tiêu đề TO NHẤT của 1 trang/khu vực, vd "CHỈNH SỬA: MÔI
     TRƯỜNG + ĐỘNG CƠ". Mỗi trang chỉ nên có TỐI ĐA 1 pageTitle.
   - "Tên nhóm"       -> tiêu đề QGroupBox (tự động, không cần set gì
     thêm - xem QGroupBox::title bên dưới, 15px đậm xanh đậm).
   - "Nội dung"       -> mặc định QWidget (14px thường) - không cần set
     property gì, đây là kiểu chữ MẶC ĐỊNH của mọi QLabel/QWidget.
   - "Số liệu"        -> role="value" (20px đậm, font monospace) - CHỈ
     dùng cho số đo cảm biến/khối lượng, KHÔNG dùng cho chữ thường.
   - "Trạng thái"     -> role="status-ok"/"status-error"/"status-warning"/
     "status-neutral" (14px đậm, chỉ đổi MÀU chữ, không icon/emoji).

2) NÚT BẤM - ĐÚNG 5 VAI TRÒ, không tự chế thêm màu/kiểu riêng:

   - role="btnPrimary"  : xanh dương đặc - hành động điều hướng/lưu chính
     (vd "SET MÔI TRƯỜNG", "SET LỊCH", "LƯU THÀNH ID MỚI").
   - role="btnSuccess"  : xanh lá đặc - hành động TÍCH CỰC/xác nhận
     (vd "CHO ĂN NGAY").
   - role="btnDanger"   : đỏ đặc - hành động NGUY HIỂM/khẩn cấp
     (vd "DỪNG NGAY").
   - role="btnOutline"  : viền xanh, nền trắng - hành động PHỤ, ít quan
     trọng hơn (vd "BACK", "Xóa vùng", "Xóa camera đang chọn").
   - role="toggleOn"/"toggleOff": GIỮ NGUYÊN như cũ - đây là NÚT THỂ HIỆN
     TRẠNG THÁI THIẾT BỊ (ON/OFF), khác bản chất với 4 loại nút HÀNH ĐỘNG
     ở trên nên không gộp chung.

3) PANEL - CHỈ 1 LỚP VIỀN, không lồng viền thừa:
   QGroupBox đã có viền + nền trắng riêng - KHÔNG bọc thêm QFrame có viền
   bên trong 1 QGroupBox nữa (gây 2 lớp viền lồng nhau, rối mắt). Nếu cần
   1 khối con nổi bật bên trong (vd ô số liệu), dùng role="value" (đã có
   nền be nhạt riêng, không cần thêm khung ngoài).

4) KHÔNG DÙNG ICON/EMOJI: mọi trạng thái/cảnh báo chỉ thể hiện qua MÀU
   CHỮ (role="status-*") hoặc đèn tròn (tao_den_led()) - không chèn icon
   trang trí, không emoji trong chuỗi hiển thị.

5) THANH TRẠNG THÁI MỎNG (#thinStatusBar): 1 dải ngang đặt NGAY DƯỚI
   header, LẶP LẠI Ở MỌI TAB (không riêng gì HOME) - hiển thị nhiệt độ/
   độ ẩm/nguồn đang chọn/trạng thái Cloud, để người dùng không phải quay
   về tab HOME mới biết được các thông tin này. Xem class ThinStatusBar
   trong ui/thin_status_bar.py.
===========================================================================
"""

from PyQt5.QtWidgets import QLabel

COLOR_HEADER_BLUE = "#1857a4"
COLOR_HEADER_BLUE_DARK = "#123f7c"
COLOR_BG_CREAM = "#f5f0dc"
COLOR_BG_WHITE = "#ffffff"
COLOR_NAV_BLUE = "#1857a4"
COLOR_NAV_BLUE_ACTIVE = "#0e3f8a"
COLOR_ON_GREEN = "#2fae4e"
COLOR_OFF_GRAY = "#8a8a8a"
COLOR_ALARM_RED = "#d13c3c"
COLOR_TEXT_DARK = "#1c2b4a"
COLOR_WARNING_AMBER = "#c47a12"

# SUA: THEM MOI - mau chu phu (muted) dung cho nhan/ghi chu it quan trong
# hon chu thuong - vd don vi do, ghi chu nho duoi 1 khoi.
COLOR_TEXT_MUTED = "#6b6b6b"

# SUA: THEM MOI - mau nen/vien rieng cho THANH TRANG THAI MONG (lap lai
# moi tab) - dung mau xanh dam hon header 1 chut de phan biet ro day la 1
# dai thong tin phu, khong phai thanh tieu de chinh.
COLOR_STATUSBAR_BG = "#123f7c"
COLOR_STATUSBAR_DIVIDER = "#4a75ab"

FONT_MONO = "Consolas"

APP_STYLESHEET = f"""
QWidget {{
    font-family: "Segoe UI", "Arial", sans-serif;
    color: {COLOR_TEXT_DARK};
    font-size: 14px;
}}

QMainWindow, #centralArea {{
    background-color: {COLOR_BG_CREAM};
}}

#headerBar {{
    background-color: {COLOR_HEADER_BLUE};
}}

#headerTitle {{
    color: white;
    font-size:23px;
    font-weight: 700;
}}

#headerClock {{
    color: white;
    font-size:17px;
    padding-right: 14px;
}}

#navBar {{
    background-color: {COLOR_NAV_BLUE};
}}

QPushButton#navButton {{
    background-color: {COLOR_NAV_BLUE};
    color: white;
    border: none;
    border-right: 1px solid #2a6bc2;
    font-size:17px;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 10px 4px;
}}

QPushButton#navButton:hover {{
    background-color: #2569b8;
}}

QPushButton#navButton:checked {{
    background-color: {COLOR_NAV_BLUE_ACTIVE};
    border-bottom: 3px solid #ffd54a;
}}

/* SUA: THEM MOI - THANH TRANG THAI MONG, lap lai moi tab (xem
ui/thin_status_bar.py). Dat NGAY DUOI headerBar/navBar. */
#thinStatusBar {{
    background-color: {COLOR_STATUSBAR_BG};
}}

QLabel[role="statusbarItem"] {{
    color: white;
    font-size: 13px;
}}

QLabel[role="statusbarValue"] {{
    color: white;
    font-size: 13px;
    font-weight: 700;
    font-family: "{FONT_MONO}", "Consolas", monospace;
}}

QFrame#statusbarDivider {{
    background-color: {COLOR_STATUSBAR_DIVIDER};
    max-width: 1px;
    min-width: 1px;
}}

/* SUA: THEM MOI - "Tieu de chinh" (cap typography lon nhat sau header) -
dung objectName="pageTitle", KHONG dung font-size roi rac tung noi. */
QLabel#pageTitle {{
    font-size: 21px;
    font-weight: 700;
    color: {COLOR_HEADER_BLUE_DARK};
}}

QGroupBox {{
    background-color: {COLOR_BG_WHITE};
    border: 1px solid #c9c2a0;
    border-radius:0px;
    margin-top: 14px;
    font-weight: 700;
    font-size:15px;
    color: {COLOR_HEADER_BLUE_DARK};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}}

QLabel[role="value"] {{
    background-color: #fbf8ec;
    border: 1px solid #b9b28e;
    border-radius:0px;
    padding: 4px 8px;
    font-size:19px;
    font-weight: 700;
    font-family: "{FONT_MONO}", "Consolas", monospace;
}}

QLabel[role="unit"] {{
    color: {COLOR_TEXT_MUTED};
    font-size:15px;
}}

/* "role" cho CHU THONG BAO TRANG THAI, dung MAU SAC thay cho icon/emoji
(theo dung huong "khong icon, chi chu + mau"). Vi du dung:
lbl.setProperty("role", "status-ok"); lbl.setText("DA GUI THANH CONG") */
QLabel[role="status-ok"] {{
    color: {COLOR_ON_GREEN};
    font-weight: 700;
}}

QLabel[role="status-error"] {{
    color: {COLOR_ALARM_RED};
    font-weight: 700;
}}

QLabel[role="status-warning"] {{
    color: {COLOR_WARNING_AMBER};
    font-weight: 700;
}}

QLabel[role="status-neutral"] {{
    color: {COLOR_TEXT_MUTED};
    font-weight: 600;
}}

/* SUA: THEM MOI - 4 VAI TRO NUT HANH DONG CHUAN (xem muc 2 o docstring
dau file) - THAY THE moi kieu nut tu che rieng le truoc day (vd outline
xanh la cho "SET MOI TRUONG" nhung nen dac xanh duong cho "SET LICH"). */
QPushButton[role="btnPrimary"] {{
    background-color: {COLOR_HEADER_BLUE};
    color: white;
    font-weight: 700;
    font-size:15px;
    border-radius: 3px;
    border: none;
    padding: 10px 16px;
}}
QPushButton[role="btnPrimary"]:hover {{
    background-color: #2569b8;
}}

QPushButton[role="btnSuccess"] {{
    background-color: {COLOR_ON_GREEN};
    color: white;
    font-weight: 700;
    font-size:15px;
    border-radius: 3px;
    border: none;
    padding: 10px 16px;
}}
QPushButton[role="btnSuccess"]:hover {{
    background-color: #279141;
}}

QPushButton[role="btnDanger"] {{
    background-color: {COLOR_ALARM_RED};
    color: white;
    font-weight: 700;
    font-size:15px;
    border-radius: 3px;
    border: none;
    padding: 10px 16px;
}}
QPushButton[role="btnDanger"]:hover {{
    background-color: #b32f2f;
}}

QPushButton[role="btnOutline"] {{
    background-color: white;
    color: {COLOR_HEADER_BLUE};
    font-weight: 700;
    border-radius: 3px;
    border: 1px solid {COLOR_HEADER_BLUE};
    padding: 9px 16px;
}}
QPushButton[role="btnOutline"]:hover {{
    background-color: #eef4fb;
}}

QPushButton[role="toggleOn"] {{
    background-color: {COLOR_ON_GREEN};
    color: white;
    font-weight: 700;
    border-radius:0px;
    border: 1px solid #218a3c;
}}
QPushButton[role="toggleOn"]:hover {{
    background-color: #279141;
}}

QPushButton[role="toggleOff"] {{
    background-color: #d9d9d9;
    color: #444;
    font-weight: 700;
    border-radius:0px;
    border: 1px solid #aaaaaa;
}}
/* SUA: THEM MOI - hover ro rang hon cho toggleOff, tranh trong giong 1
nhan tinh khong bam duoc (diem da bi ghi nhan khi ra soat giao dien). */
QPushButton[role="toggleOff"]:hover {{
    background-color: #c8c8c8;
    border: 1px solid #888888;
}}

/* SUA: THEM MOI - style rieng cho QComboBox (dung o SourceSwitch/
ModeSwitch trong ui/manual_tab.py) - de khop tong mau chung, khong de
mac dinh theo giao dien he dieu hanh (vo tinh gay lac tong voi phan con
lai cua app). */
QComboBox {{
    background-color: white;
    border: 1px solid #b9b28e;
    border-radius:0px;
    padding: 4px 10px;
    font-size:14px;
}}
QComboBox:hover {{
    border: 1px solid {COLOR_HEADER_BLUE};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: white;
    border: 1px solid #b9b28e;
    selection-background-color: {COLOR_HEADER_BLUE};
    selection-color: white;
}}

QTableWidget {{
    background-color: white;
    gridline-color: #d8d2b8;
    border: 1px solid #c9c2a0;
}}

QHeaderView::section {{
    background-color: {COLOR_HEADER_BLUE};
    color: white;
    padding: 4px;
    border: none;
    font-weight: 600;
}}
"""


def tao_den_led(mau, kich_thuoc=11):
    """Tao 1 'den bao' hinh tron mau THAT (khong phai emoji) - dung chung
    cho MOI noi can hien trang thai dang (ket noi camera, relay bat/tat,
    canh bao...), de dong bo 1 kieu "den" xuyen suot toan app, dung y het
    kieu den bao tren tu dieu khien cong nghiep that.

    Cach dung:
        den = tao_den_led(COLOR_ON_GREEN)
        ...
        doi_mau_den_led(den, COLOR_ALARM_RED)  # doi mau sau nay
    """
    den = QLabel()
    den.setFixedSize(kich_thuoc, kich_thuoc)
    den.setStyleSheet(
        f"background:{mau}; border-radius:{kich_thuoc // 2}px; border:1px solid rgba(0,0,0,40);"
    )
    return den


def doi_mau_den_led(den: QLabel, mau: str):
    """Doi mau 1 den da tao boi tao_den_led(), giu nguyen kich thuoc/bo tron."""
    kich_thuoc = den.width()
    den.setStyleSheet(
        f"background:{mau}; border-radius:{kich_thuoc // 2}px; border:1px solid rgba(0,0,0,40);"
    )