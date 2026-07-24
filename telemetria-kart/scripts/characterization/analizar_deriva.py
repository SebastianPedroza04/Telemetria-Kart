"""
analizar_deriva.py — Fase 3 (cierre): deriva del giroscopio en captura larga en reposo.

Calcula:
  1. Bias del gyro en ventanas de 1 min vs tiempo (estabilidad del bias).
  2. Ángulo integrado theta(t) = integral de omega dt SIN corrección de bias
     -> muestra la deriva que sufriría el yaw en el kart.
  3. Ángulo integrado CON el bias corregido (bias de los primeros 60 s)
     -> muestra cuánto mejora la calibración al arranque y cuánta deriva residual queda.
  4. Deriva en °/min de ambos casos, por eje.

Uso:
    python analizar_deriva.py data\\deriva_XXXX.csv
Genera: <archivo>_deriva.png y tabla en consola.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLS = ["t_us", "ax", "ay", "az", "gx", "gy", "gz"]

def main(path):
    df = pd.read_csv(path, comment="#", header=None, names=COLS, on_bad_lines="skip")
    df = df.apply(pd.to_numeric, errors="coerce").dropna().reset_index(drop=True)
    t = df["t_us"].to_numpy(np.float64) / 1e6
    dt = np.diff(t, prepend=t[0])
    dt[(dt <= 0) | (dt > 0.1)] = 0.01
    ts = np.cumsum(dt)
    dur_min = ts[-1] / 60
    print(f"{path}: {len(df)} muestras, {dur_min:.1f} min\n")

    ejes = ["gx", "gy", "gz"]
    # 1) Bias por ventanas de 1 min
    df["min"] = (ts // 60).astype(int)
    ventanas = df.groupby("min")[ejes].mean()

    # 2/3) Ángulos integrados sin y con corrección de bias inicial (primeros 60 s)
    bias0 = df.loc[ts <= 60, ejes].mean()
    ang_sin, ang_con = {}, {}
    for e in ejes:
        w = df[e].to_numpy()
        ang_sin[e] = np.cumsum(w * dt)
        ang_con[e] = np.cumsum((w - bias0[e]) * dt)

    print("=== Deriva del giroscopio ===")
    print(f"{'eje':<4}{'bias 1er min':>14}{'bias ult min':>14}{'cambio':>10}"
          f"{'deriva SIN corr':>17}{'deriva CON corr':>17}")
    filas = []
    for e in ejes:
        b_ini, b_fin = ventanas[e].iloc[0], ventanas[e].iloc[-1]
        d_sin = ang_sin[e][-1] / dur_min      # °/min
        d_con = ang_con[e][-1] / dur_min
        print(f"{e:<4}{b_ini:>13.3f}°/s{b_fin:>12.3f}°/s{b_fin-b_ini:>9.3f}"
              f"{d_sin:>14.2f}°/min{d_con:>14.3f}°/min")
        filas.append(dict(eje=e, bias_ini=b_ini, bias_fin=b_fin,
                          deriva_sin=d_sin, deriva_con=d_con))
    print("\nLectura: 'SIN corr' es la deriva bruta (justifica calibrar al arranque);")
    print("'CON corr' es la deriva residual tras restar el bias inicial (lo que el")
    print("Kalman/reanclaje debe absorber en pista, donde no se puede recalibrar).")

    out = Path(path).with_suffix("")
    pd.DataFrame(filas).to_csv(f"{out}_deriva.csv", index=False)

    fig, axs = plt.subplots(3, 1, figsize=(12, 10))
    for e in ejes:
        axs[0].plot(ventanas.index, ventanas[e], marker="o", ms=3, label=e)
    axs[0].set_xlabel("minuto"); axs[0].set_ylabel("bias [°/s]")
    axs[0].set_title("Bias del giroscopio por ventana de 1 min"); axs[0].legend(); axs[0].grid(alpha=.3)
    for e in ejes:
        axs[1].plot(ts / 60, ang_sin[e], label=e)
    axs[1].set_xlabel("t [min]"); axs[1].set_ylabel("ángulo [°]")
    axs[1].set_title("Ángulo integrado SIN corrección de bias (deriva bruta)")
    axs[1].legend(); axs[1].grid(alpha=.3)
    for e in ejes:
        axs[2].plot(ts / 60, ang_con[e], label=e)
    axs[2].set_xlabel("t [min]"); axs[2].set_ylabel("ángulo [°]")
    axs[2].set_title("Ángulo integrado CON bias inicial corregido (deriva residual)")
    axs[2].legend(); axs[2].grid(alpha=.3)
    fig.tight_layout()
    fig.savefig(f"{out}_deriva.png", dpi=150)
    print(f"\nGuardado: {out}_deriva.csv y {out}_deriva.png")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python analizar_deriva.py data\\deriva_XXXX.csv")
    main(sys.argv[1])
