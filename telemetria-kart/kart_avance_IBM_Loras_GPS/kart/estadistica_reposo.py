"""
estadistica_reposo.py — Fase 3 (inicio): estadística de una captura en reposo.
Calcula por eje: media, varianza, desviación estándar, offset (acel) y bias (gyro).
Verifica |a| ~ 9.81, frecuencia de muestreo real y jitter. Genera figuras PNG.

Uso:
    pip install pandas matplotlib
    python estadistica_reposo.py data/sesion_XXXX.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

G = 9.80665
COLS = ["t_us", "ax", "ay", "az", "gx", "gy", "gz"]

def main(path):
    df = pd.read_csv(path, comment="#", header=None, names=COLS, on_bad_lines="skip")
    df = df.apply(pd.to_numeric, errors="coerce").dropna().reset_index(drop=True)
    t = df["t_us"].to_numpy(dtype=np.int64)
    df["t_s"] = (t - t[0]) / 1e6
    dur = df["t_s"].iloc[-1]
    print(f"Archivo: {path}\nMuestras: {len(df)}  Duración: {dur:.1f} s")

    # --- Frecuencia de muestreo y jitter ---
    dt = np.diff(t) / 1e3  # ms
    fs = 1000.0 / np.mean(dt)
    huecos = int(np.sum(dt > 1.5 * np.median(dt)))
    print(f"\nfs real = {fs:.2f} Hz | dt medio = {np.mean(dt):.3f} ms | "
          f"jitter (σ) = {np.std(dt):.3f} ms | max = {np.max(dt):.2f} ms | huecos = {huecos}")

    # --- Estadística por eje ---
    print("\n=== Tabla de caracterización (reposo) ===")
    print(f"{'eje':<4}{'media':>12}{'varianza':>14}{'desv.est':>12}{'offset/bias':>14}  unidad")
    esperado = {"ax": 0.0, "ay": 0.0, "az": G, "gx": 0.0, "gy": 0.0, "gz": 0.0}
    filas = []
    for c in ["ax", "ay", "az", "gx", "gy", "gz"]:
        v = df[c].to_numpy()
        m, var, sd = v.mean(), v.var(ddof=1), v.std(ddof=1)
        off = m - esperado[c]
        unidad = "m/s²" if c.startswith("a") else "°/s"
        nombre = "offset" if c.startswith("a") else "bias"
        print(f"{c:<4}{m:>12.5f}{var:>14.6e}{sd:>12.5f}{off:>14.5f}  {unidad} ({nombre})")
        filas.append(dict(eje=c, media=m, varianza=var, desv_est=sd,
                          offset_bias=off, unidad=unidad))
    # NOTA: el offset de az asume el sensor nivelado con z hacia arriba.
    # Si el eje vertical es otro, ajustar 'esperado'.

    norma = np.sqrt(df.ax**2 + df.ay**2 + df.az**2)
    print(f"\n|a| media = {norma.mean():.4f} m/s² (esperado ~{G})  σ = {norma.std():.4f}")
    if abs(norma.mean() - G) > 0.3:
        print("AVISO: |a| lejos de 9.81 -> revisar escala configurada o nivelación.")

    # Guardar tabla
    out = Path(path).with_suffix("")
    pd.DataFrame(filas).to_csv(f"{out}_stats.csv", index=False)

    # --- Figuras ---
    fig, axs = plt.subplots(3, 1, figsize=(11, 8), sharex=True)
    for c in ["ax", "ay", "az"]:
        axs[0].plot(df.t_s, df[c], lw=0.5, label=c)
    axs[0].set_ylabel("acel [m/s²]"); axs[0].legend(loc="upper right"); axs[0].grid(alpha=.3)
    for c in ["gx", "gy", "gz"]:
        axs[1].plot(df.t_s, df[c], lw=0.5, label=c)
    axs[1].set_ylabel("gyro [°/s]"); axs[1].legend(loc="upper right"); axs[1].grid(alpha=.3)
    axs[2].hist(dt, bins=100)
    axs[2].set_xlabel("Δt [ms] (histograma)"); axs[2].set_ylabel("frec."); axs[2].grid(alpha=.3)
    fig.suptitle(f"Reposo — {Path(path).name} — fs={fs:.1f} Hz")
    fig.tight_layout()
    fig.savefig(f"{out}_reposo.png", dpi=150)
    print(f"\nGuardado: {out}_stats.csv y {out}_reposo.png")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python estadistica_reposo.py data/sesion_XXXX.csv")
    main(sys.argv[1])