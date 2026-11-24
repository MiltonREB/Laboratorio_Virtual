"""Advertencias de viabilidad, calculadas **antes** de ejecutar la batería.

No cambian el veredicto: señalan diseños que probablemente no puedan sostener
ninguna conclusión, para ahorrar la corrida o para que el lector sepa de
antemano qué va a fallar y por qué.

Cada aviso es una comprobación con su propio criterio, no una opinión.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from .contrato import Hipotesis
from .datos import ConjuntoDatos

#: Filas de calibración mínimas por parámetro libre para considerarlo identificable.
FILAS_POR_PARAMETRO = 10
#: Filas reservadas mínimas para que un bootstrap percentil sea informativo.
RESERVADO_MINIMO = 30


@dataclass(frozen=True)
class Aviso:
    codigo: str
    severidad: str  # alta | media | baja
    mensaje: str
    detalle: str = ""

    def como_dict(self) -> dict[str, str]:
        return {
            "codigo": self.codigo,
            "severidad": self.severidad,
            "mensaje": self.mensaje,
            "detalle": self.detalle,
        }


def evaluar(
    hipotesis: Hipotesis,
    dataset: ConjuntoDatos,
    verificacion: Any | None = None,
) -> list[Aviso]:
    """Lista de avisos aplicables; vacía si no hay nada que objetar."""
    avisos: list[Aviso] = []
    avisos.extend(_identificabilidad(hipotesis, dataset))
    avisos.extend(_reservado(hipotesis, dataset))
    avisos.extend(_umbral_en_el_ruido(hipotesis, dataset))
    avisos.extend(_dominio(hipotesis, dataset))
    avisos.extend(_incertidumbre(hipotesis))
    avisos.extend(_preregistro(verificacion))
    return avisos


def _identificabilidad(h: Hipotesis, dataset: ConjuntoDatos) -> list[Aviso]:
    libres = h.parametros_libres()
    if not libres:
        return []
    filas = len(dataset.calibracion)
    necesarias = FILAS_POR_PARAMETRO * len(libres)
    if filas >= necesarias:
        return []
    return [Aviso(
        "V01", "alta" if filas < necesarias / 2 else "media",
        f"{len(libres)} parámetros libres sobre {filas} filas de calibración",
        f"Con {FILAS_POR_PARAMETRO} filas por parámetro harían falta {necesarias}. "
        "Por debajo de esa proporción el ajuste puede acomodar ruido y el "
        "reservado no basta para detectarlo.",
    )]


def _reservado(h: Hipotesis, dataset: ConjuntoDatos) -> list[Aviso]:
    filas = len(dataset.reservado)
    if filas >= RESERVADO_MINIMO:
        return []
    if filas < 3:
        return [Aviso(
            "V02", "alta",
            f"Sólo {filas} filas reservadas",
            "El bootstrap de la mejora necesita al menos 3 filas para remuestrear. "
            "T07 quedará sin evidencia.",
        )]
    return [Aviso(
        "V02", "media",
        f"{filas} filas reservadas, por debajo de {RESERVADO_MINIMO}",
        "El intervalo bootstrap será ancho y las verificaciones por bloques no "
        "podrán ejecutarse.",
    )]


def _umbral_en_el_ruido(h: Hipotesis, dataset: ConjuntoDatos) -> list[Aviso]:
    """Si lo exigido es menor que el ruido, la prueba no discrimina nada."""
    umbral = h.umbral_mejora
    if umbral is None or not dataset.observables:
        return []
    sigma = dataset.ruido.get(h.observable_objetivo)
    if sigma is None:
        return []
    # El error del baseline se desconoce antes de predecir; se usa el ruido como
    # cota inferior razonable de la escala del problema.
    exigido_absoluto = float(umbral) * float(sigma)
    if exigido_absoluto >= float(sigma) * 0.5:
        return []
    return [Aviso(
        "V03", "media",
        f"El umbral de mejora ({umbral:g}) exige {exigido_absoluto:.3g}, "
        f"menos que el ruido declarado ({float(sigma):.3g})",
        "Una mejora de esa magnitud cabe dentro del ruido: el criterio no "
        "distingue un modelo informativo de uno que no lo es.",
    )]


def _dominio(h: Hipotesis, dataset: ConjuntoDatos) -> list[Aviso]:
    if h.dominio is None:
        return [Aviso(
            "V04", "alta", "La hipótesis no declara dominio de validez",
            "T12 fallará y el resultado no podrá acotarse.",
        )]
    faltantes = [v for v in h.dominio.rango if v not in dataset.columnas]
    if faltantes:
        return [Aviso(
            "V04", "alta",
            f"El dominio declara variables que el dataset no tiene: {faltantes}",
            "T12 no podrá verificar la cobertura del dominio.",
        )]
    variables = dataset.variables_de(None, list(h.dominio.rango))
    fuera = h.dominio.contiene(variables)
    malas = {k: f for k, f in fuera.items() if f > 0.0}
    if not malas:
        return []
    detalle = ", ".join(f"{k}: {f:.0%}" for k, f in malas.items())
    return [Aviso(
        "V04", "alta",
        "Parte del dataset cae fuera del dominio declarado",
        f"{detalle}. T12 fallará: o se amplía el dominio con justificación, o se "
        "recorta el conjunto antes de evaluar.",
    )]


def _incertidumbre(h: Hipotesis) -> list[Aviso]:
    if np.isfinite(float(h.incertidumbre_declarada)) and float(h.incertidumbre_declarada) > 0:
        return []
    return [Aviso(
        "V05", "baja",
        "No se declara presupuesto de incertidumbre",
        "T10 quedará en PENDIENTE y el informe no podrá decir si el error "
        "observado cabe en lo esperado.",
    )]


def _preregistro(verificacion: Any | None) -> list[Aviso]:
    if verificacion is None:
        return []
    estado = getattr(verificacion, "estado_preregistro", None)
    if estado in (None, "VALIDO"):
        return []
    mensajes: Mapping[str, tuple[str, str]] = {
        "AUSENTE": ("alta", "No hay sello de preregistro: T04 quedará en PENDIENTE"),
        "RECIENTE": ("alta", "El sello es demasiado reciente para acreditar anterioridad"),
        "TARDIO": ("alta", "El sello se creó durante la evaluación"),
        "ALTERADO": ("alta", "La firma cambió después de sellar: T04 fallará"),
        "NO_PUBLICADO": ("media", "El sello no está publicado en un commit"),
    }
    severidad, mensaje = mensajes.get(str(estado), ("media", f"Preregistro: {estado}"))
    return [Aviso("V06", severidad, mensaje)]
