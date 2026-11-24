"""Contrato de modelos, hipótesis y resultados del laboratorio.

El laboratorio no sabe física: sólo sabe qué exige un protocolo. Toda
hipótesis nueva se declara heredando de :class:`Hipotesis` y entregando
metadatos verificables. Si falta un metadato, la prueba T01 lo reporta; el
laboratorio nunca rellena huecos por su cuenta.

Reglas del contrato
-------------------
1. ``predecir`` es una función pura: mismas variables y parámetros deben
   producir exactamente los mismos números.
2. Todo parámetro es explícito, con unidad y con estado ``congelado``.
   Un parámetro no congelado sólo puede ajustarse con la muestra de
   calibración.
3. La hipótesis declara su baseline, su métrica, el umbral de mejora y el
   umbral de sensibilidad **antes** de ver los datos reservados.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Sequence

import numpy as np

#: Estados posibles de una prueba del protocolo (v1.1.0).
#:
#: Se reducen a cuatro a propósito. ``APROBADO`` incluye el caso vacuo (la
#: prueba no tiene sujeto, p. ej. T05 sin parámetros libres): una exigencia
#: sobre el conjunto vacío se cumple, y el informe lo marca como «vacuo».
#: No existe un estado «no presentada»: eso es ``PENDIENTE`` con la marca
#: :attr:`ResultadoPrueba.es_ausencia`.
ESTADOS: tuple[str, ...] = ("APROBADO", "PENDIENTE", "SENSIBLE", "FALLIDO")

#: Métricas admitidas por el protocolo (ver ``lab.metricas``).
METRICAS: tuple[str, ...] = ("rmse", "mae", "chi2_reducido")

#: Estados que cuentan como "no bloqueante" al agregar el veredicto.
ESTADOS_ACEPTABLES: frozenset[str] = frozenset({"APROBADO"})


# --------------------------------------------------------------------------
# Piezas declarativas
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Parametro:
    """Parámetro declarado de un modelo.

    ``congelado=True`` significa fijado a priori (no se ajusta con datos).
    ``congelado=False`` significa parámetro libre: sólo podrá ajustarse con
    la partición de calibración y su valor ajustado quedará registrado.
    """

    nombre: str
    valor: float
    unidad: str = ""
    congelado: bool = True
    descripcion: str = ""

    def __post_init__(self) -> None:
        if not self.nombre or not isinstance(self.nombre, str):
            raise ValueError("Todo parámetro necesita un nombre no vacío")
        valor = float(self.valor)
        if not np.isfinite(valor):
            raise ValueError(f"Parámetro '{self.nombre}' no es finito: {self.valor!r}")
        object.__setattr__(self, "valor", valor)

    def como_dict(self) -> dict[str, object]:
        return {
            "nombre": self.nombre,
            "valor": self.valor,
            "unidad": self.unidad,
            "congelado": self.congelado,
            "descripcion": self.descripcion,
        }


@dataclass(frozen=True)
class Dominio:
    """Dominio de validez declarado.

    ``rango`` mapea nombre de variable -> (mínimo, máximo) en unidades del
    dataset. Una evaluación fuera de rango es extrapolación y la prueba T12
    la rechaza; el laboratorio no la recorta en silencio.
    """

    descripcion: str
    rango: Mapping[str, tuple[float, float]]
    limitaciones: tuple[str, ...] = ()

    def contiene(self, variables: Mapping[str, np.ndarray]) -> dict[str, float]:
        """Fracción de filas fuera de rango por variable (0.0 si está dentro)."""
        fuera: dict[str, float] = {}
        for nombre, (lo, hi) in self.rango.items():
            if nombre not in variables:
                fuera[nombre] = 1.0
                continue
            x = np.asarray(variables[nombre], dtype=float)
            if x.size == 0:
                fuera[nombre] = 0.0
                continue
            malas = np.count_nonzero((x < lo) | (x > hi))
            fuera[nombre] = float(malas) / float(x.size)
        return fuera


@dataclass(frozen=True)
class ResultadoPrueba:
    """Resultado de una prueba del protocolo.

    ``es_ausencia`` marca el caso en que no hay nada que contrastar (la
    hipótesis coincide con el baseline, o su predicción no es falsable). No es
    un quinto estado: es un matiz sobre ``PENDIENTE`` o ``FALLIDO`` que el
    veredicto usa para distinguir «no se presentó» de «falta evidencia».
    """

    codigo: str
    titulo: str
    estado: str
    detalle: str
    evidencia: Mapping[str, object] = field(default_factory=dict)
    es_ausencia: bool = False

    def __post_init__(self) -> None:
        if self.estado not in ESTADOS:
            raise ValueError(f"Estado desconocido: {self.estado!r}")

    def como_dict(self) -> dict[str, object]:
        return {
            "codigo": self.codigo,
            "titulo": self.titulo,
            "estado": self.estado,
            "detalle": self.detalle,
            "evidencia": dict(self.evidencia),
            "es_ausencia": self.es_ausencia,
        }


# --------------------------------------------------------------------------
# Modelos
# --------------------------------------------------------------------------


class Modelo(ABC):
    """Un modelo es una función declarada de variables a observables.

    Se usa igual para una hipótesis y para su baseline convencional: lo que
    distingue a una hipótesis es la capa de metadatos y umbrales, no la
    aritmética.
    """

    id: str = ""
    nombre: str = ""
    version: str = "0.1.0"
    #: Nombres de los observables que devuelve ``predecir``.
    observables: tuple[str, ...] = ()
    #: Nombres de las variables de entrada que necesita.
    requiere: tuple[str, ...] = ()
    #: Texto breve de qué asume el modelo.
    supuestos: str = ""

    PARAMETROS: tuple[Parametro, ...] = ()

    def parametros(self) -> tuple[Parametro, ...]:
        return tuple(self.PARAMETROS)

    def valores_iniciales(self) -> dict[str, float]:
        return {p.nombre: p.valor for p in self.parametros()}

    @abstractmethod
    def predecir(
        self,
        variables: Mapping[str, np.ndarray],
        parametros: Mapping[str, float],
    ) -> dict[str, np.ndarray]:
        """Devuelve un arreglo por cada observable declarado."""

    def __repr__(self) -> str:  # pragma: no cover - sólo diagnóstico
        return f"<{type(self).__name__} id={self.id!r} v{self.version}>"


class Hipotesis(Modelo):
    """Modelo con metadatos y umbrales exigidos por el protocolo."""

    #: Enunciado falsable en una frase.
    enunciado: str = ""
    #: Qué predice distinto del baseline, y dónde sería observable.
    prediccion_diferenciadora: str = ""
    #: :class:`Dominio` de validez.
    dominio: Dominio | None = None
    #: Observable que se compara contra el baseline.
    observable_objetivo: str = ""
    #: Unidad del observable objetivo.
    unidad_observable: str = ""
    #: Modelo de referencia convencional (instancia).
    baseline: Modelo | None = None
    #: ``id`` del dataset declarado con el que se evalúa.
    dataset_id: str = ""
    #: ``id`` de un dataset independiente reservado para el holdout externo
    #: (verificación opcional O04). Vacío = no declarado.
    dataset_validacion: str = ""
    #: Baselines adicionales contra los que contrastar (verificación O01).
    baselines_alternativos: tuple[Modelo, ...] = ()
    #: Métrica de la comparación (una de :data:`METRICAS`).
    metrica: str = "rmse"
    #: Mejora relativa mínima exigida frente al baseline (0.10 = 10 %).
    umbral_mejora: float | None = None
    #: Cuántas veces el error del baseline debe superar |ΔO| como mínimo para
    #: considerar que la predicción es distinguible (T03). Adimensional.
    factor_diferenciacion: float = 1.0
    #: Resolución instrumental absoluta, si existe (suelo opcional de T03).
    #: ``None`` = no declarada; T03 se guía sólo por el factor anterior.
    umbral_sensibilidad: float | None = None
    #: Presupuesto de incertidumbre declarado para el observable (misma unidad).
    incertidumbre_declarada: float = float("nan")
    #: Semilla para todo sorteo (bootstrap, remuestreos, controles nulos).
    semilla: int = 0

    def ajustar(
        self,
        variables: Mapping[str, np.ndarray],
        observado: np.ndarray,
        parametros: Mapping[str, float],
    ) -> dict[str, float]:
        """Ajusta parámetros libres usando SÓLO la muestra de calibración.

        Por defecto no hay ajuste: los parámetros declarados son los usados.
        """
        return dict(parametros)

    # -- verificación del contrato -------------------------------------

    def parametros_libres(self) -> tuple[Parametro, ...]:
        return tuple(p for p in self.parametros() if not p.congelado)

    def problemas_de_contrato(self) -> list[str]:
        """Lista de metadatos faltantes o inválidos (vacía si está completo)."""
        fallos: list[str] = []

        for attr in ("id", "nombre", "version", "enunciado",
                     "prediccion_diferenciadora", "observable_objetivo",
                     "unidad_observable", "dataset_id"):
            if not str(getattr(self, attr, "") or "").strip():
                fallos.append(f"Falta '{attr}'")

        if not self.observables:
            fallos.append("Falta 'observables'")
        elif self.observable_objetivo and self.observable_objetivo not in self.observables:
            fallos.append(
                f"observable_objetivo '{self.observable_objetivo}' no está en observables"
            )

        if self.dominio is None:
            fallos.append("Falta 'dominio'")
        else:
            if not self.dominio.descripcion.strip():
                fallos.append("dominio.descripcion vacío")
            if not dict(self.dominio.rango):
                fallos.append("dominio.rango vacío")

        if self.baseline is None:
            fallos.append("Falta 'baseline'")
        elif not isinstance(self.baseline, Modelo):
            fallos.append("baseline no es un Modelo")
        elif self.baseline.id == self.id:
            fallos.append("baseline no puede ser la propia hipótesis")

        if self.metrica not in METRICAS:
            fallos.append(
                f"métrica '{self.metrica}' no admitida (usa {', '.join(METRICAS)})"
            )

        if self.umbral_mejora is None:
            fallos.append("Falta 'umbral_mejora'")
        elif not (0.0 < float(self.umbral_mejora) < 1.0):
            fallos.append("umbral_mejora debe estar en (0, 1)")

        if not (float(self.factor_diferenciacion) > 0.0):
            fallos.append("factor_diferenciacion debe ser > 0")

        if self.umbral_sensibilidad is not None and float(self.umbral_sensibilidad) < 0.0:
            fallos.append("umbral_sensibilidad no puede ser negativo (usa None)")

        for p in self.parametros():
            if not str(p.unidad).strip():
                fallos.append(f"Parámetro '{p.nombre}' sin unidad")

        return fallos

    def firma_de_parametros(self) -> dict[str, object]:
        """Instantánea canónica de lo que un preregistro debe congelar."""
        return {
            "id": self.id,
            "version": self.version,
            "metrica": self.metrica,
            "umbral_mejora": self.umbral_mejora,
            "factor_diferenciacion": self.factor_diferenciacion,
            "umbral_sensibilidad": self.umbral_sensibilidad,
            "incertidumbre_declarada": (
                None if not np.isfinite(self.incertidumbre_declarada)
                else float(self.incertidumbre_declarada)
            ),
            "semilla": self.semilla,
            "observable_objetivo": self.observable_objetivo,
            "dataset_id": self.dataset_id,
            "dataset_validacion": self.dataset_validacion,
            "parametros": [
                {
                    "nombre": p.nombre,
                    "valor": p.valor,
                    "unidad": p.unidad,
                    "congelado": p.congelado,
                }
                for p in self.parametros()
            ],
        }


# --------------------------------------------------------------------------
# Utilidades de validación compartidas
# --------------------------------------------------------------------------


def verificar_salida(
    salida: Mapping[str, np.ndarray],
    observables: Sequence[str],
    filas: int,
) -> list[str]:
    """Comprueba que la salida de un modelo sea usable (lista de errores)."""
    errores: list[str] = []
    for nombre in observables:
        if nombre not in salida:
            errores.append(f"El modelo no devolvió el observable '{nombre}'")
            continue
        x = np.asarray(salida[nombre], dtype=float)
        if x.shape != (filas,):
            errores.append(
                f"'{nombre}' tiene forma {x.shape}, se esperaba ({filas},)"
            )
        elif not np.all(np.isfinite(x)):
            errores.append(f"'{nombre}' contiene valores no finitos")
    return errores


def describir_parametros(parametros: Iterable[Parametro]) -> str:
    partes = []
    for p in parametros:
        marca = "fijo" if p.congelado else "libre"
        unidad = f" {p.unidad}" if p.unidad else ""
        partes.append(f"{p.nombre}={p.valor:g}{unidad} ({marca})")
    return ", ".join(partes) if partes else "sin parámetros"
