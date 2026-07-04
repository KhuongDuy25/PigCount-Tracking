import os
import time
from pathlib import Path

import cv2
import torch
from ultralytics import YOLO

# ==================== TỐI ƯU GPU ====================
torch.backends.cudnn.benchmark = True

# ==================== CẤU HÌNH ====================
MODEL_PATH = "bestV8-75.pt"
OUTPUT_DIR = "outputs"

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Loading YOLO model...")
model = YOLO(MODEL_PATH)
print("✓ Model loaded successfully!")

# ==================== CHỌN ẢNH ====================
image_path = input("\nNhập đường dẫn ảnh (Enter để dùng ảnh đầu tiên): ").strip()

if image_path == "":
    exts = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp")
    images = []

    for ext in exts:
        images.extend(Path(".").glob(ext))
        images.extend(Path(".").glob(ext.upper()))

    if len(images) == 0:
        print("Không tìm thấy ảnh!")
        exit()

    image_path = str(images[0])
    print(f"Dùng ảnh: {image_path}")

if not os.path.exists(image_path):
    print("Không tìm thấy ảnh!")
    exit()

# ==================== ĐỌC ẢNH ====================
image = cv2.imread(image_path)

if image is None:
    print("Không đọc được ảnh!")
    exit()

h, w = image.shape[:2]

print(f"\nẢnh: {w} x {h}")

# ==================== DETECT ====================
print("\nĐang detect...")

start = time.time()

results = model.predict(
    source=image,
    imgsz=640,
    conf=0.25,
    device=0,          # GTX1650
    verbose=False
)

infer_time = time.time() - start

result = results[0]

# tránh lỗi readonly
annotated = result.plot().copy()

# ==================== THÔNG TIN ====================
boxes = result.boxes
count = len(boxes)

print(f"\nPhát hiện {count} đối tượng")
print(f"Thời gian suy luận: {infer_time*1000:.1f} ms")
print(f"FPS tương đương: {1/infer_time:.2f}")

for i, box in enumerate(boxes):

    cls = int(box.cls[0])
    conf = float(box.conf[0])

    x1, y1, x2, y2 = map(int, box.xyxy[0])

    print(
        f"{i+1}. {result.names[cls]}"
        f" | {conf:.2%}"
        f" | ({x1},{y1}) ({x2},{y2})"
    )

# ==================== GHI THÔNG TIN LÊN ẢNH ====================
cv2.putText(
    annotated,
    f"Detections: {count}",
    (10, 35),
    cv2.FONT_HERSHEY_SIMPLEX,
    1,
    (0,255,0),
    2
)

cv2.putText(
    annotated,
    f"Inference: {infer_time*1000:.1f} ms",
    (10,70),
    cv2.FONT_HERSHEY_SIMPLEX,
    0.8,
    (0,255,0),
    2
)

# ==================== LƯU ====================
output_path = os.path.join(
    OUTPUT_DIR,
    f"detection_{Path(image_path).stem}.jpg"
)

cv2.imwrite(output_path, annotated)

print("\n====================================")
print(f"Model      : {MODEL_PATH}")
print(f"Ảnh gốc    : {image_path}")
print(f"Kết quả    : {output_path}")
print("====================================")