"""
capturar_serial.py — Captura el CSV que emite el ESP32 y lo guarda en data/
Uso:
    pip install pyserial
    python capturar_serial.py COM5            # Windows (ver puerto en el IDE)
    python capturar_serial.py COM5 --min 10   # detener a los 10 minutos
Detener manualmente: Ctrl+C (el archivo queda cerrado y válido).
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import serial

BAUD = 500000

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("puerto", help="p.ej. COM5 o /dev/ttyUSB0")
    ap.add_argument("--min", type=float, default=0, help="minutos a capturar (0 = hasta Ctrl+C)")
    ap.add_argument("--nombre", default="sesion", help="prefijo del archivo")
    args = ap.parse_args()

    Path("data").mkdir(exist_ok=True)
    fname = Path("data") / f"{args.nombre}_{datetime.now():%Y%m%d_%H%M%S}.csv"

    ser = serial.Serial(args.puerto, BAUD, timeout=2)
    ser.reset_input_buffer()
    print(f"Capturando de {args.puerto} -> {fname}  (Ctrl+C para detener)")

    t0 = time.time()
    n = 0
    try:
        with open(fname, "w", newline="", encoding="utf-8", errors="replace") as f:
            f.write(f"# capturado={datetime.now().isoformat()} puerto={args.puerto}\n")
            while True:
                linea = ser.readline().decode(errors="replace").strip()
                if not linea:
                    continue
                f.write(linea + "\n")
                if not linea.startswith("#"):
                    n += 1
                    if n % 1000 == 0:
                        rate = n / (time.time() - t0)
                        print(f"\r{n} muestras  (~{rate:.1f} Hz)", end="")
                if args.min and (time.time() - t0) >= args.min * 60:
                    break
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()

    dur = time.time() - t0
    print(f"\nListo: {n} muestras en {dur:.1f} s ({n/dur:.1f} Hz efectivos) -> {fname}")
    if n and abs(n / dur - 100) > 3:
        print("AVISO: la tasa efectiva difiere de 100 Hz. Revisar baudios/pérdidas.")

if __name__ == "__main__":
    sys.exit(main())