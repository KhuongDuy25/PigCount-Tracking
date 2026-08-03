# -*- coding: utf-8 -*-
"""
camera_zone.py
==================
Widget camera cho tab HOME:
 - Hiển thị hình ảnh trực tiếp từ webcam / camera IP (OpenCV VideoCapture).
 - Cho phép người dùng VẼ VÙNG (zone) máng ăn bằng cách click chuột trái
   để thêm điểm, click chuột phải (hoặc double-click) để đóng đa giác.
 - NHẬN DIỆN + THEO DÕI (TRACKING) LỢN BẰNG MODEL YOLO (model.track(),
   dùng ByteTrack tích hợp sẵn trong ultralytics) để giữ ID mượt giữa các
   khung hình liên tiếp, KẾT HỢP với mẫu MÀU SẮC VÙNG LƯNG để xác định và
   TỰ SỬA ID thật (real_id) mỗi khi phát hiện lệch (đối chiếu định kỳ).

   Nguyên tắc quan trọng: "nguồn sự thật" (source of truth) về ID luôn là
   MÀU LƯNG trên chính con vật (vật lý, sống ngoài đời, không phụ thuộc
   điện/RAM) — KHÔNG BAO GIỜ là tracker_id do ByteTrack cấp (chỉ tồn tại
   trong phiên chạy, mất sạch khi restart app/cúp điện). Nhờ vậy khi mất
   điện rồi có điện lại, frame đầu tiên sau khi khởi động lại app sẽ ĐỌC
   LẠI MÀU và nhận đúng ID ngay lập tức, không cần "nhớ" gì từ trước.
   Xem chi tiết ở hàm `_resolve_real_id()`.

 - Nếu chưa cài `ultralytics` hoặc chưa có file model, tự động rơi về chế độ
   DÒ MÀU THUẦN TÚY (color-blob) như bản cũ để vẫn có thể test được ngay.
 - Nếu máy không có camera, widget tự chuyển sang "chế độ giả lập" (demo).
 - MỚI: CHẾ ĐỘ HIỆU CHỈNH MÀU (calibration) - click vào 1 điểm bất kỳ trên
   video để đo chính xác giá trị HSV camera thực tế nhìn thấy tại điểm đó,
   dùng để xây dựng đúng PIG_COLOR_IDS mà không cần đoán mò. Xem
   `_toggle_calibrate()` / `_on_mouse_press()`.
"""

import time
import json
import os
import re
import threading
import numpy as np
from collections import deque, Counter

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

# ---------------------------------------------------------------------
# YOLO (Ultralytics). Cài đặt:  pip install ultralytics
# ---------------------------------------------------------------------
try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover
    YOLO = None

# File luu vung mang an (zone), dat o thu muc goc du an (ngang hang voi main.py)
# de ton tai qua cac lan tat/mo app.
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZONE_CONFIG_PATH = os.path.join(_BASE_DIR, "zone_config.json")  # zone MAC DINH (khi chua chon camera nao / demo)

# SUA: THEM MOI - ho tro NHIEU CAMERA (nhap URL tren giao dien, khong con
# gan cung stream_url trong code nua). Luu danh sach {ten, url} + camera
# dang chon + che do (camera/demo) ra 1 file JSON o goc du an.
CAMERA_CONFIG_PATH = os.path.join(_BASE_DIR, "camera_config.json")
# SUA: THEM MOI - duong dan TUYET DOI toi file cau hinh ByteTrack rieng
# (track_buffer tang len de bot mat ID khi mat dau ngan han) - dung duong
# dan tuyet doi giong cac config khac o tren, tranh loi neu app duoc chay
# tu 1 thu muc lam viec (working directory) khac thu muc goc du an.
BYTETRACK_CONFIG_PATH = os.path.join(_BASE_DIR, "bytetrack_custom.yaml")

# Chu ky tu dong thu ket noi lai (giay) khi dang o che do "camera" ma bi mat
# ket noi - khong thu lai lien tuc moi frame (66ms) de tranh spam ket noi.
RECONNECT_INTERVAL_SEC = 5


def _sanitize_ten_camera(ten):
    """Doi ten camera (co the co dau/khoang trang) thanh 1 chuoi AN TOAN de
    dat ten file (chi chu/so/gach duoi), dung lam hau to cho file zone rieng
    cua tung camera - vi moi camera thuong dat 1 goc quay/vi tri khac nhau
    trong chuong, nen KHONG THE dung chung 1 vung mang an duy nhat."""
    an_toan = re.sub(r"[^a-zA-Z0-9_\-]", "_", (ten or "").strip())
    return an_toan or "mac_dinh"


def _zone_config_path_cho_camera(ten_camera):
    if not ten_camera:
        return ZONE_CONFIG_PATH
    return os.path.join(_BASE_DIR, f"zone_config_{_sanitize_ten_camera(ten_camera)}.json")

from PyQt5.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QPolygon, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QGroupBox, QComboBox, QMessageBox, QLineEdit, QListWidgetItem, QSizePolicy
)

# SUA: THEM MOI - dung chung 1 kieu "den LED" that (khong phai emoji
# 🟢🟡🔴⚪) cho trang thai ket noi camera, dong bo voi dinh huong "khong
# icon, chi chu + mau" cua toan app.
from ui.style import tao_den_led, doi_mau_den_led, COLOR_ON_GREEN, COLOR_ALARM_RED, COLOR_WARNING_AMBER, COLOR_OFF_GRAY

# ======================= CẤU HÌNH MODEL YOLO =======================
# Duong dan model: dung DUNG hoa/thuong nhu file that tren dia ("Yolos26-200.pt",
# chu Y hoa) - sai hoa/thuong se chay OK tren Windows nhung LOI IM LANG tren
# Linux/macOS (phan biet hoa thuong), roi tu roi ve che do do mau ma khong
# bao loi ro rang. Dung duong dan TUYET DOI (cung thu muc goc voi main.py)
# de khong phu thuoc thu muc dang dung khi chay app.
YOLO_MODEL_PATH = os.path.join(_BASE_DIR, "C:/Users/KhuongDuy/Downloads/Yolos26-200.pt")

# Ngưỡng tin cậy tối thiểu để chấp nhận 1 phát hiện là "lợn"
YOLO_CONF_THRESHOLD = 0.4

# Model bạn train có 2 class: "human" và "pig". CHỈ GIỮ LẠI các class có tên
# nằm trong danh sách này (không phân biệt hoa/thường); mọi detection khác
# (vd "human") sẽ bị BỎ QUA hoàn toàn, không vẽ, không tính vào vùng máng ăn.
# Nếu tên class thật trong model bạn train khác đi (vd "Pig", "heo"...), sửa
# lại danh sách này cho khớp (mở panel "Nguồn camera & Model" ở tab HOME khi
# chạy app để xem chương trình đọc được đúng tên class nào từ model).
TARGET_CLASS_NAMES = {"pig"}

# Tỉ lệ phần TRÊN của khung/khối lợn được coi là "vùng lưng" để lấy mẫu màu
# (0.5 = lấy nửa trên, tránh lấy nhầm màu chân/nền/sàn chuồng phía dưới).
BACK_REGION_TOP_RATIO = 0.8

# Dung sai (đơn vị Hue OpenCV, 0-179) khi so khớp màu mẫu với bảng màu ID.
COLOR_MATCH_HUE_MARGIN = 6

# SUA: Ngưỡng tối thiểu để chấp nhận 1 màu là "marker thật" khi ĐẾM PIXEL
# (thay vì lấy trung bình cả vùng - xem _detect_dominant_marker_color).
# Cần khớp CẢ 2: đủ số pixel tuyệt đối (tránh nhiễu lốm đốm nhỏ) VÀ đủ tỉ lệ
# % diện tích vùng thân (tránh trường hợp vùng thân quá lớn làm % quá nhỏ).
MIN_MARKER_PIXELS = 40
MIN_MARKER_AREA_RATIO = 0.02  # tối thiểu 2% diện tích vùng thân/lưng đã quét

# Nhãn hiển thị khi màu lưng đo được không khớp bất kỳ ID nào trong bảng.
UNKNOWN_ID_LABEL = "Chua_ro_ID"
UNKNOWN_DRAW_BGR = (140, 140, 140)

# ======================= VUNG MAU "NGUY HIEM" (do/hong da) =================
# Dung de canh bao trong CHE DO HIEU CHINH MAU: mau da lon that (mau hong/do
# nhat) va mau do thuong roi vao khoang Hue nay (OpenCV Hue 0-179, do vong
# tron mau nen do nam o CA 2 dau thang: gan 0 VA gan 179). Neu mau ban do
# duoc roi vao day, RAT DE bi lan voi da lon that -> nen doi mau danh dau
# khac (vang, xanh la, xanh duong... nhu ban dang dung).
DANGER_HUE_RANGES = [(0, 12), (168, 179)]
# Nguong bao hoa/do sang thap qua cung de canh bao la "co the la nen/da nhat
# mau, khong phai mau danh dau that" (mau danh dau thuong ruc ro, S/V cao).
DANGER_LOW_SATURATION = 60
DANGER_LOW_VALUE = 60

# File luu bang mau ID lon (co the them/sua/xoa qua che do hieu chinh),
# ton tai qua cac lan tat/mo app - giong het co che cua ZONE_CONFIG_PATH.
PIG_COLOR_IDS_CONFIG_PATH = os.path.join(_BASE_DIR, "pig_color_ids.json")

# Bảng màu ID lợn MẶC ĐỊNH (dùng khi CHƯA có file pig_color_ids.json nào
# được lưu trước đó, vd lần đầu chạy app). Sau khi người dùng lưu ít nhất
# 1 ID qua chế độ hiệu chỉnh, PIG_COLOR_IDS thực tế sẽ được NẠP TỪ FILE,
# không còn dùng bảng mặc định này nữa - xem `_nap_pig_color_ids_tu_file()`.
#s_range:bão hoà
#v_range: độ sáng
DEFAULT_PIG_COLOR_IDS = {
    "Lon_Vang_02": {
        "hue_ranges": [(20, 35)],
        "s_range": (120, 255), "v_range": (80, 255),
        "draw_bgr": (0, 220, 255),
    },
    "Lon_Tim_03": {
        "hue_ranges": [(45, 75)],
        "s_range": (100, 255), "v_range": (70, 255),
        "draw_bgr": (0, 200, 0),
    },
    "Lon_Xanhduong_04": {
        "hue_ranges": [(95, 130)],
        "s_range": (100, 255), "v_range": (70, 255),
        "draw_bgr": (255, 120, 0),
    },
}

# Bien "SONG" thuc su duoc dung o MOI noi khac trong file nay (giu NGUYEN
# TEN CU "PIG_COLOR_IDS" de khong phai sua hang chuc cho tham chieu khac
# trong file) - noi dung se duoc NAP TU FILE JSON (neu co) ngay khi module
# duoc import, hoac fallback ve DEFAULT_PIG_COLOR_IDS neu chua co file nao.
PIG_COLOR_IDS = {}


def _pig_color_ids_tu_dict_luu(data):
    """Chuyen du lieu doc tu JSON (list thay vi tuple) thanh dung dinh dang
    PIG_COLOR_IDS ma cac ham trong file nay dang mong doi (tuple cho
    hue_ranges/s_range/v_range/draw_bgr)."""
    result = {}
    for pig_id, cfg in data.items():
        result[pig_id] = {
            "hue_ranges": [tuple(r) for r in cfg["hue_ranges"]],
            "s_range": tuple(cfg["s_range"]),
            "v_range": tuple(cfg["v_range"]),
            "draw_bgr": tuple(cfg["draw_bgr"]),
        }
    return result


def _nap_pig_color_ids_tu_file():
    """Nap PIG_COLOR_IDS tu file JSON da luu (neu co), fallback ve
    DEFAULT_PIG_COLOR_IDS neu chua tung luu lan nao. Ghi de truc tiep vao
    dict PIG_COLOR_IDS o tren (khong tao dict moi) de moi tham chieu
    `PIG_COLOR_IDS` o cac ham khac trong file van thay dung du lieu moi."""
    global PIG_COLOR_IDS
    PIG_COLOR_IDS.clear()
    if os.path.exists(PIG_COLOR_IDS_CONFIG_PATH):
        try:
            with open(PIG_COLOR_IDS_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            PIG_COLOR_IDS.update(_pig_color_ids_tu_dict_luu(data))
            return
        except Exception as e:
            print(f"[camera_zone] Loi doc pig_color_ids.json, dung mac dinh: {e}")
    PIG_COLOR_IDS.update(DEFAULT_PIG_COLOR_IDS)


def _luu_pig_color_ids_ra_file():
    """Ghi PIG_COLOR_IDS hien tai (da bao gom ID moi them qua hieu chinh)
    ra file JSON, ton tai qua cac lan tat/mo app."""
    try:
        with open(PIG_COLOR_IDS_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(PIG_COLOR_IDS, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[camera_zone] Khong the luu pig_color_ids.json: {e}")


_nap_pig_color_ids_tu_file()  # nap ngay khi module duoc import lan dau

MIN_BLOB_AREA = 600  # ngưỡng diện tích tối thiểu (pixel) để coi là 1 con lợn hợp lệ (chế độ dò màu thuần túy)

# ======================= TRACKING (ByteTrack) + DOI CHIEU MAU DINH KY =======
# tracker_id (do model.track() cap) CHI song trong 1 phien chay, mat het khi
# restart app / cup dien. real_id (ID that, tra tu mau lung) moi la "nguon
# su that" - khong phu thuoc RAM. tracker_id chi dung de theo doi MUOT giua
# cac frame lien tiep trong luc dang chay, KHONG dung de luu tru ID lau dai.
COLOR_HISTORY_LEN = 5          # so mau mau gan nhat luu lai cho moi tracker_id, dung bau chon da so
RECONCILE_INTERVAL_SEC = 8     # chu ky doi chieu lai mau, phat hien tracker bi "trao doi" ID do occlusion
TRACKER_STALE_TIMEOUT_SEC = 30 # tracker_id khong xuat hien qua lau -> don khoi bo nho, tranh phinh to

# ======================= HIEU CHINH MAU (calibration) =======================
CALIBRATE_SAMPLE_RADIUS = 6    # ban kinh (px) vung quet quanh diem click de lay mau trung binh, chong nhieu 1 pixel le


def _hue_to_draw_bgr(h):
    """Tu sinh 1 mau BGR ruc ro DAI DIEN cho Hue do duoc, dung de ve len
    video (khong can nguoi dung tu chon mau ve rieng) - lay S=255,V=255 de
    ra mau tuoi nhat co the, de phan biet."""
    if cv2 is None:
        return (0, 200, 0)
    hsv_px = np.uint8([[[h, 255, 255]]])
    bgr_px = cv2.cvtColor(hsv_px, cv2.COLOR_HSV2BGR)[0][0]
    return tuple(int(c) for c in bgr_px)


class _VideoStreamReader:
    """Doc frame tu camera (webcam/IP) tren 1 LUONG RIENG, chay LIEN TUC va
    LUON GHI DE frame moi nhat - khong xep hang doi. Day la mau "drop-frame"
    chuan cho stream mang: neu ben tieu thu (YOLO/hien thi) xu ly cham hon
    toc do camera gui ve, cac frame cu se TU DONG BI BO QUA thay vi don ung
    trong buffer noi bo cua OpenCV/FFmpeg - day chinh la nguyen nhan gay lag
    2-3 giay cong don theo thoi gian (giong het loi trong testcam.py).
    """

    def __init__(self, source):
        self.source = source
        self.cap = cv2.VideoCapture(source)
        self.frame = None
        self.ret = False
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        if self.cap.isOpened():
            self.running = True
            self.thread = threading.Thread(target=self._update_loop, daemon=True)
            self.thread.start()

    def isOpened(self):
        return self.cap.isOpened()

    def _update_loop(self):
        while self.running:
            ok, frame = self.cap.read()
            if ok:
                with self.lock:
                    self.frame = frame
                    self.ret = True
            else:
                # Doc loi (mat ket noi tam thoi) - nghi 100ms roi thu lai,
                # tranh vong lap chiem 100% CPU khi mat ket noi keo dai
                time.sleep(0.1)

    def read(self):
        """Luon tra ve FRAME MOI NHAT hien co, khong bao gio xep hang doi."""
        with self.lock:
            if self.frame is None:
                return False, None
            return self.ret, self.frame.copy()

    def release(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1.0)
        if self.cap is not None:
            self.cap.release()


class CameraZoneWidget(QWidget):
    """Widget hiển thị camera + vẽ vùng máng ăn + nhận diện lợn (YOLO) + gán ID theo màu lưng."""

    zone_status_changed = pyqtSignal(list)  # danh sách ID đang ở trong vùng
    # SUA: THEM MOI - phat toa do (da chuan hoa 0-1) cua tung real_id moi
    # frame, kem theo vung mang an (cung chuan hoa) de tab CHART ve duoc
    # heatmap/duong di ma khong can biet frame_w/frame_h that cua camera nay.
    position_updated = pyqtSignal(dict)

    def __init__(self, camera_index=0, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.cap = None
        self.frame_w, self.frame_h = 560, 540  # Y cao hon (dang doc) theo yeu cau

        self.zone_points = []          # các điểm đa giác (tọa độ theo ảnh gốc)
        self.zone_closed = False
        self.drawing_enabled = False

        # ---- MOI: da camera (nhap URL tren giao dien, luu lai, chon/xoa duoc) ----
        self.cameras = []              # list[{"ten":.., "url":..}]
        self.active_camera_name = None
        self.source_mode = "demo"      # "demo" | "camera" - mac dinh Demo cho toi khi nguoi dung tu chon
        self.is_connected = False
        self._dang_ket_noi = False     # co danh dau dang co 1 luong nen thu ket noi, tranh chay chong nhau
        self.last_connect_attempt_ms = 0
        self._load_camera_config()     # doc lai danh sach camera + che do da luu (neu co)

        # ---- MOI: che do hieu chinh mau (calibration) ----
        self.calibrating = False
        self._last_frame_bgr = None    # luu lai frame BGR THAT (khong qua ve/annotate) de click do dung mau goc
        self._last_calibration_hsv = None  # (h,s,v) cua lan do gan nhat - dung khi bam "Luu thanh ID moi"

        self.demo_t0 = time.time()

        self.model = None
        self.model_ready = False
        # SUA: THEM MOI - co BAT/TAT nhan dien. True = binh thuong (van
        # chay YOLO/fallback mau nhu cu). False = CHI hien video + duong
        # vien vung mang an, bo qua HOAN TOAN moi tinh toan AI - dung khi
        # nguoi dung chi can XEM camera (canh vi tri vat ly, tiet kiem tai
        # nguyen luc chi can 1 camera dang "nhan dien that", camera con lai
        # chi can xem).
        self.detection_enabled = True

        # --- Trang thai tracking (chi song trong RAM/phien chay hien tai) ---
        self.tracker_id_to_real_id = {}   # tracker_id (ByteTrack) -> real_id (nguon su that = mau)
        self.color_history = {}           # tracker_id -> deque(cac mau mau gan nhat)
        self.last_reconcile_time = {}     # tracker_id -> lan doi chieu gan nhat
        self.tracker_last_seen = {}       # tracker_id -> lan cuoi xuat hien (de don don lieu cu)

        self._build_ui()
        self._init_camera()
        self._init_model()
        self._load_zone_from_file()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_frame)
        self.timer.start(66)  # ~15 FPS, đủ mượt; tăng lên 150-200ms nếu máy yếu / CPU-only

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        body = QHBoxLayout()
        root.addLayout(body)

        # -- video label (nhận sự kiện chuột để vẽ vùng / hiệu chỉnh màu) --
        video_col = QVBoxLayout()
        body.addLayout(video_col)

        # SUA: THEM MOI - hang dieu khien BAT/TAT NHAN DIEN, dat NGAY TREN
        # video de bam nhanh trong luc dang nhin video (vd luc canh vi tri
        # camera vat ly, hoac muon giai phong tai nguyen khi chi can XEM 1
        # camera ma khong can du lieu vi tri luc do). Khi tat: bo qua HOAN
        # TOAN ca 2 nhanh detect (YOLO lan fallback mau) trong _update_frame(),
        # chi con doc + hien thi khung hinh + ve duong vien vung mang an
        # (khong phu thuoc AI de ve).
        hang_detect = QHBoxLayout()
        self.btn_toggle_detect = QPushButton("TẮT NHẬN DIỆN (CHỈ XEM CAM)")
        self.btn_toggle_detect.setCheckable(True)
        self.btn_toggle_detect.setStyleSheet(
            "QPushButton { background:#1857a4; color:white; font-weight:700; border-radius:0px; padding:6px; }"
            "QPushButton:checked { background:#8a8a8a; }"
        )
        self.btn_toggle_detect.clicked.connect(self._toggle_detection)
        hang_detect.addWidget(self.btn_toggle_detect)
        video_col.addLayout(hang_detect)

        self.video_label = QLabel()
        self.video_label.setFixedSize(self.frame_w, self.frame_h)
        self.video_label.setStyleSheet("background:#000; border:2px solid #123f7c; border-radius:0px;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMouseTracking(True)
        self.video_label.mousePressEvent = self._on_mouse_press
        self.video_label.mouseDoubleClickEvent = self._on_mouse_double_click
        video_col.addWidget(self.video_label)

        # -- panel điều khiển bên phải --
        side = QVBoxLayout()
        body.addLayout(side)

        # SUA: sap xep lai dung theo anh mau giao dien nguoi dung yeu cau:
        #   Hang 1: Hiệu chỉnh màu + Nguồn camera (Nguồn camera RỘNG hơn 1 chút)
        #   Hang 2: Điều khiển vùng máng ăn (Zone) + Danh sách ID lợn đang ăn
        #           (2 khoi nay CAO BANG NHAU, dat Maximum size policy cho ca
        #           2 de khong bi "side.addStretch(1)" keo gian khac nhau)
        top_controls_row = QHBoxLayout()
        side.addLayout(top_controls_row)

        bottom_controls_row = QHBoxLayout()
        side.addLayout(bottom_controls_row)

        gb = QGroupBox("Điều khiển vùng máng ăn (Zone)")
        gb_lay = QVBoxLayout(gb)

        self.btn_draw = QPushButton("Bắt đầu vẽ vùng máng ăn")
        self.btn_draw.setCheckable(True)
        self.btn_draw.clicked.connect(self._toggle_drawing)
        gb_lay.addWidget(self.btn_draw)

        self.btn_clear = QPushButton("Xóa vùng đã vẽ")
        self.btn_clear.clicked.connect(self._clear_zone)
        gb_lay.addWidget(self.btn_clear)

        hint = QLabel("Hướng dẫn: bấm 'Bắt đầu vẽ vùng', click trái để thêm\n"
                      "điểm quanh máng ăn, double-click để đóng vùng.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#555; font-size:14px;")
        gb_lay.addWidget(hint)
        # Maximum: khong cho khoi nay bi keo gian cao hon noi dung that su
        # can, de khop chieu cao voi Danh sach ID lon dang an ben canh.
        gb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        bottom_controls_row.addWidget(gb, 1)

        # ---- MOI: khoi HIEU CHINH MAU ----
        gb_cal = QGroupBox("HIỆU CHỈNH MÀU (TEST CAMERA THỰC TẾ)")
        gb_cal_lay = QVBoxLayout(gb_cal)

        self.btn_calibrate = QPushButton("BẬT CHẾ ĐỘ ĐO MÀU (CLICK VÀO ĐIỂM ĐÃ TÔ)")
        self.btn_calibrate.setCheckable(True)
        self.btn_calibrate.clicked.connect(self._toggle_calibrate)
        gb_cal_lay.addWidget(self.btn_calibrate)



        self.lbl_calibration_result = QLabel("Chưa đo màu nào.")
        self.lbl_calibration_result.setWordWrap(True)
        self.lbl_calibration_result.setStyleSheet(
            "background:#fbf8ec; border:1px solid #b9b28e; border-radius:0px; "
            "padding:8px; font-family:monospace; font-size:12px; color:#1e2a3a;"
        )
        gb_cal_lay.addWidget(self.lbl_calibration_result)

        # ---- MOI: dinh danh ngay sau khi do mau ----
        row_name = QHBoxLayout()
        self.input_new_id_name = QLineEdit()
        self.input_new_id_name.setPlaceholderText("Đặt tên ID, vd: Lon_Cam_05")
        row_name.addWidget(self.input_new_id_name)
        gb_cal_lay.addLayout(row_name)

        self.btn_save_new_id = QPushButton("LƯU THÀNH ID MỚI")
        self.btn_save_new_id.setEnabled(False)  # chi bat sau khi da do duoc 1 mau
        self.btn_save_new_id.setStyleSheet(
            "background:#1857a4; color:white; font-weight:700; border-radius:0px; padding:6px;"
        )
        self.btn_save_new_id.clicked.connect(self._luu_id_moi_tu_hieu_chinh)
        gb_cal_lay.addWidget(self.btn_save_new_id)

        gb_cal_lay.addWidget(QLabel("Các ID màu đã lưu:"))
        self.list_saved_ids = QListWidget()
        self.list_saved_ids.setMaximumHeight(100)
        gb_cal_lay.addWidget(self.list_saved_ids)

        self.btn_delete_id = QPushButton("XÓA ID ĐANG CHỌN")
        self.btn_delete_id.clicked.connect(self._xoa_id_dang_chon)
        gb_cal_lay.addWidget(self.btn_delete_id)

        self._refresh_saved_id_list()

        top_controls_row.addWidget(gb_cal, 2)

        gb2 = QGroupBox("Danh sách ID lợn đang ăn (trong vùng)")
        gb2_lay = QVBoxLayout(gb2)
        self.list_ids = QListWidget()
        self.list_ids.setMaximumHeight(140)
        gb2_lay.addWidget(self.list_ids)
        gb2.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        bottom_controls_row.addWidget(gb2, 1)

        gb3 = QGroupBox("Nguồn camera & Model")
        gb3_lay = QVBoxLayout(gb3)

        # ---- Chon che do: Ket noi Camera / Demo ----
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["KẾT NỐI CAMERA", "CHẾ ĐỘ DEMO"])
        self.combo_mode.setCurrentIndex(0 if self.source_mode == "camera" else 1)
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        gb3_lay.addWidget(self.combo_mode)

        # ---- Danh sach camera da luu + nut Ket noi (gop chung "chon" + "ket noi" lam 1) ----
        row_pick = QHBoxLayout()
        self.combo_camera_list = QComboBox()
        row_pick.addWidget(self.combo_camera_list, 1)
        self.btn_connect_selected = QPushButton("KẾT NỐI")
        self.btn_connect_selected.clicked.connect(self._on_connect_clicked)
        row_pick.addWidget(self.btn_connect_selected)
        gb3_lay.addLayout(row_pick)

        self.btn_delete_camera = QPushButton("XÓA CAMERA ĐANG CHỌN")
        self.btn_delete_camera.clicked.connect(self._on_delete_camera)
        gb3_lay.addWidget(self.btn_delete_camera)

        # ---- Them camera moi (ten + URL) ----
        gb3_lay.addWidget(QLabel("Thêm camera mới:"))
        self.input_cam_name = QLineEdit()
        self.input_cam_name.setPlaceholderText("Tên gợi nhớ, vd: Cam máng ăn 1")
        gb3_lay.addWidget(self.input_cam_name)

        self.input_cam_url = QLineEdit()
        self.input_cam_url.setPlaceholderText("URL, vd: http://192.168.1.50:8080/video")
        gb3_lay.addWidget(self.input_cam_url)

        self.btn_save_new_camera = QPushButton("LƯU CAMERA")
        self.btn_save_new_camera.setStyleSheet(
            "background:#1857a4; color:white; font-weight:700; border-radius:0px; padding:5px;"
        )
        self.btn_save_new_camera.clicked.connect(self._on_save_new_camera)
        gb3_lay.addWidget(self.btn_save_new_camera)

        # SUA: THEM MOI - thay label 1 dong (truoc day tu ghep emoji vao
        # dau chuoi) bang 1 hang ngang: den LED THAT (widget hinh tron) +
        # chu trang thai, dung y het kieu "den bao" tren tu dieu khien.
        hang_trang_thai_ket_noi = QHBoxLayout()
        self.den_ket_noi = tao_den_led(COLOR_OFF_GRAY)
        hang_trang_thai_ket_noi.addWidget(self.den_ket_noi)
        self.lbl_connection_status = QLabel("")
        self.lbl_connection_status.setWordWrap(True)
        self.lbl_connection_status.setStyleSheet("font-size:13px; font-weight:700;")
        hang_trang_thai_ket_noi.addWidget(self.lbl_connection_status, 1)
        gb3_lay.addLayout(hang_trang_thai_ket_noi)

        self.lbl_model_status = QLabel("Model: đang tải...")
        self.lbl_model_status.setWordWrap(True)
        self.lbl_model_status.setStyleSheet("color:#555; font-size:14px;")
        gb3_lay.addWidget(self.lbl_model_status)
        gb3.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        # weight=3 (so voi Hieu chinh mau weight=2) -> rong hon mot chut,
        # dung theo yeu cau "cho do dai cua no dai ra hon chut".
        top_controls_row.addWidget(gb3, 3)

        self._refresh_camera_combo()
        self._update_connection_status_label()

        # Ca 2 hang (Hiệu chỉnh màu + Nguồn camera / Zone + Danh sách ID) đều
        # đã bị khóa Maximum size policy ở từng khối con nên không tự tranh
        # giành khoảng trống dư ra trong "side" - stretch=1 cho cả 2 hàng để
        # chúng giữ đúng chiều cao theo nội dung, không bị móp/giãn khác nhau.
        side.setStretchFactor(top_controls_row, 1)
        side.setStretchFactor(bottom_controls_row, 1)

        side.addStretch(1)

    # -------------------------------------------------------------- camera
    def _init_camera(self):
        if cv2 is None:
            self.source_mode = "demo"
            return
        if self.source_mode == "camera":
            self._try_connect_active_camera(force=True)

    def _get_active_camera_url(self):
        for cam in self.cameras:
            if cam["ten"] == self.active_camera_name:
                return cam["url"]
        return None

    def _try_connect_active_camera(self, force=False):
        """Thu ket noi camera dang duoc chon lam active. Neu force=False,
        chi thu lai neu da du RECONNECT_INTERVAL_SEC tu lan thu truoc - tranh
        spam ket noi moi frame (66ms). force=True dung khi nguoi dung bam nut
        'Kết nối' hoac vua chuyen Demo -> Camera (ket noi NGAY LAP TUC, khong
        cho du chu ky).

        SUA: viec ket noi THAT SU (cv2.VideoCapture voi URL mang) duoc day
        sang 1 THREAD RIENG (_ket_noi_nen), vi 2 ly do:
          1. cv2.VideoCapture voi stream mang co the mat vai giay de mo/that
             bai - neu chay thang tren luong chinh se lam DUNG HINH ca giao
             dien trong luc cho.
          2. Thu KET NOI LAI NOI BO vai lan (thay vi 1 lan roi bao that bai
             ngay) - vi stream HTTP MJPEG tu dien thoai (IP Webcam...) rat
             hay that bai NGAU NHIEN o lan thu dau tien (dien thoai "khoi
             dong" HTTP server hoi cham), thanh cong ngay lan thu 2-3 ngay
             sau do - dung 1 nguyen nhan khien truoc day phai bam nut nhieu
             lan moi thany cong."""
        if self.source_mode != "camera":
            return
        if getattr(self, "_dang_ket_noi", False):
            return  # da co 1 luong khac dang thu ket noi, khong chay chong

        now_ms = time.time() * 1000
        if not force and (now_ms - self.last_connect_attempt_ms) < RECONNECT_INTERVAL_SEC * 1000:
            return
        self.last_connect_attempt_ms = now_ms

        url = self._get_active_camera_url()
        if not url:
            self.is_connected = False
            self._update_connection_status_label()
            return

        self._dang_ket_noi = True
        self._update_connection_status_label()
        threading.Thread(target=self._ket_noi_nen, args=(url,), daemon=True).start()

    def _ket_noi_nen(self, url):
        """Chay o thread rieng (KHONG lam dung hinh giao dien). Thu ket noi
        toi da 3 lan, moi lan cach nhau 0.5s, truoc khi coi la that bai han."""
        SO_LAN_THU_LAI_NOI_BO = 3
        cap_moi = None
        for lan in range(SO_LAN_THU_LAI_NOI_BO):
            try:
                ung_vien = _VideoStreamReader(url)
                if ung_vien.isOpened():
                    cap_moi = ung_vien
                    break
                ung_vien.release()
            except Exception:
                pass
            if lan < SO_LAN_THU_LAI_NOI_BO - 1:
                time.sleep(0.5)

        cap_cu = self.cap
        self.cap = cap_moi
        self.is_connected = cap_moi is not None
        self._dang_ket_noi = False
        self._update_connection_status_label()
        if cap_cu is not None:
            cap_cu.release()

    def _update_connection_status_label(self):
        if self.source_mode == "demo":
            doi_mau_den_led(self.den_ket_noi, COLOR_OFF_GRAY)
            self.lbl_connection_status.setText("Đang ở chế độ Demo (không kết nối camera)")
            self.lbl_connection_status.setStyleSheet("color:#666; font-size:13px; font-weight:700;")
        elif not self.active_camera_name:
            doi_mau_den_led(self.den_ket_noi, COLOR_WARNING_AMBER)
            self.lbl_connection_status.setText("Chưa chọn camera nào - hãy thêm/chọn 1 camera")
            self.lbl_connection_status.setStyleSheet("color:#b8860b; font-size:13px; font-weight:700;")
        elif getattr(self, "_dang_ket_noi", False):
            doi_mau_den_led(self.den_ket_noi, COLOR_WARNING_AMBER)
            self.lbl_connection_status.setText(f"Đang kết nối tới '{self.active_camera_name}'...")
            self.lbl_connection_status.setStyleSheet("color:#b8860b; font-size:13px; font-weight:700;")
        elif self.is_connected:
            doi_mau_den_led(self.den_ket_noi, COLOR_ON_GREEN)
            self.lbl_connection_status.setText(f"Đã kết nối: {self.active_camera_name}")
            self.lbl_connection_status.setStyleSheet("color:#2fae4e; font-size:13px; font-weight:700;")
        else:
            doi_mau_den_led(self.den_ket_noi, COLOR_ALARM_RED)
            self.lbl_connection_status.setText(
                f"Mất kết nối tới '{self.active_camera_name}' - đang tự thử lại mỗi {RECONNECT_INTERVAL_SEC}s"
            )
            self.lbl_connection_status.setStyleSheet("color:#d13c3c; font-size:13px; font-weight:700;")

    def _on_mode_changed(self, idx):
        new_mode = "camera" if idx == 0 else "demo"
        if new_mode == self.source_mode:
            return
        self.source_mode = new_mode
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.is_connected = False
        if new_mode == "camera":
            self._try_connect_active_camera(force=True)  # ket noi NGAY, khong cho chu ky retry
        self._update_connection_status_label()
        self._save_camera_config()

    def _refresh_camera_combo(self):
        self.combo_camera_list.blockSignals(True)
        self.combo_camera_list.clear()
        self.combo_camera_list.addItems([c["ten"] for c in self.cameras])
        if self.active_camera_name:
            i = self.combo_camera_list.findText(self.active_camera_name)
            if i >= 0:
                self.combo_camera_list.setCurrentIndex(i)
        self.combo_camera_list.blockSignals(False)

    def _on_save_new_camera(self):
        ten = self.input_cam_name.text().strip()
        url = self.input_cam_url.text().strip()
        if not ten or not url:
            QMessageBox.warning(self, "Thiếu thông tin", "Cần nhập cả tên gợi nhớ và URL camera.")
            return
        if not (url.startswith("http://") or url.startswith("https://") or url.startswith("rtsp://")):
            QMessageBox.warning(
                self, "URL không hợp lệ",
                "URL phải bắt đầu bằng http://, https:// hoặc rtsp:// - kiểm tra lại đường dẫn camera."
            )
            return

        for cam in self.cameras:
            if cam["ten"] == ten:
                cam["url"] = url  # da co ten nay -> cap nhat URL, khong tao trung
                break
        else:
            self.cameras.append({"ten": ten, "url": url})

        self.input_cam_name.clear()
        self.input_cam_url.clear()
        self._refresh_camera_combo()
        self._switch_active_camera(ten)  # them xong -> chon luon lam active

    def _on_delete_camera(self):
        ten = self.combo_camera_list.currentText()
        if not ten:
            return
        self.cameras = [c for c in self.cameras if c["ten"] != ten]

        if self.active_camera_name == ten:
            camera_ke_tiep = self.cameras[0]["ten"] if self.cameras else None
            if camera_ke_tiep:
                self._switch_active_camera(camera_ke_tiep)
            else:
                self.active_camera_name = None
                if self.cap is not None:
                    self.cap.release()
                    self.cap = None
                self.is_connected = False
                self._save_camera_config()
                self._update_connection_status_label()

        self._refresh_camera_combo()

    def _on_connect_clicked(self):
        """Nut 'Kết nối' duy nhất: lay camera dang chon trong dropdown, TU
        DONG chuyen sang che do Camera neu dang o Demo, roi ket noi NGAY -
        gop lam 1 thao tac thay vi phai bam rieng 'Chon' roi 'Ket noi' nhu
        truoc (theo dung yeu cau: chon dropdown + bam Ket noi la xong)."""
        ten = self.combo_camera_list.currentText()
        if not ten:
            QMessageBox.warning(self, "Chưa có camera", "Hãy thêm ít nhất 1 camera (tên + URL) trước.")
            return

        if self.source_mode != "camera":
            self.source_mode = "camera"
            self.combo_mode.blockSignals(True)
            self.combo_mode.setCurrentIndex(0)
            self.combo_mode.blockSignals(False)

        self._switch_active_camera(ten)  # tu goi _try_connect_active_camera(force=True) vi source_mode da la "camera"

    def _switch_active_camera(self, ten_camera):
        """Doi camera dang active: ngat ket noi camera cu, doi sang vung
        mang an RIENG cua camera moi (moi camera 1 goc quay khac nhau nen
        KHONG dung chung 1 vung), roi ket noi ngay neu dang o che do Camera."""
        self.active_camera_name = ten_camera

        self.zone_points = []
        self.zone_closed = False
        self._load_zone_from_file()  # tu doc dung file zone_config_<ten_camera>.json

        if self.source_mode == "camera":
            self._try_connect_active_camera(force=True)

        self._refresh_camera_combo()
        self._save_camera_config()
        self._update_connection_status_label()

    # ---------------------------------------------------- luu/doc cau hinh camera
    def _load_camera_config(self):
        self.cameras = []
        self.active_camera_name = None
        self.source_mode = "demo"
        if not os.path.exists(CAMERA_CONFIG_PATH):
            return
        try:
            with open(CAMERA_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.cameras = data.get("cameras", [])
            self.active_camera_name = data.get("active_camera")
            self.source_mode = data.get("source_mode", "demo")
        except Exception as e:
            print(f"[CameraZoneWidget] Khong doc duoc {CAMERA_CONFIG_PATH}: {e}")

    def _save_camera_config(self):
        try:
            with open(CAMERA_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "cameras": self.cameras,
                    "active_camera": self.active_camera_name,
                    "source_mode": self.source_mode,
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CameraZoneWidget] Khong luu duoc {CAMERA_CONFIG_PATH}: {e}")

    # ---------------------------------------------------------------- model
    def _init_model(self):
        """Nạp model YOLO (yolos26-200.pt). Nếu lỗi (chưa cài ultralytics /
        thiếu file model), chương trình tự rơi về chế độ DÒ MÀU THUẦN TÚY
        (color-blob) để vẫn hoạt động được, chỉ là kém chính xác hơn."""
        if YOLO is None:
            self.lbl_model_status.setProperty("role", "status-warning")
            self.lbl_model_status.setText(
                "Chưa cài 'ultralytics' -> đang dùng chế độ dò màu thuần túy.\n"
                "Chạy: pip install ultralytics"
            )
            self.lbl_model_status.style().unpolish(self.lbl_model_status)
            self.lbl_model_status.style().polish(self.lbl_model_status)
            return
        if not os.path.exists(YOLO_MODEL_PATH):
            self.lbl_model_status.setProperty("role", "status-warning")
            self.lbl_model_status.setText(
                f"Không tìm thấy model tại: {YOLO_MODEL_PATH}\n"
                "-> đang dùng chế độ dò màu thuần túy."
            )
            self.lbl_model_status.style().unpolish(self.lbl_model_status)
            self.lbl_model_status.style().polish(self.lbl_model_status)
            return
        try:
            self.model = YOLO(YOLO_MODEL_PATH)
            self.model_ready = True
            class_list = ", ".join(f"{i}:{n}" for i, n in self.model.names.items())
            self.lbl_model_status.setProperty("role", "status-ok")
            self.lbl_model_status.setText(
                f"Model đã sẵn sàng: {YOLO_MODEL_PATH}\n"
                f"Class: {class_list}\n"
                f"Đang chỉ nhận diện: {', '.join(TARGET_CLASS_NAMES)}"
            )
            self.lbl_model_status.style().unpolish(self.lbl_model_status)
            self.lbl_model_status.style().polish(self.lbl_model_status)
        except Exception as e:
            self.model = None
            self.model_ready = False
            self.lbl_model_status.setProperty("role", "status-error")
            self.lbl_model_status.setText(f"Lỗi nạp model: {e}")
            self.lbl_model_status.style().unpolish(self.lbl_model_status)
            self.lbl_model_status.style().polish(self.lbl_model_status)

    # ------------------------------------------------------------ drawing
    def _toggle_drawing(self, checked):
        self.drawing_enabled = checked
        if checked:
            # Ve vung va hieu chinh mau la 2 viec khac nhau, khong lam cung
            # luc de tranh nham lan click (VD dang do mau ma lo them diem zone)
            if self.calibrating:
                self.calibrating = False
                self.btn_calibrate.setChecked(False)
                self.btn_calibrate.setText("Bật chế độ đo màu (click vào điểm đã tô)")
            self.zone_points = []
            self.zone_closed = False
            self.btn_draw.setText("Đang vẽ... (double-click để đóng)")
        else:
            self.btn_draw.setText("Bắt đầu vẽ vùng máng ăn")

    def _clear_zone(self):
        self.zone_points = []
        self.zone_closed = False
        self.btn_draw.setChecked(False)
        self.btn_draw.setText("Bắt đầu vẽ vùng máng ăn")
        self._save_zone_to_file()  # luu lai trang thai "da xoa" -> lan sau mo app khong bi hien lai vung cu

    # ------------------------------------------------------ bat/tat nhan dien
    def _toggle_detection(self, checked):
        self.detection_enabled = not checked  # nut dang o trang thai "checked" nghia la DA BAM TAT
        self.btn_toggle_detect.setText(
            "BẬT LẠI NHẬN DIỆN" if checked else "TẮT NHẬN DIỆN (CHỈ XEM CAM)"
        )

    # ------------------------------------------------------ hieu chinh mau
    def _toggle_calibrate(self, checked):
        self.calibrating = checked
        self._last_calibration_hsv = None
        self.btn_save_new_id.setEnabled(False)
        if checked:
            # Doi ngay voi che do ve vung, ly do giai thich o _toggle_drawing
            if self.drawing_enabled:
                self.drawing_enabled = False
                self.btn_draw.setChecked(False)
                self.btn_draw.setText("Bắt đầu vẽ vùng máng ăn")
            self.btn_calibrate.setText("Đang đo màu... (click vào chấm đã tô trên video)")
        else:
            self.btn_calibrate.setText("Bật chế độ đo màu (click vào điểm đã tô)")

    def _sample_hsv_at_point(self, x, y):
        """Lay mau HSV trung binh trong 1 vung nho quanh diem (x,y) nguoi
        dung vua click, dua tren frame BGR THAT (chua ve/annotate gi ca) de
        dam bao mau doc duoc la mau camera thuc te nhin thay, khong bi lan
        boi khung/chu ve de len tren."""
        if self._last_frame_bgr is None or cv2 is None:
            return None
        h_img, w_img = self._last_frame_bgr.shape[:2]
        x0 = max(0, x - CALIBRATE_SAMPLE_RADIUS)
        y0 = max(0, y - CALIBRATE_SAMPLE_RADIUS)
        x1 = min(w_img, x + CALIBRATE_SAMPLE_RADIUS)
        y1 = min(h_img, y + CALIBRATE_SAMPLE_RADIUS)
        if x1 <= x0 or y1 <= y0:
            return None
        roi_bgr = self._last_frame_bgr[y0:y1, x0:x1]
        roi_hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
        mean_h, mean_s, mean_v = roi_hsv.reshape(-1, 3).mean(axis=0)
        return int(round(mean_h)), int(round(mean_s)), int(round(mean_v))

    def _is_trong_vung_nguy_hiem(self, h, s, v):
        """Kiem tra mau vua do co roi vao vung 'do/hong da' de canh bao -
        de mau nay TRUNG voi da lon that, rat de gay nham lan/false-positive."""
        for lo, hi in DANGER_HUE_RANGES:
            if lo <= h <= hi:
                return True
        if s < DANGER_LOW_SATURATION or v < DANGER_LOW_VALUE:
            return True  # co the la nen/da nhat mau, khong phai marker ruc ro
        return False

    def _hien_thi_ket_qua_hieu_chinh(self, h, s, v):
        margin = COLOR_MATCH_HUE_MARGIN
        suggested_lo = max(0, h - 8)
        suggested_hi = min(179, h + 8)

        canh_bao = ""
        if self._is_trong_vung_nguy_hiem(h, s, v):
            canh_bao = (
                "\nCẢNH BÁO: màu này rơi vào vùng ĐỎ/HỒNG DA hoặc quá nhạt\n"
                "(dễ trùng màu da lợn thật, dễ gây nhận diện sai)!\n"
            )

        text = (
            f"Kết quả đo (điểm vừa click):\n"
            f"  H = {h}   S = {s}   V = {v}\n"
            f'  "hue_ranges": [({suggested_lo}, {suggested_hi})],\n'
            f'  "s_range": ({max(0, s - 60)}, 255),' f'  "v_range": ({max(0, v - 60)}, 255),'
            f"{canh_bao}"
        )
        self.lbl_calibration_result.setText(text)
        if canh_bao:
            self.lbl_calibration_result.setStyleSheet(
                "background:#fdf0f0; border:1px solid #e24b4a; border-radius:6px; "
                "padding:8px; font-family:monospace; font-size:12px; color:#791f1f;"
            )
        else:
            self.lbl_calibration_result.setStyleSheet(
                "background:#eafaf1; border:1px solid #2fae4e; border-radius:6px; "
                "padding:8px; font-family:monospace; font-size:12px; color:#1c6b2c;"
            )

    def _refresh_saved_id_list(self):
        """Ve lai danh sach cac ID mau dang co trong PIG_COLOR_IDS (bang
        "song" hien tai) len QListWidget ben canh. Luu pig_id THAT vao
        item.data() thay vi parse chuoi hien thi, tranh loi neu sau nay
        doi cach hien thi text ma quen sua ham xoa."""
        self.list_saved_ids.clear()
        for pig_id, cfg in PIG_COLOR_IDS.items():
            lo, hi = cfg["hue_ranges"][0]
            text = f"{pig_id}   (Hue {lo}-{hi})"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, pig_id)
            self.list_saved_ids.addItem(item)

    def _tim_id_chong_lan(self, ten_id_moi, hue_lo, hue_hi):
        """Kiem tra dai Hue (hue_lo,hue_hi) sap luu cho ten_id_moi co CHONG
        LAN voi bat ky ID nao KHAC da co san trong PIG_COLOR_IDS hay khong.
        Tinh CA phan mo rong COLOR_MATCH_HUE_MARGIN (dung dung margin ma
        _match_color_id() ap dung luc nhan dien that), vi 2 dai Hue nhin
        "co ve" tach biet tren giay nhung sau khi cong them margin dung sai
        van co the chong nhau khi chay thuc te. Tra ve list ten cac ID bi
        chong lan (rong neu khong chong ID nao)."""
        lo_moi = max(0, hue_lo - COLOR_MATCH_HUE_MARGIN)
        hi_moi = min(179, hue_hi + COLOR_MATCH_HUE_MARGIN)

        trung = []
        for pig_id, cfg in PIG_COLOR_IDS.items():
            if pig_id == ten_id_moi:
                continue  # dang CAP NHAT chinh no thi khong tinh la chong lan
            for h_lo, h_hi in cfg["hue_ranges"]:
                lo_cu = max(0, h_lo - COLOR_MATCH_HUE_MARGIN)
                hi_cu = min(179, h_hi + COLOR_MATCH_HUE_MARGIN)
                # 2 khoang [lo_moi,hi_moi] va [lo_cu,hi_cu] chong nhau khi:
                if lo_moi <= hi_cu and lo_cu <= hi_moi:
                    trung.append(pig_id)
                    break
        return trung

    def _luu_id_moi_tu_hieu_chinh(self):
        """Bam nut '💾 Lưu thành ID mới': lay ten nguoi dung go + gia tri HSV
        vua do duoc, tinh san dai hue/s/v gioi han, tu sinh mau ve, ghi vao
        PIG_COLOR_IDS (bang dang dung de nhan dien) VA luu ra file JSON de
        ton tai qua cac lan tat/mo app."""
        name = self.input_new_id_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Thiếu tên ID", "Bạn cần đặt tên cho ID này trước khi lưu (vd: Lon_Cam_05).")
            return
        if self._last_calibration_hsv is None:
            QMessageBox.warning(self, "Chưa đo màu", "Bạn cần click vào 1 điểm để đo màu trước khi lưu.")
            return

        h, s, v = self._last_calibration_hsv
        da_ton_tai = name in PIG_COLOR_IDS

        hue_lo_moi = max(0, h - 8)
        hue_hi_moi = min(179, h + 8)
        id_chong_lan = self._tim_id_chong_lan(name, hue_lo_moi, hue_hi_moi)
        if id_chong_lan:
            danh_sach = ", ".join(id_chong_lan)
            xac_nhan = QMessageBox.question(
                self, "CẢNH BÁO TRÙNG DẢI MÀU",
                f"Dải Hue vừa đo ({hue_lo_moi}-{hue_hi_moi}, đã tính cả sai số "
                f"±{COLOR_MATCH_HUE_MARGIN}) CHỒNG LẤN với ID đã có sẵn: {danh_sach}.\n\n"
                f"Nếu vẫn lưu, hệ thống sẽ nhận diện KHÔNG ỔN ĐỊNH giữa '{name}' và "
                f"{danh_sach} (luôn ưu tiên ID nào đứng trước trong file, ID còn lại "
                f"có thể không bao giờ được nhận diện).\n\n"
                f"Bạn vẫn muốn lưu ID này chứ?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if xac_nhan != QMessageBox.Yes:
                self.lbl_calibration_result.setText(
                    f"Đã HỦY lưu '{name}' vì chồng lấn với: {danh_sach}.\n"
                    f"Hãy đo lại ở vị trí màu khác biệt hơn."
                )
                self.lbl_calibration_result.setStyleSheet(
                    "background:#fdf0f0; border:1px solid #e24b4a; border-radius:6px; "
                    "padding:8px; font-family:monospace; font-size:12px; color:#791f1f;"
                )
                return

        PIG_COLOR_IDS[name] = {
            "hue_ranges": [(hue_lo_moi, hue_hi_moi)],
            "s_range": (max(0, s - 60), 255),
            "v_range": (max(0, v - 60), 255),
            "draw_bgr": _hue_to_draw_bgr(h),
        }
        _luu_pig_color_ids_ra_file()
        self._refresh_saved_id_list()

        hanh_dong = "Đã CẬP NHẬT" if da_ton_tai else "Đã THÊM MỚI"
        self.lbl_calibration_result.setText(f"{hanh_dong} ID '{name}' vào bảng màu.\nĐã lưu vào pig_color_ids.json.")
        self.lbl_calibration_result.setStyleSheet(
            "background:#eafaf1; border:1px solid #2fae4e; border-radius:6px; "
            "padding:8px; font-family:monospace; font-size:12px; color:#1c6b2c;"
        )
        self.input_new_id_name.clear()
        self._last_calibration_hsv = None
        self.btn_save_new_id.setEnabled(False)

    def _xoa_id_dang_chon(self):
        """Bam nut 'Xóa ID đang chọn': xoa 1 ID khoi PIG_COLOR_IDS (theo
        pig_id THAT luu trong item.data(), khong parse chuoi hien thi) va
        luu lai file JSON ngay."""
        item = self.list_saved_ids.currentItem()
        if item is None:
            QMessageBox.information(self, "Chưa chọn ID", "Bạn cần chọn 1 ID trong danh sách để xóa.")
            return
        pig_id = item.data(Qt.UserRole)
        xac_nhan = QMessageBox.question(
            self, "Xác nhận xóa", f"Xóa hẳn ID '{pig_id}' khỏi bảng màu?",
            QMessageBox.Yes | QMessageBox.No
        )
        if xac_nhan != QMessageBox.Yes:
            return
        PIG_COLOR_IDS.pop(pig_id, None)
        _luu_pig_color_ids_ra_file()
        self._refresh_saved_id_list()
        self.lbl_calibration_result.setText(f"Đã xóa ID '{pig_id}' khỏi bảng màu.")

    # -------------------------------------------------------- luu / doc file
    def _save_zone_to_file(self):
        """Ghi danh sach diem cua vung mang an ra file JSON RIENG cho camera
        dang active (moi camera 1 goc quay khac nhau -> khong dung chung 1
        vung), ton tai qua cac lan mo/tat app."""
        path = _zone_config_path_cho_camera(self.active_camera_name)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"zone_points": self.zone_points, "zone_closed": self.zone_closed}, f)
        except Exception as e:
            print(f"[CameraZoneWidget] Khong the luu vung mang an ({path}): {e}")

    def _load_zone_from_file(self):
        """Doc lai vung mang an tu file JSON RIENG cua camera dang active
        (neu co) - goi moi khi widget khoi dong HOAC moi khi chuyen camera."""
        path = _zone_config_path_cho_camera(self.active_camera_name)
        if not os.path.exists(path):
            self.btn_draw.setText("Bắt đầu vẽ vùng máng ăn")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            points = data.get("zone_points", [])
            closed = data.get("zone_closed", False)
            # JSON luu list [x, y] -> doi lai thanh tuple (x, y) de dung voi cv2/QPoint nhu code goc
            self.zone_points = [tuple(p) for p in points]
            self.zone_closed = bool(closed) and len(self.zone_points) >= 3
            if self.zone_closed:
                self.btn_draw.setText("Bắt đầu vẽ vùng máng ăn (đã có vùng đã lưu)")
            else:
                self.btn_draw.setText("Bắt đầu vẽ vùng máng ăn")
        except Exception as e:
            print(f"[CameraZoneWidget] Khong the doc vung mang an da luu ({path}): {e}")

    def _on_mouse_press(self, event):
        # MOI: uu tien che do hieu chinh mau neu dang bat, khong lien quan
        # gi toi viec ve vung (2 che do da duoc dam bao khong bao gio cung
        # bat 1 luc trong _toggle_drawing / _toggle_calibrate o tren).
        if self.calibrating and event.button() == Qt.LeftButton:
            x, y = event.pos().x(), event.pos().y()
            result = self._sample_hsv_at_point(x, y)
            if result is not None:
                h, s, v = result
                self._last_calibration_hsv = (h, s, v)
                self.btn_save_new_id.setEnabled(True)
                self._hien_thi_ket_qua_hieu_chinh(h, s, v)
            else:
                self._last_calibration_hsv = None
                self.btn_save_new_id.setEnabled(False)
                self.lbl_calibration_result.setText("Không đọc được màu tại điểm này (thử click lại).")
            return

        if not self.drawing_enabled or self.zone_closed:
            return
        if event.button() == Qt.LeftButton:
            self.zone_points.append((event.pos().x(), event.pos().y()))
        elif event.button() == Qt.RightButton:
            self._close_zone()

    def _on_mouse_double_click(self, event):
        if self.drawing_enabled and not self.zone_closed:
            self._close_zone()

    def _close_zone(self):
        if len(self.zone_points) >= 3:
            self.zone_closed = True
            self.drawing_enabled = False
            self.btn_draw.setChecked(False)
            self.btn_draw.setText("Bắt đầu vẽ vùng máng ăn")
            self._save_zone_to_file()  # luu ngay khi vung duoc dong thanh cong
        else:
            QMessageBox.information(self, "Vùng chưa hợp lệ",
                                     "Cần ít nhất 3 điểm để tạo thành 1 vùng kín.")

    # ------------------------------------------------------------- frame
    def _get_frame(self):
        """Trả về 1 khung hình BGR (numpy array). Dùng camera thật hoặc demo.
        - source_mode == "demo": KHÔNG BAO GIỜ thử kết nối camera, chỉ vẽ demo.
        - source_mode == "camera": nếu đang mất kết nối, TỰ ĐỘNG thử kết nối
          lại theo chu kỳ RECONNECT_INTERVAL_SEC (không spam mỗi frame)."""
        if self.source_mode == "demo":
            return self._ve_frame_demo()

        if self.cap is None or not self.is_connected:
            self._try_connect_active_camera()  # tu gioi han theo chu ky, khong force
            if self.cap is None or not self.is_connected:
                return self._ve_frame_demo(canh_bao="MẤT KẾT NỐI CAMERA - đang tự thử kết nối lại...")

        ok, frame = self.cap.read()
        if ok and frame is not None:
            frame = cv2.resize(frame, (self.frame_w, self.frame_h))
            return frame

        # doc that bai -> danh dau mat ket noi, lan sau _get_frame se tu kich
        # hoat lai _try_connect_active_camera() theo dung chu ky retry
        self.is_connected = False
        self._update_connection_status_label()
        return self._ve_frame_demo(canh_bao="MẤT KẾT NỐI CAMERA - đang tự thử kết nối lại...")

    def _ve_frame_demo(self, canh_bao=None):
        """Ve khung hinh gia lap (chuong trai + cac 'con lon' di chuyen)."""
        frame = np.full((self.frame_h, self.frame_w, 3), (235, 245, 250), dtype=np.uint8)
        t = time.time() - self.demo_t0
        colors = [cfg["draw_bgr"] for cfg in PIG_COLOR_IDS.values()]
        for i, draw_bgr in enumerate(colors):
            cx = int(self.frame_w / 2 + 150 * np.sin(t * 0.4 + i * 1.7))
            cy = int(self.frame_h / 2 + 80 * np.cos(t * 0.3 + i * 2.1))
            cv2.circle(frame, (cx, cy), 26, draw_bgr, -1)
            cv2.circle(frame, (cx, cy), 26, (40, 40, 40), 2)
        text = canh_bao or "DEMO MODE"
        mau_chu = (0, 0, 200) if canh_bao else (0, 0, 120)  # do dam hon neu la canh bao mat ket noi that
        cv2.putText(frame, text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, mau_chu, 1, cv2.LINE_AA)
        return frame

    # ------------------------------------------------------ so khop mau ID
    def _match_color_id(self, hsv_pixel):
        """So sanh 1 mau HSV trung binh voi bang PIG_COLOR_IDS, tra ve
        (pig_id, draw_bgr). Neu khong khop ID nao, tra ve (UNKNOWN, xam)."""
        h, s, v = int(hsv_pixel[0]), int(hsv_pixel[1]), int(hsv_pixel[2])
        for pig_id, cfg in PIG_COLOR_IDS.items():
            s_lo, s_hi = cfg["s_range"]
            v_lo, v_hi = cfg["v_range"]
            if not (s_lo <= s <= s_hi and v_lo <= v <= v_hi):
                continue
            for h_lo, h_hi in cfg["hue_ranges"]:
                lo = max(0, h_lo - COLOR_MATCH_HUE_MARGIN)
                hi = min(179, h_hi + COLOR_MATCH_HUE_MARGIN)
                if lo <= h <= hi:
                    return pig_id, cfg["draw_bgr"]
        return UNKNOWN_ID_LABEL, UNKNOWN_DRAW_BGR

    # ------------------------------------- tracker_id (tam) -> real_id (goc)
    def _resolve_real_id(self, tracker_id, sampled_id, now):
        """
        tracker_id: ID tam thoi do ByteTrack cap (model.track()) - CHI song
                    trong phien chay hien tai, mat sach khi restart/cup dien.
        sampled_id: ID doc duoc tu MAU LUNG trong FRAME NAY (co the None neu
                    khong lay duoc mau, hoac UNKNOWN_ID_LABEL neu khong khop
                    mau nao trong bang).

        Tra ve real_id ON DINH cho tracker_id nay:
        - Lan dau gap tracker_id -> gan ngay theo mau doc duoc (khong cho
          quet du lieu, vi can hien thi ID tu frame dau tien).
        - Cac lan sau, moi RECONCILE_INTERVAL_SEC giay: doi chieu lai bang
          MAU DA SO trong COLOR_HISTORY_LEN mau gan nhat (chong nhieu do 1
          frame le bi sai), neu lech voi real_id dang gan thi TU SUA - day
          la co che phat hien tracker bi "trao doi" ID giua 2 con vat khi
          chung di cat ngang nhau (occlusion), khong lien quan gi toi cup
          dien ma la loi rieng cua thuat toan tracking.
        """
        if tracker_id not in self.color_history:
            self.color_history[tracker_id] = deque(maxlen=COLOR_HISTORY_LEN)

        if sampled_id is not None and sampled_id != UNKNOWN_ID_LABEL:
            self.color_history[tracker_id].append(sampled_id)

        hist = self.color_history[tracker_id]
        majority_id = Counter(hist).most_common(1)[0][0] if hist else UNKNOWN_ID_LABEL

        current_real_id = self.tracker_id_to_real_id.get(tracker_id)

        if current_real_id is None:
            current_real_id = majority_id
            self.tracker_id_to_real_id[tracker_id] = current_real_id
            self.last_reconcile_time[tracker_id] = now
        else:
            last_check = self.last_reconcile_time.get(tracker_id, 0)
            if now - last_check > RECONCILE_INTERVAL_SEC:
                if len(hist) >= 3 and majority_id != UNKNOWN_ID_LABEL and majority_id != current_real_id:
                    print(f"[CameraZoneWidget] Phat hien lech ID: tracker#{tracker_id} "
                          f"{current_real_id} -> {majority_id} (da tu sua sau doi chieu mau).")
                    current_real_id = majority_id
                    self.tracker_id_to_real_id[tracker_id] = current_real_id
                self.last_reconcile_time[tracker_id] = now

        self.tracker_last_seen[tracker_id] = now
        return current_real_id

    def _don_dep_tracker_cu(self, now):
        """Xoa du lieu cua cac tracker_id da lau khong xuat hien (con vat ra
        khoi khung hinh, hoac ByteTrack da bo theo doi) - tranh cac dict
        trang thai phinh to vo han neu chay lien tuc nhieu ngay."""
        stale = [tid for tid, t in self.tracker_last_seen.items()
                 if now - t > TRACKER_STALE_TIMEOUT_SEC]
        for tid in stale:
            self.tracker_id_to_real_id.pop(tid, None)
            self.color_history.pop(tid, None)
            self.last_reconcile_time.pop(tid, None)
            self.tracker_last_seen.pop(tid, None)


    def _sample_back_color_hsv(self, frame_bgr, x, y, w, h, poly=None):
        """Lay mau mau HSV trung binh trong VUNG LUNG (nua tren) cua 1 con vat
        vua duoc YOLO phat hien, uu tien gioi han theo mask segmentation (neu co)
        de tranh lay nham mau nen/san chuong."""
        back_h = max(1, int(h * BACK_REGION_TOP_RATIO))
        y2 = min(frame_bgr.shape[0], y + back_h)
        x2 = min(frame_bgr.shape[1], x + w)
        x0, y0 = max(0, x), max(0, y)
        if y2 <= y0 or x2 <= x0:
            return None

        if poly is not None:
            mask_full = np.zeros(frame_bgr.shape[:2], dtype=np.uint8)
            cv2.fillPoly(mask_full, [poly], 255)
            back_limit = np.zeros_like(mask_full)
            back_limit[y0:y2, x0:x2] = 255
            combined = cv2.bitwise_and(mask_full, back_limit)
            if cv2.countNonZero(combined) == 0:
                return None
            mean_bgr = cv2.mean(frame_bgr, mask=combined)[:3]
        else:
            roi = frame_bgr[y0:y2, x0:x2]
            if roi.size == 0:
                return None
            mean_bgr = roi.reshape(-1, 3).mean(axis=0)

        mean_bgr_np = np.uint8([[mean_bgr]])
        mean_hsv = cv2.cvtColor(mean_bgr_np, cv2.COLOR_BGR2HSV)[0][0]
        return mean_hsv

    def _detect_dominant_marker_color(self, frame_bgr, x, y, w, h, poly=None):
        """SUA: thay vi lay MAU TRUNG BINH ca vung (de bi mieng danh dau nho bi
        "pha loang" boi mau da/long xung quanh - vd mieng xanh nho tren nen hong
        se ra trung binh ngieng ve hong, sai hoan toan), ham nay DEM SO PIXEL
        khop voi tung mau trong PIG_COLOR_IDS ngay trong vung than con vat, va
        chon mau nao co NHIEU PIXEL KHOP NHAT (thay vi trung binh tat ca).
        Tra ve (pig_id_hoac_None, dict_so_pixel_moi_mau) de con debug duoc."""
        x0, y0 = max(0, x), max(0, y)
        x2 = min(frame_bgr.shape[1], x + w)
        y2 = min(frame_bgr.shape[0], y + h)
        if x2 <= x0 or y2 <= y0:
            return None, {}

        # gioi han vung quet trong dung polygon/mask cua con vat (neu co YOLO-seg)
        # de khong bi lan sang nen ban/con vat ben canh
        region_mask = np.zeros(frame_bgr.shape[:2], dtype=np.uint8)
        if poly is not None:
            cv2.fillPoly(region_mask, [poly], 255)
        else:
            region_mask[y0:y2, x0:x2] = 255
        bbox_limit = np.zeros_like(region_mask)
        bbox_limit[y0:y2, x0:x2] = 255
        region_mask = cv2.bitwise_and(region_mask, bbox_limit)

        total_px = cv2.countNonZero(region_mask)
        if total_px == 0:
            return None, {}

        hsv_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)

        counts = {}
        best_id, best_count = None, 0
        for pig_id, cfg in PIG_COLOR_IDS.items():
            s_lo, s_hi = cfg["s_range"]
            v_lo, v_hi = cfg["v_range"]
            color_mask = np.zeros(frame_bgr.shape[:2], dtype=np.uint8)
            for h_lo, h_hi in cfg["hue_ranges"]:
                lo = max(0, h_lo - COLOR_MATCH_HUE_MARGIN)
                hi = min(179, h_hi + COLOR_MATCH_HUE_MARGIN)
                lower = np.array([lo, s_lo, v_lo], dtype=np.uint8)
                upper = np.array([hi, s_hi, v_hi], dtype=np.uint8)
                color_mask |= cv2.inRange(hsv_frame, lower, upper)
            color_mask = cv2.bitwise_and(color_mask, region_mask)
            count = cv2.countNonZero(color_mask)
            counts[pig_id] = count
            if count > best_count:
                best_count = count
                best_id = pig_id

        min_required = max(MIN_MARKER_PIXELS, int(total_px * MIN_MARKER_AREA_RATIO))
        if best_id is None or best_count < min_required:
            return None, counts
        return best_id, counts

    # ------------------------------------------------------- YOLO tracking
    def _detect_by_yolo_track_color(self, frame_bgr):
        """Dung model.track() (ByteTrack tich hop san trong ultralytics) de
        theo doi tung con vat MUOT giua cac frame lien tiep (tracker_id),
        ket hop doi chieu mau lung (real_id) de xac dinh VA TU SUA ID that
        khi phat hien tracker bi trao doi (xem _resolve_real_id). Tra ve
        (frame_ve, danh_sach_real_id_trong_vung)."""
        found_ids = []
        positions_dict = {}  # SUA: THEM MOI - {real_id: (x_norm, y_norm)} cho tab CHART
        zone_np = np.array(self.zone_points, dtype=np.int32) if self.zone_points else None
        now = time.time()

        # persist=True: giu bo nho tracking cua ByteTrack giua cac lan goi
        # (khong phai persist qua restart app - van la trong RAM cua tien
        # trinh dang chay, dung y nghia "tracker tam thoi" da giai thich)
        # SUA: dung file cau hinh ByteTrack RIENG (bytetrack_custom.yaml, o
        # thu muc goc du an) thay vi mac dinh cua ultralytics - tang
        # track_buffer tu 30 len 60 khung hinh, giup nhung lan MAT DAU NGAN
        # HAN (anh mo do di chuyen nhanh) khong bi xoa track va gan ID moi.
        results = self.model.track(frame_bgr, conf=YOLO_CONF_THRESHOLD, persist=True,
                                    tracker=BYTETRACK_CONFIG_PATH, verbose=False)
        if not results:
            return frame_bgr, []

        r = results[0]
        boxes = r.boxes
        masks = r.masks
        if boxes is None or len(boxes) == 0 or boxes.id is None:
            # boxes.id la None khi ByteTrack chua kip cap tracker_id (vd frame
            # dau tien) - bo qua frame nay, frame sau se co
            return frame_bgr, []

        cls_ids = boxes.cls.int().tolist()
        class_names = r.names
        track_ids = boxes.id.int().tolist()

        for i in range(len(boxes)):
            cls_name = class_names.get(cls_ids[i], "").lower()
            if cls_name not in TARGET_CLASS_NAMES:
                continue

            tracker_id = track_ids[i]
            x1, y1, x2, y2 = boxes.xyxy[i].tolist()
            x, y, w, h = int(x1), int(y1), int(x2 - x1), int(y2 - y1)

            poly = None
            if masks is not None and i < len(masks.xy):
                poly = np.array(masks.xy[i], dtype=np.int32)

            if poly is not None:
                M = cv2.moments(poly)
                cx = int(M["m10"] / M["m00"]) if M["m00"] != 0 else x + w // 2
                cy = int(M["m01"] / M["m00"]) if M["m00"] != 0 else y + h // 2
            else:
                cx, cy = x + w // 2, y + h // 2

            sampled_id, _color_counts = self._detect_dominant_marker_color(frame_bgr, x, y, w, h, poly=poly)

            real_id = self._resolve_real_id(tracker_id, sampled_id, now)
            id_color = PIG_COLOR_IDS.get(real_id, {}).get("draw_bgr", UNKNOWN_DRAW_BGR)

            inside = False
            if self.zone_closed and zone_np is not None and len(zone_np) >= 3:
                inside = cv2.pointPolygonTest(zone_np, (cx, cy), False) >= 0

            color = id_color if inside else (150, 150, 150)
            if poly is not None:
                cv2.polylines(frame_bgr, [poly], True, color, 2)
            else:
                cv2.rectangle(frame_bgr, (x, y), (x + w, y + h), color, 2)

            back_h = max(1, int(h * BACK_REGION_TOP_RATIO))
            cv2.rectangle(frame_bgr, (x, y), (x + w, y + back_h), (255, 255, 0), 1)

            cv2.circle(frame_bgr, (cx, cy), 4, color, -1)
            cv2.putText(frame_bgr, f"{real_id} (#{tracker_id})", (x, max(0, y - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2, cv2.LINE_AA)

            if inside:
                found_ids.append(real_id)

            # SUA: THEM MOI - chi ghi lai toa do cho ID DA XAC DINH RO (bo qua
            # "Chua_ro_ID" - khong co y nghia thong ke cho heatmap/duong di
            # theo tung ca the cu the).
            if real_id != UNKNOWN_ID_LABEL:
                positions_dict[real_id] = (cx / self.frame_w, cy / self.frame_h)

        self._don_dep_tracker_cu(now)

        if positions_dict:
            zone_norm = [(px / self.frame_w, py / self.frame_h) for (px, py) in self.zone_points]
            self.position_updated.emit({
                "positions": positions_dict,
                "zone": zone_norm,
                "zone_closed": self.zone_closed,
                # SUA: THEM MOI - gui kem ty le khung hinh THAT (frame_w x
                # frame_h) sang ChartTab, de Heatmap/Trajectory ve DUNG TY
                # LE nhu video that, khong bi keo gian/bop meo do khung ve
                # (Figure) co kich thuoc khac ty le voi khung hinh camera.
                "frame_w": self.frame_w,
                "frame_h": self.frame_h,
                # SUA: THEM MOI (Giai doan 1 - da camera) - gui kem TEN
                # CAMERA dang active, de ChartTab ghi vao CSV va phan biet
                # duoc du lieu vi tri den tu chuong/camera nao. "Demo" khi
                # dang o che do demo (khong co camera that).
                "camera_id": self.active_camera_name or "Demo",
            })

        return frame_bgr, found_ids


    # ---------------------------------------------------- fallback: do mau
    def _detect_by_color_blob(self, frame_bgr):
        """CHẾ ĐỘ DỰ PHÒNG khi chưa có model YOLO: dò trực tiếp các vùng màu
        (color-blob) khớp bảng PIG_COLOR_IDS trên toàn khung hình. Kém chính
        xác hơn YOLO (dễ lẫn nền/ánh sáng) nhưng vẫn giúp app chạy được ngay."""
        if cv2 is None:
            return frame_bgr, []

        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        found_ids = []
        zone_np = np.array(self.zone_points, dtype=np.int32) if self.zone_points else None

        for pig_id, cfg in PIG_COLOR_IDS.items():
            s_lo, s_hi = cfg["s_range"]
            v_lo, v_hi = cfg["v_range"]
            mask_total = np.zeros(hsv.shape[:2], dtype=np.uint8)
            for h_lo, h_hi in cfg["hue_ranges"]:
                lower = np.array([h_lo, s_lo, v_lo], dtype=np.uint8)
                upper = np.array([h_hi, s_hi, v_hi], dtype=np.uint8)
                mask_total |= cv2.inRange(hsv, lower, upper)

            mask_total = cv2.morphologyEx(mask_total, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
            contours, _ = cv2.findContours(mask_total, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                area = cv2.contourArea(c)
                if area < MIN_BLOB_AREA:
                    continue
                M = cv2.moments(c)
                if M["m00"] == 0:
                    continue
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])

                inside = False
                if self.zone_closed and zone_np is not None and len(zone_np) >= 3:
                    inside = cv2.pointPolygonTest(zone_np, (cx, cy), False) >= 0

                color = cfg["draw_bgr"] if inside else (150, 150, 150)
                cv2.drawContours(frame_bgr, [c], -1, color, 2)
                cv2.circle(frame_bgr, (cx, cy), 4, color, -1)
                cv2.putText(frame_bgr, pig_id, (cx - 30, cy - 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

                if inside:
                    found_ids.append(pig_id)
                break  # chỉ lấy blob lớn nhất cho mỗi màu (1 màu = 1 ID)

        return frame_bgr, found_ids

    def _draw_zone_overlay(self, frame_bgr):
        if cv2 is None:
            return frame_bgr
        if len(self.zone_points) >= 2:
            pts = np.array(self.zone_points, dtype=np.int32)
            if self.zone_closed:
                overlay = frame_bgr.copy()
                cv2.fillPoly(overlay, [pts], (0, 215, 255))
                cv2.addWeighted(overlay, 0.25, frame_bgr, 0.75, 0, frame_bgr)
                cv2.polylines(frame_bgr, [pts], True, (0, 165, 255), 2)
            else:
                cv2.polylines(frame_bgr, [pts], False, (0, 165, 255), 2)
        for p in self.zone_points:
            cv2.circle(frame_bgr, p, 4, (0, 100, 255), -1)
        return frame_bgr

    def _update_frame(self):
        frame = self._get_frame()
        if frame is None:
            return

        # MOI: luu lai BAN GOC (chua ve gi ca) TRUOC khi dua qua bat ky ham
        # ve/annotate nao - de che do hieu chinh mau doc dung mau camera
        # thuc te, khong bi lan boi khung/chu vua ve de len tren.
        self._last_frame_bgr = frame.copy()

        if not self.detection_enabled:
            # SUA: THEM MOI - CHI XEM CAMERA, bo qua HOAN TOAN ca 2 nhanh
            # detect (khong goi YOLO, khong goi fallback mau) - tiet kiem
            # toi da tai nguyen CPU/GPU luc chi can nhin video.
            ids_in_zone = []
        elif cv2 is not None and self.model_ready and self.model is not None:
            frame, ids_in_zone = self._detect_by_yolo_track_color(frame)
        else:
            frame, ids_in_zone = self._detect_by_color_blob(frame)

        frame = self._draw_zone_overlay(frame)

        # cập nhật danh sách ID đang ăn
        self.list_ids.clear()
        if not self.detection_enabled:
            self.list_ids.addItem("(Đang tắt nhận diện - chỉ xem camera)")
        elif ids_in_zone:
            for pig_id in ids_in_zone:
                self.list_ids.addItem(f"{pig_id} — đang ăn tại máng")
        else:
            self.list_ids.addItem("(Không có lợn nào trong vùng máng ăn)")
        self.zone_status_changed.emit(ids_in_zone)

        # numpy BGR -> QImage RGB -> hiển thị
        rgb = frame[:, :, ::-1].copy()
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(qimg))

    def closeEvent(self, event):
        if self.cap is not None:
            self.cap.release()
        super().closeEvent(event)