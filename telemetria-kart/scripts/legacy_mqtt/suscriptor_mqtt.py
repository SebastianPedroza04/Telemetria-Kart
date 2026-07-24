"""
suscriptor_mqtt.py — Estación base: recibe la telemetría del kart por MQTT,
la guarda en CSV y mide pérdida de paquetes con el contador 'seq'.

Uso:
    pip install paho-mqtt
    python suscriptor_mqtt.py                    # broker en esta misma PC
    python suscriptor_mqtt.py --host 192.168.1.5 # broker en otra máquina
Detener: Ctrl+C (imprime el resumen de pérdidas).
"""
import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--topic", default="kart/#")
    args = ap.parse_args()

    Path("data/mqtt").mkdir(parents=True, exist_ok=True)
    fname = Path("data/mqtt") / f"mqtt_{datetime.now():%Y%m%d_%H%M%S}.csv"
    f = open(fname, "w", newline="")
    f.write("t_rx,topic,ts,seq,ax,ay,az,gx,gy,gz\n")

    stats = {"n": 0, "perdidos": 0, "ultimo_seq": None, "t0": time.time()}

    def on_connect(client, userdata, flags, rc, props=None):
        print(f"Conectado al broker {args.host}:{args.port} (rc={rc}). "
              f"Suscrito a '{args.topic}'. Guardando en {fname}")
        client.subscribe(args.topic)

    def on_message(client, userdata, msg):
        t_rx = time.time()
        try:
            d = json.loads(msg.payload)
        except json.JSONDecodeError:
            print(f"[{msg.topic}] no-JSON: {msg.payload[:60]}")
            return

        if "seq" in d:  # medir pérdida de paquetes
            s = d["seq"]
            if stats["ultimo_seq"] is not None:
                salto = s - stats["ultimo_seq"]
                # el ESP32 publica 1 de cada 10 muestras: salto esperado = 10
                if 0 < salto != 10:
                    stats["perdidos"] += max(0, salto // 10 - 1)
            stats["ultimo_seq"] = s

        if "ax" in d:  # dato IMU -> CSV
            stats["n"] += 1
            f.write(f"{t_rx:.3f},{msg.topic},{d.get('ts','')},{d.get('seq','')},"
                    f"{d.get('ax','')},{d.get('ay','')},{d.get('az','')},"
                    f"{d.get('gx','')},{d.get('gy','')},{d.get('gz','')}\n")
            if stats["n"] % 50 == 0:
                dur = t_rx - stats["t0"]
                tot = stats["n"] + stats["perdidos"]
                loss = 100 * stats["perdidos"] / tot if tot else 0
                print(f"\r{stats['n']} msgs ({stats['n']/dur:.1f}/s) "
                      f"perdida={loss:.2f} %", end="")
        else:          # eventos (status, lap...): mostrarlos
            print(f"\n[{msg.topic}] {d}")

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.on_connect = on_connect
    c.on_message = on_message
    c.connect(args.host, args.port, 60)
    try:
        c.loop_forever()
    except KeyboardInterrupt:
        pass
    finally:
        f.close()
        tot = stats["n"] + stats["perdidos"]
        loss = 100 * stats["perdidos"] / tot if tot else 0
        print(f"\n\nResumen: {stats['n']} recibidos, ~{stats['perdidos']} perdidos "
              f"({loss:.2f} %) -> {fname}")

if __name__ == "__main__":
    main()
