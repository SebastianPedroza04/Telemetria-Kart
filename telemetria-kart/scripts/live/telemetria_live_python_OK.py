# telemetria_live_python_OK.py
# Telemetría Kart en vivo SIN Node-RED.
#
# Lee la ESP32 base por serial, grafica en vivo y guarda CSV.
#
# Uso:
#   pip install pyserial matplotlib numpy pandas
#   python C:\TelemetriaKart\telemetria_live_python_OK.py COM4
#   python C:\TelemetriaKart\telemetria_live_python_OK.py COM4 --raw
#
# IMPORTANTE:
# Cierra Node-RED y Arduino Serial Monitor antes de correr este script.
# El puerto COM no puede ser leído por varios programas al mismo tiempo.

import argparse
import csv
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import serial
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation


FIELDS = [
    "seq", "t_ms", "roll", "pitch", "g_lat", "g_lon", "yaw_rate",
    "lat", "lon", "gps_speed_mps", "gps_course_deg", "gps_sats",
    "gps_hdop", "gps_fix", "rssi", "snr", "lost", "total"
]

CSV_FIELDS = ["t_pc"] + FIELDS


def parse_line(line):
    line = line.strip()
    if not line:
        return None

    # Mensajes de arranque o encabezado.
    if line.startswith("#") or line.startswith("seq") or line.startswith("ets") or line.startswith("rst:"):
        return None

    # Si por error llega con prefijo K, lo quitamos.
    if line.startswith("K,"):
        line = line[2:]

    p = line.split(",")
    if len(p) < 18:
        return None

    try:
        d = {
            "seq": int(float(p[0])),
            "t_ms": float(p[1]),
            "roll": float(p[2]),
            "pitch": float(p[3]),
            "g_lat": float(p[4]),
            "g_lon": float(p[5]),
            "yaw_rate": float(p[6]),
            "lat": float(p[7]),
            "lon": float(p[8]),
            "gps_speed_mps": float(p[9]),
            "gps_course_deg": float(p[10]),
            "gps_sats": int(float(p[11])),
            "gps_hdop": float(p[12]),
            "gps_fix": int(float(p[13])),
            "rssi": float(p[14]),
            "snr": float(p[15]),
            "lost": int(float(p[16])),
            "total": int(float(p[17])),
        }
        d["t_pc"] = datetime.now().isoformat(timespec="milliseconds")
        return d
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port", help="Puerto serial. Ejemplo: COM4")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--max-points", type=int, default=240)
    ap.add_argument("--raw", action="store_true", help="Imprime líneas serial crudas en consola.")
    args = ap.parse_args()

    outdir = Path(r"C:\TelemetriaKart\data")
    outdir.mkdir(parents=True, exist_ok=True)
    out_csv = outdir / f"live_python_{datetime.now():%Y%m%d_%H%M%S}.csv"

    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.25)
    except Exception as e:
        print(f"ERROR abriendo {args.port}: {e}")
        print("Cierra Node-RED y Arduino Serial Monitor. Revisa que el puerto sea el de la ESP32 base.")
        sys.exit(1)

    ser.reset_input_buffer()

    data = deque(maxlen=args.max_points)
    last_raw_time = time.time()
    parsed_count = 0
    raw_count = 0

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()

        fig, axes = plt.subplots(4, 1, figsize=(11, 9), sharex=True)
        fig.suptitle(f"Telemetría Kart en vivo - {args.port}")
        status_text = fig.text(0.5, 0.02, "Esperando datos seriales...", ha="center", fontsize=10)

        def drain_serial():
            nonlocal raw_count, parsed_count, last_raw_time

            # Leer varias líneas por frame para no atrasarse.
            for _ in range(50):
                raw = ser.readline()
                if not raw:
                    break

                line = raw.decode(errors="replace").strip()
                raw_count += 1
                last_raw_time = time.time()

                if args.raw:
                    print("RAW:", line)

                d = parse_line(line)
                if d is None:
                    continue

                parsed_count += 1
                data.append(d)
                writer.writerow(d)
                f.flush()

        def update(_):
            drain_serial()

            for ax in axes:
                ax.clear()
                ax.grid(True, alpha=0.3)

            if len(data) < 2:
                axes[0].text(
                    0.5, 0.5,
                    "Sin datos parseados aún.\n"
                    "Revisa: Node-RED cerrado, COM correcto, receptor encendido,\n"
                    "emisor transmitiendo, baud 115200.\n"
                    f"Líneas crudas leídas: {raw_count}",
                    ha="center", va="center", transform=axes[0].transAxes
                )
                status_text.set_text(f"CSV: {out_csv} | crudas={raw_count} | parseadas={parsed_count}")
                return []

            t0 = data[0]["t_ms"] / 1000.0
            t = [d["t_ms"] / 1000.0 - t0 for d in data]

            axes[0].plot(t, [d["roll"] for d in data], label="Roll [°]")
            axes[0].plot(t, [d["pitch"] for d in data], label="Pitch [°]")
            axes[0].plot(t, [d["yaw_rate"] for d in data], label="Yaw rate [°/s]")
            axes[0].set_title("Orientación y giro")
            axes[0].legend(loc="upper right")

            axes[1].plot(t, [d["g_lat"] for d in data], label="G lateral [G]")
            axes[1].plot(t, [d["g_lon"] for d in data], label="G longitudinal [G]")
            axes[1].plot(t, [d["gps_speed_mps"] for d in data], label="Velocidad GPS [m/s]")
            axes[1].set_title("Dinámica")
            axes[1].legend(loc="upper right")

            axes[2].plot(t, [d["rssi"] for d in data], label="RSSI [dBm]")
            axes[2].plot(t, [d["snr"] for d in data], label="SNR [dB]")
            axes[2].plot(t, [d["lost"] for d in data], label="Perdidos")
            axes[2].set_title("Enlace LoRa")
            axes[2].legend(loc="upper right")

            axes[3].plot(t, [d["gps_sats"] for d in data], label="Satélites")
            axes[3].plot(t, [d["gps_hdop"] for d in data], label="HDOP")
            axes[3].plot(t, [d["gps_fix"] for d in data], label="Fix")
            axes[3].set_title("GPS")
            axes[3].set_xlabel("Tiempo [s]")
            axes[3].legend(loc="upper right")

            last = data[-1]
            fig.suptitle(
                f"Telemetría Kart en vivo - {args.port} | "
                f"GPS fix={last['gps_fix']} sats={last['gps_sats']} "
                f"RSSI={last['rssi']:.0f} dBm SNR={last['snr']:.1f} dB"
            )
            status_text.set_text(f"CSV: {out_csv} | crudas={raw_count} | parseadas={parsed_count}")
            return []

        ani = FuncAnimation(fig, update, interval=500, cache_frame_data=False)

        try:
            plt.show()
        finally:
            ser.close()
            print(f"CSV guardado en: {out_csv}")


if __name__ == "__main__":
    main()
