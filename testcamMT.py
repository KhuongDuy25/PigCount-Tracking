from ultralytics import YOLO
import cv2
import torch
import time

torch.backends.cudnn.benchmark = True

MODEL_PATH = "yolo26s.pt"
CONFIDENCE = 0.5
IMGSZ = 640  # ← fix 2: dùng 640

print("Loading YOLO model...")
model = YOLO(MODEL_PATH)
print("✓ Model loaded!")

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)

cv2.namedWindow("YOLO26 Detection", cv2.WINDOW_NORMAL)

prev_time = time.time()

while True:
    ret, frame = cap.read()
    if not ret:
        break

    t0 = time.time()

    # ← fix 1: bỏ stream=True, lấy [0] trực tiếp
    result = model.predict(
        source=frame,
        imgsz=IMGSZ,
        conf=CONFIDENCE,
        device=0,
        half=True,
        verbose=False
    )[0]

    t1 = time.time()
    annotated = result.plot()
    t2 = time.time()

    # ← fix 3: tính FPS đúng
    cur_time = time.time()
    fps = 1.0 / (cur_time - prev_time + 1e-9)
    prev_time = cur_time

    inference_ms = (t1 - t0) * 1000
    plot_ms = (t2 - t1) * 1000

    cv2.putText(annotated, f"FPS: {fps:.1f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(annotated, f"Detections: {len(result.boxes)}", (10, 70),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(annotated, f"Infer: {inference_ms:.1f} ms", (10, 110),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
    cv2.putText(annotated, f"Plot: {plot_ms:.1f} ms", (10, 145),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

    cv2.imshow("YOLO26 Detection", annotated)
    if cv2.waitKey(1) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()