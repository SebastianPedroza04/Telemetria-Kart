"""
kalman_offline.py — Fase 8: filtro de Kalman (roll y pitch) sobre un CSV grabado.

Estado por ángulo: x = [theta, bias_gyro]. Predicción con el giroscopio,
corrección con el ángulo del acelerómetro. R y Q derivados de la
caracterización propia del BMI160 (reposo + seis posiciones).

Uso:
    python kalman_offline.py data\\mov_1_XXXX.csv
    python kalman_offline.py data\\reposo_v4_XXXX.csv --qscale 10   # barrido de Q
Genera: <archivo>_kalman.png y métricas en consola.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

G = 9.80665
COLS = ["t_us", "ax", "ay", "az", "gx", "gy", "gz"]

# ---- Calibración medida (seis posiciones + reposo, 17/07/2026) ----
OFFSET = {"ax": 0.319, "ay": -0.236, "az": -0.471}       # m/s²
SENS   = {"ax": 1.0041, "ay": 0.9931, "az": 0.9969}
BIAS_G = {"gx": -0.065, "gy": 0.194, "gz": -0.086}       # °/s (estado inicial)

# ---- Parámetros del filtro (de la caracterización) ----
R_DEG2       = 0.004     # varianza del ángulo por acelerómetro, (°)²
SIGMA_GYRO   = 0.05      # °/s (ruido del gyro en reposo)
Q_BIAS_BASE  = 1e-8      # caminata del bias, (°/s)²·s

def cargar(path):
    df = pd.read_csv(path, comment="#", header=None, names=COLS, on_bad_lines="skip")
    df = df.apply(pd.to_numeric, errors="coerce").dropna().reset_index(drop=True)
    # aplicar calibración
    for e in ["ax", "ay", "az"]:
        df[e] = (df[e] - OFFSET[e]) / SENS[e]
    for e in ["gx", "gy", "gz"]:
        df[e] = df[e] - BIAS_G[e]     # el KF estimará el residual
    t = df["t_us"].to_numpy(np.float64) / 1e6
    dt = np.diff(t, prepend=t[0])
    dt[(dt <= 0) | (dt > 0.1)] = 0.01   # sanear saltos (reset DTR, huecos)
    df["dt"] = dt
    df["t_s"] = np.cumsum(dt)
    return df

def kalman_angulo(theta_med, omega, dt, R, q_theta_scale=1.0):
    """KF 2x2: estado [theta, bias]. omega en °/s, theta_med en °."""
    n = len(theta_med)
    x = np.array([theta_med[0], 0.0])
    P = np.diag([1.0, 0.1])
    out = np.zeros((n, 2)); K_hist = np.zeros(n); resid = np.zeros(n)
    for k in range(n):
        h = dt[k]
        # Predicción
        x = np.array([x[0] + (omega[k] - x[1]) * h, x[1]])
        F = np.array([[1.0, -h], [0.0, 1.0]])
        Q = np.diag([(SIGMA_GYRO ** 2) * h * q_theta_scale, Q_BIAS_BASE * h])
        P = F @ P @ F.T + Q
        # Corrección (H = [1 0])
        S = P[0, 0] + R
        K = P[:, 0] / S
        r = theta_med[k] - x[0]
        r = (r + 180.0) % 360.0 - 180.0   # residuo envuelto a [-180, 180]
        x = x + K * r
        P = P - np.outer(K, P[0, :])
        out[k] = x; K_hist[k] = K[0]; resid[k] = r
    return out[:, 0], out[:, 1], K_hist, resid

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--qscale", type=float, default=1.0,
                    help="multiplicador de Q_theta para barrido (0.1, 1, 10, 100)")
    a = ap.parse_args()

    df = cargar(a.csv)
    print(f"{a.csv}: {len(df)} muestras, {df.t_s.iloc[-1]:.1f} s, qscale={a.qscale}")

    # Ángulos por acelerómetro (grados)
    roll_acc  = np.degrees(np.arctan2(df.ay, df.az))
    pitch_acc = np.degrees(np.arctan2(-df.ax, np.hypot(df.ay, df.az)))

    dt = df.dt.to_numpy()
    roll_kf,  bias_x, _, res_r = kalman_angulo(roll_acc.to_numpy(),  df.gx.to_numpy(), dt, R_DEG2, a.qscale)
    pitch_kf, bias_y, _, res_p = kalman_angulo(pitch_acc.to_numpy(), df.gy.to_numpy(), dt, R_DEG2, a.qscale)

    # Referencia "solo gyro" (muestra la deriva que el KF corrige)
    roll_gyro  = roll_acc.iloc[0]  + np.cumsum(df.gx.to_numpy() * dt)
    pitch_gyro = pitch_acc.iloc[0] + np.cumsum(df.gy.to_numpy() * dt)

    print(f"Roll : sigma_acc={roll_acc.std():.3f}°  sigma_KF={np.std(roll_kf):.3f}°  "
          f"bias_gx final={bias_x[-1]:+.3f}°/s  residuo sigma={np.std(res_r):.3f}°")
    print(f"Pitch: sigma_acc={pitch_acc.std():.3f}°  sigma_KF={np.std(pitch_kf):.3f}°  "
          f"bias_gy final={bias_y[-1]:+.3f}°/s  residuo sigma={np.std(res_p):.3f}°")
    print("(En reposo: sigma_KF << sigma_acc y residuo ~ ruido blanco = filtro sano)")

    fig, axs = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    axs[0].plot(df.t_s, roll_acc,  color="0.75", lw=0.6, label="roll acel (crudo)")
    axs[0].plot(df.t_s, roll_gyro, "g--", lw=0.9, label="roll solo gyro (deriva)")
    axs[0].plot(df.t_s, roll_kf,   "b",   lw=1.2, label="roll Kalman")
    axs[0].set_ylabel("roll [°]"); axs[0].legend(loc="upper right"); axs[0].grid(alpha=.3)
    axs[1].plot(df.t_s, pitch_acc,  color="0.75", lw=0.6, label="pitch acel (crudo)")
    axs[1].plot(df.t_s, pitch_gyro, "g--", lw=0.9, label="pitch solo gyro (deriva)")
    axs[1].plot(df.t_s, pitch_kf,   "r",   lw=1.2, label="pitch Kalman")
    axs[1].set_ylabel("pitch [°]"); axs[1].legend(loc="upper right"); axs[1].grid(alpha=.3)
    axs[2].plot(df.t_s, bias_x, label="bias gx estimado")
    axs[2].plot(df.t_s, bias_y, label="bias gy estimado")
    axs[2].set_ylabel("bias [°/s]"); axs[2].set_xlabel("t [s]")
    axs[2].legend(loc="upper right"); axs[2].grid(alpha=.3)
    fig.suptitle(f"Kalman offline — {Path(a.csv).name} — R={R_DEG2} (°)², qscale={a.qscale}")
    fig.tight_layout()
    out = str(Path(a.csv).with_suffix("")) + f"_kalman_q{a.qscale:g}.png"
    fig.savefig(out, dpi=150)
    print(f"Guardado: {out}")

if __name__ == "__main__":
    main()
