// =====================================================================
// 04_gps_test.ino — Prueba del GPS Quectel L86-M33 (Fase 10)
// Objetivo: fix, satélites, HDOP, posición, velocidad y rumbo a 10 Hz.
//
// LIBRERÍA REQUERIDA: "TinyGPSPlus" de Mikal Hart
//   (Arduino IDE -> Tools -> Manage Libraries -> buscar "TinyGPSPlus" -> Install)
//
// Cableado L86 -> ESP32:
//   VCC -> 3V3        GND -> GND
//   TX  -> GPIO16     RX  -> GPIO17
//   (TX del GPS al RX2 del ESP32 y viceversa: van CRUZADOS)
//   La IMU puede quedar conectada (usa otros pines); este sketch no la lee.
//
// IMPORTANTE: probar CERCA DE UNA VENTANA o al aire libre. Bajo techo no
// hay fix. Primer fix en frío: 30-60 s con cielo visible. El L86 arranca
// a 9600 baudios y 1 Hz; este sketch lo sube a 115200 y 10 Hz en caliente
// (no queda guardado: se reconfigura en cada arranque).
//
// Salida (monitor serie a 500000):
//   Líneas '#' -> estado legible cada segundo
//   Líneas CSV -> t_us,lat,lon,v_ms,rumbo,sats,hdop   (solo cuando hay fix)
//   Compatible con capturar_serial.py para registrar recorridos.
// =====================================================================

#include <TinyGPSPlus.h>

#define BAUD_PC   500000
#define GPS_RX    16        // RX2 del ESP32  <- TX del L86
#define GPS_TX    17        // TX2 del ESP32  -> RX del L86

TinyGPSPlus gps;
HardwareSerial SerialGPS(2);

uint32_t t_status = 0;
uint32_t nmea_rx = 0;
bool     fix_anunciado = false;

// Detecta a qué baudios está hablando el L86 (9600 de fábrica; 115200 si
// quedó configurado de un arranque anterior sin cortar alimentación)
long detectarBaud() {
  const long candidatos[] = { 9600, 115200 };
  for (long b : candidatos) {
    SerialGPS.begin(b, SERIAL_8N1, GPS_RX, GPS_TX);
    uint32_t t0 = millis();
    while (millis() - t0 < 1500) {
      if (SerialGPS.available() && SerialGPS.read() == '$') return b;
    }
    SerialGPS.end();
  }
  return 0;
}

void setup() {
  Serial.begin(BAUD_PC);
  delay(500);
  Serial.println("# Prueba GPS Quectel L86-M33");

  long b = detectarBaud();
  if (b == 0) {
    Serial.println("# ERROR: no llegan tramas NMEA. Revisar cruce TX/RX y alimentacion.");
    Serial.println("# (el LED del L86 parpadea lento solo cuando tiene fix; sin LED no significa muerto)");
    while (1) delay(1000);
  }
  Serial.printf("# L86 detectado a %ld baudios\n", b);

  if (b == 9600) {
    // Subir a 115200 (necesario para 10 Hz sin saturar el UART)
    SerialGPS.println("$PMTK251,115200*1F");
    delay(200);
    SerialGPS.end();
    SerialGPS.begin(115200, SERIAL_8N1, GPS_RX, GPS_TX);
  }
  // Tasa de actualizacion: 10 Hz (100 ms)
  SerialGPS.println("$PMTK220,100*2F");
  // Solo RMC+GGA (velocidad/rumbo + posicion/sats/hdop), menos trafico:
  SerialGPS.println("$PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0*28");
  Serial.println("# Configurado: 115200 baudios, 10 Hz, RMC+GGA");
  Serial.println("t_us,lat,lon,v_ms,rumbo,sats,hdop");
}

void loop() {
  while (SerialGPS.available()) {
    if (gps.encode(SerialGPS.read())) {
      // Sentencia completa parseada
      if (gps.location.isValid() && gps.location.isUpdated()) {
        Serial.printf("%lu,%.6f,%.6f,%.2f,%.1f,%d,%.2f\n",
                      (unsigned long)micros(),
                      gps.location.lat(), gps.location.lng(),
                      gps.speed.mps(),
                      gps.course.deg(),
                      (int)gps.satellites.value(),
                      gps.hdop.hdop());
        if (!fix_anunciado) { Serial.println("# *** FIX CONSEGUIDO ***"); fix_anunciado = true; }
      }
    }
    nmea_rx++;
  }

  // Estado legible cada segundo
  if (millis() - t_status >= 1000) {
    t_status = millis();
    Serial.printf("# sats=%d hdop=%.2f fix=%s chars=%lu edad_pos=%lus\n",
                  (int)gps.satellites.value(),
                  gps.hdop.isValid() ? gps.hdop.hdop() : 99.9,
                  gps.location.isValid() ? "SI" : "no",
                  (unsigned long)nmea_rx,
                  gps.location.isValid() ? (unsigned long)(gps.location.age() / 1000) : 0);
    if (nmea_rx == 0)
      Serial.println("# (0 caracteres: revisar cableado TX/RX cruzado)");
  }
}
