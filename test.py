from ultralytics import YOLO
import cv2
import time
import os
from datetime import datetime

# Load model
print("Loading YOLO model...")


## C:/Users/KhuongDuy/Downloads/ChuongThongMinh/Yolo11-Result/yolo11s.pt
#model = YOLO("C:/Users/KhuongDuy/Downloads/ChuongThongMinh/Yolo11-Result/yolo11s.pt")
model = YOLO("bestV8-75.pt")

print("Model loaded successfully!")

# Mở webcam laptop
cap = cv2.VideoCapture(0)

# Nếu có nhiều camera:
# cap = cv2.VideoCapture(1)

if not cap.isOpened():
    print("Không mở được webcam!")
    exit()

# FPS
frame_count = 0
start_time = time.time()
fps = 0

# Thư mục lưu video
output_dir = "outputs"
os.makedirs(output_dir, exist_ok=True)

output_path = os.path.join(
    output_dir,
    f"detection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avi"
)

fourcc = cv2.VideoWriter_fourcc(*'XVID')
out = None

print("Camera started...")

try:
    while True:
        success, frame = cap.read()

        if not success:
            print("Không đọc được frame từ webcam!")
            break

        # Khởi tạo video writer
        if out is None:
            h, w = frame.shape[:2]
            out = cv2.VideoWriter(
                output_path,
                fourcc,
                20.0,
                (w, h)
            )
            print(f"Saving video to: {output_path}")

        # YOLO Detection
        results = model(frame)

        # Vẽ box
        annotated_frame = results[0].plot().copy()

        # FPS
        frame_count += 1
        elapsed = time.time() - start_time

        if elapsed >= 1:
            fps = frame_count / elapsed
            frame_count = 0
            start_time = time.time()

        cv2.putText(
            annotated_frame,
            f"FPS: {fps:.2f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )

        # Đếm object
        detections = results[0]

        if detections.boxes is not None:
            count = len(detections.boxes)

            cv2.putText(
                annotated_frame,
                f"Detections: {count}",
                (10, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
            )

        # Ghi video
        out.write(annotated_frame)

        # Hiển thị
        cv2.imshow("YOLO Webcam Detection", annotated_frame)

        key = cv2.waitKey(1) & 0xFF

        # Q để thoát
        if key == ord('q'):
            break

except KeyboardInterrupt:
    print("Stopped by user")

finally:
    cap.release()

    if out is not None:
        out.release()

    cv2.destroyAllWindows()

    print(f"Video saved: {output_path}")