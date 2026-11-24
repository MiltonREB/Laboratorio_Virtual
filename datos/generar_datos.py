"""Genera los datasets sintéticos de demostración del laboratorio.

Estos datos NO son una medición. Son un control de la maquinaria del
laboratorio: la verdad generadora está escrita en el propio código y los
números son reproducibles bit a bit.

Modelo generador (péndulo simple, corrección de amplitud finita):

    T = 2π√(L/g) · (1 + θ0²/16 + 11·θ0⁴/3072) + ε,   ε ~ N(0, σ²)

con g = 9.80665 m/s², σ = 8.0e-4 s.

Ejecutar desde la raíz del laboratorio:

    python datos/generar_datos.py

Volver a ejecutarlo produce los mismos bytes (semillas fijas), así que los
SHA-256 del manifiesto no cambian.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

G = 9.80665           # m/s^2
SIGMA = 8.0e-4        # s


def periodo_real(L: np.ndarray, theta0: np.ndarray) -> np.ndarray:
    """Serie de amplitud finita hasta θ⁴, con la que se generan los datos."""
    t0 = 2.0 * np.pi * np.sqrt(L / G)
    return t0 * (1.0 + theta0 ** 2 / 16.0 + 11.0 * theta0 ** 4 / 3072.0)


def _escribir_csv(ruta: Path, filas: list[tuple[float, float, float]]) -> None:
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["L_m", "theta0_rad", "T_s"])
        for L, th, T in filas:
            w.writerow([f"{L:.17g}", f"{th:.17g}", f"{T:.17g}"])


def _sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _generar(
    n: int,
    semilla: int,
    theta_min: float = 0.02,
    theta_max: float = 1.20,
    l_min: float = 0.50,
    l_max: float = 2.00,
    sigma: float = SIGMA,
) -> tuple[list[tuple[float, float, float]], tuple[int, ...], tuple[int, ...]]:
    rng = np.random.default_rng(semilla)
    L = rng.uniform(l_min, l_max, size=n)
    theta0 = rng.uniform(theta_min, theta_max, size=n)
    T = periodo_real(L, theta0) + rng.normal(0.0, sigma, size=n)

    orden = rng.permutation(n)
    corte = int(round(n * 0.60))
    calibracion = tuple(sorted(int(i) for i in orden[:corte]))
    reservado = tuple(sorted(int(i) for i in orden[corte:]))
    filas = [(float(L[i]), float(theta0[i]), float(T[i])) for i in range(n)]
    return filas, calibracion, reservado


def main() -> int:
    raiz = Path(__file__).resolve().parent
    especificaciones = [
        dict(
            id="pendulo_v1",
            archivo="pendulo_v1.csv",
            n=240,
            semilla=20261124,
            theta_min=0.02,
            theta_max=1.20,
            descripcion=(
                "Péndulo simple sintético (240 filas). Control de la maquinaria del "
                "laboratorio: la verdad generadora es "
                "T = 2π√(L/g)(1+θ²/16+11θ⁴/3072) + ruido gaussiano σ=8e-4 s. "
                "No es una medición física."
            ),
            notas=(
                "Amplitudes hasta 1.2 rad: la corrección de amplitud es grande "
                "frente al ruido."
            ),
        ),
        dict(
            id="pendulo_amplitud_pequena_v1",
            archivo="pendulo_amplitud_pequena_v1.csv",
            n=72,
            semilla=20261125,
            theta_min=0.005,
            theta_max=0.08,
            descripcion=(
                "Péndulo simple sintético (72 filas), misma verdad generadora, "
                "amplitudes muy pequeñas. La corrección de amplitud vale del orden "
                "del ruido, así que un modelo flexible sólo puede ajustar ruido."
            ),
            notas=(
                "Diseñado para que el sobreajuste sea detectable: no hay señal "
                "suficiente para sostener 16 parámetros."
            ),
        ),
        dict(
            id="pendulo_holdout_v1",
            archivo="pendulo_holdout_v1.csv",
            n=80,
            semilla=20261126,
            theta_min=0.03,
            theta_max=0.95,
            l_min=0.45,
            l_max=2.30,
            sigma=1.2e-3,
            uso="validacion_externa",
            descripcion=(
                "Péndulo simple sintético (80 filas) generado aparte, con otro "
                "rango de longitudes y amplitudes y otro nivel de ruido (σ=1.2e-3 s). "
                "Sirve de holdout externo: no tiene partición calibración/reservado "
                "porque no se ajusta nada con él."
            ),
            notas=(
                "Se declara como dataset_validacion de una hipótesis. Su error no "
                "interviene en el veredicto: lo reporta la verificación O04."
            ),
        ),
    ]

    entradas = []
    for spec in especificaciones:
        filas, calibracion, reservado = _generar(
            spec["n"], spec["semilla"], spec.get("theta_min", 0.02),
            spec.get("theta_max", 1.20), spec.get("l_min", 0.50),
            spec.get("l_max", 2.00), spec.get("sigma", SIGMA),
        )
        ruta = raiz / spec["archivo"]
        _escribir_csv(ruta, filas)
        entrada = {
            "id": spec["id"],
            "ruta": spec["archivo"],
            "sha256": _sha256(ruta),
            "descripcion": spec["descripcion"],
            "notas": spec["notas"],
            "origen": "sintetico",
            "generado_por": "datos/generar_datos.py",
            "variables": ["L_m", "theta0_rad"],
            "observables": ["T_s"],
            "unidades": {"L_m": "m", "theta0_rad": "rad", "T_s": "s"},
            "filas": spec["n"],
            "ruido": {"T_s": spec.get("sigma", SIGMA)},
        }
        if spec.get("uso") == "validacion_externa":
            entrada["uso"] = "validacion_externa"
        else:
            entrada["calibracion"] = list(calibracion)
            entrada["reservado"] = list(reservado)
        entradas.append(entrada)

    manifiesto = {
        "version": 1,
        "descripcion": (
            "Catálogo de datasets congelados del laboratorio. Cada entrada declara "
            "su SHA-256, sus unidades y la partición calibración/reservado. Si un "
            "CSV cambia, el laboratorio rechaza la evaluación hasta que el "
            "manifiesto se actualice de forma explícita."
        ),
        "datasets": entradas,
    }
    destino = raiz / "manifiesto.json"
    destino.write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    for e in entradas:
        cal = len(e.get("calibracion", []))
        res = len(e.get("reservado", []))
        uso = e.get("uso", "ajuste")
        print(f"{e['id']:30s} filas={e['filas']:4d}  "
              f"cal={cal:3d}  res={res:3d}  uso={uso:15s} "
              f"sha256={e['sha256'][:16]}...")
    print(f"\nManifiesto escrito en {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
