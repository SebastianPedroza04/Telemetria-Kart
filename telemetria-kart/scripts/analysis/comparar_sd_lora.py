"""
comparar_sd_lora.py — Compara la grabacion a bordo (SD, 100 Hz) con la
telemetria recibida en vivo por LoRa (~1-2 Hz) de la MISMA sesion.

Ambas fuentes comparten el contador 'seq' del firmware, asi que se alinean
exactamente muestra a muestra. Demuestra que lo visto en vivo coincide con
lo grabado a bordo, y cuantifica cuanto se pierde al bajar la tasa.

Uso:
    python comparar_sd_lora.py KART023.CSV data\\lora\\lora_20260724_163112.csv
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLS18 = ["seq","t_us","ax","ay","az","gx","gy","gz","roll","pitch",
          "g_lat","g_lon","yaw_rate","lat","lon","gps_spd","sats","gps_fix"]
COLS17 = COLS18[:-1]

def leer_sd(path):
    raw = pd.read_csv(path, comment="#", header=0, on_bad_lines="skip")
    names = COLS18 if raw.shape[1] >= 18 else COLS17
    df = pd.read_csv(path, comment="#", header=None, names=names, skiprows=1, on_bad_lines="skip")
    df = df.apply(pd.to_numeric, errors="coerce").dropna(subset=["seq"])
    return df.reset_index(drop=True)

def leer_lora(path):
    df = pd.read_csv(path, comment="#", on_bad_lines="skip")
    df = df.apply(pd.to_numeric, errors="coerce").dropna(subset=["seq"])
    return df.reset_index(drop=True)

def main(sd_path, lora_path):
    sd = leer_sd(sd_path)
    lo = leer_lora(lora_path)
    print(f"SD   : {len(sd)} muestras, seq {sd.seq.min():.0f}-{sd.seq.max():.0f}")
    print(f"LoRa : {len(lo)} paquetes, seq {lo.seq.min():.0f}-{lo.seq.max():.0f}")

    # Solapamiento de secuencia (misma sesion del firmware)
    lo_ok = lo[(lo.seq >= sd.seq.min()) & (lo.seq <= sd.seq.max())]
    print(f"Paquetes LoRa dentro del rango de la SD: {len(lo_ok)}")
    if len(lo_ok) < 5:
        print("\nAVISO: casi no hay solapamiento de 'seq'.")
        print("Probablemente el CSV de LoRa es de OTRA sesion (otro encendido).")
        print("Se comparan igual, pero por tiempo relativo, no por seq.")

    t_sd = (sd.t_us - sd.t_us.iloc[0]) / 1e6
    usar_seq = len(lo_ok) >= 5
    if usar_seq:
        t_lo = (lo_ok.t_us - sd.t_us.iloc[0]) / 1e6
        L = lo_ok
    else:
        L = lo
        t_lo = (lo.t_us - lo.t_us.iloc[0]) / 1e6

    # Tasas efectivas
    fs_sd = len(sd) / (t_sd.iloc[-1] - t_sd.iloc[0]) if len(sd) > 1 else 0
    fs_lo = len(L) / (t_lo.iloc[-1] - t_lo.iloc[0]) if len(L) > 1 else 0
    print(f"\nTasa efectiva  SD: {fs_sd:.1f} Hz   |   LoRa: {fs_lo:.2f} Hz "
          f"(factor {fs_sd/max(fs_lo,0.01):.0f}x menos datos por radio)")

    fig, axs = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
    pares = [("g_lat", "G lateral [g]"), ("roll", "roll [°]"), ("yaw_rate", "yaw rate [°/s]")]
    for ax, (col, etiqueta) in zip(axs, pares):
        if col in sd:
            ax.plot(t_sd, sd[col], color="#1a3a5c", lw=0.5, label="SD a bordo (100 Hz)")
        if col in L:
            ax.plot(t_lo, L[col], "o-", color="#c0392b", ms=3, lw=0.9,
                    label=f"LoRa en vivo ({fs_lo:.1f} Hz)")
        ax.set_ylabel(etiqueta); ax.grid(alpha=.3); ax.legend(loc="upper right", fontsize=8)
    axs[0].set_title("Grabacion a bordo (SD) vs telemetria en vivo (LoRa) — misma sesion")
    axs[-1].set_xlabel("t [s]")
    fig.tight_layout()
    out = str(Path(sd_path).with_suffix("")) + "_sd_vs_lora.png"
    fig.savefig(out, dpi=150)

    # Calidad del enlace
    if "rssi" in L:
        print(f"\nEnlace LoRa: RSSI medio {L.rssi.mean():.0f} dBm (min {L.rssi.min():.0f}), "
              f"SNR medio {L.snr.mean():.1f} dB")
    # Cuanto se pierde al decimar: pico real vs pico visto por radio
    for col, etiqueta in pares:
        if col in sd and col in L and len(L) > 2:
            print(f"{etiqueta:<18} pico SD {sd[col].abs().max():>7.2f}   "
                  f"pico LoRa {L[col].abs().max():>7.2f}   "
                  f"({100*L[col].abs().max()/max(sd[col].abs().max(),1e-9):.0f} % del real)")
    print(f"\nGuardado: {out}")
    print("\nLectura para el informe: la radio reproduce bien la TENDENCIA, pero al ir")
    print("a ~1 Hz no captura los picos instantaneos -> por eso la SD es la fuente de verdad.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Uso: python comparar_sd_lora.py KART023.CSV data\\lora\\lora_XXXX.csv")
    main(sys.argv[1], sys.argv[2])
