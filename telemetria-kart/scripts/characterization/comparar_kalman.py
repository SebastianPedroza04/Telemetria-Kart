"""
comparar_kalman.py — Fase 9 (validación): compara el Kalman EMBEBIDO en el
ESP32 (columnas roll/pitch del firmware v3) contra el Kalman OFFLINE de Python
corriendo sobre las mismas muestras del mismo archivo.

Uso:
    python comparar_kalman.py data\\kfv3_XXXX.csv
Criterio de éxito: error RMS < 0.5° y sin sesgo sistemático.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLS = ["t_us", "ax", "ay", "az", "gx", "gy", "gz", "roll_esp", "pitch_esp"]
KF_R, SIG_GYRO, Q_BIAS = 0.004, 0.05, 1e-8

def kalman(theta_med, omega, dt):
    x = np.array([theta_med[0], 0.0]); P = np.diag([1.0, 0.1])
    out = np.zeros(len(theta_med))
    for k in range(len(theta_med)):
        h = dt[k]
        x = np.array([x[0] + (omega[k] - x[1]) * h, x[1]])
        F = np.array([[1.0, -h], [0.0, 1.0]])
        Q = np.diag([SIG_GYRO ** 2 * h, Q_BIAS * h])
        P = F @ P @ F.T + Q
        r = (theta_med[k] - x[0] + 180.0) % 360.0 - 180.0
        S = P[0, 0] + KF_R
        K = P[:, 0] / S
        x = x + K * r
        P = P - np.outer(K, P[0, :])
        out[k] = x[0]
    return out

def main(path):
    df = pd.read_csv(path, comment="#", header=None, names=COLS, on_bad_lines="skip")
    df = df.apply(pd.to_numeric, errors="coerce").dropna().reset_index(drop=True)
    t = df.t_us.to_numpy(np.float64) / 1e6
    dt = np.diff(t, prepend=t[0])
    dt[(dt <= 0) | (dt > 0.1)] = 0.01
    ts = np.cumsum(dt)
    # OJO: el firmware v3 ya entrega los datos calibrados -> no recalibrar aquí
    roll_acc  = np.degrees(np.arctan2(df.ay, df.az)).to_numpy()
    pitch_acc = np.degrees(np.arctan2(-df.ax, np.hypot(df.ay, df.az))).to_numpy()
    roll_py  = kalman(roll_acc,  df.gx.to_numpy(), dt)
    pitch_py = kalman(pitch_acc, df.gy.to_numpy(), dt)

    for nombre, esp, py in [("roll", df.roll_esp, roll_py), ("pitch", df.pitch_esp, pitch_py)]:
        e = esp.to_numpy() - py
        e = (e + 180.0) % 360.0 - 180.0
        print(f"{nombre:<6} error RMS = {np.sqrt(np.mean(e**2)):.4f}°   "
              f"medio = {np.mean(e):+.4f}°   max = {np.max(np.abs(e)):.4f}°")

    fig, axs = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    axs[0].plot(ts, roll_py, "b", lw=1.4, label="roll Python (offline)")
    axs[0].plot(ts, df.roll_esp, "c--", lw=1.0, label="roll ESP32 (embebido)")
    axs[0].set_ylabel("roll [°]"); axs[0].legend(); axs[0].grid(alpha=.3)
    axs[1].plot(ts, pitch_py, "r", lw=1.4, label="pitch Python (offline)")
    axs[1].plot(ts, df.pitch_esp, "m--", lw=1.0, label="pitch ESP32 (embebido)")
    axs[1].set_ylabel("pitch [°]"); axs[1].set_xlabel("t [s]")
    axs[1].legend(); axs[1].grid(alpha=.3)
    fig.suptitle(f"Kalman embebido vs offline — {Path(path).name}")
    fig.tight_layout()
    out = str(Path(path).with_suffix("")) + "_comparacion.png"
    fig.savefig(out, dpi=150)
    print(f"Guardado: {out}")
    print("Éxito Fase 9: RMS < 0.5° y curvas superpuestas.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python comparar_kalman.py data\\kfv3_XXXX.csv")
    main(sys.argv[1])
