from ultralytics import YOLO
import cv2
import torch
import time

# ==================== TỐI ƯU CUDA ====================
torch.backends.cudnn.benchmark = True

# ==================== CẤU HÌNH ====================
MODEL_PATH = "best11-150.pt"
STREAM_URL = "http://192.168.0.105"

CONFIDENCE = 0.5
IMGSZ = 640          # Nên để 640 vì model train ở 640

print("Loading YOLO model...")
model = YOLO(MODEL_PATH)
print("✓ Model loaded!")

# ==================== KẾT NỐI CAMERA ====================
def connect_camera():
    while True:
        print("Connecting to:", STREAM_URL)

        cap = cv2.VideoCapture(STREAM_URL, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if cap.isOpened():
            print("✓ Connected!")
            return cap

        print("Không kết nối được, thử lại sau 2 giây...")
        time.sleep(2)

cap = connect_camera()

frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

print("Resolution:", frame_width, "x", frame_height)

cv2.namedWindow("YOLO11 Detection", cv2.WINDOW_NORMAL)

frame_counter = 0
fps = 0
fps_timer = time.time()

while True:

    # Bỏ hết frame cũ trong buffer
    for _ in range(5):
        cap.grab()

    ret, frame = cap.retrieve()

    # mất kết nối
    if not ret:
        print("Mất kết nối, reconnect...")
        cap.release()
        cap = connect_camera()
        continue

    # ==================== YOLO ====================
    t0 = time.time()

    results = model.predict(
        source=frame,
        imgsz=IMGSZ,
        conf=CONFIDENCE,
        device=0,
        half=True,
        verbose=False
    )

    t1 = time.time()

    result = results[0]

    annotated = result.plot().copy()

    t2 = time.time()

    # ==================== FPS ====================
    frame_counter += 1

    if time.time() - fps_timer >= 1:
        fps = frame_counter / (time.time() - fps_timer)
        frame_counter = 0
        fps_timer = time.time()

    infer_ms = (t1 - t0) * 1000
    plot_ms = (t2 - t1) * 1000

    detections = len(result.boxes)

    cv2.putText(
        annotated,
        f"FPS: {fps:.1f}",
        (10,30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0,255,0),
        2
    )

    cv2.putText(
        annotated,
        f"Detections: {detections}",
        (10,70),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0,255,0),
        2
    )

    cv2.putText(
        annotated,
        f"Infer: {infer_ms:.1f} ms",
        (10,110),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255,255,0),
        2
    )

    cv2.putText(
        annotated,
        f"Plot: {plot_ms:.1f} ms",
        (10,145),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255,255,0),
        2
    )

    cv2.imshow("YOLO11 Detection", annotated)

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()