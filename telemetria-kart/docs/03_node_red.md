# Node-RED

## Flujo base

```text
serial in -> function parse telemetria -> debug
```

Configuración del nodo serial:

```text
Serial Port: COM de la ESP32 base
Baud rate: 115200
Data bits: 8
Parity: None
Stop bits: 1
Split input: on character \n
Deliver: ASCII strings
```

## Dashboard

Variables recomendadas:

- Roll: chart, rango -180 a 180.
- Pitch: chart, rango -90 a 90.
- G lateral: gauge, rango -3 a 3 G.
- G longitudinal: gauge, rango -3 a 3 G.
- Yaw rate: chart, rango -300 a 300 °/s.
- RSSI LoRa: gauge, rango -120 a -20 dBm.
- SNR: gauge, rango -20 a 20 dB.
- Paquetes perdidos: text o gauge.

## Función principal

Ver `node-red/functions/parse_telemetria.js`.
