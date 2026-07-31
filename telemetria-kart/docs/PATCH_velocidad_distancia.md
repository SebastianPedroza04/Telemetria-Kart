# Agregar velocidad y distancia al firmware

Cómo transmitir la velocidad fusionada y la distancia recorrida dentro del
paquete LoRa, para verlas en vivo en Node-RED sin depender de scripts en el PC.

Son cinco cambios en el emisor, uno en el receptor y la actualización de los
consumidores. El receptor casi no se toca porque reenvía el paquete tal como
llega.

---

## Qué se agrega y por qué

La aceleración ya se transmite (`g_lon`) y la velocidad del GPS también
(`gps_speed_mps`). Lo que falta es:

- **Velocidad fusionada:** el GPS entrega velocidad a 5 Hz y con saltos; el
  acelerómetro es continuo pero se desvía. Un filtro de Kalman los combina y
  entrega una velocidad suave y sin deriva.
- **Distancia recorrida:** es la integral de esa velocidad.

El filtro de velocidad es el mismo esquema del de ángulo, cambiando las
variables:

```
estado:      x = [v, b_a]        v = velocidad, b_a = bias del acelerómetro
predicción:  v ← v + (a_long − b_a) · dt      con el acelerómetro, a 100 Hz
corrección:  con la velocidad del GPS, cuando llega una lectura nueva con fix
distancia:   d ← d + v · dt
```

---

## Emisor: `kart_final_imu_gps_lora_sd.ino`

### Cambio 1 — Agregar la clase del filtro

Justo después de `KalmanAngle kalmanRoll, kalmanPitch;`, pegar:

```cpp
// -------------------- Kalman de velocidad --------------------
// Predice con la aceleración longitudinal y corrige con la velocidad del GPS.
// Estima además el bias residual del acelerómetro, que es lo que hace que
// integrar la aceleración sola termine desviándose.
class KalmanVelocidad {
public:
  float v = 0.0, bias = 0.0;
  float P00 = 1.0, P01 = 0.0, P10 = 0.0, P11 = 0.1;

  const float R_GPS   = 0.04;   // (0.2 m/s)^2 : ruido de la velocidad GPS
  const float SIG_ACC = 0.05;   // m/s^2       : ruido del acelerómetro medido
  const float Q_BIAS  = 1e-6;

  void predecir(float aLong, float dt) {
    v = v + (aLong - bias) * dt;

    float Qv = SIG_ACC * SIG_ACC * dt;
    float a = P00, b = P01, c = P10, d = P11;

    P00 = a + dt * (dt * d - b - c) + Qv;
    P01 = b - dt * d;
    P10 = c - dt * d;
    P11 = d + Q_BIAS * dt;
  }

  void corregir(float vGps) {
    float S  = P00 + R_GPS;
    float K0 = P00 / S;
    float K1 = P10 / S;
    float r  = vGps - v;

    v    = v + K0 * r;
    bias = bias + K1 * r;

    float p00 = P00, p01 = P01;
    P00 = P00 - K0 * p00;
    P01 = P01 - K0 * p01;
    P10 = P10 - K1 * p00;
    P11 = P11 - K1 * p01;
  }
};

KalmanVelocidad kalmanVel;

float velKf = 0.0;    // velocidad fusionada [m/s]
float distM = 0.0;    // distancia recorrida [m]
```

### Cambio 2 — Calcular velocidad y distancia en cada muestra

En `updateIMU()`, después de la línea `gLon = ax / G_TO_MS2;` y antes del
`return true;`, agregar:

```cpp
  // Velocidad fusionada y distancia acumulada.
  // La predicción corre a 100 Hz; la corrección solo cuando el GPS entrega
  // una lectura NUEVA y válida (si no, el filtro le haría demasiado caso al
  // mismo dato repetido).
  kalmanVel.predecir(ax, dt);

#if ENABLE_GPS
  if (gpsFix() && gps.speed.isUpdated()) {
    kalmanVel.corregir(gps.speed.mps());
  }
#endif

  velKf = kalmanVel.v;
  if (velKf < 0.0) velKf = 0.0;    // el kart no va en reversa
  distM += velKf * dt;
```

### Cambio 3 — Agregar los campos al paquete LoRa

En `sendLoRaPacket()`, ampliar el buffer y agregar dos campos al final:

```cpp
  char packet[240];                       // era 220

  snprintf(packet, sizeof(packet),
           "K,%lu,%lu,%.2f,%.2f,%.3f,%.3f,%.2f,%.6f,%.6f,%.2f,%.1f,%d,%.2f,%d,%.2f,%.1f",
           radioSeq,
           millis(),
           rollOut, pitchOut,
           gLat, gLon, yawRate,
           gpsLat(), gpsLon(),
           gpsSpeed(), gpsCourse(),
           gpsSats(), gpsHdop(),
           gpsFix() ? 1 : 0,
           velKf, distM);                 // <- nuevos
```

Y actualizar el comentario del formato que está arriba de la función:

```cpp
  // Formato:
  // K,radio_seq,t_ms,roll,pitch,g_lat,g_lon,yaw_rate,lat,lon,speed,course,
  //   sats,hdop,fix,vel_kf,dist_m
```

### Cambio 4 — Guardarlos también en la microSD

En `logSDLine()`, agregar `,%.3f,%.2f` al final del formato y las dos variables:

```cpp
  snprintf(line, sizeof(line),
           "%lu,%lu,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.3f,%.3f,%.4f,%.4f,%.4f,"
           "%.6f,%.6f,%.2f,%.1f,%d,%.2f,%d,%lu,%.3f,%.2f",
           sampleSeq,
           (unsigned long)micros(),
           ax, ay, az,
           gx, gy, gz,
           rollOut, pitchOut,
           gLat, gLon, yawRate,
           gpsLat(), gpsLon(),
           gpsSpeed(), gpsCourse(),
           gpsSats(), gpsHdop(),
           gpsFix() ? 1 : 0,
           gpsAge(),
           velKf, distM);                 // <- nuevos
```

Ampliar también el buffer: `char line[300];` (era 260).

### Cambio 5 — Actualizar la cabecera del CSV de la SD

En `initSD()`, agregar los dos nombres al final:

```cpp
  logFile.println("sample_seq,t_us,ax,ay,az,gx,gy,gz,roll,pitch,g_lat,g_lon,"
                  "yaw_rate,gps_lat,gps_lon,gps_speed_mps,gps_course_deg,"
                  "gps_sats,gps_hdop,gps_fix,gps_age_ms,vel_kf,dist_m");
```

---

## Receptor: `base_final_lora_serial_gps.ino`

Un solo cambio. El receptor reenvía el paquete tal como llega, así que los
campos nuevos pasan solos; únicamente hay que corregir la cabecera que imprime
al arrancar.

En `setup()`, reemplazar la línea del encabezado por:

```cpp
  Serial.println("seq,t_ms,roll,pitch,g_lat,g_lon,yaw_rate,lat,lon,"
                 "gps_speed_mps,gps_course_deg,gps_sats,gps_hdop,gps_fix,"
                 "vel_kf,dist_m,rssi,snr,lost,total");
```

Conviene también actualizar el comentario del formato al inicio del archivo.

---

## Consumidores

El paquete pasa de 18 a **20 columnas**, y `rssi`, `snr`, `lost` y `total` se
corren dos posiciones. Hay que avisarle a quien lea los datos.

### Node-RED

En el nodo `function` que parsea la línea, la lista de campos queda:

```javascript
const campos = ["seq","t_ms","roll","pitch","g_lat","g_lon","yaw_rate",
                "lat","lon","gps_speed_mps","gps_course_deg","gps_sats",
                "gps_hdop","gps_fix","vel_kf","dist_m",
                "rssi","snr","lost","total"];

const v = msg.payload.trim().split(",");
if (v.length < 20) return null;

const d = {};
campos.forEach((c, i) => d[c] = Number(v[i]));
msg.payload = d;
return msg;
```

Después basta con arrastrar dos widgets más al dashboard: uno para `vel_kf`
(gauge de velocidad, rango 0 a 20 m/s) y otro para `dist_m` (texto o gráfica
acumulada).

### Aplicación en Python

En `telemetria_live_python_OK.py`, agregar los dos campos a la lista `FIELDS`
en el mismo orden, entre `gps_fix` y `rssi`:

```python
FIELDS = [
    "seq", "t_ms", "roll", "pitch", "g_lat", "g_lon", "yaw_rate",
    "lat", "lon", "gps_speed_mps", "gps_course_deg", "gps_sats",
    "gps_hdop", "gps_fix", "vel_kf", "dist_m",
    "rssi", "snr", "lost", "total"
]
```

Y en la función `parse_line`, cambiar `if len(p) < 18:` por `if len(p) < 20:` y
agregar las dos entradas al diccionario:

```python
    "vel_kf": float(p[14]),
    "dist_m": float(p[15]),
    "rssi":   float(p[16]),
    "snr":    float(p[17]),
    "lost":   int(float(p[18])),
    "total":  int(float(p[19])),
```

---

## Cómo probarlo

1. Cargar el emisor y el receptor actualizados.
2. Con el kart **quieto**, verificar en el monitor que `vel_kf` esté cerca de 0
   y `dist_m` no crezca. Si la distancia sube estando quieto, el filtro está
   confiando de más en el acelerómetro: subir `R_GPS` a `0.09` (0.3 m/s).
3. Caminar o rodar en línea recta una distancia conocida (por ejemplo 50 m
   medidos con cinta) y comparar con `dist_m`. Un error del 5 % es razonable.
4. Verificar que al frenar la velocidad baje suavemente y sin quedarse negativa.

---

## Detalles que conviene saber

**Por qué se corrige solo con lecturas nuevas del GPS.** El GPS entrega datos a
5 Hz pero el filtro corre a 100 Hz. Si se corrigiera en cada iteración con el
mismo valor repetido, el filtro le daría veinte veces más peso del que merece y
la estimación quedaría pegada al GPS, perdiendo la suavidad que aporta el
acelerómetro. Por eso se usa `gps.speed.isUpdated()`.

**Qué pasa si se pierde el fix.** El filtro sigue prediciendo solo con el
acelerómetro, así que la velocidad se irá desviando poco a poco. Es el
comportamiento esperado y de hecho sirve para mostrar en la sustentación por qué
hace falta la corrección externa.

**La inclinación del sensor afecta la medida.** Si el sensor no está horizontal,
el eje longitudinal capta una componente de la gravedad que se suma a la
aceleración real. El estado de bias del filtro absorbe esa componente mientras
el GPS corrija, pero es una razón más para hacer el cero de montaje.

**La distancia se reinicia en cada encendido.** Si se quiere acumulado entre
tandas, habría que guardarlo en memoria no volátil, lo que no vale la pena para
este uso.
