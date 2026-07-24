#include <SPI.h>
#include <LoRa.h>

#define DEBUG_DISCARDED false

#define LORA_SCK   18
#define LORA_MISO  19
#define LORA_MOSI  23
#define LORA_SS    5
#define LORA_RST   14
#define LORA_DIO0  26
#define LORA_FREQ 433E6

unsigned long lastSeq = 0;
bool firstPacket = true;
unsigned long receivedPackets = 0;
unsigned long lostPackets = 0;

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
  LoRa.enableCrc();
  Serial.println("LoRa RECEPTOR OK.");
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println();
  Serial.println("=== BASE: RECEPTOR LORA PARA NODE-RED v2 ===");
  if (!initLoRa()) {
    while (true) delay(1000);
  }
  Serial.println("seq,t_us,ax,ay,az,gx,gy,gz,roll,pitch,g_lat,g_lon,yaw_rate,rssi,snr,lost,total");
}

void loop() {
  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    String packet = "";
    while (LoRa.available()) {
      packet += (char)LoRa.read();
    }
    if (!packet.startsWith("K,")) {
      if (DEBUG_DISCARDED) {
        Serial.print("DESCARTADO,");
        Serial.println(packet);
      }
      return;
    }
    packet = packet.substring(2);

    int rssi = LoRa.packetRssi();
    float snr = LoRa.packetSnr();

    int firstComma = packet.indexOf(',');
    if (firstComma <= 0) return;
    long seqParsed = packet.substring(0, firstComma).toInt();
    if (seqParsed < 0) return;
    unsigned long seq = (unsigned long)seqParsed;

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
}