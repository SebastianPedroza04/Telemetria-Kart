// =====================================================================
// base_final_lora_serial_gps.ino
// BASE: LoRa SF9 -> USB Serial para Node-RED
//
// Recibe paquete compacto del kart:
//   K,seq,t_ms,roll,pitch,g_lat,g_lon,yaw_rate,lat,lon,speed,course,sats,hdop,fix
//
// Sale por Serial USB como CSV:
//   seq,t_ms,roll,pitch,g_lat,g_lon,yaw_rate,lat,lon,gps_speed_mps,
//   gps_course_deg,gps_sats,gps_hdop,gps_fix,rssi,snr,lost,total
// =====================================================================

#include <SPI.h>
#include <LoRa.h>

#define DEBUG_DISCARDED false

#define LORA_SCK   18
#define LORA_MISO  19
#define LORA_MOSI  23
#define LORA_SS    5
#define LORA_RST   14
#define LORA_DIO0  26
#define LORA_FREQ  433E6

unsigned long lastSeq = 0;
bool firstPacket = true;
unsigned long receivedPackets = 0;
unsigned long lostPackets = 0;

bool initLoRa() {
  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("# ERROR: LoRa no inicio. Revisar SPI, alimentacion 3V3 y antena.");
    return false;
  }

  LoRa.setSpreadingFactor(9);       // Debe coincidir con emisor
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);
  LoRa.setSyncWord(0x12);
  LoRa.enableCrc();

  Serial.println("# LoRa RECEPTOR OK: SF9, BW125, CR4/5, 433 MHz.");
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("# ==================================================");
  Serial.println("# BASE FINAL: LoRa SF9 -> Serial -> Node-RED");
  Serial.println("# ==================================================");

  if (!initLoRa()) {
    while (true) delay(1000);
  }

  Serial.println("seq,t_ms,roll,pitch,g_lat,g_lon,yaw_rate,lat,lon,gps_speed_mps,gps_course_deg,gps_sats,gps_hdop,gps_fix,rssi,snr,lost,total");
}

void loop() {
  int packetSize = LoRa.parsePacket();
  if (!packetSize) return;

  String packet = "";
  while (LoRa.available()) {
    packet += (char)LoRa.read();
  }

  if (!packet.startsWith("K,")) {
#if DEBUG_DISCARDED
    Serial.print("# DESCARTADO,");
    Serial.println(packet);
#endif
    return;
  }

  // Quitar cabecera K,
  packet = packet.substring(2);

  int firstComma = packet.indexOf(',');
  if (firstComma <= 0) return;

  long seqParsed = packet.substring(0, firstComma).toInt();
  if (seqParsed < 0) return;

  unsigned long seq = (unsigned long)seqParsed;

  // Si seq retrocede, el emisor se reinició.
  if (!firstPacket && seq < lastSeq) {
    firstPacket = true;
    lostPackets = 0;
    receivedPackets = 0;
    Serial.println("# emisor reiniciado: contadores a cero");
  }

  if (firstPacket) {
    firstPacket = false;
    lastSeq = seq;
  } else {
    if (seq > lastSeq + 1) {
      lostPackets += (seq - lastSeq - 1);
    }
    lastSeq = seq;
  }

  receivedPackets++;

  int rssi = LoRa.packetRssi();
  float snr = LoRa.packetSnr();

  // packet:
  // seq,t_ms,roll,pitch,g_lat,g_lon,yaw_rate,lat,lon,speed,course,sats,hdop,fix
  Serial.print(packet);
  Serial.print(",");
  Serial.print(rssi);
  Serial.print(",");
  Serial.print(snr, 2);
  Serial.print(",");
  Serial.print(lostPackets);
  Serial.print(",");
  Serial.println(receivedPackets);
}
