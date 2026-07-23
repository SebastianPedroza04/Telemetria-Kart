// =====================================================================
// 06_gps_crudo.ino — v2: Passthrough NMEA crudo del L86, baudios FIJOS 9600
// (el L86 siempre arranca a 9600 tras cortarle la energía)
//
// Cableado: L86 VCC->3V3, GND->GND, TX->GPIO16, RX->GPIO17
// Monitor serie a 500000.
//
// Cómo leer las tramas $GPGSV / $GLGSV:
//   $GPGSV,3,1,10,05,65,123,38,12,40,210,25,...
//                ^^ satélites a la vista (10 aquí)
//   Grupos de 4 números: sat, elevación, azimut, SNR.
//   El ÚLTIMO de cada grupo es el SNR en dB:
//     vacío o <15 = casi nada | 20-30 = regular | >30 = buena señal
//
// Diagnóstico:
//   Varios sats con SNR >25   -> antena bien; el fix es cuestión de esperar
//   Sats listados, SNR vacíos -> obstrucción / orientación / interferencia
//   Siempre 0 sats (3+ min a cielo abierto) -> problema de RF/antena
//   Basura o silencio         -> contacto físico (soldar el header)
// =====================================================================

#define GPS_RX 16
#define GPS_TX 17
HardwareSerial SerialGPS(2);

void setup() {
  Serial.begin(500000);
  delay(300);

  SerialGPS.begin(9600, SERIAL_8N1, GPS_RX, GPS_TX);

  // Restaurar TODAS las tramas por defecto (incluye GSV) a 1 Hz
  SerialGPS.println("$PMTK314,-1*04");
  SerialGPS.println("$PMTK220,1000*1F");

  Serial.println("# Passthrough crudo del L86 a 9600. Buscar lineas $GPGSV / $GLGSV:");
}

void loop() {
  while (SerialGPS.available()) Serial.write(SerialGPS.read());
}