# Estado actual del proyecto

## Funcionando

- Lectura BMI160 en ESP32.
- Comunicación LoRa entre ESP32 emisora y ESP32 base.
- Recepción serial en Node-RED.
- Dashboard funcional con gráficos y medidores.
- Kalman embebido para roll/pitch.
- Medición de RSSI, SNR y paquetes perdidos.

## Observaciones actuales

- La IMU está montada invertida; por eso `az` puede aparecer cerca de `-9.81` y `roll` cerca de `180°`.
- Esto no impide probar telemetría, pero conviene corregirlo por software o montaje físico antes de la presentación final.
- El GPS se deja como pendiente porque ha sido inestable para obtener fix satelital.
- La microSD todavía no se puede probar porque falta comprar la tarjeta.
- La alimentación del LoRa puede requerir regulador 3.3 V externo o MB102, siempre con tierra común con la ESP32.

## Evidencia para documentar

Guardar en `evidence/dashboard/`:

- Capturas del dashboard.
- Fotos del montaje.
- Capturas del Serial Monitor.
- Videos cortos de movimiento manual.
