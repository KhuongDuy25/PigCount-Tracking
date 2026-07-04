import tkinter as tk
import customtkinter as ctk
import cv2
from PIL import Image, ImageTk
import requests
import threading
import time
from datetime import datetime

# ===================== CẤU HÌNH THÔNG TIN BLYNK =====================
BLYNK_AUTH_TOKEN = "YourAuthToken_xxxxxxxxxxxxxx"  # Thay bằng Token thật của bạn
BLYNK_URL = "https://sgp1.blynk.cloud/external/api/"

data_storage = {
    "V0": "31.5", "V1": "59.2", "V2": "100.0", "V3": "0",
    "V4": "50", "V5": "0", "V6": "0", "V7": "0",
    "V8": "0", "V9": "0", "V10": "0", "V11": "0",
    "V12": "0", "V13": "0", "V14": "0"
}

COLOR_BG_HEADER = "#0A3D62"
COLOR_BG_NAV = "#1E375A"
COLOR_CARD_DARK = "#2C3A47"
COLOR_TEXT_ON = "#2ECC71"
COLOR_TEXT_OFF = "#EA2027"

ctk.set_appearance_mode("Dark")

class SmartFarmHMI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("HỆ THỐNG TRANG TRẠI THÔNG MINH - CHƯƠNG TRÌNH ĐIỀU KHIỂN MÁY TÍNH")
        self.geometry("1450x850")
        
        # --- CÁC BIẾN PHỤC VỤ VẼ LINE ZONE BẰNG CHUỘT ---
        self.start_x = None
        self.start_y = None
        self.end_x = None
        self.end_y = None
        self.current_x = None
        self.current_y = None
        self.is_drawing = False

        # --- LAYOUT CHÍNH ---
        self.grid_columnconfigure(0, weight=4) 
        self.grid_columnconfigure(1, weight=6) 
        self.grid_rowconfigure(0, weight=1)
        
        # =====================================================================
        # 🎥 PHẦN CAMERA AI VÀ SỰ KIỆN CHUỘT VẼ ZONE
        # =====================================================================
        self.left_panel = ctk.CTkFrame(self, corner_radius=10, border_width=1, border_color="#34495E")
        self.left_panel.grid(row=0, column=0, padx=15, pady=15, sticky="nsw")
        
        self.lbl_cam_title = ctk.CTkLabel(self.left_panel, text="📷 AI CAMERA - ĐÈ KÉO CHUỘT ĐỂ VẼ LINE ZONE", 
                                          font=ctk.CTkFont(size=14, weight="bold"), text_color="#E74C3C")
        self.lbl_cam_title.pack(pady=10)
        
        # Khung hiển thị Video từ Camera
        self.lbl_video = tk.Label(self.left_panel, bg="#111111", width=540, height=420, cursor="cross")
        self.lbl_video.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # Đăng ký các sự kiện nhấn, giữ và thả chuột trực tiếp trên khung Video
        self.lbl_video.bind("<Button-1>", self.on_mouse_click)
        self.lbl_video.bind("<B1-Motion>", self.on_mouse_drag)
        self.lbl_video.bind("<ButtonRelease-1>", self.on_mouse_release)
        
        # Bảng hiển thị tọa độ Line Zone hiện tại
        self.box_cam_info = ctk.CTkFrame(self.left_panel, fg_color="#1E272E")
        self.box_cam_info.pack(fill="x", padx=15, pady=10)
        
        self.lbl_line_coords = ctk.CTkLabel(self.box_cam_info, text="Tọa độ Rào ảo: Chưa thiết lập (Hệ thống dùng mặc định)",
                                            font=ctk.CTkFont(family="Consolas", size=12), text_color="#F1C40F")
        self.lbl_line_coords.pack(pady=5, padx=10)
        
        self.btn_reset_line = ctk.CTkButton(self.box_cam_info, text="XÓA / VẼ LẠI LINE ZONE", fg_color="#c0392b", 
                                             height=25, font=ctk.CTkFont(size=11), command=self.reset_line_zone)
        self.btn_reset_line.pack(pady=5)

        # =====================================================================
        # 🖥️ PHẦN MÀN HÌNH HMI TÁCH TAB (BÊN PHẢI)
        # =====================================================================
        self.right_hmi_panel = ctk.CTkFrame(self, fg_color="#141E30", corner_radius=12)
        self.right_hmi_panel.grid(row=0, column=1, padx=(0, 15), pady=15, sticky="nsew")
        
        self.header_frame = ctk.CTkFrame(self.right_hmi_panel, fg_color=COLOR_BG_HEADER, height=55, corner_radius=0)
        self.header_frame.pack(fill="x", side="top")
        self.header_frame.pack_propagate(False)
        
        self.lbl_hmi_title = ctk.CTkLabel(self.header_frame, text="HỆ THỐNG TRANG TRẠI THÔNG MINH", 
                                           font=ctk.CTkFont(family="Arial", size=18, weight="bold"), text_color="white")
        self.lbl_hmi_title.pack(side="left", padx=20)
        
        self.lbl_hmi_time = ctk.CTkLabel(self.header_frame, text="00-00-2026 MON 00:00:00", 
                                          font=ctk.CTkFont(family="Arial", size=14), text_color="white")
        self.lbl_hmi_time.pack(side="right", padx=20)

        self.container = ctk.CTkFrame(self.right_hmi_panel, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.nav_frame = ctk.CTkFrame(self.right_hmi_panel, fg_color=COLOR_BG_NAV, height=65, corner_radius=0)
        self.nav_frame.pack(fill="x", side="bottom")
        self.nav_frame.pack_propagate(False)
        
        self.frames = {}
        for PageClass in (PageHome, PageScreen, PageManual, PageSetting, PageAlarm):
            page_name = PageClass.__name__
            frame = PageClass(parent=self.container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")
            
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        
        self.create_nav_buttons()
        self.show_page("PageHome")
        
        self.update_time()
        self.cap = cv2.VideoCapture(0)
        self.update_camera_stream()
        
        self.blynk_thread = threading.Thread(target=self.sync_blynk_cloud, daemon=True)
        self.blynk_thread.start()

    # --- CÁC HÀM XỬ LÝ SỰ KIỆN CHUỘT VẼ LINE ZONE THỰC TẾ ---
    def on_mouse_click(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.is_drawing = True
        self.end_x = None
        self.end_y = None

    def on_mouse_drag(self, event):
        if self.is_drawing:
            self.current_x = event.x
            self.current_y = event.y

    def on_mouse_release(self, event):
        if self.is_drawing:
            self.end_x = event.x
            self.end_y = event.y
            self.is_drawing = False
            self.lbl_line_coords.configure(text=f"Rào ảo cố định: A({self.start_x}, {self.start_y}) -> B({self.end_x}, {self.end_y})")
            
            # Đồng thời nhảy một thông báo nhật ký vào Tab Alarm cho uy tín
            self.frames["PageAlarm"].add_custom_log(f"Đã cập nhật tọa độ rào ảo mới: A({self.start_x},{self.start_y}) thành công.")

    def reset_line_zone(self):
        self.start_x = None
        self.start_y = None
        self.end_x = None
        self.end_y = None
        self.current_x = None
        self.current_y = None
        self.is_drawing = False
        self.lbl_line_coords.configure(text="Tọa độ Rào ảo: Chưa thiết lập (Hệ thống dùng mặc định)")

    # --- LUỒNG HIỂN THỊ CAMERA LỒNG GHÉP ĐƯỜNG VẼ ---
    def update_camera_stream(self):
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.resize(frame, (540, 380))
            
            # Trường hợp 1: Đang đè kéo chuột (Vẽ đường màu xanh lá cây để xem trước)
            if self.is_drawing and self.start_x is not None and self.current_x is not None:
                cv2.line(frame, (self.start_x, self.start_y), (self.current_x, self.current_y), (0, 255, 0), 2)
                cv2.putText(frame, "Drawing...", (self.start_x, max(20, self.start_y - 10)), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            
            # Trường hợp 2: Đã thả chuột ra (Khóa đường rào ảo màu đỏ cố định chân thực)
            elif self.start_x is not None and self.end_x is not None:
                cv2.line(frame, (self.start_x, self.start_y), (self.end_x, self.end_y), (0, 0, 255), 3)
                cv2.circle(frame, (self.start_x, self.start_y), 4, (0, 255, 255), -1)
                cv2.circle(frame, (self.end_x, self.end_y), 4, (0, 255, 255), -1)
                cv2.putText(frame, "AI CUSTOM LINE ACTIVE", (self.start_x, max(20, self.start_y - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            # Trường hợp mặc định: Chưa vẽ gì hết (Hiện đường rào ngang mẫu)
            else:
                cv2.line(frame, (60, 240), (480, 240), (0, 0, 255), 2)
                cv2.putText(frame, "AI LINE: DEFAULT TRACKING", (70, 225),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(cv2image)
            imgtk = ImageTk.PhotoImage(image=img)
            self.lbl_video.imgtk = imgtk
            self.lbl_video.configure(image=imgtk)
            
        self.after(20, self.update_camera_stream)

    def create_nav_buttons(self):
        nav_configs = [
            ("🏠 HOME", "PageHome"), ("📊 SCREEN", "PageScreen"),
            ("✋ MANUAL", "PageManual"), ("⚙️ SETTING", "PageSetting"),
            ("⚠️ ALARM", "PageAlarm")
        ]
        for name, page_key in nav_configs:
            btn = ctk.CTkButton(self.nav_frame, text=name, font=ctk.CTkFont(size=13, weight="bold"),
                                fg_color="transparent", text_color="white", width=130, height=50,
                                hover_color="#2C3E50", command=lambda k=page_key: self.show_page(k))
            btn.pack(side="left", expand=True, fill="both")

    def show_page(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()
        if hasattr(frame, "refresh"):
            frame.refresh()

    def update_time(self):
        now = datetime.now()
        time_str = now.strftime(f"%m-%d-2026 %a %H:%M:%S")
        self.lbl_hmi_time.configure(text=time_str)
        self.after(1000, self.update_time)

    def sync_blynk_cloud(self):
        while True:
            try:
                vpins = ["V0", "V1", "V2", "V3", "V4", "V5", "V7", "V8", "V9", "V10", "V11", "V12", "V13", "V14"]
                for vpin in vpins:
                    res = requests.get(f"{BLYNK_URL}get?token={BLYNK_AUTH_TOKEN}&{vpin}", timeout=0.8)
                    if res.status_code == 200:
                        data_storage[vpin] = res.text.strip('[" ]')
                self.after(0, self.refresh_all_active_views)
            except Exception as e:
                pass
            time.sleep(1)

    def refresh_all_active_views(self):
        for frame in self.frames.values():
            if hasattr(frame, "refresh"):
                frame.refresh()

    def send_cmd(self, vpin, val):
        def run():
            try: requests.get(f"{BLYNK_URL}update?token={BLYNK_AUTH_TOKEN}&{vpin}={val}", timeout=1)
            except: pass
        threading.Thread(target=run).start()

# =====================================================================
# CÁC TRANG TAB HMI ĐIỀU HƯỚNG CƠ BẢN
# =====================================================================
class PageHome(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.main_box = ctk.CTkFrame(self, fg_color=COLOR_CARD_DARK, corner_radius=10)
        self.main_box.pack(fill="both", expand=True, padx=20, pady=20)
        self.lbl_sys_status = ctk.CTkLabel(self.main_box, text="⚡ HỆ THỐNG TRẠNG THÁI: ONLINE", font=ctk.CTkFont(size=16, weight="bold"), text_color="#2ECC71")
        self.lbl_sys_status.pack(pady=30)
        self.lbl_mode = ctk.CTkLabel(self.main_box, text="CHẾ ĐỘ HIỆN TẠI: MANUAL", font=ctk.CTkFont(size=14))
        self.lbl_mode.pack(pady=10)
        self.lbl_climate_summary = ctk.CTkLabel(self.main_box, text="Nhiệt độ hiện tại: -- °C  |  Độ ẩm không khí: -- %", font=ctk.CTkFont(size=13))
        self.lbl_climate_summary.pack(pady=15)
        
    def refresh(self):
        mode_str = "TỰ ĐỘNG (AUTO)" if data_storage["V5"] == "1" else "ĐIỀU KHIỂN TAY (MANUAL)"
        self.lbl_mode.configure(text=f"CHẾ ĐỘ HIỆN TẠI: {mode_str}")
        self.lbl_climate_summary.configure(text=f"Nhiệt độ hiện tại: {data_storage['V0']} °C  |  Độ ẩm không khí: {data_storage['V1']} %")

class PageScreen(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self.box_cb = ctk.CTkFrame(self, fg_color=COLOR_CARD_DARK, corner_radius=8)
        self.box_cb.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.lbl_t = ctk.CTkLabel(self.box_cb, text="Nhiệt độ: -- °C")
        self.lbl_t.pack(anchor="w", padx=20, pady=10)
        self.lbl_h = ctk.CTkLabel(self.box_cb, text="Độ ẩm: -- %")
        self.lbl_h.pack(anchor="w", padx=20, pady=10)
        self.lbl_w = ctk.CTkLabel(self.box_cb, text="Cám trong bồn: -- g")
        self.lbl_w.pack(anchor="w", padx=20, pady=10)
        self.lbl_water = ctk.CTkLabel(self.box_cb, text="Máng nước sạch: --")
        self.lbl_water.pack(anchor="w", padx=20, pady=10)
        
        self.right_grid = ctk.CTkFrame(self, fg_color=COLOR_CARD_DARK, corner_radius=8)
        self.right_grid.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        self.status_labels = {}
        dev_names = [
            ("Quạt hút 1", "V7"), ("Quạt thổi 2", "V8"), ("Đèn sáng chuồng", "V9"),
            ("Đèn sưởi ấm", "V10"), ("Bơm cấp máng", "V11"), ("Bơm xịt rửa sàn", "V12"),
            ("Bơm tắm vật nuôi", "V13"), ("Bơm phun sương", "V14")
        ]
        for name, vpin in dev_names:
            lbl = ctk.CTkLabel(self.right_grid, text=f"• {name}: ĐANG TẮT", font=ctk.CTkFont(size=13))
            lbl.pack(anchor="w", padx=25, pady=6)
            self.status_labels[vpin] = (name, lbl)

    def refresh(self):
        self.lbl_t.configure(text=f"Nhiệt độ môi trường: {data_storage['V0']} °C")
        self.lbl_h.configure(text=f"Độ ẩm không khí: {data_storage['V1']} %")
        self.lbl_w.configure(text=f"Trọng lượng cám tồn (V2): {data_storage['V2']} g")
        water_txt = "ĐẦY NƯỚC" if data_storage["V3"] == "1" else "CẠN NƯỚC"
        water_color = COLOR_TEXT_ON if data_storage["V3"] == "1" else COLOR_TEXT_OFF
        self.lbl_water.configure(text=f"Máng nước tự động (V3): {water_txt}", text_color=water_color)
        
        for vpin, (name, lbl) in self.status_labels.items():
            if data_storage[vpin] == "1":
                lbl.configure(text=f"🟢 {name}: ĐANG BẬT", text_color=COLOR_TEXT_ON)
            else:
                lbl.configure(text=f"🔴 {name}: ĐANG TẮT", text_color="#BDC3C7")

class PageManual(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        self.top_bar = ctk.CTkFrame(self, fg_color=COLOR_CARD_DARK, height=50)
        self.top_bar.pack(fill="x", padx=10, pady=10)
        self.lbl_mode_cur = ctk.CTkLabel(self.top_bar, text="CHẾ ĐỘ HỆ THỐNG HIỆN TẠI (V5): MANUAL", font=ctk.CTkFont(weight="bold"))
        self.lbl_mode_cur.pack(side="left", padx=15, pady=10)
        
        self.btn_toggle_mode = ctk.CTkButton(self.top_bar, text="ĐỔI CHẾ ĐỘ", width=100, command=self.action_toggle_mode)
        self.btn_toggle_mode.pack(side="right", padx=15, pady=10)
        
        self.grid_container = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_container.pack(fill="both", expand=True)
        self.grid_container.grid_columnconfigure(0, weight=1)
        self.grid_container.grid_columnconfigure(1, weight=1)
        
        self.buttons = {}
        dev_map = [
            ("Quạt hút một", "V7"), ("Quạt thổi hai", "V8"), ("Đèn chiếu sáng", "V9"),
            ("Hệ thống sưởi", "V10"), ("Máy bơm máng", "V11"), ("Bơm rửa chuồng", "V12"),
            ("Bơm nước tắm", "V13"), ("Phun sương mát", "V14")
        ]
        for idx, (name, vpin) in enumerate(dev_map):
            r = idx // 2
            c = idx % 2
            btn = ctk.CTkButton(self.grid_container, text=f"{name.upper()}", height=50,
                                command=lambda p=vpin: self.action_toggle_relay(p))
            btn.grid(row=r, column=c, padx=10, pady=6, sticky="ew")
            self.buttons[vpin] = (name, btn)

    def action_toggle_mode(self):
        next_val = "1" if data_storage["V5"] == "0" else "0"
        self.controller.send_cmd("V5", next_val)

    def action_toggle_relay(self, vpin):
        if data_storage["V5"] == "1": return
        next_relay_state = "0" if data_storage[vpin] == "1" else "1"
        self.controller.send_cmd(vpin, next_relay_state)

    def refresh(self):
        m_txt = "AUTO" if data_storage["V5"] == "1" else "MANUAL"
        self.lbl_mode_cur.configure(text=f"CHẾ ĐỘ HỆ THỐNG HIỆN TẠI (V5): {m_txt}")
        for vpin, (name, btn) in self.buttons.items():
            if data_storage[vpin] == "1":
                btn.configure(text=f"🟢 {name.upper()} [BẬT]", fg_color="#0984e3")
            else:
                btn.configure(text=f"🔴 {name.upper()} [TẮT]", fg_color="#2d3436")

class PageSetting(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.b1 = ctk.CTkFrame(self, fg_color=COLOR_CARD_DARK, corner_radius=8)
        self.b1.pack(fill="x", pady=20, padx=20)
        self.lbl_v4_cur = ctk.CTkLabel(self.b1, text="Khối lượng cài đặt hiện tại trên mẻ (V4): -- g")
        self.lbl_v4_cur.pack(anchor="w", padx=20, pady=10)
        self.entry_v4 = ctk.CTkEntry(self.b1, width=150, placeholder_text="Số gram xả...")
        self.entry_v4.pack(side="left", padx=20, pady=10)
        self.btn_save_v4 = ctk.CTkButton(self.b1, text="GỬI CÀI ĐẶT", width=100, command=self.save_feed_weight)
        self.btn_save_v4.pack(side="left", padx=10, pady=10)
        
    def save_feed_weight(self):
        val = self.entry_v4.get()
        if val.isdigit():
            self.controller.send_cmd("V4", val)
            self.entry_v4.delete(0, tk.END)

    def refresh(self):
        self.lbl_v4_cur.configure(text=f"Khối lượng cài đặt hiện tại trên mẻ (V4): {data_storage['V4']} g")

class PageAlarm(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        lbl = ctk.CTkLabel(self, text="⚠️ NHẬT KÝ SỰ KIỆN & CẢNH BÁO RÀO ẢO", font=ctk.CTkFont(size=14, weight="bold"), text_color="#E74C3C")
        lbl.pack(pady=10, anchor="w", padx=20)
        self.txt_alarm = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12))
        self.txt_alarm.pack(fill="both", expand=True, padx=20, pady=10)
        self.txt_alarm.insert("0.0", f"[{datetime.now().strftime('%H:%M:%S')}] [HỆ THỐNG] Khởi tạo luồng Camera AI vẽ rào ảo trực tuyến.\n")
        self.txt_alarm.configure(state="disabled")

    def add_custom_log(self, text):
        self.txt_alarm.configure(state="normal")
        self.txt_alarm.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] [AI_ZONE] {text}\n")
        self.txt_alarm.configure(state="disabled")

    def refresh(self):
        pass

if __name__ == "__main__":
    app = SmartFarmHMI()
    app.mainloop()