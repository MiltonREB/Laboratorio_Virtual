"""Hipótesis de ejemplo 1: corrección de amplitud finita del péndulo.

Es el caso de control del laboratorio: una hipótesis que **debe** corroborarse
si la maquinaria funciona, porque los datos se generaron justamente con la
ley que la hipótesis propone. Sirve para comprobar que las doce pruebas no
rechazan por sistema.

Contraste que se explota: el baseline de pequeña amplitud predice un período
independiente de θ0; la hipótesis predice que crece con θ0², que es una
diferencia medible con estos datos.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from lab.contrato import Dominio, Hipotesis, Modelo, Parametro

G = 9.80665  # m/s^2


class PenduloLineal(Modelo):
    """Baseline: péndulo simple de pequeña amplitud, T = 2π√(L/g)."""

    id = "pendulo_lineal"
    nombre = "Péndulo simple de pequeña amplitud"
    version = "1.0.0"
    observables = ("T_s",)
    requiere = ("L_m", "theta0_rad")
    supuestos = (
        "Amplitud despreciable (θ0 → 0), masa puntual, sin rozamiento, g fija. "
        "No depende de θ0."
    )

    PARAMETROS = (
        Parametro("g", G, "m/s^2", congelado=True,
                  descripcion="Gravedad estándar; no se ajusta"),
    )

    def predecir(
        self,
        variables: Mapping[str, np.ndarray],
        parametros: Mapping[str, float],
    ) -> dict[str, np.ndarray]:
        L = np.asarray(variables["L_m"], dtype=float)
        g = float(parametros["g"])
        if np.any(L <= 0):
            raise ValueError("L_m debe ser positiva")
        return {"T_s": 2.0 * np.pi * np.sqrt(L / g)}


class PenduloSegundoOrden(Modelo):
    """Baseline alternativo: corrección de amplitud truncada en θ0².

    Es un rival más exigente que el péndulo lineal, porque ya incorpora el
    término dominante. Sirve para la verificación O01: ganar al modelo lineal
    es fácil; ganar a este no lo es tanto.
    """

    id = "pendulo_segundo_orden"
    nombre = "Péndulo con corrección cuadrática de amplitud"
    version = "1.0.0"
    observables = ("T_s",)
    requiere = ("L_m", "theta0_rad")
    supuestos = "Serie de amplitud truncada en θ0², con coeficiente 1/16."

    PARAMETROS = (
        Parametro("g", G, "m/s^2", congelado=True),
        Parametro("c2", 1.0 / 16.0, "rad^-2", congelado=True),
    )

    def predecir(
        self,
        variables: Mapping[str, np.ndarray],
        parametros: Mapping[str, float],
    ) -> dict[str, np.ndarray]:
        L = np.asarray(variables["L_m"], dtype=float)
        th = np.asarray(variables["theta0_rad"], dtype=float)
        t0 = 2.0 * np.pi * np.sqrt(L / float(parametros["g"]))
        return {"T_s": t0 * (1.0 + float(parametros["c2"]) * th ** 2)}


class PenduloSerieCuartoOrden(Modelo):
    """Baseline alternativo: la misma serie que la hipótesis, con coeficientes fijos.

    Representa el caso incómodo: un rival correcto cuyos coeficientes no se
    ajustaron con estos datos. Si la hipótesis no lo supera, su ventaja puede
    venir del ajuste y no de la forma funcional.
    """

    id = "pendulo_serie_cuarto_orden"
    nombre = "Péndulo con serie de cuarto orden fija"
    version = "1.0.0"
    observables = ("T_s",)
    requiere = ("L_m", "theta0_rad")
    supuestos = (
        "Serie 1 + θ²/16 + 11θ⁴/3072 con coeficientes conocidos, sin ajuste."
    )

    PARAMETROS = (
        Parametro("g", G, "m/s^2", congelado=True),
        Parametro("c2", 1.0 / 16.0, "rad^-2", congelado=True),
        Parametro("c4", 11.0 / 3072.0, "rad^-4", congelado=True),
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
                1.0
                + float(parametros["c2"]) * th ** 2
                + float(parametros["c4"]) * th ** 4
            )
        }


class PenduloAmplitudFinita(Hipotesis):
    """El período crece con la amplitud según 1 + c2·θ0² + c4·θ0⁴."""

    id = "pendulo_amplitud"
    nombre = "Corrección de amplitud finita del péndulo"
    version = "1.0.0"

    observables = ("T_s",)
    requiere = ("L_m", "theta0_rad")

    enunciado = (
        "A amplitud finita, el período del péndulo simple es mayor que 2π√(L/g) "
        "y crece con θ0² y θ0⁴."
    )
    prediccion_diferenciadora = (
        "Para θ0 = 1.2 rad el modelo predice un período ≈ 9 % mayor que el "
        "baseline de pequeña amplitud; la separación crece cuadráticamente con θ0. "
        "El baseline predice separación nula, así que un barrido en amplitud "
        "distingue las dos propuestas sin ambigüedad."
    )

    dominio = Dominio(
        descripcion="Péndulo simple ideal, amplitudes moderadas, una sola masa",
        rango={"L_m": (0.40, 2.50), "theta0_rad": (0.0, 1.40)},
        limitaciones=(
            "Sin rozamiento, sin masa de hilo, sin elasticidad.",
            "Más allá de θ0 ≈ 1.4 rad la serie de cuarto orden deja de ser "
            "suficiente.",
        ),
    )

    observable_objetivo = "T_s"
    unidad_observable = "s"
    baseline = PenduloLineal()
    #: Verificación O01: rivales declarados además del baseline principal.
    baselines_alternativos = (PenduloSegundoOrden(), PenduloSerieCuartoOrden())

    dataset_id = "pendulo_v1"
    #: Verificación O04: contraste sobre datos generados aparte.
    dataset_validacion = "pendulo_holdout_v1"
    metrica = "rmse"
    umbral_mejora = 0.10
    umbral_sensibilidad = 1.0e-4
    incertidumbre_declarada = 1.0e-3
    semilla = 20261124

    PARAMETROS = (
        Parametro("g", G, "m/s^2", congelado=True,
                  descripcion="Gravedad; fijada, no ajustada"),
        Parametro("c2", 0.0, "rad^-2", congelado=False,
                  descripcion="Coeficiente de θ0², ajustado con calibración"),
        Parametro("c4", 0.0, "rad^-4", congelado=False,
                  descripcion="Coeficiente de θ0⁴, ajustado con calibración"),
    )

    def predecir(
        self,
        variables: Mapping[str, np.ndarray],
        parametros: Mapping[str, float],
    ) -> dict[str, np.ndarray]:
        L = np.asarray(variables["L_m"], dtype=float)
        th = np.asarray(variables["theta0_rad"], dtype=float)
        g = float(parametros["g"])
        c2 = float(parametros["c2"])
        c4 = float(parametros["c4"])
        t0 = 2.0 * np.pi * np.sqrt(L / g)
        return {"T_s": t0 * (1.0 + c2 * th ** 2 + c4 * th ** 4)}

    def ajustar(
        self,
        variables: Mapping[str, np.ndarray],
        observado: np.ndarray,
        parametros: Mapping[str, float],
    ) -> dict[str, float]:
        """Mínimos cuadrados lineales en (c2, c4) usando sólo la calibración."""
        L = np.asarray(variables["L_m"], dtype=float)
        th = np.asarray(variables["theta0_rad"], dtype=float)
        y = np.asarray(observado, dtype=float)
        g = float(parametros["g"])
        t0 = 2.0 * np.pi * np.sqrt(L / g)
        diseno = np.column_stack([t0 * th ** 2, t0 * th ** 4])
        coeficientes, *_ = np.linalg.lstsq(diseno, y - t0, rcond=None)
        actualizado = dict(parametros)
        actualizado["c2"] = float(coeficientes[0])
        actualizado["c4"] = float(coeficientes[1])
        return actualizado


def registrar() -> list[Modelo]:
    return [
        PenduloLineal(),
        PenduloSegundoOrden(),
        PenduloSerieCuartoOrden(),
        PenduloAmplitudFinita(),
    ]
