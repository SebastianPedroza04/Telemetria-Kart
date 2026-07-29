"""
trazada_sd.py — Trayectoria y análisis desde los CSV de la microSD del kart.

Lee UNO O VARIOS archivos KARTxxx.CSV (18 columnas del firmware con GPS),
los une en orden y dibuja:
  1. Trayectoria (lat/lon) coloreada por velocidad GPS
  2. G lateral y G longitudinal vs tiempo
  3. Yaw rate vs tiempo
  4. Velocidad GPS y roll/pitch
Filtra automáticamente los puntos sin fix (gps_fix=0 o lat=0).

Columnas esperadas:
  seq,t_us,ax,ay,az,gx,gy,gz,roll,pitch,g_lat,g_lon,yaw_rate,lat,lon,gps_spd,sats,gps_fix

Uso (varias formas):
    python trazada_sd.py D:\\KART014.CSV
    python trazada_sd.py D:\\KART013.CSV D:\\KART014.CSV D:\\KART015.CSV
    python trazada_sd.py D:\\KART*.CSV
    python trazada_sd.py D:\\            (toma todos los KART*.CSV de la carpeta)
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLS = ["seq", "t_us", "ax", "ay", "az", "gx", "gy", "gz", "roll", "pitch",
        "g_lat", "g_lon", "yaw_rate", "lat", "lon", "gps_spd", "sats", "gps_fix"]

def expandir(args):
    archivos = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            archivos += glob.glob(str(p / "KART*.CSV")) + glob.glob(str(p / "KART*.csv"))
        else:
            archivos += glob.glob(a)
    # ordenar por nombre (KART001, KART002, ...)
    return sorted(set(archivos))

def cargar(path):
    df = pd.read_csv(path, comment="#", header=None, names=COLS,
                     skiprows=1, on_bad_lines="skip")
    df = df.apply(pd.to_numeric, errors="coerce").dropna(subset=["seq"])
    df["archivo"] = Path(path).name
    return df

def main(args):
    archivos = expandir(args)
    if not archivos:
        sys.exit("No se encontraron archivos. Ej: python trazada_sd.py D:\\KART014.CSV")
    print("Archivos:", ", ".join(Path(a).name for a in archivos))

    partes = []
    t_offset = 0.0
    for a in archivos:
        d = cargar(a)
        if len(d) == 0:
            continue
        t = (d["t_us"].to_numpy(np.float64) - d["t_us"].iloc[0]) / 1e6
        d["t_s"] = t + t_offset
        t_offset = d["t_s"].iloc[-1] + 1.0   # 1 s de separación entre archivos
        partes.append(d)
    df = pd.concat(partes, ignore_index=True)
    print(f"Total muestras: {len(df)}  ({len(df)/100:.0f} s aprox a 100 Hz)")

    # Puntos con fix válido para la trayectoria
    g = df[(df["gps_fix"] == 1) & (df["lat"] != 0) & (df["lon"] != 0)].copy()
    print(f"Muestras con GPS fijo: {len(g)}  "
          f"({100*len(g)/len(df):.0f} % de la sesión)")

    fig = plt.figure(figsize=(14, 10))

    # --- Trayectoria ---
    ax1 = fig.add_subplot(2, 2, 1)
    if len(g) > 5:
        lat0 = np.radians(g["lat"].mean()); R = 6371000.0
        x = np.radians(g["lon"] - g["lon"].mean()) * R * np.cos(lat0)
        y = np.radians(g["lat"] - g["lat"].mean()) * R
        sc = ax1.scatter(x, y, c=g["gps_spd"], s=8, cmap="viridis")
        ax1.plot(x.iloc[0], y.iloc[0], "g^", ms=13, label="inicio")
        ax1.plot(x.iloc[-1], y.iloc[-1], "rs", ms=11, label="fin")
        fig.colorbar(sc, ax=ax1, label="velocidad [m/s]")
        paso = np.hypot(np.diff(x), np.diff(y)); paso[paso > 30] = 0
        ax1.set_title(f"Trayectoria — {paso.sum():.0f} m recorridos")
        ax1.legend(); ax1.axis("equal")
    else:
        ax1.text(0.5, 0.5, "Sin puntos GPS con fix\n(¿grabado bajo techo?)",
                 ha="center", va="center", transform=ax1.transAxes)
        ax1.set_title("Trayectoria — sin datos GPS")
    ax1.set_xlabel("este [m]"); ax1.set_ylabel("norte [m]"); ax1.grid(alpha=.3)

    # --- Fuerzas G ---
    ax2 = fig.add_subplot(2, 2, 2)
    ax2.plot(df["t_s"], df["g_lat"], "m", lw=0.6, label="G lateral")
    ax2.plot(df["t_s"], df["g_lon"], "c", lw=0.6, label="G longitudinal")
    ax2.set_xlabel("t [s]"); ax2.set_ylabel("G"); ax2.set_title("Fuerzas G (100 Hz)")
    ax2.legend(); ax2.grid(alpha=.3)

    # --- Yaw rate ---
    ax3 = fig.add_subplot(2, 2, 3)
    ax3.plot(df["t_s"], df["yaw_rate"], "g", lw=0.6)
    ax3.set_xlabel("t [s]"); ax3.set_ylabel("yaw rate [°/s]")
    ax3.set_title("Velocidad de giro"); ax3.grid(alpha=.3)

    # --- Velocidad y actitud ---
    ax4 = fig.add_subplot(2, 2, 4)
    ax4.plot(df["t_s"], df["gps_spd"], "b", lw=0.7, label="vel GPS [m/s]")
    ax4b = ax4.twinx()
    ax4b.plot(df["t_s"], df["roll"], color="0.6", lw=0.5, label="roll [°]")
    ax4.set_xlabel("t [s]"); ax4.set_ylabel("vel [m/s]", color="b")
    ax4b.set_ylabel("roll [°]", color="0.5")
    ax4.set_title("Velocidad GPS + roll"); ax4.grid(alpha=.3)

    fig.suptitle(f"Sesión SD — {len(archivos)} archivo(s)", fontsize=13)
    fig.tight_layout()
    out = Path(archivos[0]).with_suffix("")
    out = str(out) + "_sesion.png"
    fig.savefig(out, dpi=150)

    print("\n--- Resumen ---")
    print(f"G lat: {df.g_lat.min():+.2f} a {df.g_lat.max():+.2f} g")
    print(f"G lon: {df.g_lon.min():+.2f} a {df.g_lon.max():+.2f} g")
    print(f"Yaw rate: {df.yaw_rate.min():+.0f} a {df.yaw_rate.max():+.0f} °/s")
    if len(g) > 5:
        print(f"Velocidad GPS: media {g.gps_spd.mean():.1f} | máx {g.gps_spd.max():.1f} m/s "
              f"({g.gps_spd.max()*3.6:.0f} km/h)")
    print(f"\nGuardado: {out}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Uso: python trazada_sd.py <archivo(s) o carpeta>\n"
                 "Ej: python trazada_sd.py D:\\KART014.CSV")
    main(sys.argv[1:])
