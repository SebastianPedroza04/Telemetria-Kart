"""
analizar_sesion_lora.py — Gráficas de una sesión de telemetría LoRa.

Toma el CSV que guarda puente_serial_mqtt.py (data/lora/lora_*.csv) y genera:
  1. Roll y pitch vs tiempo
  2. G lateral y G longitudinal vs tiempo
  3. Yaw rate vs tiempo
  4. Calidad del enlace: RSSI, SNR y pérdida acumulada
Más un resumen numérico de la sesión.

Uso:
    python analizar_sesion_lora.py data\\lora\\lora_20260721_122409.csv
    python analizar_sesion_lora.py          (usa el archivo más reciente)
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def main(path=None):
    if path is None:
        candidatos = sorted(glob.glob("data/lora/lora_*.csv"))
        if not candidatos:
            sys.exit("No hay archivos data/lora/lora_*.csv")
        path = candidatos[-1]
        print(f"(usando el más reciente: {path})")

    df = pd.read_csv(path, comment="#", on_bad_lines="skip")
    df = df.apply(pd.to_numeric, errors="coerce").dropna(subset=["seq", "t_us"])
    if len(df) == 0:
        sys.exit("Archivo sin datos válidos.")
    t = (df["t_rx"] - df["t_rx"].iloc[0]).to_numpy()   # tiempo de recepción, s
    dur = t[-1]
    perdida = 100.0 * df["lost"].iloc[-1] / df["total"].iloc[-1] if df["total"].iloc[-1] else 0

    print(f"\n=== Sesión: {Path(path).name} ===")
    print(f"Paquetes: {len(df)}  Duración: {dur/60:.1f} min  Tasa: {len(df)/dur:.1f}/s")
    print(f"Pérdida de radio: {perdida:.2f} %  RSSI medio: {df.rssi.mean():.0f} dBm "
          f"(mín {df.rssi.min():.0f})  SNR medio: {df.snr.mean():.1f} dB")
    print(f"Roll:  min {df.roll.min():+.1f}°  max {df.roll.max():+.1f}°")
    print(f"Pitch: min {df.pitch.min():+.1f}°  max {df.pitch.max():+.1f}°")
    print(f"G lat: min {df.g_lat.min():+.2f} g  max {df.g_lat.max():+.2f} g")
    print(f"G lon: min {df.g_lon.min():+.2f} g  max {df.g_lon.max():+.2f} g")
    print(f"Yaw rate: min {df.yaw_rate.min():+.1f} °/s  max {df.yaw_rate.max():+.1f} °/s")

    fig, axs = plt.subplots(4, 1, figsize=(13, 12), sharex=True)

    axs[0].plot(t, df.roll, "b", lw=1.0, label="roll")
    axs[0].plot(t, df.pitch, "r", lw=1.0, label="pitch")
    axs[0].set_ylabel("ángulo [°]")
    axs[0].set_title("Inclinación (Kalman a bordo)")
    axs[0].legend(loc="upper right"); axs[0].grid(alpha=.3)

    axs[1].plot(t, df.g_lat, "m", lw=1.0, label="G lateral")
    axs[1].plot(t, df.g_lon, "c", lw=1.0, label="G longitudinal")
    axs[1].set_ylabel("aceleración [g]")
    axs[1].set_title("Fuerzas G")
    axs[1].legend(loc="upper right"); axs[1].grid(alpha=.3)

    axs[2].plot(t, df.yaw_rate, "g", lw=1.0)
    axs[2].set_ylabel("yaw rate [°/s]")
    axs[2].set_title("Velocidad de giro (guiñada)")
    axs[2].grid(alpha=.3)

    ax3b = axs[3].twinx()
    axs[3].plot(t, df.rssi, color="#1a3a5c", lw=1.0, label="RSSI")
    ax3b.plot(t, 100.0 * df.lost / df.total.clip(lower=1), color="#c0392b",
              lw=1.2, ls="--", label="pérdida acumulada")
    axs[3].set_ylabel("RSSI [dBm]", color="#1a3a5c")
    ax3b.set_ylabel("pérdida [%]", color="#c0392b")
    axs[3].set_xlabel("tiempo [s]")
    axs[3].set_title("Calidad del enlace LoRa")
    axs[3].grid(alpha=.3)

    fig.suptitle(f"Sesión LoRa — {Path(path).name}", fontsize=13)
    fig.tight_layout()
    out = str(Path(path).with_suffix("")) + "_graficas.png"
    fig.savefig(out, dpi=150)
    print(f"\nGuardado: {out}")
    print("Ábrelo desde el explorador de archivos (carpeta kart\\data\\lora).")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
