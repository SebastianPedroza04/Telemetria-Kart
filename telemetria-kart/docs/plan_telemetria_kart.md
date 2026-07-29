# Sistema de telemetría inercial e IoT para kart
## Guía técnica y plan de ejecución por fases

Curso: Sensores y Actuadores · Plataforma: ESP32 + IMU + MQTT + Python

---

## 1. Resumen técnico del proyecto

### Qué se construye
Un registrador/transmisor de telemetría montado en un kart que:

1. Adquiere aceleraciones (ax, ay, az) y velocidades angulares (gx, gy, gz) de una IMU a 100–200 Hz.
2. Convierte a unidades físicas, corrige offset/bias y filtra (pasa-bajo + Kalman).
3. Registra todo con timestamp en CSV (SD) y publica por MQTT (WiFi) a una estación base.
4. Analiza los datos en Python: G lateral, G longitudinal, yaw rate, crudo vs filtrado, y eventualmente tiempos de vuelta con un sensor de meta.

### Qué se puede medir realmente con una IMU
| Variable | ¿Medible? | Calidad |
|---|---|---|
| Aceleración longitudinal (G long.) | Sí, directa (ax) | Buena tras calibrar y filtrar vibración |
| Aceleración lateral (G lat.) | Sí, directa (ay) | Buena |
| Yaw rate (velocidad de guiñada) | Sí, directa (gz) | Buena; el *ángulo* de yaw deriva |
| Roll / pitch (ángulos) | Sí, fusionando accel+gyro (Kalman) | Buena en cuasi-estático; sesgada bajo aceleración sostenida |
| Vibración / impactos (pianos, baches) | Sí | Buena |
| Velocidad lineal | Solo integrando ax → **deriva en segundos** | Mala sin referencia externa |
| Posición / trazada | Doble integración → **deriva en segundos** | Inutilizable sin GPS u otra referencia |
| Ángulo de yaw absoluto (rumbo) | Integrando gz → deriva; sin magnetómetro no hay referencia | Solo válido en ventanas cortas (una curva) |

### Limitaciones de una IMU sin GPS ni magnetómetro
- **Deriva del giroscopio:** el bias de gz (típ. 0.5–3 °/s sin calibrar) integrado da errores de decenas de grados por minuto. El yaw absoluto no es confiable más allá de segundos.
- **Deriva de velocidad/posición:** un bias residual de 0.05 m/s² en ax produce ~3 m/s de error de velocidad en 60 s y ~90 m de error de posición. Por eso la trazada por integración pura es imposible.
- **Ambigüedad gravedad/aceleración:** el acelerómetro mide aceleración específica (movimiento + gravedad). En una curva sostenida no puede distinguir inclinación de aceleración lateral sin más información.
- **Sin referencia de rumbo:** sin magnetómetro (y en un kart el magnetómetro sufre interferencia del motor) no hay yaw absoluto.

### Qué se puede prometer y qué no
**Prometer con confianza:** G lateral y longitudinal calibradas, yaw rate, detección de curvas/frenadas/aceleraciones, roll y pitch estimados por Kalman, comparación crudo vs filtrado, caracterización completa del sensor, telemetría MQTT en vivo, y tiempos de vuelta si se agrega sensor de meta.

**No prometer:** trazada (mapa de la pista) solo con IMU; velocidad absoluta solo con IMU; yaw absoluto sostenido. Estas requieren GPS (trazada/velocidad) o Hall de rueda (velocidad/distancia). Enmarcar el proyecto como "telemetría inercial de dinámica del kart", no como "reconstrucción de trayectoria".

---

## 2. Arquitectura recomendada

### Arquitectura mínima viable (MVA)
```
[IMU BMI160]--I2C/SPI-->[ESP32]
                          ├── Adquisición 100 Hz (timer/tarea RTOS)
                          ├── Calibración (offset/bias) + LPF
                          ├── Buffer + microSD (CSV)
                          └── WiFi → MQTT (10–20 Hz) → [Broker Mosquitto en laptop]
                                                            └── [Python: suscriptor, log, gráficas]
```
Kalman corre **offline en Python** sobre los CSV. Esto ya cubre el 80 % de los objetivos del curso.

### Arquitectura extendida
```
[BMI160] [Sensor meta IR/Hall] [Hall rueda] [GPS opc.]
    └────────┬───────┴──────────┬───────────┘
           [ESP32]
      ├ Adquisición multi-sensor con timestamp común
      ├ Calibración + Kalman embebido (roll/pitch, bias gyro)
      ├ microSD (CSV/binario, alta frecuencia)
      ├ MQTT por WiFi (pits) ─ opcional puente LoRa si no hay cobertura
      └ Watchdog + detección de vuelta
           ↓
   [Estación base: broker + Node-RED/Grafana dashboard]
           ↓
   [Python: análisis post-sesión, comparación de vueltas]
```

### ¿MQTT, LoRa o ambos?
- **Primero MQTT sobre WiFi.** Es trivial en ESP32, tiene QoS, y en pruebas de mesa/patio el alcance sobra. Permite validar toda la cadena de datos.
- **LoRa después, solo si hace falta.** En un kartódromo el WiFi puede no cubrir toda la pista. Opciones: (a) aceptar telemetría solo cerca de pits + registro completo en SD (recomendado), o (b) puente LoRa → gateway → MQTT. LoRa tiene ancho de banda bajo (~1–5 kB/s útiles): solo resúmenes (1–5 Hz de variables clave), nunca datos crudos a 100 Hz.
- **La SD es el respaldo obligatorio:** la telemetría en vivo es "nice to have"; el análisis serio siempre sale de la SD.

### ¿Cuándo agregar GPS?
Solo después de que IMU + caracterización + Kalman + MQTT funcionen (Fase 10+). Tiene sentido si se quiere: velocidad absoluta (validar la estimación con Hall), trazada aproximada (con GPS 10 Hz tipo u-blox M8/M10), o tiempo de vuelta sin sensor de meta (geocerca). No antes: añade complejidad (antena, parsing NMEA/UBX, 1–10 Hz vs 100 Hz de la IMU) y desvía el foco del curso.

---

## 3. Lista de materiales

### Comparación de IMU
| Criterio | MPU6050 | BMI160 | ICM-42688-P |
|---|---|---|---|
| Estado | Obsoleto (EOL, clones abundantes) | Vigente, maduro | Vigente, gama alta |
| Ruido acel. | ~400 µg/√Hz | ~180 µg/√Hz | ~70 µg/√Hz |
| Ruido gyro | ~0.005 °/s/√Hz | ~0.008 °/s/√Hz | ~0.0028 °/s/√Hz |
| Rango acel. | ±2 a ±16 g | ±2 a ±16 g | ±2 a ±16 g |
| Rango gyro | ±250 a ±2000 °/s | ±125 a ±2000 °/s | ±15.6 a ±2000 °/s |
| ODR máx útil | 1 kHz (I2C) | 1.6 kHz | 32 kHz (SPI) |
| Interfaz | I2C 400 kHz | I2C / SPI 10 MHz | I2C / SPI 24 MHz |
| FIFO | 1 KB | 1 KB | 2 KB |
| Estabilidad de bias | Regular (clones: mala) | Buena | Muy buena |
| Documentación/librerías | Enorme | Buena | Creciente |
| Precio módulo | ~2–4 USD | ~4–7 USD | ~8–15 USD |

**Recomendación: BMI160 como sensor principal.** Mejor ruido y estabilidad que MPU6050, precio bajo, SPI disponible (útil a 200+ Hz). El ICM-42688-P es superior pero cuesta más y su ventaja no cambia las conclusiones del curso. El MPU6050, si ya lo tienen, sirve como **segundo sensor para comparar caracterizaciones** — eso enriquece el informe (selección de sensores con datos propios).

### Resto del BOM
| Ítem | Recomendación | Justificación técnica |
|---|---|---|
| Microcontrolador | **ESP32 DevKit (WROOM-32)** o ESP32-S3 | WiFi integrado (MQTT nativo), 2 núcleos (núcleo 0: red; núcleo 1: adquisición determinista), FPU para Kalman embebido, SPI/I2C/UART simultáneos |
| Almacenamiento | Módulo microSD SPI + tarjeta clase 10 ≥8 GB | 100 Hz × ~60 B/muestra ≈ 6 kB/s → 20 MB/h; escribir en bloques de 512 B con buffer doble para no bloquear la adquisición |
| RTC de tiempo | No imprescindible: usar `millis()`/`esp_timer` + sincronización NTP al arrancar | Timestamp relativo consistente es suficiente; NTP da hora absoluta para correlacionar con video |
| LoRa (opcional) | RFM95W / SX1276 868–915 MHz (verificar banda local: Colombia 915 MHz) | Alcance >1 km; solo para resumen 1–5 Hz |
| Sensor de meta | **Emisor/receptor IR de barrera** en el borde de pista + receptor en el kart (tipo transponder casero), o **imán en pista + Hall/reed en el chasis** | Da un pulso por vuelta → reancla el tiempo de vuelta y segmenta los datos; el IR es inmune a vibración; el Hall requiere pasar cerca del imán (<2 cm), más difícil en kart |
| Hall de rueda (opcional) | Sensor Hall A3144 o inductivo + 1–4 imanes en el eje trasero | Velocidad y distancia reales: v = 2πr·(pulsos/s)/N_imanes. Es la mejor referencia para el Kalman de velocidad |
| GPS (opcional) | u-blox NEO-M8N o M10, 10 Hz, antena activa | Velocidad Doppler (precisa ~0.1 m/s) y trazada aproximada (~2.5 m CEP) |
| Alimentación | Batería Li-ion 18650 ×2 o LiPo 2S + regulador buck a 5 V + LDO 3.3 V de bajo ruido (AMS1117 mínimo, mejor MIC5219); condensadores 470 µF + 100 nF en la entrada del ESP32 | El kart vibra y el motor genera picos; el WiFi del ESP32 demanda picos de ~400 mA — una alimentación pobre causa brownouts y reinicios |
| Montaje | Caja rígida (impresa/ABS) atornillada al chasis **con la IMU pegada rígidamente a la placa**, y la caja montada sobre **espuma de doble densidad o silentblocks pequeños** | Aislar la vibración del motor (>100 Hz) sin filtrar la dinámica del vehículo (<10 Hz). Nunca montar la IMU "colgando" de cables |
| Cableado | Cables cortos, trenzados, conectores JST con seguro, termocontraíble | La vibración afloja Dupont sueltos: causa #1 de datos corruptos |

---

## 4. Plan por fases (resumen ejecutivo)

| Fase | Objetivo | Entregable | Criterio de éxito | Error típico | Validación |
|---|---|---|---|---|---|
| **0. Alineación** | Confirmar estado, roles, repositorio | Repo Git + tablero de tareas + este plan aprobado | Todos saben qué hace cada quien | Empezar a soldar sin plan de datos | Reunión: cada uno explica la arquitectura en 2 min |
| **1. Lectura IMU** | ax..gz crudos en el monitor serie | Sketch `01_imu_raw` | Valores estables, ~1 g en el eje vertical, ~0 °/s en reposo | Dirección I2C errada, ejes confundidos, escala mal configurada | Girar la placa: cada eje marca ±1 g cuando apunta abajo |
| **2. CSV** | Registro con timestamp a ≥100 Hz | `02_logger` + primer CSV | 10 min de log sin pérdidas ni bloqueos | Escribir la SD muestra a muestra (bloquea); timestamp de baja resolución | Verificar Δt entre filas: media ≈10 ms, jitter <1 ms |
| **3. Caract. estática** | Media, σ, offset, bias, ruido por eje | Tabla de caracterización + notebook | Valores coherentes con datasheet (mismo orden de magnitud) | Mesa que vibra, sensor sin estabilizar térmicamente | Repetir la prueba 2 días distintos: resultados similares |
| **4. Caract. dinámica** | fs real, retardo, espectro de vibración, saturación | Notebook con FFT y análisis | fs medida = configurada ±1 %; espectro interpretado | Confundir vibración con ruido eléctrico | FFT de prueba en reposo vs con motor de vibración |
| **5. Offset/bias** | Corrección en el ESP32 | `05_calibrated` + rutina de calibración al arrancar | Reposo: |a|≈9.81 m/s², gyro <0.05 °/s tras corrección | Calibrar con el kart inclinado o en movimiento | Log calibrado en reposo: medias ≈ 0 (y g en vertical) |
| **6. MQTT** | Publicar crudo/calibrado/filtrado | Broker + topics + suscriptor Python | 15 min publicando a 10–20 Hz, pérdida <1 % | Payloads gigantes a 100 Hz saturan WiFi; QoS mal elegido | Contador de secuencia: verificar huecos en el suscriptor |
| **7. Análisis Python** | Pipeline de CSV → gráficas | Paquete `analysis/` con scripts | Gráficas de G lat/long y yaw rate de un log real | Unidades mezcladas (g vs m/s²), ejes sin rotular | Revisión cruzada entre compañeros de cada gráfica |
| **8. Kalman offline** | Roll/pitch + bias gyro estimados en Python | Notebook Kalman + comparativas | Ángulo estable en reposo, sigue movimientos, sin lag excesivo | Q y R inventados sin relación con la caracterización | Comparar contra ángulo de referencia (nivel/protractor del celular) |
| **9. Kalman embebido** | Mismo filtro corriendo a 100 Hz en ESP32 | `09_kalman_esp32` | Salida ESP32 ≈ salida Python (misma entrada, error <2 %) | Aritmética float mal dimensionada, dt variable no medido | Alimentar al ESP32 un CSV grabado y comparar salidas |
| **10. Sensor auxiliar** | Meta (vueltas) y/o Hall (velocidad) integrados | Firmware con eventos de vuelta / velocidad | Detección de vuelta 100 % en 10 pasadas; v_Hall coherente | Rebotes del sensor (debounce), interrupciones mal manejadas | Contar pasadas manualmente vs contadas por el sistema |
| **11. Prueba controlada** | Sistema completo en bici/carro lento | Dataset + análisis de la prueba | Curvas y frenadas visibles y coherentes en las gráficas | Montaje flojo, batería insuficiente, olvido de iniciar log | Checklist pre-prueba; comparar eventos contra video |
| **12. Pista** | Sesión real en kart | Dataset de pista + vueltas segmentadas | ≥10 min de datos válidos, ≥5 vueltas detectadas | Vibración satura ±2 g; conectores sueltos; sin plan B | Redundancia SD+MQTT; rango ±8 g/±1000 °/s configurado |
| **13. Cierre** | Informe, gráficas, conclusiones | Informe + presentación + video | Historia completa: sensor→caracterización→filtro→pista | Gráficas sin unidades, conclusiones sin datos | Ensayo de la defensa con preguntas cruzadas |

---

## 5. Desarrollo técnico de cada fase

### Fase 0 — Alineación
**Qué/por qué:** acordar alcance (sección 1), crear repo Git (carpetas `firmware/`, `analysis/`, `data/`, `docs/`), definir convención de ejes del kart (**x = adelante, y = izquierda, z = arriba**, regla de la mano derecha) y diccionario de datos (nombres de columnas del CSV, unidades). Sin convención de ejes, cada integrante grafica cosas distintas.
**Entregable:** `docs/convenciones.md` con ejes, unidades y formato CSV.

### Fase 1 — Lectura de la IMU
**Qué:** conectar BMI160 por I2C (SDA=21, SCL=22, 3.3 V) y leer registros crudos.
**Por qué:** todo lo demás depende de una lectura confiable y a ritmo constante.
**Fórmulas de conversión** (LSB → físico):
```
a[m/s²] = raw · (rango_g · 9.80665) / 32768      # p.ej. ±8 g → /4096 LSB/g
ω[°/s]  = raw · rango_dps / 32768                 # p.ej. ±1000 °/s → /32.8 LSB/(°/s)
```
**Pseudocódigo:**
```cpp
setup(): I2C 400kHz; config BMI160 {acc ±8g @100Hz, gyro ±1000dps @100Hz, LPF ODR/4}
loop @100Hz (esp_timer o vTaskDelayUntil):
    leer 12 bytes burst (ax..gz)
    convertir a unidades físicas
    imprimir t_us, ax, ay, az, gx, gy, gz
```
**Verificación:** tabla de 6 orientaciones — cada eje debe leer ≈ +1 g y −1 g apuntando abajo/arriba.
**Errores a evitar:** leer registro por registro (usa lectura burst para que ax..gz sean de la misma muestra); dejar el rango en ±2 g (satura en el kart); usar `delay()` en vez de un timer (jitter).

### Fase 2 — Registro CSV
**Qué:** escribir a microSD líneas `t_us,ax,ay,az,gx,gy,gz` con cabecera y metadatos (fecha, rango, fs, versión firmware).
**Por qué:** el CSV es la materia prima de TODA la caracterización y del Kalman offline.
**Clave de implementación:** doble buffer — la tarea de adquisición llena un buffer en RAM; una tarea de menor prioridad lo vuelca a SD en bloques de 4–8 kB. Nunca `file.println()` por muestra.
**Gráfica a obtener:** histograma de Δt entre muestras (debe ser una espiga en 10 ms).
**Errores:** pérdida de muestras durante escritura SD (medir con contador de secuencia); corrupción por corte de energía (cerrar/flush cada 5 s); nombres de archivo repetidos (numerar sesiones).

### Fase 3 — Caracterización estática
Ver sección 6 (procedimientos completos). Resultado: tabla por eje de media, varianza, σ, offset, bias del gyro y densidad de ruido, comparada con datasheet.

### Fase 4 — Caracterización dinámica
**Qué:** medir fs real (con los timestamps), estimar retardo del filtro interno, obtener el espectro (FFT) en reposo y bajo vibración, y comprobar saturación/aliasing.
**Por qué:** el kart vibra a frecuencias del motor (50–300 Hz); si fs=100 Hz, todo lo que esté por encima de 50 Hz (Nyquist) se aliasea dentro de la banda útil. La defensa: usar el **LPF interno de la IMU** (analógico/digital antes del muestreo) configurado a ~ODR/4, y muestrear a 200 Hz si es posible.
**Fórmulas:** Nyquist f_max = fs/2; FFT con `scipy.signal.welch` para densidad espectral.
**Gráficas:** PSD en reposo vs con vibración (celular con motor vibrando pegado a la mesa); serie temporal mostrando saturación al golpear la mesa con rango ±2 g vs ±8 g.
**Errores:** confundir aliasing con ruido; medir fs con `millis()` (resolución 1 ms — usar `esp_timer_get_time()`, µs).

### Fase 5 — Corrección de offset y bias
**Qué:** al arrancar (kart quieto, 5–10 s): promediar N=500–1000 muestras.
```
bias_g[i]   = mean(gyro_i)                  → restar siempre
offset_a[i] = mean(acc_i) − g_esperado[i]   → g_esperado = (0,0,9.81) si está nivelado
a_corr = a_raw − offset_a ;  ω_corr = ω_raw − bias_g
```
**Por qué:** el bias del gyro es lo que hace inútil la integración; quitarlo en el arranque reduce la deriva 10–100×. El Kalman luego estima el bias *residual* que cambia con temperatura.
**LPF inicial (IIR de 1er orden):**
```
y[k] = α·x[k] + (1−α)·y[k−1],   α = dt/(dt+RC),  RC = 1/(2π·fc)
fc sugerida: 5–10 Hz para dinámica de vehículo
```
**Gráfica:** crudo vs LPF en una maniobra manual.
**Errores:** calibrar con el kart en pendiente y "tragarse" la componente de g como offset; recalibrar el acelerómetro con el motor encendido.

### Fase 6 — MQTT
Ver sección 8 (topics, payloads, frecuencias). Implementación: `PubSubClient` o `esp-mqtt`; broker Mosquitto en laptop; reconexión automática; publicar desde el núcleo 0 para no perturbar la adquisición.

### Fase 7 — Análisis Python
Ver sección 9 (scripts). Estructura: paquete `analysis/` con módulos reutilizables, no notebooks monolíticos.

### Fase 8 — Kalman offline
Ver sección 7. Implementar primero en `numpy` puro (las matrices son 2×2 — no usar librerías caja negra, el curso pide entenderlo).
**Validación:** reproducir el ángulo de un movimiento conocido (inclinar la placa 45° con un soporte impreso o un nivel digital del celular).

### Fase 9 — Kalman embebido
**Qué:** portar el filtro a C++ (floats, matrices 2×2 explícitas, sin librerías de álgebra).
**Clave:** usar el **dt medido** entre muestras, no el nominal. Costo: ~30 multiplicaciones por iteración — despreciable a 100 Hz en ESP32 (240 MHz con FPU).
**Validación "replay":** guardar un CSV, reproducirlo por serial hacia el ESP32, comparar su salida con la de Python muestra a muestra (error RMS <2 % del rango del ángulo).

### Fase 10 — Sensor auxiliar
**Meta (IR o imán+Hall):** entrada por interrupción con debounce temporal (ignorar pulsos <5 s tras el anterior — no hay vueltas de 5 s). Cada pulso: publicar evento `lap` con timestamp y número de vuelta; marcar el CSV.
**Hall de rueda:** interrupción por flanco; velocidad:
```
v = (2π·r_rueda / N_imanes) / Δt_pulso     [m/s]
```
con timeout a cero si no hay pulsos en 1 s. Filtrar Δt con mediana de 3 para rebotes.
**Errores:** rebotes mecánicos (usar histéresis/Schmitt o debounce por software); interrupciones que hacen trabajo pesado (solo capturar timestamp, procesar fuera).

### Fases 11–12 — Pruebas
Ver sección 10 (plan de pruebas escalonado con criterios).

### Fase 13 — Cierre
Consolidar: tabla de caracterización final, gráficas clave (sección 9), video, informe y presentación (sección 15). Regla: **cada conclusión del informe debe apuntar a una gráfica o tabla con datos propios.**

---

## 6. Caracterización del sensor

### 6.1 Prueba en reposo (la fundamental)
Sensor nivelado, mesa rígida, sin gente caminando, 5 min tras 10 min de calentamiento térmico. Registrar a fs nominal. Calcular por eje:
```
media:     x̄ = (1/N)Σxᵢ
varianza:  s² = (1/(N−1))Σ(xᵢ−x̄)²
desv. est: s = √s²
```
- **Offset acelerómetro** = x̄ − valor esperado (0, o ±g en el eje vertical).
- **Bias giroscopio** = x̄ (el valor esperado en reposo es 0).
- **Ruido** = s. Comparar con datasheet: σ ≈ densidad_de_ruido × √(ancho_de_banda). Ej. BMI160 accel 180 µg/√Hz con BW=50 Hz → σ ≈ 180·√50 ≈ 1.3 mg ≈ 0.012 m/s².

### 6.2 Prueba de seis posiciones (acelerómetro)
Apoyar el módulo en sus 6 caras (cada eje a +g y −g), 60 s por posición. Para cada eje:
```
offset = (x̄₊g + x̄₋g)/2          # lo que no cambia al voltear
sensibilidad = (x̄₊g − x̄₋g)/2g    # ideal = 1.0; da el error de escala
```
Esto separa offset de error de sensibilidad — el promedio simple de la Fase 5 no puede hacerlo. Presentarlo como tabla 3 ejes × {offset, sensibilidad, error %}.

### 6.3 Prueba de deriva (giroscopio)
30–60 min en reposo registrando. Graficar: (a) bias del gyro en ventanas de 1 min vs tiempo (deriva del bias, correlacionarla con temperatura si el sensor la reporta), y (b) el **ángulo integrado** θ(t)=∫ω dt — mostrará crecimiento aproximadamente lineal: esa pendiente ES la deriva en °/min que justifica el Kalman y el reanclaje. Opcional avanzado: varianza de Allan para separar ruido blanco (ARW) de inestabilidad de bias.

### 6.4 Prueba de vibración
Fuente controlada (motor con masa excéntrica, celular vibrando) acoplada a la mesa. Registrar con y sin el aislamiento (espuma) previsto para el kart. Comparar PSD (Welch): el montaje aislado debe atenuar >10 dB por encima de ~30 Hz sin tocar la banda <10 Hz.

### 6.5 Prueba de frecuencia de muestreo
Del CSV: Δtᵢ = tᵢ − tᵢ₋₁. Reportar media, σ (jitter), máximo, y % de muestras perdidas (huecos > 1.5·Δt nominal). Histograma de Δt.

### 6.6 De la caracterización al Kalman
- **R** (varianza de medición) sale directo de la prueba en reposo: para el Kalman de ángulo, R = varianza del ángulo calculado con el acelerómetro en reposo (propagar: calcular θ_acc para cada muestra en reposo y tomar su varianza; típico 0.5–3 (°)²).
- **Q** parte del ruido del gyro: Q_ángulo ≈ σ²_gyro·dt; Q_bias ≈ (deriva del bias)²·dt. Luego se ajusta (sección 7).
- El bias medido en 6.1 es la condición inicial del estado de bias.

### 6.7 Tablas para el informe
1. Condiciones de prueba (fs, rango, temperatura, duración, N).
2. Estática por eje: media, varianza, σ, offset, bias, comparación con datasheet.
3. Seis posiciones: offset y sensibilidad por eje.
4. Deriva: bias inicial, bias final, deriva °/min, ángulo integrado a 1/5/30 min.
5. Dinámica: fs real, jitter, pérdidas, frecuencias dominantes de vibración, atenuación del montaje.
6. Parámetros derivados para Kalman: R, Q iniciales.
7. (Si hay dos IMU) Comparación MPU6050 vs BMI160 → justifica la selección de sensor con datos propios.

---

## 7. Filtro de Kalman aplicado

### 7.1 Qué estimar primero
**Kalman #1 (empezar aquí): ángulo (roll o pitch) + bias del giroscopio.** Es el caso 2×2 clásico, observable con IMU sola, y demuestra fusión de dos sensores con ruidos complementarios: el gyro es bueno a corto plazo (pero deriva), el accel es bueno a largo plazo (pero ruidoso y sensible a aceleraciones).

- **Estado:** x = [θ, b]ᵀ (ángulo, bias del gyro en ese eje)
- **Entrada (control):** u = ω_gyro (velocidad angular medida)
- **Medición:** z = θ_acc, el ángulo por acelerómetro:
```
roll_acc  = atan2(ay, az)
pitch_acc = atan2(−ax, √(ay²+az²))
```

### 7.2 Matrices
Modelo: θₖ = θₖ₋₁ + (ω − b)·dt; el bias camina lento (random walk).
```
F = | 1  −dt |      G = | dt |      H = [ 1  0 ]
    | 0   1  |          | 0  |

Q = | σ²_gyro·dt        0          |     R = [ σ²_θacc ]   (escalar)
    | 0            σ²_biaswalk·dt  |

Predicción:  x̂ = F·x̂ + G·u ;  P = F·P·Fᵀ + Q
Corrección:  K = P·Hᵀ/(H·P·Hᵀ + R) ;  x̂ = x̂ + K(z − H·x̂) ;  P = (I − K·H)P
```

### 7.3 Significado de Q y R en ESTE proyecto
- **R = cuánto desconfiar del acelerómetro.** Físicamente: ruido del accel + el hecho de que en curvas/frenadas θ_acc miente (la aceleración del kart contamina la medida de gravedad). Base: varianza de θ_acc en reposo (sección 6.6). En el kart conviene **inflar R dinámicamente** cuando |‖a‖ − g| es grande (el kart está acelerando → el accel no está midiendo solo gravedad).
- **Q = cuánto desconfiar del modelo/giroscopio.** Q grande → el filtro sigue rápido pero deja pasar ruido; Q pequeño → salida suave pero lenta y ciega ante cambios de bias.

### 7.4 Obtención y ajuste
- **R desde caracterización:** directo de la prueba en reposo (varianza de θ_acc). No se inventa.
- **Q experimental:** partir de σ²_gyro·dt del datasheet/caracterización; luego, con un log grabado, barrer Q ×{0.1, 1, 10, 100} en Python y elegir por: (a) σ del ángulo en reposo baja, (b) tiempo de respuesta a un escalón de inclinación aceptable (<0.3 s), (c) el residuo (z − Hx̂) parece ruido blanco (si tiene estructura, el modelo/Q está mal). Documentar el barrido con una gráfica — es material de informe excelente.

### 7.5 Qué se logra con cada sensor
| Configuración | Se estima bien | Sigue sin poderse |
|---|---|---|
| Solo IMU | Roll, pitch, bias gyro, yaw rate, G lat/long filtradas | Yaw absoluto, velocidad, posición |
| + Sensor de meta | Lo anterior + tiempo de vuelta exacto + **reanclaje por vuelta**: reset de la integral de yaw y segmentación (el error deja de acumularse entre vueltas; permite comparar vueltas) | Velocidad y trazada continuas |
| + Hall de rueda | + **velocidad y distancia reales** → habilita el Kalman de velocidad (7.6), detecta bloqueo de rueda (v_Hall vs ax) | Trazada (posición 2D) |
| + GPS (10 Hz) | + velocidad Doppler absoluta, trazada aproximada (~2–3 m), rumbo en movimiento → corrige el yaw integrado | Precisión centimétrica (requeriría RTK) |
| Sin ninguna referencia externa | — | **Nada de lo anterior: sin medición externa, ningún filtro elimina la deriva de una integral; solo la ralentiza.** Este es un punto conceptual clave del informe. |

### 7.6 Kalman extendido/kinemático para velocidad (con Hall o GPS)
- **Estado:** x = [v, b_a]ᵀ (velocidad longitudinal, bias de ax)
- **Predicción con la IMU:** vₖ = vₖ₋₁ + (ax − b_a)·dt (mismas F, G que 7.2 con ω→ax)
- **Corrección:** z = v_Hall (cada pulso, ~5–50 Hz) o v_GPS (10 Hz). H = [1 0].
- R_Hall desde la dispersión de v_Hall a velocidad constante; R_GPS ~ (0.1–0.5 m/s)².
- Distancia: integrar v̂ (la deriva ya está acotada por la corrección). Con esto sí se puede prometer velocidad y distancia por vuelta.
- Nota: es lineal, así que basta KF; "extendido" (EKF) solo sería necesario si se acopla el yaw para estimar trazada 2D con GPS — extensión opcional de nota alta, no del alcance base.

---

## 8. MQTT y estructura de datos

### 8.1 Topics
```
kart/K01/imu/raw        # decimado, para monitoreo
kart/K01/imu/filt       # salida calibrada + Kalman
kart/K01/speed          # si hay Hall
kart/K01/lap            # evento de vuelta
kart/K01/status         # 0.5 Hz: batería, RSSI, SD ok, uptime, drops
kart/K01/cmd            # (suscrito) start/stop log, recalibrar
```
QoS 0 para flujos continuos (imu/*), QoS 1 para eventos (`lap`, `status`, `cmd`).

### 8.2 Payloads JSON
```json
// imu/filt (lote de muestras para eficiencia)
{"ts":123456789,"seq":4021,"n":5,
 "ax":[0.12,...],"ay":[8.90,...],"gz":[45.2,...],
 "roll":2.1,"pitch":-0.8}

// lap
{"ts":123456789,"lap":7,"t_lap":52.31}

// status
{"ts":123456789,"vbat":7.4,"rssi":-61,"sd":true,"drops":3,"fw":"1.3"}
```
`seq` es el contador de secuencia global: imprescindible para medir pérdidas.

### 8.3 CSV/binario como alternativa
- **SD siempre en CSV** (o binario empaquetado `struct` de 32 B/muestra si 200 Hz aprieta; conversor a CSV en Python).
- Por MQTT, si el JSON pesa mucho: payload binario (mismo `struct`) reduce ~70 % el tamaño; JSON es mejor para depurar. Recomendación: JSON en desarrollo, evaluar binario solo si hay pérdidas.

### 8.4 Frecuencias — adquisición ≠ transmisión
- **Adquisición: 100–200 Hz** (la dinámica y la vibración lo exigen; alimenta SD y Kalman).
- **Transmisión MQTT: 10–20 Hz efectivos**, en lotes (1 mensaje con 5–10 muestras cada 100 ms). Publicar cada muestra individual a 100 Hz satura el stack WiFi y añade latencia.
- El dashboard no necesita más de 10–20 Hz para verse fluido; el análisis fino usa la SD.

### 8.5 Métricas de la red (material de informe)
- **Pérdida de paquetes:** en el suscriptor Python, contar huecos de `seq`: pérdida % = huecos/esperados. Graficar vs tiempo y vs RSSI.
- **Latencia:** (a) sincronizar ESP32 por NTP y comparar `ts` de emisión vs hora de llegada (resolución ~decenas de ms), o (b) eco: publicar en `cmd/ping`, el ESP32 responde, medir RTT/2.
- **Organización para análisis:** el suscriptor guarda todo en `data/mqtt/sesion_YYYYMMDD_HHMM.csv` con columna extra `t_rx`. Convención de sesiones idéntica a la SD para poder cruzarlas.

---

## 9. Análisis en Python

Estructura sugerida del paquete:
```
analysis/
  io_csv.py        # load_session(path) → DataFrame validado
  clean.py         # huecos, duplicados, outliers, unidades
  calib.py         # aplica offset/bias de la caracterización
  filters.py       # LPF, Kalman offline (numpy)
  laps.py          # segmentación por eventos de meta
  plots.py         # todas las gráficas con estilo común
  metrics.py       # G máx, medias por vuelta, RMS
  export.py        # PNG/CSV de resultados
notebooks/         # exploración; la lógica vive en analysis/
```

| Script/función | Qué hace | Detalle clave |
|---|---|---|
| `io_csv.load_session` | Lee CSV, parsea metadatos de cabecera, valida columnas | `t` a segundos float64 desde µs |
| `clean.fix` | Elimina duplicados, detecta huecos (Δt>1.5 nominal), marca saturación (|raw|=32767) | Reportar % afectado, no borrar silenciosamente |
| `calib.apply` | Resta offset/bias de la tabla de caracterización | La tabla vive en un `calib.json` versionado |
| `plots.accel / plots.gyro` | Series temporales 3 ejes, unidades SI, zoom por vuelta | Crudo en gris claro, filtrado encima |
| `metrics.g_lat / g_long` | ay/9.81 y ax/9.81 (tras rotar IMU→vehículo si el montaje no está alineado) | La matriz de rotación sale de una calibración estática + una frenada recta |
| `metrics.yaw_rate` | gz corregido de bias, en °/s | Signo coherente con la convención (izq. positivo) |
| `filters.kalman_offline` | Corre el KF sobre el log, devuelve θ̂, b̂, K(t), residuos | Base del ajuste de Q (sección 7.4) |
| `plots.raw_vs_filt` | Superpone crudo, LPF y Kalman; panel de residuos | LA gráfica estrella del informe |
| `laps.detect` | Corta el DataFrame por eventos `lap`; fallback sin sensor de meta: autocorrelación de la señal de yaw rate | Devuelve lista de DataFrames por vuelta |
| `laps.compare` | Superpone vueltas alineadas por distancia (con Hall) o tiempo normalizado | G-G diagram (ay vs ax) por vuelta: espectacular y fácil |
| `export.report_pack` | Guarda todas las figuras en `figs/` a 300 dpi + `resumen.csv` de métricas por vuelta | Reproducible con un solo comando |

---

## 10. Plan de pruebas escalonado

| Prueba | Qué medir | Qué esperar | Problema típico | Validez si... |
|---|---|---|---|---|
| **1. Mesa (estática)** | Todo lo de la sección 6 | σ y bias del orden del datasheet; |a|=9.81±0.05 | Mesa vibrando, deriva térmica al inicio | Repetible entre días (<20 % de variación en σ) |
| **2. Movimiento manual** | Rotaciones ±90° conocidas, inclinaciones a ángulos medidos | Kalman sigue el ángulo real ±2°; gz integra ≈90° en giros cortos | Confusión de ejes/signos; lag del filtro | Ángulos estimados vs referencia física (soporte a 30/45/60°) |
| **3. Bicicleta / carro lento** | Sistema completo con batería: SD+MQTT+Kalman; curvas y frenadas reales suaves | G lat 0.1–0.3 g en curvas, G long 0.2–0.4 g frenando; eventos visibles y con el signo correcto | Montaje flojo (señal "doble"), pérdida WiFi al alejarse, brownout | Cada evento del video aparece en la gráfica con el timestamp correcto |
| **4. Patio / pista pequeña** | Vueltas a un circuito improvisado con sensor de meta; Hall si está | Vueltas detectadas 100 %; t_vuelta consistente ±0.2 s; patrón de yaw rate repetible entre vueltas | Falsos disparos de meta, vibración mayor que en bici | Conteo manual de vueltas = conteo del sistema; vueltas superpuestas se parecen |
| **5. Kart en pista** | Sesión completa ≥10 min; rangos ±8 g / ±1000 °/s | G lat hasta 1.5–2.5 g en curvas, yaw rate hasta 100–200 °/s; vibración fuerte pero no saturación | Saturación si quedó ±2 g; conector suelto; WiFi solo en pits (SD salva la sesión); temperatura | Sin saturación (<0.1 % muestras al límite), ≥5 vueltas segmentadas, G-G diagram con forma de "sobre" coherente |

Regla general: **no pasar a la siguiente prueba hasta que la anterior tenga criterio de validez cumplido y dataset archivado.**

---

## 11. Cronograma (8 semanas)

| Sem | Tareas | Responsables sugeridos | Entregable |
|---|---|---|---|
| 1 | Fase 0 + compra de materiales + Fase 1 (lectura IMU) | Todos (F0); Firmware: F1 | Repo, convenciones, sketch IMU |
| 2 | Fase 2 (CSV/SD) + inicio Fase 3 (reposo, 6 posiciones) | Firmware: logger; Análisis: protocolo de caracterización | Primer dataset + histograma Δt |
| 3 | Fase 3 completa + Fase 4 (FFT, deriva 30 min) | Análisis: notebooks; Firmware: soporte | Tablas de caracterización |
| 4 | Fase 5 (calibración en ESP32) + Fase 6 (MQTT) + Fase 7 (pipeline Python) | Firmware: calib+MQTT; Análisis: paquete `analysis/` | Demo en vivo MQTT + gráficas |
| 5 | Fase 8 (Kalman offline, ajuste Q/R con barrido) | Análisis lidera; todos entienden el filtro | Notebook Kalman + gráfica crudo vs filtrado |
| 6 | Fase 9 (Kalman embebido + replay) + Fase 10 (meta/Hall) | Firmware: KF y sensores; Hardware: montaje y alimentación | Firmware v1.0 + caja montada |
| 7 | Fase 11 (prueba bici/patio) + correcciones | Todos en campo | Dataset controlado + análisis |
| 8 | Fase 12 (pista si es posible) + Fase 13 (informe, video, presentación) | Todos; Documentación lidera cierre | Paquete final de entregables |

Colchón: si la pista no se consigue, la prueba 4 (patio) es el resultado defendible — el cronograma no depende del kartódromo. Roles sugeridos para 3–4 personas: Firmware/HW, Análisis/Kalman, Integración/Pruebas, Documentación (rotar la documentación).

---

## 12. Riesgos técnicos y mitigación

| Riesgo | Efecto | Mitigación |
|---|---|---|
| Ruido de la IMU | Gráficas ilegibles, Kalman mal ajustado | Caracterizar primero (R real); LPF interno de la IMU a ODR/4; promediado donde aplique |
| Vibración del kart | Enmascara la dinámica, aliasing, tornillos flojos | Montaje rígido IMU-caja + aislamiento caja-chasis (espuma); fs 200 Hz; verificar con FFT antes/después |
| Deriva del giroscopio | Yaw/ángulos inútiles a mediano plazo | Calibración de bias al arranque; estado de bias en el Kalman; reanclaje con sensor de meta; NO prometer yaw absoluto |
| Saturación del sensor | Datos truncados irrecuperables en curvas/baches | Rango ±8 g y ±1000 °/s en kart; monitorear % de muestras al límite en `status` |
| Pérdida de paquetes MQTT | Huecos en telemetría en vivo | SD como fuente primaria; `seq` + medición de pérdida; lotes pequeños QoS 0; QoS 1 solo eventos |
| Alcance inalámbrico | Sin datos en vivo lejos de pits | Aceptarlo (SD) o AP dedicado con antena; LoRa solo como extensión de resumen a 1–5 Hz |
| Alimentación inestable | Brownouts, SD corrupta, reinicios | Batería dedicada (nunca la del kart directa), buck+LDO, condensadores, flush periódico de SD, watchdog |
| Montaje mecánico deficiente | Ejes desalineados, señal contaminada, sensor suelto | Caja atornillada, ejes marcados, calibración de alineación (frenada recta), checklist pre-prueba |
| Sobreprometer trazada con IMU | Expectativas rotas en la evaluación | Alcance explícito desde la Fase 0 (sección 1); trazada solo como "extensión futura con GPS" |

---

## 13. Resultado mínimo viable (defendible)

1. BMI160 leyendo a 100 Hz con conversión a unidades físicas. ✚
2. Datasets CSV con timestamp en SD (varias sesiones archivadas).
3. Caracterización estática y dinámica completa con tablas comparadas contra datasheet.
4. Corrección de offset/bias + LPF en el ESP32.
5. MQTT publicando calibrado a 10–20 Hz con medición de pérdida de paquetes.
6. Kalman offline (roll/pitch + bias) con Q y R derivados de la caracterización y barrido de ajuste documentado.
7. Gráficas: crudo vs LPF vs Kalman; G lat, G long, yaw rate de una **prueba controlada** (bici/patio).

Esto cubre todos los temas del curso (estadística, características estáticas y dinámicas, selección de sensores, Kalman) aunque el kart nunca pise la pista.

## 14. Resultado ideal

Todo lo anterior más: Kalman embebido validado por replay; sensor de meta detectando vueltas + Hall de rueda con Kalman de velocidad; dashboard en vivo (Node-RED o Grafana sobre el broker); comparación entre vueltas (yaw rate superpuesto + G-G diagram); sesión en kartódromo ≥10 min; registro SD robusto a 200 Hz; MQTT estable en pits; LoRa solo si el alcance lo exigió. GPS 10 Hz como cereza: validación de velocidad y trazada aproximada.

## 15. Entregables finales

| Entregable | Contenido mínimo |
|---|---|
| Diagrama de arquitectura | Bloques MVA y extendida (sección 2), flujos de datos con frecuencias |
| Tabla de selección de sensores | Comparativa sección 3 + criterios ponderados + (ideal) datos propios de 2 IMU |
| Tabla de caracterización | Las 6–7 tablas de la sección 6.7 |
| Código ESP32 | Repo con tags por fase; README de pines y compilación |
| Código Python | Paquete `analysis/` + notebooks; `requirements.txt`; reproducible |
| Dataset CSV | Sesiones crudas + calibradas, con metadatos, organizadas por fecha |
| Gráficas | Crudo vs filtrado, G lat/long, yaw rate, PSD vibración, barrido de Q, deriva del gyro, (ideal) comparación de vueltas y G-G |
| Video | 2–3 min: montaje, prueba en movimiento, dashboard en vivo, sincronizado con una gráfica |
| Informe técnico | Estructura: objetivo → selección → caracterización → calibración → filtrado (LPF y Kalman con matrices y ajuste) → comunicación → pruebas → resultados → limitaciones (deriva, trazada) → conclusiones |
| Presentación | 10–15 láminas siguiendo la misma narrativa; demo en vivo de MQTT si es posible |

---

*Regla de oro del proyecto: la SD es la verdad, MQTT es la vitrina, la caracterización es la nota, y el Kalman es la estrella — pero solo brilla si Q y R salen de datos propios.*
