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

    def is_device_online(self):
        """Hoi THANG Blynk Cloud xem ESP32 CO DANG THUC SU ket noi hay
        khong, dung API rieng "isHardwareConnected" - KHAC HAN voi
        get_pin()/get_pins(): doc gia tri pin van "thanh cong" binh thuong
        du thiet bi da offline tu lau, vi Blynk Cloud tra ve GIA TRI CACHE
        CUOI CUNG chu khong bao loi gi ca. Day la CACH DUY NHAT de biet
        DUNG trang thai online/offline that su cua ESP32.

        Tra ve True/False, hoac None neu KHONG hoi duoc (loi mang/token -
        khac voi False, vi False nghia la HOI DUOC va biet chac la offline,
        con None nghia la KHONG BIET vi chinh viec hoi cung that bai)."""
        try:
            resp = requests.get(
                f"{self.BASE_URL}/isHardwareConnected",
                params={"token": self.token},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            text = resp.text.strip().lower()
            return text == "true"
        except Exception as e:
            print(f"[Blynk] Lỗi kiểm tra trạng thái online: {e}")
            return None

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

    def get_pins(self, pins):
        """Đọc NHIỀU virtual pin trong 1 request duy nhất (Blynk hỗ trợ gộp
        nhiều tham số pin vào 1 lần gọi /get, trả về dict {pin: value}).
        Dùng cho polling định kỳ (BlynkPoller) để tránh gọi API riêng lẻ
        từng pin một, vừa chậm vừa dễ bị giới hạn tần suất (rate limit)."""
        try:
            params = {"token": self.token}
            for p in pins:
                params[p] = ""
            resp = requests.get(f"{self.BASE_URL}/get", params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                return {}
            # SUA: Blynk Cloud tra ve key dang VIET THUONG (vd "v0") du minh
            # goi voi ten pin VIET HOA ("V0") trong request - neu tra cuu
            # thang bang raw.get("V0") se LUON ra None do lech hoa/thuong,
            # am tham lam ca polling cam bien LAN dong bo 2 chieu deu hong.
            # Chuan hoa lai ve dung ten pin da yeu cau (khong phan biet hoa
            # thuong khi so khop) de tranh loi nay hoan toan.
            normalized = {k.lower(): v for k, v in data.items()}
            return {p: normalized.get(p.lower()) for p in pins}
        except Exception as e:
            print(f"[Blynk] Lỗi đọc nhiều pin {pins}: {e}")
            return {}

    def get_history(self, pin, period="DAY", granularity="MINUTE", tz_name="Asia/Ho_Chi_Minh", timeout=15):
        """Lay LICH SU 1 pin tu Blynk Cloud (API 'Get Historical Data') -
        CHI nen goi 1 LAN LUC MO APP, vi Blynk GIOI HAN TOI DA 10 LAN GOI
        API NAY / THIET BI / NGAY (xem docs.blynk.io/blynk.console/limits).
        Goi lien tuc/lap lai se rat nhanh het quota.

        LUU Y: theo tai lieu chinh thuc, API nay co tham so "output" quyet
        dinh dang phan hoi - MAC DINH la "FILE" (tra ve {"link": "...zip"},
        phai tu tai + giai nen CSV ben trong), con "output=JSON" tra thang
        JSON ve luon (khong can tai file rieng). SUA: TRUOC DAY code khong
        truyen tham so nay nen LUON di theo nhanh ZIP (phuc tap, nhieu buoc
        co the loi hon) - gio ep thang "output=JSON" cho don gian, it diem
        loi hon va de debug hon. Ham nay VAN giu lai nhanh xu ly ZIP/"link"
        de phong truong hop server bo qua tham so output va van tra "link".

        Tra ve None neu goi that bai THAT SU (loi mang/token/HTTP loi) -
        KHONG lam crash app; tra ve [] (danh sach RONG) neu goi THANH CONG
        nhung Blynk khong co du lieu nao trong khoang thoi gian yeu cau."""
        try:
            resp = requests.get(
                f"{self.BASE_URL}/data/get",
                params={
                    "token": self.token,
                    "period": period,
                    "granularityType": granularity,
                    "sourceType": "AVG",
                    "tzName": tz_name,
                    "format": "ISO_SIMPLE",
                    "output": "JSON",  # SUA: THEM MOI - ep tra JSON truc tiep, bo qua nhanh tai file ZIP
                    "pin": pin,
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            payload = resp.json()

            if isinstance(payload, dict) and "error" in payload:
                print(f"[Blynk] Lỗi lấy lịch sử {pin}: {payload['error']}")
                return None

            # Kieu (b): du lieu JSON tra thang ve
            if isinstance(payload, dict) and "data" in payload:
                # SUA: BUG THAT (thay tu log console): Blynk tra ve moi
                # dong trong "data" dang LIST ["2026-07-31 05:39:00", 30]
                # chu KHONG PHAI dict {"ts":.., "value":..} nhu code truoc
                # gia dinh -> goi row.get(...) tren 1 list se nem loi
                # "'list' object has no attribute 'get'". Gio xu ly duoc
                # CA 2 dang (dict LAN list/tuple) de an toan voi moi kieu
                # phan hoi Blynk co the tra ve.
                ket_qua = []
                for row in payload["data"]:
                    if isinstance(row, dict):
                        ket_qua.append((row.get("ts"), row.get("value")))
                    elif isinstance(row, (list, tuple)) and len(row) >= 2:
                        ket_qua.append((row[0], row[1]))
                    else:
                        print(f"[Blynk] Bỏ qua 1 dòng lịch sử {pin} có định dạng lạ: {row!r}")
                # SUA: THEM MOI - luon in ra so dong THO nhan duoc (truoc khi
                # chart_tab.py loc/parse them) de lan sau neu van ra "0
                # diem" thi biet ngay la do BLYNK TRA VE RONG THAT (khong
                # phai do parse sai o phia app) - kem theo "rows"/"meta" tho
                # Blynk co gui kem, giup doi chieu nhanh.
                print(f"[Blynk] Lịch sử {pin} (period={period}, granularity={granularity}): "
                      f"nhận {len(ket_qua)} dòng thô từ Blynk "
                      f"(rows_before_limit={payload.get('rows_before_limit_at_least', '?')})")
                return ket_qua

            # Kieu (a): can tai file ZIP roi giai nen doc CSV ben trong
            # (du da ep output=JSON, van giu nhanh nay de phong Blynk bo
            # qua tham so va tra "link" nhu cu)
            if isinstance(payload, dict) and "link" in payload:
                print(f"[Blynk] Lịch sử {pin}: Blynk vẫn trả về dạng file ZIP dù đã yêu cầu JSON, đang tải: {payload['link']}")
                return self._tai_va_doc_zip_lich_su(payload["link"], timeout)

            print(f"[Blynk] Định dạng phản hồi lịch sử {pin} không như dự kiến: {payload}")
            return None
        except Exception as e:
            print(f"[Blynk] Lỗi lấy lịch sử {pin}: {e}")
            return None

    def _tai_va_doc_zip_lich_su(self, link, timeout):
        """Tai file ZIP tu 'link' Blynk tra ve, giai nen va doc file CSV
        (hoac tuong tu) ben trong ra list (timestamp_str, value)."""
        import io
        import zipfile

        try:
            r = requests.get(link, timeout=timeout)
            r.raise_for_status()
            ket_qua = []
            with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                for ten_file in zf.namelist():
                    with zf.open(ten_file) as f:
                        noi_dung = f.read().decode("utf-8", errors="ignore")
                        cac_dong = noi_dung.strip().split("\n")
                        for dong in cac_dong[1:]:  # bo dong tieu de
                            phan = dong.split(";") if ";" in dong else dong.split(",")
                            if len(phan) >= 2:
                                ket_qua.append((phan[0].strip(), phan[1].strip()))
                    # SUA: THEM MOI - log so dong THO trong file (ke ca
                    # dong tieu de) de biet ngay file ZIP co THUC SU rong
                    # hay khong, thay vi chi thay ket qua cuoi cung la 0.
                    print(f"[Blynk] File '{ten_file}' trong ZIP có {len(cac_dong)} dòng (kể cả tiêu đề)")
            return ket_qua
        except Exception as e:
            print(f"[Blynk] Lỗi tải/đọc file ZIP lịch sử: {e}")
            return None

    def set_pin_async(self, pin, value, callback=None):
        """Ghi pin ở thread nền để KHÔNG làm treo giao diện Qt khi chờ mạng."""
        def _run():
            ok = self.set_pin(pin, value)
            if callback:
                callback(ok)
        threading.Thread(target=_run, daemon=True).start()


class BlynkPoller(QThread):
    """Thread nền, định kỳ đọc CẢ cảm biến (V0-V3) LẪN trạng thái relay/mode
    (V5-V14) từ Blynk Cloud, phát tín hiệu `data_updated(dict)` để giao diện
    Qt cập nhật an toàn. Đây là phần "chiều ngược lại" của đồng bộ 2 chiều:
    khi người dùng bấm nút trên app MOBILE (hoặc AUTO tự điều khiển), giao
    diện Python cũng phải phản ánh đúng, không chỉ 1 chiều Python -> Blynk
    như trước đây (set_pin_async)."""

    data_updated = pyqtSignal(dict)

    SENSOR_PINS = ["V0", "V1", "V2", "V3"]
    DEVICE_PINS = ["V5", "V6", "V7", "V8", "V9", "V10", "V11", "V12", "V13", "V14"]
    ALARM_PIN = "V18"  # SUA: THEM MOI - noi dung canh bao gan nhat tu guiCanhBaoAnToan() ben firmware
    ALL_PINS = SENSOR_PINS + DEVICE_PINS + [ALARM_PIN]

    def __init__(self, client: BlynkClient, interval_sec=3, parent=None):
        super().__init__(parent)
        self.client = client
        self.interval_sec = interval_sec
        self._running = True

    def run(self):
        while self._running:
            raw = self.client.get_pins(self.ALL_PINS)
            # SUA: THEM MOI - hoi THAT xem ESP32 co dang online hay khong
            # (khac han viec doc pin, van "thanh cong" du thiet bi da
            # offline vi Blynk Cloud tra ve gia tri cache cu). Xem
            # is_device_online() de biet ly do can co hoi rieng nay.
            device_online = self.client.is_device_online()
            data = {
                "temp": raw.get("V0"),
                "humi": raw.get("V1"),
                "cam": raw.get("V2"),
                "water": raw.get("V3"),
                "mode": raw.get("V5"),
                "devices": {p: raw.get(p) for p in self.DEVICE_PINS},
                "alarm": raw.get(self.ALARM_PIN),
                "device_online": device_online,
            }
            self.data_updated.emit(data)
            for _ in range(self.interval_sec * 10):
                if not self._running:
                    break
                time.sleep(0.1)

    def stop(self):
        self._running = False
        self.wait(1500)