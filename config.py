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

# SUA: THEM MOI - dia chi Web Server LOCAL chay tren ESP32 chinh, dung lam
# duong DU PHONG khi co WiFi/LAN nhung MAT INTERNET (khong toi duoc Blynk
# Cloud). Mac dinh dung ten mDNS "chuongtrai.local" (ESP32 tu dang ky qua
# thu vien ESPmDNS trong firmware). Neu mang cua ban KHONG ho tro mDNS
# (mot so router/Windows can cai them Bonjour), doi sang IP LAN that cua
# ESP32 (vd "192.168.1.50"), xem trong Serial Monitor dong "[WEB LOCAL] San
# sang tai ...". De trong ("") de TAT han co che du phong nay.
LOCAL_ESP32_HOST = "chuongtrai.local"

# Thoi gian cho toi da (giay) cho MOI request goi sang Web Server local.
# De NGAN vi day la mang LAN noi bo, phan hoi phai rat nhanh (thuong <100ms)
# - neu cham hon nghia la ESP32 that su khong con tren mang, khong nen cho
# lau lam nguoi dung cam thay ung dung bi "dong hinh".
LOCAL_HTTP_TIMEOUT = 1.5

# KHONG CON DUNG: truoc day dung cho AutoScheduler tu dem gio o Python (Huong
# A, da bo). Gio lich chay hoan toan tren ESP32 (qua V16 + NTP), giu lai
# hang so nay chi de tranh loi import neu code cu con tham chieu dau do.
SCHEDULER_CHECK_INTERVAL_SEC = 15
