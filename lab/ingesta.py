"""Registro de un CSV real en el manifiesto del laboratorio.

Un dataset real no se convierte en dataset del laboratorio por copiarlo a
``datos/``: hay que congelarlo. Este módulo lee el CSV, comprueba el esquema,
calcula su SHA-256, fija una partición calibración/reservado y escribe la
entrada en ``manifiesto.json``.

Esquema mínimo (Paso 2 de la hoja de ruta):

    L_m, theta0_rad, T_s, u_T_s, u_L_m, u_theta0_rad

Las columnas ``u_*`` son las incertidumbres experimentales por fila. Si faltan,
el dataset se acepta pero T10 lo dirá: no se inventan incertidumbres.

La partición se decide **al ingerir**, con semilla registrada, y queda
congelada. El laboratorio no la sortea en cada corrida.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .datos import ARCHIVO_MANIFIESTO, ErrorDeDatos, sha256_de_archivo

#: Columnas sin las cuales el CSV no es un dataset de péndulo.
COLUMNAS_OBLIGATORIAS: tuple[str, ...] = ("L_m", "theta0_rad", "T_s")

#: Columnas de incertidumbre que el laboratorio sabe usar hoy.
COLUMNAS_INCERTIDUMBRE: tuple[str, ...] = ("u_T_s", "u_L_m", "u_theta0_rad")


class ErrorDeIngesta(ErrorDeDatos):
    """El CSV no cumple el esquema o el manifiesto no se puede actualizar."""


@dataclass
class Inspeccion:
    columnas: tuple[str, ...]
    filas: int
    faltantes: tuple[str, ...]
    incertidumbres: tuple[str, ...]
    avisos: list[str] = field(default_factory=list)

    @property
    def valido(self) -> bool:
        return not self.faltantes

    def como_dict(self) -> dict[str, Any]:
        return {
            "columnas": list(self.columnas),
            "filas": self.filas,
            "faltantes": list(self.faltantes),
            "incertidumbres": list(self.incertidumbres),
            "avisos": list(self.avisos),
            "valido": self.valido,
        }


def inspeccionar(ruta: str | Path) -> Inspeccion:
    """Lee la cabecera y cuenta filas sin cargar todo el archivo."""
    camino = Path(ruta)
    if not camino.is_file():
        raise ErrorDeIngesta(f"No existe el CSV: {camino}")
    with open(camino, "r", newline="", encoding="utf-8-sig") as f:
        lector = csv.DictReader(f)
        columnas = tuple(lector.fieldnames or ())
        filas = sum(1 for _ in lector)
    faltantes = tuple(c for c in COLUMNAS_OBLIGATORIAS if c not in columnas)
    incertidumbres = tuple(c for c in COLUMNAS_INCERTIDUMBRE if c in columnas)
    avisos: list[str] = []
    if faltantes:
        avisos.append(f"Faltan columnas obligatorias: {list(faltantes)}")
    if "u_T_s" not in columnas:
        avisos.append(
            "No hay columna 'u_T_s': T10 no podrá usar la incertidumbre "
            "experimental por fila y dependerá del presupuesto declarado."
        )
    if filas < 20:
        avisos.append(f"Sólo {filas} filas: revisa si hay datos suficientes.")
    return Inspeccion(columnas, filas, faltantes, incertidumbres, avisos)


def construir_entrada(
    ruta_csv: str | Path,
    *,
    id_: str,
    raiz_datos: str | Path,
    fraccion_calibracion: float = 0.6,
    semilla: int = 2026,
    procedencia: str = "",
    descripcion: str = "",
    filtros: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Construye (sin escribir) la entrada de manifiesto de un CSV real."""
    camino = Path(ruta_csv)
    info = inspeccionar(camino)
    if not info.valido:
        raise ErrorDeIngesta(
            f"{camino.name}: no es un dataset de péndulo válible. {info.avisos}"
        )
    if not 0.1 <= float(fraccion_calibracion) <= 0.9:
        raise ValueError("fraccion_calibracion debe estar entre 0.1 y 0.9")

    import numpy as np

    n = info.filas
    rng = np.random.default_rng(int(semilla))
    orden = rng.permutation(n)
    corte = int(round(n * float(fraccion_calibracion)))
    calibracion = sorted(int(i) for i in orden[:corte])
    reservado = sorted(int(i) for i in orden[corte:])
    if not calibracion or not reservado:
        raise ErrorDeIngesta("La partición resultante está vacía; ajusta la fracción.")

    incertidumbres = {
        observable: columna
        for observable, columna in (("T_s", "u_T_s"), ("L_m", "u_L_m"),
                                     ("theta0_rad", "u_theta0_rad"))
        if columna in info.columnas
    }

    destino = Path(raiz_datos) / camino.name
    ruido = _ruido_de_columna(camino, "u_T_s") if "u_T_s" in info.columnas else {}

    entrada: dict[str, Any] = {
        "id": id_,
        "ruta": camino.name,
        "sha256": sha256_de_archivo(camino),
        "descripcion": descripcion or f"Dataset real importado desde {camino.name}",
        "notas": "Importado con `lab ingestar`; la partición se fijó al ingerir.",
        "origen": "medido",
        "generado_por": "lab ingestar",
        "procedencia": procedencia or "no declarada",
        "variables": ["L_m", "theta0_rad"],
        "observables": ["T_s"],
        "unidades": {"L_m": "m", "theta0_rad": "rad", "T_s": "s"},
        "filas": n,
        "ruido": ruido,
        "incertidumbres": incertidumbres,
        "calibracion": calibracion,
        "reservado": reservado,
        "particion": {
            "fraccion_calibracion": float(fraccion_calibracion),
            "semilla": int(semilla),
        },
    }
    if filtros:
        entrada["filtros"] = dict(filtros)
    return entrada


def _ruido_de_columna(camino: Path, columna: str) -> dict[str, float]:
    """Ruido típico del observable, estimado con la mediana de u_T."""
    import numpy as np

    valores: list[float] = []
    with open(camino, "r", newline="", encoding="utf-8-sig") as f:
        for fila in csv.DictReader(f):
            try:
                valores.append(float(fila[columna]))
            except (TypeError, ValueError):
                continue
    if not valores:
        return {}
    return {"T_s": float(np.median(valores))}


def registrar(
    ruta_csv: str | Path,
    raiz_datos: str | Path,
    *,
    id_: str,
    fraccion_calibracion: float = 0.6,
    semilla: int = 2026,
    procedencia: str = "",
    descripcion: str = "",
    copiar: bool = True,
    reemplazar: bool = False,
) -> dict[str, Any]:
    """Copia el CSV a ``datos/`` y añade su entrada al manifiesto."""
    raiz = Path(raiz_datos)
    raiz.mkdir(parents=True, exist_ok=True)
    camino = Path(ruta_csv)
    if copiar:
        destino = raiz / camino.name
        if destino.exists() and not reemplazar:
            raise ErrorDeIngesta(
                f"Ya existe {destino}. Usa otro nombre o --reemplazar."
            )
        if destino.resolve() != camino.resolve():
            destino.write_bytes(camino.read_bytes())

    entrada = construir_entrada(
        raiz / camino.name,
        id_=id_,
        raiz_datos=raiz,
        fraccion_calibracion=fraccion_calibracion,
        semilla=semilla,
        procedencia=procedencia,
        descripcion=descripcion,
    )

    archivo = raiz / ARCHIVO_MANIFIESTO
    if archivo.is_file():
        contenido = json.loads(archivo.read_text(encoding="utf-8"))
    else:
        contenido = {"version": 1, "datasets": []}
    datasets = [d for d in contenido.get("datasets", []) if d.get("id") != id_]
    if len(datasets) != len(contenido.get("datasets", [])) and not reemplazar:
        raise ErrorDeIngesta(
            f"El id '{id_}' ya está en el manifiesto. Usa --reemplazar."
        )
    datasets.append(entrada)
    contenido["datasets"] = datasets
    archivo.write_text(
        json.dumps(contenido, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return entrada


def huella(entrada: Mapping[str, Any]) -> str:
    """SHA-256 de la entrada canónica del manifiesto (sin la ruta)."""
    relevante = {k: v for k, v in entrada.items() if k != "ruta"}
    texto = json.dumps(relevante, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def columnas_de_incertidumbre(columnas: Sequence[str]) -> dict[str, str]:
    """Mapea observable -> columna de incertidumbre disponible."""
    mapa: dict[str, str] = {}
    for columna in columnas:
        if columna.startswith("u_") and len(columna) > 2:
            mapa[columna[2:]] = columna
    return mapa
