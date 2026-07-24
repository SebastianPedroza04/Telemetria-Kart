# analizar_microsd_offline.py
# Análisis offline del CSV real de microSD a 100 Hz.
#
# Uso:
#   pip install pandas numpy matplotlib
#   python C:\TelemetriaKart\analizar_microsd_offline.py C:\TelemetriaKart\data\microsd\KART000.CSV
#
# Si no pasas archivo, busca el KART*.CSV más reciente en C:\TelemetriaKart\data\microsd.
# Guarda resultados en C:\TelemetriaKart\resultados.

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


IN_DIR = Path(r"C:\TelemetriaKart\data\microsd")
OUTDIR = Path(r"C:\TelemetriaKart\resultados")


def pick_file():
    files = sorted([f for f in IN_DIR.glob("KART*.CSV") if "_fusion" not in f.stem])
    if not files:
        raise FileNotFoundError("No hay KART*.CSV en C:\\TelemetriaKart\\data\\microsd")
    return files[-1]


def load_df(path):
    df = pd.read_csv(path)
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    if "t_us" not in df.columns:
        raise ValueError("No parece CSV de microSD: falta columna t_us.")

    df = df.dropna(subset=["t_us"]).sort_values("t_us").reset_index(drop=True)
    df["t_s"] = (df["t_us"] - df["t_us"].iloc[0]) / 1_000_000.0
    return df


def plot(df, prefix):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    t = df["t_s"]
    outputs = []

    plots = [
        ("acelerometro", ["ax", "ay", "az"], "Acelerómetro", "m/s²"),
        ("giroscopio", ["gx", "gy", "gz"], "Giroscopio", "°/s"),
        ("orientacion", ["roll", "pitch", "yaw_rate"], "Orientación y yaw rate", ""),
        ("dinamica", ["g_lat", "g_lon", "gps_speed_mps"], "Dinámica", ""),
    ]

    for suffix, cols, title, ylabel in plots:
        fig, ax = plt.subplots(figsize=(10, 4.8))
        for c in cols:
            if c in df.columns:
                ax.plot(t, df[c], label=c)
        ax.set_title(title)
        ax.set_xlabel("Tiempo [s]")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=.3)
        ax.legend()
        out = OUTDIR / f"{prefix}_{suffix}.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        outputs.append(out)

    # GPS local
    fig, ax = plt.subplots(figsize=(7, 6.2))
    if {"gps_fix", "gps_lat", "gps_lon"}.issubset(df.columns):
        dfg = df[(df["gps_fix"] == 1) & (df["gps_lat"] != 0) & (df["gps_lon"] != 0)].copy()
        if len(dfg) >= 2:
            lat0 = float(dfg["gps_lat"].iloc[0])
            lon0 = float(dfg["gps_lon"].iloc[0])
            x = (dfg["gps_lon"] - lon0) * 111320.0 * np.cos(np.deg2rad(lat0))
            y = (dfg["gps_lat"] - lat0) * 111320.0
            ax.plot(x, y, marker="o", markersize=3, label="GPS")
            ax.axis("equal")
            ax.legend()
        else:
            ax.text(.5, .5, "Sin puntos GPS válidos", ha="center", va="center", transform=ax.transAxes)
    else:
        ax.text(.5, .5, "El CSV no tiene columnas GPS", ha="center", va="center", transform=ax.transAxes)

    ax.set_title("Trayectoria GPS")
    ax.set_xlabel("Este-Oeste [m]")
    ax.set_ylabel("Norte-Sur [m]")
    ax.grid(True, alpha=.3)
    out = OUTDIR / f"{prefix}_gps.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    outputs.append(out)

    return outputs


def main():
    try:
        path = Path(sys.argv[1]) if len(sys.argv) > 1 else pick_file()
        df = load_df(path)
        if df.empty:
            raise ValueError("CSV vacío o sin filas válidas")

        dur = max(float(df["t_s"].iloc[-1]), 1e-9)
        fs = len(df) / dur

        files = plot(df, path.stem)

        print("=== ANÁLISIS MICROSD ===")
        print(f"Archivo: {path}")
        print(f"Muestras: {len(df)}")
        print(f"Duración: {dur:.2f} s")
        print(f"Frecuencia aprox.: {fs:.2f} Hz")
        if "gps_fix" in df.columns:
            print(f"GPS fix: {100*(df['gps_fix']==1).mean():.1f} %")
        print("Gráficas:")
        for f in files:
            print(f" - {f}")

    except Exception as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    main()
