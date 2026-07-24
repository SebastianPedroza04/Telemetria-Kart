// =====================================================================
// kart_final_imu_gps_lora_sd_CORREGIDO.ino
// KART: BMI160 + Kalman + GPS L86 + microSD 100 Hz + LoRa SF9 2 Hz
//
// Corrección importante:
// - sampleSeq: contador de muestras guardadas en microSD a 100 Hz.
// - radioSeq: contador de paquetes enviados por LoRa a 2 Hz.
// Así el receptor NO interpreta como "perdidos" los 98 datos/s que
// normalmente solo van a microSD.
// =====================================================================

#include <Wire.h>
#include <SPI.h>
#include <LoRa.h>
#include <SD.h>
#include <TinyGPSPlus.h>
#include <math.h>

// -------------------- MODOS --------------------
#define DEBUG_SERIAL true
#define ENABLE_SD_LOG true
#define ENABLE_GPS true

// -------------------- FRECUENCIAS --------------------
const unsigned long SAMPLE_PERIOD_US = 10000;  // IMU + SD: 100 Hz
const unsigned long LORA_PERIOD_MS   = 500;    // LoRa SF9: 2 Hz
const int FLUSH_EVERY_N_LINES = 50;

// -------------------- I2C / BMI160 --------------------
#define I2C_SDA 21
#define I2C_SCL 22
#define BMI160_ADDR 0x68

#define BMI160_CHIP_ID_REG  0x00
#define BMI160_DATA_START   0x0C
#define BMI160_ACC_CONF     0x40
#define BMI160_ACC_RANGE    0x41
#define BMI160_GYR_CONF     0x42
#define BMI160_GYR_RANGE    0x43
#define BMI160_CMD_REG      0x7E

// -------------------- SPI compartido: LoRa + SD --------------------
#define SPI_SCK   18
#define SPI_MISO  19
#define SPI_MOSI  23

#define LORA_SS    5
#define LORA_RST   14
#define LORA_DIO0  26
#define LORA_FREQ  433E6

#define SD_CS      13

// -------------------- GPS L86 --------------------
#define GPS_RX 16       // RX2 ESP32 <- TX GPS
#define GPS_TX 17       // TX2 ESP32 -> RX GPS
#define SERIAL_BAUD 115200

TinyGPSPlus gps;
HardwareSerial SerialGPS(2);

// -------------------- Escalas y calibración IMU --------------------
const float G_TO_MS2        = 9.80665;
const float ACC_LSB_PER_G   = 4096.0;    // ±8 g
const float GYR_LSB_PER_DPS = 32.768;    // ±1000 °/s

// Calibración reportada en el avance del proyecto.
// Offset en m/s², sensibilidad adimensional, bias gyro en °/s.
const float ACC_OFF_X  =  0.319;
const float ACC_OFF_Y  = -0.236;
const float ACC_OFF_Z  = -0.471;

const float ACC_SENS_X =  1.0041;
const float ACC_SENS_Y =  0.9931;
const float ACC_SENS_Z =  0.9969;

const float GYR_BIAS_X = -0.065;
const float GYR_BIAS_Y =  0.194;
const float GYR_BIAS_Z = -0.086;

// -------------------- Cero de montaje --------------------
// Ajustar después de fijar la caja en el kart.
const float MOUNT_ROLL_ZERO_DEG  = 0.0;
const float MOUNT_PITCH_ZERO_DEG = 0.0;

// -------------------- Variables globales --------------------
unsigned long sampleSeq = 0;  // microSD a 100 Hz
unsigned long radioSeq  = 0;  // LoRa a 2 Hz

unsigned long lastSampleUs = 0;
unsigned long lastLoraMs = 0;

float ax = 0, ay = 0, az = 0;      // m/s²
float gx = 0, gy = 0, gz = 0;      // °/s
float rollKal = 0, pitchKal = 0;   // °
float rollOut = 0, pitchOut = 0;   // ° con cero de montaje
float gLat = 0, gLon = 0;          // g
float yawRate = 0;                 // °/s

bool sdOk = false;
File logFile;
char logName[24];
int linesSinceFlush = 0;

// -------------------- Kalman --------------------
class KalmanAngle {
public:
  float theta = 0.0, bias = 0.0;
  float P00 = 1.0, P01 = 0.0, P10 = 0.0, P11 = 0.1;

  const float KF_R = 0.004;
  const float SIG_GYRO = 0.05;
  const float Q_BIAS = 1e-8;

  float update(float theta_med, float omega, float dt) {
    theta = theta + (omega - bias) * dt;

    float Q_theta = SIG_GYRO * SIG_GYRO * dt;
    float Q_bias = Q_BIAS * dt;

    float P00_old = P00, P01_old = P01, P10_old = P10, P11_old = P11;

    P00 = P00_old + dt * (dt * P11_old - P01_old - P10_old) + Q_theta;
    P01 = P01_old - dt * P11_old;
    P10 = P10_old - dt * P11_old;
    P11 = P11_old + Q_bias;

    float r = theta_med - theta;
    while (r > 180.0) r -= 360.0;
    while (r < -180.0) r += 360.0;

    float S = P00 + KF_R;
    float K0 = P00 / S;
    float K1 = P10 / S;

    theta = theta + K0 * r;
    bias = bias + K1 * r;

    P00_old = P00;
    P01_old = P01;

    P00 = P00 - K0 * P00_old;
    P01 = P01 - K0 * P01_old;
    P10 = P10 - K1 * P00_old;
    P11 = P11 - K1 * P01_old;

    return theta;
  }
};

KalmanAngle kalmanRoll, kalmanPitch;

// -------------------- Utilidades --------------------
float wrap180(float a) {
  while (a > 180.0) a -= 360.0;
  while (a < -180.0) a += 360.0;
  return a;
}

void deselectSPI() {
  digitalWrite(LORA_SS, HIGH);
  digitalWrite(SD_CS, HIGH);
}

void writeReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(BMI160_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

uint8_t readReg(uint8_t reg) {
  Wire.beginTransmission(BMI160_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom(BMI160_ADDR, (uint8_t)1);
  if (Wire.available()) return Wire.read();
  return 0xFF;
}

bool readBurst12(int16_t &gxRaw, int16_t &gyRaw, int16_t &gzRaw,
                 int16_t &axRaw, int16_t &ayRaw, int16_t &azRaw) {
  Wire.beginTransmission(BMI160_ADDR);
  Wire.write(BMI160_DATA_START);
  if (Wire.endTransmission(false) != 0) return false;

  Wire.requestFrom(BMI160_ADDR, (uint8_t)12);
  if (Wire.available() < 12) return false;

  uint8_t d[12];
  for (int i = 0; i < 12; i++) d[i] = Wire.read();

  gxRaw = (int16_t)((d[1] << 8) | d[0]);
  gyRaw = (int16_t)((d[3] << 8) | d[2]);
  gzRaw = (int16_t)((d[5] << 8) | d[4]);

  axRaw = (int16_t)((d[7] << 8) | d[6]);
  ayRaw = (int16_t)((d[9] << 8) | d[8]);
  azRaw = (int16_t)((d[11] << 8) | d[10]);

  return true;
}

inline float calAx(int16_t raw) {
  return (((float)raw / ACC_LSB_PER_G) * G_TO_MS2 - ACC_OFF_X) / ACC_SENS_X;
}
inline float calAy(int16_t raw) {
  return (((float)raw / ACC_LSB_PER_G) * G_TO_MS2 - ACC_OFF_Y) / ACC_SENS_Y;
}
inline float calAz(int16_t raw) {
  return (((float)raw / ACC_LSB_PER_G) * G_TO_MS2 - ACC_OFF_Z) / ACC_SENS_Z;
}

// -------------------- Inicialización BMI160 --------------------
bool initBMI160() {
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);
  delay(100);

  uint8_t chip = readReg(BMI160_CHIP_ID_REG);

#if DEBUG_SERIAL
  Serial.print("# BMI160 CHIP_ID = 0x");
  Serial.println(chip, HEX);
#endif

  if (chip != 0xD1) {
    Serial.println("# ERROR: BMI160 no detectada. Revisar VCC, GND, SDA, SCL, CSB y SDO.");
    return false;
  }

  writeReg(BMI160_CMD_REG, 0xB6); delay(100);
  writeReg(BMI160_CMD_REG, 0x11); delay(50);
  writeReg(BMI160_CMD_REG, 0x15); delay(100);

  writeReg(BMI160_ACC_CONF, 0x28);  // ODR 100 Hz
  writeReg(BMI160_GYR_CONF, 0x28);  // ODR 100 Hz
  writeReg(BMI160_ACC_RANGE, 0x08); // ±8 g
  writeReg(BMI160_GYR_RANGE, 0x01); // ±1000 °/s

  Serial.println("# BMI160 OK: 100 Hz, +/-8g, +/-1000 dps.");
  return true;
}

// -------------------- Inicialización GPS --------------------
#if ENABLE_GPS
long detectarBaudGPS() {
  const long candidatos[] = {9600, 115200};
  for (long b : candidatos) {
    SerialGPS.begin(b, SERIAL_8N1, GPS_RX, GPS_TX);
    uint32_t t0 = millis();
    while (millis() - t0 < 1200) {
      if (SerialGPS.available() && SerialGPS.read() == '$') return b;
    }
    SerialGPS.end();
  }
  return 0;
}

bool initGPS() {
  long b = detectarBaudGPS();
  if (b == 0) {
    Serial.println("# AVISO: GPS sin NMEA. Se continua sin fix. Revisar TX/RX, VCC, GND y V_BCKP.");
    SerialGPS.begin(9600, SERIAL_8N1, GPS_RX, GPS_TX);
    return false;
  }

  Serial.print("# GPS detectado a ");
  Serial.print(b);
  Serial.println(" baudios.");

  if (b == 9600) {
    SerialGPS.println("$PMTK251,115200*1F");
    delay(250);
    SerialGPS.end();
    SerialGPS.begin(115200, SERIAL_8N1, GPS_RX, GPS_TX);
  }

  // 5 Hz y solo sentencias RMC + GGA.
  SerialGPS.println("$PMTK220,200*2C");
  SerialGPS.println("$PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0*28");

  Serial.println("# GPS configurado: 115200 baudios, 5 Hz, RMC+GGA.");
  return true;
}
#endif

void serviceGPS() {
#if ENABLE_GPS
  while (SerialGPS.available()) {
    gps.encode(SerialGPS.read());
  }
#endif
}

// -------------------- Inicialización SD --------------------
bool initSD() {
#if !ENABLE_SD_LOG
  Serial.println("# SD desactivada por ENABLE_SD_LOG=false.");
  return false;
#else
  pinMode(SD_CS, OUTPUT);
  pinMode(LORA_SS, OUTPUT);
  deselectSPI();

  if (!SD.begin(SD_CS, SPI)) {
    Serial.println("# ERROR: SD no inicio. Revisar microSD FAT32, CS=13, cables y alimentacion.");
    return false;
  }

  for (int i = 0; i < 1000; i++) {
    snprintf(logName, sizeof(logName), "/KART%03d.CSV", i);
    if (!SD.exists(logName)) {
      logFile = SD.open(logName, FILE_WRITE);
      break;
    }
  }

  if (!logFile) {
    Serial.println("# ERROR: No se pudo crear archivo CSV en SD.");
    return false;
  }

  logFile.println("sample_seq,t_us,ax,ay,az,gx,gy,gz,roll,pitch,g_lat,g_lon,yaw_rate,gps_lat,gps_lon,gps_speed_mps,gps_course_deg,gps_sats,gps_hdop,gps_fix,gps_age_ms");
  logFile.flush();

  Serial.print("# SD OK. Guardando en ");
  Serial.println(logName);
  return true;
#endif
}

// -------------------- Inicialización LoRa --------------------
bool initLoRa() {
  pinMode(SD_CS, OUTPUT);
  pinMode(LORA_SS, OUTPUT);
  deselectSPI();

  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("# ERROR: LoRa no inicio. Revisar SPI, NSS=5, RST=14, DIO0=26, antena y 3V3.");
    return false;
  }

  LoRa.setSpreadingFactor(9);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);
  LoRa.setSyncWord(0x12);
  LoRa.setTxPower(17);
  LoRa.enableCrc();

  Serial.println("# LoRa EMISOR OK: SF9, BW125, CR4/5, 433 MHz, envio 2 Hz.");
  return true;
}

// -------------------- Actualización IMU --------------------
bool updateIMU(float dt) {
  int16_t gxRaw, gyRaw, gzRaw, axRaw, ayRaw, azRaw;

  if (!readBurst12(gxRaw, gyRaw, gzRaw, axRaw, ayRaw, azRaw)) {
    Serial.println("# ERROR lectura BMI160");
    return false;
  }

  ax = calAx(axRaw);
  ay = calAy(ayRaw);
  az = calAz(azRaw);

  gx = (float)gxRaw / GYR_LSB_PER_DPS - GYR_BIAS_X;
  gy = (float)gyRaw / GYR_LSB_PER_DPS - GYR_BIAS_Y;
  gz = (float)gzRaw / GYR_LSB_PER_DPS - GYR_BIAS_Z;

  float rollAcc = atan2(ay, az) * 180.0 / PI;
  float pitchAcc = atan2(-ax, sqrt(ay * ay + az * az)) * 180.0 / PI;

  rollKal = kalmanRoll.update(rollAcc, gx, dt);
  pitchKal = kalmanPitch.update(pitchAcc, gy, dt);

  rollOut = wrap180(rollKal - MOUNT_ROLL_ZERO_DEG);
  pitchOut = wrap180(pitchKal - MOUNT_PITCH_ZERO_DEG);

  yawRate = gz;
  gLat = ay / G_TO_MS2;
  gLon = ax / G_TO_MS2;

  return true;
}

// -------------------- Datos GPS normalizados --------------------
bool gpsFix() {
#if ENABLE_GPS
  return gps.location.isValid() && gps.location.age() < 2500;
#else
  return false;
#endif
}

double gpsLat() {
#if ENABLE_GPS
  return gpsFix() ? gps.location.lat() : 0.0;
#else
  return 0.0;
#endif
}

double gpsLon() {
#if ENABLE_GPS
  return gpsFix() ? gps.location.lng() : 0.0;
#else
  return 0.0;
#endif
}

float gpsSpeed() {
#if ENABLE_GPS
  return gps.speed.isValid() ? gps.speed.mps() : 0.0;
#else
  return 0.0;
#endif
}

float gpsCourse() {
#if ENABLE_GPS
  return gps.course.isValid() ? gps.course.deg() : 0.0;
#else
  return 0.0;
#endif
}

int gpsSats() {
#if ENABLE_GPS
  return gps.satellites.isValid() ? (int)gps.satellites.value() : 0;
#else
  return 0;
#endif
}

float gpsHdop() {
#if ENABLE_GPS
  return gps.hdop.isValid() ? gps.hdop.hdop() : 99.99;
#else
  return 99.99;
#endif
}

unsigned long gpsAge() {
#if ENABLE_GPS
  return gps.location.isValid() ? gps.location.age() : 999999;
#else
  return 999999;
#endif
}

// -------------------- microSD 100 Hz --------------------
void logSDLine() {
  if (!sdOk || !logFile) return;

  char line[260];
  snprintf(line, sizeof(line),
           "%lu,%lu,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.3f,%.3f,%.4f,%.4f,%.4f,%.6f,%.6f,%.2f,%.1f,%d,%.2f,%d,%lu",
           sampleSeq,
           (unsigned long)micros(),
           ax, ay, az,
           gx, gy, gz,
           rollOut, pitchOut,
           gLat, gLon, yawRate,
           gpsLat(), gpsLon(),
           gpsSpeed(), gpsCourse(),
           gpsSats(), gpsHdop(),
           gpsFix() ? 1 : 0,
           gpsAge());

  digitalWrite(LORA_SS, HIGH);
  digitalWrite(SD_CS, LOW);
  logFile.println(line);
  digitalWrite(SD_CS, HIGH);

  linesSinceFlush++;
  if (linesSinceFlush >= FLUSH_EVERY_N_LINES) {
    digitalWrite(LORA_SS, HIGH);
    digitalWrite(SD_CS, LOW);
    logFile.flush();
    digitalWrite(SD_CS, HIGH);
    linesSinceFlush = 0;
  }
}

// -------------------- LoRa 2 Hz --------------------
void sendLoRaPacket() {
  // Formato:
  // K,radio_seq,t_ms,roll,pitch,g_lat,g_lon,yaw_rate,lat,lon,speed,course,sats,hdop,fix

  char packet[220];

  snprintf(packet, sizeof(packet),
           "K,%lu,%lu,%.2f,%.2f,%.3f,%.3f,%.2f,%.6f,%.6f,%.2f,%.1f,%d,%.2f,%d",
           radioSeq,
           millis(),
           rollOut, pitchOut,
           gLat, gLon, yawRate,
           gpsLat(), gpsLon(),
           gpsSpeed(), gpsCourse(),
           gpsSats(), gpsHdop(),
           gpsFix() ? 1 : 0);

  digitalWrite(SD_CS, HIGH);

  if (!LoRa.beginPacket()) return;
  LoRa.print(packet);
  LoRa.endPacket(true);

#if DEBUG_SERIAL
  static unsigned long tLastPrint = 0;
  if (millis() - tLastPrint > 2000) {
    tLastPrint = millis();
    Serial.print("# TX ");
    Serial.println(packet);
  }
#endif

  radioSeq++;
}

// -------------------- Setup --------------------
void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(1000);

  Serial.println();
  Serial.println("# ==================================================");
  Serial.println("# KART FINAL: BMI160 + GPS + microSD + LoRa SF9");
  Serial.println("# ==================================================");

  pinMode(LORA_SS, OUTPUT);
  pinMode(SD_CS, OUTPUT);
  deselectSPI();

  SPI.begin(SPI_SCK, SPI_MISO, SPI_MOSI);

  if (!initBMI160()) {
    while (true) delay(1000);
  }

#if ENABLE_GPS
  initGPS();
#else
  Serial.println("# GPS desactivado por ENABLE_GPS=false.");
#endif

  sdOk = initSD();

  if (!initLoRa()) {
    while (true) delay(1000);
  }

  int16_t gxRaw, gyRaw, gzRaw, axRaw, ayRaw, azRaw;
  if (readBurst12(gxRaw, gyRaw, gzRaw, axRaw, ayRaw, azRaw)) {
    float ax0 = calAx(axRaw);
    float ay0 = calAy(ayRaw);
    float az0 = calAz(azRaw);
    kalmanRoll.theta = atan2(ay0, az0) * 180.0 / PI;
    kalmanPitch.theta = atan2(-ax0, sqrt(ay0 * ay0 + az0 * az0)) * 180.0 / PI;
  }

  lastSampleUs = micros();
  lastLoraMs = millis();

  Serial.println("# Sistema listo.");
  Serial.println("# SD: 100 Hz. LoRa: 2 Hz.");
}

// -------------------- Loop --------------------
void loop() {
  serviceGPS();

  unsigned long nowUs = micros();

  if ((long)(nowUs - lastSampleUs) >= (long)SAMPLE_PERIOD_US) {
    float dt = (nowUs - lastSampleUs) / 1000000.0;
    if (dt <= 0.0 || dt > 0.1) dt = 0.01;

    lastSampleUs += SAMPLE_PERIOD_US;

    if (updateIMU(dt)) {
      logSDLine();
      sampleSeq++;
    }
  }

  if (millis() - lastLoraMs >= LORA_PERIOD_MS) {
    lastLoraMs = millis();
    sendLoRaPacket();
  }
}
