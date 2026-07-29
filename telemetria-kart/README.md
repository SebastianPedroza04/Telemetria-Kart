# Telemetría Kart

Sistema de telemetría para kart con **ESP32, BMI160, GPS L86, LoRa, microSD,
Node-RED y Python**.

El proyecto mide las variables dinámicas del kart 100 veces por segundo, las
guarda a bordo en una tarjeta microSD, transmite un resumen por LoRa a una
estación base para verlo en vivo, y permite analizar todo después con scripts de
Python.

Proyecto de la asignatura Sensores y Actuadores, Universidad Nacional de Colombia.

**Equipo:** Marbel Alexandra Garavito Cordero, Andrés Felipe Osorio Ortiz,
Sebastián Ramiro Pedroza Garnica.

---

## 1. Qué hace el sistema

El sistema trabaja con dos unidades.

### Unidad del kart

La ESP32 del kart:

- Lee la IMU BMI160 a 100 Hz por acceso directo a registros.
- Aplica calibración de acelerómetro (offset y sensibilidad) y giroscopio (bias).
- Calcula `roll` y `pitch` con filtro de Kalman embebido.
- Lee el GPS L86 a 10 Hz.
- Guarda todas las muestras en la microSD, un archivo por encendido.
- Envía por LoRa un paquete resumido a la estación base.

### Unidad base

La ESP32 base:

- Recibe los paquetes LoRa.
- Calcula RSSI, SNR, paquetes recibidos y paquetes perdidos.
- Envía los datos por USB Serial al computador.

### Computador

El computador:

- Visualiza en vivo con Node-RED, con la aplicación en Python o a través de un
  puente MQTT, según convenga.
- Guarda un CSV local de la sesión recibida por LoRa.
- Analiza después los CSV (de LoRa y de la microSD) con scripts de Python.

La idea de fondo: **la microSD es la fuente de verdad y la radio es la vitrina.**
Por LoRa no caben 100 Hz a la distancia de la pista, así que el análisis fino se
hace con los archivos de la tarjeta y la radio sirve para supervisar en vivo.

---

## 2. Estado actual

### Funciona

- BMI160 leyendo a 100 Hz reales, sin pérdida de muestras.
- Caracterización completa del sensor: reposo (4 corridas de 10 min), prueba de
  seis posiciones, deriva de 45 min y espectro de vibración.
- Calibración aplicada en firmware con constantes medidas por nosotros.
- Filtro de Kalman para `roll` y `pitch`, validado contra el de Python
  (error RMS de 0.11°).
- GPS L86 con fix real (11 satélites, HDOP 0.95 en la validación).
- Enlace LoRa funcionando en SF9.
- **microSD funcionando**: graba a 100 Hz mientras el LoRa transmite, sin perder
  muestras.
- Node-RED recibe por Serial, dashboard y gráficas en vivo.
- Aplicación de visualización en Python, alternativa a Node-RED.
- Guardado de CSV desde Node-RED y desde los scripts.
- Prueba de campo con el kart en movimiento realizada.
- Scripts de caracterización y de análisis de sesión.

> **Nota sobre la microSD.** Durante un tiempo el módulo no inicializaba aunque
> la tarjeta estuviera en FAT32 y el cableado fuera correcto. Al final resultó
> ser una **tarjeta defectuosa**: con otra microSD de 16 GB el mismo módulo
> DFR0229 funcionó sin cambiar nada más. Si alguien repite el montaje y ve
> `SD FALLA`, lo primero que conviene probar es otra tarjeta antes de revisar
> conexiones. El otro detalle es que el DFR0229 se alimenta a **5 V**, no a 3.3 V
> como el resto de los módulos.

### Falta

- Hacer el cero de montaje de la IMU cuando la caja quede fija en el kart. En las
  pruebas el sensor quedó invertido y por eso el `roll` aparece cerca de 180°.
  Los datos son válidos, pero conviene alinear los ejes con los del vehículo.
- Mejorar la ubicación de la antena GPS. En la prueba con el kart solo hubo fix
  el 41 % del tiempo, lo que impidió reconstruir bien la trayectoria de esa toma.
- Unificar el firmware (ver sección 7).

---

## 3. Flujo de datos

```text
BMI160 + GPS L86
        ↓
   ESP32 del kart
        ↓
 Kalman + calibración
        ↓
   ┌────┴────┐
   ↓         ↓
microSD    LoRa SF9
100 Hz     1–2 Hz
   ↓         ↓
 análisis  ESP32 base
 offline     ↓
          USB Serial
             ↓
      ┌──────┴──────┐
      ↓             ↓
  Node-RED    puente MQTT
  o Python    (Mosquitto)
      ↓             ↓
  dashboard   suscriptor + CSV
```

Del lado del computador hay dos formas de consumir los datos: leer el serial
directamente (Node-RED o la aplicación en Python) o pasarlos por un broker MQTT
local. Las dos funcionan; solo no pueden usarse al mismo tiempo porque el puerto
COM admite un solo programa.

Las dos ramas comparten el mismo contador `seq`, así que se pueden alinear
muestra a muestra para comparar lo grabado a bordo con lo que llegó por radio.

---

## 4. Formato de los datos

### 4.1 Lo que entrega la base por Serial (viene del LoRa)

```csv
seq,t_ms,roll,pitch,g_lat,g_lon,yaw_rate,lat,lon,gps_speed_mps,gps_course_deg,gps_sats,gps_hdop,gps_fix,rssi,snr,lost,total
```

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

### 4.2 Lo que guarda la microSD

Archivos `KART001.CSV`, `KART002.CSV`, … uno por cada encendido:

```csv
seq,t_us,ax,ay,az,gx,gy,gz,roll,pitch,g_lat,g_lon,yaw_rate,lat,lon,gps_spd,sats,gps_fix
```

Aquí sí van las aceleraciones y giros crudos calibrados (`ax`…`gz`), que por
LoRa no se transmiten para no saturar el enlace.

Un detalle práctico: el ESP32 no tiene reloj, así que **todos los archivos
aparecen con fecha de 1980**. Para saber cuál es cuál hay que usar el número de
archivo, el tamaño o correr `inspeccionar.py` (sección 9.4). Conviene anotar en
papel qué encendido corresponde a cada toma.

---

## 5. Hardware

### Unidad del kart

- ESP32.
- IMU BMI160.
- GPS L86.
- LoRa RA-01.
- Módulo microSD DFR0229 + tarjeta de 8–16 GB en FAT32.
- Powerbank o batería.
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

Dirección I2C usada: `0x68`

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
VCC       → 3V3
GND       → GND
TX GPS    → GPIO16
RX GPS    → GPIO17
V_BCKP    → 3V3
FORCE_ON  → 3V3
```

El pin `V_BCKP` **debe** estar alimentado o el módulo no arranca, aunque el LED
encienda. El manual de Quectel indica que se alimente al mismo tiempo o antes que
VCC. `FORCE_ON` a 3V3 evita que quede en modo de bajo consumo.

### microSD

```text
VCC   → 5V / VIN   (el DFR0229 es de 5 V, no de 3.3 V)
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

### Cuál usar

> En el repositorio hay dos líneas de firmware que **no son compatibles entre sí**
> porque el paquete LoRa es distinto. La versión oficial es
> `firmware/kart_final_imu_gps_lora_sd/` con
> `firmware/base_final_lora_serial_gps/`. Lo que está en `firmware/legacy/` se
> conserva solo como historial del desarrollo.

| | Versión oficial | `legacy/` |
|---|---|---|
| Paquete LoRa | 15 campos, **incluye GPS** | 13 campos, sin GPS |
| Salida de la base | 18 columnas | 17 columnas |
| Spreading factor | SF9 (~120 m) | SF7 |

Esto importa al analizar: los scripts que leen CSV de LoRa esperan uno u otro
formato. Los datos de la campaña del 24/07 se tomaron con la versión anterior.

### Firmware del kart

- Inicializa BMI160, GPS, LoRa y microSD.
- Lee la IMU a 100 Hz.
- Corrige offset, sensibilidad y bias con las constantes medidas.
- Calcula `roll` y `pitch` con Kalman.
- Calcula `g_lat`, `g_lon` y `yaw_rate`.
- Escribe cada muestra en la microSD.
- Envía el paquete de telemetría por LoRa.

Si la microSD falla al arrancar, el firmware **sigue funcionando** solo con LoRa,
para no perder la prueba.

Las constantes de calibración corresponden a *nuestra* unidad de BMI160. Con otro
sensor hay que repetir la caracterización (sección 9.1) y reemplazarlas.

### Firmware de la base

- Inicializa LoRa con los mismos parámetros del emisor.
- Recibe y filtra paquetes válidos (los que empiezan por `K,`).
- Calcula RSSI, SNR y paquetes perdidos por saltos de secuencia.
- Detecta si el emisor se reinició y reinicia los contadores.
- Imprime CSV por Serial USB.

Librerías necesarias: `LoRa` (Sandeep Mistry), `TinyGPSPlus`, `SD`.

---

## 8. Node-RED

Node-RED se usa para:

- Leer el puerto Serial de la ESP32 base.
- Convertir la línea CSV en objeto.
- Mostrar panel de datos y gráficas en vivo.
- Guardar la sesión en CSV local.

Archivo que se genera:

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

La guía completa de instalación está en `node-red/instalacion_uso_node_red.md`.

---

## 9. Scripts de Python

Los scripts están divididos por propósito. Solo un programa puede usar el puerto
COM a la vez, así que hay que cerrar Node-RED y el monitor serie de Arduino antes
de correr cualquier script que lea el serial.

---

### 9.1 Caracterización de la IMU

Sirven para estudiar y validar el BMI160. No son para la prueba en vivo, sino
para justificar la calibración y el comportamiento del sensor. Están en
`scripts/characterization/`.

#### `capturar_serial.py`

Captura datos crudos desde el Serial y los guarda en CSV. Es la base de todo lo
demás: cualquier prueba de caracterización empieza grabando con este script.

```bash
python capturar_serial.py COM3 --min 10 --nombre reposo
```

`--min` son los minutos de captura y `--nombre` el prefijo del archivo. Al
terminar informa la tasa efectiva conseguida, lo que sirve para detectar si se
perdieron muestras.

#### `estadistica_reposo.py`

Analiza una captura con el sensor quieto. Entrega media, varianza, desviación
estándar, offset del acelerómetro, bias del giroscopio, frecuencia real de
muestreo, jitter y huecos, más una gráfica.

Se usa para justificar que el sensor es estable y para obtener los valores de
ruido que después alimentan las matrices R y Q del filtro de Kalman.

```bash
python estadistica_reposo.py data/reposo_XXXX.csv
```

#### `seis_posiciones.py`

Caracteriza el acelerómetro con la IMU apoyada en sus seis caras. Detecta solo
qué eje quedó vertical en cada archivo, así que no hay que anotar el orden: basta
capturar un minuto por cara, como si fuera un dado.

Entrega offset y sensibilidad por eje, que son las constantes que van al
firmware. Avisa si alguna cara quedó inclinada o si falta alguna orientación.

```bash
python seis_posiciones.py data/pos_*.csv
```

#### `analizar_deriva.py`

Analiza la deriva del giroscopio en una captura larga en reposo. Muestra cómo
cambia el bias minuto a minuto y cuánto se desvía el ángulo integrado con y sin
corrección de bias.

Es el script que justifica por qué se calibra al arranque: en nuestra prueba de
45 minutos la deriva pasó de 11.76 °/min sin corregir a 0.31 °/min corregida.

```bash
python analizar_deriva.py data/deriva_XXXX.csv
```

#### `analizar_vibracion.py`

Compara dos capturas bajo vibración (por ejemplo montaje rígido contra montaje
sobre espuma) mediante densidad espectral de potencia, y calcula la atenuación
del aislamiento en dB.

En nuestro caso sirvió para descubrir que la espuma blanda **amplifica** la
vibración en lugar de atenuarla, por lo que el montaje en el kart quedó rígido.

```bash
python analizar_vibracion.py data/vib_directa.csv data/vib_espuma.csv
```

#### `kalman_offline.py`

Corre el filtro de Kalman en Python sobre un CSV grabado. Sirve para validar la
lógica del filtro antes de llevarlo al ESP32 y para ajustar el parámetro Q: con
la opción `--qscale` se puede hacer un barrido y comparar el efecto.

```bash
python kalman_offline.py data/mov_XXXX.csv
python kalman_offline.py data/mov_XXXX.csv --qscale 10
```

#### `comparar_kalman.py`

Compara el Kalman ejecutado en el ESP32 contra el de referencia en Python sobre
el mismo archivo. Demuestra que el filtro embebido entrega resultados
equivalentes al procesamiento offline. El criterio que usamos fue error RMS menor
a 0.5°.

```bash
python comparar_kalman.py data/kfv3_XXXX.csv
```

#### `trazada_gps.py`

Analiza un CSV del sketch de prueba del GPS y dibuja la trayectoria, la velocidad
y la calidad de la señal. Se usó para validar el GPS antes de integrarlo.

```bash
python trazada_gps.py data/gps_caminata_XXXX.csv
```

---

### 9.2 Análisis de sesión LoRa

Se usan después de una prueba con Node-RED. Están en `scripts/analysis/`.

#### `analisis_sesion_lora.py`

Lee `C:\TelemetriaKart\data\sesion_actual.csv` o el CSV que se le indique, y
entrega duración de la prueba, tasa LoRa real, RSSI promedio y mínimo, SNR,
paquetes perdidos, porcentaje de GPS fix, satélites promedio, HDOP y gráficas
PNG.

```bash
python analisis_sesion_lora.py C:\TelemetriaKart\data\sesion_actual.csv
```

---

### 9.3 Python en vivo, sin Node-RED

Está en `scripts/live/`.

#### `telemetria_live_python_OK.py`

Alternativa a Node-RED para ver la telemetría en vivo. Lee directamente el COM de
la ESP32 base, grafica en tiempo real con Matplotlib (orientación y giro,
dinámica, enlace LoRa y estado del GPS) y guarda un CSV local de la sesión.

Refresca cada 500 ms con una ventana de las últimas 240 muestras, tolera tramas
corruptas sin interrumpirse y muestra en el título el estado del GPS y del
enlace, lo que sirve para verificar todo antes de arrancar una tanda.

```bash
python telemetria_live_python_OK.py COM4
```

Si no se ven datos, con `--raw` imprime las líneas crudas del serial para
diagnosticar:

```bash
python telemetria_live_python_OK.py COM4 --raw
```

Node-RED y el monitor serie de Arduino deben estar cerrados.

---

### 9.4 Análisis de los archivos de la microSD

Están en `scripts/analysis/`. Trabajan con los `KARTxxx.CSV` de la tarjeta, que
tienen los 100 Hz completos.

#### `inspeccionar.py`

Es el primero que conviene correr. Hace un inventario de todos los `KART*.CSV`:
cuántas muestras tiene cada uno, cuánto duró, qué porcentaje tuvo GPS fijo,
cuántos metros se recorrieron y los picos de G y yaw.

Sirve para identificar cuál archivo corresponde a cada toma, ya que todos
aparecen con fecha de 1980. Los archivos con pocas muestras suelen ser arranques
o pruebas cortas; los que tienen movimiento y GPS son las tomas reales.

```bash
python inspeccionar.py D:\
```

#### `analizar_microsd_offline.py`

Analiza un archivo de la microSD: acelerómetro y giroscopio a 100 Hz, roll,
pitch, yaw rate, G lateral y longitudinal, GPS y frecuencia real de muestreo.

```bash
python analizar_microsd_offline.py C:\TelemetriaKart\data\microsd\KART000.CSV
```

#### `trazada_sd.py`

Dibuja la trayectoria a partir de las columnas GPS de uno o varios archivos de la
microSD, coloreada por velocidad, junto con las fuerzas G, el yaw rate y la
velocidad. Descarta automáticamente los puntos sin fix.

Acepta varios archivos o una carpeta completa, y los une en orden, que es útil
cuando una misma sesión quedó repartida en varios encendidos.

```bash
python trazada_sd.py KART020.CSV
python trazada_sd.py D:\
```

#### `comparar_tomas.py`

Superpone varias tomas para compararlas: trayectorias, G lateral, velocidad y el
diagrama G-G (aceleración lateral contra longitudinal), cada toma en un color.

El diagrama G-G es especialmente útil para ver la diferencia entre regímenes: las
tomas caminando quedan concentradas cerca del centro, mientras que la del kart
expande la envolvente hasta ±2 g.

```bash
python comparar_tomas.py KART019.CSV KART020.CSV KART023.CSV
```

#### `detectar_vueltas.py`

Separa las vueltas dentro de una toma. Primero recorta automáticamente el tramo
inicial en que el vehículo estaba quieto, y después detecta cada paso cerca del
punto de meta usando el GPS. Si el GPS no alcanza, permite forzar el número de
vueltas con `--nvueltas`.

Entrega una tabla con la duración y los picos de cada vuelta, y las grafica
superpuestas con el tiempo normalizado para poder compararlas.

```bash
python detectar_vueltas.py KART023.CSV
python detectar_vueltas.py KART023.CSV --nvueltas 4
```

Requiere buena cobertura GPS para funcionar bien. Con poca disponibilidad de fix
las vueltas detectadas no son confiables.

#### `comparar_sd_lora.py`

Compara la grabación a bordo con la telemetría que llegó por radio en la misma
sesión, alineando ambas fuentes por el contador `seq`.

Sirve para dos cosas: comprobar que lo que se ve en vivo coincide con lo grabado,
y medir cuánta información se pierde al transmitir a menor frecuencia. En nuestra
prueba, con 100 Hz en la SD contra 1.04 Hz por LoRa, se conservó el 97 % del pico
de roll pero solo el 61 % del pico de aceleración lateral.

```bash
python comparar_sd_lora.py KART023.CSV data/lora/lora_XXXX.csv
```

---

### 9.5 Fusión IMU + GPS

#### `fusion_imu_gps_kalman_offline.py`

Corrige la deriva de posición y velocidad fusionando IMU y GPS con un filtro tipo
Kalman. Requiere un CSV de microSD a 100 Hz.

No debe usarse con el CSV de LoRa, porque ese solo tiene datos resumidos a
1–2 Hz.

```bash
python fusion_imu_gps_kalman_offline.py data/microsd/KART000.CSV
```

Genera la trayectoria GPS cruda, la trayectoria fusionada y un CSV fusionado.
Corrige deriva de posición y velocidad; no corrige directamente roll ni pitch,
porque de eso ya se encarga el Kalman del acelerómetro.

---

### 9.6 Scripts MQTT

Conviene aclarar algo, porque "MQTT" aparece en dos momentos distintos del
proyecto y significan cosas diferentes.

**Como enlace inalámbrico: se abandonó.** En la primera etapa el ESP32 del kart
publicaba directamente por WiFi a un broker Mosquitto. Eso quedó atrás al pasar a
LoRa, porque el WiFi no cubría la pista.

**Como bus de datos en el computador: se sigue usando.** El receptor LoRa entrega
los datos por USB, y de ahí en adelante hay dos caminos posibles: Node-RED, o el
puente MQTT. Con el puente, los datos quedan publicados en un broker local y
cualquier programa puede suscribirse: el suscriptor que registra el CSV, un
dashboard, o los dos a la vez. Los archivos `lora_*.csv` de la campaña del 24/07
se generaron por esta vía.

Los scripts están en `scripts/legacy_mqtt/` (el nombre de la carpeta viene de la
primera etapa, aunque sigan siendo funcionales).

#### `puente_serial_mqtt.py`

Lee el serial del receptor LoRa, publica cada trama en los tópicos
`kart/K01/imu/filt` (los datos del kart) y `kart/K01/radio` (RSSI, SNR y
pérdidas), y guarda además un CSV de respaldo con la hora de recepción.

```bash
python puente_serial_mqtt.py COM3
```

Requiere que el broker Mosquitto esté corriendo antes:

```bash
mosquitto.exe -c kart.conf -v
```

El archivo `kart.conf` solo necesita dos líneas para aceptar conexiones que no
sean del propio computador:

```text
listener 1883
allow_anonymous true
```

#### `suscriptor_mqtt.py`

Se suscribe a los tópicos, registra lo recibido en CSV y mide la pérdida de
paquetes a partir del contador de secuencia.

```bash
python suscriptor_mqtt.py
```

**Cuál usar.** Para una prueba rápida, Node-RED o la aplicación en Python son más
directos. El puente MQTT tiene sentido cuando se quiere que varios programas
consuman los mismos datos al tiempo, o cuando interesa dejar el registro corriendo
aparte del dashboard. Los dos caminos son válidos; lo único que no se puede es
usarlos a la vez, porque el puerto COM solo admite un programa.

---

## 10. Metodología de prueba

### Prueba con Node-RED

1. Borrar el CSV anterior si hace falta:

```bash
del C:\TelemetriaKart\data\sesion_actual.csv
```

2. Encender emisor y receptor.
3. Abrir Node-RED con el monitor serie de Arduino cerrado.
4. Verificar GPS fix, RSSI y SNR antes de arrancar.
5. Hacer la prueba.
6. Guardar video o capturas.
7. Analizar el CSV con Python.

### Prueba con Python en vivo

1. Cerrar Node-RED y el monitor serie.
2. Correr `telemetria_live_python_OK.py COM4`.
3. Observar las gráficas.
4. Guardar el CSV generado.

### Prueba con microSD

1. Conectar la batería con el kart **quieto y nivelado**: el Kalman toma el
   ángulo inicial en ese momento.
2. Confirmar en el monitor que aparece `SD OK -> /KARTxxx.CSV` y que el GPS
   llegue a `fix=1`.
3. Hacer la prueba. Anotar en papel qué número de archivo corresponde.
4. Esperar un par de segundos quieto antes de cortar la energía, para que
   termine de escribirse el archivo.
5. Copiar los `KARTxxx.CSV` al computador.
6. Correr `inspeccionar.py` para identificarlos y después los análisis.

Conviene hacer una vuelta corta de prueba primero, revisar que el CSV tenga
datos buenos, y solo entonces hacer las tandas largas.

---

## 11. Resultados obtenidos

### Caracterización del sensor

| Medida | Resultado |
|---|---|
| Ruido del acelerómetro (σ) | 0.010–0.013 m/s² |
| Ruido del giroscopio (σ) | 0.045–0.059 °/s |
| Offset del acelerómetro | +0.319, −0.236, −0.471 m/s² (x, y, z) |
| Sensibilidad | 1.0041, 0.9931, 0.9969 |
| Bias del giroscopio | −0.065, +0.194, −0.086 °/s |
| Deriva sin corregir | hasta 11.76 °/min |
| Deriva corregida | 0.24–0.51 °/min |
| Error del Kalman embebido vs referencia | 0.11° RMS |

De ahí salieron los parámetros del filtro: R = 0.004 (°)² y
Q_θ = 2.5×10⁻⁵ (°)², ambos derivados de las mediciones y no de valores tomados
de la literatura.

### Campaña de campo del 24 de julio

Tres tomas, la última con el kart en movimiento:

| Archivo | Qué fue | Duración | GPS fix | G lat. máx |
|---|---|---|---|---|
| KART019 | recorrido de la pista caminando | 315 s | 65 % | 0.95 g |
| KART020 | extremo de la pista | 203 s | 99 % | 0.90 g |
| KART023 | **kart en movimiento** | 355 s | 41 % | **1.64 g** |

En la toma con el kart se alcanzaron 1.64 g laterales, −1.5 g en frenada y
135 °/s de guiñada, con velocidad GPS de hasta 6.5 m/s.

### Registro a bordo contra telemetría por radio

Comparando la misma sesión con las dos fuentes alineadas por `seq`:

| Variable | Pico en la SD | Pico visto por LoRa | Se conserva |
|---|---|---|---|
| Roll | 208.7° | 203.1° | 97 % |
| Yaw rate | 134.9 °/s | 99.5 °/s | 74 % |
| G lateral | 1.64 g | 0.99 g | 61 % |

Las variables lentas se ven casi igual por radio, pero los picos rápidos se
pierden. Es la razón práctica de mantener el registro a bordo como fuente de los
datos que se analizan.

Las figuras están en `docs/figuras/` y el informe completo en `docs/informe/`.

---

## 12. Interpretación de resultados

### LoRa

- RSSI menos negativo indica señal más fuerte.
- SNR positivo indica enlace estable.
- Paquetes perdidos bajos indican buena transmisión.
- Si `lost` se dispara a valores enormes, normalmente es porque el emisor se
  reinició y el contador de secuencia saltó. Se resuelve reiniciando el receptor
  con el emisor ya encendido.

### GPS

- `gps_fix = 1` indica coordenadas válidas.
- Más satélites mejora la estabilidad.
- HDOP más bajo indica mejor geometría satelital.
- En reposo la trayectoria puede moverse por ruido; no debe interpretarse como
  movimiento real.

### IMU

- `roll` y `pitch` describen la orientación.
- `g_lat` responde a las curvas.
- `g_lon` responde a aceleración y frenada.
- `yaw_rate` responde al giro.
- Si en reposo no están cerca de cero, falta el cero de montaje.

---

## 13. Estructura del repositorio

```text
telemetria-kart/
├── firmware/
│   ├── kart_final_imu_gps_lora_sd/    <- nodo del kart (oficial)
│   ├── base_final_lora_serial_gps/    <- estación base (oficial)
│   └── legacy/                        <- versiones anteriores
├── Firmware-PlatformIO/               <- mismo firmware en PlatformIO
├── node-red/
│   ├── flows/                         <- dashboards para importar
│   ├── functions/                     <- funciones de parseo
│   └── instalacion_uso_node_red.md
├── scripts/
│   ├── characterization/              <- caracterización del sensor
│   ├── analysis/                      <- análisis de sesiones y microSD
│   ├── live/                          <- visualización en vivo
│   └── legacy_mqtt/                   <- puente MQTT (etapa anterior)
├── data/
│   └── campo_20260724/                <- campaña de campo con el kart
├── docs/
│   ├── figuras/                       <- gráficas de resultados
│   └── informe/                       <- informe en LaTeX
├── hardware/                          <- lista de materiales
└── archive/                           <- sketches y datos de las primeras etapas
```

---

## 14. Resumen de uso

Para la entrega actual el flujo es:

```text
microSD                      → datos completos a 100 Hz para el análisis
Node-RED / Python / MQTT     → visualización en vivo y CSV de respaldo
Python                       → caracterización, análisis de sesión y gráficas
```

La microSD es la fuente de los datos que se analizan; la radio sirve para
supervisar en vivo y para demostrar el funcionamiento del enlace.
