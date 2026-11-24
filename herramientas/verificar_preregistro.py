"""Verifica que un sello de preregistro publicado coincide con la corrida.

Dos comprobaciones, ambas sin privilegios:

1. **Local.** Recalcula el SHA-256 canónico de la firma del sello y lo compara
   con la firma que la corrida registró en ``resumen.json``.
2. **Remota** (``--url``). Descarga el sello publicado y comprueba que su
   ``firma_sha256`` es el mismo. Es lo que haría un revisor anónimo.

    python herramientas/verificar_preregistro.py \
        --sello resultados/preregistro/pendulo_amplitud/<fichero>.json \
        --resumen resultados/<corrida>/resumen.json \
        --url https://raw.githubusercontent.com/<usuario>/<repo>/<commit>/<ruta>

Devuelve 0 si todo coincide y 1 si algo no cuadra.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from lab.preregistro import firmar  # noqa: E402


def _leer_json(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def _firma_local(sello: dict) -> str:
    return firmar(sello.get("firma", {}))


def _descargar(url: str, tiempo_limite: float = 30.0) -> dict:
    peticion = urllib.request.Request(
        url, headers={"User-Agent": "lab-hipotesis-verificador/1.1"}
    )
    with urllib.request.urlopen(peticion, timeout=tiempo_limite) as respuesta:
        return json.loads(respuesta.read().decode("utf-8"))


def _configurar_salida() -> None:
    """Evita que un símbolo reviente en una consola cp1252."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _configurar_salida()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sello", required=True, help="Ruta local del sello")
    parser.add_argument("--resumen", help="resumen.json de la corrida")
    parser.add_argument("--url", help="URL pública del sello en el commit")
    args = parser.parse_args(argv)

    sello = _leer_json(Path(args.sello))
    firma = _firma_local(sello)
    declarada = sello.get("firma_sha256")

    print(f"sello:            {args.sello}")
    print(f"firma recalculada: {firma}")
    print(f"firma declarada:   {declarada}")
    ok = True
    if firma != declarada:
        print("  ✗ el sello está alterado: la firma no coincide con su contenido")
        ok = False
    else:
        print("  ✓ el sello coincide con su contenido")

    if args.resumen:
        resumen = _leer_json(Path(args.resumen))
        preg = resumen.get("preregistro") or {}
        esperada = preg.get("firma_actual")
        print(f"\nresumen de la corrida: {args.resumen}")
        print(f"firma registrada:      {esperada}")
        if esperada == firma:
            print("  ✓ la corrida usó exactamente este sello")
        else:
            print("  ✗ la corrida registró otra firma: el sello cambió después")
            ok = False
        estado = preg.get("estado_preregistro")
        print(f"estado en la corrida:  {estado}")

    if args.url:
        print(f"\ndescargando: {args.url}")
        try:
            remoto = _descargar(args.url)
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
            print(f"  ✗ no se pudo descargar: {exc}")
            return 1
        remota = remoto.get("firma_sha256")
        print(f"firma publicada:   {remota}")
        if remota == firma:
            print("  ✓ la copia publicada es idéntica a la local")
        else:
            print("  ✗ la copia publicada difiere de la local")
            ok = False
        print(f"creado (UTC):      {remoto.get('creado_utc')}")

    print("\nresultado:", "OK" if ok else "REVISAR")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
