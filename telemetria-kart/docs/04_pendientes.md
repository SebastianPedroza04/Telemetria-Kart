# Pendientes

## Hardware

- [ ] Comprar microSD.
- [ ] Probar módulo microSD.
- [ ] Decidir alimentación final del LoRa: 3V3 de ESP32, MB102 o regulador 3.3 V externo.
- [ ] Fijar IMU de forma rígida.
- [ ] Montar caja plástica.
- [ ] Ubicar antena LoRa lejos de masas metálicas.

## Firmware

- [ ] Cargar versión final emisor LoRa + Kalman.
- [ ] Cargar versión receptor LoRa + Serial.
- [ ] Activar logging microSD cuando se compre la tarjeta.
- [ ] Ajustar orientación de IMU para que en reposo: ax≈0, ay≈0, az≈+9.81, roll≈0, pitch≈0.

## IMU

- [ ] Calibrar a cero con montaje final.
- [ ] Repetir reposo limpio.
- [ ] Hacer seis posiciones.
- [ ] Medir deriva de giroscopio.
- [ ] Caracterización dinámica/vibración.

## GPS

- [ ] Dejar como integración secundaria.
- [ ] Reintentar solo si el sistema base queda completo.
- [ ] Probar cielo abierto real.
- [ ] Validar UART y NMEA.

## Node-RED

- [ ] Mejorar nombres de página/grupo.
- [ ] Separar dashboard por secciones: enlace, actitud, dinámica y diagnóstico.
- [ ] Ajustar colores/rangos.
- [ ] Agregar indicadores de conexión y paquetes perdidos.

## Pruebas

- [ ] Prueba de mesa 5 min.
- [ ] Prueba de movimiento manual.
- [ ] Prueba de alcance LoRa.
- [ ] Prueba caminando.
- [ ] Prueba bicicleta/carro lento.
- [ ] Prueba kart.
