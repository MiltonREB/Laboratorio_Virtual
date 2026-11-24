"""Utilidades compartidas por las pruebas del laboratorio.

No es un módulo de pruebas (el descubridor no lo recoge): sólo construye
objetos de apoyo.
"""

from __future__ import annotations

import atexit
import shutil
import uuid
from pathlib import Path
from typing import Mapping

import numpy as np

from lab.contrato import Dominio, Hipotesis, Modelo, Parametro
from lab.datos import ConjuntoDatos
from lab.protocolo import ContextoEvaluacion

#: Raíz del laboratorio (``laboratorio/``).
RAIZ_LAB = Path(__file__).resolve().parent.parent
_BASE_TEMPORAL = RAIZ_LAB / ".tmp_pruebas"


def espacio_temporal(prefijo: str = "corrida") -> Path:
    """Carpeta de trabajo desechable dentro del proyecto.

    Se usa el espacio del propio laboratorio, no el directorio temporal del
    sistema, para que el borrado no dependa de permisos externos. La carpeta
    se crea con permisos heredados (no con ``mkdtemp``, que aplica 0700 y en
    Windows puede quedar fuera del alcance del proceso confinado).
    """
    _BASE_TEMPORAL.mkdir(parents=True, exist_ok=True)
    destino = _BASE_TEMPORAL / f"{prefijo}_{uuid.uuid4().hex[:10]}"
    destino.mkdir()
    return destino


@atexit.register
def _limpiar_temporales() -> None:  # pragma: no cover - limpieza de salida
    shutil.rmtree(_BASE_TEMPORAL, ignore_errors=True)


class ModeloConstante(Modelo):
    """Modelo trivial: predice la constante ``c``."""

    id = "modelo_constante"
    nombre = "Modelo constante"
    version = "1.0.0"
    observables = ("y",)
    requiere = ("x",)
    supuestos = "Predice una constante"

    PARAMETROS = (Parametro("c", 0.0, "u", congelado=True),)

    def predecir(self, variables, parametros):
        n = len(np.asarray(variables["x"], dtype=float))
        return {"y": np.full(n, float(parametros["c"]))}


class HipotesisDePrueba(Hipotesis):
    """Hipótesis completa y válida, para pruebas unitarias."""

    id = "hipotesis_de_prueba"
    nombre = "Hipótesis de prueba"
    version = "1.0.0"
    observables = ("y",)
    requiere = ("x",)

    enunciado = "La señal crece con x."
    prediccion_diferenciadora = "Predice una pendiente; el baseline no."
    dominio = Dominio(
        descripcion="Prueba unitaria",
        rango={"x": (0.0, 100.0)},
        limitaciones=(),
    )
    observable_objetivo = "y"
    unidad_observable = "u"
    baseline = ModeloConstante()
    dataset_id = "dataset_de_prueba"
    metrica = "rmse"
    umbral_mejora = 0.10
    umbral_sensibilidad = 0.01
    incertidumbre_declarada = 0.5
    semilla = 7

    PARAMETROS = (
        Parametro("a", 1.0, "u", congelado=True),
        Parametro("b", 1.0, "u", congelado=False),
    )

    def predecir(self, variables, parametros):
        x = np.asarray(variables["x"], dtype=float)
        return {"y": float(parametros["a"]) * x + float(parametros["b"])}

    def ajustar(self, variables, observado, parametros):
        actualizado = dict(parametros)
        actualizado["b"] = float(np.mean(np.asarray(observado, dtype=float)))
        return actualizado


def conjunto_de_prueba(filas: int = 20) -> ConjuntoDatos:
    """Conjunto de datos sintético en memoria, con particiones declaradas."""
    x = np.linspace(1.0, float(filas), filas)
    y = 2.0 * x + 1.0
    calibracion = tuple(range(0, int(filas * 0.6)))
    reservado = tuple(range(int(filas * 0.6), filas))
    return ConjuntoDatos(
        id="dataset_de_prueba",
        ruta=None,  # type: ignore[arg-type]
        sha256_declarado="0" * 64,
        sha256_actual="0" * 64,
        descripcion="Sintético en memoria",
        origen="sintetico",
        generado_por="pruebas/ayudas.py",
        variables=("x",),
        observables=("y",),
        unidades={"x": "u", "y": "u"},
        columnas={"x": x, "y": y},
        calibracion=calibracion,
        reservado=reservado,
        ruido={"y": 0.1},
    )


def contexto(
    *,
    hipotesis: Hipotesis | None = None,
    observado: np.ndarray | None = None,
    pred_hip: np.ndarray | None = None,
    pred_base: np.ndarray | None = None,
    **cambios,
) -> ContextoEvaluacion:
    """Contexto de evaluación con valores por defecto razonables."""
    h = hipotesis or HipotesisDePrueba()
    conjunto = conjunto_de_prueba()
    obs = np.asarray(observado if observado is not None else [10.0, 11.0, 12.0, 13.0])
    ph = np.asarray(pred_hip if pred_hip is not None else [10.1, 11.1, 12.1, 13.1])
    pb = np.asarray(pred_base if pred_base is not None else [9.5, 10.5, 11.5, 12.5])
    n = obs.size
    variables = {"x": np.arange(n, dtype=float)}

    base = dict(
        hipotesis=h,
        dataset=conjunto,
        baseline=h.baseline,
        parametros_declarados={"a": 1.0, "b": 1.0},
        parametros_ajustados={"a": 1.0, "b": 2.0},
        ajuste_usado=True,
        variables_calibracion=variables,
        variables_reservado=variables,
        observado_calibracion=obs,
        observado_reservado=obs,
        pred_hip_calibracion=ph,
        pred_base_calibracion=pb,
        pred_hip_reservado=ph,
        pred_base_reservado=pb,
        errores_calibracion={"hipotesis": 0.1, "baseline": 0.5},
        errores_reservado={"hipotesis": 0.1, "baseline": 0.5},
        estabilidad={
            "ensayos": [
                {"particion": 0, "semilla": 1, "mejora": 0.10, "alcanza_umbral": True},
                {"particion": 1, "semilla": 2, "mejora": 0.20, "alcanza_umbral": True},
            ]
        },
        control_nulo={
            "mejora": -0.01, "ic_inferior": -0.05, "ic_superior": 0.02,
        },
        reproducibilidad={
            "prediccion_identica": True,
            "bootstrap_identico": True,
            "sha_prediccion_1": "a" * 64,
            "sha_prediccion_2": "a" * 64,
            "sha_bootstrap_1": "b" * 64,
            "sha_bootstrap_2": "b" * 64,
        },
    )
    base.update(cambios)
    return ContextoEvaluacion(**base)


def sustituir(objeto, **cambios):
    """Copia superficial de un objeto tipo instancia con atributos cambiados."""
    nuevo = objeto.__class__.__new__(objeto.__class__)
    nuevo.__dict__.update(objeto.__dict__)
    for clave, valor in cambios.items():
        setattr(nuevo, clave, valor)
    return nuevo


def hipotesis_con(**cambios) -> Hipotesis:
    """Instancia de la hipótesis de prueba con atributos sobrescritos."""
    h = HipotesisDePrueba()
    for clave, valor in cambios.items():
        setattr(h, clave, valor)
    return h


def mapa(resultados) -> Mapping[str, str]:
    return {r.codigo: r.estado for r in resultados}
