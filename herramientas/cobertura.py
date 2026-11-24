"""Cobertura de las pruebas sobre el paquete ``lab`` sin dependencias externas.

Usa el módulo ``trace`` de la biblioteca estándar, así que funciona en el
mismo entorno que el laboratorio (no requiere ``coverage`` ni red).

    python herramientas/cobertura.py             # informe
    python herramientas/cobertura.py --minimo 80 # falla si baja del umbral

El denominador son las líneas que producen bytecode (``dis.findlinestarts``), no
las líneas físicas del archivo: comentarios y líneas en blanco no cuentan.
"""

from __future__ import annotations

import argparse
import dis
import io
import sys
import trace
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

#: Módulos que no entran en el total: ``__main__.py`` sólo se ejecuta como
#: script en otro proceso (lo cubre la prueba de ``python -m lab``).
EXCLUIDOS = {"__main__.py"}


def lineas_ejecutables(archivo: Path) -> set[int]:
    """Líneas que generan bytecode en un módulo."""
    fuente = archivo.read_text(encoding="utf-8")
    codigo = compile(fuente, str(archivo), "exec")
    lineas: set[int] = set()

    def recorrer(c) -> None:
        for _, numero in dis.findlinestarts(c):
            if numero:
                lineas.add(numero)
        for constante in c.co_consts:
            if hasattr(constante, "co_code"):
                recorrer(constante)

    recorrer(codigo)
    return lineas


def medir(minimo: float | None = None, verboso: bool = True) -> int:
    tracer = trace.Trace(
        count=True,
        trace=False,
        ignoredirs=[sys.prefix, sys.exec_prefix],
    )
    salida = io.StringIO()

    def ejecutar_suite():
        # El descubrimiento debe ocurrir DENTRO del trazado: importa los módulos
        # de prueba y, con ellos, el paquete ``lab``.
        cargador = unittest.TestLoader()
        suite = cargador.discover(str(RAIZ / "pruebas"), top_level_dir=str(RAIZ))
        ejecutor = unittest.TextTestRunner(stream=salida, verbosity=0)
        return ejecutor.run(suite)

    resultado = tracer.runfunc(ejecutar_suite)
    cuentas = tracer.results().counts

    cubiertas_por_archivo: dict[str, set[int]] = {}
    for (nombre, numero), veces in cuentas.items():
        if veces:
            cubiertas_por_archivo.setdefault(str(Path(nombre).resolve()), set()).add(numero)

    filas = []
    total_ejecutables = total_cubiertas = 0
    sin_cubrir: dict[str, list[int]] = {}

    for archivo in sorted((RAIZ / "lab").glob("*.py")):
        ejecutables = lineas_ejecutables(archivo)
        cubiertas = cubiertas_por_archivo.get(str(archivo.resolve()), set())
        alcanzadas = ejecutables & cubiertas
        porcentaje = 100.0 * len(alcanzadas) / len(ejecutables) if ejecutables else 100.0
        filas.append((archivo.name, len(ejecutables), len(alcanzadas), porcentaje))
        if archivo.name in EXCLUIDOS:
            sin_cubrir[archivo.name] = sorted(ejecutables - cubiertas)
            continue
        total_ejecutables += len(ejecutables)
        total_cubiertas += len(alcanzadas)
        sin_cubrir[archivo.name] = sorted(ejecutables - cubiertas)

    total = 100.0 * total_cubiertas / total_ejecutables if total_ejecutables else 0.0

    if verboso:
        print(f"Pruebas ejecutadas: {resultado.testsRun}  "
              f"fallos: {len(resultado.failures)}  errores: {len(resultado.errors)}")
        print()
        print(f"{'módulo':28s} {'líneas':>7s} {'cubiertas':>10s} {'%':>7s}")
        print("-" * 56)
        for nombre, n, c, p in filas:
            print(f"{nombre:28s} {n:7d} {c:10d} {p:6.1f}%")
        print("-" * 56)
        print(f"{'TOTAL del paquete lab':28s} {total_ejecutables:7d} "
              f"{total_cubiertas:10d} {total:6.1f}%")
        print()
        peores = sorted(filas, key=lambda f: f[3])[:4]
        for nombre, _, _, p in peores:
            lineas = sin_cubrir[nombre]
            if lineas and p < 95:
                muestra = ", ".join(str(x) for x in lineas[:14])
                extra = "…" if len(lineas) > 14 else ""
                print(f"  {nombre} ({p:.1f}%): sin cubrir {muestra}{extra}")

    if resultado.failures or resultado.errors:
        print("\nLa suite no pasó; la cobertura no es interpretable.")
        return 1
    if minimo is not None and total < minimo:
        print(f"\nCobertura {total:.1f}% por debajo del mínimo {minimo:.1f}%.")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimo", type=float, default=None,
                        help="Porcentaje mínimo exigido (por defecto, no exigir)")
    args = parser.parse_args(argv)
    return medir(minimo=args.minimo)


if __name__ == "__main__":
    raise SystemExit(main())
