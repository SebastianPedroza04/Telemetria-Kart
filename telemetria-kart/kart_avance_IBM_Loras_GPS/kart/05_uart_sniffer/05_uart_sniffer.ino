// =====================================================================
// 05_uart_sniffer.ino — Diagnóstico del enlace con el GPS L86
// Escucha en GPIO16 probando varios baudios y reporta CUÁNTOS bytes
// llegan en cada uno (aunque sean basura). Distingue:
//   - bytes > 0 en algún baudio -> el GPS vive; era cuestión de baudios
//   - bytes = 0 en TODOS        -> problema de cableado o alimentación
// Repite el ciclo indefinidamente (puedes recablear sin resubir).
// Monitor serie a 500000.
// =====================================================================

#define GPS_RX 16
#define GPS_TX 17

HardwareSerial SerialGPS(2);
const long BAUDS[] = { 9600, 115200, 4800, 38400, 57600, 19200 };

void setup() {
  Serial.begin(500000);
  delay(300);
  Serial.println("# Sniffer UART2 (GPIO16). Ciclo de baudios cada ~2 s por tasa.");
}

void loop() {
  for (long b : BAUDS) {
    SerialGPS.begin(b, SERIAL_8N1, GPS_RX, GPS_TX);
    uint32_t n = 0, imprimibles = 0, dolares = 0;
    char muestra[41]; int m = 0;
    uint32_t t0 = millis();
    while (millis() - t0 < 2000) {
      while (SerialGPS.available()) {
        char c = SerialGPS.read();
        n++;
        if (c >= 32 && c < 127) {
          imprimibles++;
          if (m < 40) muestra[m++] = c;
        }
        if (c == '$') dolares++;
      }
    }
    muestra[m] = 0;
    SerialGPS.end();
    Serial.printf("# %6ld baud: %5lu bytes, %5lu legibles, %3lu '$'  |%s|\n",
                  b, (unsigned long)n, (unsigned long)imprimibles,
                  (unsigned long)dolares, muestra);
  }
  Serial.println("# --- fin de ciclo; repite ---");
}
