"""Conjuntos de datos, procedencia e integridad.

Un dataset del laboratorio es un CSV congelado más una entrada de manifiesto
que declara su SHA-256, sus columnas, sus unidades y la partición entre
muestra de calibración y muestra reservada. El laboratorio nunca divide los
datos por su cuenta: si la partición no está declarada y congelada, no hay
validación fuera de muestra.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np

#: Nombre del archivo de manifiesto dentro del directorio de datos.
ARCHIVO_MANIFIESTO = "manifiesto.json"

#: Orígenes admitidos en un manifiesto.
ORIGENES = ("sintetico", "medido", "publicado", "derivado")

#: Uso de un dataset que sirve de contraste externo y no se parte.
USO_VALIDACION_EXTERNA = "validacion_externa"


class ErrorDeDatos(RuntimeError):
    """El dataset no existe, no coincide con su hash o está mal declarado."""


def sha256_de_archivo(ruta: str | Path, bloque: int = 1 << 20) -> str:
    """SHA-256 en hexadecimal de los bytes actuales del archivo."""
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        while True:
            trozo = f.read(bloque)
            if not trozo:
                break
            h.update(trozo)
    return h.hexdigest()


def _leer_csv(ruta: Path) -> dict[str, np.ndarray]:
    with open(ruta, "r", newline="", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        if not lector.fieldnames:
            raise ErrorDeDatos(f"{ruta.name}: CSV sin encabezado")
        campos = list(lector.fieldnames)
        acumulado: dict[str, list[float]] = {c: [] for c in campos}
        for numero, fila in enumerate(lector, start=2):
            for columna in campos:
                bruto = fila.get(columna)
                try:
                    acumulado[columna].append(float(bruto))
                except (TypeError, ValueError) as exc:
                    raise ErrorDeDatos(
                        f"{ruta.name}: valor no numérico en línea {numero}, "
                        f"columna '{columna}': {bruto!r}"
                    ) from exc
    if not acumulado[campos[0]]:
        raise ErrorDeDatos(f"{ruta.name}: sin filas de datos")
    return {c: np.asarray(v, dtype=float) for c, v in acumulado.items()}


@dataclass(frozen=True)
class ConjuntoDatos:
    """Dataset cargado y verificado contra su manifiesto."""

    id: str
    ruta: Path
    sha256_declarado: str
    sha256_actual: str
    descripcion: str
    origen: str
    generado_por: str
    variables: tuple[str, ...]
    observables: tuple[str, ...]
    unidades: Mapping[str, str]
    columnas: Mapping[str, np.ndarray]
    calibracion: tuple[int, ...]
    reservado: tuple[int, ...]
    ruido: Mapping[str, float] = field(default_factory=dict)
    notas: str = ""
    uso: str = "ajuste"
    #: Incertidumbre experimental por fila, por observable (``u_T_s`` -> arreglo).
    incertidumbres: Mapping[str, np.ndarray] = field(default_factory=dict)
    #: Quién, cuándo y con qué instrumento se tomaron los datos.
    procedencia: str = ""

    @property
    def es_validacion_externa(self) -> bool:
        return self.uso == USO_VALIDACION_EXTERNA

    def incertidumbre_media(self, observable: str) -> float | None:
        """RMS de la incertidumbre por fila, o ``None`` si no se declaró."""
        valores = self.incertidumbres.get(observable)
        if valores is None:
            return None
        arreglo = np.asarray(valores, dtype=float)
        if arreglo.size == 0 or not np.all(np.isfinite(arreglo)):
            return None
        return float(np.sqrt(np.mean(arreglo ** 2)))

    def escala_efectiva(self, observable: str, declarada: float | None = None) -> float:
        """Presupuesto de incertidumbre combinado: declarado ⊕ experimental.

        Se combinan en cuadratura porque son fuentes independientes. Si no hay
        ninguna de las dos, se devuelve 0.0 y quien llame decide qué hacer.
        """
        partes: list[float] = []
        if declarada is not None and np.isfinite(float(declarada)) and float(declarada) > 0:
            partes.append(float(declarada))
        media = self.incertidumbre_media(observable)
        if media is not None and media > 0:
            partes.append(media)
        if not partes:
            return 0.0
        return float(np.sqrt(np.sum(np.square(partes))))

    # -- integridad ----------------------------------------------------

    @property
    def integridad(self) -> bool:
        return self.sha256_declarado == self.sha256_actual

    def exigir_integridad(self) -> None:
        if not self.integridad:
            raise ErrorDeDatos(
                f"{self.id}: el SHA-256 no coincide con el manifiesto "
                f"(declarado {self.sha256_declarado[:12]}…, "
                f"actual {self.sha256_actual[:12]}…). "
                "Si el cambio es intencional, actualiza el manifiesto y "
                "registra el motivo."
            )

    # -- acceso --------------------------------------------------------

    @property
    def filas(self) -> int:
        return int(len(self.columnas[self.variables[0]]))

    def matriz(self, columnas: Sequence[str], indices: Sequence[int] | None = None) -> dict[str, np.ndarray]:
        faltan = [c for c in columnas if c not in self.columnas]
        if faltan:
            raise ErrorDeDatos(f"{self.id}: faltan columnas {faltan}")
        if indices is None:
            return {c: np.asarray(self.columnas[c], dtype=float) for c in columnas}
        idx = np.asarray(list(indices), dtype=int)
        return {c: np.asarray(self.columnas[c], dtype=float)[idx] for c in columnas}

    def variables_de(self, indices: Sequence[int] | None = None, requeridas: Iterable[str] | None = None) -> dict[str, np.ndarray]:
        nombres = tuple(requeridas) if requeridas is not None else self.variables
        return self.matriz(nombres, indices)

    def observado(self, nombre: str, indices: Sequence[int] | None = None) -> np.ndarray:
        if nombre not in self.observables:
            raise ErrorDeDatos(
                f"{self.id}: '{nombre}' no es un observable declarado "
                f"({', '.join(self.observables)})"
            )
        return self.matriz([nombre], indices)[nombre]

    def sigma(self, observable: str) -> float:
        """Incertidumbre declarada del observable; 1.0 si no consta."""
        valor = float(self.ruido.get(observable, 1.0))
        return valor if valor > 0 else 1.0

    # -- particiones ---------------------------------------------------

    def con_particion(self, semilla: int, fraccion_reservado: float = 0.4) -> tuple[tuple[int, ...], tuple[int, ...]]:
        """Partición alternativa reproducible, para la prueba de estabilidad."""
        if not 0.0 < fraccion_reservado < 1.0:
            raise ValueError("fraccion_reservado debe estar en (0, 1)")
        rng = np.random.default_rng(semilla)
        orden = rng.permutation(self.filas)
        corte = int(round(self.filas * (1.0 - fraccion_reservado)))
        calibracion = tuple(int(i) for i in np.sort(orden[:corte]))
        reservado = tuple(int(i) for i in np.sort(orden[corte:]))
        return calibracion, reservado

    def resumen(self) -> dict[str, object]:
        return {
            "id": self.id,
            "ruta": str(self.ruta),
            "filas": self.filas,
            "variables": list(self.variables),
            "observables": list(self.observables),
            "unidades": dict(self.unidades),
            "calibracion": len(self.calibracion),
            "reservado": len(self.reservado),
            "ruido": dict(self.ruido),
            "incertidumbres": {
                k: self.incertidumbre_media(k) for k in self.incertidumbres
            },
            "procedencia": self.procedencia,
            "origen": self.origen,
            "generado_por": self.generado_por,
            "uso": self.uso,
            "sha256": self.sha256_declarado,
            "integridad": self.integridad,
            "descripcion": self.descripcion,
            "notas": self.notas,
        }


class Manifiesto:
    """Catálogo de datasets congelados de un directorio."""

    def __init__(self, raiz: str | Path, entradas: Sequence[Mapping[str, object]]):
        self.raiz = Path(raiz)
        self._entradas = {str(e["id"]): dict(e) for e in entradas}
        self._cache: dict[str, ConjuntoDatos] = {}

    # -- construcción --------------------------------------------------

    @classmethod
    def desde_directorio(cls, raiz: str | Path, archivo: str = ARCHIVO_MANIFIESTO) -> "Manifiesto":
        raiz = Path(raiz)
        ruta = raiz / archivo
        if not ruta.is_file():
            raise ErrorDeDatos(f"No existe el manifiesto {ruta}")
        with open(ruta, "r", encoding="utf-8") as f:
            contenido = json.load(f)
        entradas = contenido.get("datasets", [])
        if not isinstance(entradas, list) or not entradas:
            raise ErrorDeDatos(f"{ruta}: 'datasets' vacío o mal formado")
        return cls(raiz, entradas)

    # -- consulta ------------------------------------------------------

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(self._entradas)

    def entrada(self, id_: str) -> Mapping[str, object]:
        try:
            return self._entradas[id_]
        except KeyError as exc:
            raise ErrorDeDatos(
                f"Dataset '{id_}' no está en el manifiesto "
                f"(disponibles: {', '.join(self.ids)})"
            ) from exc

    def contiene(self, id_: str) -> bool:
        return id_ in self._entradas

    def cargar(self, id_: str) -> ConjuntoDatos:
        if id_ in self._cache:
            return self._cache[id_]
        e = self.entrada(id_)
        ruta = self.raiz / str(e.get("ruta", f"{id_}.csv"))
        if not ruta.is_file():
            raise ErrorDeDatos(f"Dataset '{id_}': no existe {ruta}")
        columnas = _leer_csv(ruta)
        variables = tuple(str(v) for v in e.get("variables", []))
        observables = tuple(str(v) for v in e.get("observables", []))
        if not variables or not observables:
            raise ErrorDeDatos(
                f"Dataset '{id_}': declara 'variables' y 'observables'"
            )
        faltan = [c for c in (*variables, *observables) if c not in columnas]
        if faltan:
            raise ErrorDeDatos(f"Dataset '{id_}': faltan columnas {faltan} en el CSV")

        filas = int(e.get("filas", len(columnas[variables[0]])))
        if filas != len(columnas[variables[0]]):
            raise ErrorDeDatos(
                f"Dataset '{id_}': el manifiesto declara {filas} filas y el CSV "
                f"tiene {len(columnas[variables[0]])}"
            )

        calibracion, reservado = _leer_particion(e, filas, id_)
        incertidumbres = _leer_incertidumbres(e, columnas, id_)
        conjunto = ConjuntoDatos(
            id=id_,
            ruta=ruta,
            sha256_declarado=str(e.get("sha256", "")).lower(),
            sha256_actual=sha256_de_archivo(ruta),
            descripcion=str(e.get("descripcion", "")),
            origen=str(e.get("origen", "sintetico")),
            generado_por=str(e.get("generado_por", "")),
            variables=variables,
            observables=observables,
            unidades={str(k): str(v) for k, v in dict(e.get("unidades", {})).items()},
            columnas=columnas,
            calibracion=calibracion,
            reservado=reservado,
            ruido={str(k): float(v) for k, v in dict(e.get("ruido", {})).items()},
            notas=str(e.get("notas", "")),
            uso=str(e.get("uso", "ajuste")),
            incertidumbres=incertidumbres,
            procedencia=str(e.get("procedencia", "")),
        )
        self._cache[id_] = conjunto
        return conjunto

    def verificar(self) -> dict[str, dict[str, object]]:
        """Comprueba hash y partición de todos los datasets del manifiesto."""
        informe: dict[str, dict[str, object]] = {}
        for id_ in self.ids:
            try:
                d = self.cargar(id_)
                informe[id_] = {
                    "ok": d.integridad,
                    "sha256_declarado": d.sha256_declarado,
                    "sha256_actual": d.sha256_actual,
                    "filas": d.filas,
                    "calibracion": len(d.calibracion),
                    "reservado": len(d.reservado),
                    "error": None,
                }
            except ErrorDeDatos as exc:
                informe[id_] = {
                    "ok": False,
                    "sha256_declarado": None,
                    "sha256_actual": None,
                    "filas": None,
                    "calibracion": None,
                    "reservado": None,
                    "error": str(exc),
                }
        return informe

    def resumen(self) -> list[dict[str, object]]:
        return [self.cargar(i).resumen() for i in self.ids]


def _leer_incertidumbres(
    entrada: Mapping[str, object],
    columnas: Mapping[str, np.ndarray],
    id_: str,
) -> dict[str, np.ndarray]:
    """Carga las columnas de incertidumbre declaradas (``u_T_s``, etc.)."""
    declaradas = dict(entrada.get("incertidumbres", {}) or {})
    salida: dict[str, np.ndarray] = {}
    for observable, columna in declaradas.items():
        nombre = str(columna)
        if nombre not in columnas:
            raise ErrorDeDatos(
                f"Dataset '{id_}': declara la incertidumbre '{nombre}' para "
                f"'{observable}' pero esa columna no existe en el CSV"
            )
        arreglo = np.asarray(columnas[nombre], dtype=float)
        if np.any(~np.isfinite(arreglo)) or np.any(arreglo < 0):
            raise ErrorDeDatos(
                f"Dataset '{id_}': la columna '{nombre}' tiene valores no "
                "finitos o negativos"
            )
        salida[str(observable)] = arreglo
    return salida


def _leer_particion(
    entrada: Mapping[str, object], filas: int, id_: str
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    # Un dataset de validación externa no se ajusta: no tiene partición.
    if str(entrada.get("uso", "")) == USO_VALIDACION_EXTERNA:
        sobrantes = [k for k in ("calibracion", "reservado") if k in entrada]
        if sobrantes:
            raise ErrorDeDatos(
                f"Dataset '{id_}': un dataset de validación externa no debe "
                f"declarar {sobrantes}; no participa en ningún ajuste."
            )
        return (), ()

    calibracion = entrada.get("calibracion")
    reservado = entrada.get("reservado")
    if calibracion is None or reservado is None:
        raise ErrorDeDatos(
            f"Dataset '{id_}': el manifiesto debe declarar 'calibracion' y "
            "'reservado'. El laboratorio no inventa particiones: sin datos "
            "reservados no hay validación fuera de muestra."
        )
    cal = tuple(int(i) for i in calibracion)
    res = tuple(int(i) for i in reservado)
    if not cal or not res:
        raise ErrorDeDatos(f"Dataset '{id_}': particiones vacías")
    todos = (*cal, *res)
    if len(set(todos)) != len(todos):
        raise ErrorDeDatos(f"Dataset '{id_}': calibración y reservado se solapan")
    fuera = [i for i in todos if i < 0 or i >= filas]
    if fuera:
        raise ErrorDeDatos(f"Dataset '{id_}': índices fuera de rango {fuera[:5]}")
    cubiertas = set(todos)
    omitidas = [i for i in range(filas) if i not in cubiertas]
    if omitidas:
        raise ErrorDeDatos(
            f"Dataset '{id_}': {len(omitidas)} filas no declaradas en ninguna "
            f"partición (p. ej. {omitidas[:5]})"
        )
    return cal, res


def cargar_manifiesto(directorio: str | Path) -> Manifiesto:
    """Carga el manifiesto del directorio de datos indicado."""
    return Manifiesto.desde_directorio(directorio)
