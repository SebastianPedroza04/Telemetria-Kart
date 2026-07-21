# node-red/flows/

Esta carpeta contiene lo necesario para compartir el flujo de Node-RED del proyecto **Telemetría Kart**.

## Archivos

```text
node-red/flows/
├── README.md
├── telemetria_dashboard_flow.json
├── flujo_minimo_debug.json
├── parse_telemetria.js
└── funciones_variables.md
```

## Cómo usarlo

1. Abrir Node-RED:

```text
http://localhost:1880
```

2. Instalar estos paquetes desde:

```text
Menú ☰ → Manage palette → Install
```

Instalar:

```text
node-red-node-serialport
@flowfuse/node-red-dashboard
```

3. Importar el flujo:

```text
Menú ☰ → Importar
```

Seleccionar el archivo:

```text
node-red/flows/telemetria_dashboard_flow.json
```

4. Revisar el puerto serial:

Abrir el nodo **COM4** y cambiarlo por el COM de la ESP32 receptora si es necesario.

Configuración serial:

```text
Baud rate: 115200
Data bits: 8
Parity: None
Stop bits: 1
Split input: on character \n
Deliver: ASCII strings
```

5. Cerrar el Serial Monitor de Arduino.

6. Presionar:

```text
Instanciar
```

7. Abrir el dashboard:

```text
http://localhost:1880/dashboard/page1
```

## Variables del dashboard

El receptor envía a Node-RED esta línea CSV:

```csv
seq,t_us,ax,ay,az,gx,gy,gz,roll,pitch,g_lat,g_lon,yaw_rate,rssi,snr,lost,total
```

Se visualiza:

- Roll
- Pitch
- G lateral
- G longitudinal
- Yaw rate
- RSSI LoRa
- SNR
- Paquetes perdidos

## Importante

Node-RED y Arduino Serial Monitor no pueden usar el mismo COM al mismo tiempo.
Si Node-RED no recibe datos, cerrar el Serial Monitor de Arduino.
