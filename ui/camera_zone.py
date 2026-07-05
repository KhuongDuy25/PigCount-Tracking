# -*- coding: utf-8 -*-
"""
camera_zone.py
==================
Widget camera cho tab HOME:
 - Hiển thị hình ảnh trực tiếp từ webcam / camera IP (OpenCV VideoCapture).
 - Cho phép người dùng VẼ VÙNG (zone) máng ăn bằng cách click chuột trái
   để thêm điểm, click chuột phải (hoặc double-click) để đóng đa giác.
 - NHẬN DIỆN LỢN BẰNG MODEL YOLO (yolos26-200.pt) để khoanh vùng chính xác
   từng con vật (không phụ thuộc ánh sáng/tư thế như cách dò màu thuần túy),
   SAU ĐÓ lấy mẫu MÀU SẮC VÙNG LƯNG ngay trong vùng YOLO vừa phát hiện được
   để so khớp với bảng màu ID (PIG_COLOR_IDS) -> GÁN ID cho từng con.

   Nói cách khác: YOLO trả lời "con nào đang ở đâu", còn màu lưng trả lời
   "con đó là con nào (ID gì)" — kết hợp cả 2 để vừa chính xác vừa có ID
   ổn định theo màu sơn/thẻ đánh dấu thực tế trên lưng con vật.

 - Nếu chưa cài `ultralytics` hoặc chưa có file model, tự động rơi về chế độ
   DÒ MÀU THUẦN TÚY (color-blob) như bản cũ để vẫn có thể test được ngay.
 - Nếu máy không có camera, widget tự chuyển sang "chế độ giả lập" (demo).
"""

import time
import json
import os
import numpy as np

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
ZONE_CONFIG_PATH = os.path.join(_BASE_DIR, "zone_config.json")

from PyQt5.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QPolygon, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QGroupBox, QComboBox, QMessageBox
)

# ======================= CẤU HÌNH MODEL YOLO =======================
# Đường dẫn model đã train riêng cho lợn (đổi thành đường dẫn thật trên máy bạn,
# vd "runs/detect/train/weights/yolos26-200.pt" hoặc để cùng thư mục với main.py).
YOLO_MODEL_PATH = "yolos26-200.pt"

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
BACK_REGION_TOP_RATIO = 0.5

# Dung sai (đơn vị Hue OpenCV, 0-179) khi so khớp màu mẫu với bảng màu ID.
COLOR_MATCH_HUE_MARGIN = 6

# Nhãn hiển thị khi màu lưng đo được không khớp bất kỳ ID nào trong bảng.
UNKNOWN_ID_LABEL = "Chua_ro_ID"
UNKNOWN_DRAW_BGR = (140, 140, 140)

# Bảng màu ID lợn: tên hiển thị -> khoảng màu HSV (có thể nhiều dải hue, vd
# màu đỏ vòng qua 2 đầu thang Hue 0 và 179) + màu vẽ (BGR) tương ứng.
PIG_COLOR_IDS = {
    "Lon_Do_01": {
        "hue_ranges": [(0, 8), (170, 179)],  # đỏ nằm ở 2 đầu thang Hue
        "s_range": (120, 255), "v_range": (80, 255),
        "draw_bgr": (0, 0, 255),
    },
    "Lon_Vang_02": {
        "hue_ranges": [(20, 35)],
        "s_range": (120, 255), "v_range": (80, 255),
        "draw_bgr": (0, 220, 255),
    },
    "Lon_Xanhla_03": {
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

MIN_BLOB_AREA = 600  # ngưỡng diện tích tối thiểu (pixel) để coi là 1 con lợn hợp lệ (chế độ dò màu thuần túy)


class CameraZoneWidget(QWidget):
    """Widget hiển thị camera + vẽ vùng máng ăn + nhận diện lợn (YOLO) + gán ID theo màu lưng."""

    zone_status_changed = pyqtSignal(list)  # danh sách ID đang ở trong vùng

    def __init__(self, camera_index=0, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.cap = None
        self.frame_w, self.frame_h = 640, 360

        self.zone_points = []          # các điểm đa giác (tọa độ theo ảnh gốc)
        self.zone_closed = False
        self.drawing_enabled = False

        self.demo_mode = False
        self.demo_t0 = time.time()

        self.model = None
        self.model_ready = False

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

        title = QLabel("CAMERA MÁNG ĂN — YOLO PHÁT HIỆN + MÀU LƯNG GÁN ID")
        title.setStyleSheet("font-weight:700; color:#1857a4; font-size:12px; padding:4px;")
        root.addWidget(title)

        body = QHBoxLayout()
        root.addLayout(body)

        # -- video label (nhận sự kiện chuột để vẽ vùng) --
        self.video_label = QLabel()
        self.video_label.setFixedSize(self.frame_w, self.frame_h)
        self.video_label.setStyleSheet("background:#000; border:2px solid #123f7c; border-radius:4px;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMouseTracking(True)
        self.video_label.mousePressEvent = self._on_mouse_press
        self.video_label.mouseDoubleClickEvent = self._on_mouse_double_click
        body.addWidget(self.video_label)

        # -- panel điều khiển bên phải --
        side = QVBoxLayout()
        body.addLayout(side)

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
        hint.setStyleSheet("color:#555; font-size:11px;")
        gb_lay.addWidget(hint)

        side.addWidget(gb)

        gb2 = QGroupBox("Danh sách ID lợn đang ăn (trong vùng)")
        gb2_lay = QVBoxLayout(gb2)
        self.list_ids = QListWidget()
        gb2_lay.addWidget(self.list_ids)
        side.addWidget(gb2)

        gb3 = QGroupBox("Nguồn camera & Model")
        gb3_lay = QVBoxLayout(gb3)
        self.combo_source = QComboBox()
        self.combo_source.addItems(["Camera 0 (mặc định)", "Camera 1", "Chế độ giả lập (demo)"])
        self.combo_source.currentIndexChanged.connect(self._on_source_changed)
        gb3_lay.addWidget(self.combo_source)

        self.lbl_model_status = QLabel("Model: đang tải...")
        self.lbl_model_status.setWordWrap(True)
        self.lbl_model_status.setStyleSheet("color:#555; font-size:11px;")
        gb3_lay.addWidget(self.lbl_model_status)
        side.addWidget(gb3)

        side.addStretch(1)

    # -------------------------------------------------------------- camera
    def _init_camera(self):
        if cv2 is None:
            self.demo_mode = True
            return
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                self.cap = None
                self.demo_mode = True
        except Exception:
            self.cap = None
            self.demo_mode = True

    def _on_source_changed(self, idx):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        if idx == 2:
            self.demo_mode = True
        else:
            self.demo_mode = False
            self.camera_index = idx
            self._init_camera()

    # ---------------------------------------------------------------- model
    def _init_model(self):
        """Nạp model YOLO (yolos26-200.pt). Nếu lỗi (chưa cài ultralytics /
        thiếu file model), chương trình tự rơi về chế độ DÒ MÀU THUẦN TÚY
        (color-blob) để vẫn hoạt động được, chỉ là kém chính xác hơn."""
        if YOLO is None:
            self.lbl_model_status.setText(
                "⚠️ Chưa cài 'ultralytics' -> đang dùng chế độ dò màu thuần túy.\n"
                "Chạy: pip install ultralytics"
            )
            return
        if not os.path.exists(YOLO_MODEL_PATH):
            self.lbl_model_status.setText(
                f"⚠️ Không tìm thấy model tại: {YOLO_MODEL_PATH}\n"
                "-> đang dùng chế độ dò màu thuần túy."
            )
            return
        try:
            self.model = YOLO(YOLO_MODEL_PATH)
            self.model_ready = True
            class_list = ", ".join(f"{i}:{n}" for i, n in self.model.names.items())
            self.lbl_model_status.setText(
                f"✅ Model đã sẵn sàng: {YOLO_MODEL_PATH}\n"
                f"Class: {class_list}\n"
                f"Đang chỉ nhận diện: {', '.join(TARGET_CLASS_NAMES)}"
            )
        except Exception as e:
            self.model = None
            self.model_ready = False
            self.lbl_model_status.setText(f"⚠️ Lỗi nạp model: {e}\n-> đang dùng chế độ dò màu thuần túy.")

    # ------------------------------------------------------------ drawing
    def _toggle_drawing(self, checked):
        self.drawing_enabled = checked
        if checked:
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

    # -------------------------------------------------------- luu / doc file
    def _save_zone_to_file(self):
        """Ghi danh sach diem cua vung mang an ra file JSON, ton tai qua cac lan mo/tat app."""
        try:
            with open(ZONE_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"zone_points": self.zone_points, "zone_closed": self.zone_closed}, f)
        except Exception as e:
            print(f"[CameraZoneWidget] Khong the luu vung mang an: {e}")

    def _load_zone_from_file(self):
        """Doc lai vung mang an tu file JSON (neu co) luc khoi dong widget."""
        if not os.path.exists(ZONE_CONFIG_PATH):
            return
        try:
            with open(ZONE_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            points = data.get("zone_points", [])
            closed = data.get("zone_closed", False)
            # JSON luu list [x, y] -> doi lai thanh tuple (x, y) de dung voi cv2/QPoint nhu code goc
            self.zone_points = [tuple(p) for p in points]
            self.zone_closed = bool(closed) and len(self.zone_points) >= 3
            if self.zone_closed:
                self.btn_draw.setText("Bắt đầu vẽ vùng máng ăn (đã có vùng đã lưu)")
        except Exception as e:
            print(f"[CameraZoneWidget] Khong the doc vung mang an da luu: {e}")

    def _on_mouse_press(self, event):
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
        """Trả về 1 khung hình BGR (numpy array). Dùng camera thật hoặc demo."""
        if not self.demo_mode and self.cap is not None:
            ok, frame = self.cap.read()
            if ok:
                frame = cv2.resize(frame, (self.frame_w, self.frame_h))
                return frame
            # camera lỗi -> rơi về demo
            self.demo_mode = True

        # ----- chế độ giả lập: vẽ nền chuồng trại + các "con lợn" di chuyển -----
        frame = np.full((self.frame_h, self.frame_w, 3), (235, 245, 250), dtype=np.uint8)
        t = time.time() - self.demo_t0
        colors = [cfg["draw_bgr"] for cfg in PIG_COLOR_IDS.values()]
        for i, draw_bgr in enumerate(colors):
            cx = int(self.frame_w / 2 + 150 * np.sin(t * 0.4 + i * 1.7))
            cy = int(self.frame_h / 2 + 80 * np.cos(t * 0.3 + i * 2.1))
            cv2.circle(frame, (cx, cy), 26, draw_bgr, -1)
            cv2.circle(frame, (cx, cy), 26, (40, 40, 40), 2)
        cv2.putText(frame, "DEMO MODE - khong tim thay camera that",
                    (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 120), 1, cv2.LINE_AA)
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

    # ------------------------------------------------------- YOLO detection
    def _detect_by_yolo_color(self, frame_bgr):
        """Dùng YOLO để phát hiện từng con lợn (bbox hoặc mask segmentation),
        sau đó lấy mẫu màu vùng lưng NGAY TRONG vùng YOLO phát hiện được để
        so khớp bảng màu -> gán ID. Trả về (frame_ve, danh_sach_id_trong_vung)."""
        found_ids = []
        zone_np = np.array(self.zone_points, dtype=np.int32) if self.zone_points else None

        results = self.model.predict(frame_bgr, conf=YOLO_CONF_THRESHOLD, verbose=False)
        if not results:
            return frame_bgr, []

        r = results[0]
        boxes = r.boxes
        masks = r.masks
        if boxes is None or len(boxes) == 0:
            return frame_bgr, []

        cls_ids = boxes.cls.int().tolist()
        class_names = r.names  # dict: id -> tên class (vd {0:"human", 1:"pig"})

        for i in range(len(boxes)):
            cls_name = class_names.get(cls_ids[i], "").lower()
            if cls_name not in TARGET_CLASS_NAMES:
                continue  # BỎ QUA human (hoặc bất kỳ class nào không nằm trong TARGET_CLASS_NAMES)

            x1, y1, x2, y2 = boxes.xyxy[i].tolist()
            x, y, w, h = int(x1), int(y1), int(x2 - x1), int(y2 - y1)

            poly = None
            if masks is not None and i < len(masks.xy):
                poly = np.array(masks.xy[i], dtype=np.int32)

            # tâm điểm: ưu tiên tâm mask, không có thì lấy tâm bbox
            if poly is not None:
                M = cv2.moments(poly)
                cx = int(M["m10"] / M["m00"]) if M["m00"] != 0 else x + w // 2
                cy = int(M["m01"] / M["m00"]) if M["m00"] != 0 else y + h // 2
            else:
                cx, cy = x + w // 2, y + h // 2

            # --- lấy mẫu màu vùng lưng + so khớp bảng màu -> gán ID ---
            mean_hsv = self._sample_back_color_hsv(frame_bgr, x, y, w, h, poly=poly)
            if mean_hsv is None:
                continue
            pig_id, id_color = self._match_color_id(mean_hsv)

            inside = False
            if self.zone_closed and zone_np is not None and len(zone_np) >= 3:
                inside = cv2.pointPolygonTest(zone_np, (cx, cy), False) >= 0

            color = id_color if inside else (150, 150, 150)
            if poly is not None:
                cv2.polylines(frame_bgr, [poly], True, color, 2)
            else:
                cv2.rectangle(frame_bgr, (x, y), (x + w, y + h), color, 2)

            # khung nhỏ đánh dấu đúng vùng lưng đã lấy mẫu màu (để dễ kiểm tra trực quan)
            back_h = max(1, int(h * BACK_REGION_TOP_RATIO))
            cv2.rectangle(frame_bgr, (x, y), (x + w, y + back_h), (255, 255, 0), 1)

            cv2.circle(frame_bgr, (cx, cy), 4, color, -1)
            cv2.putText(frame_bgr, pig_id, (x, max(0, y - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)

            if inside:
                found_ids.append(pig_id)

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

        if cv2 is not None and self.model_ready and self.model is not None:
            frame, ids_in_zone = self._detect_by_yolo_color(frame)
        else:
            frame, ids_in_zone = self._detect_by_color_blob(frame)

        frame = self._draw_zone_overlay(frame)

        # cập nhật danh sách ID đang ăn
        self.list_ids.clear()
        if ids_in_zone:
            for pig_id in ids_in_zone:
                self.list_ids.addItem(f"🐷 {pig_id} — đang ăn tại máng")
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