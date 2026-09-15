# -*- coding: utf-8 -*-
"""
ui/thin_status_bar.py
========================
Thanh trạng thái MỎNG, đặt NGAY DƯỚI header/nav, LẶP LẠI Ở MỌI TAB (HOME,
MANUAL, SETTING, ALARM, CHART) - giải quyết vấn đề: trước đây CHỈ tab HOME
mới thấy được nhiệt độ/độ ẩm/nguồn đang chọn/trạng thái Cloud, các tab
khác phải quay về HOME mới biết.

Đây KHÔNG phải bản sao của sidebar chi tiết bên HOME - chỉ là 1 dải TÓM
TẮT ngắn gọn, đủ để người dùng liếc qua là biết:
  - Nhiệt độ / độ ẩm hiện tại
  - Cám tồn (báo đỏ khi < 10g) / Mực nước (báo đỏ khi cạn)
  - Đang điều khiển qua nguồn nào (Cloud/Local)
  - ESP32 có đang kết nối Cloud hay không

Cách dùng ở mỗi tab (vd ManualTab, SettingTab...):
    from ui.thin_status_bar import ThinStatusBar
    self.thin_status = ThinStatusBar()
    root.addWidget(self.thin_status)
    ...
    # main.py nối sẵn tín hiệu data_updated -> update_from_blynk() của
    # MỖI tab rồi, nên chỉ cần gọi thêm self.thin_status.update_from_blynk(data)
    # trong hàm update_from_blynk()/sync_from_blynk() sẵn có của tab đó.
"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PyQt5.QtCore import Qt


class ThinStatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("thinStatusBar")
        # SUA: LOI THAT DA GAP - QWidget (khac voi QFrame/QGroupBox) KHONG
        # tu ve background-color dat qua QSS theo objectName, TRU KHI bat
        # co WA_StyledBackground. Thieu dong nay khien nen xanh duong cua
        # thanh trang thai KHONG hien ra (van trong suot, lo nen cream cua
        # cua so chinh phia sau), lam chu TRANG (mau danh cho nen xanh)
        # gan nhu khong doc duoc tren nen sang - dung nguyen nhan gay loi
        # "thanh thinstatus" nguoi dung bao cao.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._build_ui()

    def _build_ui(self):
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 6, 16, 6)
        row.setSpacing(18)

        self.lbl_temp = self._item("NHIỆT ĐỘ", "-- °C")
        self.lbl_humi = self._item("ĐỘ ẨM", "-- %")
        # SUA: THEM MOI - "CAM TON" (V2) va "MUC NUOC" (V3) - du lieu nay
        # DA co san trong dict data (BlynkPoller da doc ca 2 pin nay tu
        # truoc, hoat dong dong nhat o CA Local lan Cloud vi ConnectionManager
        # dung chung 1 interface get_pins() cho 2 nguon), chi la truoc day
        # CHUA duoc hien len thanh nay - nen cac tab khac ngoai HOME khong
        # thay duoc, phai quay ve HOME moi biet.
        self.lbl_cam = self._item("CÁM TỒN", "-- g")
        self.lbl_water = self._item("MỰC NƯỚC", "--")
        row.addWidget(self._divider())
        self.lbl_source = self._item("NGUỒN", "CLOUD")
        self.lbl_cloud = QLabel("ĐANG KIỂM TRA...")
        self.lbl_cloud.setProperty("role", "statusbarItem")
        row.addWidget(self.lbl_cloud)
        row.addStretch(1)

    def _item(self, label, value):
        """Tạo 1 mục 'NHÃN: giá trị' trên thanh, trả về QLabel giá trị để
        tự cập nhật số sau này."""
        wrap = QHBoxLayout()
        wrap.setSpacing(6)
        lbl_name = QLabel(f"{label}:")
        lbl_name.setProperty("role", "statusbarItem")
        lbl_value = QLabel(value)
        lbl_value.setProperty("role", "statusbarValue")
        wrap.addWidget(lbl_name)
        wrap.addWidget(lbl_value)
        container = QWidget()
        container.setLayout(wrap)
        self.layout().addWidget(container)
        return lbl_value

    def _divider(self):
        line = QFrame()
        line.setObjectName("statusbarDivider")
        line.setFrameShape(QFrame.VLine)
        return line

    def update_from_blynk(self, data: dict):
        """Gọi hàm này từ update_from_blynk()/sync_from_blynk() sẵn có của
        MỖI tab, truyền thẳng dict data nhận từ BlynkPoller.data_updated -
        không cần xử lý gì thêm ở nơi gọi."""
        temp = data.get("temp")
        humi = data.get("humi")
        if temp is not None:
            self.lbl_temp.setText(f"{temp} °C")
        if humi is not None:
            self.lbl_humi.setText(f"{humi} %")

        # SUA: THEM MOI - "CAM TON" bao do khi < 10g (nguong nguoi dung tu
        # chon), "MUC NUOC" bao do khi can - giong dung quy uoc hien co ben
        # home_tab.py (water==1 la Day, khac 1 la can).
        cam = data.get("cam")
        if cam is not None:
            try:
                cam_val = float(cam)
                self.lbl_cam.setText(f"{cam_val:g} g")
                self._set_value_warning(self.lbl_cam, cam_val < 10)
            except (TypeError, ValueError):
                self.lbl_cam.setText(str(cam))
                self._set_value_warning(self.lbl_cam, False)

        water = data.get("water")
        if water is not None:
            try:
                is_day = int(float(water)) == 1
                self.lbl_water.setText("Đầy" if is_day else "Cạn")
                self._set_value_warning(self.lbl_water, not is_day)
            except (TypeError, ValueError):
                self.lbl_water.setText("--")
                self._set_value_warning(self.lbl_water, False)

        device_online = data.get("device_online")
        if device_online is True:
            self.lbl_cloud.setText("ĐÃ KẾT NỐI CLOUD")
            self.lbl_cloud.setProperty("role", "status-ok")
        elif device_online is False:
            self.lbl_cloud.setText("MẤT KẾT NỐI CLOUD")
            self.lbl_cloud.setProperty("role", "status-error")
        else:
            self.lbl_cloud.setText("KHÔNG KIỂM TRA ĐƯỢC CLOUD")
            self.lbl_cloud.setProperty("role", "status-warning")
        self.lbl_cloud.style().unpolish(self.lbl_cloud)
        self.lbl_cloud.style().polish(self.lbl_cloud)

    def set_source(self, mode: str):
        """Gọi từ ConnectionManager.on_mode_changed() (qua main.py) mỗi khi
        nguồn Cloud/Local đổi, để thanh trạng thái cập nhật đúng ngay."""
        self.lbl_source.setText("LOCAL (LAN)" if mode == "local" else "CLOUD")

    def _set_value_warning(self, label: QLabel, is_warning: bool):
        """Chuyển 1 ô giá trị (vd Cám tồn/Mực nước) giữa kiểu chữ trắng bình
        thường và kiểu chữ đỏ cảnh báo, giữ nguyên font-size/weight/family
        (chỉ đổi màu) - dùng lại đúng cơ chế property+unpolish/polish mà
        lbl_cloud đã dùng, để nhất quán trong cùng 1 file."""
        label.setProperty("role", "statusbarValueWarning" if is_warning else "statusbarValue")
        label.style().unpolish(label)
        label.style().polish(label)