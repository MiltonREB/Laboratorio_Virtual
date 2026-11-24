"""Adaptadores para reutilizar código externo como modelo del laboratorio.

Sirven para lo que ya existe: un script de una versión anterior, una función
de otro paquete, un binario que calcula un observable. El adaptador convierte
cualquiera de esos en un :class:`~lab.contrato.Modelo`, que es lo único que el
laboratorio sabe usar como baseline o como motor de una hipótesis.

Dos formas
----------
1. **En proceso** (:class:`ModeloDesdeFuncion`): envuelve un ``callable`` que
   recibe ``(variables, parametros)`` y devuelve los observables. Es el modo
   recomendado cuando el código es importable.
2. **En subproceso** (:class:`ModeloSubproceso`): habla JSON por tuberías con
   un programa externo. Sirve para código con otro intérprete, otra versión de
   Python o que no se puede importar sin efectos secundarios.

Protocolo del subproceso
------------------------
Entrada (stdin), un único objeto JSON::

    {"variables": {"L_m": [1.0, 2.0]},
     "parametros": {"g": 9.80665},
     "observables": ["T_s"]}

Salida (stdout), un único objeto JSON::

    {"T_s": [2.006, 2.837]}

Si el proceso sale con código distinto de cero, tarda más de lo permitido o
devuelve algo que no es JSON, el adaptador lanza una excepción con el motivo.
El laboratorio la convierte en un error de evaluación: un modelo que falla no
puede parecer un modelo que predice mal.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from .contrato import Modelo, Parametro

#: Firma de una función adaptable.
Funcion = Callable[[Mapping[str, np.ndarray], Mapping[str, float]],
                   "Mapping[str, Any] | Sequence[Any] | np.ndarray"]


# --------------------------------------------------------------------------
# Normalización de salidas
# --------------------------------------------------------------------------


def normalizar_salida(
    salida: Any,
    observables: Sequence[str],
    filas: int,
    permitir_escalar: bool = True,
) -> dict[str, np.ndarray]:
    """Convierte lo que devolvió el código externo en ``{observable: arreglo}``.

    Acepta un diccionario por nombre, una secuencia en el orden declarado o un
    arreglo único. Un escalar se difunde sólo si ``permitir_escalar``.
    """
    resultado: dict[str, np.ndarray] = {}

    if isinstance(salida, Mapping):
        for nombre in observables:
            if nombre not in salida:
                raise ValueError(f"La salida no contiene el observable '{nombre}'")
            resultado[nombre] = _como_arreglo(salida[nombre], filas, permitir_escalar)
        return resultado

    if isinstance(salida, np.ndarray) and salida.ndim == 1 and len(observables) == 1:
        return {observables[0]: _como_arreglo(salida, filas, permitir_escalar)}

    if isinstance(salida, (list, tuple)):
        if len(salida) == len(observables) and not (
            len(observables) == 1 and np.ndim(salida[0]) == 0 and len(salida) == filas
        ):
            return {
                nombre: _como_arreglo(valor, filas, permitir_escalar)
                for nombre, valor in zip(observables, salida)
            }
        if len(observables) == 1:
            return {observables[0]: _como_arreglo(salida, filas, permitir_escalar)}

    raise ValueError(
        f"Salida no reconocible de tipo {type(salida).__name__}; se esperaba un "
        f"diccionario con {list(observables)} o una secuencia equivalente"
    )


def _como_arreglo(valor: Any, filas: int, permitir_escalar: bool) -> np.ndarray:
    arreglo = np.asarray(valor, dtype=float)
    if arreglo.ndim == 0:
        if not permitir_escalar:
            raise ValueError("Se recibió un escalar y no se permite difundirlo")
        arreglo = np.full(filas, float(arreglo))
    if arreglo.shape != (filas,):
        raise ValueError(f"Forma {arreglo.shape} incompatible con ({filas},)")
    if not np.all(np.isfinite(arreglo)):
        raise ValueError("La salida contiene valores no finitos")
    return arreglo


def _validar_basico(id_: str, observables: Sequence[str],
                    requiere: Sequence[str]) -> None:
    if not str(id_).strip():
        raise ValueError("El modelo adaptado necesita un 'id'")
    if not observables:
        raise ValueError(f"'{id_}': declara al menos un observable")
    if not requiere:
        raise ValueError(f"'{id_}': declara al menos una variable de entrada")


# --------------------------------------------------------------------------
# Adaptador en proceso
# --------------------------------------------------------------------------


class ModeloDesdeFuncion(Modelo):
    """Modelo que delega en una función de Python ya existente."""

    def __init__(
        self,
        *,
        id: str,
        nombre: str,
        funcion: Funcion,
        observables: Sequence[str],
        requiere: Sequence[str],
        version: str = "0.1.0",
        supuestos: str = "",
        parametros: Sequence[Parametro] = (),
        permitir_escalar: bool = True,
    ) -> None:
        if not callable(funcion):
            raise TypeError("'funcion' debe ser invocable")
        self.id = str(id)
        self.nombre = str(nombre)
        self.version = str(version)
        self.observables = tuple(str(o) for o in observables)
        self.requiere = tuple(str(r) for r in requiere)
        self.supuestos = str(supuestos)
        self._funcion = funcion
        self._parametros = tuple(parametros)
        self._permitir_escalar = bool(permitir_escalar)
        _validar_basico(self.id, self.observables, self.requiere)

    def parametros(self) -> tuple[Parametro, ...]:
        return tuple(self._parametros)

    def predecir(
        self,
        variables: Mapping[str, np.ndarray],
        parametros: Mapping[str, float],
    ) -> dict[str, np.ndarray]:
        faltantes = [v for v in self.requiere if v not in variables]
        if faltantes:
            raise KeyError(f"'{self.id}': faltan variables {faltantes}")
        filas = _filas(variables, self.requiere)
        salida = self._funcion(dict(variables), dict(parametros))
        return normalizar_salida(salida, self.observables, filas,
                                 self._permitir_escalar)


# --------------------------------------------------------------------------
# Adaptador en subproceso
# --------------------------------------------------------------------------


class ModeloSubproceso(Modelo):
    """Modelo que delega en un programa externo mediante JSON por tuberías."""

    def __init__(
        self,
        *,
        id: str,
        nombre: str,
        comando: Sequence[str],
        observables: Sequence[str],
        requiere: Sequence[str],
        version: str = "0.1.0",
        supuestos: str = "",
        parametros: Sequence[Parametro] = (),
        tiempo_limite: float = 60.0,
        directorio: str | None = None,
    ) -> None:
        if not comando:
            raise ValueError("'comando' no puede estar vacío")
        self.id = str(id)
        self.nombre = str(nombre)
        self.version = str(version)
        self.observables = tuple(str(o) for o in observables)
        self.requiere = tuple(str(r) for r in requiere)
        self.supuestos = str(supuestos)
        self._comando = [str(c) for c in comando]
        self._parametros = tuple(parametros)
        self._tiempo_limite = float(tiempo_limite)
        self._directorio = directorio
        _validar_basico(self.id, self.observables, self.requiere)

    def parametros(self) -> tuple[Parametro, ...]:
        return tuple(self._parametros)

    def predecir(
        self,
        variables: Mapping[str, np.ndarray],
        parametros: Mapping[str, float],
    ) -> dict[str, np.ndarray]:
        faltantes = [v for v in self.requiere if v not in variables]
        if faltantes:
            raise KeyError(f"'{self.id}': faltan variables {faltantes}")
        filas = _filas(variables, self.requiere)
        carga = {
            "variables": {
                nombre: np.asarray(variables[nombre], dtype=float).tolist()
                for nombre in self.requiere
            },
            "parametros": {k: float(v) for k, v in parametros.items()},
            "observables": list(self.observables),
        }
        try:
            proceso = subprocess.run(
                self._comando,
                input=json.dumps(carga),
                capture_output=True,
                text=True,
                timeout=self._tiempo_limite,
                cwd=self._directorio,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"'{self.id}': el subproceso excedió {self._tiempo_limite:.0f} s"
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"'{self.id}': no se pudo ejecutar {self._comando}: {exc}"
            ) from exc

        if proceso.returncode != 0:
            raise RuntimeError(
                f"'{self.id}': el subproceso terminó con código "
                f"{proceso.returncode}: {proceso.stderr.strip()[:400]}"
            )
        try:
            salida = json.loads(proceso.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"'{self.id}': la salida no es JSON válido: "
                f"{proceso.stdout.strip()[:200]}"
            ) from exc
        return normalizar_salida(salida, self.observables, filas)


def _filas(variables: Mapping[str, np.ndarray], requeridas: Sequence[str]) -> int:
    longitudes = {
        len(np.atleast_1d(np.asarray(variables[nombre], dtype=float)))
        for nombre in requeridas
        if nombre in variables
    }
    if not longitudes:
        raise KeyError("No hay variables utilizables para determinar el número de filas")
    if len(longitudes) > 1:
        raise ValueError(f"Las variables tienen longitudes distintas: {sorted(longitudes)}")
    return longitudes.pop()


def modelo_desde_funcion(funcion: Funcion, **kwargs: Any) -> ModeloDesdeFuncion:
    """Atajo para :class:`ModeloDesdeFuncion`."""
    return ModeloDesdeFuncion(funcion=funcion, **kwargs)


def modelo_desde_subproceso(comando: Sequence[str], **kwargs: Any) -> ModeloSubproceso:
    """Atajo para :class:`ModeloSubproceso`."""
    return ModeloSubproceso(comando=comando, **kwargs)
