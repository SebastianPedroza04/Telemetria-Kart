# Telemetría Kart

Sistema de telemetría para kart con **ESP32, BMI160, GPS L86, LoRa, Node-RED y Python**.

El proyecto permite medir variables dinámicas del kart, transmitirlas inalámbricamente por LoRa, visualizarlas en vivo y analizarlas después con scripts de Python.

---

## 1. Qué hace el sistema

El sistema trabaja con dos unidades:

### Unidad del kart

La ESP32 del kart:

- Lee la IMU BMI160.
- Aplica calibración del acelerómetro y giroscopio.
- Calcula `roll` y `pitch` con filtro de Kalman.
- Lee el GPS L86.
- Envía por LoRa un paquete resumido a la estación base.
- Conserva código para guardar en microSD a 100 Hz cuando el módulo SD sea reemplazado.

### Unidad base

La ESP32 base:

- Recibe los paquetes LoRa.
- Calcula RSSI, SNR, paquetes recibidos y paquetes perdidos.
- Envía los datos por USB Serial al computador.

### Computador

El computador:

- Usa Node-RED para visualizar datos en vivo.
- Guarda un CSV local de la sesión recibida por LoRa.
- Usa Python para analizar el CSV y generar gráficas.

---

## 2. Estado actual

### Funciona

- BMI160 detectada y leyendo datos.
- Calibración de IMU aplicada en firmware.
- Filtro de Kalman para `roll` y `pitch`.
- GPS L86 con fix real.
- Enlace LoRa funcionando en SF9.
- Node-RED recibe datos por Serial.
- Dashboard en vivo funcionando.
- Gráficas en vivo funcionando.
- Guardado CSV desde Node-RED.
- Análisis Python del CSV de LoRa.
- Scripts de caracterización disponibles.

### Falta

- Cambiar o validar el módulo microSD, porque el módulo actual no inicializó aunque la tarjeta estaba en FAT32.
- Hacer cero de montaje de la IMU cuando la caja quede instalada en el kart.
- Hacer prueba de movimiento real.
- Ejecutar análisis de microSD cuando exista CSV real a 100 Hz.
- Ejecutar fusión IMU + GPS cuando exista CSV de microSD.

---

## 3. Flujo de datos final

```text
BMI160 + GPS
     ↓
ESP32 del kart
     ↓
Kalman + calibración
     ↓
LoRa SF9
     ↓
ESP32 base
     ↓
USB Serial
     ↓
Node-RED
     ↓
CSV local + dashboard
     ↓
Python
```

La microSD queda prevista para este flujo:

```text
ESP32 del kart → microSD → CSV IMU + GPS a 100 Hz
```

---

## 4. Formato de datos recibido por Node-RED

La ESP32 base entrega por Serial:

```csv
seq,t_ms,roll,pitch,g_lat,g_lon,yaw_rate,lat,lon,gps_speed_mps,gps_course_deg,gps_sats,gps_hdop,gps_fix,rssi,snr,lost,total
```

Significado:

| Campo | Uso |
|---|---|
| `seq` | número de paquete LoRa |
| `t_ms` | tiempo del emisor en milisegundos |
| `roll` | inclinación lateral estimada |
| `pitch` | inclinación longitudinal estimada |
| `g_lat` | aceleración lateral en G |
| `g_lon` | aceleración longitudinal en G |
| `yaw_rate` | velocidad angular de giro |
| `lat` | latitud GPS |
| `lon` | longitud GPS |
| `gps_speed_mps` | velocidad GPS en m/s |
| `gps_course_deg` | rumbo GPS en grados |
| `gps_sats` | satélites usados |
| `gps_hdop` | indicador de precisión GPS |
| `gps_fix` | 1 si hay fix, 0 si no |
| `rssi` | potencia recibida LoRa |
| `snr` | relación señal-ruido LoRa |
| `lost` | paquetes perdidos acumulados |
| `total` | paquetes recibidos |

---

## 5. Hardware

### Unidad del kart

- ESP32.
- IMU BMI160.
- GPS L86.
- LoRa RA-01.
- Módulo microSD pendiente por reemplazar.
- Powerbank.
- Caja o soporte rígido.

### Unidad base

- ESP32.
- LoRa RA-01.
- Cable USB al computador.

---

## 6. Conexiones

### BMI160

```text
VCC  → 3V3
GND  → GND
SDA  → GPIO21
SCL  → GPIO22
CSB  → 3V3
SDO  → GND
```

Dirección I2C usada:

```text
0x68
```

### LoRa RA-01

```text
VCC   → 3V3
GND   → GND
SCK   → GPIO18
MISO  → GPIO19
MOSI  → GPIO23
NSS   → GPIO5
RST   → GPIO14
DIO0  → GPIO26
```

Importante:

```text
No alimentar LoRa con 5 V.
No transmitir sin antena.
```

### GPS L86

```text
VCC     → 3V3
GND     → GND
TX GPS  → GPIO16
RX GPS  → GPIO17
V_BCKP  → 3V3
```

### microSD prevista

```text
VCC   → 3V3
GND   → GND
SCK   → GPIO18
MISO  → GPIO19
MOSI  → GPIO23
CS    → GPIO13
```

La microSD comparte SPI con LoRa, pero usa otro CS:

```text
LoRa NSS = GPIO5
SD CS    = GPIO13
```

---

## 7. Firmware

### Firmware del kart

Usar el sketch final del kart.

Hace:

- Inicializa BMI160.
- Inicializa GPS.
- Inicializa LoRa.
- Intenta inicializar microSD.
- Lee IMU.
- Corrige offset, sensibilidad y bias.
- Calcula `roll` y `pitch` con Kalman.
- Calcula `g_lat`, `g_lon` y `yaw_rate`.
- Envía por LoRa el paquete de telemetría.
- Conserva la lógica de guardado a microSD.

### Firmware de la base

Usar el sketch final de la base.

Hace:

- Inicializa LoRa.
- Recibe paquetes del kart.
- Filtra paquetes válidos.
- Calcula RSSI y SNR.
- Calcula paquetes perdidos.
- Imprime CSV por Serial USB.

---

## 8. Node-RED

Node-RED se usa para:

- Leer el puerto Serial de la ESP32 base.
- Convertir la línea CSV en objeto.
- Mostrar panel de datos.
- Mostrar gráficas en vivo.
- Guardar la sesión en CSV local.

Archivo local que se genera:

```text
C:\TelemetriaKart\data\sesion_actual.csv
```

### Uso

1. Cerrar Arduino Serial Monitor.
2. Encender emisor y receptor.
3. Abrir Node-RED.
4. Verificar que el nodo serial use el COM correcto.
5. Presionar `Instanciar`.
6. Revisar el dashboard.
7. Confirmar que se crea `sesion_actual.csv`.

---

## 9. Scripts de Python

Los scripts se dividen por propósito.

---

### 9.1 Scripts de caracterización de IMU

Estos scripts se usan para estudiar y validar el BMI160. No son para la prueba final en vivo, sino para justificar la calibración y el comportamiento del sensor.

#### `capturar_serial.py`

Sirve para capturar datos crudos desde el Serial y guardarlos en CSV.

Uso típico:

```bash
python capturar_serial.py COM4
```

Se usa cuando se quiere registrar datos del sensor directamente desde el firmware de pruebas.

---

#### `estadistica_reposo.py`

Sirve para analizar el sensor quieto.

Permite obtener:

- media,
- desviación estándar,
- ruido,
- valores promedio de acelerómetro y giroscopio.

Se usa para justificar que el sensor es estable en reposo.

---

#### `seis_posiciones.py`

Sirve para caracterizar el acelerómetro poniendo la IMU en seis orientaciones.

Permite estimar:

- offset por eje,
- sensibilidad por eje,
- error respecto a la gravedad.

Se usa para obtener constantes de calibración del acelerómetro.

---

#### `analizar_deriva.py`

Sirve para analizar la deriva del giroscopio durante una prueba larga en reposo.

Permite justificar el bias del giroscopio y mostrar por qué se requiere corrección.

---

#### `analizar_vibracion.py`

Sirve para analizar vibraciones del sistema.

Permite revisar contenido de frecuencia y detectar si el montaje mecánico introduce vibraciones fuertes.

---

#### `kalman_offline.py`

Sirve para probar el filtro de Kalman en Python antes de llevarlo al ESP32.

Se usa para validar la lógica del filtro con datos guardados.

---

#### `comparar_kalman.py`

Sirve para comparar el Kalman ejecutado en el ESP32 contra el Kalman de referencia en Python.

Se usa para demostrar que el filtro embebido entrega resultados equivalentes al procesamiento offline.

---

#### `trazada_gps.py`

Sirve para analizar puntos GPS guardados en CSV y dibujar una trayectoria.

Se usa para revisar si la señal GPS permite reconstruir una ruta aproximada.

---

### 9.2 Scripts de análisis de sesión LoRa

Estos scripts se usan después de una prueba con Node-RED.

#### `analisis_sesion_lora.py`

Lee:

```text
C:\TelemetriaKart\data\sesion_actual.csv
```

o un CSV indicado por el usuario.

Genera:

- duración de la prueba,
- tasa LoRa real,
- RSSI promedio y mínimo,
- SNR promedio y mínimo,
- paquetes perdidos,
- porcentaje de GPS fix,
- satélites promedio,
- HDOP promedio,
- gráficas PNG.

Uso:

```bash
python C:\TelemetriaKart\scripts\analysis\analisis_sesion_lora.py C:\TelemetriaKart\data\sesion_actual.csv
```

---

### 9.3 Python en vivo sin Node-RED

#### `telemetria_live_python_OK.py`

Sirve para hacer una prueba sin Node-RED.

Hace:

- lee directamente el COM de la ESP32 base,
- grafica en vivo con Matplotlib,
- guarda un CSV local.

Importante:

```text
Node-RED debe estar cerrado.
Arduino Serial Monitor debe estar cerrado.
```

Uso:

```bash
python C:\TelemetriaKart\scripts\live\telemetria_live_python_OK.py COM4
```

Si no se ven datos:

```bash
python C:\TelemetriaKart\scripts\live\telemetria_live_python_OK.py COM4 --raw
```

---

### 9.4 Scripts de microSD

Estos scripts están preparados para cuando el módulo microSD funcione.

#### `analizar_microsd_offline.py`

Lee un archivo como:

```text
C:\TelemetriaKart\data\microsd\KART000.CSV
```

Analiza:

- acelerómetro a 100 Hz,
- giroscopio a 100 Hz,
- roll,
- pitch,
- yaw rate,
- G lateral,
- G longitudinal,
- GPS,
- frecuencia real de muestreo.

Uso:

```bash
python C:\TelemetriaKart\scripts\analysis\analizar_microsd_offline.py C:\TelemetriaKart\data\microsd\KART000.CSV
```

---

### 9.5 Fusión IMU + GPS

#### `fusion_imu_gps_kalman_offline.py`

Este script corrige drift de posición y velocidad usando una fusión IMU + GPS tipo Kalman.

Requiere CSV de microSD a 100 Hz.

No debe usarse con el CSV LoRa de Node-RED, porque ese CSV solo tiene datos resumidos a 2 Hz.

Uso:

```bash
python C:\TelemetriaKart\scripts\analysis\fusion_imu_gps_kalman_offline.py C:\TelemetriaKart\data\microsd\KART000.CSV
```

Genera:

- trayectoria GPS cruda,
- trayectoria fusionada,
- CSV fusionado.

Importante:

```text
Corrige drift de posición y velocidad.
No corrige directamente roll ni pitch.
```

---

### 9.6 Scripts MQTT

Estos scripts quedan como antecedente histórico.

#### `puente_serial_mqtt.py`

Sirve para tomar datos seriales y publicarlos por MQTT.

#### `suscriptor_mqtt.py`

Sirve para suscribirse a un tópico MQTT y recibir datos.

La versión final del proyecto no usa MQTT. La versión final usa:

```text
LoRa → ESP32 base → Serial USB → Node-RED
```

---

## 10. Metodología de prueba

### Prueba con Node-RED

1. Borrar CSV anterior:

```bash
del C:\TelemetriaKart\data\sesion_actual.csv
```

2. Encender emisor y receptor.
3. Abrir Node-RED.
4. Cerrar Arduino Serial Monitor.
5. Verificar GPS fix, RSSI y SNR.
6. Hacer la prueba.
7. Guardar video o capturas.
8. Analizar el CSV con Python.

---

### Prueba con Python en vivo

1. Cerrar Node-RED.
2. Cerrar Arduino Serial Monitor.
3. Correr:

```bash
python C:\TelemetriaKart\scripts\live\telemetria_live_python_OK.py COM4
```

4. Observar gráficas.
5. Guardar el CSV generado.

---

### Prueba futura con microSD

1. Instalar módulo microSD funcional.
2. Confirmar que el firmware diga:

```text
SD OK. Guardando en /KART000.CSV
```

3. Hacer prueba física.
4. Copiar `KART000.CSV` a:

```text
C:\TelemetriaKart\data\microsd\
```

5. Ejecutar análisis microSD.
6. Ejecutar fusión IMU + GPS.

---

## 11. Interpretación de resultados

### LoRa

- RSSI menos negativo indica señal más fuerte.
- SNR positivo indica enlace estable.
- Paquetes perdidos bajos indican buena transmisión.

### GPS

- `gps_fix = 1` indica coordenadas válidas.
- Más satélites mejora la estabilidad.
- HDOP más bajo indica mejor geometría satelital.
- En reposo, la trayectoria puede moverse por ruido GPS; no debe interpretarse como movimiento real.

### IMU

- `roll` y `pitch` describen orientación.
- `g_lat` responde a curvas.
- `g_lon` responde a aceleración y frenada.
- `yaw_rate` responde a giro.
- Si en reposo no está cerca de cero, falta cero de montaje.

---

## 12. Conclusión de uso

Para la entrega actual, el flujo principal es:

```text
Node-RED para visualizar y guardar CSV.
Python para analizar el CSV.
microSD y fusión IMU + GPS como etapa preparada para cuando el módulo SD funcione.
```
