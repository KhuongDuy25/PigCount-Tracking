# -*- coding: utf-8 -*-
"""
camera_zone.py
==================
Widget camera cho tab HOME:
 - Hiển thị hình ảnh trực tiếp từ webcam / camera IP (OpenCV VideoCapture).
 - Cho phép người dùng VẼ VÙNG (zone) máng ăn bằng cách click chuột trái
   để thêm điểm, click chuột phải (hoặc double-click) để đóng đa giác.
 - Phát hiện lợn đang ở trong vùng máng ăn dựa trên MÀU SẮC VÙNG LƯNG
   (mỗi con lợn được đánh dấu bằng 1 màu sơn/thẻ màu riêng -> đóng vai trò ID).
   Đây là bản nền tảng đơn giản (color-blob detection bằng HSV), có thể
   nâng cấp sau này thành mô hình AI nhận diện thật (YOLO / DeepSORT...).

Ghi chú: Nếu máy không có camera (hoặc chạy trên server không có thiết bị),
widget sẽ tự chuyển sang "chế độ giả lập" (demo simulation) để giao diện
vẫn hoạt động và có thể thao tác vẽ vùng / xem logic ID hoạt động ra sao.
"""

import time
import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

from PyQt5.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QPolygon, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QGroupBox, QComboBox, QMessageBox
)


# ======================= CẤU HÌNH MODEL YOLO-SEG =======================
# Đổi đường dẫn này thành file model bạn đã train (vd: "runs/segment/train/weights/best.pt").
# Nếu để "yolo26-seg.pt" mà chưa có sẵn, Ultralytics sẽ tự tải model gốc (cần internet)
# — với model đã train riêng cho lợn thì trỏ thẳng vào file .pt của bạn.
YOLO_MODEL_PATH = "yolo26-seg.pt"

# Ngưỡng tin cậy tối thiểu để chấp nhận 1 phát hiện là "lợn"
YOLO_CONF_THRESHOLD = 0.4

# Tên tracker tích hợp sẵn trong Ultralytics: "bytetrack.yaml" hoặc "botsort.yaml"
YOLO_TRACKER = "bytetrack.yaml"

# Nếu model của bạn có NHIỀU CLASS đại diện cho từng cá thể lợn cụ thể
# (vd train riêng theo màu/đốm lưng: "heo_do", "heo_vang"...), đặt True để
# hiển thị theo TÊN CLASS làm ID. Nếu model chỉ có 1 class "pig" chung,
# để False -> ID sẽ lấy theo track_id do tracker cấp (Pig_<id>).
USE_CLASS_NAME_AS_ID = False
class CameraZoneWidget(QWidget):
    """Widget hiển thị camera + vẽ vùng máng ăn + nhận diện ID lợn theo màu lưng."""

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

        self._build_ui()
        self._init_camera()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_frame)
        self.timer.start(66)  # ~15 FPS, đủ mượt và nhẹ CPU

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        title = QLabel("CAMERA MÁNG ĂN — NHẬN DIỆN LỢN THEO ID (MÀU LƯNG)")
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

        gb3 = QGroupBox("Nguồn camera")
        gb3_lay = QVBoxLayout(gb3)
        self.combo_source = QComboBox()
        self.combo_source.addItems(["Camera 0 (mặc định)", "Camera 1", "Chế độ giả lập (demo)"])
        self.combo_source.currentIndexChanged.connect(self._on_source_changed)
        gb3_lay.addWidget(self.combo_source)
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
        colors = list(PIG_COLOR_IDS.values())
        for i, cfg in enumerate(colors):
            cx = int(self.frame_w / 2 + 150 * np.sin(t * 0.4 + i * 1.7))
            cy = int(self.frame_h / 2 + 80 * np.cos(t * 0.3 + i * 2.1))
            cv2.circle(frame, (cx, cy), 26, cfg["draw_bgr"], -1)
            cv2.circle(frame, (cx, cy), 26, (40, 40, 40), 2)
        cv2.putText(frame, "DEMO MODE - khong tim thay camera that",
                    (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 120), 1, cv2.LINE_AA)
        return frame

    def _detect_pig_ids_in_zone(self, frame_bgr):
        """Phát hiện các vùng màu (blob) khớp với bảng màu ID, kiểm tra tâm điểm
        có nằm trong vùng máng ăn (zone) hay không. Trả về (frame_ve, danh_sach_id)."""
        if cv2 is None:
            return frame_bgr, []

        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        found_ids = []
        zone_np = np.array(self.zone_points, dtype=np.int32) if self.zone_points else None

        for pig_id, cfg in PIG_COLOR_IDS.items():
            lower = np.array(cfg["hsv_lower"], dtype=np.uint8)
            upper = np.array(cfg["hsv_upper"], dtype=np.uint8)
            mask = cv2.inRange(hsv, lower, upper)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                area = cv2.contourArea(c)
                if area < MIN_BLOB_AREA:
                    continue
                M = cv2.moments(c)
                if M["m00"] == 0:
                    continue
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])

                inside = True
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

        frame, ids_in_zone = self._detect_pig_ids_in_zone(frame)
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
