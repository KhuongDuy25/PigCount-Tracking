# -*- coding: utf-8 -*-
"""
config.py — Cấu hình kết nối Blynk Cloud

QUAN TRỌNG: Điền đúng giá trị BLYNK_AUTH_TOKEN giống HỆT với
BLYNK_AUTH_TOKEN trong code ESP32 (KHÔNG cần sửa gì thêm ở firmware).
"""

# Lấy trong code ESP32: #define BLYNK_AUTH_TOKEN "YourAuthToken_xxxxxxxxxxxxxx"
BLYNK_AUTH_TOKEN = "QMrwb-rZl7D-H5CLg1nMmrGk7mU1MznC"

# Chu kỳ polling đọc cảm biến (giây). ESP32 gửi dữ liệu lên Blynk mỗi 2s
# (timer.setInterval(2000L, ...) trong firmware), nên để 3s là hợp lý.
BLYNK_POLL_INTERVAL_SEC = 3

# Thời gian chờ tối đa (giây) cho mỗi request HTTP tới Blynk Cloud
BLYNK_HTTP_TIMEOUT = 4

# KHONG CON DUNG: truoc day dung cho AutoScheduler tu dem gio o Python (Huong
# A, da bo). Gio lich chay hoan toan tren ESP32 (qua V16 + NTP), giu lai
# hang so nay chi de tranh loi import neu code cu con tham chieu dau do.
SCHEDULER_CHECK_INTERVAL_SEC = 15

# ---------------- WEB SERVER LOCAL (LAN, du phong khi mat Internet) ----------------
# Dia chi mDNS ESP32 tu quang ba (xem MDNS.begin("chuongtrai") trong
# firmware) - KHONG can biet truoc IP, he dieu hanh (Windows/macOS/Linux
# co dich vu mDNS) tu resolve duoc thanh IP that trong LAN.
LOCAL_SERVER_HOST = "chuongtrai.local"

# Timeout rieng cho request toi LAN (thuong nhanh hon Cloud nhieu vi khong
# di qua Internet, nhung van can 1 nguong de khong treo giao dien qua lau
# neu ESP32 bi tat/roi mang).
LOCAL_HTTP_TIMEOUT = 8