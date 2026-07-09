# -*- coding: utf-8 -*-
"""
scheduler.py — Bộ lịch hẹn giờ chạy nền (AutoScheduler)
===========================================================
Đây là phần trả lời trực tiếp câu hỏi: "đang AUTO, bấm tay đèn lúc 16:59,
đến 19h (giờ đã hẹn) thì sẽ ra sao?"

QUY TẮC ÁP DỤNG (giống 1 CHIẾC ĐỒNG HỒ BÁO THỨC, không phải 1 LUẬT LIÊN TỤC):
  Mỗi dòng lịch là 1 THỜI ĐIỂM KÍCH HOẠT CỐ ĐỊNH. Đến đúng giờ:phút đã cài,
  scheduler gửi lệnh xuống ESP32 y hệt như vừa có người bấm nút — BẤT KỂ
  trước đó thiết bị đang ở trạng thái nào (do tay bấm hay do gì khác).

  => Ví dụ cụ thể của bạn: đèn hẹn BẬT lúc 19:00, bạn bấm tay BẬT đèn lúc
     16:59. Đến đúng 19:00, scheduler vẫn gửi lệnh BẬT xuống — vì đèn đã
     bật sẵn nên không có gì thay đổi (lệnh trùng trạng thái, vô hại).
     Nhưng nếu giữa 16:59 và 19:00 bạn lỡ tắt đèn đi, thì đúng 19:00 lịch
     vẫn sẽ BẬT LẠI như đã hẹn — lịch luôn "thắng" tại đúng thời điểm của nó,
     không quan tâm tay đã làm gì trước đó. Tương tự cho "giờ tắt" của đèn.

  => Với Bơm tắm / Bơm rửa sàn (bật rồi tự tắt sau X giây): đến giờ hẹn,
     scheduler BẬT bơm rồi tự đếm đúng X giây cấu hình rồi TẮT — không quan
     tâm bạn đã bấm tay bật/tắt gì trước đó trong khoảng thời gian đó.

  => Với Cho ăn (nút xung V6): đến giờ hẹn, scheduler KHÔNG tự ghi V4 rồi
     đoán thời gian bấm V6 nữa — mà gọi qua `FeedCoordinator` dùng chung
     với nút "CHO ĂN" tay ở tab MANUAL. FeedCoordinator dùng 1 khóa duy
     nhất (chỉ 1 lệnh cho ăn chạy tại 1 thời điểm, dù là tay hay tự động)
     và XÁC NHẬN THẬT giá trị V4 đã tới Blynk Cloud trước khi bấm V6 —
     xem chi tiết trong feed_coordinator.py.

CHỐNG BẮN TRÙNG LỊCH NHIỀU LẦN TRONG CÙNG 1 PHÚT:
  Scheduler kiểm tra mỗi 15 giây (nhanh hơn 1 phút), nên mỗi mốc giờ:phút có
  thể bị quét trúng 3-4 lần liên tiếp trong đúng phút đó. Để tránh gửi lệnh
  lặp lại, mỗi lần kích hoạt được đánh dấu bằng 1 "khóa" duy nhất theo
  (loại lịch, số thứ tự dòng, ngày giờ phút) — chỉ bắn đúng 1 lần cho mỗi
  khóa, dù có quét trúng bao nhiêu lần trong phút đó.
"""

from PyQt5.QtCore import QObject, QTimer, QDateTime, pyqtSignal


class AutoScheduler(QObject):
    """Bộ đếm giờ chạy nền, đối chiếu đồng hồ hệ thống với lịch đã cài trong
    SettingTab, tự động gửi lệnh xuống ESP32 qua BlynkClient khi tới giờ."""

    schedule_fired = pyqtSignal(str)  # phát ra log dễ đọc mỗi khi có 1 lịch kích hoạt

    def __init__(self, setting_tab, blynk_client, feed_coordinator, check_interval_sec=15, parent=None):
        super().__init__(parent)
        self.setting_tab = setting_tab
        self.blynk = blynk_client
        self.feed_coordinator = feed_coordinator

        self._fired_keys = set()  # chống bắn trùng trong cùng 1 phút (xem ghi chú ở đầu file)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_all)
        self.timer.start(check_interval_sec * 1000)

    # ------------------------------------------------------------------
    def _check_all(self):
        now = QDateTime.currentDateTime()
        hh, mm = now.time().hour(), now.time().minute()
        minute_key = now.toString("yyyy-MM-dd HH:mm")

        schedules = self.setting_tab.get_all_schedules()

        for i, row in enumerate(schedules.get("cho_an", [])):
            if row["gio"] == hh and row["phut"] == mm:
                self._fire_once(f"cho_an_{i}_{minute_key}", self._fire_feed, row["value"])

        for i, row in enumerate(schedules.get("tam", [])):
            if row["gio"] == hh and row["phut"] == mm:
                self._fire_once(f"tam_{i}_{minute_key}", self._fire_pump, "V13", "Tắm", row["value"])

        for i, row in enumerate(schedules.get("rua_chuong", [])):
            if row["gio"] == hh and row["phut"] == mm:
                self._fire_once(f"rua_{i}_{minute_key}", self._fire_pump, "V12", "Rửa chuồng", row["value"])

        for i, row in enumerate(schedules.get("den", [])):
            if row["gio_bat"] == hh and row["phut_bat"] == mm:
                self._fire_once(f"den_on_{i}_{minute_key}", self._fire_light, True)
            if row["gio_tat"] == hh and row["phut_tat"] == mm:
                self._fire_once(f"den_off_{i}_{minute_key}", self._fire_light, False)

        # dọn bớt để tránh set phình to vô hạn sau nhiều ngày chạy liên tục
        if len(self._fired_keys) > 3000:
            self._fired_keys.clear()

    def _fire_once(self, key, func, *args):
        if key in self._fired_keys:
            return  # đã bắn lịch này trong đúng phút này rồi, không bắn lại
        self._fired_keys.add(key)
        func(*args)

    # ---------------------------------------------------------- cho ăn
    def _fire_feed(self, gram):
        self.schedule_fired.emit(f"⏰ Lịch CHO ĂN kích hoạt: {gram} gram (đang xác nhận qua FeedCoordinator...)")

        def on_status(ok, message):
            self.schedule_fired.emit(message)

        self.feed_coordinator.trigger_feed_async(gram, source_label="Lịch tự động", on_status=on_status)

    # ------------------------------------------------------ bơm (tắm/rửa)
    def _fire_pump(self, pin, ten_thiet_bi, duration_sec):
        self.schedule_fired.emit(f"⏰ Lịch {ten_thiet_bi.upper()} kích hoạt: BẬT trong {duration_sec}s")
        self.blynk.set_pin_async(pin, 1)
        QTimer.singleShot(int(duration_sec * 1000), lambda: self._turn_off_pump(pin, ten_thiet_bi))

    def _turn_off_pump(self, pin, ten_thiet_bi):
        self.schedule_fired.emit(f"⏰ Lịch {ten_thiet_bi.upper()}: đã hết {ten_thiet_bi.lower()} theo giờ, TẮT")
        self.blynk.set_pin_async(pin, 0)

    # --------------------------------------------------------------- đèn
    def _fire_light(self, turn_on):
        trang_thai = "BẬT" if turn_on else "TẮT"
        self.schedule_fired.emit(f"⏰ Lịch ĐÈN kích hoạt: {trang_thai}")
        self.blynk.set_pin_async("V9", 1 if turn_on else 0)

    # ------------------------------------------------------------------
    def stop(self):
        self.timer.stop()
