"""Preregistro criptográfico de una hipótesis.

Antes de evaluar, la hipótesis sella su firma de parámetros: enunciado,
umbrales, métrica, semilla y valores de cada parámetro. El sello es un
archivo con la firma canónica y su SHA-256.

Qué garantiza y qué no:

* **Garantiza** que, si alguien cambia un umbral después de ver los datos,
  el hash deja de coincidir y la prueba T04 lo detecta.
* **No garantiza** que el sello se creara antes de mirar los datos. Eso no
  se puede probar con software. Por eso un sello generado durante la
  evaluación se marca ``tardio=True`` y T04 no lo acepta como preregistro.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .contrato import Hipotesis

#: Subdirectorio de resultados donde viven los sellos.
DIRECTORIO_SELLOS = "preregistro"


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def serializar_canonico(objeto: object) -> str:
    """JSON canónico: claves ordenadas, sin espacios, UTF-8 literal."""
    return json.dumps(
        objeto, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def firmar(firma: Mapping[str, object]) -> str:
    """SHA-256 hexadecimal de la forma canónica de ``firma``."""
    import hashlib

    return hashlib.sha256(serializar_canonico(firma).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Sello:
    id: str
    creado_utc: str
    firma_sha256: str
    tardio: bool
    firma: Mapping[str, object]
    ruta: Path

    def como_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "creado_utc": self.creado_utc,
            "firma_sha256": self.firma_sha256,
            "tardio": self.tardio,
            "firma": dict(self.firma),
            "ruta": str(self.ruta),
        }


def directorio_sellos(raiz_resultados: str | Path, id_: str | None = None) -> Path:
    base = Path(raiz_resultados) / DIRECTORIO_SELLOS
    return base / id_ if id_ else base


def sellar(
    hipotesis: Hipotesis,
    raiz_resultados: str | Path,
    tardio: bool = False,
    momento: datetime | None = None,
) -> Sello:
    """Congela la firma actual y la escribe en un archivo nuevo."""
    firma = hipotesis.firma_de_parametros()
    sha = firmar(firma)
    instante = momento or _ahora()
    destino = directorio_sellos(raiz_resultados, hipotesis.id)
    destino.mkdir(parents=True, exist_ok=True)
    nombre = f"{instante.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    ruta = destino / nombre
    contenido = {
        "id": hipotesis.id,
        "creado_utc": instante.isoformat(),
        "firma_sha256": sha,
        "tardio": bool(tardio),
        "firma": firma,
    }
    ruta.write_text(
        json.dumps(contenido, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return Sello(hipotesis.id, contenido["creado_utc"], sha, bool(tardio), firma, ruta)


def _leer_sello(ruta: Path) -> Sello | None:
    try:
        contenido = json.loads(ruta.read_text(encoding="utf-8"))
        return Sello(
            id=str(contenido["id"]),
            creado_utc=str(contenido["creado_utc"]),
            firma_sha256=str(contenido["firma_sha256"]),
            tardio=bool(contenido.get("tardio", False)),
            firma=dict(contenido.get("firma", {})),
            ruta=ruta,
        )
    except (OSError, ValueError, KeyError):
        return None


def sellos(raiz_resultados: str | Path, id_: str) -> list[Sello]:
    """Todos los sellos de una hipótesis, del más antiguo al más reciente."""
    carpeta = directorio_sellos(raiz_resultados, id_)
    if not carpeta.is_dir():
        return []
    encontrados = [s for s in (_leer_sello(p) for p in sorted(carpeta.glob("*.json"))) if s]
    return encontrados


def ultimo_sello(raiz_resultados: str | Path, id_: str) -> Sello | None:
    todos = sellos(raiz_resultados, id_)
    return todos[-1] if todos else None


@dataclass(frozen=True)
class Verificacion:
    existe: bool
    coincide: bool
    tardio: bool
    firma_en_sello: str | None
    firma_actual: str
    ruta: str | None
    creado_utc: str | None

    @property
    def aceptable(self) -> bool:
        return self.existe and self.coincide and not self.tardio

    def como_dict(self) -> dict[str, object]:
        return {
            "existe": self.existe,
            "coincide": self.coincide,
            "tardio": self.tardio,
            "firma_en_sello": self.firma_en_sello,
            "firma_actual": self.firma_actual,
            "ruta": self.ruta,
            "creado_utc": self.creado_utc,
            "aceptable": self.aceptable,
        }


def verificar(hipotesis: Hipotesis, raiz_resultados: str | Path) -> Verificacion:
    """Compara la firma actual con el último sello registrado."""
    actual = firmar(hipotesis.firma_de_parametros())
    sello = ultimo_sello(raiz_resultados, hipotesis.id)
    if sello is None:
        return Verificacion(False, False, False, None, actual, None, None)
    return Verificacion(
        existe=True,
        coincide=(sello.firma_sha256 == actual),
        tardio=sello.tardio,
        firma_en_sello=sello.firma_sha256,
        firma_actual=actual,
        ruta=str(sello.ruta),
        creado_utc=sello.creado_utc,
    )


# --------------------------------------------------------------------------
# Diferencias legibles entre dos firmas
# --------------------------------------------------------------------------


def diferencias(antes: Mapping[str, object], despues: Mapping[str, object]) -> list[str]:
    """Cambios entre dos firmas, en texto apto para un informe."""
    cambios: list[str] = []
    claves = sorted(set(antes) | set(despues))
    for clave in claves:
        a = antes.get(clave)
        b = despues.get(clave)
        if isinstance(a, list) and isinstance(b, list) and clave == "parametros":
            mapaa = {str(p.get("nombre")): p.get("valor") for p in a if isinstance(p, dict)}
            mapab = {str(p.get("nombre")): p.get("valor") for p in b if isinstance(p, dict)}
            for nombre in sorted(set(mapaa) | set(mapab)):
                if mapaa.get(nombre) != mapab.get(nombre):
                    cambios.append(
                        f"parámetro '{nombre}': {mapaa.get(nombre)!r} -> {mapab.get(nombre)!r}"
                    )
            continue
        if a != b:
            cambios.append(f"'{clave}': {a!r} -> {b!r}")
    return cambios
