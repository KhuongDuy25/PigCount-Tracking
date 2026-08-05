# -*- coding: utf-8 -*-
"""
chart_tab.py — Tab CHART
==================================================================================
Biểu đồ Nhiệt độ/Độ ẩm:
  - Lúc mở app: gọi Historical Data API của Blynk (đã có sẵn trong
    blynk_client.get_history) 1 LẦN DUY NHẤT để lấy toàn bộ dữ liệu từ đầu
    ngày đến thời điểm mở app -> vẽ phần "quá khứ".
  - Trong lúc app chạy: BlynkPoller (đã có sẵn, đọc V0/V1 mỗi vài giây) tiếp
    tục đẩy dữ liệu real-time vào qua update_from_blynk() -> chỉ NỐI THÊM
    điểm mới vào cuối, không gọi lại Historical Data API (API đó giới hạn
    tối đa 10 lần/thiết bị/ngày, khác hẳn API đọc pin hiện tại).

Heatmap hoạt động + Đường đi (Trajectory):
  - SUA: đổi từ 1 file JSON DUY NHẤT (position_history.json, ghi đè lại toàn
    bộ mỗi lần lưu) SANG 1 FILE CSV RIÊNG CHO MỖI NGÀY
    (logs/vitri_YYYY-MM-DD.csv). Ngày nào có camera nhận diện được thì ngày
    đó mới có file, sang ngày mới tự tạo file mới - không phải đọc/ghi lại
    một file khổng lồ phình to vô hạn theo thời gian nữa.
  - Có ô chọn ngày (QDateEdit) ở đầu tab, mặc định = hôm nay, cho phép xem
    lại dữ liệu các ngày trước.
  - Có 1 QTimer chỉ chạy khi tab CHART đang được hiển thị (MainWindow gọi
    set_active()) - cứ vài giây tự đọc lại đúng file CSV của ngày đang chọn
    và vẽ lại, gần như real-time mà không tốn CPU khi người dùng đang ở tab khác.
  - Heatmap: chọn "Tất cả lợn" hoặc từng ID riêng.
  - Đường đi: mặc định xem 1 ID cụ thể (không có lựa chọn "tất cả" vì vẽ
    chồng nhiều đường đi lên nhau sẽ rối), kèm panel thông tin số "lượt vào
    máng ăn" (đếm số lần toạ độ đi từ ngoài vùng máng ăn vào trong).
"""

import os
import csv
import json
import re
import time
import threading
from collections import deque, defaultdict
from datetime import datetime

from PyQt5.QtCore import QTimer, QDate, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QComboBox,
    QPushButton, QDateEdit
)

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.path import Path as MplPath
import matplotlib.dates as mdates
import numpy as np

# so mau gan nhat giu lai de ve bieu do nhiet do/do am. SUA: TANG len rat
# nhieu so voi ban cu (60) vi gio con phai chua ca 1 ngay du lieu LICH SU
# (granularity MINUTE ~ toi da 1440 diem/ngay) CONG THEM du lieu realtime
# noi them lien tuc trong ca phien lam viec.
MAX_DIEM = 20000

# so diem toi da giu lai MOI ID khi doc 1 file CSV ngay - tranh ngon RAM/lag
# ve hinh neu file cua ngay do qua lon.
MAX_DIEM_VI_TRI_MOI_ID = 4000

# SUA: chi ghi 1 dong/giay cho MOI ID xuong CSV (thay vi ghi MOI LAN camera
# gui toa do ve, co the toi ~15 lan/giay) - du day de ve heatmap/duong di
# muot, ma khong lam file CSV phinh to vo ich va khong lam I/O dia lien tuc.
GHI_TOI_THIEU_MOI_GIAY = 1.0

# SUA: THEM MOI - nguong khoang cach thoi gian TOI DA (giay) giua 2 diem
# LIEN TIEP de con TINH LA THOI GIAN LIEN TUC o trong/ngoai vung mang an.
# Neu khoang cach giua 2 diem lon hon nguong nay (vd camera mat dau con
# vat 1 luc, app bi tat/mo lai, hoac con vat ra khoi khung hinh) thi
# KHONG cong don khoang do vao tong thoi gian o mang - vi khong the chac
# chan con vat van dung yen lien tuc trong khoang bi mat du lieu do.
NGUONG_GAP_TOI_DA_GIAY = 5.0

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(_BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# SUA: THEM MOI - cache lai VUNG MANG AN GAN NHAT ma ChartTab tung nhan
# duoc qua signal (zone_norm + zone_closed), luu rieng ra 1 file JSON nho
# CHO TUNG CAMERA (Giai doan 1 - da camera: truoc day chi co 1 file cache
# DUNG CHUNG cho ca app, sai hoan toan neu co >1 camera vi vung mang an
# cua "Chuong A" se bi hien nham thanh vung cua "Chuong B" khi chuyen qua
# lai). Ly do can cache: zone_norm/zone_closed hien tai CHI song trong RAM,
# duoc cap nhat MOI KHI co 1 khung hinh camera phat hien duoc it nhat 1 con
# heo co ID ro rang (position_updated chi emit() khi positions_dict khong
# rong). Neu nguoi dung mo tab CHART truoc khi camera kip nhan dien duoc
# con nao trong phien lam viec nay, zone_norm se van rong - cache nay giup
# hien THI NGAY vung gan nhat tung biet, roi se duoc GHI DE bang du lieu
# THAT ngay khi co tin hieu moi cho DUNG camera dang xem.
def _ten_file_an_toan(ten):
    """Doi ten camera thanh chuoi AN TOAN de lam ten file (bo ky tu dac
    biet/dau tieng Viet co the gay loi tren 1 so he dieu hanh)."""
    if not ten:
        return "demo"
    return re.sub(r"[^A-Za-z0-9_-]+", "_", ten).strip("_") or "demo"


def _duong_dan_cache_zone(camera_id):
    return os.path.join(LOGS_DIR, f"last_zone_cache_{_ten_file_an_toan(camera_id)}.json")


def _luu_cache_zone(camera_id, zone_norm, zone_closed):
    try:
        with open(_duong_dan_cache_zone(camera_id), "w", encoding="utf-8") as f:
            json.dump({"zone_norm": zone_norm, "zone_closed": zone_closed}, f)
    except Exception as e:
        print(f"[ChartTab] Không thể lưu cache vùng máng ăn ({camera_id}): {e}")


def _doc_cache_zone(camera_id):
    path = _duong_dan_cache_zone(camera_id)
    if not os.path.exists(path):
        return [], False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        zone_norm = [tuple(p) for p in data.get("zone_norm", [])]
        zone_closed = bool(data.get("zone_closed", False))
        return zone_norm, zone_closed
    except Exception as e:
        print(f"[ChartTab] Không thể đọc cache vùng máng ăn ({camera_id}): {e}")
        return [], False


def _duong_dan_csv_ngay(date_str):
    """date_str dang 'YYYY-MM-DD' -> duong dan file logs/vitri_YYYY-MM-DD.csv"""
    return os.path.join(LOGS_DIR, f"vitri_{date_str}.csv")


def _lam_min_gaussian_2d(mang, sigma=1.6):
    """Lam mo Gaussian 2 chieu bang THUAN NUMPY (khong can them thu vien
    scipy) - bien heatmap tu dang O VUONG THO (nhu histogram2d ve thang)
    thanh dang KHOI MAU LOANG MEM MAI giong anh mau nguoi dung gui. Lam mo
    theo tung truc rieng (separable convolution: mo theo hang roi mo theo
    cot) cho nhanh hon nhieu so voi tich chap 2D truc tiep."""
    ban_kinh = max(1, int(sigma * 3))
    x = np.arange(-ban_kinh, ban_kinh + 1)
    nhan = np.exp(-(x ** 2) / (2 * sigma ** 2))
    nhan /= nhan.sum()
    tam = np.apply_along_axis(lambda m: np.convolve(m, nhan, mode="same"), axis=0, arr=mang)
    ket_qua = np.apply_along_axis(lambda m: np.convolve(m, nhan, mode="same"), axis=1, arr=tam)
    return ket_qua



def _dinh_dang_thoi_luong(tong_giay):
    """Doi so giay (float) sang chuoi de doc, vd 754.2 -> '12 phút 34 giây'.
    Duoi 60 giay chi hien so giay (vd '45 giây'), khong hien '0 phút'."""
    tong_giay = int(round(tong_giay))
    phut, giay = divmod(tong_giay, 60)
    if phut > 0:
        return f"{phut} phút {giay} giây"
    return f"{giay} giây"


def _mau_mac_dinh_cho_id(real_id):
    """Bang mau du phong don gian (khong phu thuoc camera_zone.py de tranh
    rang buoc import qua lai) - chi dung khi ve duong di 1 ID cu the."""
    bang_mau = ["#d13c3c", "#e8963c", "#2f8f4e", "#1857a4", "#8a5a00", "#7b3fa0"]
    return bang_mau[hash(real_id) % len(bang_mau)]


def _doc_csv_ngay(date_str, camera_id=None):
    """Doc TOAN BO file CSV vi tri cua 1 ngay tu dia, tra ve
    {real_id: deque[(x, y, ts)]}. Tra ve dict rong neu ngay do chua co file
    (vd chua bat camera / camera chua nhan dien duoc con nao).

    SUA: THEM MOI tham so camera_id (Giai doan 1 - da camera) - neu duoc
    chi dinh, CHI lay nhung dong khop DUNG camera do (bo qua du lieu cua
    camera/chuong khac trong CUNG 1 file ngay). Neu camera_id=None, lay
    TAT CA khong loc (dung cho ham liet ke danh sach camera ben duoi)."""
    ket_qua = defaultdict(lambda: deque(maxlen=MAX_DIEM_VI_TRI_MOI_ID))
    path = _duong_dan_csv_ngay(date_str)
    if not os.path.exists(path):
        return ket_qua
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)  # bo dong tieu de "time_epoch,time_str,real_id,x,y,camera_id"
            for row in reader:
                if len(row) < 5:
                    continue
                try:
                    ts = float(row[0])
                    real_id = row[2]
                    x = float(row[3])
                    y = float(row[4])
                except ValueError:
                    continue
                # SUA: cot camera_id la MOI THEM - file CSV cu (ghi truoc khi
                # co tinh nang nay) se KHONG co cot nay (chi 5 cot), gan nhan
                # "(cũ - không rõ chuồng)" de nguoi dung van xem lai duoc du
                # lieu cu thay vi mat trang, va de phan biet ro voi du lieu
                # co gan camera that.
                cam = row[5] if len(row) >= 6 and row[5] else "(cũ - không rõ chuồng)"
                if camera_id is not None and cam != camera_id:
                    continue
                ket_qua[real_id].append((x, y, ts))
    except Exception as e:
        print(f"[ChartTab] Không thể đọc {path}: {e}")
    return ket_qua


def _liet_ke_camera_trong_ngay(date_str):
    """Quet nhanh file CSV cua 1 ngay, tra ve TAP HOP ten cac camera/chuong
    da tung ghi du lieu trong ngay do - dung de do combo "Chuồng (Camera)"
    o tab CHART, tuong tu cach danh sach ID lon duoc do dong tu du lieu."""
    path = _duong_dan_csv_ngay(date_str)
    cac_camera = set()
    if not os.path.exists(path):
        return cac_camera
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 6 and row[5]:
                    cac_camera.add(row[5])
                elif len(row) >= 5:
                    cac_camera.add("(cũ - không rõ chuồng)")
    except Exception as e:
        print(f"[ChartTab] Không thể liệt kê camera ngày {date_str}: {e}")
    return cac_camera


def _iso_sang_epoch(ts_str):
    """Chuyen chuoi thoi gian Blynk Historical Data API tra ve (dang
    ISO_SIMPLE, vd '2026-07-27T08:30:00' hoac '2026-07-27 08:30:00') sang
    epoch giay de dung chung don vi voi du lieu realtime (time.time()).

    SUA: BUG THAT tung gay ra "0 diem" du Blynk co du lieu that su - da tu
    kiem chung bang file CSV nguoi dung xuat truc tiep tu dashboard Blynk:
    MOI DONG DU LIEU co 1 KY TU TAB o dau ('\\t2026-07-29 05:49:00,...').
    Truoc day ham nay cat chuoi [:19] TRUOC roi moi xu ly, nen 1 ky tu tab
    thua o dau lam LECH mat ky tu cuoi cua gio:phut:giay -> parse luon that
    bai -> MOI DIEM LICH SU BI AM THAM BO QUA het, bieu do trong trong khi
    Blynk Cloud thuc su co du lieu. Gio strip() truoc khi cat de loai bo
    tab/khoang trang thua o dau/cuoi."""
    if ts_str is None:
        return None
    s = str(ts_str).strip()[:19].replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).timestamp()
        except ValueError:
            continue
    try:
        return float(ts_str)
    except (TypeError, ValueError):
        return None


class ChartTab(QWidget):
    # SUA: THEM MOI - dung signal de ket qua goi Historical Data API (chay
    # tren thread nen, vi la 1 HTTP request co the mat vai giay) duoc "chuyen
    # giao" ve LAI DUNG luong chinh cua Qt truoc khi dung vao widget - Qt
    # KHONG cho phep dong bo giao dien tu thread khac ngoai main thread.
    _history_loaded = pyqtSignal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.temp_history = deque(maxlen=MAX_DIEM)   # (epoch, gia_tri)
        self.humi_history = deque(maxlen=MAX_DIEM)

        # du lieu vi tri CUA NGAY DANG CHON, doc tu CSV - khong con giu ca
        # "lich su toan phien" trong RAM nhu ban cu nua.
        self.position_history = defaultdict(lambda: deque(maxlen=MAX_DIEM_VI_TRI_MOI_ID))
        # SUA: Giai doan 1 - da camera. zone_norm/zone_closed gio la CUA
        # CAMERA DANG DUOC CHON XEM (self.selected_camera), khong con la
        # "1 vung dung chung ca app" nua. self._zone_thuoc_camera theo doi
        # xem zone_norm hien tai dang la cua camera nao, de biet luc nao
        # can nap lai cache khi doi camera xem.
        self.zone_norm = []
        self.zone_closed = False
        self.selected_camera = None
        self._zone_thuoc_camera = None
        # SUA: THEM MOI - ty le khung hinh THAT cua camera (mac dinh tam
        # thoi 560x540 giong camera_zone.py, se duoc CAP NHAT DUNG ngay khi
        # co tin hieu dau tien tu camera) - dung de Heatmap/Trajectory ve
        # DUNG TY LE, khong bi keo gian/bop meo so voi video that.
        self.frame_w, self.frame_h = 560, 540
        self.selected_date = QDate.currentDate().toString("yyyy-MM-dd")

        # --- ghi CSV lien tuc (luon ghi vao file cua HOM NAY, bat ke dang
        # xem lai ngay nao o combo chon ngay) ---
        self._log_date = None
        self._csv_file = None
        self._csv_writer = None
        # SUA: throttle gio khoa theo CA (camera_id, real_id) thay vi chi
        # real_id - vi neu 2 camera vo tinh cung dang bao 1 ma ID trung
        # nhau (hiem nhung co the), throttle theo real_id don thuan se lam
        # camera nay "an chan" mat ghi cua camera kia.
        self._last_write_ts = {}

        self._active = False         # SUA: chi True khi dang dung o tab CHART

        self._build_ui()
        self._history_loaded.connect(self._on_history_loaded)

        # ve lai ban do vi tri THEO CHU KY RIENG, CHI KHI dang o tab CHART
        # (set_active() bat/tat), khong ve moi lan nhan toa do - qua nang.
        self._map_timer = QTimer(self)
        self._map_timer.timeout.connect(self._doc_lai_va_ve_ban_do)

        self._doc_lai_va_ve_ban_do()  # ve lan dau (co the rong, khong sao)

    # ================================================================== UI
    def _build_ui(self):
        root = QVBoxLayout(self)

        # -------- hang tren cung: chon ngay xem du lieu (dung chung cho ca
        # Heatmap lan Duong di, vi ca 2 deu doc tu CUNG 1 file CSV/ngay) --------
        hang_ngay = QHBoxLayout()
        hang_ngay.addWidget(QLabel("XEM DỮ LIỆU VỊ TRÍ NGÀY:"))
        self.date_picker = QDateEdit()
        self.date_picker.setCalendarPopup(True)
        self.date_picker.setDisplayFormat("dd/MM/yyyy")
        self.date_picker.setDate(QDate.currentDate())
        self.date_picker.setMaximumDate(QDate.currentDate())  # chua co du lieu tuong lai
        self.date_picker.dateChanged.connect(self._doi_ngay_xem)
        hang_ngay.addWidget(self.date_picker)

        # SUA: THEM MOI (Giai doan 1 - da camera) - dropdown chon XEM DU
        # LIEU CUA CHUONG/CAMERA NAO, dat canh o chon ngay vi ca 2 cung anh
        # huong DEN VIEC LOC du lieu doc tu file CSV cua ngay do.
        hang_ngay.addWidget(QLabel("CHUỒNG (CAMERA):"))
        self.combo_camera = QComboBox()
        self.combo_camera.addItem("Chưa có dữ liệu", userData=None)
        self.combo_camera.currentIndexChanged.connect(self._doi_camera_xem)
        hang_ngay.addWidget(self.combo_camera)

        hang_ngay.addStretch(1)
        self.btn_xoa_lich_su = QPushButton("XÓA DỮ LIỆU NGÀY NÀY")
        self.btn_xoa_lich_su.clicked.connect(self._xoa_lich_su)
        hang_ngay.addWidget(self.btn_xoa_lich_su)
        self.lbl_so_dong = QLabel("")
        self.lbl_so_dong.setStyleSheet("color:#888; font-size:11px;")
        hang_ngay.addWidget(self.lbl_so_dong)
        root.addLayout(hang_ngay)

        # -------- hang giua: Heatmap (trai) + Duong di/Trajectory (phai) --------
        hang_ban_do = QHBoxLayout()

        # ---- Heatmap ----
        gb_heat = QGroupBox("HEATMAP HOẠT ĐỘNG (THỜI GIAN ĐỨNG LÂU)")
        hl = QVBoxLayout(gb_heat)
        ctr_heat = QHBoxLayout()
        ctr_heat.addWidget(QLabel("Hiển thị:"))
        self.combo_heatmap = QComboBox()
        self.combo_heatmap.addItem("Tất cả lợn", userData=None)
        self.combo_heatmap.currentIndexChanged.connect(lambda _: self._ve_heatmap())
        ctr_heat.addWidget(self.combo_heatmap, 1)
        hl.addLayout(ctr_heat)

        # SUA: doi cau truc sang GIONG HET khung Trajectory ben duoi (khung
        # ve BEN TRAI + 1 hop chu thich BEN PHAI trong QHBoxLayout), thay vi
        # 1 dong chu thich nam DUOI khung ve nhu truoc - vua dua chu thich
        # sang phai theo yeu cau, vua lam 2 khung Heatmap/Trajectory CAN
        # DOI kich thuoc voi nhau (cung 1 kieu bo cuc: ve 2 phan, chu thich 1 phan).
        khu_giua_heat = QHBoxLayout()
        self.figure_heat = Figure(figsize=(4, 3.2))
        self.canvas_heat = FigureCanvas(self.figure_heat)
        self.ax_heat = self.figure_heat.add_subplot(111)
        khu_giua_heat.addWidget(self.canvas_heat, 2)

        gb_chu_thich_heat = QGroupBox("CHÚ THÍCH")
        chu_thich_lay = QVBoxLayout(gb_chu_thich_heat)
        # SUA: BO cham tron emoji 🔴🔵 - to MAU THAT ngay len chu "do"/"xanh"
        # thay the (dung mau tuong ung tren heatmap: do = jet-do, xanh =
        # jet-xanh duong dam), dung y het huong "khong icon, chi chu + mau".
        lbl_do = QLabel("Màu đỏ: đứng lâu")
        lbl_do.setStyleSheet("font-size:12px; padding:2px 0; font-weight:700; color:#c0392b;")
        lbl_xanh = QLabel("Màu xanh: ít đi qua")
        lbl_xanh.setStyleSheet("font-size:12px; padding:2px 0; font-weight:700; color:#1857a4;")
        chu_thich_lay.addWidget(lbl_do)
        chu_thich_lay.addWidget(lbl_xanh)
        chu_thich_lay.addStretch(1)
        khu_giua_heat.addWidget(gb_chu_thich_heat, 1)

        hl.addLayout(khu_giua_heat)

        hang_ban_do.addWidget(gb_heat, 1)

        # ---- Duong di / Trajectory ----
        gb_traj = QGroupBox("ĐƯỜNG ĐI (TRAJECTORY)")
        tl = QVBoxLayout(gb_traj)
        ctr_traj = QHBoxLayout()
        ctr_traj.addWidget(QLabel("Chọn ID lợn:"))
        self.combo_traj = QComboBox()
        self.combo_traj.addItem("Chưa có dữ liệu", userData=None)
        self.combo_traj.currentIndexChanged.connect(lambda _: self._ve_trajectory())
        ctr_traj.addWidget(self.combo_traj, 1)
        tl.addLayout(ctr_traj)

        khu_giua = QHBoxLayout()
        self.figure_traj = Figure(figsize=(4, 3.2))
        self.canvas_traj = FigureCanvas(self.figure_traj)
        self.ax_traj = self.figure_traj.add_subplot(111)
        khu_giua.addWidget(self.canvas_traj, 2)

        gb_info = QGroupBox("Thông tin")
        info_lay = QVBoxLayout(gb_info)
        self.lbl_info_id = QLabel("ID lợn: —")
        self.lbl_info_luot = QLabel("Lượt vào máng ăn: —")
        self.lbl_info_thoigian = QLabel("Thời gian ở máng ăn: —")
        for lbl in (self.lbl_info_id, self.lbl_info_luot, self.lbl_info_thoigian):
            lbl.setStyleSheet("font-size:12px; padding:2px 0;")
        info_lay.addWidget(self.lbl_info_id)
        info_lay.addWidget(self.lbl_info_luot)
        info_lay.addWidget(self.lbl_info_thoigian)
        info_lay.addStretch(1)
        khu_giua.addWidget(gb_info, 1)

        tl.addLayout(khu_giua)

        hang_ban_do.addWidget(gb_traj, 1)
        root.addLayout(hang_ban_do, 3)

        # -------- hang duoi: bieu do nhiet do/do am (du lieu that) --------
        # SUA: xep 2 khung THEO CHIEU NGANG (2 cot, canh nhau) thay vi xep
        # CHONG THEO CHIEU DOC (2 hang) nhu ban truoc - theo dung yeu cau,
        # moi khung van co truc Y rieng tu co gian theo dung thang do cua
        # no, chi khac cach BO TRI tren man hinh.
        gb_chart = QGroupBox("BIỂU ĐỒ NHIỆT ĐỘ / ĐỘ ẨM TRUNG BÌNH THEO THỜI GIAN")
        cl = QVBoxLayout(gb_chart)
        self.figure = Figure(figsize=(10, 3.4))
        self.canvas = FigureCanvas(self.figure)
        self.ax_temp = self.figure.add_subplot(121)
        self.ax_humi = self.figure.add_subplot(122)
        cl.addWidget(self.canvas)

        hang_thong_ke = QHBoxLayout()
        self.lbl_empty = QLabel("Đang tải dữ liệu hôm nay...")
        self.lbl_empty.setStyleSheet("color:#999; font-style:italic;")
        hang_thong_ke.addWidget(self.lbl_empty)
        # SUA: THEM MOI - dong trang thai tai lich su RIENG, KHONG BAO GIO
        # bi an di khi co du lieu song toi (khac voi lbl_empty o tren, von
        # se .hide() ngay khi co 1 diem song bat ky). Ly do: neu lich su
        # tai LOI/RONG nhung sau do co du lieu song, lbl_empty bien mat
        # ngay lap tuc -> nguoi dung KHONG CO CACH NAO biet duoc lich su co
        # thuc su tai duoc hay khong nua. Dong nay giu nguyen de kiem tra.
        self.lbl_trang_thai_lichsu = QLabel("Lịch sử: đang tải...")
        self.lbl_trang_thai_lichsu.setStyleSheet("color:#888; font-size:11px; font-style:italic;")
        hang_thong_ke.addWidget(self.lbl_trang_thai_lichsu)
        hang_thong_ke.addStretch(1)
        self.lbl_thongke = QLabel("")
        self.lbl_thongke.setStyleSheet("color:#555; font-size:12px;")
        hang_thong_ke.addWidget(self.lbl_thongke)
        cl.addLayout(hang_thong_ke)

        root.addWidget(gb_chart, 2)

    # ============================================================ vong doi tab
    def set_active(self, active: bool):
        """Goi tu main.py moi khi nguoi dung chuyen VAO/RA khoi tab CHART
        (qua QStackedWidget.currentChanged). CHI ve lai ban do vi tri khi
        dang thuc su dung o tab nay - tranh doc dia + ve matplotlib vo ich
        khi dang o tab khac."""
        self._active = active
        if active:
            self._doc_lai_va_ve_ban_do()  # ve ngay, khong doi tick dau tien
            if not self._map_timer.isActive():
                self._map_timer.start(3000)  # gan nhu real-time: 3 giay/lan
        else:
            self._map_timer.stop()

    def shutdown(self):
        """Goi tu MainWindow.closeEvent() de dong file CSV dang ghi do cho
        gon gang truoc khi thoat app."""
        self._dong_file_ghi()

    # ============================================================ vi tri lon
    def record_positions(self, payload: dict):
        """Goi tu main.py moi khi CameraZoneWidget.position_updated phat tin
        hieu. payload = {"positions": {real_id: (x,y)}, "zone": [...],
        "zone_closed": bool, "camera_id": str, "frame_w"/"frame_h": int}.
        SUA: gio GHI THANG XUONG FILE CSV CUA HOM NAY (co throttle 1 dong/
        giay/ID), khong con tich luy vao 1 dict RAM khong gioi han + luu
        JSON dinh ky nhu ban cu. Giai doan 1 - da camera: MOI dong ghi kem
        camera_id, va vung mang an CHI cap nhat hien thi NGAY neu tin hieu
        nay THUOC DUNG camera dang duoc chon xem."""
        camera_id = payload.get("camera_id") or "Demo"
        zone_norm = payload.get("zone", [])
        zone_closed = payload.get("zone_closed", False)
        if zone_closed and len(zone_norm) >= 3:
            _luu_cache_zone(camera_id, zone_norm, zone_closed)  # cap nhat cache cho lan mo app sau

        # SUA: CHI cap nhat vung dang VE TREN MAN HINH neu tin hieu nay
        # THUOC DUNG camera dang duoc chon o combo - tranh vung cua "Chuong
        # A" bi de len man hinh dang xem "Chuong B" chi vi camera A vua gui
        # tin hieu song.
        if camera_id == self.selected_camera:
            self.zone_norm = zone_norm
            self.zone_closed = zone_closed
            self._zone_thuoc_camera = camera_id

        # SUA: THEM MOI - cap nhat ty le khung hinh THAT tu payload (neu
        # camera doi kich thuoc khung hinh sau nay, Heatmap/Trajectory se
        # tu dong ve dung theo ty le moi, khong bi "cung" theo gia tri mac
        # dinh 560x540 nua).
        self.frame_w = payload.get("frame_w", self.frame_w)
        self.frame_h = payload.get("frame_h", self.frame_h)
        positions = payload.get("positions", {})
        if not positions:
            return

        self._dam_bao_dung_file_ghi()
        now = time.time()
        co_ghi_dong_moi = False
        for real_id, (x, y) in positions.items():
            khoa_throttle = (camera_id, real_id)
            lan_cuoi = self._last_write_ts.get(khoa_throttle, 0)
            if now - lan_cuoi < GHI_TOI_THIEU_MOI_GIAY:
                continue  # chua du 1 giay ke tu lan ghi truoc cho ID nay (o CAMERA nay) - bo qua
            self._last_write_ts[khoa_throttle] = now
            self._csv_writer.writerow([
                f"{now:.3f}",
                time.strftime("%H:%M:%S", time.localtime(now)),
                real_id,
                f"{x:.4f}",
                f"{y:.4f}",
                camera_id,
            ])
            co_ghi_dong_moi = True

        if co_ghi_dong_moi:
            self._csv_file.flush()  # ghi xuong dia ngay - "gan nhu real-time" that su, khong cho buffer

    def _dam_bao_dung_file_ghi(self):
        """Dam bao file dang mo de GHI la dung file cua NGAY HOM NAY. Tu
        dong dong file cu + mo file moi neu vua sang ngay moi trong luc app
        van dang chay."""
        hom_nay = time.strftime("%Y-%m-%d")
        if hom_nay == self._log_date and self._csv_file is not None:
            return
        self._dong_file_ghi()
        self._log_date = hom_nay
        path = _duong_dan_csv_ngay(hom_nay)
        la_file_moi = not os.path.exists(path)
        self._csv_file = open(path, "a", encoding="utf-8", newline="")
        self._csv_writer = csv.writer(self._csv_file)
        if la_file_moi:
            self._csv_writer.writerow(["time_epoch", "time_str", "real_id", "x", "y", "camera_id"])
        self._last_write_ts = {}  # reset throttle khi sang file/ngay moi

    def _dong_file_ghi(self):
        if self._csv_file is not None:
            try:
                self._csv_file.close()
            except Exception:
                pass
            self._csv_file = None
            self._csv_writer = None

    def _doi_ngay_xem(self, qdate: QDate):
        self.selected_date = qdate.toString("yyyy-MM-dd")
        self._doc_lai_va_ve_ban_do()

    def _doi_camera_xem(self, _idx=None):
        self.selected_camera = self.combo_camera.currentData()
        self._doc_lai_va_ve_ban_do()

    def _doc_lai_va_ve_ban_do(self):
        """Doc lai TU DIA dung file CSV cua ngay dang chon, roi ve lai CA 2
        khung Heatmap + Trajectory. Day la ham duoc QTimer goi dinh ky
        (moi 3s) khi tab CHART dang active, dung y muon "gan nhu real-time,
        doc lai CSV" thay vi chi dua vao du lieu tich luy san trong RAM.

        SUA: Giai doan 1 - da camera. Truoc khi doc du lieu vi tri, CAP
        NHAT danh sach camera co trong ngay dang chon (combo_camera), roi
        CHI doc/ve du lieu CUA DUNG CAMERA dang duoc chon - tranh tron toa
        do cua 2 chuong/camera khac nhau (khac he quy chieu vat ly) vao
        chung 1 heatmap/duong di, se ra vo nghia."""
        self._cap_nhat_danh_sach_camera()

        if self.selected_camera and self.selected_camera != self._zone_thuoc_camera:
            # doi camera xem -> nap lai DUNG vung mang an cua camera moi tu
            # cache, khong con giu vung cua camera cu tren man hinh nua.
            self.zone_norm, self.zone_closed = _doc_cache_zone(self.selected_camera)
            self._zone_thuoc_camera = self.selected_camera

        self.position_history = _doc_csv_ngay(self.selected_date, camera_id=self.selected_camera)
        self._cap_nhat_danh_sach_id()

        tong_diem = sum(len(v) for v in self.position_history.values())
        ten_camera_hien_thi = f" - {self.selected_camera}" if self.selected_camera else ""
        if self.selected_date == QDate.currentDate().toString("yyyy-MM-dd"):
            self.lbl_so_dong.setText(f"{tong_diem} điểm ghi nhận hôm nay{ten_camera_hien_thi}")
        else:
            self.lbl_so_dong.setText(
                f"{tong_diem} điểm ghi nhận ngày {self.date_picker.date().toString('dd/MM/yyyy')}{ten_camera_hien_thi}"
            )

        self._ve_heatmap()
        self._ve_trajectory()

    def _cap_nhat_danh_sach_camera(self):
        """Do dong danh sach camera/chuong TU DU LIEU THAT co trong ngay
        dang chon (quet file CSV), tuong tu cach danh sach ID lon duoc do
        dong o _cap_nhat_danh_sach_id(). Tu dong chon camera DAU TIEN tim
        thay neu nguoi dung chua tung chon camera nao.

        SUA: BUG THAT tung gay hien TRUNG LAP camera trong combo (vd
        "cam1" xuat hien 2 lan) - da tu kiem chung: self.combo_camera.
        addItem() CO THE TU DONG kich hoat currentIndexChanged() NGAY LAP
        TUC (dac biet ro rang khi addItem() DAU TIEN lam so luong item tu
        0 len 1 - Qt tu dong chon o index 0 va phat tin hieu). Tin hieu do
        goi thang toi _doi_camera_xem() -> _doc_lai_va_ve_ban_do() ->
        goi NGUOC LAI chinh ham nay MOT LAN NUA trong luc vong lap 'for cam
        in cac_camera' o DUOI con dang chay do - lam vong lap NGOAI tiep
        tuc voi 'da_co'/'count()' da LOI THOI (khong con phan anh dung
        trang thai MOI vua duoc vong lap TRONG them vao), dan den them
        trung 1 camera. Truoc day CHI chan tin hieu quanh dong
        setCurrentIndex() cuoi ham - CHUA DU, vi addItem() cung co the tu
        kich hoat tin hieu. Gio chan tin hieu cho CA QUA TRINH thao tac
        combo (ca vong lap addItem/removeItem LAN setCurrentIndex), roi tu
        tay dong bo lai self.selected_camera sau khi da mo tin hieu."""
        cac_camera = sorted(_liet_ke_camera_trong_ngay(self.selected_date))

        dang_co_du_lieu = self.combo_camera.currentData() is not None or self.combo_camera.count() > 1
        da_co = {self.combo_camera.itemData(i) for i in range(self.combo_camera.count())}
        co_them_moi = False

        self.combo_camera.blockSignals(True)
        for cam in cac_camera:
            if cam not in da_co:
                if self.combo_camera.count() == 1 and self.combo_camera.itemData(0) is None:
                    self.combo_camera.removeItem(0)  # bo dong "Chua co du lieu" placeholder
                self.combo_camera.addItem(cam, userData=cam)
                co_them_moi = True

        if not dang_co_du_lieu and co_them_moi:
            self.combo_camera.setCurrentIndex(0)
        self.combo_camera.blockSignals(False)

        if not dang_co_du_lieu and co_them_moi:
            self.selected_camera = self.combo_camera.currentData()

    def _cap_nhat_danh_sach_id(self):
        cac_id = sorted(self.position_history.keys())

        # combo Heatmap: giu lua chon "Tat ca lon" o dau, them cac ID con thieu
        da_co_heat = {self.combo_heatmap.itemData(i) for i in range(self.combo_heatmap.count())}
        for real_id in cac_id:
            if real_id not in da_co_heat:
                self.combo_heatmap.addItem(real_id, userData=real_id)

        # combo Trajectory: khong co lua chon "tat ca", mac dinh chon ID dau tien
        dang_co_du_lieu = self.combo_traj.currentData() is not None or self.combo_traj.count() > 1
        da_co_traj = {self.combo_traj.itemData(i) for i in range(self.combo_traj.count())}
        co_them_id_moi = False
        for real_id in cac_id:
            if real_id not in da_co_traj:
                if self.combo_traj.count() == 1 and self.combo_traj.itemData(0) is None:
                    self.combo_traj.removeItem(0)  # bo dong "Chua co du lieu" placeholder
                self.combo_traj.addItem(real_id, userData=real_id)
                co_them_id_moi = True
        if not dang_co_du_lieu and co_them_id_moi:
            self.combo_traj.setCurrentIndex(0)  # tu chon ID dau tien tim thay

    def _xoa_lich_su(self):
        """Xoa file CSV cua NGAY DANG CHON (khong dung ghi lai duoc)."""
        path = _duong_dan_csv_ngay(self.selected_date)
        try:
            if path == _duong_dan_csv_ngay(self._log_date or ""):
                self._dong_file_ghi()
                self._last_write_ts = {}
                self._log_date = None
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"[ChartTab] Không thể xóa {path}: {e}")
        self._doc_lai_va_ve_ban_do()

    # ---------------------------------------------------------------- ve heatmap
    def _ve_heatmap(self):
        self.ax_heat.clear()
        self._ve_vien_vung_mang_an(self.ax_heat)

        che_do = self.combo_heatmap.currentData()  # None = tat ca, hoac 1 ID cu the
        if che_do is None:
            all_x, all_y = [], []
            for points in self.position_history.values():
                for (x, y, _ts) in points:
                    all_x.append(x)
                    all_y.append(y)
        else:
            points = self.position_history.get(che_do, [])
            all_x = [p[0] for p in points]
            all_y = [p[1] for p in points]

        if all_x:
            # SUA: TANG so bins (tu 25 len 60) de co du chi tiet TRUOC KHI
            # lam mo, roi LAM MO GAUSSIAN + VE VOI NOI SUY "bilinear" - bien
            # heatmap tu dang O VUONG THO/CUNG sang dang KHOI MAU LOANG MEM
            # MAI giong anh mau nguoi dung gui, de nhan biet vung "nong"
            # (do/cam) va vung "it hoat dong" (xanh duong) hon han.
            h, _xedges, _yedges = np.histogram2d(all_x, all_y, bins=60, range=[[0, 1], [0, 1]])
            h_min = _lam_min_gaussian_2d(h, sigma=1.8)
            self.ax_heat.imshow(h_min.T, origin="upper", extent=[0, 1, 1, 0],
                                 cmap="jet", aspect="auto", alpha=0.9, zorder=1,
                                 interpolation="bilinear")
        else:
            self.ax_heat.text(0.5, 0.5, "Chưa có dữ liệu vị trí ngày này",
                               ha="center", va="center", color="#999")

        self._trang_tri_truc(self.ax_heat)
        self.figure_heat.tight_layout()
        self.canvas_heat.draw()

    # ------------------------------------------------------------- ve trajectory
    def _ve_trajectory(self):
        self.ax_traj.clear()
        self._ve_vien_vung_mang_an(self.ax_traj)

        real_id = self.combo_traj.currentData()
        points = list(self.position_history.get(real_id, [])) if real_id else []

        if real_id and points:
            mau = _mau_mac_dinh_cho_id(real_id)
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            self.ax_traj.plot(xs, ys, color=mau, linewidth=1, alpha=0.7, zorder=2)
            self.ax_traj.scatter([xs[0]], [ys[0]], color="green", s=45, zorder=4,
                                  edgecolors="black", label="Điểm đầu")
            self.ax_traj.scatter([xs[-1]], [ys[-1]], color="red", s=45, zorder=4,
                                  edgecolors="black", label="Vị trí gần nhất")
            self.ax_traj.legend(loc="upper right", fontsize=7)

            self.lbl_info_id.setText(f"ID lợn: {real_id}")
            luot_vao = self._dem_luot_vao_mang(points)
            self.lbl_info_luot.setText(
                f"Lượt vào máng ăn: {luot_vao}" if luot_vao is not None
                else "Lượt vào máng ăn: (chưa vẽ vùng máng ăn ở tab HOME)"
            )
            thoi_gian_giay = self._tinh_thoi_gian_o_trong_mang(points)
            self.lbl_info_thoigian.setText(
                f"Thời gian ở máng ăn: {_dinh_dang_thoi_luong(thoi_gian_giay)}" if thoi_gian_giay is not None
                else "Thời gian ở máng ăn: (chưa vẽ vùng máng ăn ở tab HOME)"
            )
        else:
            self.ax_traj.text(0.5, 0.5, "Chưa có dữ liệu đường đi",
                               ha="center", va="center", color="#999")
            self.lbl_info_id.setText("ID lợn: —")
            self.lbl_info_luot.setText("Lượt vào máng ăn: —")
            self.lbl_info_thoigian.setText("Thời gian ở máng ăn: —")

        self._trang_tri_truc(self.ax_traj)
        self.figure_traj.tight_layout()
        self.canvas_traj.draw()

    def _dem_luot_vao_mang(self, points):
        """Dem so LAN toa do di tu NGOAI vung mang an VAO TRONG (canh len),
        dung cac diem da SAP XEP theo thoi gian tang dan (dung thu tu doc
        tu CSV). Tra ve None neu chua co vung mang an nao duoc ve/dong o
        tab HOME (khong the tinh duoc "lot vao mang")."""
        if not (self.zone_norm and self.zone_closed and len(self.zone_norm) >= 3):
            return None
        duong_bao = MplPath(self.zone_norm)
        diem_da_sap_xep = sorted(points, key=lambda p: p[2])
        dang_trong = False
        so_luot = 0
        for (x, y, _ts) in diem_da_sap_xep:
            trong_vung = bool(duong_bao.contains_point((x, y)))
            if trong_vung and not dang_trong:
                so_luot += 1
            dang_trong = trong_vung
        return so_luot

    def _tinh_thoi_gian_o_trong_mang(self, points):
        """Tinh TONG THOI GIAN (giay) o TRONG vung mang an trong ngay dang
        chon, dua tren khoang cach thoi gian GIUA CAC DIEM DA GHI LIEN
        TIEP (moi diem CSV cach nhau ~1 giay do throttle ghi
        GHI_TOI_THIEU_MOI_GIAY). Voi moi cap diem lien tiep (i, i+1): neu
        diem i dang O TRONG vung VA khoang cach thoi gian giua 2 diem
        KHONG QUA LON (duoi NGUONG_GAP_TOI_DA_GIAY - tuc KHONG bi mat dau/
        gian doan du lieu giua chung), cong khoang thoi gian do vao tong.
        Neu khoang cach qua lon (vd camera mat dau con vat, app tat/mo
        lai...) thi BO QUA doan do - khong the chac chan con vat van dung
        yen trong mang suot khoang thoi gian bi mat du lieu.

        Tra ve None neu chua co vung mang an nao duoc ve/dong o tab HOME
        (giong _dem_luot_vao_mang, de dong bo cach bao 'chua co du lieu')."""
        if not (self.zone_norm and self.zone_closed and len(self.zone_norm) >= 3):
            return None
        duong_bao = MplPath(self.zone_norm)
        diem_da_sap_xep = sorted(points, key=lambda p: p[2])
        tong_giay = 0.0
        for i in range(len(diem_da_sap_xep) - 1):
            x1, y1, ts1 = diem_da_sap_xep[i]
            _x2, _y2, ts2 = diem_da_sap_xep[i + 1]
            khoang_cach = ts2 - ts1
            if khoang_cach <= 0 or khoang_cach > NGUONG_GAP_TOI_DA_GIAY:
                continue  # gian doan du lieu qua lon - khong tinh la lien tuc o trong mang
            if duong_bao.contains_point((x1, y1)):
                tong_giay += khoang_cach
        return tong_giay

    def _ve_vien_vung_mang_an(self, ax):
        if self.zone_norm and self.zone_closed and len(self.zone_norm) >= 3:
            xs = [p[0] for p in self.zone_norm] + [self.zone_norm[0][0]]
            ys = [p[1] for p in self.zone_norm] + [self.zone_norm[0][1]]
            ax.plot(xs, ys, color="orange", linewidth=1.5, linestyle="--", zorder=10)

    def _trang_tri_truc(self, ax):
        ax.set_xlim(0, 1)
        ax.set_ylim(1, 0)  # dao truc Y vi (0,0) toa do anh la goc TREN-TRAI
        ax.set_xticks([])
        ax.set_yticks([])
        # SUA: THEM MOI - ep khung ve theo DUNG TY LE khung hinh camera that
        # (frame_w x frame_h, vd 560x540) thay vi de matplotlib tu keo gian
        # data [0,1]x[0,1] cho vua khit hinh chu nhat cua Figure (vd 4x3.2 -
        # ty le rat khac ty le video that) - do la nguyen nhan heatmap/duong
        # di bi "meo"/khong deu so voi khung hinh camera nguoi dung thay.
        # LUU Y CONG THUC: set_aspect(A) trong matplotlib nghia la "1 don vi
        # DU LIEU truc Y duoc ve dai gap A lan 1 don vi DU LIEU truc X" - DA
        # TU KIEM CHUNG BANG SO LIEU THAT (ve 1 hinh tron that trong khong
        # gian pixel, do lai ty le rong/cao sau khi ve): dung frame_h/frame_w
        # cho ra ty le 1.010 (gan dung 1.000), con frame_w/frame_h (tuong
        # nham luc dau) cho ra 0.941 (sai). "adjustable=box": co RUT NHO
        # khung ve lai cho vua khit vung hien thi, giu dung ty le that.
        ax.set_aspect(self.frame_h / self.frame_w, adjustable="box")

    # ================================================== nhiet do/do am (Blynk)
    def load_history_from_blynk(self, blynk_client):
        """Goi 1 LAN DUY NHAT tu main.py ngay luc mo app: lay du lieu LICH
        SU ca ngay hom nay (tinh den thoi diem mo app) cho nhiet do (V0) va
        do am (V1) qua Blynk Historical Data API, de bieu do KHONG bi rong
        tu dau khi vua mo app. Chay tren thread nen vi day la 1 HTTP
        request co the mat vai giay - KHONG duoc chan giao dien luc khoi
        dong app."""
        def _chay_nen():
            # SUA: KHONG coi None (that bai khi goi API) thanh [] (goi
            # THANH CONG nhung khong co du lieu) ngay tai day nua - giu
            # nguyen 2 truong hop KHAC NHAU nay de _on_history_loaded phan
            # biet duoc va bao dung nguyen nhan cho nguoi dung, thay vi gop
            # chung thanh 1 dong chu chung chung "chua co du lieu".
            temp_rows = blynk_client.get_history("V0", period="DAY", granularity="MINUTE")
            humi_rows = blynk_client.get_history("V1", period="DAY", granularity="MINUTE")
            self._history_loaded.emit(temp_rows, humi_rows)
        threading.Thread(target=_chay_nen, daemon=True).start()

    def _on_history_loaded(self, temp_rows, humi_rows):
        """Chay TREN LUONG CHINH cua Qt (nhan qua signal) - an toan de dong
        bo vao widget/deque. Chi THEM du lieu qua khu vao dau bieu do, KHONG
        xoa nhung diem realtime da lo nhan duoc trong luc cho ket qua API
        (hiem khi xay ra nhung van xu ly an toan).

        temp_rows/humi_rows co THE la:
          - None  -> GOI API THAT BAI (loi mang, sai token, Blynk tra ve
            error...) - xem console de biet chi tiet (blynk_client.py da
            tu in ra dong "[Blynk] Loi lay lich su ...").
          - []    -> GOI API THANH CONG nhung KHONG CO du lieu nao trong
            24 gio gan nhat (vd phan cung khong chay lien tuc, chi bat len
            luc test nen khong co gi de Blynk ghi lai truoc do).
          - [...] -> co du lieu, xu ly binh thuong.
        """
        loi_o_pin = []
        so_diem_temp = 0
        so_diem_humi = 0

        if temp_rows is None:
            loi_o_pin.append("nhiệt độ (V0)")
        else:
            diem_moi = []
            for ts_str, val in temp_rows:
                ep = _iso_sang_epoch(ts_str)
                if ep is None or val in (None, ""):
                    continue
                try:
                    diem_moi.append((ep, float(val)))
                except (TypeError, ValueError):
                    continue
            so_diem_temp = len(diem_moi)
            if diem_moi:
                gop = list(self.temp_history) + diem_moi
                gop.sort(key=lambda t: t[0])
                self.temp_history = deque(gop, maxlen=MAX_DIEM)

        if humi_rows is None:
            loi_o_pin.append("độ ẩm (V1)")
        else:
            diem_moi = []
            for ts_str, val in humi_rows:
                ep = _iso_sang_epoch(ts_str)
                if ep is None or val in (None, ""):
                    continue
                try:
                    diem_moi.append((ep, float(val)))
                except (TypeError, ValueError):
                    continue
            so_diem_humi = len(diem_moi)
            if diem_moi:
                gop = list(self.humi_history) + diem_moi
                gop.sort(key=lambda t: t[0])
                self.humi_history = deque(gop, maxlen=MAX_DIEM)

        # SUA: dong nay LUON duoc cap nhat va KHONG BAO GIO bi an di boi du
        # lieu song sau do (khac lbl_empty ben duoi) - de bat cu luc nao
        # nguoi dung cung xem lai duoc: lich su co tai duoc hay khong, tai
        # duoc bao nhieu diem, hay bi loi that su.
        if loi_o_pin:
            self.lbl_trang_thai_lichsu.setText(
                f"Lịch sử: lỗi tải cho {', '.join(loi_o_pin)} (xem console)"
            )
        else:
            self.lbl_trang_thai_lichsu.setText(
                f"Lịch sử: đã nạp {so_diem_temp} điểm nhiệt độ, {so_diem_humi} điểm độ ẩm "
                f"(24 giờ qua từ Blynk Cloud)"
            )

        if self.temp_history or self.humi_history:
            self.lbl_empty.hide()
        elif loi_o_pin:
            # SUA: bao RO RANG day la LOI GOI API (khong phai "chua co du
            # lieu") - de nguoi dung biet ngay can kiem tra console/token,
            # thay vi tuong nham la phan cung chua tung chay bao gio.
            self.lbl_empty.setText(
                f"Không tải được lịch sử Blynk Cloud cho: {', '.join(loi_o_pin)} "
                f"— xem cửa sổ console/terminal để biết chi tiết lỗi."
            )
        else:
            self.lbl_empty.setText(
                "Không có dữ liệu nào trong 24 giờ qua trên Blynk Cloud "
                "(có thể do phần cứng không chạy liên tục, chỉ bật lúc test)."
            )
        self._ve_lai()

    def update_from_blynk(self, data: dict):
        """Goi tu main.py moi khi BlynkPoller doc xong 1 chu ky (vai giay/
        lan). SUA: gio CHI NOI THEM diem moi vao CUOI du lieu da co (bao
        gom ca phan lich su vua nap o load_history_from_blynk) - khong gan
        lai "moc thoi gian 0" theo mau dau tien nhu ban cu nua, vi bieu do
        gio hien thi CA NGAY chu khong chi vai chuc mau gan nhat."""
        now = time.time()
        temp = data.get("temp")
        humi = data.get("humi")

        co_du_lieu_moi = False
        if temp is not None:
            try:
                self.temp_history.append((now, float(temp)))
                co_du_lieu_moi = True
            except (ValueError, TypeError):
                pass
        if humi is not None:
            try:
                self.humi_history.append((now, float(humi)))
                co_du_lieu_moi = True
            except (ValueError, TypeError):
                pass

        if co_du_lieu_moi:
            self.lbl_empty.hide()
            self._ve_lai()

    def _ve_lai(self):
        self.ax_temp.clear()
        self.ax_humi.clear()

        if self.temp_history:
            xs = [datetime.fromtimestamp(t) for t, _ in self.temp_history]
            vals_t = [v for _, v in self.temp_history]
            self.ax_temp.plot(xs, vals_t, color="#d13c3c", label="Nhiệt độ (°C)", linewidth=1.6)
            self.ax_temp.fill_between(xs, vals_t, color="#d13c3c", alpha=0.08)

        if self.humi_history:
            xs = [datetime.fromtimestamp(t) for t, _ in self.humi_history]
            vals_h = [v for _, v in self.humi_history]
            self.ax_humi.plot(xs, vals_h, color="#1857a4", label="Độ ẩm (%)", linewidth=1.6)
            self.ax_humi.fill_between(xs, vals_h, color="#1857a4", alpha=0.08)

        # SUA: MOI truc co thang do RIENG, TU CO GIAN theo du lieu thuc te.
        self.ax_temp.set_title("Nhiệt độ (°C)", fontsize=10, color="#d13c3c", loc="left")
        self.ax_temp.grid(True, alpha=0.25)
        self.ax_temp.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

        self.ax_humi.set_title("Độ ẩm (%)", fontsize=10, color="#1857a4", loc="left")
        self.ax_humi.grid(True, alpha=0.25)
        self.ax_humi.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

        # SUA: xoay nhan truc X CHO TUNG khung rieng (khong dung
        # figure.autofmt_xdate() nua vi ham do chi xoay dung dep khi cac
        # subplot XEP CHONG THEO HANG, gio 2 khung xep CANH NHAU theo cot).
        for ax in (self.ax_temp, self.ax_humi):
            for nhan in ax.get_xticklabels():
                nhan.set_rotation(25)
                nhan.set_ha("right")

        self._cap_nhat_thong_ke()

        self.figure.tight_layout()
        self.canvas.draw()

    def _cap_nhat_thong_ke(self):
        phan = []
        if self.temp_history:
            vals = [v for _, v in self.temp_history]
            phan.append(f"Nhiệt độ: cao {max(vals):.1f}°C · thấp {min(vals):.1f}°C · TB {sum(vals)/len(vals):.1f}°C")
        if self.humi_history:
            vals = [v for _, v in self.humi_history]
            phan.append(f"Độ ẩm: cao {max(vals):.1f}% · thấp {min(vals):.1f}% · TB {sum(vals)/len(vals):.1f}%")
        self.lbl_thongke.setText("   |   ".join(phan))
