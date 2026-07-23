"""
puente_serial_mqtt.py — Puente entre el receptor LoRa (ESP32 base por USB)
y el broker MQTT. Además guarda TODO en CSV (respaldo local de la sesión).

Entrada serial esperada (una línea por paquete LoRa):
    seq,t_us,ax,ay,az,gx,gy,gz,roll,pitch,g_lat,g_lon,yaw_rate,rssi,snr,lost,total
Publica:
    kart/K01/imu/filt  {seq,ts,ax..gz,roll,pitch,g_lat,g_lon,yaw}
    kart/K01/radio     {seq,rssi,snr,lost,total,perdida_pct}

Uso:
    pip install pyserial paho-mqtt
    python puente_serial_mqtt.py COM3                  # puerto del ESP32 base
    python puente_serial_mqtt.py COM3 --baud 115200 --broker localhost
Detener: Ctrl+C (imprime el resumen y deja el CSV en data/lora/).
"""
import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import serial
import paho.mqtt.client as mqtt

CAMPOS = ["seq", "t_us", "ax", "ay", "az", "gx", "gy", "gz",
          "roll", "pitch", "g_lat", "g_lon", "yaw_rate",
          "rssi", "snr", "lost", "total"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("puerto")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--broker", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    args = ap.parse_args()

    Path("data/lora").mkdir(parents=True, exist_ok=True)
    fname = Path("data/lora") / f"lora_{datetime.now():%Y%m%d_%H%M%S}.csv"
    f = open(fname, "w", newline="", encoding="utf-8", errors="replace")
    f.write("t_rx," + ",".join(CAMPOS) + "\n")

    cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="puente-lora")
    cli.connect(args.broker, args.port, 60)
    cli.loop_start()

    ser = serial.Serial(args.puerto, args.baud, timeout=2)
    try:
        ser.set_buffer_size(rx_size=1 << 20)
    except Exception:
        pass
    ser.reset_input_buffer()
    print(f"Puente: {args.puerto}@{args.baud} -> mqtt://{args.broker}:{args.port}"
          f"  |  respaldo: {fname}")

    n, malos = 0, 0
    t0 = time.time()
    try:
        while True:
            linea = ser.readline().decode(errors="replace").strip()
            if not linea or linea.startswith("#"):
                continue
            v = linea.split(",")
            if len(v) != len(CAMPOS):
                malos += 1
                continue
            try:
                d = {k: float(x) for k, x in zip(CAMPOS, v)}
            except ValueError:
                malos += 1
                continue

            f.write(f"{time.time():.3f},{linea}\n")
            cli.publish("kart/K01/imu/filt", json.dumps({
                "seq": int(d["seq"]), "ts": int(d["t_us"]),
                "ax": d["ax"], "ay": d["ay"], "az": d["az"],
                "gx": d["gx"], "gy": d["gy"], "gz": d["gz"],
                "roll": d["roll"], "pitch": d["pitch"],
                "g_lat": d["g_lat"], "g_lon": d["g_lon"], "yaw": d["yaw_rate"]}))
            perdida = 100.0 * d["lost"] / d["total"] if d["total"] else 0.0
            cli.publish("kart/K01/radio", json.dumps({
                "seq": int(d["seq"]), "rssi": d["rssi"], "snr": d["snr"],
                "lost": int(d["lost"]), "total": int(d["total"]),
                "perdida_pct": round(perdida, 2)}))
            n += 1
            if n % 50 == 0:
                print(f"\r{n} paquetes ({n/(time.time()-t0):.1f}/s) "
                      f"corruptos={malos} perdida_radio={perdida:.1f} %", end="")
    except KeyboardInterrupt:
        pass
    finally:
        f.close(); ser.close(); cli.loop_stop()
        print(f"\nFin: {n} paquetes, {malos} corruptos -> {fname}")

if __name__ == "__main__":
    main()
