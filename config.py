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

# Chu kỳ scheduler kiểm tra lịch hẹn giờ (giây). 15s là đủ nhanh để không bỏ
# lỡ mốc phút nào, mà không gọi API quá dày.
SCHEDULER_CHECK_INTERVAL_SEC = 15
