"""Hipótesis para datos **reales** de péndulo (Fase 1 de la hoja de ruta).

Diferencias con la versión sintética, y por qué:

1. **g no está fijada.** En un experimento real la gravedad local no se conoce
   a priori; se estima con los propios datos de calibración. Fijarla en
   9.80665 sería imponer la respuesta.
2. **La incertidumbre es experimental.** El dataset trae ``u_T_s`` por fila y
   T10 la usa como término explícito del presupuesto, no como ruido de ajuste.
3. **El baseline también se ajusta.** Comparar un modelo con g ajustada contra
   otro con g nominal daría una ventaja artificial.

Este módulo no genera datos ni afirma nada: sólo declara cómo se contrasta la
corrección de amplitud cuando el período se midió de verdad.

Confondo conocido
-----------------
``ajustar_g`` estima g con el cuartil inferior de amplitud porque ignora la
corrección. Queda un sesgo residual a la baja del orden del 0.3 %, que infla
ligeramente el error del baseline y por tanto favorece a la hipótesis. Está
documentado y medido en las pruebas; corregirlo del todo exige un modelo
conjunto (g, c2) o datos de amplitud pequeña dedicados, que es trabajo de la
Fase 1 con datos reales.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from lab.contrato import Dominio, Hipotesis, Modelo, Parametro

G_NOMINAL = 9.80665  # m/s^2, sólo como valor inicial del ajuste


def ajustar_g(L: np.ndarray, T: np.ndarray, theta: np.ndarray | None = None) -> float:
    """Estima g por mínimos cuadrados sobre T² = (4π²/g)·L.

    Es una regresión lineal por el origen. Si se pasan amplitudes, se usan sólo
    las filas de menor θ0: el modelo lineal ignora la corrección de amplitud, y
    ajustar con amplitudes grandes sesgaría g a la baja, regalándole error al
    baseline y favoreciendo artificialmente a la hipótesis.
    """
    L = np.asarray(L, dtype=float)
    T = np.asarray(T, dtype=float)
    if theta is not None:
        theta = np.asarray(theta, dtype=float)
        if theta.size == L.size and theta.size:
            corte = float(np.quantile(theta, 0.25))
            mascara = theta <= corte
            if int(np.count_nonzero(mascara)) >= 10:
                L, T = L[mascara], T[mascara]
    b = T ** 2
    denominador = float(np.sum(L * L))
    if denominador <= 0 or not np.all(np.isfinite(b)):
        raise ValueError("Datos no utilizables para estimar g")
    pendiente = float(np.sum(L * b) / denominador)
    if pendiente <= 0:
        raise ValueError("Pendiente no positiva al estimar g")
    return float(4.0 * np.pi ** 2 / pendiente)


class PenduloLinealMedido(Modelo):
    """Baseline: T = 2π√(L/g) con g estimada de los datos de calibración."""

    id = "pendulo_lineal_medido"
    nombre = "Péndulo simple con g estimada"
    version = "1.0.0"
    observables = ("T_s",)
    requiere = ("L_m", "theta0_rad")
    supuestos = (
        "Amplitud despreciable; g se estima por regresión T²-L, que ignora la "
        "corrección de amplitud a propósito."
    )

    PARAMETROS = (
        Parametro("g", G_NOMINAL, "m/s^2", congelado=False,
                  descripcion="Gravedad local estimada con calibración"),
    )

    def predecir(self, variables, parametros):
        L = np.asarray(variables["L_m"], dtype=float)
        g = float(parametros["g"])
        if g <= 0 or np.any(L <= 0):
            raise ValueError("g y L deben ser positivas")
        return {"T_s": 2.0 * np.pi * np.sqrt(L / g)}

    def ajustar(self, variables, observado, parametros):
        actualizado = dict(parametros)
        actualizado["g"] = ajustar_g(
            variables["L_m"], observado, variables.get("theta0_rad")
        )
        return actualizado


class PenduloAmplitudMedida(Modelo):
    """Baseline alternativo: g estimada más corrección cuadrática fija."""

    id = "pendulo_amplitud_medida_alternativo"
    nombre = "Péndulo con g estimada y corrección cuadrática fija"
    version = "1.0.0"
    observables = ("T_s",)
    requiere = ("L_m", "theta0_rad")
    supuestos = "g estimada de los datos; c2 = 1/16 fijo, c4 = 0."

    PARAMETROS = (
        Parametro("g", G_NOMINAL, "m/s^2", congelado=False),
        Parametro("c2", 1.0 / 16.0, "rad^-2", congelado=True),
    )

    def predecir(self, variables, parametros):
        L = np.asarray(variables["L_m"], dtype=float)
        th = np.asarray(variables["theta0_rad"], dtype=float)
        t0 = 2.0 * np.pi * np.sqrt(L / float(parametros["g"]))
        return {"T_s": t0 * (1.0 + float(parametros["c2"]) * th ** 2)}

    def ajustar(self, variables, observado, parametros):
        actualizado = dict(parametros)
        actualizado["g"] = ajustar_g(
            variables["L_m"], observado, variables.get("theta0_rad")
        )
        return actualizado


class PenduloAmplitudReal(Hipotesis):
    """La corrección de amplitud existe también en datos medidos."""

    id = "pendulo_amplitud_real"
    nombre = "Corrección de amplitud en un péndulo medido"
    version = "1.0.0"

    observables = ("T_s",)
    requiere = ("L_m", "theta0_rad")

    enunciado = (
        "En un péndulo real, el período medido crece con la amplitud por encima "
        "de lo que predice la teoría de pequeña amplitud con la misma g."
    )
    prediccion_diferenciadora = (
        "Para θ0 ≈ 0.3 rad la corrección predice un exceso de ~0.6 % del período "
        "frente al modelo lineal, creciente con θ0². Con incertidumbre de "
        "periodo del orden de 1 ms en períodos de ~2 s, la separación es "
        "resoluble en un barrido de amplitudes."
    )

    dominio = Dominio(
        descripcion="Péndulo físico real, amplitudes moderadas, un solo hilo y masa",
        rango={"L_m": (0.05, 10.0), "theta0_rad": (0.0, 1.5)},
        limitaciones=(
            "Amortiguamiento no modelado: si es apreciable, contamina el período.",
            "Requiere que θ0 se haya medido, no supuesto.",
            "La estimación de g ignora la corrección de amplitud por diseño.",
        ),
    )

    observable_objetivo = "T_s"
    unidad_observable = "s"
    baseline = PenduloLinealMedido()
    baselines_alternativos = (PenduloAmplitudMedida(),)

    dataset_id = "pendulo_real"

    metrica = "rmse"
    umbral_mejora = 0.10
    factor_diferenciacion = 1.0
    umbral_sensibilidad = None
    #: La incertidumbre viene del dataset (u_T_s); no se declara un número
    #: inventado. T10 combina declarada ⊕ experimental y aquí sólo hay la segunda.
    incertidumbre_declarada = float("nan")
    semilla = 2026

    PARAMETROS = (
        Parametro("g", G_NOMINAL, "m/s^2", congelado=False,
                  descripcion="Gravedad estimada con la calibración"),
        Parametro("c2", 0.0, "rad^-2", congelado=False,
                  descripcion="Coeficiente de θ0²"),
        Parametro("c4", 0.0, "rad^-4", congelado=False,
                  descripcion="Coeficiente de θ0⁴"),
    )

    def predecir(
        self,
        variables: Mapping[str, np.ndarray],
        parametros: Mapping[str, float],
    ) -> dict[str, np.ndarray]:
        L = np.asarray(variables["L_m"], dtype=float)
        th = np.asarray(variables["theta0_rad"], dtype=float)
        t0 = 2.0 * np.pi * np.sqrt(L / float(parametros["g"]))
        return {
            "T_s": t0 * (
                1.0 + float(parametros["c2"]) * th ** 2
                + float(parametros["c4"]) * th ** 4
            )
        }

    def ajustar(self, variables, observado, parametros):
        """Primero g con el subconjunto de baja amplitud; después c2 y c4."""
        actualizado = dict(parametros)
        g = ajustar_g(
            variables["L_m"], observado, variables.get("theta0_rad")
        )
        actualizado["g"] = g
        L = np.asarray(variables["L_m"], dtype=float)
        th = np.asarray(variables["theta0_rad"], dtype=float)
        y = np.asarray(observado, dtype=float)
        t0 = 2.0 * np.pi * np.sqrt(L / g)
        diseno = np.column_stack([t0 * th ** 2, t0 * th ** 4])
        coef, *_ = np.linalg.lstsq(diseno, y - t0, rcond=None)
        actualizado["c2"] = float(coef[0])
        actualizado["c4"] = float(coef[1])
        return actualizado


def registrar() -> list[Modelo]:
    return [PenduloLinealMedido(), PenduloAmplitudMedida(), PenduloAmplitudReal()]
