"""
puente_mqtt_v2.py — Puente LoRa -> MQTT que ADEMÁS calcula velocidad y distancia.

Lee el puerto serie de la ESP32 base (formato de 18 columnas del firmware final),
calcula en el computador la velocidad fusionada y la distancia recorrida, y
publica todo a Mosquitto. Guarda también un CSV de respaldo.

No requiere ningún cambio en el firmware: usa la aceleración (g_lon) y la
velocidad del GPS (gps_speed_mps) que ya vienen en el paquete.

Publica en:
    kart/K01/imu      roll, pitch, g_lat, g_lon, yaw_rate
    kart/K01/gps      lat, lon, velocidad GPS, rumbo, satélites, hdop, fix
    kart/K01/derivado velocidad fusionada, velocidad por IMU, distancia, bias
    kart/K01/radio    rssi, snr, perdidos, total, % de pérdida

Uso:
    pip install pyserial paho-mqtt
    python puente_mqtt_v2.py COM4
    python puente_mqtt_v2.py COM4 --rgps 0.3        (si el GPS va saltón)
    python puente_mqtt_v2.py COM4 --broker 192.168.0.13

Requiere Mosquitto corriendo antes:
    mosquitto.exe -c kart.conf -v
"""
import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import serial
import paho.mqtt.client as mqtt

G = 9.80665

# Formato que entrega la base con el firmware final (18 columnas)
CAMPOS = ["seq", "t_ms", "roll", "pitch", "g_lat", "g_lon", "yaw_rate",
          "lat", "lon", "gps_speed_mps", "gps_course_deg", "gps_sats",
          "gps_hdop", "gps_fix", "rssi", "snr", "lost", "total"]


class KalmanVelocidad:
    """Fusiona la aceleración longitudinal con la velocidad del GPS.

    Estado: [v, b]  ->  velocidad y bias residual del acelerómetro.
    El bias es lo que hace que integrar la aceleración sola se desvíe; el
    filtro lo va estimando y por eso su salida no deriva.
    """

    def __init__(self, r_gps=0.2, sigma_a=0.05, q_bias=1e-6):
        self.v = 0.0
        self.b = 0.0
        self.P = [[1.0, 0.0], [0.0, 0.1]]
        self.R = r_gps ** 2
        self.sa = sigma_a
        self.qb = q_bias

    def predecir(self, a_long, dt):
        self.v += (a_long - self.b) * dt
        P = self.P
        qv = (self.sa ** 2) * dt
        self.P = [
            [P[0][0] + dt * (dt * P[1][1] - P[0][1] - P[1][0]) + qv,
             P[0][1] - dt * P[1][1]],
            [P[1][0] - dt * P[1][1],
             P[1][1] + self.qb * dt]]

    def corregir(self, v_gps):
        P = self.P
        S = P[0][0] + self.R
        k0, k1 = P[0][0] / S, P[1][0] / S
        r = v_gps - self.v
        self.v += k0 * r
        self.b += k1 * r
        p00, p01 = P[0][0], P[0][1]
        self.P = [[p00 - k0 * p00, p01 - k0 * p01],
                  [P[1][0] - k1 * p00, P[1][1] - k1 * p01]]


def parsear(linea):
    linea = linea.strip()
    if not linea or linea.startswith("#") or linea.startswith("seq"):
        return None
    if linea.startswith("ets") or linea.startswith("rst:"):
        return None
    if linea.startswith("K,"):
        linea = linea[2:]
    partes = linea.split(",")
    if len(partes) < 18:
        return None
    try:
        return {k: float(v) for k, v in zip(CAMPOS, partes[:18])}
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("puerto")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--broker", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--rgps", type=float, default=0.2,
                    help="ruido de la velocidad GPS en m/s")
    args = ap.parse_args()

    Path("data/lora").mkdir(parents=True, exist_ok=True)
    archivo = Path("data/lora") / f"sesion_{datetime.now():%Y%m%d_%H%M%S}.csv"
    f = open(archivo, "w", newline="", encoding="utf-8")
    w = csv.writer(f)
    w.writerow(["t_pc"] + CAMPOS + ["v_kalman", "v_imu", "distancia_m", "bias_acc"])

    cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="puente-kart")
    try:
        cli.connect(args.broker, args.port, 60)
    except Exception as e:
        sys.exit(f"ERROR conectando al broker {args.broker}:{args.port}: {e}\n"
                 "¿Está corriendo Mosquitto?")
    cli.loop_start()

    try:
        ser = serial.Serial(args.puerto, args.baud, timeout=2)
    except Exception as e:
        sys.exit(f"ERROR abriendo {args.puerto}: {e}\n"
                 "Cierra Node-RED y el monitor serie de Arduino.")
    try:
        ser.set_buffer_size(rx_size=1 << 20)
    except Exception:
        pass
    ser.reset_input_buffer()

    kf = KalmanVelocidad(r_gps=args.rgps)
    t_ant = None
    v_imu = 0.0
    dist = 0.0
    n = malos = 0
    t0 = time.time()
    seq_gps_ant = None

    print(f"Puente v2: {args.puerto}@{args.baud} -> mqtt://{args.broker}:{args.port}")
    print(f"Respaldo: {archivo}")
    print("Calculando velocidad fusionada y distancia. Ctrl+C para terminar.\n")

    try:
        while True:
            linea = ser.readline().decode(errors="replace")
            d = parsear(linea)
            if d is None:
                if linea.strip() and not linea.startswith("#"):
                    malos += 1
                continue

            t = d["t_ms"] / 1000.0
            if t_ant is None:
                t_ant = t
                continue
            dt = t - t_ant
            t_ant = t
            if dt <= 0 or dt > 5:
                continue

            a_long = d["g_lon"] * G          # aceleración longitudinal [m/s²]
            v_gps = d["gps_speed_mps"]
            hay_fix = d["gps_fix"] >= 1

            # Integración pura (para comparar: se desvía)
            v_imu += a_long * dt

            # Fusión
            kf.predecir(a_long, dt)
            # Solo corregimos si el GPS cambió de valor: llega a 5 Hz, no a la
            # tasa de los paquetes, y repetir la misma medida le daría un peso
            # que no le corresponde.
            if hay_fix and v_gps != seq_gps_ant:
                kf.corregir(v_gps)
                seq_gps_ant = v_gps

            v_kf = max(kf.v, 0.0)
            dist += v_kf * dt

            # --- Publicar ---
            cli.publish("kart/K01/imu", json.dumps({
                "seq": int(d["seq"]), "roll": d["roll"], "pitch": d["pitch"],
                "g_lat": d["g_lat"], "g_lon": d["g_lon"],
                "a_long": round(a_long, 3), "yaw_rate": d["yaw_rate"]}))

            cli.publish("kart/K01/gps", json.dumps({
                "lat": d["lat"], "lon": d["lon"], "v_gps": v_gps,
                "rumbo": d["gps_course_deg"], "sats": int(d["gps_sats"]),
                "hdop": d["gps_hdop"], "fix": int(d["gps_fix"])}))

            cli.publish("kart/K01/derivado", json.dumps({
                "velocidad_ms": round(v_kf, 2),
                "velocidad_kmh": round(v_kf * 3.6, 1),
                "velocidad_solo_imu": round(v_imu, 2),
                "distancia_m": round(dist, 1),
                "bias_acc": round(kf.b, 4)}))

            perdida = 100.0 * d["lost"] / max(d["lost"] + d["total"], 1)
            cli.publish("kart/K01/radio", json.dumps({
                "rssi": d["rssi"], "snr": d["snr"],
                "lost": int(d["lost"]), "total": int(d["total"]),
                "perdida_pct": round(perdida, 2)}))

            w.writerow([datetime.now().isoformat(timespec="milliseconds")]
                       + [d[k] for k in CAMPOS]
                       + [round(v_kf, 3), round(v_imu, 3), round(dist, 2),
                          round(kf.b, 4)])
            f.flush()

            n += 1
            if n % 20 == 0:
                print(f"\r{n} paq ({n/(time.time()-t0):.1f}/s) | "
                      f"v={v_kf*3.6:5.1f} km/h | dist={dist:6.0f} m | "
                      f"GPS={'ok ' if hay_fix else 'sin'} | "
                      f"RSSI={d['rssi']:.0f} | corruptos={malos}", end="")

    except KeyboardInterrupt:
        pass
    finally:
        f.close(); ser.close(); cli.loop_stop()
        print(f"\n\nFin: {n} paquetes, {malos} corruptos")
        print(f"Distancia total recorrida: {dist:.0f} m")
        print(f"Velocidad por integración pura al final: {v_imu:.1f} m/s "
              f"(si es absurda, esa es justo la deriva que corrige el filtro)")
        print(f"Bias del acelerómetro estimado: {kf.b:+.3f} m/s²")
        print(f"Archivo: {archivo}")


if __name__ == "__main__":
    main()
