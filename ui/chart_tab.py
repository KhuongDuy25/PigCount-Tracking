# -*- coding: utf-8 -*-
"""
chart_tab.py — Tab CHART (đã có Heatmap + Đường đi THẬT, không còn placeholder)
==================================================================================
Biểu đồ Nhiệt độ/Độ ẩm: giữ nguyên, dữ liệu thật từ BlynkPoller.

Bản đồ nhiệt (Heatmap) & Đường đi di chuyển của lợn: dữ liệu THẬT, lấy từ
`CameraZoneWidget.position_updated` (camera_zone.py) — mỗi khi YOLO+tracking
phát hiện 1 con vật có ID rõ ràng (đã xác định qua màu lưng), tọa độ tâm của
nó (đã chuẩn hóa 0-1 theo khung hình) được gửi qua đây và lưu vào lịch sử.

- "Heatmap tổng hợp": gộp TẤT CẢ tọa độ của TẤT CẢ ID đã ghi nhận thành 1
  bản đồ mật độ (2D histogram) — cho biết khu vực nào lợn hay tập trung.
- "Đường đi: <ID>": vẽ đường di chuyển của RIÊNG 1 cá thể theo thời gian.
- Vùng máng ăn (zone đã vẽ ở tab HOME) được vẽ chồng lên làm mốc tham chiếu.
- Lịch sử được LƯU RA FILE (`position_history.json`, cùng thư mục gốc dự án)
  định kỳ, không mất khi tắt/mở lại app — theo đúng quy ước đã dùng cho
  zone_config/pig_color_ids/env_config/schedule_config trong dự án.
"""

import os
import json
import time
from collections import deque, defaultdict

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QComboBox, QPushButton
)

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

MAX_DIEM = 60  # so mau gan nhat giu lai de ve bieu do nhiet do/do am (moi mau ~ 1 chu ky polling)

# so diem toi da luu MOI ID cho ban do nhiet/duong di - tranh phinh bo nho/file
# vo han khi chay lien tuc nhieu ngay. ~3000 diem du de xem duong di vai gio.
MAX_DIEM_VI_TRI_MOI_ID = 3000

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSITION_HISTORY_PATH = os.path.join(_BASE_DIR, "position_history.json")

# luu ra file dinh ky (khong luu MOI lan nhan duoc toa do - qua nhieu I/O vi
# camera co the gui toi ~15 lan/giay). Luu sau moi N lan nhan du lieu.
LUU_FILE_MOI_N_LAN = 50


def _mau_mac_dinh_cho_id(real_id):
    """Bang mau du phong don gian (khong phu thuoc camera_zone.py de tranh
    rang buoc import qua lai) - chi dung khi ve duong di 1 ID cu the."""
    bang_mau = ["#d13c3c", "#e8963c", "#2f8f4e", "#1857a4", "#8a5a00", "#7b3fa0"]
    return bang_mau[hash(real_id) % len(bang_mau)]


class ChartTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.temp_history = deque(maxlen=MAX_DIEM)   # (timestamp, gia_tri)
        self.humi_history = deque(maxlen=MAX_DIEM)

        # {real_id: deque[(x_norm, y_norm, timestamp)]}
        self.position_history = defaultdict(lambda: deque(maxlen=MAX_DIEM_VI_TRI_MOI_ID))
        self.zone_norm = []        # danh sach diem vung mang an (da chuan hoa 0-1)
        self.zone_closed = False
        self._so_lan_nhan_toa_do = 0

        self._build_ui()
        self._load_position_history()

        # ve lai ban do THEO CHU KY RIENG (khong ve moi lan nhan toa do - qua
        # nang cho matplotlib neu camera gui toi ~15 lan/giay)
        self._ve_map_timer = QTimer(self)
        self._ve_map_timer.timeout.connect(self._ve_ban_do)
        self._ve_map_timer.start(2000)

    def _build_ui(self):
        root = QHBoxLayout(self)

        # -------- bieu do nhiet do / do am theo thoi gian (du lieu THAT) --------
        gb_chart = QGroupBox("Biểu đồ Nhiệt độ / Độ ẩm theo thời gian (dữ liệu thật)")
        cl = QVBoxLayout(gb_chart)
        self.figure = Figure(figsize=(5, 4))
        self.canvas = FigureCanvas(self.figure)
        self.ax_temp = self.figure.add_subplot(111)
        self.ax_humi = self.ax_temp.twinx()  # truc Y rieng cho do am, tranh "det" duong nhiet do
        cl.addWidget(self.canvas)

        self.lbl_empty = QLabel("Đang chờ dữ liệu từ ESP32...")
        self.lbl_empty.setStyleSheet("color:#999; font-style:italic; padding:6px;")
        cl.addWidget(self.lbl_empty)

        root.addWidget(gb_chart, 2)

        # -------- Ban do nhiet & duong di lon (DU LIEU THAT) --------
        gb_heat = QGroupBox("Bản đồ nhiệt & đường đi di chuyển của lợn")
        hl = QVBoxLayout(gb_heat)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Xem:"))
        self.combo_view = QComboBox()
        self.combo_view.addItem("🔥 Heatmap tổng hợp (tất cả)", userData=None)
        self.combo_view.currentIndexChanged.connect(lambda _: self._ve_ban_do())
        controls.addWidget(self.combo_view, 1)

        self.btn_xoa_lich_su = QPushButton("🗑️ Xóa lịch sử")
        self.btn_xoa_lich_su.clicked.connect(self._xoa_lich_su)
        controls.addWidget(self.btn_xoa_lich_su)
        hl.addLayout(controls)

        self.figure_map = Figure(figsize=(4, 4))
        self.canvas_map = FigureCanvas(self.figure_map)
        self.ax_map = self.figure_map.add_subplot(111)
        hl.addWidget(self.canvas_map)

        self.lbl_map_info = QLabel(
            "Dữ liệu lấy từ camera giám sát ở tab HOME (theo dõi ID qua màu lưng).\n"
            "Cần bật camera + để hệ thống nhận diện được ít nhất 1 lần thì mới có dữ liệu."
        )
        self.lbl_map_info.setWordWrap(True)
        self.lbl_map_info.setStyleSheet("color:#888; font-size:11px; padding-top:4px;")
        hl.addWidget(self.lbl_map_info)

        root.addWidget(gb_heat, 1)

    # ------------------------------------------------------------ nhiet do/do am
    def update_from_blynk(self, data: dict):
        """Goi tu main.py moi khi BlynkPoller doc xong 1 chu ky. Chi THEM
        diem moi khi co gia tri thuc su (khong ve gia tri gia/noi suy khi
        mat ket noi tam thoi), va TU VE LAI bieu do."""
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
            ts_t = [t for t, _ in self.temp_history]
            vals_t = [v for _, v in self.temp_history]
            t0 = ts_t[0]
            x_t = [(t - t0) for t in ts_t]  # giay ke tu mau dau tien hien co trong bo dem
            self.ax_temp.plot(x_t, vals_t, color="#d13c3c", label="Nhiệt độ (°C)", linewidth=2)

        if self.humi_history:
            ts_h = [t for t, _ in self.humi_history]
            vals_h = [v for _, v in self.humi_history]
            t0 = ts_h[0]
            x_h = [(t - t0) for t in ts_h]
            self.ax_humi.plot(x_h, vals_h, color="#1857a4", label="Độ ẩm (%)", linewidth=2)

        self.ax_temp.set_ylabel("Nhiệt độ (°C)", color="#d13c3c")
        self.ax_temp.tick_params(axis="y", labelcolor="#d13c3c")
        self.ax_temp.set_ylim(0, 50)

        self.ax_humi.set_ylabel("Độ ẩm (%)", color="#1857a4")
        self.ax_humi.tick_params(axis="y", labelcolor="#1857a4")
        self.ax_humi.set_ylim(0, 100)

        self.ax_temp.set_xlabel("Giây trước (0 = mới nhất trong khoảng hiển thị)")

        lines_1, labels_1 = self.ax_temp.get_legend_handles_labels()
        lines_2, labels_2 = self.ax_humi.get_legend_handles_labels()
        self.ax_temp.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper right", fontsize=8)

        self.figure.tight_layout()
        self.canvas.draw()

    # ------------------------------------------------------------ vi tri lon (MOI)
    def record_positions(self, payload: dict):
        """Goi tu main.py moi khi CameraZoneWidget.position_updated phat tin
        hieu (xem camera_zone.py). payload = {"positions": {real_id: (x,y)},
        "zone": [...], "zone_closed": bool}."""
        positions = payload.get("positions", {})
        self.zone_norm = payload.get("zone", [])
        self.zone_closed = payload.get("zone_closed", False)

        if not positions:
            return

        now = time.time()
        co_id_moi = False
        for real_id, (x, y) in positions.items():
            if real_id not in self.position_history:
                co_id_moi = True
            self.position_history[real_id].append((x, y, now))

        if co_id_moi:
            self._cap_nhat_danh_sach_id()

        self._so_lan_nhan_toa_do += 1
        if self._so_lan_nhan_toa_do % LUU_FILE_MOI_N_LAN == 0:
            self._save_position_history()

    def _cap_nhat_danh_sach_id(self):
        """Them cac ID moi xuat hien vao combo_view (khong xoa ID cu di dù
        tam thoi khong con trong khung hinh - van con lich su de xem lai)."""
        ten_da_co = {self.combo_view.itemData(i) for i in range(self.combo_view.count())}
        for real_id in self.position_history.keys():
            if real_id not in ten_da_co:
                self.combo_view.addItem(f"🐷 Đường đi: {real_id}", userData=real_id)

    def _xoa_lich_su(self):
        self.position_history.clear()
        self.combo_view.clear()
        self.combo_view.addItem("🔥 Heatmap tổng hợp (tất cả)", userData=None)
        try:
            if os.path.exists(POSITION_HISTORY_PATH):
                os.remove(POSITION_HISTORY_PATH)
        except Exception as e:
            print(f"[ChartTab] Không thể xóa {POSITION_HISTORY_PATH}: {e}")
        self._ve_ban_do()

    # ------------------------------------------------------------ ve ban do
    def _ve_ban_do(self):
        self.ax_map.clear()

        # ve duong vien vung mang an (neu co) lam moc tham chieu truc quan
        if self.zone_norm and self.zone_closed and len(self.zone_norm) >= 3:
            xs = [p[0] for p in self.zone_norm] + [self.zone_norm[0][0]]
            ys = [p[1] for p in self.zone_norm] + [self.zone_norm[0][1]]
            self.ax_map.plot(xs, ys, color="orange", linewidth=1.5, linestyle="--",
                              label="Vùng máng ăn", zorder=10)

        che_do = self.combo_view.currentData()  # None = heatmap tong hop, hoac ten 1 ID cu the

        if che_do is None:
            all_x, all_y = [], []
            for points in self.position_history.values():
                for (x, y, _ts) in points:
                    all_x.append(x)
                    all_y.append(y)

            if all_x:
                h, _xedges, _yedges = np.histogram2d(all_x, all_y, bins=25, range=[[0, 1], [0, 1]])
                self.ax_map.imshow(h.T, origin="upper", extent=[0, 1, 1, 0],
                                   cmap="inferno", aspect="auto", alpha=0.85)
                self.ax_map.set_title(f"Heatmap tổng hợp ({len(all_x)} điểm ghi nhận)", fontsize=10)
            else:
                self.ax_map.text(0.5, 0.5, "Chưa có dữ liệu vị trí", ha="center", va="center",
                                  color="#999")
        else:
            points = self.position_history.get(che_do, [])
            if points:
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                mau = _mau_mac_dinh_cho_id(che_do)
                self.ax_map.plot(xs, ys, color=mau, linewidth=1, alpha=0.6)
                self.ax_map.scatter([xs[-1]], [ys[-1]], color=mau, s=70, zorder=5,
                                    edgecolors="black", label="Vị trí gần nhất")
                self.ax_map.set_title(f"Đường đi: {che_do} ({len(points)} điểm)", fontsize=10)
                self.ax_map.legend(loc="upper right", fontsize=7)
            else:
                self.ax_map.text(0.5, 0.5, "Chưa có dữ liệu vị trí cho ID này",
                                  ha="center", va="center", color="#999")

        self.ax_map.set_xlim(0, 1)
        self.ax_map.set_ylim(1, 0)  # dao truc Y vi (0,0) toa do anh la goc TREN-TRAI
        self.ax_map.set_xticks([])
        self.ax_map.set_yticks([])
        self.figure_map.tight_layout()
        self.canvas_map.draw()

    # ------------------------------------------------------------ luu/doc file
    def _save_position_history(self):
        try:
            data = {
                real_id: [[x, y, ts] for (x, y, ts) in points]
                for real_id, points in self.position_history.items()
            }
            with open(POSITION_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"[ChartTab] Không thể lưu {POSITION_HISTORY_PATH}: {e}")

    def _load_position_history(self):
        if not os.path.exists(POSITION_HISTORY_PATH):
            return
        try:
            with open(POSITION_HISTORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for real_id, points in data.items():
                dq = deque(maxlen=MAX_DIEM_VI_TRI_MOI_ID)
                for p in points[-MAX_DIEM_VI_TRI_MOI_ID:]:
                    dq.append((p[0], p[1], p[2]))
                self.position_history[real_id] = dq
            self._cap_nhat_danh_sach_id()
        except Exception as e:
            print(f"[ChartTab] Không thể đọc {POSITION_HISTORY_PATH}: {e}")