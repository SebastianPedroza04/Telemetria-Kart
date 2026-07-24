
#include <Wire.h>
#include <SPI.h>
#include <LoRa.h>
#include <math.h>

#define DEBUG_SERIAL true      // eco del paquete LoRa por serial (5 Hz)
#define MODO_LAB     false     // CSV de 100 Hz por serial para laboratorio

const unsigned long LORA_PERIOD_MS  = 200;    // 5 Hz
const unsigned long SAMPLE_PERIOD_US = 10000; // 100 Hz

#define I2C_SDA 21
#define I2C_SCL 22
#define BMI160_ADDR 0x68

#define LORA_SCK   18
#define LORA_MISO  19
#define LORA_MOSI  23
#define LORA_SS    5
#define LORA_RST   14
#define LORA_DIO0  26
#define LORA_FREQ 433E6

#define BMI160_CHIP_ID_REG  0x00
#define BMI160_DATA_START   0x0C
#define BMI160_ACC_CONF     0x40
#define BMI160_ACC_RANGE    0x41
#define BMI160_GYR_CONF     0x42
#define BMI160_GYR_RANGE    0x43
#define BMI160_CMD_REG      0x7E

const float G_TO_MS2       = 9.80665;
const float ACC_LSB_PER_G  = 4096.0;    // ±8 g
const float GYR_LSB_PER_DPS = 32.768;   // ±1000 °/s (32768/1000)

// ---- Calibración DEFINITIVA (seis posiciones + reposo, 17/07/2026) ----
const float ACC_OFF_X  =  0.319,  ACC_OFF_Y  = -0.236,  ACC_OFF_Z  = -0.471;  // m/s²
const float ACC_SENS_X =  1.0041, ACC_SENS_Y =  0.9931, ACC_SENS_Z =  0.9969;
const float GYR_BIAS_X = -0.065,  GYR_BIAS_Y =  0.194,  GYR_BIAS_Z = -0.086;  // °/s

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
unsigned long seq = 0;
unsigned long lastSampleUs = 0;
unsigned long lastLoraMs = 0;
float ax = 0, ay = 0, az = 0;
float gx = 0, gy = 0, gz = 0;
float rollKal = 0, pitchKal = 0;
float gLat = 0, gLon = 0, yawRate = 0;

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

// Conversión + calibración completa (offset Y sensibilidad)
inline float calAx(int16_t raw) { return (((float)raw / ACC_LSB_PER_G) * G_TO_MS2 - ACC_OFF_X) / ACC_SENS_X; }
inline float calAy(int16_t raw) { return (((float)raw / ACC_LSB_PER_G) * G_TO_MS2 - ACC_OFF_Y) / ACC_SENS_Y; }
inline float calAz(int16_t raw) { return (((float)raw / ACC_LSB_PER_G) * G_TO_MS2 - ACC_OFF_Z) / ACC_SENS_Z; }

bool initBMI160() {
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);
  delay(100);
  uint8_t chip = readReg(BMI160_CHIP_ID_REG);
  Serial.print("BMI160 CHIP_ID = 0x");
  Serial.println(chip, HEX);
  if (chip != 0xD1) {
    Serial.println("ERROR: BMI160 no detectada.");
    return false;
  }
  writeReg(BMI160_CMD_REG, 0xB6);
  delay(100);
  writeReg(BMI160_CMD_REG, 0x11);
  delay(50);
  writeReg(BMI160_CMD_REG, 0x15);
  delay(100);
  writeReg(BMI160_ACC_CONF, 0x28);
  writeReg(BMI160_GYR_CONF, 0x28);
  writeReg(BMI160_ACC_RANGE, 0x08);
  writeReg(BMI160_GYR_RANGE, 0x01);
  Serial.println("BMI160 OK: 100 Hz, +/-8g, +/-1000 dps.");
  return true;
}

bool initLoRa() {
  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("ERROR: LoRa no inicio.");
    return false;
  }
  LoRa.setSpreadingFactor(7);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);
  LoRa.setSyncWord(0x12);
  LoRa.setTxPower(17);
  LoRa.enableCrc();
  Serial.println("LoRa EMISOR OK (envio asincrono, 5 Hz).");
  return true;
}

void updateIMU(float dt) {
  int16_t gxRaw, gyRaw, gzRaw, axRaw, ayRaw, azRaw;
  if (!readBurst12(gxRaw, gyRaw, gzRaw, axRaw, ayRaw, azRaw)) {
    Serial.println("# ERROR lectura BMI160");
    return;
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
  yawRate = gz;
  gLat = ay / G_TO_MS2;
  gLon = ax / G_TO_MS2;

#if MODO_LAB
  // CSV 100 Hz compatible con capturar_serial.py / comparar_kalman.py
  Serial.printf("%lu,%.4f,%.4f,%.4f,%.3f,%.3f,%.3f,%.3f,%.3f\n",
                (unsigned long)micros(), ax, ay, az, gx, gy, gz, rollKal, pitchKal);
#endif
}

String buildDataLine() {
  String line = "";
  line += String(seq);          line += ",";
  line += String(micros());     line += ",";
  line += String(ax, 3);        line += ",";
  line += String(ay, 3);        line += ",";
  line += String(az, 3);        line += ",";
  line += String(gx, 3);        line += ",";
  line += String(gy, 3);        line += ",";
  line += String(gz, 3);        line += ",";
  line += String(rollKal, 3);   line += ",";
  line += String(pitchKal, 3);  line += ",";
  line += String(gLat, 3);      line += ",";
  line += String(gLon, 3);      line += ",";
  line += String(yawRate, 3);
  return line;
}

void sendLoRaPacket() {
  // CAMBIO CLAVE: si el radio sigue transmitiendo el paquete anterior,
  // beginPacket() devuelve 0 y saltamos este ciclo (sin bloquear jamás).
  if (!LoRa.beginPacket()) return;
  String dataLine = buildDataLine();
  LoRa.print("K,");
  LoRa.print(dataLine);
  LoRa.endPacket(true);   // true = asincrono: el loop sigue a 100 Hz
#if !MODO_LAB
  if (DEBUG_SERIAL) {
    Serial.print("TX,K,");
    Serial.println(dataLine);
  }
#endif
  seq++;
}

void setup() {
  Serial.begin(MODO_LAB ? 500000 : 115200);
  delay(1000);
  Serial.println();
  Serial.println("=== KART: BMI160 + KALMAN + LORA v2 ===");
  if (!initBMI160()) while (true) delay(1000);

  // Inicializar el Kalman con el angulo real de arranque
  int16_t gxRaw, gyRaw, gzRaw, axRaw, ayRaw, azRaw;
  if (readBurst12(gxRaw, gyRaw, gzRaw, axRaw, ayRaw, azRaw)) {
    float ax0 = calAx(axRaw), ay0 = calAy(ayRaw), az0 = calAz(azRaw);
    kalmanRoll.theta = atan2(ay0, az0) * 180.0 / PI;
    kalmanPitch.theta = atan2(-ax0, sqrt(ay0 * ay0 + az0 * az0)) * 180.0 / PI;
  }

  if (!initLoRa()) while (true) delay(1000);
#if MODO_LAB
  Serial.println("# MODO_LAB activo: CSV 100 Hz por serial");
  Serial.println("t_us,ax,ay,az,gx,gy,gz,roll,pitch");
#endif
  lastSampleUs = micros();
  lastLoraMs = millis();
  Serial.println("Sistema listo.");
}

void loop() {
  unsigned long nowUs = micros();
  if ((long)(nowUs - lastSampleUs) >= (long)SAMPLE_PERIOD_US) {
    float dt = (nowUs - lastSampleUs) / 1000000.0;
    if (dt <= 0.0 || dt > 0.1) dt = 0.01;
    lastSampleUs += SAMPLE_PERIOD_US;
    updateIMU(dt);
  }
  if (millis() - lastLoraMs >= LORA_PERIOD_MS) {
    lastLoraMs = millis();
    sendLoRaPacket();
  }
}