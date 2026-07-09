# Phần mềm HỆ THỐNG TRANG TRẠI THÔNG MINH (Python / PyQt5)

Phần mềm desktop mô phỏng lại giao diện màn hình HMI (WeinView) gốc, gồm 6 tab
điều hướng ở thanh dưới cùng: **HOME · SCREEN · MANUAL · SETTING · ALARM · CHART**.

## 1. Cài đặt

Yêu cầu Python 3.9+. Cài các thư viện cần thiết:

```bash
pip install -r requirements.txt
```

(hoặc cài lẻ: `pip install PyQt5 opencv-python numpy matplotlib`)

## 2. Chạy chương trình

```bash
python main.py
```

## 3. Cấu trúc thư mục

```
smart_farm_app/
├── main.py                # Điểm khởi chạy, header + thanh điều hướng dưới + stack các tab
├── requirements.txt
└── ui/
    ├── style.py            # Bảng màu / stylesheet chung (giao diện xanh dương - vàng nhạt)
    ├── home_tab.py          # Tab HOME: dashboard + camera giám sát máng ăn (MỚI)
    ├── camera_zone.py       # Widget camera: vẽ vùng (zone) + nhận diện ID lợn theo màu lưng
    ├── screen_tab.py        # Tab SCREEN: cảm biến / đèn báo / trạng thái thiết bị
    ├── manual_tab.py        # Tab MANUAL: lưới 3x3 nút bật/tắt thiết bị bằng tay
    ├── setting_tab.py       # Tab SETTING: môi trường / động cơ cho ăn / lịch hoạt động / chiếu sáng
    ├── alarm_tab.py         # Tab ALARM: bảng cảnh báo hiện tại + lịch sử lỗi
    └── chart_tab.py         # Tab CHART: biểu đồ nhiệt độ/độ ẩm + placeholder bản đồ nhiệt lợn
```

## 4. Chi tiết tab HOME (tab được nâng cấp thêm)

Giữ nguyên toàn bộ bố cục tổng quan gốc (nhiệt độ, độ ẩm, lịch trình tiếp theo,
thống kê hôm nay, trạng thái hệ thống, tổng quan vận hành), và bổ sung:

- **Camera giám sát máng ăn**: mặc định mở webcam số 0 (`cv2.VideoCapture(0)`).
  Nếu máy không có camera, phần mềm tự chuyển sang **chế độ giả lập (demo)**
  để vẫn xem được giao diện và test logic hoạt động.
- **Vẽ vùng (zone) máng ăn**: bấm nút "Bắt đầu vẽ vùng máng ăn", sau đó:
  - Click chuột **trái** trên khung hình để thêm từng điểm quanh khu vực máng ăn.
  - **Double-click** (hoặc click chuột phải) để đóng vùng thành đa giác kín.
  - Có thể bấm "Xóa vùng đã vẽ" để vẽ lại.
- **Nhận diện ID lợn theo màu vùng lưng**: phần mềm dùng phương pháp phát hiện
  màu (HSV color-blob detection) để giả lập việc mỗi con lợn được đánh dấu
  bằng 1 màu sơn/thẻ màu riêng ở lưng (đóng vai trò như "ID"). Khi tâm điểm
  của vùng màu đó nằm trong vùng máng ăn đã vẽ, ID lợn tương ứng sẽ hiện
  trong danh sách "đang ăn tại máng".
  - Bảng màu ID mặc định định nghĩa trong `ui/camera_zone.py`
    (biến `PIG_COLOR_IDS`) — có thể chỉnh sửa ngưỡng màu HSV cho khớp với
    màu sơn/thẻ đánh dấu thực tế của trại.
  - Đây là **bản nền tảng (baseline) đơn giản**, đủ để chạy demo và mở rộng.
    Khi cần độ chính xác cao hơn (nhiều lợn cùng màu, môi trường ánh sáng
    phức tạp...), nên nâng cấp lên mô hình AI thật (YOLOv8 + DeepSORT/ByteTrack
    để theo dõi ID xuyên suốt thời gian, không phụ thuộc màu sơn).

## 5. Tab CHART

Hiện có biểu đồ nhiệt độ/độ ẩm theo thời gian (dữ liệu demo, thay bằng dữ liệu
thật khi tích hợp cảm biến qua Serial/PLC/MQTT...).

Phần **"Bản đồ nhiệt & đường đi di chuyển của lợn"** hiện là khung placeholder —
theo đúng yêu cầu, sẽ nâng cấp sau khi hệ thống camera + tracking đã thu thập
đủ dữ liệu tọa độ di chuyển của từng ID lợn theo thời gian.

## 6. Kết nối với phần cứng thật (bước tiếp theo)

Các tab hiện tại đang dùng dữ liệu tĩnh/demo để đúng bố cục giao diện. Để kết
nối với hệ thống ESP32 + Blynk / PLC thật, gợi ý:

- Đọc dữ liệu cảm biến qua Serial (`pyserial`) hoặc MQTT rồi cập nhật vào
  `HomeTab._tick()` và `ScreenTab`.
- Gửi lệnh điều khiển thiết bị (tab MANUAL) qua Serial/MQTT trong hàm
  `DeviceToggle._toggle()`.
- Lưu/đọc cấu hình (tab SETTING) ra file JSON hoặc gửi xuống PLC khi bấm
  nút "SET...".
- Ghi log cảnh báo thật (tab ALARM) thay cho nút demo hiện tại.

Nếu cần, mình có thể viết thêm phần kết nối Serial/MQTT cụ thể cho phần cứng
bạn đang dùng.
