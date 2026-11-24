"""Verifica el panel generado: HTML bien formado, SVG válidos y bien escalados.

Útil después de tocar ``lab/panel.py`` o ``lab/graficos.py``: el panel es
HTML estático sin pruebas de navegador, así que esta comprobación hace de
red de seguridad.

    python herramientas/verificar_panel.py
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

VACIAS = {"meta", "br", "hr", "img", "input", "link"}


class _VerificadorHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.pila: list[str] = []
        self.errores: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in VACIAS:
            self.pila.append(tag)

    def handle_endtag(self, tag):
        if tag in VACIAS:
            return
        if not self.pila:
            self.errores.append(f"cierre sin apertura: {tag}")
            return
        if self.pila[-1] != tag:
            self.errores.append(f"esperaba </{self.pila[-1]}> y llegó </{tag}>")
        else:
            self.pila.pop()


def _coordenadas_fuera(svg: str) -> list[str]:
    raiz = ET.fromstring(svg)
    vista = (raiz.get("viewBox") or "0 0 340 190").split()
    ancho, alto = float(vista[2]), float(vista[3])
    problemas: list[str] = []
    for nodo in raiz.iter():
        for clave, limite in (("x", ancho), ("cx", ancho), ("x1", ancho),
                              ("x2", ancho), ("y", alto), ("cy", alto),
                              ("y1", alto), ("y2", alto)):
            valor = nodo.get(clave)
            if valor is None:
                continue
            try:
                v = float(valor)
            except ValueError:
                continue
            if v < -1 or v > limite + 1:
                local = nodo.tag.split("}")[-1]
                problemas.append(f"{local} {clave}={v:.1f} fuera de [0, {limite:.0f}]")
    return problemas


def revisar(carpeta_panel: Path) -> int:
    fallos = 0
    for archivo in sorted(carpeta_panel.rglob("*.html")):
        texto = archivo.read_text(encoding="utf-8")
        verificador = _VerificadorHTML()
        verificador.feed(texto)
        problemas = list(verificador.errores)
        if verificador.pila:
            problemas.append(f"sin cerrar: {verificador.pila}")

        svgs = re.findall(r"<svg.*?</svg>", texto, flags=re.S)
        for i, svg in enumerate(svgs):
            try:
                ET.fromstring(svg)
            except ET.ParseError as exc:
                problemas.append(f"svg#{i} mal formado: {exc}")
                continue
            problemas.extend(f"svg#{i} {p}" for p in _coordenadas_fuera(svg))

        estado = "OK" if not problemas else " | ".join(problemas)
        print(f"{archivo.as_posix():58s} {len(texto):7d} B  {len(svgs):2d} svg  {estado}")
        fallos += len(problemas)

    if not list(carpeta_panel.rglob("*.html")):
        print(f"No hay HTML en {carpeta_panel}: ejecuta `lab panel` primero.")
        return 1
    print(f"\nProblemas encontrados: {fallos}")
    return 1 if fallos else 0


def main(argv: list[str] | None = None) -> int:
    argumentos = list(sys.argv[1:] if argv is None else argv)
    raiz = Path(__file__).resolve().parent.parent
    carpeta = Path(argumentos[0]) if argumentos else raiz / "panel"
    return revisar(carpeta)


if __name__ == "__main__":
    raise SystemExit(main())
