# Plan de pruebas

## Prueba 1: mesa quieta

Duración: 5 minutos.

Registrar:

- RSSI promedio.
- SNR promedio.
- Paquetes perdidos.
- Roll y pitch estables.
- Reinicios del emisor, si ocurren.

Criterio de éxito:

```text
lost bajo o cero, RSSI estable, SNR positivo, sin reinicios.
```

## Prueba 2: movimiento manual

Acciones:

- Inclinar lateralmente: debe cambiar roll.
- Inclinar adelante/atrás: debe cambiar pitch.
- Girar la caja: debe cambiar yaw_rate.
- Mover lateralmente: debe cambiar g_lat.
- Mover longitudinalmente: debe cambiar g_lon.

## Prueba 3: alcance LoRa

Distancias sugeridas:

- 5 m
- 20 m
- 50 m
- 100 m

Registrar RSSI, SNR, paquetes perdidos y estabilidad de enlace.
