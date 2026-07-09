# -*- coding: utf-8 -*-
"""
blynk_client.py
=================
Lớp giao tiếp với BLYNK CLOUD qua HTTPS API (Blynk 2.0 / blynk.cloud),
dùng ĐÚNG token của project ESP32 hiện tại — không cần sửa firmware.

  - Đọc 1 pin:  GET https://blynk.cloud/external/api/get?token={token}&{pin}
  - Ghi 1 pin:  GET https://blynk.cloud/external/api/update?token={token}&{pin}={value}
"""

import json
import threading
import time

import requests
from PyQt5.QtCore import QThread, pyqtSignal


class BlynkClient:
    """Gọi Blynk Cloud HTTPS API để đọc/ghi virtual pin (V0-V14)."""

    BASE_URL = "https://blynk.cloud/external/api"

    def __init__(self, token, timeout=4):
        self.token = token
        self.timeout = timeout

    def get_pin(self, pin):
        """Đọc giá trị hiện tại của 1 virtual pin. Trả về None nếu lỗi."""
        try:
            resp = requests.get(
                f"{self.BASE_URL}/get",
                params={"token": self.token, pin: ""},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            text = resp.text.strip()
            if text.startswith("["):
                arr = json.loads(text)
                return arr[0] if arr else None
            return text
        except Exception as e:
            print(f"[Blynk] Lỗi đọc {pin}: {e}")
            return None

    def set_pin(self, pin, value):
        """Ghi giá trị xuống 1 virtual pin. Trả về True/False."""
        try:
            resp = requests.get(
                f"{self.BASE_URL}/update",
                params={"token": self.token, pin: value},
                timeout=self.timeout,
            )
            return resp.ok
        except Exception as e:
            print(f"[Blynk] Lỗi ghi {pin}={value}: {e}")
            return False

    def set_pin_async(self, pin, value, callback=None):
        """Ghi pin ở thread nền để KHÔNG làm treo giao diện Qt khi chờ mạng."""
        def _run():
            ok = self.set_pin(pin, value)
            if callback:
                callback(ok)
        threading.Thread(target=_run, daemon=True).start()


class BlynkPoller(QThread):
    """Thread nền, định kỳ đọc các virtual pin cảm biến (V0-V3) từ Blynk Cloud
    và phát tín hiệu `data_updated(dict)` để giao diện Qt cập nhật an toàn."""

    data_updated = pyqtSignal(dict)

    def __init__(self, client: BlynkClient, interval_sec=3, parent=None):
        super().__init__(parent)
        self.client = client
        self.interval_sec = interval_sec
        self._running = True

    def run(self):
        while self._running:
            data = {
                "temp": self.client.get_pin("V0"),
                "humi": self.client.get_pin("V1"),
                "cam": self.client.get_pin("V2"),
                "water": self.client.get_pin("V3"),
            }
            self.data_updated.emit(data)
            for _ in range(self.interval_sec * 10):
                if not self._running:
                    break
                time.sleep(0.1)

    def stop(self):
        self._running = False
        self.wait(1500)
