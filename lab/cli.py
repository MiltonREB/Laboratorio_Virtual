"""Interfaz de línea de comandos del laboratorio.

    lab hipotesis listar
    lab datos verificar
    lab preregistrar --id mi_hipotesis
    lab ejecutar --id mi_hipotesis
    lab ejecutar --todos
    lab estado
    lab panel
    lab nuevo --id mi_hipotesis --nombre "Mi hipótesis"
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Sequence

from . import consolidado, evaluador, ingesta, panel as modulo_panel, preregistro
from .datos import ErrorDeDatos, Manifiesto
from .evaluador import ErrorDeEvaluacion, evaluar_hipotesis
from .informe import resumen_consola
from .protocolo import ORDEN, TITULOS
from .registro import ErrorDeRegistro, cargar_registro

RAIZ_POR_DEFECTO = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# Utilidades de consola
# --------------------------------------------------------------------------


def _configurar_salida() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def _titulo(texto: str) -> None:
    print(texto)
    print("=" * len(texto))


def _raiz(args: argparse.Namespace) -> Path:
    return Path(args.raiz).resolve() if args.raiz else RAIZ_POR_DEFECTO


def _rutas(raiz: Path) -> tuple[Path, Path, Path]:
    return raiz / "hipotesis", raiz / "datos", raiz / "resultados"


# --------------------------------------------------------------------------
# Comandos
# --------------------------------------------------------------------------


def cmd_hipotesis(args: argparse.Namespace) -> int:
    raiz = _raiz(args)
    registro = cargar_registro(_rutas(raiz)[0])
    if args.json:
        print(json.dumps(registro.resumen(), indent=2, ensure_ascii=False))
        return 0

    _titulo(f"Hipótesis registradas ({len(registro)})")
    if not registro.hipotesis:
        print("  (ninguna)")
    for h in sorted(registro.hipotesis.values(), key=lambda x: x.id):
        faltas = h.problemas_de_contrato()
        marca = "lista" if not faltas else f"contrato incompleto ({len(faltas)})"
        libres = [p.nombre for p in h.parametros() if not p.congelado]
        print(f"  {h.id:30s} v{h.version:8s} [{marca}]")
        print(f"    {h.nombre}")
        if h.baseline is not None:
            print(f"    baseline: {h.baseline.id}   dataset: {h.dataset_id or '-'}"
                  f"   metrica: {h.metrica}   libres: {', '.join(libres) or 'ninguno'}")
        for falta in faltas:
            print(f"    ! {falta}")

    if registro.modelos:
        print()
        _titulo(f"Modelos de referencia ({len(registro.modelos)})")
        for m in sorted(registro.modelos.values(), key=lambda x: x.id):
            print(f"  {m.id:30s} {m.nombre}")

    if registro.errores:
        print()
        _titulo(f"Errores de carga ({len(registro.errores)})")
        for e in registro.errores:
            print(f"  {e.archivo}:")
            for linea in e.mensaje.strip().splitlines()[-4:]:
                print(f"    {linea}")
    return 0


def cmd_datos(args: argparse.Namespace) -> int:
    raiz = _raiz(args)
    try:
        manifiesto = Manifiesto.desde_directorio(_rutas(raiz)[1])
    except ErrorDeDatos as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(manifiesto.resumen(), indent=2, ensure_ascii=False))
        return 0

    informe = manifiesto.verificar()
    _titulo(f"Conjuntos de datos ({len(manifiesto.ids)})")
    fallos = 0
    for id_, datos in informe.items():
        if datos["error"]:
            print(f"  [FALLO] {id_}: {datos['error']}")
            fallos += 1
            continue
        estado = "[OK] integridad verificada" if datos["ok"] else "[FALLO] SHA-256 NO COINCIDE"
        if not datos["ok"]:
            fallos += 1
        print(f"  {id_}: {estado}")
        print(f"    filas: {datos['filas']}   calibracion: {datos['calibracion']}"
              f"   reservado: {datos['reservado']}")
        print(f"    sha256: {datos['sha256_declarado']}")
        if not datos["ok"]:
            print(f"    sha256 actual: {datos['sha256_actual']}")
    print()
    if fallos:
        print(f"{fallos} dataset(s) con problemas de integridad.", file=sys.stderr)
        return 1
    return 0


def cmd_preregistrar(args: argparse.Namespace) -> int:
    raiz = _raiz(args)
    registro = cargar_registro(_rutas(raiz)[0])
    try:
        h = registro.obtener(args.id)
    except ErrorDeRegistro as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    faltas = h.problemas_de_contrato()
    if faltas and not args.forzar:
        print("No se puede preregistrar una hipótesis con el contrato incompleto:",
              file=sys.stderr)
        for falta in faltas:
            print(f"  ! {falta}", file=sys.stderr)
        print("\nCorrige el contrato o usa --forzar (no recomendado: el sello"
              " quedaría incompleto).", file=sys.stderr)
        return 1

    sello = preregistro.sellar(h, _rutas(raiz)[2], tardio=False)
    print(f"Sello creado para '{h.id}'")
    print(f"  firma SHA-256: {sello.firma_sha256}")
    print(f"  archivo:       {sello.ruta}")
    print(f"  creado:        {sello.creado_utc}")
    print()
    print("A partir de aquí no cambies parámetros, umbrales, métrica ni semilla:"
          " cualquier cambio invalidará el preregistro (prueba T04).")
    print()
    print("Para acreditar anterioridad, publica el sello en un commit:")
    print(f"  git add \"{sello.ruta}\"")
    print(f"  git commit -m \"preregistro: {h.id}\"")
    print("Después añade --exigir-publicacion al ejecutar.")
    return 0


def cmd_ejecutar(args: argparse.Namespace) -> int:
    raiz = _raiz(args)
    dir_hip, dir_datos, dir_resultados = _rutas(raiz)
    registro = cargar_registro(dir_hip)
    try:
        manifiesto = Manifiesto.desde_directorio(dir_datos)
    except ErrorDeDatos as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.id and args.todos:
        print("Usa --id o --todos, no ambos.", file=sys.stderr)
        return 2
    if not args.id and not args.todos:
        ids = list(registro.ids_hipotesis())
        if not ids:
            print("No hay hipótesis registradas.", file=sys.stderr)
            return 2
        print("Ninguna hipótesis indicada: se evalúan todas:", ", ".join(ids))
        args.todos = True

    ids = list(registro.ids_hipotesis()) if args.todos else [args.id]
    comparten: dict[str, int] = {}
    for otra in registro.hipotesis.values():
        comparten[otra.dataset_id] = comparten.get(otra.dataset_id, 0) + 1
    fallos = 0
    evaluadas = 0
    resultados = []
    for id_ in ids:
        try:
            h = registro.obtener(id_)
        except ErrorDeRegistro as exc:
            print(f"Error: {exc}", file=sys.stderr)
            fallos += 1
            continue
        if h.dataset_id and not manifiesto.contiene(h.dataset_id):
            print(
                f"[{id_}] omitida: el dataset '{h.dataset_id}' no está declarado "
                "en el manifiesto. Regístralo con `lab ingestar`.",
                file=sys.stderr,
            )
            continue
        try:
            resultado = evaluar_hipotesis(
                h,
                manifiesto,
                dir_resultados,
                remuestreos=args.remuestreos,
                particiones=args.particiones,
                guardar=not args.sin_guardar,
                sensibilidad_bootstrap=args.sensibilidad_bootstrap,
                hipotesis_mismo_dataset=comparten.get(h.dataset_id, 1),
                separacion_minima=args.separacion_minima,
                exigir_publicacion=args.exigir_publicacion,
            )
        except ErrorDeEvaluacion as exc:
            print(f"\n[{id_}] no se pudo evaluar: {exc}", file=sys.stderr)
            fallos += 1
            continue
        except ErrorDeDatos as exc:
            print(f"\n[{id_}] problema de datos: {exc}", file=sys.stderr)
            fallos += 1
            continue
        resultados.append(resultado)
        evaluadas += 1
        print()
        print(resumen_consola(resultado))
        if not args.sin_guardar:
            print(f"Artefactos: {resultado.corrida}")

    if evaluadas == 0:
        print(
            "\nNinguna hipótesis se pudo evaluar. Revisa el manifiesto de datos "
            "(`lab datos verificar`) o registra el dataset con `lab ingestar`.",
            file=sys.stderr,
        )
        return 2

    if args.panel and resultados:
        indice = modulo_panel.generar_panel(dir_resultados, raiz / "panel")
        print(f"\nPanel actualizado: {indice}")

    return 1 if fallos else 0


def cmd_ingestar(args: argparse.Namespace) -> int:
    raiz = _raiz(args)
    dir_datos = _rutas(raiz)[1]
    try:
        entrada = ingesta.registrar(
            args.csv,
            dir_datos,
            id_=args.id,
            fraccion_calibracion=args.fraccion,
            semilla=args.semilla,
            procedencia=args.procedencia,
            descripcion=args.descripcion,
            reemplazar=args.reemplazar,
        )
    except (ingesta.ErrorDeIngesta, ErrorDeDatos) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Dataset ingresado: {entrada['id']}")
    print(f"  archivo:   {dir_datos / entrada['ruta']}")
    print(f"  filas:     {entrada['filas']}")
    print(f"  partición: {len(entrada['calibracion'])} calibración / "
          f"{len(entrada['reservado'])} reservado "
          f"(fracción {entrada['particion']['fraccion_calibracion']}, "
          f"semilla {entrada['particion']['semilla']})")
    print(f"  sha256:    {entrada['sha256']}")
    if entrada.get("incertidumbres"):
        print(f"  incertidumbres: {entrada['incertidumbres']}")
    else:
        print("  incertidumbres: no declaradas (T10 dependerá del presupuesto)")
    print()
    print("La partición queda congelada en el manifiesto. Para evaluar:")
    print(f"  lab ejecutar --id <hipotesis que use '{entrada['id']}'>")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Ingesta (si hace falta) y evalúa en un solo paso.

    Equivale a `lab ingestar` + `lab ejecutar`. No sella: el preregistro debe
    hacerse antes, o T04 quedará en PENDIENTE y el veredicto lo dirá.
    """
    raiz = _raiz(args)
    dir_datos = _rutas(raiz)[1]
    try:
        manifiesto = Manifiesto.desde_directorio(dir_datos)
        ids = manifiesto.ids
    except ErrorDeDatos:
        ids = ()
    if args.id not in ids:
        args_csv = args.csv
        if not args_csv:
            print(
                f"El dataset '{args.id}' no está en el manifiesto y no se indicó "
                "--csv para ingerirlo.",
                file=sys.stderr,
            )
            return 2
        try:
            entrada = ingesta.registrar(
                args_csv,
                dir_datos,
                id_=args.id,
                fraccion_calibracion=args.fraccion,
                semilla=args.semilla,
                procedencia=args.procedencia,
                descripcion=args.descripcion,
                reemplazar=args.reemplazar,
            )
        except (ingesta.ErrorDeIngesta, ErrorDeDatos) as exc:
            print(f"Error al ingerir: {exc}", file=sys.stderr)
            return 1
        print(f"Dataset '{entrada['id']}' registrado con {entrada['filas']} filas.")
    args.id = args.hipotesis
    args.todos = False
    return cmd_ejecutar(args)


def cmd_estado(args: argparse.Namespace) -> int:
    raiz = _raiz(args)
    dir_resultados = _rutas(raiz)[2]
    ultimas = evaluador.ultima_corrida_por_hipotesis(dir_resultados)
    if not ultimas:
        print("No hay corridas registradas todavía.")
        return 0

    if args.json:
        print(json.dumps(
            {
                id_: {
                    "veredicto": c.get("veredicto", {}).get("estado"),
                    "motivo": c.get("veredicto", {}).get("motivo"),
                    "utc": c.get("entorno", {}).get("utc"),
                    "pruebas": {p["codigo"]: p["estado"] for p in c.get("pruebas", [])},
                }
                for id_, c in ultimas.items()
            },
            indent=2, ensure_ascii=False,
        ))
        return 0

    _titulo("Estado del laboratorio (última corrida por hipótesis)")
    ancho = 34
    cabecera = "hipotesis".ljust(ancho) + " " + " ".join(ORDEN)
    print(cabecera)
    print("-" * len(cabecera))
    simbolos = {
        "APROBADO": "ok ",
        "FALLIDO": "X  ",
        "PENDIENTE": ".  ",
        "SENSIBLE": "sn ",
    }
    for id_, c in sorted(ultimas.items()):
        estados = {p["codigo"]: p["estado"] for p in c.get("pruebas", [])}
        fila = id_[:ancho].ljust(ancho) + " " + " ".join(
            simbolos.get(estados.get(cod, "PENDIENTE"), "?  ") for cod in ORDEN
        )
        print(fila)
    print()
    for id_, c in sorted(ultimas.items()):
        v = c.get("veredicto", {})
        print(f"  {id_}: {v.get('estado')}")
        print(f"    {v.get('motivo')}")
    print()
    print("Leyenda: ok=aprobado  X=fallido  .=pendiente  sn=sensible al diseno")
    print()
    for cod in ORDEN:
        print(f"  {cod}  {TITULOS[cod]}")
    return 0


def cmd_consolidado(args: argparse.Namespace) -> int:
    raiz = _raiz(args)
    destino = Path(args.salida) if args.salida else None
    ruta = consolidado.generar_informe(_rutas(raiz)[2], destino)
    print(f"Informe consolidado: {ruta}")
    if not args.salida:
        print(f"Se abre como texto; el panel sigue en {raiz / 'panel' / 'index.html'}")
    return 0


def cmd_panel(args: argparse.Namespace) -> int:
    raiz = _raiz(args)
    indice = modulo_panel.generar_panel(
        _rutas(raiz)[2], raiz / "panel", titulo=args.titulo
    )
    print(f"Panel generado: {indice}")
    print("Abre ese archivo con el navegador (no necesita servidor).")
    return 0


PLANTILLA = '''"""Hipótesis: {nombre}.

Rellena los TODO. El laboratorio rechazará la hipótesis (T01) mientras falte
cualquier metadato, y no la dará por corroborada (T04) sin preregistro.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from lab.contrato import Dominio, Hipotesis, Modelo, Parametro


class Baseline{clase}(Modelo):
    """Modelo convencional de referencia. No puede ser la propia hipótesis."""

    id = "{id}_baseline"
    nombre = "Baseline de {nombre}"
    version = "0.1.0"
    observables = ("y", )            # TODO: nombre del observable
    requiere = ("x", )               # TODO: variables de entrada
    supuestos = "TODO: qué asume este modelo de referencia"

    PARAMETROS = ()

    def predecir(
        self,
        variables: Mapping[str, np.ndarray],
        parametros: Mapping[str, float],
    ) -> dict[str, np.ndarray]:
        x = np.asarray(variables["x"], dtype=float)
        # TODO: implementa el modelo de referencia
        raise NotImplementedError("TODO: implementa el baseline")


class {clase}(Hipotesis):
    """TODO: enunciado en una frase."""

    id = "{id}"
    nombre = "{nombre}"
    version = "0.1.0"

    observables = ("y", )
    requiere = ("x", )

    enunciado = "TODO: una frase falsable"
    prediccion_diferenciadora = (
        "TODO: qué predice esta hipótesis que el baseline no predice"
    )

    dominio = Dominio(
        descripcion="TODO: condiciones en las que la hipótesis pretende valer",
        rango={{"x": (0.0, 1.0)}},          # TODO: rango real
        limitaciones=(),
    )

    observable_objetivo = "y"
    unidad_observable = "u"              # TODO: unidad
    baseline = Baseline{clase}()

    dataset_id = "TODO_dataset"
    metrica = "rmse"
    umbral_mejora = 0.10                 # TODO: fijar ANTES de ver los datos
    umbral_sensibilidad = 1e-3           # TODO: |dO| mínimo apreciable
    incertidumbre_declarada = float("nan")  # TODO: presupuesto de incertidumbre
    semilla = 0

    PARAMETROS = (
        # Parametro("g", 9.80665, "m/s^2", congelado=True),
        # Parametro("k", 0.0, "1", congelado=False),   # libre: se ajusta
    )

    def predecir(
        self,
        variables: Mapping[str, np.ndarray],
        parametros: Mapping[str, float],
    ) -> dict[str, np.ndarray]:
        x = np.asarray(variables["x"], dtype=float)
        # TODO: implementa la predicción. Debe ser una función pura.
        raise NotImplementedError("TODO: implementa la predicción de la hipótesis")

    # Si declaras parámetros libres, ajusta SOLO con lo que recibes aquí:
    #
    # def ajustar(self, variables, observado, parametros):
    #     ...  # devuelve el diccionario de parámetros ajustados


def registrar() -> list[Modelo]:
    return [Baseline{clase}(), {clase}()]
'''


def cmd_nuevo(args: argparse.Namespace) -> int:
    raiz = _raiz(args)
    id_ = args.id
    if not id_.isidentifier():
        print(f"El id '{id_}' no es un identificador válido de Python.",
              file=sys.stderr)
        return 2
    destino = _rutas(raiz)[0] / f"{id_}.py"
    if destino.exists() and not args.forzar:
        print(f"Ya existe {destino}. Usa otro --id o --forzar.", file=sys.stderr)
        return 1
    clase = "".join(parte.capitalize() for parte in id_.split("_"))
    contenido = PLANTILLA.format(id=id_, nombre=args.nombre, clase=clase)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8", newline="\n")
    print(f"Hipótesis creada: {destino}")
    print()
    print("Siguiente:")
    print("  1. Rellena los TODO del archivo.")
    print("  2. Comprueba el contrato:  lab hipotesis listar")
    print("  3. Declara el dataset en datos/manifiesto.json (con su SHA-256).")
    print(f"  4. Sella los umbrales:     lab preregistrar --id {id_}")
    print(f"  5. Evalúa:                 lab ejecutar --id {id_}")
    return 0


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lab",
        description=(
            "Laboratorio virtual de hipótesis: preregistro, datos reservados, "
            "baseline convencional, control nulo y veredicto explícito."
        ),
    )
    parser.add_argument("--raiz", help="Raíz del laboratorio (por defecto, la del paquete)")
    parser.add_argument("--version", action="version", version="lab 1.0.0")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("hipotesis", help="Lista las hipótesis registradas")
    p.add_argument("accion", nargs="?", default="listar", choices=["listar"])
    p.add_argument("--json", action="store_true", help="Salida JSON")
    p.set_defaults(func=cmd_hipotesis)

    p = sub.add_parser("datos", help="Lista y verifica los datasets")
    p.add_argument("accion", nargs="?", default="verificar", choices=["listar", "verificar"])
    p.add_argument("--json", action="store_true", help="Salida JSON")
    p.set_defaults(func=cmd_datos)

    p = sub.add_parser("preregistrar", help="Sella parámetros y umbrales antes de evaluar")
    p.add_argument("--id", required=True)
    p.add_argument("--forzar", action="store_true",
                   help="Sella aunque el contrato esté incompleto")
    p.set_defaults(func=cmd_preregistrar)

    p = sub.add_parser("ejecutar", help="Evalúa una hipótesis o todas")
    p.add_argument("--id")
    p.add_argument("--todos", action="store_true")
    p.add_argument("--remuestreos", type=int,
                   default=evaluador.REMUESTREOS_POR_DEFECTO)
    p.add_argument("--particiones", type=int,
                   default=evaluador.PARTICIONES_POR_DEFECTO)
    p.add_argument("--sin-guardar", action="store_true",
                   help="No escribe artefactos en resultados/")
    p.add_argument("--sensibilidad-bootstrap", action="store_true",
                   help="Ejecuta la verificación O03 (500 y 4000 remuestreos)")
    p.add_argument("--separacion-minima", type=float, default=60.0,
                   help="Segundos mínimos entre el sello y la corrida (por defecto 60)")
    p.add_argument("--exigir-publicacion", action="store_true",
                   help="Exige que el sello esté publicado en un commit de git")
    p.add_argument("--panel", action="store_true",
                   help="Regenera el panel al terminar")
    p.set_defaults(func=cmd_ejecutar)

    p = sub.add_parser("ingestar", help="Registra un CSV real en el manifiesto")
    p.add_argument("--csv", required=True, help="Ruta del CSV (L_m, theta0_rad, T_s, u_*)")
    p.add_argument("--id", required=True, help="Identificador del dataset")
    p.add_argument("--fraccion", type=float, default=0.6,
                   help="Fracción de calibración (por defecto 0.6)")
    p.add_argument("--semilla", type=int, default=2026,
                   help="Semilla de la partición, que queda registrada")
    p.add_argument("--procedencia", default="", help="Quién, cuándo y con qué instrumento")
    p.add_argument("--descripcion", default="", help="Descripción del dataset")
    p.add_argument("--reemplazar", action="store_true",
                   help="Sustituye una entrada existente con el mismo id")
    p.set_defaults(func=cmd_ingestar)

    p = sub.add_parser("run", help="Ingesta un CSV (si hace falta) y evalúa")
    p.add_argument("--csv", help="CSV a ingerir si el dataset no está registrado")
    p.add_argument("--id", required=True, help="Identificador del dataset")
    p.add_argument("--hipotesis", required=True, help="Hipótesis a evaluar")
    p.add_argument("--fraccion", type=float, default=0.6)
    p.add_argument("--semilla", type=int, default=2026)
    p.add_argument("--procedencia", default="")
    p.add_argument("--descripcion", default="")
    p.add_argument("--reemplazar", action="store_true")
    p.add_argument("--remuestreos", type=int,
                   default=evaluador.REMUESTREOS_POR_DEFECTO)
    p.add_argument("--particiones", type=int,
                   default=evaluador.PARTICIONES_POR_DEFECTO)
    p.add_argument("--sin-guardar", action="store_true")
    p.add_argument("--sensibilidad-bootstrap", action="store_true")
    p.add_argument("--separacion-minima", type=float,
                   default=evaluador.SEPARACION_MINIMA_POR_DEFECTO)
    p.add_argument("--exigir-publicacion", action="store_true")
    p.add_argument("--panel", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("estado", help="Matriz de estados de la última corrida")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_estado)

    p = sub.add_parser("consolidado",
                       help="Informe único que compara todas las hipótesis")
    p.add_argument("--salida", help="Ruta del Markdown (por defecto resultados/INFORME_CONSOLIDADO.md)")
    p.set_defaults(func=cmd_consolidado)

    p = sub.add_parser("panel", help="Genera el panel HTML estático")
    p.add_argument("--titulo", default="Laboratorio virtual de hipótesis")
    p.set_defaults(func=cmd_panel)

    p = sub.add_parser("nuevo", help="Crea el esqueleto de una hipótesis nueva")
    p.add_argument("--id", required=True)
    p.add_argument("--nombre", required=True)
    p.add_argument("--forzar", action="store_true")
    p.set_defaults(func=cmd_nuevo)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _configurar_salida()
    parser = construir_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\nInterrumpido.", file=sys.stderr)
        return 130
    except (ErrorDeDatos, ErrorDeRegistro) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception:
        print("Error inesperado:", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
