"""
seis_posiciones.py — Prueba de seis posiciones con AUTODETECCIÓN de cara.
Captura 6 archivos (uno por cara del módulo, en cualquier orden) y este script
detecta solo qué eje quedó vertical en cada uno, verifica que estén las 6
orientaciones y calcula offset y sensibilidad por eje del acelerómetro,
además del bias promedio del giroscopio.

Uso:
    python seis_posiciones.py data\\pos_1_*.csv ... (o simplemente:)
    python seis_posiciones.py data\\pos_*.csv
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

G = 9.80665
COLS = ["t_us", "ax", "ay", "az", "gx", "gy", "gz"]

def cargar(path):
    df = pd.read_csv(path, comment="#", header=None, names=COLS, on_bad_lines="skip")
    df = df.apply(pd.to_numeric, errors="coerce").dropna()
    return df

def main(patrones):
    archivos = []
    for p in patrones:
        archivos += glob.glob(p)
    archivos = sorted(set(archivos))
    if len(archivos) < 6:
        sys.exit(f"Se encontraron {len(archivos)} archivos; se necesitan 6 (uno por cara). "
                 f"Patrones: {patrones}")

    print(f"{len(archivos)} archivos encontrados.\n")
    medias = {}   # clave: ('ax','+') etc. -> (media del eje vertical, archivo, medias 6 canales)
    for f in archivos:
        df = cargar(f)
        m = df[["ax", "ay", "az"]].mean()
        eje = m.abs().idxmax()               # eje dominante = el vertical
        signo = "+" if m[eje] > 0 else "-"
        # Validaciones básicas
        residual = np.sqrt(sum(m[e] ** 2 for e in ["ax", "ay", "az"] if e != eje))
        if abs(m[eje]) < 8.5:
            print(f"AVISO {Path(f).name}: eje dominante {eje} solo marca {m[eje]:.2f} m/s² "
                  f"(¿estaba inclinado o en movimiento?)")
        if residual > 1.5:
            print(f"AVISO {Path(f).name}: componentes horizontales grandes ({residual:.2f} m/s²) "
                  f"-> cara mal apoyada (inclinación ~{np.degrees(np.arcsin(min(residual/G,1))):.1f}°)")
        clave = (eje, signo)
        if clave in medias:
            print(f"AVISO: orientación {signo}{eje} repetida ({Path(f).name} y "
                  f"{Path(medias[clave][1]).name}); se usa la primera.")
            continue
        medias[clave] = (m[eje], f, df[["gx", "gy", "gz"]].mean())
        print(f"{Path(f).name:<40} -> cara {signo}{eje}  ({m[eje]:+.4f} m/s²)")

    faltan = [f"{s}{e}" for e in ["ax", "ay", "az"] for s in ["+", "-"]
              if (e, s) not in medias]
    if faltan:
        sys.exit(f"\nFaltan orientaciones: {faltan}. Captura esas caras y repite.")

    print("\n=== Tabla seis posiciones (acelerómetro) ===")
    print(f"{'eje':<5}{'media +g':>12}{'media -g':>12}{'offset':>12}{'sensibilidad':>14}{'error escala':>14}")
    filas = []
    for eje in ["ax", "ay", "az"]:
        mp = medias[(eje, "+")][0]
        mn = medias[(eje, "-")][0]
        offset = (mp + mn) / 2
        sens = (mp - mn) / (2 * G)
        err = (sens - 1) * 100
        print(f"{eje:<5}{mp:>12.4f}{mn:>12.4f}{offset:>12.4f}{sens:>14.4f}{err:>13.2f}%")
        filas.append(dict(eje=eje, media_pos_g=mp, media_neg_g=mn,
                          offset_ms2=offset, sensibilidad=sens, error_escala_pct=err))

    # Bias del gyro: promedio de las 6 capturas (todas en reposo)
    gb = pd.concat([m[2] for m in medias.values()], axis=1).mean(axis=1)
    print("\nBias giroscopio (promedio de las 6 capturas):")
    print(f"  gx={gb['gx']:+.3f}  gy={gb['gy']:+.3f}  gz={gb['gz']:+.3f}  °/s")

    out = Path("data") / "seis_posiciones_resultado.csv"
    pd.DataFrame(filas).to_csv(out, index=False)
    print(f"\nGuardado: {out}")
    print("Estos offsets y sensibilidades van directo a la tabla 6.2 del informe y")
    print("a la corrección de calibración del firmware (Fase 5):")
    print("  a_corregida = (a_medida - offset) / sensibilidad")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Uso: python seis_posiciones.py data\\pos_*.csv")
    main(sys.argv[1:])
