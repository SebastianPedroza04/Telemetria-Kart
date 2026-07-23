// =====================================================================
// 02_bmi160_csv_mqtt.ino — v2.1
// BMI160 a 100 Hz + CSV serial + MQTT a 10 Hz
// Proyecto: Telemetría inercial e IoT para kart
//
// v2.1: lectura por registro directo (leerBurst) en vez de
//       getAccelGyroData() de la libreria DFRobot, que era lenta
//       (bajaba el muestreo real a ~43 Hz). La libreria queda solo
//       para el arranque del sensor.
//
// Cableado: VIN->3V3, GND->GND, SDA->21, SCL->22, SAO->GND (0x68), CS->3V3
// Monitor serie / capturar_serial.py: 500000 baudios
// Salida serial: t_us,ax,ay,az,gx,gy,gz  (m/s², °/s)
// =====================================================================

#include <DFRobot_BMI160.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>

// ---------- WiFi / MQTT ----------
const char* ssid        = "Tanjito_5G";
const char* password    = "Kipling17@";
const char* mqtt_server = "192.168.2.5";     // IP del PC con Mosquitto (ipconfig)
const int   mqtt_port   = 1883;
const char* topic_imu    = "kart/K01/imu/raw";
const char* topic_status = "kart/K01/status";

// ---------- Muestreo ----------
#define FS_HZ        100
#define PERIODO_US   (1000000UL / FS_HZ)
#define DECIMA_MQTT  10          // publica 1 de cada 10 muestras (10 Hz)
#define BAUD         500000

// ---------- Escalas (rangos configurados abajo) ----------
const float ACC_LSB_POR_G   = 4096.0f;   // ±8 g
const float GYR_LSB_POR_DPS = 32.768f;   // ±1000 °/s
const float G_MS2           = 9.80665f;

// ---------- Objetos ----------
DFRobot_BMI160 bmi160;
const uint8_t i2c_addr = 0x68;
WiFiClient    espClient;
PubSubClient  client(espClient);

uint32_t t_siguiente_us;
uint32_t seq = 0;                 // contador de secuencia (mide pérdidas)
uint32_t ultima_reconexion = 0;

// ---------- Acceso directo a registros del BMI160 ----------
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

  // ---- IMU PRIMERO: debe funcionar aunque no haya red ----
  Wire.begin(21, 22);
  Wire.setClock(400000);

  if (bmi160.softReset() != BMI160_OK) {
    Serial.println("# ERROR: BMI160 no responde. Revisar SAO->GND (0x68), CS->3V3, cables.");
    while (1) delay(1000);
  }
  if (bmi160.I2cInit(i2c_addr) != BMI160_OK) {
    Serial.println("# ERROR: fallo I2cInit. Probar direccion 0x69 (SAO al aire/3V3).");
    while (1) delay(1000);
  }
  Wire.setClock(400000);   // la libreria baja el reloj I2C: volver a subirlo

  // Rangos y frecuencia por registro (independiente de la libreria)
  regWrite(0x40, 0x28);  // ACC_CONF : ODR 100 Hz, filtro normal
  regWrite(0x41, 0x08);  // ACC_RANGE: ±8 g
  regWrite(0x42, 0x28);  // GYR_CONF : ODR 100 Hz, filtro normal
  regWrite(0x43, 0x01);  // GYR_RANGE: ±1000 °/s
  delay(50);
  Serial.println("# sensor=BMI160 fs=100Hz acc=+-8g gyro=+-1000dps fw=2.1");

  // ---- WiFi NO bloqueante ----
  // MODO CARACTERIZACION: WiFi comentado para eliminar bloqueos de MQTT.
  // Para la Fase 6 (telemetria en vivo), descomentar las 3 lineas siguientes.
  // WiFi.mode(WIFI_STA);
  // WiFi.begin(ssid, password);
  // Serial.println("# WiFi conectando en segundo plano...");

  client.setServer(mqtt_server, mqtt_port);
  client.setBufferSize(512);

  Serial.println("t_us,ax,ay,az,gx,gy,gz");
  t_siguiente_us = micros() + PERIODO_US;
}

// Reconexión MQTT sin bloquear (máx. 1 intento cada 3 s)
void mqttMantener() {
  if (WiFi.status() != WL_CONNECTED) return;
  if (client.connected()) { client.loop(); return; }
  uint32_t ahora = millis();
  if (ahora - ultima_reconexion < 3000) return;
  ultima_reconexion = ahora;
  String cid = "kart-K01-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  if (client.connect(cid.c_str())) {
    Serial.println("# MQTT conectado");
    client.publish(topic_status, "{\"evt\":\"boot\"}");
  }
}

void loop() {
  // Instante de muestreo por reloj (no delay); el tiempo muerto es para la red
  while ((int32_t)(micros() - t_siguiente_us) < 0) {
    mqttMantener();
  }
  uint32_t t = micros();
  t_siguiente_us += PERIODO_US;

  // Lectura burst directa: 12 bytes desde 0x0C (gyro+acel, little-endian)
  uint8_t b[12];
  if (!leerBurst(0x0C, b, 12)) {
    Serial.println("# ERROR lectura BMI160");
    return;
  }
  int16_t raw[6] = {
    (int16_t)(b[0]  | (b[1]  << 8)),   // gx
    (int16_t)(b[2]  | (b[3]  << 8)),   // gy
    (int16_t)(b[4]  | (b[5]  << 8)),   // gz
    (int16_t)(b[6]  | (b[7]  << 8)),   // ax
    (int16_t)(b[8]  | (b[9]  << 8)),   // ay
    (int16_t)(b[10] | (b[11] << 8))    // az
  };

  float gx = raw[0] / GYR_LSB_POR_DPS;
  float gy = raw[1] / GYR_LSB_POR_DPS;
  float gz = raw[2] / GYR_LSB_POR_DPS;
  float ax = raw[3] / ACC_LSB_POR_G * G_MS2;
  float ay = raw[4] / ACC_LSB_POR_G * G_MS2;
  float az = raw[5] / ACC_LSB_POR_G * G_MS2;

  // CSV por serial SIEMPRE (100 Hz) — fuente de verdad para caracterizar
  Serial.printf("%lu,%.4f,%.4f,%.4f,%.3f,%.3f,%.3f\n",
                (unsigned long)t, ax, ay, az, gx, gy, gz);

  // MQTT decimado (10 Hz), 6 canales + seq, solo si hay conexión
  if (++seq % DECIMA_MQTT == 0 && client.connected()) {
    char msg[192];
    snprintf(msg, sizeof(msg),
      "{\"ts\":%lu,\"seq\":%lu,\"ax\":%.3f,\"ay\":%.3f,\"az\":%.3f,"
      "\"gx\":%.2f,\"gy\":%.2f,\"gz\":%.2f}",
      (unsigned long)t, (unsigned long)seq, ax, ay, az, gx, gy, gz);
    client.publish(topic_imu, msg);
  }
}
