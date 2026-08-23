# -*- coding: utf-8 -*-
"""
connection_manager.py
========================
Bọc CẢ 2 nguồn điều khiển ESP32 - Cloud (BlynkClient, qua Internet) và
Local (LocalClient, qua LAN/mDNS) - đằng sau 1 giao diện DUY NHẤT, giữ
NGUYÊN chữ ký hàm giống hệt BlynkClient/LocalClient (get_pin/set_pin/
get_pins/set_pin_async/is_device_online/get_history). Nhờ vậy, mọi nơi
đang cầm "blynk_client" trong tay (ManualTab, FeedCoordinator, BlynkPoller,
EmergencyPanel...) KHÔNG CẦN SỬA GÌ - chỉ cần main.py truyền vào 1
ConnectionManager thay vì BlynkClient thô, việc chuyển Cloud/Local diễn ra
HOÀN TOÀN trong suốt với chúng.

Người dùng chủ động chọn nguồn qua công tắc trên tab MANUAL (xem
SourceSwitch trong ui/manual_tab.py) - KHÔNG tự động fallback, để tránh
gây bất ngờ (vd đang tưởng đã gửi lệnh qua Cloud/từ xa nhưng thực ra do
tự động fallback nó lại chỉ chạy trong LAN cục bộ mà người dùng không hay
biết).

LƯU Ý QUAN TRỌNG - CÁC PIN CHỈ CLOUD MỚI HỖ TRỢ:
V0-V3 (cảm biến), V16/V17 (lịch hẹn/ngưỡng môi trường), V18 (log cảnh
báo) KHÔNG có trên Web Server local (xem local_client.py). Vì vậy:
  - scheduler.py (ScheduleSyncer, ghi V16/V17) và chart_tab.py
    (get_history cho V0/V1) trong main.py CỐ Ý được truyền THẲNG
    BlynkClient gốc (self.cloud_client), KHÔNG đi qua ConnectionManager -
    2 việc này LUÔN LUÔN cần Cloud, bất kể người dùng đang chọn nguồn nào
    cho tab MANUAL.
  - Khi ConnectionManager đang ở chế độ "local", BlynkPoller vẫn gọi
    get_pins() với đầy đủ danh sách pin như cũ, nhưng các pin không được
    Local hỗ trợ sẽ tự động trả về None (xem LocalClient.get_pins) - giao
    diện Python sẽ ngừng cập nhật cảm biến/cảnh báo cho tới khi chuyển lại
    Cloud, đây là ĐÁNH ĐỔI CÓ CHỦ Ý khi ưu tiên LAN lúc mất Internet.
"""


class ConnectionManager:
    """mode: "cloud" hoặc "local" - quyết định client nào đang ACTIVE."""

    def __init__(self, cloud_client, local_client, mode="cloud"):
        self.cloud = cloud_client
        self.local = local_client
        self.mode = mode
        self._listeners = []  # callback(mode:str) - gọi mỗi khi set_mode() thành công

    def on_mode_changed(self, callback):
        """Đăng ký callback(mode) - gọi ngay mỗi khi nguồn đổi, để UI khác
        (vd label trạng thái) có thể tự cập nhật theo mà không cần polling."""
        self._listeners.append(callback)

    def set_mode(self, mode):
        if mode not in ("cloud", "local") or mode == self.mode:
            return
        self.mode = mode
        for cb in self._listeners:
            try:
                cb(mode)
            except Exception as e:
                print(f"[ConnectionManager] Lỗi trong listener khi đổi mode: {e}")

    @property
    def active(self):
        return self.cloud if self.mode == "cloud" else self.local

    @property
    def using_local(self):
        """True nếu đang ở chế độ Local - 1 số nơi (vd BlynkPoller) cần cờ
        này để biết đường mà đổi cách xử lý (vd bỏ qua pin Cloud-only)."""
        return self.mode == "local"

    # ----- Giữ NGUYÊN chữ ký hàm của BlynkClient/LocalClient -----
    def get_pin(self, pin):
        return self.active.get_pin(pin)

    def set_pin(self, pin, value):
        return self.active.set_pin(pin, value)

    def get_pins(self, pins):
        return self.active.get_pins(pins)

    def set_pin_async(self, pin, value, callback=None):
        return self.active.set_pin_async(pin, value, callback=callback)

    def is_device_online(self):
        return self.active.is_device_online()

    def get_history(self, *args, **kwargs):
        # Lịch sử CHỈ Cloud có - dù đang ở mode "local" vẫn cố gắng lấy
        # qua Cloud thay vì trả None ngay, vì get_history() thường chỉ gọi
        # 1 lần lúc mở app (chart_tab.py) - không có lý do gì để bó tay
        # nếu Cloud vẫn với tới được dù tab MANUAL đang ưu tiên Local.
        return self.cloud.get_history(*args, **kwargs)