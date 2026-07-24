# fusion_imu_gps_kalman_offline.py
# Corrección OFFLINE de drift IMU con GPS usando Kalman 2D.
#
# Requiere CSV de microSD a 100 Hz, no el CSV LoRa de 2 Hz.
#
# Uso:
#   pip install pandas numpy matplotlib
#   python C:\TelemetriaKart\fusion_imu_gps_kalman_offline.py C:\TelemetriaKart\data\microsd\KART000.CSV
#
# Salidas:
#   C:\TelemetriaKart\resultados\KART000_fusion.csv
#   C:\TelemetriaKart\resultados\KART000_fusion_trayectoria.png
#
# Nota:
# Esto NO corrige roll/pitch. Corrige drift de posición/velocidad.
# Roll/pitch ya se estiman con Kalman IMU en firmware.
# La calidad depende del cero de montaje, orientación de ejes y de tener GPS con movimiento real.

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


G = 9.80665
OUTDIR = Path(r"C:\TelemetriaKart\resultados")


def load_df(path):
    df = pd.read_csv(path)
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    required = ["t_us", "g_lat", "g_lon", "gps_lat", "gps_lon", "gps_speed_mps", "gps_course_deg", "gps_fix"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas para fusión: {missing}")
    df = df.dropna(subset=["t_us", "g_lat", "g_lon"]).sort_values("t_us").reset_index(drop=True)
    df["t_s"] = (df["t_us"] - df["t_us"].iloc[0]) / 1_000_000.0
    return df


def ll_to_xy(lat, lon, lat0, lon0):
    x = (lon - lon0) * 111320.0 * np.cos(np.deg2rad(lat0))
    y = (lat - lat0) * 111320.0
    return x, y


def xy_to_ll(x, y, lat0, lon0):
    lat = lat0 + y / 111320.0
    lon = lon0 + x / (111320.0 * np.cos(np.deg2rad(lat0)))
    return lat, lon


def fuse(df):
    valid = df[(df["gps_fix"] == 1) & (df["gps_lat"] != 0) & (df["gps_lon"] != 0)].copy()
    if len(valid) < 2:
        raise ValueError("No hay suficientes puntos GPS válidos")

    lat0 = float(valid["gps_lat"].iloc[0])
    lon0 = float(valid["gps_lon"].iloc[0])
    df["gps_x_m"], df["gps_y_m"] = ll_to_xy(df["gps_lat"], df["gps_lon"], lat0, lon0)

    first = valid.index[0]

    # Estado: x, y, vx, vy
    x = np.array([df.loc[first, "gps_x_m"], df.loc[first, "gps_y_m"], 0.0, 0.0], dtype=float)

    v0 = float(df.loc[first, "gps_speed_mps"]) if np.isfinite(df.loc[first, "gps_speed_mps"]) else 0.0
    course0 = np.deg2rad(float(df.loc[first, "gps_course_deg"]) if np.isfinite(df.loc[first, "gps_course_deg"]) else 0.0)
    x[2] = v0 * np.sin(course0)
    x[3] = v0 * np.cos(course0)

    P = np.diag([25.0, 25.0, 4.0, 4.0])
    accel_noise = 1.5
    gps_pos_sigma_base = 3.0
    gps_vel_sigma = 0.8

    last_t = float(df["t_s"].iloc[0])
    heading = course0
    rows = []

    for _, r in df.iterrows():
        t = float(r["t_s"])
        dt = max(0.001, min(0.2, t - last_t))
        last_t = t

        gps_fix = int(r["gps_fix"]) == 1
        gps_speed = float(r["gps_speed_mps"]) if np.isfinite(r["gps_speed_mps"]) else 0.0

        # Solo usar rumbo GPS cuando hay movimiento. En reposo el rumbo GPS es inestable.
        if gps_fix and gps_speed > 0.5 and np.isfinite(r["gps_course_deg"]):
            heading = np.deg2rad(float(r["gps_course_deg"]))

        # Aceleración corporal aproximada. g_lon=adelante, g_lat=lateral.
        a_fwd = float(r["g_lon"]) * G
        a_lat = float(r["g_lat"]) * G

        # Convertir a marco local usando heading GPS.
        ax_w = a_fwd * np.sin(heading) + a_lat * np.cos(heading)
        ay_w = a_fwd * np.cos(heading) - a_lat * np.sin(heading)

        F = np.array([[1,0,dt,0],[0,1,0,dt],[0,0,1,0],[0,0,0,1]], dtype=float)
        B = np.array([[0.5*dt*dt,0],[0,0.5*dt*dt],[dt,0],[0,dt]], dtype=float)
        u = np.array([ax_w, ay_w])

        q = accel_noise**2
        Q = q*np.array([
            [dt**4/4,0,dt**3/2,0],
            [0,dt**4/4,0,dt**3/2],
            [dt**3/2,0,dt**2,0],
            [0,dt**3/2,0,dt**2]
        ])

        # Predicción IMU
        x = F @ x + B @ u
        P = F @ P @ F.T + Q

        # Corrección GPS posición
        if gps_fix and float(r["gps_lat"]) != 0 and float(r["gps_lon"]) != 0:
            z = np.array([float(r["gps_x_m"]), float(r["gps_y_m"])])
            H = np.array([[1,0,0,0],[0,1,0,0]], dtype=float)

            hdop = float(r["gps_hdop"]) if "gps_hdop" in r and np.isfinite(r["gps_hdop"]) else 2.0
            sigma = max(gps_pos_sigma_base, gps_pos_sigma_base * hdop)
            R = np.diag([sigma**2, sigma**2])

            y = z - H @ x
            S = H @ P @ H.T + R
            K = P @ H.T @ np.linalg.inv(S)
            x = x + K @ y
            P = (np.eye(4) - K @ H) @ P

            # Corrección GPS velocidad
            if gps_speed >= 0.1 and np.isfinite(r["gps_course_deg"]):
                c = np.deg2rad(float(r["gps_course_deg"]))
                zv = np.array([gps_speed*np.sin(c), gps_speed*np.cos(c)])
                Hv = np.array([[0,0,1,0],[0,0,0,1]], dtype=float)
                Rv = np.diag([gps_vel_sigma**2, gps_vel_sigma**2])
                yv = zv - Hv @ x
                Sv = Hv @ P @ Hv.T + Rv
                Kv = P @ Hv.T @ np.linalg.inv(Sv)
                x = x + Kv @ yv
                P = (np.eye(4) - Kv @ Hv) @ P

        flat, flon = xy_to_ll(x[0], x[1], lat0, lon0)
        rows.append({
            "t_s": t,
            "fused_x_m": x[0],
            "fused_y_m": x[1],
            "fused_vx_mps": x[2],
            "fused_vy_mps": x[3],
            "fused_speed_mps": float(np.hypot(x[2], x[3])),
            "fused_lat": flat,
            "fused_lon": flon,
            "gps_x_m": float(r["gps_x_m"]),
            "gps_y_m": float(r["gps_y_m"]),
            "gps_fix": int(r["gps_fix"]),
            "gps_speed_mps": gps_speed,
        })

    return pd.DataFrame(rows)


def plot(out, prefix):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    png = OUTDIR / f"{prefix}_fusion_trayectoria.png"

    fig, ax = plt.subplots(figsize=(8,7))
    valid = out[out["gps_fix"] == 1]
    if len(valid):
        ax.plot(valid["gps_x_m"], valid["gps_y_m"], ".", alpha=0.35, label="GPS crudo")
    ax.plot(out["fused_x_m"], out["fused_y_m"], linewidth=2.0, label="Fusión IMU+GPS Kalman")
    ax.scatter([out["fused_x_m"].iloc[0]], [out["fused_y_m"].iloc[0]], s=70, label="Inicio")
    ax.scatter([out["fused_x_m"].iloc[-1]], [out["fused_y_m"].iloc[-1]], s=70, label="Final")
    ax.set_title("Corrección de drift IMU con GPS")
    ax.set_xlabel("Este-Oeste [m]")
    ax.set_ylabel("Norte-Sur [m]")
    ax.axis("equal")
    ax.grid(True, alpha=.3)
    ax.legend()
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return png


def main():
    if len(sys.argv) < 2:
        print("ERROR: pasa el archivo KARTxxx.CSV de microSD.")
        print(r"Ejemplo: python C:\TelemetriaKart\fusion_imu_gps_kalman_offline.py C:\TelemetriaKart\data\microsd\KART000.CSV")
        return

    path = Path(sys.argv[1])
    OUTDIR.mkdir(parents=True, exist_ok=True)

    try:
        df = load_df(path)
        out = fuse(df)
        out_csv = OUTDIR / f"{path.stem}_fusion.csv"
        out.to_csv(out_csv, index=False)
        out_png = plot(out, path.stem)

        print("=== FUSIÓN IMU + GPS ===")
        print(f"Entrada: {path}")
        print(f"Salida CSV: {out_csv}")
        print(f"Salida PNG: {out_png}")
        print("Nota: esta fusión corrige drift de posición/velocidad, no roll/pitch.")
    except Exception as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    main()
