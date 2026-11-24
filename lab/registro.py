"""Descubrimiento y registro de hipótesis.

Las hipótesis viven como módulos dentro del paquete ``hipotesis/``. Un
módulo puede exportar ``registrar()`` (lo explícito, recomendado) o, si no,
el laboratorio recoge las clases de :class:`~lab.contrato.Hipotesis` y
:class:`~lab.contrato.Modelo` definidas en ese módulo.

Un módulo roto no detiene el laboratorio: se registra el error y el resto
sigue disponible. El error se muestra en ``lab hipotesis listar`` y en el
panel, porque una hipótesis que no carga no debe parecer una hipótesis que
pasa.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import inspect
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Iterable

from .contrato import Hipotesis, Modelo

#: Alias de paquete por directorio, para que dos carpetas ``hipotesis``
#: distintas no compartan espacio de nombres en ``sys.modules``.
_PAQUETES: dict[str, str] = {}


@dataclass(frozen=True)
class ErrorDeCarga:
    archivo: str
    mensaje: str

    def como_dict(self) -> dict[str, str]:
        return {"archivo": self.archivo, "mensaje": self.mensaje}


class ErrorDeRegistro(RuntimeError):
    """Se pidió una hipótesis o modelo que no está registrado."""


@dataclass
class Registro:
    """Colección de hipótesis y modelos disponibles."""

    hipotesis: dict[str, Hipotesis] = field(default_factory=dict)
    modelos: dict[str, Modelo] = field(default_factory=dict)
    errores: list[ErrorDeCarga] = field(default_factory=list)
    raiz: Path | None = None

    # -- consulta ------------------------------------------------------

    def ids_hipotesis(self) -> tuple[str, ...]:
        return tuple(sorted(self.hipotesis))

    def ids_modelos(self) -> tuple[str, ...]:
        return tuple(sorted(self.modelos))

    def obtener(self, id_: str) -> Hipotesis:
        try:
            return self.hipotesis[id_]
        except KeyError as exc:
            disponibles = ", ".join(self.ids_hipotesis()) or "ninguna"
            raise ErrorDeRegistro(
                f"Hipótesis '{id_}' no registrada (disponibles: {disponibles})"
            ) from exc

    def modelo(self, id_: str) -> Modelo:
        try:
            return self.modelos[id_]
        except KeyError as exc:
            raise ErrorDeRegistro(f"Modelo '{id_}' no registrado") from exc

    def __contains__(self, id_: str) -> bool:
        return id_ in self.hipotesis

    def __len__(self) -> int:
        return len(self.hipotesis)

    # -- diagnóstico ---------------------------------------------------

    def problemas(self) -> list[str]:
        """Inconsistencias del registro (errores de carga, ids duplicados)."""
        avisos = [f"{e.archivo}: {e.mensaje}" for e in self.errores]
        for id_, h in self.hipotesis.items():
            faltas = h.problemas_de_contrato()
            if faltas:
                avisos.append(f"{id_}: contrato incompleto -> {'; '.join(faltas)}")
        return avisos

    def resumen(self) -> dict[str, object]:
        return {
            "raiz": str(self.raiz) if self.raiz else None,
            "hipotesis": [
                {
                    "id": h.id,
                    "nombre": h.nombre,
                    "version": h.version,
                    "dataset_id": h.dataset_id,
                    "baseline": h.baseline.id if h.baseline else None,
                    "metrica": h.metrica,
                    "umbral_mejora": h.umbral_mejora,
                    "umbral_sensibilidad": h.umbral_sensibilidad,
                    "parametros_libres": [
                        p.nombre for p in h.parametros() if not p.congelado
                    ],
                    "contrato_completo": not h.problemas_de_contrato(),
                    "problemas": h.problemas_de_contrato(),
                    "archivo": type(h).__module__,
                }
                for h in sorted(self.hipotesis.values(), key=lambda x: x.id)
            ],
            "modelos": [
                {
                    "id": m.id,
                    "nombre": m.nombre,
                    "version": m.version,
                    "observables": list(m.observables),
                    "clase": type(m).__name__,
                }
                for m in sorted(self.modelos.values(), key=lambda x: x.id)
            ],
            "errores": [e.como_dict() for e in self.errores],
        }


# --------------------------------------------------------------------------
# Carga
# --------------------------------------------------------------------------


def _directorio_por_defecto() -> Path:
    return Path(__file__).resolve().parent.parent / "hipotesis"


def _paquete_para(raiz: Path) -> str:
    """Nombre de paquete sintético y estable para un directorio de hipótesis.

    Se usa un alias en lugar del nombre real de la carpeta: si no, una
    segunda carpeta ``hipotesis`` (por ejemplo en las pruebas) reutilizaría
    el paquete ya importado y las hipótesis de la primera dejarían de verse.
    """
    import hashlib

    clave = str(raiz.resolve()).lower()
    alias = _PAQUETES.get(clave)
    if alias:
        return alias
    alias = "_lab_pkg_" + hashlib.sha256(clave.encode("utf-8")).hexdigest()[:10]
    if alias not in sys.modules:
        espec = importlib.machinery.ModuleSpec(alias, None, is_package=True)
        paquete = importlib.util.module_from_spec(espec)
        paquete.__path__ = [str(raiz)]  # type: ignore[attr-defined]
        paquete.__package__ = alias
        sys.modules[alias] = paquete
    _PAQUETES[clave] = alias
    return alias


def _importar_modulo(ruta: Path, paquete: str | None) -> ModuleType:
    """Importa ``hipotesis/<stem>.py``.

    Si el directorio es un paquete (tiene ``__init__.py``), se importa como
    submódulo de un alias, lo que permite imports relativos entre hipótesis.
    Si no, se carga por ruta y esos imports no estarán disponibles.
    """
    if paquete:
        return importlib.import_module(f"{paquete}.{ruta.stem}")
    nombre = f"_lab_hipotesis_{ruta.stem}"
    espec = importlib.util.spec_from_file_location(nombre, ruta)
    if espec is None or espec.loader is None:
        raise ImportError(f"No se pudo preparar la importación de {ruta.name}")
    modulo = importlib.util.module_from_spec(espec)
    sys.modules[nombre] = modulo
    try:
        espec.loader.exec_module(modulo)
    except BaseException:
        sys.modules.pop(nombre, None)
        raise
    return modulo


def _modelos_de_modulo(modulo: ModuleType) -> list[Modelo]:
    """Extrae modelos: ``registrar()`` explícito, instancias o clases propias."""
    if callable(getattr(modulo, "registrar", None)):
        resultado = modulo.registrar()
        if resultado is None:
            return []
        if isinstance(resultado, Modelo):
            return [resultado]
        modelos = list(resultado)
        for m in modelos:
            if not isinstance(m, Modelo):
                raise TypeError(
                    f"registrar() devolvió {type(m).__name__}, que no es un Modelo"
                )
        return modelos

    encontrados: list[Modelo] = []
    vistos: set[str] = set()
    for nombre, objeto in vars(modulo).items():
        if isinstance(objeto, Modelo):
            if objeto.id not in vistos:
                encontrados.append(objeto)
                vistos.add(objeto.id)
            continue
        if inspect.isclass(objeto) and issubclass(objeto, Modelo):
            if objeto.__module__ != modulo.__name__:
                continue  # importado, no definido aquí
            if inspect.isabstract(objeto):
                continue
            try:
                instancia = objeto()
            except TypeError as exc:
                raise TypeError(
                    f"La clase {nombre} no se puede instanciar sin argumentos; "
                    "define registrar() en el módulo"
                ) from exc
            if instancia.id not in vistos:
                encontrados.append(instancia)
                vistos.add(instancia.id)
    return encontrados


def cargar_registro(directorio: str | Path | None = None) -> Registro:
    """Importa todos los módulos de ``hipotesis/`` y construye el registro."""
    raiz = Path(directorio).resolve() if directorio else _directorio_por_defecto()
    registro = Registro(raiz=raiz)
    if not raiz.is_dir():
        registro.errores.append(
            ErrorDeCarga(str(raiz), "El directorio de hipótesis no existe")
        )
        return registro

    # Los módulos se importan bajo un alias con ``__path__`` propio, así que no
    # hace falta añadir el directorio a ``sys.path``. Insertarlo contaminaba el
    # intérprete: una carpeta ``hipotesis`` de prueba podía quedar por delante de
    # la del proyecto y romper imports posteriores.

    archivos = sorted(p for p in raiz.glob("*.py") if not p.name.startswith("_"))
    paquete = _paquete_para(raiz) if (raiz / "__init__.py").is_file() else None
    for archivo in archivos:
        try:
            modulo = _importar_modulo(archivo, paquete)
            modelos = _modelos_de_modulo(modulo)
        except Exception:
            registro.errores.append(
                ErrorDeCarga(archivo.name, traceback.format_exc(limit=6))
            )
            continue

        if not modelos:
            registro.errores.append(
                ErrorDeCarga(
                    archivo.name,
                    "El módulo no expone ninguna hipótesis ni modelo (define "
                    "registrar() o una clase Hipotesis)",
                )
            )
            continue

        for modelo in modelos:
            if not str(modelo.id).strip():
                registro.errores.append(
                    ErrorDeCarga(archivo.name, f"{type(modelo).__name__} sin 'id'")
                )
                continue
            destino = registro.hipotesis if isinstance(modelo, Hipotesis) else registro.modelos
            if modelo.id in destino:
                registro.errores.append(
                    ErrorDeCarga(
                        archivo.name,
                        f"id duplicado '{modelo.id}' (ya registrado)",
                    )
                )
                continue
            destino[modelo.id] = modelo

    return registro


def modelos_de(registro: Registro, ids: Iterable[str]) -> list[Modelo]:
    return [registro.modelo(i) for i in ids]
