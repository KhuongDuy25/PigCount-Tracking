#define BLYNK_TEMPLATE_ID   "TMPL6xxxxxx" // Thay bang ID cua ban
#define BLYNK_TEMPLATE_NAME "Chuong Trai Thong Minh"
#define BLYNK_AUTH_TOKEN    "YourAuthToken_xxxxxxxxxxxxxx" // Thay bang Token cua ban

#include <WiFi.h>
#include <WiFiClient.h>
#include <BlynkSimpleEsp32.h>
#include <DHT.h>
#include "HX711.h"
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Preferences.h>

// ===================== DINH NGHIA CHAN PHAN CUNG (GPIO) =====================
#define DHTPIN 4
#define DHTTYPE DHT11
const int HX711_DT_PIN  = 21;
const int HX711_SCK_PIN = 47;
const int WATER_SENSOR_PIN = 10;

const int IN1 = 11;
const int IN2 = 12;
const int IN3 = 13;
const int IN4 = 14;

// RELAY LA ACTIVE HIGH: HIGH = BAT, LOW = TAT (da xac nhan thuc te)
const int PIN_QUAT1       = 5;
const int PIN_QUAT2       = 6;
const int PIN_DEN_SANG    = 7;
const int PIN_DEN_SUOI    = 15;
const int PIN_BOM_MANG    = 16;
const int PIN_BOM_SAN     = 17;
const int PIN_BOM_TAM     = 8;
const int PIN_PHUN_SUONG  = 18;

// ===================== KHOI TAO DOI TUONG =====================
DHT dht(DHTPIN, DHTTYPE);
HX711 scale;
LiquidCrystal_I2C lcd(0x27, 20, 4);
Preferences prefs;
BlynkTimer timer;

// ===================== THONG SO CAU HINH HE THONG =====================
char auth[] = BLYNK_AUTH_TOKEN;
char ssid[] = "Ten_WiFi_Nha_Ban";
char pass[] = "Mat_Khau_WiFi";

float calibration_factor = -958.0;
float target_weight = 50.0;

// SUA: FEED_STEP_INTERVAL_MS thay cho step_delay (khong con dung kieu delayMicroseconds nua)
// Ban da xac nhan 1000us/buoc (~1ms/buoc) la toc do muot nhat -> dat lai dung 1ms
const unsigned long FEED_STEP_INTERVAL_MS = 1;   // 1 buoc / 1ms = 1000 buoc/giay, khop dung ban da test muot

const bool ccw_steps[8][4] = {
  {true, false, false, true}, {false, false, false, true}, {false, false, true, true}, {false, false, true, false},
  {false, true, true, false}, {false, true, false, false}, {true, true, false, false}, {true, false, false, false}
};
int step_index = 0;

float tempHigh = 31.0, tempLow = 24.0;
int humiHigh = 85, humiLow = 55;

// ===================== BIEN TRANG THAI TOAN CUC =====================
long diem_khong_raw = 0;
int cheDoAuto = 0;
bool dang_cho_an = false;

float cam_hien_tai = 0;
float cam_da_xa_me_nay = 0;
float moc_bat_dau = 0;
float luong_cam_cu = 0;
int nuocMangStatus = 0;

unsigned long lastLcdUpdate = 0;
const unsigned long LCD_UPDATE_INTERVAL = 2000;  // update LCD moi 2s, khong lam giat motor

unsigned long bomNuocStartTime = 0;
bool dangBomNuoc = false;
bool feedMotorActive = false;
unsigned long lastFeedStepMs = 0;

// SUA: canh bao do them cam hien NGAY lap tuc, khong cho chu ky LCD 2s
bool refillAlertActive = false;
unsigned long refillAlertUntilMs = 0;
const unsigned long REFILL_ALERT_DURATION_MS = 2500;  // dai hon LCD_UPDATE_INTERVAL de chac chan hien duoc

// ===================== HAM BAT/TAT RELAY =====================
// Quy uoc: HIGH = BAT, LOW = TAT (Active HIGH - da xac nhan thuc te)
void setRelayState(int pin, bool active) {
  digitalWrite(pin, active ? HIGH : LOW);
}

void setAllRelaysOff() {
  setRelayState(PIN_QUAT1, false);
  setRelayState(PIN_QUAT2, false);
  setRelayState(PIN_DEN_SANG, false);
  setRelayState(PIN_DEN_SUOI, false);
  setRelayState(PIN_BOM_MANG, false);
  setRelayState(PIN_BOM_SAN, false);
  setRelayState(PIN_BOM_TAM, false);
  setRelayState(PIN_PHUN_SUONG, false);
}

// ===================== CAC HAM XU LY LUU TRU FLASH =====================
void luuDiemKhong(long raw) {
  prefs.begin("cancamapp", false);
  prefs.putLong("diem0", raw);
  prefs.end();
  Serial.print("[FLASH] Da luu diem 0 moi: "); Serial.println(raw);
}

long docDiemKhong() {
  prefs.begin("cancamapp", true);
  long val = prefs.getLong("diem0", LONG_MIN);
  prefs.end();
  return val;
}

bool daTungHieuChuan() {
  return docDiemKhong() != LONG_MIN;
}

// ===================== CAC HAM DOC CAN NANG =====================
float docCanThuc() {
  long raw = scale.read_average(5);
  float thuc = (raw - diem_khong_raw) / calibration_factor;
  if (thuc < 0) thuc = 0;
  return thuc;
}

float docCanNhanh() {
  long raw = scale.get_units(1);
  float thuc = (raw - diem_khong_raw) / calibration_factor;
  if (thuc < 0) thuc = 0;
  return thuc;
}

// ===================== DONG CO BUOC (NON-BLOCKING) =====================
void moveOneStepCCW() {
  digitalWrite(IN1, ccw_steps[step_index][0]);
  digitalWrite(IN2, ccw_steps[step_index][1]);
  digitalWrite(IN3, ccw_steps[step_index][2]);
  digitalWrite(IN4, ccw_steps[step_index][3]);
  step_index++;
  if (step_index > 7) step_index = 0;
}

void motorStop() {
  feedMotorActive = false;
  digitalWrite(IN1, LOW); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW); digitalWrite(IN4, LOW);
}

void startFeedMotor() {
  feedMotorActive = true;
  lastFeedStepMs = millis();
}

// Goi ham nay MOI VONG LOOP - tu quyet dinh co nen buoc 1 nac hay chua dua vao millis()
void updateFeedMotor() {
  if (!dang_cho_an || !feedMotorActive) return;
  if (millis() - lastFeedStepMs < FEED_STEP_INTERVAL_MS) return;

  lastFeedStepMs = millis();
  moveOneStepCCW();
}

// SUA: goi lcdShowRefillAlert() NGAY LAP TUC, khong cho chu ky LCD 2s nua
void triggerRefillAlert() {
  refillAlertActive = true;
  refillAlertUntilMs = millis() + REFILL_ALERT_DURATION_MS;
  lcdShowRefillAlert();   // hien thi NGAY, dam bao nguoi dung thay duoc canh bao
}

void bat_dau_cho_an() {
  cam_hien_tai = docCanThuc();
  moc_bat_dau = cam_hien_tai;
  cam_da_xa_me_nay = 0;
  luong_cam_cu = cam_hien_tai;
  dang_cho_an = true;
  startFeedMotor();

  Serial.println("\n=========== BAT DAU CHU KY CHO AN ===========");
  lcd.clear();
  lcdShowFeeding();
}

// ===================== HIEN THI MAN HINH LCD =====================
void lcdShowBoot() {
  lcd.clear();
  lcd.setCursor(0, 0); lcd.print("HE THONG CAN CAM");
  lcd.setCursor(0, 1); lcd.print("Dang khoi dong...");
}

void lcdShowWaiting() {
  lcd.setCursor(0, 0); lcd.print("CHE DO: ");
  lcd.print(cheDoAuto ? "TUDONG (AUTO) " : "TAY (MANUAL)");
  lcd.setCursor(0, 1); lcd.print("Cam ton: "); lcd.print(cam_hien_tai, 1); lcd.print(" g   ");
  lcd.setCursor(0, 2); lcd.print("Nuoc mang: "); lcd.print(nuocMangStatus ? "DAY " : "CAN ");
  lcd.setCursor(0, 3); lcd.print("Cho lenh tu App... ");
}

void lcdShowFeeding() {
  lcd.setCursor(0, 0); lcd.print("DANG XA CAM...      ");
  lcd.setCursor(0, 1); lcd.print("Trong bon: "); lcd.print(cam_hien_tai, 1); lcd.print(" g      ");
  lcd.setCursor(0, 2); lcd.print("Da xa: "); lcd.print(cam_da_xa_me_nay, 1); lcd.print(" / "); lcd.print(target_weight, 0); lcd.print("g   ");
  int phantram = (int)((cam_da_xa_me_nay / target_weight) * 100);
  if (phantram > 100) phantram = 100;
  if (phantram < 0) phantram = 0;
  lcd.setCursor(0, 3); lcd.print("Tien trinh: "); lcd.print(phantram); lcd.print("%     ");
}

void lcdShowRefillAlert() {
  lcd.setCursor(0, 0); lcd.print("!! PHAT HIEN DO CAM !!");
}

// ===================== GIAO TIEP CLOUD BLYNK TRUYEN XUONG VAT LY =====================
BLYNK_WRITE(V5) { cheDoAuto = param.asInt(); lcd.clear(); }
BLYNK_WRITE(V4) { target_weight = param.asFloat(); }

BLYNK_WRITE(V6) {
  if (param.asInt() == 1 && !dang_cho_an) {
    bat_dau_cho_an();
    Blynk.virtualWrite(V6, 0);
  }
}

// Quy uoc: HIGH = BAT, LOW = TAT
BLYNK_WRITE(V7)  { if(cheDoAuto == 0) setRelayState(PIN_QUAT1, param.asInt() == 1); }
BLYNK_WRITE(V8)  { if(cheDoAuto == 0) setRelayState(PIN_QUAT2, param.asInt() == 1); }
BLYNK_WRITE(V9)  { if(cheDoAuto == 0) setRelayState(PIN_DEN_SANG, param.asInt() == 1); }
BLYNK_WRITE(V10) { if(cheDoAuto == 0) setRelayState(PIN_DEN_SUOI, param.asInt() == 1); }
BLYNK_WRITE(V11) { if(cheDoAuto == 0) { setRelayState(PIN_BOM_MANG, param.asInt() == 1); dangBomNuoc = (param.asInt() == 1); } }
BLYNK_WRITE(V12) { if(cheDoAuto == 0) setRelayState(PIN_BOM_SAN, param.asInt() == 1); }
BLYNK_WRITE(V13) { if(cheDoAuto == 0) setRelayState(PIN_BOM_TAM, param.asInt() == 1); }
BLYNK_WRITE(V14) { if(cheDoAuto == 0) setRelayState(PIN_PHUN_SUONG, param.asInt() == 1); }

// ===================== CHU KY KIEM TRA CAM BIEN & XU LY TU DONG =====================
void thucThiChuKyHeThong() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();   // GIU float de isnan() hoat dong dung - Integer chi la kieu hien thi tren Blynk, khong bat buoc bien noi bo phai la int
  int waterVal = analogRead(WATER_SENSOR_PIN);
  nuocMangStatus = (waterVal >= 200) ? 1 : 0;

  if (!isnan(t) && !isnan(h)) {
    Blynk.virtualWrite(V0, t);
    Blynk.virtualWrite(V1, h);
  }
  Blynk.virtualWrite(V2, cam_hien_tai);
  Blynk.virtualWrite(V3, nuocMangStatus);

  // Active HIGH: true = bat bom
  if (nuocMangStatus == 0) {
    if (!dangBomNuoc) {
      setRelayState(PIN_BOM_MANG, true);
      Blynk.virtualWrite(V11, 1);
      bomNuocStartTime = millis();
      dangBomNuoc = true;
    } else {
      if (millis() - bomNuocStartTime > 30000) {
        setRelayState(PIN_BOM_MANG, false);
        Blynk.virtualWrite(V11, 0);
        dangBomNuoc = false;
        Blynk.logEvent("canh_bao_he_thong", "Loi: May bom mang chay qua thoi gian an toan!");
      }
    }
  } else {
    if (dangBomNuoc) {
      setRelayState(PIN_BOM_MANG, false);
      Blynk.virtualWrite(V11, 0);
      dangBomNuoc = false;
    }
  }

  // Active HIGH: true = bat thiet bi
  if (cheDoAuto == 1 && !isnan(t) && !isnan(h)) {
    bool q1 = false, q2 = false, qSg = false, dS = false;

    if (t > tempHigh) {
      q1 = true; q2 = true; qSg = true; dS = false;
    } else if (t < tempLow) {
      q1 = false; q2 = false; qSg = false; dS = true;
    } else {
      dS = false; q2 = false;
      if (h > humiHigh) {
        q1 = true; qSg = false;
      } else if (h < humiLow) {
        q1 = false; qSg = true;
      } else {
        q1 = false; qSg = false;
      }
    }

    setRelayState(PIN_QUAT1, q1);
    setRelayState(PIN_QUAT2, q2);
    setRelayState(PIN_PHUN_SUONG, qSg);
    setRelayState(PIN_DEN_SUOI, dS);

    Blynk.virtualWrite(V7, q1);
    Blynk.virtualWrite(V8, q2);
    Blynk.virtualWrite(V10, dS);
    Blynk.virtualWrite(V14, qSg);
  }
}

// ===================== KHOI TAO HE THONG BAN DAU =====================
void setup() {
  Serial.begin(115200);

  pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT); pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);
  motorStop();

  pinMode(PIN_QUAT1, OUTPUT);
  pinMode(PIN_QUAT2, OUTPUT);
  pinMode(PIN_DEN_SANG, OUTPUT);
  pinMode(PIN_DEN_SUOI, OUTPUT);
  pinMode(PIN_BOM_MANG, OUTPUT);
  pinMode(PIN_BOM_SAN, OUTPUT);
  pinMode(PIN_BOM_TAM, OUTPUT);
  pinMode(PIN_PHUN_SUONG, OUTPUT);
  setAllRelaysOff();

  Wire.begin(1, 2);
  lcd.init();
  lcd.backlight();
  lcdShowBoot();

  dht.begin();
  scale.begin(HX711_DT_PIN, HX711_SCK_PIN);

  // SUA: them lai delay(1000) truoc khi doc diem 0 lan dau, cho HX711 on dinh
  // sau khi vua cap nguon (tranh nhieu ngay luc khoi dong lam sai diem 0)
  if (!daTungHieuChuan()) {
    Serial.println("Lan dau: dang on dinh cam bien truoc khi tare...");
    delay(1000);
    long raw_zero = scale.read_average(10);
    diem_khong_raw = raw_zero;
    luuDiemKhong(raw_zero);
  } else {
    diem_khong_raw = docDiemKhong();
    Serial.print("Doc diem 0 tu Flash: "); Serial.println(diem_khong_raw);
  }
  scale.set_scale(calibration_factor);

  Blynk.begin(auth, ssid, pass);

  timer.setInterval(2000L, thucThiChuKyHeThong);

  cam_hien_tai = docCanThuc();
  lcd.clear();
}

// ===================== LUONG CHAY LIEN TUC VONG LAP LON =====================
void loop() {
  Blynk.run();
  timer.run();

  if (dang_cho_an) {
    cam_hien_tai = docCanNhanh();

    if (cam_hien_tai > luong_cam_cu + 20.0) {
      float luong_vua_do = cam_hien_tai - luong_cam_cu;
      moc_bat_dau += luong_vua_do;
      triggerRefillAlert();   // hien canh bao NGAY, khong cho chu ky LCD
    }
    luong_cam_cu = cam_hien_tai;
    cam_da_xa_me_nay = moc_bat_dau - cam_hien_tai;

    // Buoc motor 1 nac neu du thoi gian - KHONG BLOCKING, Blynk van chay muot
    updateFeedMotor();

    if (cam_da_xa_me_nay >= target_weight) {
      dang_cho_an = false;
      motorStop();
      cam_hien_tai = docCanThuc();
      lcd.clear();
    }

    // Cap nhat LCD dinh ky (khong anh huong toc do motor vi motor da tach rieng qua updateFeedMotor())
    if (millis() - lastLcdUpdate > LCD_UPDATE_INTERVAL) {
      if (refillAlertActive && millis() < refillAlertUntilMs) {
        lcdShowRefillAlert();
      } else {
        refillAlertActive = false;
        lcdShowFeeding();
      }
      lastLcdUpdate = millis();
    }
  } else {
    cam_hien_tai = docCanThuc();

    if (millis() - lastLcdUpdate > LCD_UPDATE_INTERVAL) {
      lcdShowWaiting();
      lastLcdUpdate = millis();
    }
  }
}

/* ===================== TOM TAT CAC SUA DOI LAN NAY =====================

1. TOC DO MOTOR: FEED_STEP_INTERVAL_MS doi tu 2ms -> 1ms, khop dung voi
   step_delay=1000us (1ms) ban da xac nhan chay muot nhat truoc do.
   Bien step_delay cu (khong con dung) da bo hoan toan, tranh gay nham lan.

2. CANH BAO DO THEM CAM: goi lcdShowRefillAlert() NGAY LAP TUC trong ham
   triggerRefillAlert(), khong cho doi chu ky LCD_UPDATE_INTERVAL (2000ms)
   nua. Dong thoi keo dai REFILL_ALERT_DURATION_MS len 2500ms (dai hon
   chu ky LCD) de dam bao lan cap nhat LCD tiep theo van con thay canh bao
   neu can hien thi lai.

3. ON DINH CAM BIEN LAN DAU: them lai delay(1000) truoc khi doc diem 0 lan
   dau tien (luc chua tung hieu chuan), giup HX711 on dinh sau khi vua cap
   nguon, tranh diem 0 bi sai do nhieu dien luc khoi dong.

KIEN TRUC MOTOR (giu nguyen tu ban truoc, day la diem manh):
- Motor chay theo kieu NON-BLOCKING: moi vong loop() chi buoc DUNG 1 nac
  (khong quay 400 buoc lien tuc nhu ban dau), dua vao so sanh millis().
- Loi ich: Blynk.run() va timer.run() luon duoc goi thuong xuyen, khong bi
  "dong bang" 400ms moi lan quay nhu ban truoc -> giam nguy co Blynk mat
  ket noi hoac phan hoi cham do bi che khuat boi vong for quay motor.
- Toc do thuc te: 1 buoc/1ms = 1000 buoc/giay, dung bang toc do ban da xac
  nhan la muot nhat truoc do (voi delayMicroseconds(1000) kieu cu).

============================================================================ */