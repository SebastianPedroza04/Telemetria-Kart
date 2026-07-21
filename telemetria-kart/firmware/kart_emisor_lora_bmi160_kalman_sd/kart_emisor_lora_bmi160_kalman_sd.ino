// Versión futura: emisor LoRa + BMI160 + Kalman + microSD.
// Requiere tarjeta microSD instalada.
//
// Conexiones microSD:
// VCC  -> 3V3
// GND  -> GND
// SCK  -> GPIO18
// MISO -> GPIO19
// MOSI -> GPIO23
// CS   -> GPIO13
//
// Usar esta versión cuando se compre la microSD.
// Recomendación: partir de kart_emisor_lora_bmi160_kalman.ino
// y agregar SD.begin(13, SPI), archivo CSV y logFile.println(dataLine).
//
// Formato CSV:
// seq,t_us,ax,ay,az,gx,gy,gz,roll,pitch,g_lat,g_lon,yaw_rate
