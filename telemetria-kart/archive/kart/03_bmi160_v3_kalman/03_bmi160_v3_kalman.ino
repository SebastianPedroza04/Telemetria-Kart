// =====================================================================
// 03_bmi160_v3_kalman.ino — Firmware v3
// Fase 5: calibración en vivo (offsets/sensibilidades medidos 17/07/2026)
// Fase 9: Kalman embebido (roll y pitch) a 100 Hz
// Fase 6: MQTT anti-bloqueo (sondeo TCP 0.5 s antes de conectar)
//
// Salida serial (500000 baudios), AHORA 9 COLUMNAS:
//   t_us,ax,ay,az,gx,gy,gz,roll,pitch
//   (aceleraciones y giros YA CALIBRADOS, en m/s² y °/s; ángulos en °)
// Nota: estadistica_reposo.py espera 7 columnas (archivos del firmware
// v2.1); para estos archivos usar comparar_kalman.py.
//
// Cableado: VIN->3V3, GND->GND, SDA->21, SCL->22, SAO->GND (0x68), CS->3V3
// =====================================================================

#include <DFRobot_BMI160.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <math.h>

// ---------- WiFi / MQTT ----------
//const char* ssid        = "Tanjito_5G";
//const char* password    = "Kipling17@";
const char* ssid        = "MULTIFAMILIAR";
const char* password    = "Loft2051";
const char* mqtt_server = "192.168.0.13";
const int   mqtt_port   = 1883;
const char* topic_imu    = "kart/K01/imu/filt";
const char* topic_status = "kart/K01/status";

// ---------- Muestreo ----------
#define FS_HZ        100
#define PERIODO_US   (1000000UL / FS_HZ)
#define DECIMA_MQTT  10
#define BAUD         500000

// ---------- Escalas ----------
const float ACC_LSB_POR_G   = 4096.0f;    // ±8 g
const float GYR_LSB_POR_DPS = 32.768f;    // ±1000 °/s
const float G_MS2           = 9.80665f;

// ---------- FASE 5: calibración medida (seis posiciones + reposo) ----------
const float OFF_A[3]  = { 0.319f, -0.236f, -0.471f };   // m/s²  (x, y, z)
const float SENS_A[3] = { 1.0041f, 0.9931f, 0.9969f };
const float BIAS_G[3] = { -0.065f, 0.194f, -0.086f };   // °/s

// ---------- FASE 9: Kalman embebido ----------
const float KF_R      = 0.004f;    // (°)²    — de la caracterización
const float SIG_GYRO  = 0.05f;     // °/s
const float Q_BIAS    = 1e-8f;

struct Kalman2 {
  float ang = 0, bias = 0;
  float P00 = 1, P01 = 0, P10 = 0, P11 = 0.1f;
  bool init = false;
  float update(float ang_med, float omega, float dt) {
    if (!init) { ang = ang_med; init = true; }
    // Predicción
    ang += (omega - bias) * dt;
    float q_ang = SIG_GYRO * SIG_GYRO * dt;
    P00 += dt * (dt * P11 - P01 - P10) + q_ang;
    P01 -= dt * P11;
    P10 -= dt * P11;
    P11 += Q_BIAS * dt;
    // Corrección con residuo envuelto a [-180, 180]
    float r = ang_med - ang;
    r = fmodf(r + 540.0f, 360.0f) - 180.0f;
    float S  = P00 + KF_R;
    float K0 = P00 / S, K1 = P10 / S;
    ang  += K0 * r;
    bias += K1 * r;
    float p00 = P00, p01 = P01;
    P00 -= K0 * p00;  P01 -= K0 * p01;
    P10 -= K1 * p00;  P11 -= K1 * p01;
    return ang;
  }
};
Kalman2 kfRoll, kfPitch;

// ---------- Objetos ----------
DFRobot_BMI160 bmi160;
const uint8_t i2c_addr = 0x68;
WiFiClient    espClient;
PubSubClient  client(espClient);

uint32_t t_siguiente_us, seq = 0, ultima_reconexion = 0, t_prev_us = 0;

void regWrite(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(i2c_addr);
  Wire.write(reg); Wire.write(val);
  Wire.endTransmission();
}
bool leerBurst(uint8_t reg, uint8_t *buf, uint8_t n) {
  Wire.beginTransmission(i2c_addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(i2c_addr, n) != n) return false;
  for (uint8_t i = 0; i < n; i++) buf[i] = Wire.read();
  return true;
}

void setup() {
  Serial.begin(BAUD);
  delay(500);
  Wire.begin(21, 22);
  Wire.setClock(400000);

  if (bmi160.softReset() != BMI160_OK) {
    Serial.println("# ERROR: BMI160 no responde."); while (1) delay(1000);
  }
  if (bmi160.I2cInit(i2c_addr) != BMI160_OK) {
    Serial.println("# ERROR: fallo I2cInit."); while (1) delay(1000);
  }
  Wire.setClock(400000);
  regWrite(0x40, 0x28);  regWrite(0x41, 0x08);   // acel 100 Hz, ±8 g
  regWrite(0x42, 0x28);  regWrite(0x43, 0x01);   // gyro 100 Hz, ±1000 °/s
  delay(50);
  Serial.println("# sensor=BMI160 fw=3.0 calibrado=si kalman=si fs=100Hz");

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);            // no bloquea: sigue en segundo plano
  client.setServer(mqtt_server, mqtt_port);
  client.setBufferSize(512);

  Serial.println("t_us,ax,ay,az,gx,gy,gz,roll,pitch");
  t_prev_us = micros();
  t_siguiente_us = micros() + PERIODO_US;
}

// FASE 6: mantenimiento MQTT SIN bloqueo largo.
// Sondeo TCP con timeout de 500 ms ANTES del connect de PubSubClient:
// si el broker no responde el sondeo, ni se intenta (evita el bloqueo de ~10 s).
void mqttMantener() {
  if (WiFi.status() != WL_CONNECTED) return;
  if (client.connected()) { client.loop(); return; }
  uint32_t ahora = millis();
  if (ahora - ultima_reconexion < 3000) return;
  ultima_reconexion = ahora;
  WiFiClient sonda;
  if (!sonda.connect(mqtt_server, mqtt_port, 500)) { sonda.stop(); return; }
  sonda.stop();
  String cid = "kart-K01-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  if (client.connect(cid.c_str())) {
    Serial.println("# MQTT conectado");
    client.publish(topic_status, "{\"evt\":\"boot\",\"fw\":\"3.0\"}");
  }
}

void loop() {
  while ((int32_t)(micros() - t_siguiente_us) < 0) { mqttMantener(); }
  uint32_t t = micros();
  t_siguiente_us += PERIODO_US;
  float dt = (t - t_prev_us) * 1e-6f;
  if (dt <= 0 || dt > 0.1f) dt = 0.01f;
  t_prev_us = t;

  uint8_t b[12];
  if (!leerBurst(0x0C, b, 12)) { Serial.println("# ERROR lectura BMI160"); return; }
  int16_t rg[3] = { (int16_t)(b[0] | (b[1] << 8)), (int16_t)(b[2] | (b[3] << 8)),
                    (int16_t)(b[4] | (b[5] << 8)) };
  int16_t ra[3] = { (int16_t)(b[6] | (b[7] << 8)), (int16_t)(b[8] | (b[9] << 8)),
                    (int16_t)(b[10] | (b[11] << 8)) };

  // FASE 5: conversión + calibración en vivo
  float a[3], g[3];
  for (int i = 0; i < 3; i++) {
    a[i] = (ra[i] / ACC_LSB_POR_G * G_MS2 - OFF_A[i]) / SENS_A[i];
    g[i] = rg[i] / GYR_LSB_POR_DPS - BIAS_G[i];
  }

  // FASE 9: Kalman embebido
  float roll_acc  = atan2f(a[1], a[2]) * RAD_TO_DEG;
  float pitch_acc = atan2f(-a[0], sqrtf(a[1] * a[1] + a[2] * a[2])) * RAD_TO_DEG;
  float roll  = kfRoll.update(roll_acc,  g[0], dt);
  float pitch = kfPitch.update(pitch_acc, g[1], dt);

  // CSV 9 columnas (calibrado + ángulos KF)
  Serial.printf("%lu,%.4f,%.4f,%.4f,%.3f,%.3f,%.3f,%.3f,%.3f\n",
                (unsigned long)t, a[0], a[1], a[2], g[0], g[1], g[2], roll, pitch);

  if (++seq % DECIMA_MQTT == 0 && client.connected()) {
    char msg[224];
    snprintf(msg, sizeof(msg),
      "{\"ts\":%lu,\"seq\":%lu,\"ax\":%.3f,\"ay\":%.3f,\"az\":%.3f,"
      "\"gz\":%.2f,\"roll\":%.2f,\"pitch\":%.2f}",
      (unsigned long)t, (unsigned long)seq, a[0], a[1], a[2], g[2], roll, pitch);
    client.publish(topic_imu, msg);
  }
}
