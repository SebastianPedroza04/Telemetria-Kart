# Telemetría Kart

Sistema de telemetría inercial para kart basado en **ESP32 + BMI160 + LoRa + Node-RED**, con respaldo futuro en **microSD** y posible integración de **GPS L86**.

## Estado actual

El sistema ya permite:

- Leer la IMU BMI160 desde ESP32.
- Convertir aceleración a `m/s²` y giro a `°/s`.
- Aplicar corrección de offset/bias.
- Calcular `roll` y `pitch` con filtro de Kalman embebido.
- Enviar datos por LoRa hacia una ESP32 base.
- Recibir datos por USB serial en Node-RED.
- Visualizar variables en dashboard: Roll, Pitch, G lateral, G longitudinal, Yaw rate, RSSI, SNR y paquetes perdidos.

## Arquitectura

```text
KART
BMI160 -> ESP32 -> Kalman -> LoRa
                         \
                          microSD futura

BASE
LoRa -> ESP32 -> USB Serial -> Node-RED Dashboard
```

## Variables enviadas por LoRa

Formato transmitido por el emisor:

```csv
K,seq,t_us,ax,ay,az,gx,gy,gz,roll,pitch,g_lat,g_lon,yaw_rate
```

Formato recibido por la base y enviado a Node-RED:

```csv
seq,t_us,ax,ay,az,gx,gy,gz,roll,pitch,g_lat,g_lon,yaw_rate,rssi,snr,lost,total
```

## Próximos pasos

1. Comprar microSD.
2. Validar alimentación separada o regulada para LoRa.
3. Mejorar interfaz Node-RED.
4. Calibrar IMU a cero según montaje real.
5. Completar caracterización de IMU.
6. Integrar GPS L86 si el tiempo lo permite.
7. Hacer prueba controlada caminando, bicicleta o carro lento.
8. Hacer prueba final en kart.
