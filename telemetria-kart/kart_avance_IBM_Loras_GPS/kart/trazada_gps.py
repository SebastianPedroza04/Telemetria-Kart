"""
trazada_gps.py — Dibuja el recorrido registrado con 04_gps_test + capturar_serial.

Entrada: CSV con columnas  t_us,lat,lon,v_ms,rumbo,sats,hdop
Genera:
  1. Trazada en metros (vista de planta), coloreada por velocidad
  2. Velocidad vs tiempo
  3. Satélites y HDOP vs tiempo (calidad de la señal)
Más resumen: distancia recorrida, velocidad media/máxima, calidad.

Uso:
    python trazada_gps.py data\\gps_caminata_20260722_132950.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLS = ["t_us", "lat", "lon", "v_ms", "rumbo", "sats", "hdop"]

def main(path):
    df = pd.read_csv(path, comment="#", header=None, names=COLS, on_bad_lines="skip")
    df = df.apply(pd.to_numeric, errors="coerce").dropna().reset_index(drop=True)
    # descartar puntos sin fix o absurdos
    df = df[(df.lat != 0) & (df.lon != 0) & (df.hdop < 10)].reset_index(drop=True)
    if len(df) < 10:
        sys.exit("Muy pocos puntos con fix válido en el archivo.")

    t = (df.t_us - df.t_us.iloc[0]).to_numpy() / 1e6
    # lat/lon -> metros locales (equirrectangular alrededor del punto medio)
    lat0 = np.radians(df.lat.mean())
    R = 6371000.0
    x = np.radians(df.lon - df.lon.mean()) * R * np.cos(lat0)   # este [m]
    y = np.radians(df.lat - df.lat.mean()) * R                  # norte [m]

    paso = np.hypot(np.diff(x), np.diff(y))
    paso[paso > 20] = 0            # saltos de fix: no contarlos como distancia
    dist = paso.sum()

    print(f"\n=== Trazada: {Path(path).name} ===")
    print(f"Puntos con fix: {len(df)}   Duración: {t[-1]/60:.1f} min")
    print(f"Distancia recorrida: {dist:.0f} m")
    print(f"Velocidad: media {df.v_ms.mean():.2f} m/s | máx {df.v_ms.max():.2f} m/s "
          f"({df.v_ms.max()*3.6:.1f} km/h)")
    print(f"Satélites: media {df.sats.mean():.1f} (mín {df.sats.min():.0f})   "
          f"HDOP medio: {df.hdop.mean():.2f}")
    quieto = df.v_ms[df.v_ms < 0.5]
    if len(quieto) > 20:
        print(f"Ruido de velocidad en reposo: sigma = {quieto.std():.3f} m/s "
              f"-> R_GPS ~ ({max(quieto.std(),0.1):.2f} m/s)^2 para el Kalman de velocidad")

    fig = plt.figure(figsize=(13, 10))
    ax1 = fig.add_subplot(2, 2, 1)
    sc = ax1.scatter(x, y, c=df.v_ms, s=6, cmap="viridis")
    ax1.plot(x.iloc[0] if hasattr(x, "iloc") else x[0], y.iloc[0] if hasattr(y, "iloc") else y[0],
             "g^", ms=12, label="inicio")
    ax1.plot(x.iloc[-1] if hasattr(x, "iloc") else x[-1], y.iloc[-1] if hasattr(y, "iloc") else y[-1],
             "rs", ms=10, label="fin")
    ax1.set_xlabel("este [m]"); ax1.set_ylabel("norte [m]")
    ax1.set_title("Trazada (vista de planta)")
    ax1.axis("equal"); ax1.legend(); ax1.grid(alpha=.3)
    fig.colorbar(sc, ax=ax1, label="velocidad [m/s]")

    ax2 = fig.add_subplot(2, 2, 2)
    ax2.plot(t, df.v_ms, lw=0.9)
    ax2.set_xlabel("t [s]"); ax2.set_ylabel("velocidad [m/s]")
    ax2.set_title("Velocidad (Doppler del GPS)"); ax2.grid(alpha=.3)

    ax3 = fig.add_subplot(2, 2, 3)
    ax3.plot(t, df.sats, lw=0.9, color="#1a3a5c")
    ax3.set_xlabel("t [s]"); ax3.set_ylabel("satélites en uso")
    ax3.set_title("Satélites"); ax3.grid(alpha=.3)

    ax4 = fig.add_subplot(2, 2, 4)
    ax4.plot(t, df.hdop, lw=0.9, color="#c0392b")
    ax4.set_xlabel("t [s]"); ax4.set_ylabel("HDOP")
    ax4.set_title("Calidad geométrica (HDOP, menor = mejor)"); ax4.grid(alpha=.3)

    fig.suptitle(f"Recorrido GPS — {Path(path).name}", fontsize=13)
    fig.tight_layout()
    out = str(Path(path).with_suffix("")) + "_trazada.png"
    fig.savefig(out, dpi=150)
    print(f"\nGuardado: {out}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python trazada_gps.py data\\gps_caminata_XXXX.csv")
    main(sys.argv[1])
