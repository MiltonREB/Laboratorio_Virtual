"""Preregistro criptográfico de una hipótesis.

Antes de evaluar, la hipótesis sella su firma de parámetros: enunciado,
umbrales, métrica, semilla y valores de cada parámetro. El sello es un
archivo con la firma canónica y su SHA-256.

Separación temporal (v1.1.0)
----------------------------
Sellar y evaluar en el mismo segundo no acredita nada: el hash pudo
calcularse después de ver los datos. Por eso la verificación exige que el
sello tenga una **antigüedad mínima** (``separacion_minima``) y, opcionalmente,
que esté **publicado** en un commit de git, que es un testigo externo con
fecha propia.

Qué garantiza y qué no:

* **Garantiza** que, si alguien cambia un umbral después de ver los datos, el
  hash deja de coincidir y la prueba T04 lo detecta.
* **Garantiza**, con la antigüedad mínima, que el sello no se fabricó en el
  mismo instante de la corrida.
* **No garantiza** que nadie mirase los datos antes de sellar. Eso no se
  resuelve con software: se resuelve con un registro público y con terceros.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .contrato import Hipotesis

#: Subdirectorio de resultados donde viven los sellos.
DIRECTORIO_SELLOS = "preregistro"

#: Estados posibles del preregistro (un solo campo semántico).
ESTADOS_PREREGISTRO: tuple[str, ...] = (
    "VALIDO",
    "AUSENTE",
    "TARDIO",
    "RECIENTE",
    "NO_PUBLICADO",
    "ALTERADO",
)

#: Estados que T04 acepta.
ESTADOS_ACEPTADOS = frozenset({"VALIDO"})


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

    @property
    def momento(self) -> datetime:
        return datetime.fromisoformat(self.creado_utc)


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


# --------------------------------------------------------------------------
# Publicación en git: testigo externo con fecha propia
# --------------------------------------------------------------------------


def _raiz_git(ruta: Path) -> Path | None:
    actual = ruta.resolve()
    for candidato in (actual, *actual.parents):
        if (candidato / ".git").exists():
            return candidato
    return None


def publicacion_git(ruta: str | Path) -> str | None:
    """Fecha del último commit que toca ``ruta``, o ``None`` si no está publicado."""
    camino = Path(ruta)
    if not camino.exists():
        return None
    raiz = _raiz_git(camino)
    if raiz is None:
        return None
    try:
        relativo = camino.resolve().relative_to(raiz)
    except ValueError:
        return None
    try:
        proceso = subprocess.run(
            ["git", "-C", str(raiz), "log", "-1", "--format=%cI", "--", str(relativo)],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proceso.returncode != 0:
        return None
    fecha = proceso.stdout.strip()
    return fecha or None


# --------------------------------------------------------------------------
# Verificación
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Verificacion:
    """Resultado único del preregistro: un estado y las pruebas que lo sostienen."""

    estado_preregistro: str
    firma_actual: str
    firma_en_sello: str | None = None
    ruta: str | None = None
    creado_utc: str | None = None
    antiguedad_segundos: float | None = None
    separacion_minima: float = 0.0
    publicado_utc: str | None = None

    def __post_init__(self) -> None:
        if self.estado_preregistro not in ESTADOS_PREREGISTRO:
            raise ValueError(f"Estado de preregistro desconocido: {self.estado_preregistro}")

    @property
    def existe(self) -> bool:
        return self.estado_preregistro != "AUSENTE"

    @property
    def coincide(self) -> bool:
        return self.estado_preregistro != "ALTERADO"

    @property
    def tardio(self) -> bool:
        return self.estado_preregistro == "TARDIO"

    @property
    def publicado(self) -> bool:
        return bool(self.publicado_utc)

    @property
    def aceptable(self) -> bool:
        return self.estado_preregistro in ESTADOS_ACEPTADOS

    def como_dict(self) -> dict[str, object]:
        return {
            "estado_preregistro": self.estado_preregistro,
            "aceptable": self.aceptable,
            "firma_en_sello": self.firma_en_sello,
            "firma_actual": self.firma_actual,
            "ruta": self.ruta,
            "creado_utc": self.creado_utc,
            "antiguedad_segundos": self.antiguedad_segundos,
            "separacion_minima": self.separacion_minima,
            "publicado_utc": self.publicado_utc,
            "publicado": self.publicado,
        }


def verificar(
    hipotesis: Hipotesis,
    raiz_resultados: str | Path,
    *,
    separacion_minima: float = 0.0,
    exigir_publicacion: bool = False,
    momento: datetime | None = None,
) -> Verificacion:
    """Compara la firma actual con el último sello y evalúa su antigüedad."""
    actual = firmar(hipotesis.firma_de_parametros())
    sello = ultimo_sello(raiz_resultados, hipotesis.id)
    instante = momento or _ahora()

    if sello is None:
        return Verificacion(
            estado_preregistro="AUSENTE",
            firma_actual=actual,
            separacion_minima=float(separacion_minima),
        )

    antiguedad = (instante - sello.momento).total_seconds()
    publicado = publicacion_git(sello.ruta)

    if sello.firma_sha256 != actual:
        estado = "ALTERADO"
    elif sello.tardio:
        estado = "TARDIO"
    elif antiguedad < float(separacion_minima):
        estado = "RECIENTE"
    elif exigir_publicacion and not publicado:
        estado = "NO_PUBLICADO"
    else:
        estado = "VALIDO"

    return Verificacion(
        estado_preregistro=estado,
        firma_actual=actual,
        firma_en_sello=sello.firma_sha256,
        ruta=str(sello.ruta),
        creado_utc=sello.creado_utc,
        antiguedad_segundos=antiguedad,
        separacion_minima=float(separacion_minima),
        publicado_utc=publicado,
    )


def describir(verificacion: Verificacion) -> str:
    """Frase corta con el motivo del estado, para informes."""
    estado = verificacion.estado_preregistro
    if estado == "VALIDO":
        texto = f"Sello verificado ({verificacion.firma_actual[:12]}…)"
        if verificacion.antiguedad_segundos is not None:
            texto += f", sellado {verificacion.antiguedad_segundos / 60:.1f} min antes"
        if verificacion.publicado_utc:
            texto += f", publicado en git el {verificacion.publicado_utc}"
        return texto
    if estado == "AUSENTE":
        return (
            "No hay sello de preregistro. Ejecuta `lab preregistrar --id <hipotesis>` "
            "antes de evaluar."
        )
    if estado == "ALTERADO":
        return (
            "La firma actual no coincide con el sello: parámetros, umbrales o métrica "
            "cambiaron después del preregistro."
        )
    if estado == "TARDIO":
        return (
            "El sello se creó durante la evaluación, no antes. No acredita anterioridad."
        )
    if estado == "RECIENTE":
        minimo = verificacion.separacion_minima
        edad = verificacion.antiguedad_segundos or 0.0
        return (
            f"El sello tiene {edad:.1f} s y se exigen {minimo:.0f} s de separación. "
            "Un sello creado en el mismo instante de la corrida no acredita nada."
        )
    if estado == "NO_PUBLICADO":
        return (
            "El sello no está publicado en un commit: no hay testigo externo con "
            "fecha propia. Haz `git add` + `git commit` del archivo del sello."
        )
    return estado


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
