"""
comparar_tomas.py — Compara varias tomas (KART*.CSV de la SD) superpuestas.
Cada toma en un color: trayectorias, G lateral, velocidad y G-G diagram.

Uso:
    python comparar_tomas.py KART014.CSV KART015.CSV KART016.CSV
    python comparar_tomas.py D:\\           (todas las de la SD)
"""
import glob, sys
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLS18 = ["seq","t_us","ax","ay","az","gx","gy","gz","roll","pitch",
          "g_lat","g_lon","yaw_rate","lat","lon","gps_spd","sats","gps_fix"]
COLS17 = COLS18[:-1]
COLORES = ["#1a3a5c","#c0392b","#1e7d43","#b45f06","#7d3c98"]

def leer(path):
    raw = pd.read_csv(path, comment="#", header=0, on_bad_lines="skip")
    names = COLS18 if raw.shape[1] >= 18 else COLS17
    df = pd.read_csv(path, comment="#", header=None, names=names, skiprows=1, on_bad_lines="skip")
    df = df.apply(pd.to_numeric, errors="coerce").dropna(subset=["seq"])
    if "gps_fix" not in df: df["gps_fix"] = (df.get("lat",0)!=0).astype(int)
    df["t_s"] = (df["t_us"]-df["t_us"].iloc[0])/1e6
    return df

def expandir(args):
    out=[]
    for a in args:
        p=Path(a)
        if p.is_dir(): out+=glob.glob(str(p/"KART*.CSV"))+glob.glob(str(p/"KART*.csv"))
        else: out+=glob.glob(a)
    return sorted(set(out))

def main(args):
    archivos = expandir(args)
    if not archivos: sys.exit("Uso: python comparar_tomas.py KART014.CSV KART015.CSV ...")
    tomas=[(Path(a).name, leer(a)) for a in archivos]

    fig=plt.figure(figsize=(14,10))
    # 1) Trayectorias superpuestas (metros, mismo origen relativo)
    ax1=fig.add_subplot(2,2,1)
    hay_gps=False
    for i,(nombre,df) in enumerate(tomas):
        g=df[(df["gps_fix"]==1)&(df.get("lat",0)!=0)]
        if len(g)<5: continue
        hay_gps=True
        lat0=np.radians(g["lat"].mean()); R=6371000
        x=np.radians(g["lon"]-g["lon"].mean())*R*np.cos(lat0)
        y=np.radians(g["lat"]-g["lat"].mean())*R
        ax1.plot(x,y,lw=1.2,color=COLORES[i%5],label=nombre)
    ax1.set_title("Trayectorias" if hay_gps else "Trayectorias — sin GPS")
    ax1.set_xlabel("este [m]"); ax1.set_ylabel("norte [m]")
    ax1.axis("equal"); ax1.legend(fontsize=8); ax1.grid(alpha=.3)

    # 2) G lateral vs tiempo
    ax2=fig.add_subplot(2,2,2)
    for i,(nombre,df) in enumerate(tomas):
        ax2.plot(df["t_s"],df["g_lat"],lw=0.5,color=COLORES[i%5],label=nombre)
    ax2.set_title("G lateral"); ax2.set_xlabel("t [s]"); ax2.set_ylabel("G")
    ax2.legend(fontsize=8); ax2.grid(alpha=.3)

    # 3) Velocidad GPS vs tiempo
    ax3=fig.add_subplot(2,2,3)
    tiene_v=False
    for i,(nombre,df) in enumerate(tomas):
        if "gps_spd" in df and (df["gps_spd"]>0).any():
            tiene_v=True
            ax3.plot(df["t_s"],df["gps_spd"],lw=0.7,color=COLORES[i%5],label=nombre)
    ax3.set_title("Velocidad GPS" if tiene_v else "Velocidad — sin GPS")
    ax3.set_xlabel("t [s]"); ax3.set_ylabel("m/s"); ax3.legend(fontsize=8); ax3.grid(alpha=.3)

    # 4) G-G diagram (lateral vs longitudinal) — la "huella" de conduccion
    ax4=fig.add_subplot(2,2,4)
    for i,(nombre,df) in enumerate(tomas):
        ax4.scatter(df["g_lat"],df["g_lon"],s=3,alpha=.3,color=COLORES[i%5],label=nombre)
    ax4.set_title("G-G diagram (lat vs lon)"); ax4.set_xlabel("G lateral"); ax4.set_ylabel("G longitudinal")
    ax4.axhline(0,color="gray",lw=.5); ax4.axvline(0,color="gray",lw=.5)
    ax4.legend(fontsize=8); ax4.grid(alpha=.3); ax4.axis("equal")

    fig.suptitle(f"Comparación de {len(tomas)} tomas",fontsize=13)
    fig.tight_layout()
    out=str(Path(archivos[0]).with_suffix(""))+"_comparacion.png"
    fig.savefig(out,dpi=150)

    print(f"\n{'toma':<16}{'dur(s)':>8}{'G_lat max':>11}{'vel max(m/s)':>14}")
    for nombre,df in tomas:
        v=df["gps_spd"].max() if "gps_spd" in df else 0
        print(f"{nombre:<16}{df['t_s'].iloc[-1]:>8.1f}{df['g_lat'].abs().max():>11.2f}{v:>14.2f}")
    print(f"\nGuardado: {out}")

if __name__=="__main__":
    if len(sys.argv)<2: sys.exit("Uso: python comparar_tomas.py KART014.CSV KART015.CSV ...")
    main(sys.argv[1:])
