# analisis_sesion_lora.py
# Análisis offline del CSV guardado por Node-RED o por telemetria_live_python_OK.py.
#
# Uso:
#   pip install pandas numpy matplotlib
#   python C:\TelemetriaKart\analisis_sesion_lora.py C:\TelemetriaKart\data\sesion_actual.csv
#   python C:\TelemetriaKart\analisis_sesion_lora.py
#
# Si no pasas archivo, usa C:\TelemetriaKart\data\sesion_actual.csv.
# Guarda PNG en C:\TelemetriaKart\resultados.

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEFAULT_CSV = Path(r"C:\TelemetriaKart\data\sesion_actual.csv")
OUTDIR = Path(r"C:\TelemetriaKart\resultados")


def load_csv(path):
    df = pd.read_csv(path)
    for c in df.columns:
        if c != "t_pc":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["seq", "t_ms", "roll", "pitch", "rssi", "snr"])
    df = df.drop_duplicates(subset=["seq"], keep="last")
    df = df.sort_values("t_ms").reset_index(drop=True)
    df["t_s"] = (df["t_ms"] - df["t_ms"].iloc[0]) / 1000.0
    return df


def local_xy_from_gps(df):
    dfg = df[(df["gps_fix"] == 1) & (df["lat"] != 0) & (df["lon"] != 0)].copy()
    if len(dfg) < 2:
        return None
    lat0 = float(dfg["lat"].iloc[0])
    lon0 = float(dfg["lon"].iloc[0])
    dfg["x_m"] = (dfg["lon"] - lon0) * 111320.0 * np.cos(np.deg2rad(lat0))
    dfg["y_m"] = (dfg["lat"] - lat0) * 111320.0
    return dfg


def save_plot(df, out_prefix):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    t = df["t_s"]

    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.plot(t, df["roll"], label="Roll [°]")
    ax.plot(t, df["pitch"], label="Pitch [°]")
    ax.plot(t, df["yaw_rate"], label="Yaw rate [°/s]")
    ax.set_title("Orientación y giro")
    ax.set_xlabel("Tiempo [s]")
    ax.grid(True, alpha=.3)
    ax.legend()
    p1 = OUTDIR / f"{out_prefix}_orientacion.png"
    fig.savefig(p1, dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.plot(t, df["g_lat"], label="G lateral [G]")
    ax.plot(t, df["g_lon"], label="G longitudinal [G]")
    ax.plot(t, df["gps_speed_mps"], label="Velocidad GPS [m/s]")
    ax.set_title("Dinámica")
    ax.set_xlabel("Tiempo [s]")
    ax.grid(True, alpha=.3)
    ax.legend()
    p2 = OUTDIR / f"{out_prefix}_dinamica.png"
    fig.savefig(p2, dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig, ax1 = plt.subplots(figsize=(10, 4.8))
    ax1.plot(t, df["rssi"], label="RSSI [dBm]")
    ax1.plot(t, df["snr"], label="SNR [dB]")
    ax1.set_title("Enlace LoRa")
    ax1.set_xlabel("Tiempo [s]")
    ax1.grid(True, alpha=.3)
    ax2 = ax1.twinx()
    ax2.plot(t, df["lost"], linestyle="--", label="Perdidos")
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2)
    p3 = OUTDIR / f"{out_prefix}_enlace.png"
    fig.savefig(p3, dpi=150, bbox_inches="tight")
    plt.close(fig)

    dfg = local_xy_from_gps(df)
    p4 = OUTDIR / f"{out_prefix}_gps.png"
    fig, ax = plt.subplots(figsize=(7, 6.2))
    if dfg is not None:
        ax.plot(dfg["x_m"], dfg["y_m"], marker="o", markersize=3, label="GPS")
        ax.scatter([dfg["x_m"].iloc[0]], [dfg["y_m"].iloc[0]], label="Inicio")
        ax.scatter([dfg["x_m"].iloc[-1]], [dfg["y_m"].iloc[-1]], label="Final")
        ax.axis("equal")
        ax.legend()
    else:
        ax.text(.5, .5, "Sin puntos GPS válidos", ha="center", va="center", transform=ax.transAxes)
    ax.set_title("Trayectoria GPS local")
    ax.set_xlabel("Este-Oeste [m]")
    ax.set_ylabel("Norte-Sur [m]")
    ax.grid(True, alpha=.3)
    fig.savefig(p4, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return [p1, p2, p3, p4]


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    if not path.exists():
        print(f"ERROR: no existe {path}")
        return

    df = load_csv(path)
    if df.empty:
        print("ERROR: CSV sin datos válidos")
        return

    prefix = path.stem
    files = save_plot(df, prefix)

    dur = max(float(df["t_s"].iloc[-1]), 1e-9)
    total_rx = int(df["total"].iloc[-1])
    lost = int(df["lost"].iloc[-1])
    loss_pct = 100 * lost / max(1, lost + total_rx)

    print("=== RESUMEN SESIÓN LORA ===")
    print(f"Archivo: {path}")
    print(f"Muestras: {len(df)}")
    print(f"Duración: {dur:.2f} s")
    print(f"Tasa LoRa: {len(df)/dur:.2f} Hz")
    print(f"RSSI promedio: {df['rssi'].mean():.1f} dBm | mínimo: {df['rssi'].min():.1f} dBm")
    print(f"SNR promedio: {df['snr'].mean():.2f} dB | mínimo: {df['snr'].min():.2f} dB")
    print(f"Pérdida: {loss_pct:.2f} % ({lost} paquetes)")
    print(f"GPS fix: {100*(df['gps_fix']==1).mean():.1f} %")
    print(f"Satélites promedio: {df['gps_sats'].mean():.1f}")
    print(f"HDOP promedio con fix: {df[df['gps_fix']==1]['gps_hdop'].mean():.2f}")
    print("Gráficas:")
    for f in files:
        print(f" - {f}")


if __name__ == "__main__":
    main()
