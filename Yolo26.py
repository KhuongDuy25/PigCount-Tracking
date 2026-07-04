"""
Chạy YOLO26 với Webcam
======================
Yêu cầu: pip install ultralytics opencv-python
"""

import cv2
from ultralytics import YOLO

# ── CẤU HÌNH ──────────────────────────────────────────

#yolo26s.pt
#best11-150.pt
MODEL_PATH  = "yolo26s.pt"   # tự động tải về lần đầu
CAM_INDEX   = 0          # 0 = webcam mặc định, đổi sang 1,2... nếu có nhiều cam
CONF_THRESH = 0.5            # ngưỡng confidence (0.0 - 1.0)
USE_GPU     = True           # True = dùng GTX 1650, False = CPU
SHOW_FPS    = True           # hiển thị FPS lên màn hình
# ──────────────────────────────────────────────────────

def main():
    # Load model
    print(f"[INFO] Đang tải model {MODEL_PATH} ...")
    model = YOLO(MODEL_PATH)
    device = 0 if USE_GPU else "cpu"
    print(f"[INFO] Dùng thiết bị: {'GPU (GTX 1650)' if USE_GPU else 'CPU'}")

    # Mở webcam
    cap = cv2.VideoCapture(CAM_INDEX)
    if not cap.isOpened():
        print(f"[LỖI] Không mở được webcam index={CAM_INDEX}")
        return

    # Lấy thông tin webcam
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[INFO] Webcam: {w}x{h}")
    print("[INFO] Nhấn 'Q' để thoát | 'S' để chụp màn hình")

    fps_display = 0.0
    import time
    prev_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[LỖI] Không đọc được frame từ webcam")
            break

        # Chạy YOLO26 detection
        results = model(
            frame,
            conf=CONF_THRESH,
            device=device,
            verbose=False
        )

        # Vẽ kết quả lên frame
        annotated = results[0].plot()

        # Tính và hiển thị FPS
        if SHOW_FPS:
            cur_time = time.time()
            fps_display = 1.0 / (cur_time - prev_time + 1e-9)
            prev_time = cur_time
            cv2.putText(
                annotated,
                f"FPS: {fps_display:.1f}",
                (10, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0, (0, 255, 0), 2
            )

        # Hiển thị model đang dùng
        cv2.putText(
            annotated,
            f"YOLO26s | conf={CONF_THRESH}",
            (10, h - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6, (200, 200, 200), 1
        )

        cv2.imshow("YOLO26 - Webcam (Q de thoat)", annotated)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == ord('Q'):
            print("[INFO] Thoát.")
            break
        elif key == ord('s') or key == ord('S'):
            fname = f"screenshot_{int(time.time())}.jpg"
            cv2.imwrite(fname, annotated)
            print(f"[INFO] Đã lưu: {fname}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()