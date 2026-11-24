"""Genera el CSV de prueba con el **esquema real** de la Fase 1.

No son datos medidos: son datos sintéticos escritos con las mismas columnas que
tendrá el CSV real (``L_m, theta0_rad, T_s, u_T_s, u_L_m, u_theta0_rad``), para
poder probar la tubería antes de tener una medición.

La gravedad local se fija en un valor distinto del nominal (9.7923 m/s²) a
propósito: si el ajuste no estimara g, la prueba lo detectaría.

    python pruebas/fixtures/generar_fixture.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

G_LOCAL = 9.7923          # m/s^2, distinto de 9.80665
FILAS = 120
SEMILLA = 20261124


def main() -> int:
    rng = np.random.default_rng(SEMILLA)
    L = rng.uniform(0.60, 1.80, size=FILAS)
    theta = rng.uniform(0.05, 0.70, size=FILAS)

    t0 = 2.0 * np.pi * np.sqrt(L / G_LOCAL)
    verdad = t0 * (1.0 + theta ** 2 / 16.0 + 11.0 * theta ** 4 / 3072.0)

    # Ruido heterocedástico: peor a amplitudes grandes, como en una medición real.
    sigma = (1.0 + 0.6 * theta / theta.max()) * 1.0e-3
    T = verdad + rng.normal(0.0, sigma, size=FILAS)

    # Incertidumbre declarada ligeramente conservadora respecto al ruido real.
    u_T = sigma * 1.1
    u_L = np.full(FILAS, 1.0e-3)
    u_theta = np.full(FILAS, 2.0e-3)

    destino = Path(__file__).resolve().parent / "pendulo_medido_fixture.csv"
    with open(destino, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f, lineterminator="\n")
        escritor.writerow(["L_m", "theta0_rad", "T_s", "u_T_s", "u_L_m", "u_theta0_rad"])
        for i in range(FILAS):
            escritor.writerow([
                f"{L[i]:.6f}", f"{theta[i]:.6f}", f"{T[i]:.7f}",
                f"{u_T[i]:.7f}", f"{u_L[i]:.7f}", f"{u_theta[i]:.7f}",
            ])

    print(f"Escrito {destino} con {FILAS} filas")
    print(f"  g usada para generar: {G_LOCAL} m/s^2")
    print(f"  período: {T.min():.4f}–{T.max():.4f} s")
    print(f"  u_T: {u_T.min():.2e}–{u_T.max():.2e} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
