"""Hipótesis de ejemplo 2: un polinomio con demasiados parámetros libres.

Es el caso de control **negativo** del laboratorio: debe fracasar. Si una
hipótesis con 16 coeficientes ajustados sobre 36 filas saliera corroborada, el
laboratorio estaría aprobando sobreajuste.

Qué demuestra: que la batería no se conforma con "mejor ajuste en la muestra
de calibración". El sobreajuste se detecta en T06 (no generaliza), T07 (no
supera al baseline fuera de muestra) y, a veces, T11 (gana también sobre
datos generados por el baseline).
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from lab.contrato import Dominio, Hipotesis, Parametro

from .pendulo_amplitud import PenduloLineal

#: Grado del polinomio: 16 coeficientes libres sobre 36 filas de calibración.
GRADO = 15
MU = 0.6
S = 0.3


def _parametros() -> tuple[Parametro, ...]:
    fijos = (
        Parametro("g", 9.80665, "m/s^2", congelado=True, descripcion="Gravedad"),
        Parametro("mu", MU, "rad", congelado=True, descripcion="Centro de normalización"),
        Parametro("s", S, "rad", congelado=True, descripcion="Escala de normalización"),
    )
    libres = tuple(
        Parametro(f"c{k}", 0.0, "1", congelado=False,
                  descripcion=f"Coeficiente del término z^{k}")
        for k in range(GRADO + 1)
    )
    return fijos + libres


class PenduloPolinomioAlto(Hipotesis):
    """Ajusta el período con un polinomio de grado 15 en la amplitud."""

    id = "pendulo_polinomio_alto"
    nombre = "Péndulo: polinomio de grado 15 en la amplitud"
    version = "1.0.0"

    observables = ("T_s",)
    requiere = ("L_m", "theta0_rad")

    enunciado = (
        "La dependencia del período con la amplitud no sigue una serie truncada, "
        "sino una curva suave que un polinomio de grado 15 representa mejor."
    )
    prediccion_diferenciadora = (
        "Un polinomio flexible reproduce cualquier estructura fina de la curva "
        "T(θ0) que la serie de cuarto orden no captura, incluida la que aparece "
        "a amplitudes intermedias."
    )

    dominio = Dominio(
        descripcion="Péndulo simple ideal, amplitudes moderadas",
        rango={"L_m": (0.40, 2.50), "theta0_rad": (0.0, 0.10)},
        limitaciones=("Polinomio sin base física: no extrapola fuera del rango ajustado.",),
    )

    observable_objetivo = "T_s"
    unidad_observable = "s"
    baseline = PenduloLineal()

    dataset_id = "pendulo_amplitud_pequena_v1"
    metrica = "rmse"
    umbral_mejora = 0.10
    umbral_sensibilidad = 1.0e-4
    incertidumbre_declarada = 1.0e-3
    semilla = 20261125

    PARAMETROS = _parametros()

    # -- contrato ------------------------------------------------------

    def predecir(
        self,
        variables: Mapping[str, np.ndarray],
        parametros: Mapping[str, float],
    ) -> dict[str, np.ndarray]:
        L = np.asarray(variables["L_m"], dtype=float)
        th = np.asarray(variables["theta0_rad"], dtype=float)
        g = float(parametros["g"])
        z = (th - float(parametros["mu"])) / float(parametros["s"])
        t0 = 2.0 * np.pi * np.sqrt(L / g)

        polinomio = np.zeros_like(z)
        for k in range(GRADO, -1, -1):
            polinomio = polinomio * z + float(parametros[f"c{k}"])
        return {"T_s": t0 * polinomio}

    def ajustar(
        self,
        variables: Mapping[str, np.ndarray],
        observado: np.ndarray,
        parametros: Mapping[str, float],
    ) -> dict[str, float]:
        L = np.asarray(variables["L_m"], dtype=float)
        th = np.asarray(variables["theta0_rad"], dtype=float)
        y = np.asarray(observado, dtype=float)
        g = float(parametros["g"])
        z = (th - float(parametros["mu"])) / float(parametros["s"])
        t0 = 2.0 * np.pi * np.sqrt(L / g)
        diseno = np.column_stack([t0 * z ** k for k in range(GRADO + 1)])
        coeficientes, *_ = np.linalg.lstsq(diseno, y, rcond=None)
        actualizado = dict(parametros)
        for k, valor in enumerate(coeficientes):
            actualizado[f"c{k}"] = float(valor)
        return actualizado


def registrar() -> list[Hipotesis]:
    # El baseline ``PenduloLineal`` ya lo registra ``pendulo_amplitud``; aquí
    # sólo se usa como referencia y no se vuelve a declarar.
    return [PenduloPolinomioAlto()]
