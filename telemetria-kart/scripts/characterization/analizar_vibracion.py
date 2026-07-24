"""
analizar_vibracion.py — Fase 4 (cierre): espectro de vibración y atenuación del montaje.

Compara dos capturas (montaje directo vs montaje aislado con espuma) mediante la
densidad espectral de potencia (PSD, método de Welch) y calcula la atenuación
del aislamiento en la banda de vibración.

Requiere: pip install scipy
Uso:
    python analizar_vibracion.py data\\vib_directa_XXXX.csv data\\vib_espuma_XXXX.csv
Genera: vibracion_psd.png + tabla en consola.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import signal
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLS = ["t_us", "ax", "ay", "az", "gx", "gy", "gz", "roll", "pitch"]

def cargar(path):
    df = pd.read_csv(path, comment="#", header=None, names=COLS, on_bad_lines="skip")
    df = df.apply(pd.to_numeric, errors="coerce").dropna().reset_index(drop=True)
    t = df.t_us.to_numpy(np.float64) / 1e6
    fs = 1.0 / np.median(np.diff(t))
    return df, fs

def psd(df, fs, eje):
    x = df[eje].to_numpy()
    x = x - x.mean()                       # quitar DC (gravedad/offset)
    f, p = signal.welch(x, fs=fs, nperseg=1024)
    return f, p

def rms_banda(f, p, f1, f2):
    m = (f >= f1) & (f <= f2)
    return np.sqrt(np.trapezoid(p[m], f[m]))

def main(f_directa, f_espuma):
    d1, fs1 = cargar(f_directa)
    d2, fs2 = cargar(f_espuma)
    print(f"Directo: {len(d1)} muestras @ {fs1:.1f} Hz | Espuma: {len(d2)} muestras @ {fs2:.1f} Hz")
    print(f"Nyquist = {fs1/2:.0f} Hz. OJO: el motor de un celular vibra a 150-250 Hz;")
    print("cualquier pico visible puede ser un ALIAS de esa frecuencia — el LPF interno")
    print("de la IMU (~40 Hz) atenúa pero no elimina. Interpretarlo así en el informe.\n")

    fig, axs = plt.subplots(3, 1, figsize=(11, 10))
    bandas = {}
    for i, eje in enumerate(["ax", "ay", "az"]):
        f1, p1 = psd(d1, fs1, eje)
        f2, p2 = psd(d2, fs2, eje)
        axs[i].semilogy(f1, p1, "r", lw=1.0, label="directo a la mesa")
        axs[i].semilogy(f2, p2, "b", lw=1.0, label="con espuma (aislado)")
        axs[i].set_ylabel(f"PSD {eje} [(m/s²)²/Hz]")
        axs[i].grid(alpha=.3, which="both"); axs[i].legend(loc="upper right")
        r1 = rms_banda(f1, p1, 5, min(45, fs1 / 2 - 1))
        r2 = rms_banda(f2, p2, 5, min(45, fs2 / 2 - 1))
        att = 20 * np.log10(r1 / r2) if r2 > 0 else float("inf")
        bandas[eje] = (r1, r2, att)
    axs[2].set_xlabel("frecuencia [Hz]")
    fig.suptitle("PSD de vibración: montaje directo vs aislado (Welch, banda 5-45 Hz)")
    fig.tight_layout()
    out = Path("data") / "vibracion_psd.png"
    fig.savefig(out, dpi=150)

    print("=== Atenuación del montaje aislado (banda 5-45 Hz) ===")
    print(f"{'eje':<5}{'RMS directo':>14}{'RMS espuma':>14}{'atenuación':>13}")
    for eje, (r1, r2, att) in bandas.items():
        print(f"{eje:<5}{r1:>11.4f} m/s²{r2:>11.4f} m/s²{att:>10.1f} dB")
    print("\nCriterio del plan: atenuación > 10 dB en la banda alta sin tocar la banda <10 Hz.")
    print(f"Guardado: {out}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Uso: python analizar_vibracion.py data\\vib_directa_X.csv data\\vib_espuma_X.csv")
    main(sys.argv[1], sys.argv[2])
