"""Laboratorio virtual de hipótesis.

Un marco para evaluar cualquier hipótesis cuantitativa con un protocolo
fijo: preregistro, calibración separada, validación sobre datos reservados,
comparación contra un baseline convencional, estabilidad de diseño,
reproducibilidad y control nulo.

Punto de entrada de la API::

    from lab import cargar_registro, evaluar_hipotesis

    registro = cargar_registro()
    hipotesis = registro.hipotesis("mi_hipotesis")
    resultado = evaluar_hipotesis(hipotesis, registro)
"""

from .contrato import (
    ESTADOS,
    METRICAS,
    Dominio,
    Hipotesis,
    Modelo,
    Parametro,
    ResultadoPrueba,
)
from .datos import ConjuntoDatos, Manifiesto, cargar_manifiesto
from .evaluador import ResultadoEvaluacion, evaluar_hipotesis
from .registro import Registro, cargar_registro

__all__ = [
    "ESTADOS",
    "METRICAS",
    "ConjuntoDatos",
    "Dominio",
    "Hipotesis",
    "Manifiesto",
    "Modelo",
    "Parametro",
    "Registro",
    "ResultadoEvaluacion",
    "ResultadoPrueba",
    "cargar_manifiesto",
    "cargar_registro",
    "evaluar_hipotesis",
]

__version__ = "1.0.0"
