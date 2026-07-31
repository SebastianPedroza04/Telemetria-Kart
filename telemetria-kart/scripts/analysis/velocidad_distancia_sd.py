"""
velocidad_distancia_sd.py — Velocidad y distancia desde los archivos de la microSD.

Calcula, a partir de un KARTxxx.CSV grabado a 100 Hz, la velocidad fusionada
(acelerómetro + GPS) y la distancia recorrida, usando el MISMO filtro que el
puente en vivo. La diferencia es la resolución: aquí se trabaja con las 100
muestras por segundo, no con las 2 que alcanza a transmitir la radio.

Compara tres estimaciones de velocidad:
  - integrando solo el acelerómetro  -> se desvía
  - la del GPS                       -> a saltos, con huecos cuando no hay fix
  - la fusionada por Kalman          -> suave y sin deriva

Y tres estimaciones de distancia: la del Kalman, la del GPS y la geométrica
(sumando las distancias entre puntos de latitud y longitud).

Detecta automáticamente el formato del archivo:
  - 18 columnas: firmware con GPS solo en SD
  - 21 columnas: firmware final (incluye rumbo, hdop y edad del fix)
  - 23 columnas: firmware final ya parcheado con vel_kf y dist_m

Uso:
    python velocidad_distancia_sd.py KART023.CSV
    python velocidad_distancia_sd.py D:\\KART023.CSV --rgps 0.3
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

G = 9.80665

COLS18 = ["seq", "t_us", "ax", "ay", "az", "gx", "gy", "gz", "roll", "pitch",
          "g_lat", "g_lon", "yaw_rate", "lat", "lon", "gps_spd", "sats", "gps_fix"]

COLS21 = ["seq", "t_us", "ax", "ay", "az", "gx", "gy", "gz", "roll", "pitch",
          "g_lat", "g_lon", "yaw_rate", "lat", "lon", "gps_spd", "gps_course",
          "sats", "gps_hdop", "gps_fix", "gps_age"]

COLS23 = COLS21 + ["vel_kf_esp", "dist_esp"]


def leer(path):
    """Lee el CSV detectando cuántas columnas trae."""
    prueba = pd.read_csv(path, comment="#", header=0, on_bad_lines="skip", nrows=5)
    n = prueba.shape[1]
    if n >= 23:
        nombres, fmt = COLS23, "23 columnas (firmware parcheado)"
    elif n >= 21:
        nombres, fmt = COLS21, "21 columnas (firmware final)"
    else:
        nombres, fmt = COLS18, "18 columnas (firmware anterior)"

    df = pd.read_csv(path, comment="#", header=None, names=nombres,
                     skiprows=1, on_bad_lines="skip")
    df = df.apply(pd.to_numeric, errors="coerce").dropna(subset=["seq"])
    df = df.reset_index(drop=True)
    if "gps_fix" not in df:
        df["gps_fix"] = (df.get("lat", 0) != 0).astype(int)
    print(f"{Path(path).name}: {len(df)} muestras, formato de {fmt}")
    return df


def kalman_velocidad(a_long, v_gps, hay_fix, dt, r_gps=0.2,
                     sigma_a=0.05, q_bias=1e-6):
    """Filtro de velocidad. Estado [v, bias del acelerómetro].

    Predice con la aceleración a 100 Hz y corrige solo cuando el GPS entrega
    una lectura nueva (el GPS va a 5-10 Hz, no a 100).
    """
    n = len(a_long)
    v = 0.0
    b = 0.0
    P = np.array([[1.0, 0.0], [0.0, 0.1]])
    R = r_gps ** 2

    v_out = np.zeros(n)
    b_out = np.zeros(n)
    v_gps_ant = None

    for k in range(n):
        h = dt[k]
        # Predicción
        v += (a_long[k] - b) * h
        F = np.array([[1.0, -h], [0.0, 1.0]])
        Qk = np.diag([(sigma_a ** 2) * h, q_bias * h])
        P = F @ P @ F.T + Qk

        # Corrección: solo con lectura NUEVA del GPS y con fix
        if hay_fix[k] and v_gps[k] != v_gps_ant:
            S = P[0, 0] + R
            K = P[:, 0] / S
            r = v_gps[k] - v
            v += K[0] * r
            b += K[1] * r
            P = P - np.outer(K, P[0, :])
            v_gps_ant = v_gps[k]

        v_out[k] = max(v, 0.0)   # el kart no va en reversa
        b_out[k] = b

    return v_out, b_out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--rgps", type=float, default=0.2,
                    help="ruido de la velocidad GPS en m/s")
    a = ap.parse_args()

    df = leer(a.csv)
    if len(df) < 50:
        sys.exit("Muy pocas muestras válidas.")

    t = df["t_us"].to_numpy(np.float64) / 1e6
    dt = np.diff(t, prepend=t[0])
    dt[(dt <= 0) | (dt > 0.5)] = 0.01
    ts = np.cumsum(dt)

    a_long = df["ax"].to_numpy()                    # ya viene calibrada
    v_gps = df["gps_spd"].to_numpy()
    fix = df["gps_fix"].to_numpy().astype(bool)

    # Tres estimaciones de velocidad
    v_imu = np.cumsum(a_long * dt)                  # integración pura
    v_kf, bias = kalman_velocidad(a_long, v_gps, fix, dt, r_gps=a.rgps)

    # Tres estimaciones de distancia
    d_kf = np.cumsum(v_kf * dt)
    d_gps = np.cumsum(np.where(fix, v_gps, 0) * dt)

    # Distancia geométrica a partir de lat/lon
    g = df[fix & (df["lat"] != 0)]
    d_geo = 0.0
    if len(g) > 5:
        lat0 = np.radians(g["lat"].mean())
        R = 6371000.0
        x = np.radians(g["lon"] - g["lon"].mean()) * R * np.cos(lat0)
        y = np.radians(g["lat"] - g["lat"].mean()) * R
        paso = np.hypot(np.diff(x), np.diff(y))
        paso[paso > 30] = 0          # descartar saltos de fix
        d_geo = paso.sum()

    print(f"\nDuración: {ts[-1]:.0f} s   |   GPS con fix: {100*fix.mean():.0f} %")
    print("\n--- Velocidad ---")
    print(f"  máxima (Kalman): {v_kf.max():.2f} m/s  ({v_kf.max()*3.6:.1f} km/h)")
    print(f"  media  (en movimiento): {v_kf[v_kf > 0.5].mean() if (v_kf>0.5).any() else 0:.2f} m/s")
    print(f"  integrando solo el acelerómetro, valor final: {v_imu[-1]:.1f} m/s")
    print(f"     (si es absurdo, esa es la deriva que el filtro corrige)")
    print("\n--- Distancia ---")
    print(f"  por velocidad fusionada : {d_kf[-1]:.0f} m")
    print(f"  por velocidad GPS       : {d_gps[-1]:.0f} m")
    if d_geo > 0:
        print(f"  geométrica (lat/lon)    : {d_geo:.0f} m")
        dif = 100 * abs(d_kf[-1] - d_geo) / max(d_geo, 1)
        print(f"  diferencia Kalman vs geométrica: {dif:.1f} %")
    print(f"\nBias del acelerómetro estimado: {bias[-1]:+.4f} m/s²")

    # --- Gráficas ---
    fig, axs = plt.subplots(3, 1, figsize=(12, 9), sharex=True)

    axs[0].plot(ts, v_imu, color="0.65", lw=0.8, label="solo acelerómetro (deriva)")
    axs[0].plot(ts, np.where(fix, v_gps, np.nan), color="#c0392b", lw=1.0,
                label="GPS")
    axs[0].plot(ts, v_kf, color="#1a3a5c", lw=1.5, label="Kalman (fusión)")
    axs[0].set_ylabel("velocidad [m/s]")
    axs[0].set_title("Velocidad: tres formas de estimarla")
    axs[0].legend(loc="upper left", fontsize=8); axs[0].grid(alpha=.3)
    # Acotar la escala para que la deriva no aplaste las otras curvas
    lim = max(v_kf.max(), np.nanmax(np.where(fix, v_gps, np.nan)) if fix.any() else 1) * 1.6
    axs[0].set_ylim(-1, max(lim, 2))

    axs[1].plot(ts, a_long, color="#1e7d43", lw=0.6)
    axs[1].axhline(0, color="gray", lw=0.5)
    axs[1].set_ylabel("aceleración long. [m/s²]")
    axs[1].set_title("Aceleración longitudinal (a 100 Hz)")
    axs[1].grid(alpha=.3)

    axs[2].plot(ts, d_kf, color="#b45f06", lw=1.6, label="Kalman")
    axs[2].plot(ts, d_gps, color="#c0392b", lw=1.0, ls="--", label="solo GPS")
    axs[2].set_ylabel("distancia [m]"); axs[2].set_xlabel("tiempo [s]")
    axs[2].set_title("Distancia recorrida")
    axs[2].legend(loc="upper left", fontsize=8); axs[2].grid(alpha=.3)

    fig.suptitle(f"Velocidad y distancia — {Path(a.csv).name}", fontsize=13)
    fig.tight_layout()
    out_png = str(Path(a.csv).with_suffix("")) + "_veldist.png"
    fig.savefig(out_png, dpi=150)

    # Guardar el CSV con las columnas nuevas
    df_out = df.copy()
    df_out["t_s"] = ts
    df_out["v_imu"] = v_imu
    df_out["v_kalman"] = v_kf
    df_out["distancia_m"] = d_kf
    df_out["bias_acc"] = bias
    out_csv = str(Path(a.csv).with_suffix("")) + "_veldist.csv"
    df_out.to_csv(out_csv, index=False)

    print(f"\nGuardado: {out_png}")
    print(f"Guardado: {out_csv}")


if __name__ == "__main__":
    main()
