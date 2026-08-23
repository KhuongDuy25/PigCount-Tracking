# -*- coding: utf-8 -*-
"""
local_client.py
=================
Lớp giao tiếp với ESP32 qua WEB SERVER LOCAL (LAN), dùng khi có WiFi/LAN
nhưng KHÔNG có Internet (không tới được Blynk Cloud), hoặc đơn giản là
người dùng CHỦ ĐỘNG chọn ưu tiên LAN (nhanh hơn, không phụ thuộc mạng
ngoài). Firmware (ChipChinhTest_FULL_da_sua.ino, xem khoiDongWebServerLocal())
mô phỏng ĐÚNG định dạng API của Blynk Cloud (/external/api/get,
/external/api/update), nên lớp này giữ NGUYÊN chữ ký hàm với BlynkClient
(get_pin/set_pin/get_pins/set_pin_async/is_device_online) - có thể dùng
HOÁN ĐỔI cho nhau, xem connection_manager.py.

QUAN TRỌNG - GIỚI HẠN CỦA LOCAL:
Web Server local trên ESP32 CHỈ hỗ trợ ĐÚNG 13 Vpin mà tab MANUAL đang
dùng: V4, V5, V6, V7-V15, V19 (xem docGiaTriPin()/ghiGiaTriPin() trong
firmware). KHÔNG có:
  - Cảm biến V0-V3 (nhiệt độ/độ ẩm/cân nặng/mực nước) - dữ liệu tự động,
    không thiết yếu lúc khẩn cấp, và ESP32 không định kỳ gửi qua kênh này.
  - V16/V17 (lịch hẹn giờ / ngưỡng môi trường) - CHỈ ESP32 lắng nghe qua
    BLYNK_WRITE() khi Cloud gửi xuống, Web Server local KHÔNG có route
    tương ứng -> mọi thao tác Lịch/Ngưỡng trong SettingTab BẮT BUỘC vẫn
    phải đi qua Cloud (xem scheduler.py, main.py cố tình giữ ScheduleSyncer
    dùng thẳng BlynkClient gốc, không qua ConnectionManager).
  - V18 (nội dung cảnh báo gần nhất) - không có route đọc.
"""

import json
import socket
import threading

import requests


# Các pin mà Web Server local trên ESP32 THẬT SỰ hỗ trợ đọc/ghi - khớp
# ĐÚNG danh sách trong docGiaTriPin()/ghiGiaTriPin() của firmware.
LOCAL_SUPPORTED_PINS = {
    "V4", "V5", "V6", "V7", "V8", "V9", "V10",
    "V11", "V12", "V13", "V14", "V15", "V19",
}


class LocalClient:
    """Gọi Web Server LOCAL trên ESP32 qua LAN (mặc định mDNS
    'chuongtrai.local', xem MDNS.begin("chuongtrai") trong firmware)."""

    def __init__(self, host="chuongtrai.local", timeout=3):
        self.host = host
        self.timeout = timeout
        # SUA: cache lại IP sau lần resolve mDNS đầu tiên thành công, để
        # các request sau nhanh hơn (không phải chờ mDNS mỗi lần). Nếu 1
        # request thất bại, xóa cache để lần sau tự resolve lại (phòng
        # trường hợp ESP32 đổi IP do DHCP cấp lại).
        self._resolved_ip = None
        # SUA: THEM MOI - QUAN TRONG. Thu vien WebServer tren ESP32 la
        # DONG BO, chi xu ly duoc 1 KET NOI HTTP tai 1 thoi diem. Neu Python
        # ban song song nhieu request (vd BlynkPoller dang doc + nguoi dung
        # vua bam nut ghi cung luc), ESP32 bi DON REQUEST, cai truoc chua
        # xong cai sau da toi -> timeout day chuyen (day la nguyen nhan
        # chinh gay "Read timed out" lien tuc). Dung 1 Lock de BAT BUOC moi
        # request local phai XEP HANG, chay TUAN TU - dung y het cach
        # ESP32 xu ly duoc (khong hon khong kem).
        self._lock = threading.Lock()

    @property
    def base_url(self):
        host = self._resolved_ip or self.host
        return f"http://{host}"

    def _try_cache_ip(self):
        if self._resolved_ip or not self.host.endswith(".local"):
            return
        try:
            self._resolved_ip = socket.gethostbyname(self.host)
        except Exception:
            pass  # chưa resolve được lúc này - request vẫn thử thẳng bằng hostname .local

    def is_device_online(self):
        """Web Server local KHÔNG có API kiểu isHardwareConnected như
        Cloud - dùng phép thử đọc nhanh V5 làm tín hiệu "còn với tới ESP32
        qua LAN hay không". Trả về True nếu đọc được, False nếu đọc được
        NHƯNG rỗng (hiếm khi xảy ra), None nếu KHÔNG hỏi được (mất LAN/
        ESP32 tắt/sai host)."""
        val = self.get_pin("V5")
        return None if val is None else True

    def get_pin(self, pin):
        # SUA: THEM MOI - Lock: cho request nay CHO neu dang co request khac
        # chay (vd Poller dang doc), tranh ban 2 ket noi song song vao 1
        # WebServer dong bo cua ESP32 (nguyen nhan chinh gay timeout day
        # chuyen truoc day).
        with self._lock:
            self._try_cache_ip()
            try:
                resp = requests.get(
                    f"{self.base_url}/external/api/get",
                    params={pin: ""},
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                text = resp.text.strip()
                if text.startswith("["):
                    arr = json.loads(text)
                    return arr[0] if arr else None
                return text
            except Exception as e:
                print(f"[Local] Lỗi đọc {pin}: {e}")
                self._resolved_ip = None
                return None

    def set_pin(self, pin, value):
        if pin not in LOCAL_SUPPORTED_PINS:
            print(f"[Local] Pin {pin} KHÔNG được Web Server local hỗ trợ - bỏ qua, hãy dùng Cloud cho pin này.")
            return False
        with self._lock:
            self._try_cache_ip()
            try:
                resp = requests.get(
                    f"{self.base_url}/external/api/update",
                    params={pin: value},
                    timeout=self.timeout,
                )
                return resp.ok
            except Exception as e:
                print(f"[Local] Lỗi ghi {pin}={value}: {e}")
                self._resolved_ip = None
                return False

    def get_pins(self, pins):
        """Chỉ hỏi các pin THỰC SỰ được local hỗ trợ (lọc bớt V0-V3/V16-
        V18 nếu lỡ có trong danh sách) - pin không hỗ trợ trả về None
        thẳng, không tốn 1 lượt gọi mạng vô ích."""
        supported = [p for p in pins if p in LOCAL_SUPPORTED_PINS]
        result = {p: None for p in pins}
        if not supported:
            return result
        with self._lock:
            self._try_cache_ip()
            try:
                params = {p: "" for p in supported}
                resp = requests.get(
                    f"{self.base_url}/external/api/get", params=params, timeout=self.timeout
                )
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, dict):
                    normalized = {k.lower(): v for k, v in data.items()}
                    for p in supported:
                        result[p] = normalized.get(p.lower())
                elif isinstance(data, list) and len(supported) == 1:
                    result[supported[0]] = data[0] if data else None
                return result
            except Exception as e:
                print(f"[Local] Lỗi đọc nhiều pin {pins}: {e}")
                self._resolved_ip = None
                return result

    def set_pin_async(self, pin, value, callback=None):
        def _run():
            ok = self.set_pin(pin, value)
            if callback:
                callback(ok)
        threading.Thread(target=_run, daemon=True).start()

    def get_history(self, *args, **kwargs):
        # Web Server local KHÔNG lưu lịch sử - chỉ Cloud (Blynk Historical
        # Data API) mới có. Trả None để chart_tab.py hiểu là "không lấy
        # được", KHÔNG nhầm với [] (gọi được nhưng rỗng).
        print("[Local] get_history() không được hỗ trợ ở Local - cần chuyển sang Cloud để xem lịch sử.")
        return None