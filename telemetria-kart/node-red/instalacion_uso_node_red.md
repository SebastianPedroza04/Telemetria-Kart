# README — Instalación y uso de Node-RED para Telemetría Kart

Este documento explica cómo instalar Node-RED, importar el dashboard del proyecto **Telemetría Kart** y visualizar los datos recibidos desde la ESP32 base por puerto serial.

---

## 1. ¿Qué hace este dashboard?

El sistema recibe por serial los datos que llegan desde la ESP32 base conectada al módulo LoRa.  
La ruta de datos es:

```text
KART
BMI160 + ESP32 + Kalman + LoRa
        ↓
BASE
LoRa + ESP32
        ↓ USB Serial
COM del computador
        ↓
Node-RED
        ↓
Dashboard en navegador
```

El dashboard permite visualizar en vivo:

- Roll
- Pitch
- G lateral
- G longitudinal
- Yaw rate
- RSSI LoRa
- SNR
- Paquetes perdidos

---

## 2. Requisitos

Antes de usar el dashboard, cada integrante debe tener instalado:

- Node.js LTS
- Node-RED
- Paquete serial para Node-RED
- FlowFuse Dashboard / Node-RED Dashboard 2.0
- Arduino IDE, solo si también va a cargar firmware en las ESP32

Hardware necesario para probar el dashboard:

- ESP32 base
- Módulo LoRa receptor conectado a la ESP32 base
- Cable USB de datos
- ESP32 del kart transmitiendo datos por LoRa

---

## 3. Instalar Node.js

1. Entrar a la página oficial:

```text
https://nodejs.org
```

2. Descargar la versión **LTS** para Windows.

3. Instalar dejando las opciones por defecto.

4. Abrir PowerShell o CMD y verificar:

```bash
node -v
npm -v
```

Si aparecen las versiones, Node.js quedó instalado correctamente.

---

## 4. Instalar Node-RED

En PowerShell o CMD ejecutar:

```bash
npm install -g --unsafe-perm node-red
```

Cuando termine, iniciar Node-RED con:

```bash
node-red
```

Después abrir en el navegador:

```text
http://localhost:1880
```

---

## 5. Instalar paquetes necesarios en Node-RED

Dentro de Node-RED:

```text
Menú superior derecho ☰
→ Manage palette / Gestionar paleta
→ Install / Instalar
```

Instalar estos paquetes:

```text
node-red-node-serialport
@flowfuse/node-red-dashboard
```

Notas:

- `node-red-node-serialport` agrega los nodos `serial in`, `serial out` y `serial request`.
- `@flowfuse/node-red-dashboard` es el dashboard moderno.
- No instalar `node-red-dashboard` si aparece como obsoleto.

Después de instalar, reiniciar Node-RED:

```text
Ctrl + C
node-red
```

---

## 6. Importar el flujo del dashboard

El archivo del flujo debe estar en el repositorio, por ejemplo:

```text
node-red/flows/telemetria_dashboard_flow.json
```

Para importarlo:

```text
Menú superior derecho ☰
→ Import / Importar
→ seleccionar archivo JSON o pegar el contenido
→ Import / Importar
```

Luego ubicar el flujo en el espacio de trabajo y presionar:

```text
Instanciar
```

En la interfaz en inglés ese botón se llama:

```text
Deploy
```

---

## 7. Configurar el puerto serial

El nodo principal de entrada debe ser:

```text
serial in
```

Abrirlo con doble clic y configurar:

```text
Serial Port: COM de la ESP32 base
Baud Rate: 115200
Data Bits: 8
Parity: None
Stop Bits: 1
Split input: on the character \n
Deliver: ASCII strings
```

Ejemplo:

```text
Serial Port: COM4
Baud Rate: 115200
```

Importante:

```text
Arduino Serial Monitor debe estar cerrado.
Node-RED y Arduino IDE no pueden usar el mismo COM al mismo tiempo.
```

Si Node-RED no recibe datos, cerrar Serial Monitor, revisar el COM y volver a presionar `Instanciar`.

---

## 8. Formato esperado de datos

La ESP32 base debe entregar por serial líneas CSV con esta estructura:

```csv
seq,t_us,ax,ay,az,gx,gy,gz,roll,pitch,g_lat,g_lon,yaw_rate,rssi,snr,lost,total
```

Ejemplo:

```csv
5226,1046842008,0.271,0.261,-9.797,0.035,0.019,0.056,178.5,-5.3,0.027,0.028,0.056,-37,10.25,0,5226
```

---

## 9. Función principal de parseo

El primer bloque `function` después del `serial in` debe convertir el CSV en objeto.

Nombre recomendado:

```text
telemetria
```

Código:

```javascript
let line = msg.payload.toString().trim();

if (!line) return null;

if (
    line.startsWith("===") ||
    line.startsWith("LoRa") ||
    line.startsWith("seq") ||
    line.startsWith("ERROR") ||
    line.startsWith("ets") ||
    line.startsWith("rst:")
) {
    return null;
}

let p = line.split(",");

// seq,t_us,ax,ay,az,gx,gy,gz,roll,pitch,g_lat,g_lon,yaw_rate,rssi,snr,lost,total
if (p.length < 17) {
    return null;
}

let data = {
    seq: Number(p[0]),
    t_us: Number(p[1]),
    ax: Number(p[2]),
    ay: Number(p[3]),
    az: Number(p[4]),
    gx: Number(p[5]),
    gy: Number(p[6]),
    gz: Number(p[7]),
    roll: Number(p[8]),
    pitch: Number(p[9]),
    g_lat: Number(p[10]),
    g_lon: Number(p[11]),
    yaw_rate: Number(p[12]),
    rssi: Number(p[13]),
    snr: Number(p[14]),
    lost: Number(p[15]),
    total: Number(p[16])
};

if (
    Number.isNaN(data.seq) ||
    Number.isNaN(data.roll) ||
    Number.isNaN(data.pitch)
) {
    return null;
}

msg.payload = data;
return msg;
```

Flujo mínimo de prueba:

```text
serial in → telemetria → debug
```

Si funciona, en el panel de depuración aparecerán objetos con campos como:

```json
{
  "seq": 5226,
  "ax": 0.271,
  "ay": 0.261,
  "az": -9.797,
  "roll": 178.5,
  "pitch": -5.3,
  "rssi": -37,
  "snr": 10.25,
  "lost": 0
}
```

---

## 10. Funciones para cada widget

Cada variable del dashboard se extrae con un nodo `function` pequeño conectado después de `telemetria`.

### Roll

```javascript
msg.payload = Number(msg.payload.roll);
msg.topic = "Roll";
return msg;
```

Widget recomendado:

```text
ui-chart
Rango Y: -180 a 180
Unidad: °
```

---

### Pitch

```javascript
msg.payload = Number(msg.payload.pitch);
msg.topic = "Pitch";
return msg;
```

Widget recomendado:

```text
ui-chart
Rango Y: -90 a 90
Unidad: °
```

---

### G lateral

```javascript
msg.payload = Number(msg.payload.g_lat);
msg.topic = "G lateral";
return msg;
```

Widget recomendado:

```text
ui-gauge
Rango: -3 a 3
Unidad: G
```

---

### G longitudinal

```javascript
msg.payload = Number(msg.payload.g_lon);
msg.topic = "G longitudinal";
return msg;
```

Widget recomendado:

```text
ui-gauge
Rango: -3 a 3
Unidad: G
```

---

### Yaw rate

```javascript
msg.payload = Number(msg.payload.yaw_rate);
msg.topic = "Yaw rate";
return msg;
```

Widget recomendado:

```text
ui-chart
Rango Y: -300 a 300
Unidad: °/s
```

---

### RSSI LoRa

```javascript
msg.payload = Number(msg.payload.rssi);
msg.topic = "RSSI LoRa";
return msg;
```

Widget recomendado:

```text
ui-gauge
Rango: -120 a -20
Unidad: dBm
```

Interpretación rápida:

```text
-30 dBm  → señal muy fuerte
-70 dBm  → señal buena/media
-100 dBm → señal débil
```

---

### SNR

```javascript
msg.payload = Number(msg.payload.snr);
msg.topic = "SNR";
return msg;
```

Widget recomendado:

```text
ui-gauge
Rango: -20 a 20
Unidad: dB
```

Interpretación rápida:

```text
SNR positivo → señal clara
SNR cercano a 0 → enlace más exigido
SNR negativo → enlace débil o ruidoso
```

---

### Paquetes perdidos

```javascript
msg.payload = Number(msg.payload.lost);
msg.topic = "Paquetes perdidos";
return msg;
```

Widget recomendado:

```text
ui-text o ui-gauge
Rango sugerido: 0 a 50 para pruebas cortas
```

Si en una prueba larga el valor supera 50, aumentar el rango del gauge o usar `ui-text`.

---

## 11. Organización recomendada del dashboard

Para que se vea más profesional, organizarlo en tres grupos:

```text
Página: Telemetría Kart
```

### Grupo 1 — Estado del enlace

- RSSI LoRa
- SNR
- Paquetes perdidos
- Total paquetes

### Grupo 2 — Actitud

- Roll
- Pitch

### Grupo 3 — Dinámica

- G lateral
- G longitudinal
- Yaw rate

---

## 12. Abrir el dashboard

Después de importar y presionar `Instanciar`, abrir:

```text
http://localhost:1880/dashboard/page1
```

Si el flujo fue editado para otra ruta, revisar en la pestaña Dashboard de Node-RED cuál es la URL de la página.

---

## 13. Problemas comunes

### No aparece `serial in`

Falta instalar:

```text
node-red-node-serialport
```

Solución:

```text
Manage palette → Install → node-red-node-serialport
```

Reiniciar Node-RED.

---

### Dashboard viejo aparece como obsoleto

No instalar:

```text
node-red-dashboard
```

Instalar:

```text
@flowfuse/node-red-dashboard
```

---

### Node-RED no recibe datos

Revisar:

```text
1. Arduino Serial Monitor cerrado.
2. Puerto COM correcto.
3. Baud rate 115200.
4. ESP32 base conectada por USB.
5. ESP32 emisora transmitiendo por LoRa.
6. Presionar Instanciar después de cambiar configuración.
```

---

### El dashboard recibe datos pero las gráficas no se mueven

Revisar que cada función entregue un número:

```javascript
msg.payload = Number(msg.payload.roll);
return msg;
```

También revisar rangos:

```text
Roll: -180 a 180
Pitch: -90 a 90
G lateral: -3 a 3
RSSI: -120 a -20
```

---

### El gauge aparece como nodo inválido

Abrir el `ui-gauge` y revisar:

```text
Group configurado
Label configurado
Value = msg.payload
Range min/max configurado
Segments configurados
Units configurado
```

Luego presionar:

```text
Instanciar
```

---

## 14. Recomendaciones para pruebas

Antes de usar en pista, hacer pruebas en este orden:

1. Prueba de mesa quieta.
2. Prueba manual moviendo la caja.
3. Prueba de alcance LoRa.
4. Prueba caminando.
5. Prueba en bicicleta o carro lento.
6. Prueba final en kart.

En cada prueba registrar:

- RSSI
- SNR
- Paquetes perdidos
- Roll y pitch
- G lateral y longitudinal
- Yaw rate

---

## 15. Pendientes actuales del proyecto

- Comprar microSD.
- Probar módulo microSD.
- Decidir alimentación final del LoRa:
  - ESP32 3V3 si se mantiene estable.
  - MB102 o regulador externo de 3.3 V si hay reinicios.
- Calibrar IMU a cero según montaje final.
- Caracterización de IMU:
  - reposo
  - seis posiciones
  - deriva del giroscopio
  - vibración
- Mejorar dashboard.
- Integrar GPS L86 solo si el sistema base queda cerrado.

---

## 16. Archivos recomendados en GitHub

Guardar este documento en:

```text
docs/06_instalacion_uso_node_red.md
```

Guardar el flujo exportado en:

```text
node-red/flows/telemetria_dashboard_flow.json
```

Guardar capturas o PDF del dashboard en:

```text
evidence/dashboard/
```
