"""
inspeccionar.py — Inventario rápido de los CSV de la SD (KART*.CSV).
Dice de cada archivo: muestras, duración, si tiene GPS con fix, cuánto se
movió y rangos de G/yaw. Sirve para identificar cuál toma es cuál.

Uso:
    python inspeccionar.py                 (todos los KART*.CSV de la carpeta actual)
    python inspeccionar.py D:\\            (todos los de la SD)
    python inspeccionar.py KART014.CSV KART015.CSV
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

COLS18 = ["seq","t_us","ax","ay","az","gx","gy","gz","roll","pitch",
          "g_lat","g_lon","yaw_rate","lat","lon","gps_spd","sats","gps_fix"]
COLS17 = COLS18[:-1]   # firmware anterior sin gps_fix

def leer(path):
    # detectar nº de columnas
    raw = pd.read_csv(path, comment="#", header=0, on_bad_lines="skip")
    ncol = raw.shape[1]
    names = COLS18 if ncol >= 18 else COLS17
    df = pd.read_csv(path, comment="#", header=None, names=names,
                     skiprows=1, on_bad_lines="skip")
    df = df.apply(pd.to_numeric, errors="coerce").dropna(subset=["seq"])
    if "gps_fix" not in df: df["gps_fix"] = (df.get("lat", 0) != 0).astype(int)
    return df

def expandir(args):
    if not args: args = ["."]
    out = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            out += glob.glob(str(p/"KART*.CSV")) + glob.glob(str(p/"KART*.csv"))
        else:
            out += glob.glob(a)
    return sorted(set(out))

def main(args):
    archivos = expandir(args)
    if not archivos:
        sys.exit("No hay KART*.CSV aqui. Prueba: python inspeccionar.py D:\\")
    print(f"\n{'archivo':<16}{'muestras':>9}{'dur(s)':>8}{'GPS fix%':>9}"
          f"{'movim(m)':>9}{'G_lat max':>10}{'yaw max':>9}")
    print("-" * 70)
    for a in archivos:
        try:
            df = leer(a)
        except Exception as e:
            print(f"{Path(a).name:<16}  ERROR: {e}"); continue
        n = len(df)
        dur = n / 100.0
        g = df[(df["gps_fix"] == 1) & (df.get("lat", 0) != 0)]
        pct = 100*len(g)/n if n else 0
        mov = 0.0
        if len(g) > 5:
            lat0 = np.radians(g["lat"].mean()); R = 6371000
            x = np.radians(g["lon"]-g["lon"].mean())*R*np.cos(lat0)
            y = np.radians(g["lat"]-g["lat"].mean())*R
            paso = np.hypot(np.diff(x), np.diff(y)); paso[paso>30]=0
            mov = paso.sum()
        glmax = df["g_lat"].abs().max() if "g_lat" in df else 0
        ywmax = df["yaw_rate"].abs().max() if "yaw_rate" in df else 0
        print(f"{Path(a).name:<16}{n:>9}{dur:>8.1f}{pct:>8.0f}%"
              f"{mov:>9.0f}{glmax:>10.2f}{ywmax:>9.0f}")
    print("\nPista para identificar tomas:")
    print("  - muestras/dur grandes = toma real; pocas = arranque o prueba corta")
    print("  - GPS fix% alto y movim>0 = caminata a cielo abierto")
    print("  - GPS fix% 0 = grabado bajo techo (sin trayectoria)")

if __name__ == "__main__":
    main(sys.argv[1:])
