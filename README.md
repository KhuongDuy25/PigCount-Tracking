# Phần mềm HỆ THỐNG CHUỒNG TRẠI THÔNG MINH (Python / PyQt5)

Phần mềm desktop mô phỏng lại giao diện màn hình HMI (WeinView) gốc, gồm 6 tab
điều hướng ở thanh dưới cùng: **HOME · SCREEN · MANUAL · SETTING · ALARM · CHART**.

Kết nối trực tiếp với hệ thống chuồng trại chạy ESP32 + Blynk Cloud (2 chip:
chip chính ESP32-S3 lo WiFi/relay/cảm biến, chip phụ ESP32-32D lo động cơ
bước + loadcell, giao tiếp UART riêng — xem `ChipChinh_ESP32S3.ino` /
`ChipPhu_ESP32_32D.ino`).

## 1. Cài đặt

Yêu cầu Python 3.9+. Cài các thư viện cần thiết:

```bash
pip install -r requirements.txt
```

(hoặc cài lẻ: `pip install PyQt5 matplotlib requests`)

## 2. Cấu hình trước khi chạy

Mở `config.py`, điền đúng `BLYNK_AUTH_TOKEN` **giống hệt** với token trong
firmware ESP32 (`#define BLYNK_AUTH_TOKEN "..."`).

## 3. Chạy chương trình

```bash
python main.py
```

## 4. Cấu trúc thư mục

```
ChuongThongMinh2/
├── main.py                # Điểm khởi chạy, header + thanh điều hướng dưới + stack các tab
├── config.py               # Token Blynk + các chu kỳ polling/scheduler
├── blynk_client.py         # Gọi Blynk HTTP API (đọc/ghi Vpin) + BlynkPoller đọc định kỳ
├── feed_coordinator.py     # Khóa/xác nhận trước khi gửi lệnh cho ăn (V4 + V6), dùng chung
│                           # cho cả nút bấm tay (MANUAL) lẫn lịch tự động (scheduler)
├── scheduler.py            # Gom lịch hẹn từ SETTING, đóng gói JSON, gửi vào V16 (ESP32 tự
│                           # lưu NVS + tự chạy bằng NTP, không phụ thuộc app có mở hay không)
├── Yolos26-200.pt          # Model YOLO đã train riêng để phát hiện con vật (dùng cho camera)
├── zone_config.json         # Lưu vùng máng ăn đã vẽ trên camera (tồn tại qua các lần mở app)
├── requirements.txt
└── ui/
    ├── style.py            # Bảng màu / stylesheet chung
    ├── home_tab.py         # Tab HOME: dashboard tổng quan + camera giám sát máng ăn
    ├── camera_zone.py      # Widget camera: vẽ vùng, YOLO tracking (ByteTrack) + gán ID
    │                       # theo màu lưng, tự đối chiếu định kỳ để sửa ID bị lệch
    ├── screen_tab.py       # Tab SCREEN: cảm biến / đèn báo / trạng thái thiết bị
    ├── manual_tab.py       # Tab MANUAL: lưới nút bật/tắt 8 relay + nút cho ăn bằng tay
    ├── setting_tab.py      # Tab SETTING: ngưỡng môi trường (V17) / gram cho ăn / lịch hoạt động
    ├── schedule_section.py # Widget lịch hẹn giờ dùng chung cho cho ăn/tắm/rửa chuồng/đèn
    ├── alarm_tab.py        # Tab ALARM: bảng cảnh báo hiện tại + lịch sử lỗi
    └── chart_tab.py        # Tab CHART: biểu đồ nhiệt độ/độ ẩm
```

## 5. Trạng thái tích hợp Blynk hiện tại

| Tab | Đã nối Blynk thật? |
|---|---|
| MANUAL | Đã nối — bấm nút gọi thẳng `BlynkClient`, khóa relay đúng theo AUTO/MANUAL khớp firmware |
| SETTING | Cần xác nhận đã gửi đúng JSON vào V16/V17 (xem mục 6) |
| HOME / SCREEN / CHART | Còn dùng dữ liệu tĩnh/demo — cần nối `BlynkPoller` (đã có sẵn trong `blynk_client.py`, chỉ chưa khởi tạo trong `main.py`) |
| ALARM | Chỉ có nút demo giả lập, chưa đọc `Blynk.logEvent` thật từ firmware |

## 6. Kiến trúc lịch hẹn giờ

Lịch hẹn **không chạy đếm giờ trong Python** — vì như vậy sẽ phụ thuộc máy
tính/app phải luôn mở. Thay vào đó:

1. Người dùng thêm/sửa/xóa lịch trong tab SETTING
2. `scheduler.py` gom toàn bộ lịch hiện có, đóng gói thành 1 chuỗi JSON, gửi
   **1 lần** vào Vpin **V16**
3. ESP32 (chip chính) nhận, lưu vào bộ nhớ NVS (giữ được qua mất điện), và
   **tự dùng NTP để so giờ, tự kích hoạt** — hoàn toàn độc lập với máy tính

Tương tự, ngưỡng nhiệt độ/độ ẩm trong SETTING được gửi vào **V17**, ESP32 tự
áp dụng hysteresis độc lập cho từng thiết bị (quạt, sưởi, hút ẩm, phun sương).

## 7. Việc còn thiếu (gợi ý làm tiếp)

- Nối `BlynkPoller` vào `HomeTab`/`ScreenTab`/`ChartTab` để hiển thị số liệu thật
- Đọc `Blynk.logEvent` (Events API) để `AlarmTab` hiện cảnh báo thật từ firmware
- Thêm lưu file JSON cục bộ cho lịch hẹn/ngưỡng môi trường, để mở lại app không mất cấu hình đã nhập
