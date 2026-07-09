# -*- coding: utf-8 -*-
"""
feed_coordinator.py — Xử lý AN TOÀN cho thao tác "Cho ăn" (V4 + V6)
=======================================================================
Vấn đề gốc (đúng như bạn/AI khác đã chỉ ra):
  - Ghi khối lượng (V4) rồi bấm xả (V6) là 2 request HTTP RIÊNG BIỆT gửi
    qua Blynk Cloud — không có gì đảm bảo chúng tới server đúng thứ tự.
  - Nếu người dùng bấm tay "Cho ăn ngay" đúng lúc scheduler cũng đang tự
    động kích hoạt 1 lần cho ăn theo lịch, 2 luồng có thể ghi đè V4 lẫn
    nhau, dẫn tới xả nhầm khối lượng của lần trước.

Cách xử lý ở đây (thay vì đoán thời gian bằng singleShot cố định):
  1. DÙNG 1 KHÓA (threading.Lock) DUY NHẤT cho toàn bộ thao tác cho ăn —
     dù là bấm tay hay do scheduler tự động, đều phải đi qua đúng 1 cổng
     này. Nếu đang có 1 lệnh cho ăn khác chạy dở, lệnh mới sẽ bị TỪ CHỐI
     ngay (không xếp hàng ngầm, không âm thầm ghi đè) và báo rõ lý do.
  2. SAU KHI GHI V4, ĐỌC LẠI (xác nhận thật) giá trị trên Blynk Cloud tối
     đa 3 lần (mỗi lần cách 300ms) để chắc chắn khối lượng ĐÃ THỰC SỰ tới
     server đúng như mong muốn, rồi MỚI bấm V6. Nếu sau 3 lần vẫn không
     khớp, HỦY lệnh cho ăn (an toàn hơn là xả nhầm khối lượng).

Cả `scheduler.py` (cho ăn theo lịch) và `manual_tab.py` (nút "CHO ĂN" bấm
tay) đều dùng chung 1 instance FeedCoordinator này để đảm bảo không bao
giờ có 2 luồng cho ăn chạy chồng lên nhau.
"""

import threading
import time


class FeedCoordinator:
    def __init__(self, blynk_client, confirm_retries=3, confirm_interval_sec=0.3):
        self.blynk = blynk_client
        self.confirm_retries = confirm_retries
        self.confirm_interval_sec = confirm_interval_sec
        self._lock = threading.Lock()

    def trigger_feed_async(self, gram, source_label="", on_status=None):
        """Gọi từ UI/scheduler - chạy toàn bộ ở thread nền, không làm treo Qt.
        on_status(ok: bool, message: str) sẽ được gọi khi có kết quả cuối cùng."""
        threading.Thread(
            target=self._trigger_feed, args=(gram, source_label, on_status), daemon=True
        ).start()

    def trigger_feed_now_async(self, source_label="", on_status=None):
        """Dùng cho nút 'CHO ĂN' bấm tay ở tab MANUAL — chỉ bấm V6 (dùng đúng
        khối lượng target_weight đang có sẵn trên ESP32, không ghi lại V4).
        Vẫn dùng CHUNG khóa với trigger_feed_async để không bao giờ bấm V6
        đè lên đúng lúc lịch tự động đang giữa chừng ghi V4 -> xác nhận."""
        threading.Thread(
            target=self._trigger_feed_now, args=(source_label, on_status), daemon=True
        ).start()

    def _trigger_feed_now(self, source_label, on_status):
        got_lock = self._lock.acquire(blocking=False)
        if not got_lock:
            msg = f"⛔ [{source_label}] Đang có 1 lệnh cho ăn khác (lịch tự động) chạy dở — bỏ qua để tránh chồng lệnh."
            if on_status:
                on_status(False, msg)
            return
        try:
            ok_v6 = self.blynk.set_pin("V6", 1)
            msg = (f"✅ [{source_label}] Đã bấm cho ăn (dùng khối lượng đang cấu hình sẵn trên ESP32)."
                   if ok_v6 else f"❌ [{source_label}] Gửi lệnh cho ăn thất bại.")
            if on_status:
                on_status(ok_v6, msg)
        finally:
            self._lock.release()

    def _trigger_feed(self, gram, source_label, on_status):
        # Chỉ 1 lệnh cho ăn được chạy tại 1 thời điểm - lệnh đến sau bị từ
        # chối thẳng thay vì âm thầm xếp hàng/ghi đè lên lệnh đang chạy.
        got_lock = self._lock.acquire(blocking=False)
        if not got_lock:
            msg = f"⛔ [{source_label}] Đang có 1 lệnh cho ăn khác chạy dở — bỏ qua để tránh chồng lệnh/xả nhầm khối lượng."
            if on_status:
                on_status(False, msg)
            return

        try:
            ok_v4 = self.blynk.set_pin("V4", gram)
            if not ok_v4:
                msg = f"❌ [{source_label}] Gửi khối lượng ({gram}g) thất bại — đã HỦY lệnh cho ăn."
                if on_status:
                    on_status(False, msg)
                return

            # Xác nhận THẬT: đọc lại V4 từ Blynk Cloud, không đoán thời gian.
            confirmed = False
            for _ in range(self.confirm_retries):
                time.sleep(self.confirm_interval_sec)
                val = self.blynk.get_pin("V4")
                try:
                    if val is not None and abs(float(val) - float(gram)) < 0.01:
                        confirmed = True
                        break
                except (TypeError, ValueError):
                    pass

            if not confirmed:
                msg = (f"❌ [{source_label}] Không xác nhận được khối lượng ({gram}g) đã ghi "
                       f"đúng trên Blynk Cloud sau {self.confirm_retries} lần thử — đã HỦY lệnh "
                       f"cho ăn để tránh xả nhầm khối lượng của lần trước.")
                if on_status:
                    on_status(False, msg)
                return

            ok_v6 = self.blynk.set_pin("V6", 1)
            if ok_v6:
                msg = f"✅ [{source_label}] Đã xác nhận {gram}g và bấm cho ăn thành công."
            else:
                msg = f"❌ [{source_label}] Đã ghi đúng {gram}g nhưng gửi lệnh xả (V6) thất bại."
            if on_status:
                on_status(ok_v6, msg)
        finally:
            self._lock.release()
