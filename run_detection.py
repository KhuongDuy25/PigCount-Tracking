# Wrapper script - PHẢI patch cv2 TRƯỚC khi import ultralytics
import sys
import os

# Set environment để skip GUI
os.environ['OPENCV_VIDEOIO_DEBUG'] = '0'

# Import cv2 headless
import cv2

# Patch toàn bộ constants và functions
cv2.IMREAD_COLOR = 1
cv2.IMREAD_GRAYSCALE = 0
cv2.IMREAD_UNCHANGED = -1
cv2.imshow = lambda *args, **kwargs: None
cv2.waitKey = lambda x=0: -1
cv2.destroyAllWindows = lambda: None
cv2.namedWindow = lambda *args, **kwargs: None
cv2.imread = lambda path, flags=1: None
cv2.imwrite = lambda *args, **kwargs: False

# BÂY GIỜ mới import ultralytics
from ultralytics import YOLO
import time
import threading
import os
from datetime import datetime

# ==================== CẤU HÌNH ====================
print("Loading YOLO model...")
model = YOLO("best11-150.pt")
print("Model loaded successfully!")

# IP của ESP32-CAM (PHẢI CÓ /stream endpoint)
stream_url = "http://192.168.0.113:81/stream"

# Biến để theo dõi FPS
frame_count = 0
start_time = time.time()
fps = 0

# Setup video writer để lưu output
output_dir = "outputs"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

output_path = os.path.join(output_dir, f"detection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avi")
fourcc = cv2.VideoWriter_fourcc(*'XVID')
out = None
frame_width = None
frame_height = None

def connect_stream():
    """Kết nối đến stream ESP32"""
    print(f"Connecting to {stream_url}...")
    while True:
        try:
            cap = cv2.VideoCapture(stream_url)
            if cap.isOpened():
                print("Connected to ESP32-CAM successfully!")
                return cap
            else:
                print("Failed to connect. Retrying in 3 seconds...")
                time.sleep(3)
        except Exception as e:
            print(f"Error: {e}. Retrying in 3 seconds...")
            time.sleep(3)

# Kết nối đến stream
cap = connect_stream()

try:
    frame_num = 0
    while True:
        success, frame = cap.read()

        if not success:
            print("Mất kết nối hoặc không nhận được frame. Cố gắng kết nối lại...")
            cap.release()
            cap = connect_stream()
            continue

        # Lấy kích thước frame lần đầu tiên
        if frame_width is None:
            frame_height, frame_width = frame.shape[:2]
            out = cv2.VideoWriter(output_path, fourcc, 30.0, (frame_width, frame_height))
            print(f"Saving video to: {output_path}")

        # Chạy nhận diện
        results = model(frame)

        # Vẽ bounding box
        annotated_frame = results[0].plot()

        # Tính FPS
        frame_count += 1
        elapsed_time = time.time() - start_time
        if elapsed_time > 1:
            fps = frame_count / elapsed_time
            frame_count = 0
            start_time = time.time()

        # Hiển thị FPS
        cv2.putText(annotated_frame, f"FPS: {fps:.2f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # Lấy thông tin nhận diện
        detections = results[0]
        if detections.boxes:
            count = len(detections.boxes)
            cv2.putText(annotated_frame, f"Detections: {count}", (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            print(f"Frame {frame_num}: FPS: {fps:.2f} | Detections: {count}")

        # Ghi video
        if out:
            out.write(annotated_frame)

        frame_num += 1

except KeyboardInterrupt:
    print("\nInterrupted by user")
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
finally:
    cap.release()
    if out:
        out.release()
    print(f"Stream closed. Video saved to: {output_path}")
