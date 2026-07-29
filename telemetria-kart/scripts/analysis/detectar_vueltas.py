"""
detectar_vueltas.py — Detecta vueltas dentro de una toma del kart (SD).

Pasos:
  1. Recorta automaticamente el arranque QUIETO (el kart parado antes de rodar):
     usa velocidad GPS y actividad de giro (yaw) para hallar cuando empieza el
     movimiento real.
  2. Detecta vueltas:
       - Si hay GPS suficiente: cada paso cerca del punto de meta (1er punto en
         movimiento) cuenta como una vuelta.
       - Si no hay GPS: divide la parte activa en N segmentos iguales (aprox.).
  3. Grafica las vueltas superpuestas (trayectoria y G lateral) y da tiempos.

Uso:
    python detectar_vueltas.py KART023.CSV
    python detectar_vueltas.py KART023.CSV --meta-radio 8 --min-vuelta 15
    python detectar_vueltas.py KART023.CSV --nvueltas 5      (forzar N si no hay GPS)
"""
import argparse, sys
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLS18 = ["seq","t_us","ax","ay","az","gx","gy","gz","roll","pitch",
          "g_lat","g_lon","yaw_rate","lat","lon","gps_spd","sats","gps_fix"]
COLS17 = COLS18[:-1]
COLORES = plt.cm.tab10.colors

def leer(path):
    raw = pd.read_csv(path, comment="#", header=0, on_bad_lines="skip")
    names = COLS18 if raw.shape[1] >= 18 else COLS17
    df = pd.read_csv(path, comment="#", header=None, names=names, skiprows=1, on_bad_lines="skip")
    df = df.apply(pd.to_numeric, errors="coerce").dropna(subset=["seq"])
    if "gps_fix" not in df: df["gps_fix"] = (df.get("lat",0)!=0).astype(int)
    df["t_s"] = (df["t_us"]-df["t_us"].iloc[0])/1e6
    return df.reset_index(drop=True)

def recortar_arranque(df):
    # "Actividad" = |g_lat|+|g_lon| filtrada + velocidad. Buscar donde arranca.
    act = df["g_lat"].abs().rolling(100, min_periods=1).mean() \
        + df["yaw_rate"].abs().rolling(100, min_periods=1).mean()/50.0
    spd = df["gps_spd"].fillna(0) if "gps_spd" in df else pd.Series(np.zeros(len(df)))
    movil = (act > 0.15) | (spd > 0.8)
    if movil.any():
        i0 = movil.idxmax()
        return df.iloc[i0:].reset_index(drop=True), df["t_s"].iloc[i0]
    return df, 0.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--meta-radio", type=float, default=8.0, help="radio (m) de la zona de meta")
    ap.add_argument("--min-vuelta", type=float, default=12.0, help="duracion minima de una vuelta (s)")
    ap.add_argument("--nvueltas", type=int, default=0, help="forzar N vueltas iguales (si no hay GPS)")
    a = ap.parse_args()

    df = leer(a.csv)
    df, t_arranque = recortar_arranque(df)
    print(f"{Path(a.csv).name}: arranque de movimiento en t={t_arranque:.0f} s; "
          f"parte activa {df['t_s'].iloc[-1]-df['t_s'].iloc[0]:.0f} s")

    g = df[(df["gps_fix"]==1)&(df.get("lat",0)!=0)].copy()
    cortes = []  # indices donde termina cada vuelta

    if len(g) > 50 and a.nvueltas == 0:
        # Metodo GPS: contar pasos cerca del punto de meta (1er punto activo)
        lat0 = np.radians(g["lat"].mean()); R = 6371000
        gx = np.radians(g["lon"]-g["lon"].mean())*R*np.cos(lat0)
        gy = np.radians(g["lat"]-g["lat"].mean())*R
        meta_x, meta_y = gx.iloc[0], gy.iloc[0]
        dist = np.hypot(gx-meta_x, gy-meta_y)
        dentro = dist < a.meta_radio
        t_g = g["t_s"].to_numpy()
        ultimo_t = -1e9
        for i in range(1, len(dentro)):
            if dentro.iloc[i] and not dentro.iloc[i-1]:  # entrando a la meta
                if t_g[i] - ultimo_t > a.min_vuelta:
                    cortes.append(t_g[i]); ultimo_t = t_g[i]
        metodo = f"GPS (meta radio {a.meta_radio:.0f} m)"
    else:
        # Metodo tiempo: N segmentos iguales
        n = a.nvueltas if a.nvueltas > 0 else 4
        t0, t1 = df["t_s"].iloc[0], df["t_s"].iloc[-1]
        cortes = list(np.linspace(t0, t1, n+1))[1:]
        metodo = f"tiempo ({n} segmentos iguales, sin GPS fiable)"

    # Construir vueltas entre cortes
    limites = [df["t_s"].iloc[0]] + cortes
    vueltas = []
    for k in range(len(limites)-1):
        seg = df[(df["t_s"]>=limites[k]) & (df["t_s"]<limites[k+1])]
        if len(seg) > 20:
            vueltas.append(seg)

    print(f"Metodo: {metodo}")
    print(f"Vueltas detectadas: {len(vueltas)}\n")
    print(f"{'vuelta':<8}{'dur(s)':>8}{'G_lat max':>11}{'yaw max':>9}{'vel max':>9}")
    for i, v in enumerate(vueltas):
        vmax = v["gps_spd"].max() if "gps_spd" in v else 0
        print(f"{i+1:<8}{v['t_s'].iloc[-1]-v['t_s'].iloc[0]:>8.1f}"
              f"{v['g_lat'].abs().max():>11.2f}{v['yaw_rate'].abs().max():>9.0f}{vmax:>9.1f}")

    # Graficas
    fig, axs = plt.subplots(1, 2, figsize=(14, 6))
    for i, v in enumerate(vueltas):
        c = COLORES[i % 10]
        vg = v[(v["gps_fix"]==1)&(v.get("lat",0)!=0)]
        if len(vg) > 5:
            lat0 = np.radians(vg["lat"].mean()); R = 6371000
            x = np.radians(vg["lon"]-vg["lon"].mean())*R*np.cos(lat0)
            y = np.radians(vg["lat"]-vg["lat"].mean())*R
            axs[0].plot(x, y, color=c, lw=1.2, label=f"vuelta {i+1}")
        # G lateral con tiempo normalizado 0-100% de la vuelta
        tn = (v["t_s"]-v["t_s"].iloc[0])/(v["t_s"].iloc[-1]-v["t_s"].iloc[0])*100
        axs[1].plot(tn, v["g_lat"], color=c, lw=0.6, label=f"vuelta {i+1}")
    axs[0].set_title("Trayectoria por vuelta"); axs[0].set_xlabel("este [m]"); axs[0].set_ylabel("norte [m]")
    axs[0].axis("equal"); axs[0].legend(fontsize=8); axs[0].grid(alpha=.3)
    axs[1].set_title("G lateral por vuelta (tiempo normalizado)")
    axs[1].set_xlabel("% de la vuelta"); axs[1].set_ylabel("G lateral")
    axs[1].legend(fontsize=8); axs[1].grid(alpha=.3)
    fig.suptitle(f"Vueltas — {Path(a.csv).name}", fontsize=13)
    fig.tight_layout()
    out = str(Path(a.csv).with_suffix(""))+"_vueltas.png"
    fig.savefig(out, dpi=150)
    print(f"\nGuardado: {out}")
    if len(vueltas) < 2:
        print("\nSugerencia: si no salieron vueltas claras, prueba --meta-radio 12")
        print("o fuerza N con --nvueltas 5 (mira antes cuantas vueltas diste).")

if __name__ == "__main__":
    main()
