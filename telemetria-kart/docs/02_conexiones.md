# Conexiones del sistema

## BMI160 a ESP32

```text
BMI160 VCC   -> ESP32 3V3
BMI160 GND   -> ESP32 GND
BMI160 SDA   -> ESP32 GPIO21
BMI160 SCL   -> ESP32 GPIO22
BMI160 CSB   -> ESP32 3V3
BMI160 SDO   -> ESP32 GND
```

Notas:

- `CSB` a 3V3 fuerza modo I2C.
- `SDO` a GND usa dirección I2C `0x68`.
- Si `SDO` va a 3V3, cambiar dirección a `0x69`.

## LoRa RA-01 a ESP32

```text
RA-01 VCC   -> ESP32 3V3
RA-01 GND   -> ESP32 GND
RA-01 SCK   -> ESP32 GPIO18
RA-01 MISO  -> ESP32 GPIO19
RA-01 MOSI  -> ESP32 GPIO23
RA-01 NSS   -> ESP32 GPIO5
RA-01 RST   -> ESP32 GPIO14
RA-01 DIO0  -> ESP32 GPIO26
```

Notas:

- No alimentar RA-01 con 5 V.
- No transmitir sin antena.
- Si se usa fuente externa 3.3 V para LoRa, unir GND de la fuente con GND de la ESP32.

## microSD futura

```text
microSD VCC   -> ESP32 3V3
microSD GND   -> ESP32 GND
microSD SCK   -> ESP32 GPIO18
microSD MISO  -> ESP32 GPIO19
microSD MOSI  -> ESP32 GPIO23
microSD CS    -> ESP32 GPIO13
```

Clave:

```text
LoRa NSS/CS = GPIO5
microSD CS  = GPIO13
```
