# -*- coding: utf-8 -*-
"""
scheduler.py — Dong bo lich hen gio + nguong moi truong xuong ESP32 (V16/V17)
===============================================================================
KIEN TRUC (Huong B): Python KHONG tu dem gio va tu ban lenh nua (cach cu
phu thuoc may tinh/app phai luon mo - da bo). Thay vao do:

  1. Python chi dong vai tro "nguoi soan lich": gom toan bo lich tu
     SettingTab, dong goi thanh 1 chuoi JSON, gui 1 LAN vao Vpin V16 moi
     khi nguoi dung them/sua/xoa xong (bam BACK).
  2. ESP32 (chip chinh) nhan JSON nay, luu vao NVS (giu duoc qua mat dien),
     va TU dung NTP de so gio, TU kich hoat - hoan toan doc lap voi may
     tinh co bat hay khong. Xem kiemTraLichHenGio() trong
     ChipChinh_ESP32S3.ino.

  Tuong tu, nguong moi truong (SettingTab -> ENV_ROWS) duoc gui vao V17.

CAP NHAT: SettingTab (qua ScheduleSection/LightScheduleSection) gio DA co
o chon "thu trong tuan" rieng cho tung dong lich - moi dong (row) tu
get_schedule() tra ve them field "thu" (list so 1..7, 1=Thu 2...7=Chu
nhat). build_schedule_json() ben duoi doc THANG tu do, KHONG con gan cung
ALL_WEEKDAYS nua. De tuong thich nguoc voi du lieu cu (file
schedule_config.json luu tu truoc khi co tinh nang nay, chua co key
"thu"), dung row.get("thu", ALL_WEEKDAYS) - mac dinh chay Hang ngay neu
thieu du lieu.

`next_upcoming()` chi la UOC TINH client-side de hien thi cho nguoi dung
xem truoc tren tab HOME - viec THUC THI THAT SU do chinh ESP32 tu lam
bang NTP, khong phu thuoc gi vao ham nay.
"""

import json
from PyQt5.QtCore import QObject, QTime, pyqtSignal

ALL_WEEKDAYS = [1, 2, 3, 4, 5, 6, 7]


class ScheduleSyncer(QObject):
    """Gom lich/nguong tu SettingTab, dong goi JSON, gui xuong ESP32 qua
    V16 (lich) / V17 (nguong moi truong). CHI gui khi co thay doi that su
    (nguoi dung bam BACK sau khi sua), KHONG tu chay dem gio nao ca."""

    sync_status = pyqtSignal(str)  # log de doc, co the noi vao 1 label/status bar

    def __init__(self, setting_tab, blynk_client, parent=None):
        super().__init__(parent)
        self.setting_tab = setting_tab
        self.blynk = blynk_client

    # ---------------------------------------------------------- V16
    def build_schedule_json(self):
        raw = self.setting_tab.get_all_schedules()
        items = []
        next_id = 1

        for row in raw.get("cho_an", []):
            items.append({
                "id": next_id, "loai": "cho_an",
                "gio": row["gio"], "phut": row["phut"],
                "thu": row.get("thu", ALL_WEEKDAYS), "gram": row["value"],
            })
            next_id += 1

        for row in raw.get("tam", []):
            items.append({
                "id": next_id, "loai": "tam",
                "gio": row["gio"], "phut": row["phut"],
                "thu": row.get("thu", ALL_WEEKDAYS), "duration": row["value"],
            })
            next_id += 1

        for row in raw.get("rua_chuong", []):
            items.append({
                "id": next_id, "loai": "rua_chuong",
                "gio": row["gio"], "phut": row["phut"],
                "thu": row.get("thu", ALL_WEEKDAYS), "duration": row["value"],
            })
            next_id += 1

        for row in raw.get("den", []):
            items.append({
                "id": next_id, "loai": "den",
                "gio_bat": row["gio_bat"], "phut_bat": row["phut_bat"],
                "gio_tat": row["gio_tat"], "phut_tat": row["phut_tat"],
                "thu": row.get("thu", ALL_WEEKDAYS),
            })
            next_id += 1

        return json.dumps(items, ensure_ascii=False)

    def push_schedule(self):
        """Goi khi nguoi dung bam BACK sau khi sua lich (SettingTab)."""
        payload = self.build_schedule_json()
        so_muc = payload.count('"id"')

        def on_done(ok):
            if ok:
                self.sync_status.emit(f"Da gui lich xuong ESP32 (V16), {so_muc} muc.")
            else:
                self.sync_status.emit("Loi: gui lich that bai, kiem tra ket noi mang/Blynk.")

        self.blynk.set_pin_async("V16", payload, callback=on_done)

    # ---------------------------------------------------------- V17
    def push_env(self):
        """Goi khi nguoi dung bam BACK sau khi sua nguong moi truong."""
        payload = json.dumps(self.setting_tab.get_env_values(), ensure_ascii=False)

        def on_done(ok):
            self.sync_status.emit("Da gui nguong moi truong xuong ESP32 (V17)." if ok
                                   else "Loi: gui nguong moi truong that bai.")

        self.blynk.set_pin_async("V17", payload, callback=on_done)

    # ---------------------------------------------------------- HOME
    def next_upcoming(self):
        """Tinh muc lich GAN NHAT sap toi (dua tren dong ho MAY TINH, chi
        mang tinh DU DOAN de hien thi cho nguoi dung xem truoc)."""
        now = QTime.currentTime()
        now_minutes = now.hour() * 60 + now.minute()

        candidates = []  # (phut_trong_ngay, nhan_hien_thi)
        raw = self.setting_tab.get_all_schedules()

        icon_map = {"cho_an": "Cho an", "tam": "Tam", "rua_chuong": "Rua chuong"}
        for loai, nhan in icon_map.items():
            for row in raw.get(loai, []):
                candidates.append((
                    row["gio"] * 60 + row["phut"],
                    f"{nhan} luc {row['gio']:02d}:{row['phut']:02d}"
                ))

        for row in raw.get("den", []):
            candidates.append((
                row["gio_bat"] * 60 + row["phut_bat"],
                f"Den BAT luc {row['gio_bat']:02d}:{row['phut_bat']:02d}"
            ))
            candidates.append((
                row["gio_tat"] * 60 + row["phut_tat"],
                f"Den TAT luc {row['gio_tat']:02d}:{row['phut_tat']:02d}"
            ))

        if not candidates:
            return "Chua co lich nao duoc cai dat"

        future_today = [c for c in candidates if c[0] > now_minutes]
        if future_today:
            return min(future_today, key=lambda c: c[0])[1]

        return min(candidates, key=lambda c: c[0])[1] + " (ngay mai)"
