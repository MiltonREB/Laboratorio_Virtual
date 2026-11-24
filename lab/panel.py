"""Panel HTML estático del laboratorio.

Se regenera con ``lab panel`` y no necesita servidor: son archivos que se
abren con doble clic. Todo el estilo va incrustado para que funcione sin red.
"""

from __future__ import annotations

import csv
import html
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .evaluador import cargar_corridas
from .protocolo import ORDEN, TITULOS
from .veredicto import DESCRIPCION_VEREDICTO
from . import catalogo, graficos

COLOR_ESTADO: dict[str, str] = {
    "APROBADO": "#15803d",
    "FALLIDO": "#b91c1c",
    "PENDIENTE": "#a16207",
    "NO_APLICABLE": "#475569",
    "NO_PRESENTADA": "#6d28d9",
    "SENSIBLE_AL_DISENO": "#c2410c",
}

COLOR_VEREDICTO: dict[str, str] = {
    "CORROBORADA_PROVISIONAL": "#15803d",
    "NO_CORROBORADA": "#b91c1c",
    "REFUTADA": "#7f1d1d",
    "NO_PRESENTADA": "#6d28d9",
    "SENSIBLE_AL_DISENO": "#c2410c",
    "FUERA_DE_DOMINIO": "#475569",
    "PENDIENTE": "#a16207",
}

ETIQUETA_ESTADO: dict[str, str] = {
    "APROBADO": "Aprobado",
    "FALLIDO": "Fallido",
    "PENDIENTE": "Pendiente",
    "NO_APLICABLE": "No aplicable",
    "NO_PRESENTADA": "No presentada",
    "SENSIBLE_AL_DISENO": "Sensible al diseño",
}

ETIQUETA_VEREDICTO: dict[str, str] = {
    "CORROBORADA_PROVISIONAL": "Corroborada (provisional)",
    "NO_CORROBORADA": "No corroborada",
    "REFUTADA": "Refutada",
    "NO_PRESENTADA": "No presentada",
    "SENSIBLE_AL_DISENO": "Sensible al diseño",
    "FUERA_DE_DOMINIO": "Fuera de dominio",
    "PENDIENTE": "Pendiente",
}

CSS = """
:root {
  --fondo: #0b1220;
  --panel: #121b2e;
  --panel-2: #17233b;
  --borde: #26344f;
  --texto: #e6ecf5;
  --tenue: #93a4bd;
  --acento: #38bdf8;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 0 0 64px;
  background: var(--fondo); color: var(--texto);
  font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
  font-size: 15px; line-height: 1.55;
}
header.tope {
  padding: 32px 40px 24px;
  border-bottom: 1px solid var(--borde);
  background: linear-gradient(140deg, #101a2e 0%, #0b1220 70%);
}
header.tope h1 { margin: 0 0 6px; font-size: 26px; letter-spacing: -0.3px; }
header.tope p { margin: 0; color: var(--tenue); max-width: 90ch; }
main { padding: 28px 40px 0; max-width: 1500px; }
h2 { font-size: 18px; margin: 36px 0 14px; padding-bottom: 8px;
     border-bottom: 1px solid var(--borde); font-weight: 600; }
h2:first-child { margin-top: 0; }
.kpis { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 20px; }
.kpi { background: var(--panel); border: 1px solid var(--borde);
       border-radius: 12px; padding: 14px 20px; min-width: 150px; }
.kpi .n { font-size: 26px; font-weight: 700; }
.kpi .e { color: var(--tenue); font-size: 12px; text-transform: uppercase;
          letter-spacing: .08em; }
table { width: 100%; border-collapse: collapse; margin: 8px 0 4px;
        background: var(--panel); border: 1px solid var(--borde);
        border-radius: 10px; overflow: hidden; font-size: 14px; }
th, td { padding: 9px 12px; text-align: left; border-bottom: 1px solid var(--borde); }
th { background: var(--panel-2); font-weight: 600; font-size: 12px;
     text-transform: uppercase; letter-spacing: .05em; color: var(--tenue); }
tr:last-child td { border-bottom: none; }
td.codigo { font-family: "Cascadia Mono", Consolas, monospace; font-weight: 600; }
.celda { text-align: center; font-weight: 600; font-size: 12px;
         color: #fff; border-radius: 6px; padding: 4px 0; }
.badge { display: inline-block; padding: 3px 11px; border-radius: 999px;
         font-size: 12px; font-weight: 700; color: #fff; }
.tarjetas { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
            gap: 18px; }
.tarjeta { background: var(--panel); border: 1px solid var(--borde);
           border-radius: 14px; padding: 18px 20px; }
.tarjeta h3 { margin: 0 0 4px; font-size: 17px; }
.tarjeta .id { color: var(--tenue); font-size: 12px; font-family: monospace; }
.tarjeta dl { display: grid; grid-template-columns: auto 1fr; gap: 3px 14px;
              margin: 14px 0 0; font-size: 13.5px; }
.tarjeta dt { color: var(--tenue); }
.tarjeta dd { margin: 0; font-variant-numeric: tabular-nums; }
.enlaces { margin-top: 14px; display: flex; gap: 10px; flex-wrap: wrap; }
a { color: var(--acento); text-decoration: none; }
a:hover { text-decoration: underline; }
a.boton { border: 1px solid var(--borde); border-radius: 8px;
          padding: 5px 12px; font-size: 13px; background: var(--panel-2); }
code { font-family: "Cascadia Mono", Consolas, monospace; font-size: 12.5px;
       background: #0d1627; padding: 2px 6px; border-radius: 5px; }
.vacio { color: var(--tenue); font-style: italic; }
ul.limpia { margin: 8px 0 0; padding-left: 20px; }
ul.limpia li { margin-bottom: 4px; }
footer { margin: 48px 40px 0; color: var(--tenue); font-size: 12.5px;
         border-top: 1px solid var(--borde); padding-top: 14px; }
.aviso { background: #2a1f0b; border: 1px solid #7c5a12; border-radius: 10px;
         padding: 12px 16px; margin: 16px 0; font-size: 13.5px; }
.figura { background: var(--panel); border: 1px solid var(--borde);
          border-radius: 12px; padding: 10px; margin: 10px 0; }
.figura figcaption { color: var(--tenue); font-size: 12.5px; padding: 6px 8px 2px; }
.grid-pruebas { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
                gap: 16px; margin-top: 6px; }
.prueba { background: var(--panel); border: 1px solid var(--borde);
          border-radius: 12px; padding: 14px 14px 10px; display: flex;
          flex-direction: column; }
.prueba .cab { display: flex; justify-content: space-between; align-items: center;
               gap: 8px; margin-bottom: 6px; }
.prueba .cod { font-family: "Cascadia Mono", Consolas, monospace;
               font-weight: 700; color: var(--acento); font-size: 13px; }
.prueba h4 { margin: 0 0 8px; font-size: 14px; font-weight: 600; }
.prueba p { margin: 0 0 12px; font-size: 12.8px; color: var(--tenue); }
.prueba .grafico { margin-top: auto; }
.nav { display: flex; gap: 12px; margin: 0 0 4px; flex-wrap: wrap; font-size: 13px; }
"""


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------


def _e(x: Any) -> str:
    return html.escape(str(x if x is not None else "—"))


def _num(x: Any, decimales: int = 4) -> str:
    if x is None:
        return "—"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return _e(x)
    if v != v:
        return "—"
    if v == 0:
        return "0"
    if abs(v) < 1e-3 or abs(v) >= 1e6:
        return f"{v:.3e}"
    return f"{v:+.{decimales}f}" if decimales <= 4 else f"{v:.{decimales}f}"


def _rel(destino: Path, origen: Path) -> str:
    return Path(os.path.relpath(destino, origen)).as_posix()


def _badge(estado: str, etiquetas: Mapping[str, str], colores: Mapping[str, str]) -> str:
    color = colores.get(estado, "#475569")
    texto = etiquetas.get(estado, estado)
    return f'<span class="badge" style="background:{color}">{_e(texto)}</span>'


def _celda(estado: str) -> str:
    color = COLOR_ESTADO.get(estado, "#475569")
    return (
        f'<td class="celda" style="background:{color}" '
        f'title="{_e(estado)}">{_e(estado[:4])}</td>'
    )


def _leer_predicciones(carpeta: Path) -> list[dict[str, float | str]]:
    archivo = carpeta / "predicciones.csv"
    if not archivo.is_file():
        return []
    with open(archivo, "r", newline="", encoding="utf-8") as f:
        return [
            {
                "particion": fila["particion"],
                "observado": float(fila["observado"]),
                "hipotesis": float(fila["prediccion_hipotesis"]),
                "baseline": float(fila["prediccion_baseline"]),
            }
            for fila in csv.DictReader(f)
        ]


def _svg_dispersion(carpeta: Path, ancho: int = 720, alto: int = 420) -> str:
    datos = [d for d in _leer_predicciones(carpeta) if d["particion"] == "reservado"]
    if not datos:
        return '<p class="vacio">Sin predicciones registradas para dibujar.</p>'

    observados = [float(d["observado"]) for d in datos]
    predichos = [float(d["hipotesis"]) for d in datos]
    base = [float(d["baseline"]) for d in datos]
    todos = observados + predichos + base
    lo, hi = min(todos), max(todos)
    if hi == lo:
        hi = lo + 1.0
    margen = 58
    izq, der = margen, ancho - 18
    sup, inf = 18, alto - margen

    def px(vino: float) -> float:
        return izq + (vino - lo) / (hi - lo) * (der - izq)

    def py(vino: float) -> float:
        return inf - (vino - lo) / (hi - lo) * (inf - sup)

    partes = [
        f'<svg viewBox="0 0 {ancho} {alto}" width="100%" '
        f'style="max-width:{ancho}px" role="img" '
        f'aria-label="Predicción frente a valor observado en la muestra reservada">',
        '<rect x="0" y="0" width="100%" height="100%" fill="#0d1627" rx="8"/>',
        f'<line x1="{px(lo)}" y1="{py(lo)}" x2="{px(hi)}" y2="{py(hi)}" '
        'stroke="#3f5578" stroke-dasharray="5 5" stroke-width="1.2"/>',
    ]
    for i in range(5):
        f = i / 4
        vino = lo + f * (hi - lo)
        x, y = px(vino), py(vino)
        partes.append(
            f'<line x1="{izq}" y1="{y:.1f}" x2="{der}" y2="{y:.1f}" '
            'stroke="#1b2942" stroke-width="1"/>'
        )
        partes.append(
            f'<text x="{izq - 8}" y="{y + 4:.1f}" fill="#93a4bd" font-size="10" '
            f'text-anchor="end">{vino:.4g}</text>'
        )
        partes.append(
            f'<text x="{x:.1f}" y="{inf + 16}" fill="#93a4bd" font-size="10" '
            f'text-anchor="middle">{vino:.4g}</text>'
        )
    for d in datos:
        partes.append(
            f'<circle cx="{px(float(d["observado"])):.1f}" '
            f'cy="{py(float(d["baseline"])):.1f}" r="3" fill="#64748b" '
            'fill-opacity="0.55"/>'
        )
        partes.append(
            f'<circle cx="{px(float(d["observado"])):.1f}" '
            f'cy="{py(float(d["hipotesis"])):.1f}" r="3.2" fill="#38bdf8" '
            'fill-opacity="0.85"/>'
        )
    partes.append(
        f'<text x="{(izq + der) / 2:.0f}" y="{alto - 18}" fill="#93a4bd" '
        'font-size="11" text-anchor="middle">valor observado</text>'
    )
    partes.append(
        f'<text x="16" y="{(sup + inf) / 2:.0f}" fill="#93a4bd" font-size="11" '
        f'text-anchor="middle" transform="rotate(-90 16 {(sup + inf) / 2:.0f})">'
        "valor predicho</text>"
    )
    partes.append(
        f'<text x="{der}" y="{sup + 12}" fill="#38bdf8" font-size="11" '
        'text-anchor="end">● hipótesis</text>'
    )
    partes.append(
        f'<text x="{der}" y="{sup + 26}" fill="#64748b" font-size="11" '
        'text-anchor="end">● baseline</text>'
    )
    partes.append("</svg>")
    return (
        '<figure class="figura">'
        + "".join(partes)
        + '<figcaption>Muestra reservada: puntos azules = hipótesis, grises = '
        "baseline convencional. La diagonal discontinua es la coincidencia "
        "perfecta. Cuanto más cerca de la diagonal, mejor; la separación entre "
        "azules y grises mide la predicción diferenciadora.</figcaption></figure>"
    )


def _pagina(titulo: str, cuerpo: str) -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"es\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_e(titulo)}</title>\n<style>{CSS}</style>\n</head>\n<body>\n"
        f"{cuerpo}\n</body>\n</html>\n"
    )


# --------------------------------------------------------------------------
# Página de una corrida
# --------------------------------------------------------------------------


def _seccion_pruebas(d: Mapping[str, Any], carpeta: Path) -> str:
    """Una tarjeta por prueba, con su resultado y su gráfico."""
    predicciones = _leer_predicciones(carpeta)
    tarjetas = []
    for p in d.get("pruebas", []):
        svg = graficos.grafico_prueba(p["codigo"], d, predicciones)
        tarjetas.append(
            '<article class="prueba">'
            f'<div class="cab"><span class="cod">{_e(p["codigo"])}</span>'
            f'{_badge(p["estado"], ETIQUETA_ESTADO, COLOR_ESTADO)}</div>'
            f'<h4>{_e(p["titulo"])}</h4>'
            f'<p>{_e(p["detalle"])}</p>'
            f'<div class="grafico">{svg}</div>'
            "</article>"
        )
    if not tarjetas:
        return '<p class="vacio">La corrida no registró pruebas.</p>'
    return '<div class="grid-pruebas">' + "".join(tarjetas) + "</div>"


def _seccion_verificaciones(d: Mapping[str, Any]) -> str:
    """Pruebas disponibles que se ejecutaron o que no hicieron falta, y por qué."""
    verificaciones = d.get("verificaciones") or []
    colores = {"EJECUTADA": COLOR_ESTADO["APROBADO"], "PENDIENTE": "#a16207",
               "NO_REQUERIDA": "#475569"}
    tarjetas = []
    for v in verificaciones:
        estado = str(v.get("estado", "NO_REQUERIDA"))
        color = colores.get(estado, "#475569")
        detalle = v.get("detalle") or ""
        svg = graficos.grafico_verificacion(v.get("codigo", ""), d) if v.get("ejecutada") else None
        bloque_grafico = f'<div class="grafico">{svg}</div>' if svg else ""
        tarjetas.append(
            '<article class="prueba">'
            f'<div class="cab"><span class="cod">{_e(v.get("codigo"))}</span>'
            f'<span class="badge" style="background:{color}">{_e(estado.replace("_", " "))}</span></div>'
            f'<h4>{_e(v.get("titulo"))}</h4>'
            f'<p>{_e(v.get("motivo"))}</p>'
            + (f'<p style="color:var(--texto)">{_e(detalle)}</p>' if detalle else "")
            + bloque_grafico
            + "</article>"
        )
    if not tarjetas:
        return (
            '<p class="vacio">Esta corrida no registró verificaciones opcionales '
            "(se generaron con una versión anterior del laboratorio).</p>"
        )
    return '<div class="grid-pruebas">' + "".join(tarjetas) + "</div>"


def _pagina_corrida(
    d: Mapping[str, Any], carpeta: Path, panel: Path, origen: Path
) -> str:
    h = d["hipotesis"]
    v = d["veredicto"]
    comp = d["comparacion"]
    i = comp["intervalo"]
    enlaces = [
        f'<a class="boton" href="{_e(_rel(carpeta / "INFORME.md", origen))}">Informe completo (Markdown)</a>',
        f'<a class="boton" href="{_e(_rel(carpeta / "resumen.json", origen))}">resumen.json</a>',
        f'<a class="boton" href="{_e(_rel(carpeta / "predicciones.csv", origen))}">predicciones.csv</a>',
        f'<a class="boton" href="{_e(_rel(carpeta / "matriz.csv", origen))}">matriz.csv</a>',
    ]
    est = d.get("estabilidad") or {}
    filas_est = "".join(
        f"<tr><td>{_e(e['particion'])}</td><td>{_e(e['semilla'])}</td>"
        f"<td>{_num(e.get('error_hipotesis'), 6)}</td>"
        f"<td>{_num(e.get('error_baseline'), 6)}</td>"
        f"<td>{_num(e.get('mejora'))}</td>"
        f"<td>{'sí' if e.get('alcanza_umbral') else 'no'}</td></tr>"
        for e in est.get("ensayos", [])
    ) or "<tr><td colspan='6' class='vacio'>Sin particiones alternativas</td></tr>"
    c = d.get("control_nulo") or {}
    pr = d.get("preregistro") or {}
    r = d.get("reproducibilidad") or {}
    advertencias = "".join(
        f'<div class="aviso">{_e(a)}</div>' for a in d.get("advertencias", [])
    )
    ds = d["dataset"]

    cuerpo = f"""
<header class="tope">
  <p><a href="{_e(_rel(panel / 'index.html', origen))}">← panel</a>
     · <a href="{_e(_rel(panel / 'pruebas.html', origen))}">catálogo de pruebas</a></p>
  <h1>{_e(h['nombre'])}</h1>
  <p><code>{_e(h['id'])}</code> v{_e(h['version'])} · corrida <code>{_e(d['corrida'])}</code>
     · {_e(d['entorno']['utc'])}</p>
  <div class="kpis">
    <div class="kpi"><div class="e">Veredicto</div>
      <div>{_badge(v['estado'], ETIQUETA_VEREDICTO, COLOR_VEREDICTO)}</div></div>
    <div class="kpi"><div class="e">Mejora vs baseline</div>
      <div class="n">{_num(i['mejora'])}</div></div>
    <div class="kpi"><div class="e">IC {int(i['nivel']*100)} %</div>
      <div class="n" style="font-size:16px">{_num(i['ic_inferior'])} a {_num(i['ic_superior'])}</div></div>
    <div class="kpi"><div class="e">Umbral exigido</div>
      <div class="n">{_num(h['umbral_mejora'])}</div></div>
  </div>
</header>
<main>
  {advertencias}
  <h2>Motivo del veredicto</h2>
  <p>{_e(v['motivo'])}</p>
  <p class="vacio">{_e(v['descripcion'])}</p>

  <h2>Hipótesis y predicción diferenciadora</h2>
  <p>{_e(h['enunciado'])}</p>
  <p><strong>Predicción diferenciadora:</strong> {_e(h['prediccion_diferenciadora'])}</p>
  <p><strong>Baseline:</strong> <code>{_e(h['baseline']['id'])}</code> — {_e(h['baseline']['nombre'])}</p>

  <h2>Muestra reservada</h2>
  {_svg_dispersion(carpeta)}

  <h2>Comparación</h2>
  <table>
    <tr><th>conjunto</th><th>error hipótesis</th><th>error baseline</th><th>métrica</th></tr>
    <tr><td>calibración</td><td>{_num(comp['error_calibracion'].get('hipotesis'), 6)}</td>
        <td>{_num(comp['error_calibracion'].get('baseline'), 6)}</td><td>{_e(h['metrica'])}</td></tr>
    <tr><td>reservado</td><td>{_num(comp['error_reservado'].get('hipotesis'), 6)}</td>
        <td>{_num(comp['error_reservado'].get('baseline'), 6)}</td><td>{_e(h['metrica'])}</td></tr>
  </table>

  <h2>Pruebas ejecutadas y sus resultados</h2>
  <p class="vacio">Cada tarjeta muestra el estado, el motivo y un gráfico propio
  de la prueba. Los datos salen de <code>resumen.json</code> y
  <code>predicciones.csv</code> de esta corrida.</p>
  {_seccion_pruebas(d, carpeta)}

  <h2>Verificaciones opcionales: ejecutadas y no requeridas</h2>
  <p class="vacio">Pruebas disponibles que esta corrida no necesitó, con el
  motivo concreto. «No requerida» nunca significa «superada».</p>
  {_seccion_verificaciones(d)}

  <h2>Estabilidad ante el diseño</h2>
  <table>
    <tr><th>partición</th><th>semilla</th><th>error hipótesis</th>
        <th>error baseline</th><th>mejora</th><th>alcanza umbral</th></tr>
    {filas_est}
  </table>

  <h2>Control nulo</h2>
  {f'<div class="aviso">No se pudo ejecutar: {_e(c.get("error"))}</div>' if c.get('error') else f'''
  <table>
    <tr><th>campo</th><th>valor</th></tr>
    <tr><td>mejora sobre datos generados por el baseline</td><td>{_num(c.get('mejora'))}</td></tr>
    <tr><td>IC inferior / superior</td><td>{_num(c.get('ic_inferior'))} / {_num(c.get('ic_superior'))}</td></tr>
    <tr><td>ruido usado en los datos nulos</td><td>{_num(c.get('sigma_usado'), 6)}</td></tr>
  </table>
  <p class="vacio">Si la hipótesis alcanzara su umbral aquí, la ventaja sería un
  artefacto del diseño y no un fenómeno.</p>'''}

  <h2>Preregistro y reproducibilidad</h2>
  <table>
    <tr><th>campo</th><th>valor</th></tr>
    <tr><td>sello de preregistro</td><td>{'existe' if pr.get('existe') else 'no existe'}</td></tr>
    <tr><td>coincide con la firma actual</td><td>{'sí' if pr.get('coincide') else 'no'}</td></tr>
    <tr><td>creado durante la evaluación (tardío)</td><td>{'sí' if pr.get('tardio') else 'no'}</td></tr>
    <tr><td>firma</td><td><code>{_e(pr.get('firma_actual'))}</code></td></tr>
    <tr><td>predicción idéntica en dos ejecuciones</td><td>{'sí' if r.get('prediccion_identica') else 'no'}</td></tr>
  </table>

  <h2>Dataset</h2>
  <table>
    <tr><th>campo</th><th>valor</th></tr>
    <tr><td>id</td><td><code>{_e(ds['id'])}</code></td></tr>
    <tr><td>filas</td><td>{_e(ds['filas'])}</td></tr>
    <tr><td>calibración / reservado</td><td>{_e(ds['calibracion'])} / {_e(ds['reservado'])}</td></tr>
    <tr><td>origen</td><td>{_e(ds['origen'])}</td></tr>
    <tr><td>SHA-256</td><td><code>{_e(ds['sha256'])}</code></td></tr>
    <tr><td>integridad</td><td>{'verificada' if ds['integridad'] else 'NO VERIFICADA'}</td></tr>
  </table>

  <h2>Archivos de la corrida</h2>
  <div class="enlaces">{''.join(enlaces)}</div>
</main>
<footer>Generado por el laboratorio de hipótesis. Una corroboración provisional
no es una demostración: no sustituye replicación independiente.</footer>
"""
    return _pagina(f"{h['id']} — {ETIQUETA_VEREDICTO.get(v['estado'], v['estado'])}", cuerpo)


# --------------------------------------------------------------------------
# Página índice
# --------------------------------------------------------------------------


def _pagina_catalogo(ultimas: Mapping[str, Mapping[str, Any]], panel: Path) -> str:
    """Catálogo de todas las pruebas: las vinculantes y las opcionales."""
    ids = sorted(ultimas)[:6]
    encabezados = "".join(f"<th>{_e(i)}</th>" for i in ids)

    def _prueba_de(d: Mapping[str, Any], codigo: str) -> str | None:
        for p in d.get("pruebas", []):
            if p.get("codigo") == codigo:
                return p.get("estado")
        return None

    def _verif_de(d: Mapping[str, Any], codigo: str) -> Mapping[str, Any] | None:
        for v in d.get("verificaciones", []) or []:
            if v.get("codigo") == codigo:
                return v
        return None

    filas_protocolo = []
    for definicion in catalogo.PRUEBAS_PROTOCOLO:
        celdas = []
        for id_ in ids:
            estado = _prueba_de(ultimas[id_], definicion.codigo)
            if estado is None:
                celdas.append("<td class='vacio'>—</td>")
            else:
                celdas.append(
                    f"<td>{_badge(estado, ETIQUETA_ESTADO, COLOR_ESTADO)}</td>"
                )
        filas_protocolo.append(
            f"<tr><td class='codigo'>{_e(definicion.codigo)}</td>"
            f"<td>{_e(definicion.titulo)}</td>"
            f"<td>{_e(definicion.proposito)}</td>"
            f"<td>{_e(definicion.no_requerida_cuando)}</td>"
            + "".join(celdas) + "</tr>"
        )

    filas_opcionales = []
    colores_verif = {"EJECUTADA": COLOR_ESTADO["APROBADO"], "PENDIENTE": "#a16207",
                     "NO_REQUERIDA": "#475569"}
    for definicion in catalogo.VERIFICACIONES_OPCIONALES:
        celdas = []
        for id_ in ids:
            v = _verif_de(ultimas[id_], definicion.codigo)
            if v is None:
                celdas.append("<td class='vacio'>—</td>")
                continue
            estado = str(v.get("estado", "NO_REQUERIDA"))
            color = colores_verif.get(estado, "#475569")
            etiqueta = estado.replace("_", " ")
            motivo = v.get("motivo") or ""
            celdas.append(
                f'<td><span class="badge" style="background:{color}">{_e(etiqueta)}</span>'
                f'<div class="vacio" style="margin-top:5px;font-size:11.5px">'
                f"{_e(motivo)}</div></td>"
            )
        filas_opcionales.append(
            f"<tr><td class='codigo'>{_e(definicion.codigo)}</td>"
            f"<td>{_e(definicion.titulo)}</td>"
            f"<td>{_e(definicion.proposito)}</td>"
            f"<td>{_e(definicion.no_requerida_cuando)}</td>"
            + "".join(celdas) + "</tr>"
        )

    if not ids:
        cuerpo_tablas = (
            '<p class="vacio">Todavía no hay corridas: ejecuta '
            "<code>lab ejecutar --todos --panel</code>.</p>"
        )
    else:
        cuerpo_tablas = f"""
  <h2>Pruebas del protocolo (vinculantes)</h2>
  <p class="vacio">Las doce pruebas que forman el veredicto. La columna
  «cuándo no se requiere» explica en qué caso legítimo una prueba no llega a
  ejecutarse; en ese caso el estado sería NO_APLICABLE o PENDIENTE, nunca
  APROBADO por omisión.</p>
  <table>
    <tr><th>código</th><th>prueba</th><th>propósito</th>
        <th>cuándo no se requiere</th>{encabezados}</tr>
    {''.join(filas_protocolo)}
  </table>

  <h2>Verificaciones opcionales (no vinculantes)</h2>
  <p class="vacio">Amplían el diagnóstico y <strong>no</strong> cambian el
  veredicto. Cuando no se ejecutan, el motivo queda escrito al lado: casi
  siempre es una precondición que la hipótesis no cumple.</p>
  <table>
    <tr><th>código</th><th>verificación</th><th>propósito</th>
        <th>cuándo no se requiere</th>{encabezados}</tr>
    {''.join(filas_opcionales)}
  </table>
"""

    cuerpo = f"""
<header class="tope">
  <div class="nav"><a href="{_e(_rel(panel / 'index.html', panel))}">← panel</a></div>
  <h1>Catálogo de pruebas</h1>
  <p>Qué puede hacer el laboratorio, qué hizo en la última corrida de cada
     hipótesis, y por qué alguna prueba disponible no fue necesaria.</p>
</header>
<main>
  {cuerpo_tablas}
</main>
<footer>Generado por <code>lab panel</code>. Las pruebas ejecutadas conservan su
gráfico y su detalle en la página de cada corrida.</footer>
"""
    return _pagina("Catálogo de pruebas", cuerpo)


def generar_panel(
    raiz_resultados: str | Path,
    directorio_panel: str | Path,
    *,
    titulo: str = "Laboratorio virtual de hipótesis",
) -> Path:
    """Escribe ``index.html`` y una página por corrida. Devuelve el índice."""
    raiz = Path(raiz_resultados).resolve()
    panel = Path(directorio_panel).resolve()
    panel.mkdir(parents=True, exist_ok=True)

    corridas = cargar_corridas(raiz)
    ultimas: dict[str, dict[str, Any]] = {}
    for c in corridas:
        id_ = c.get("hipotesis", {}).get("id")
        if id_ and id_ not in ultimas:
            ultimas[id_] = c

    # Páginas individuales
    for c in corridas:
        carpeta = Path(c["_archivo"]).parent
        destino = panel / "corridas" / f"{c['_carpeta']}.html"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            _pagina_corrida(c, carpeta, panel, destino.parent),
            encoding="utf-8",
            newline="\n",
        )

    corroboradas = sum(
        1 for c in ultimas.values()
        if c.get("veredicto", {}).get("estado") == "CORROBORADA_PROVISIONAL"
    )
    kpis = f"""
  <div class="kpis">
    <div class="kpi"><div class="e">Hipótesis registradas</div><div class="n">{len(ultimas)}</div></div>
    <div class="kpi"><div class="e">Corridas</div><div class="n">{len(corridas)}</div></div>
    <div class="kpi"><div class="e">Corroboradas</div><div class="n">{corroboradas}</div></div>
    <div class="kpi"><div class="e">Actualizado</div>
      <div class="n" style="font-size:15px">{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC</div></div>
  </div>"""

    # Matriz de estados
    if ultimas:
        filas = []
        for id_, c in sorted(ultimas.items()):
            estados = {p["codigo"]: p["estado"] for p in c.get("pruebas", [])}
            celdas = "".join(_celda(estados.get(cod, "PENDIENTE")) for cod in ORDEN)
            v = c.get("veredicto", {}).get("estado", "PENDIENTE")
            enlace = f"corridas/{c['_carpeta']}.html"
            filas.append(
                f"<tr><td><a href='{_e(enlace)}'>{_e(id_)}</a></td>"
                f"<td>{_badge(v, ETIQUETA_VEREDICTO, COLOR_VEREDICTO)}</td>"
                f"{celdas}</tr>"
            )
        cabecera = "".join(
            f'<th title="{_e(TITULOS[cod])}">{_e(cod)}</th>' for cod in ORDEN
        )
        tabla_matriz = (
            f"<table><tr><th>hipótesis</th><th>veredicto</th>{cabecera}</tr>"
            + "".join(filas)
            + "</table>"
            '<p class="vacio">Pasa el cursor sobre los códigos para ver el título '
            "completo. Aprobado = verde; fallido = rojo; pendiente = ámbar.</p>"
        )
    else:
        tabla_matriz = ('<p class="vacio">Todavía no hay corridas. Ejecuta '
                        "<code>lab ejecutar --todos</code>.</p>")

    # Tarjetas
    if ultimas:
        tarjetas = []
        for id_, c in sorted(ultimas.items()):
            h = c.get("hipotesis", {})
            v = c.get("veredicto", {})
            i = c.get("comparacion", {}).get("intervalo", {})
            fallidas = [p["codigo"] for p in c.get("pruebas", [])
                        if p["estado"] in ("FALLIDO", "NO_PRESENTADA", "SENSIBLE_AL_DISENO")]
            tarjetas.append(f"""
    <article class="tarjeta">
      <div class="id">{_e(id_)} · v{_e(h.get('version'))}</div>
      <h3>{_e(h.get('nombre'))}</h3>
      {_badge(v.get('estado', 'PENDIENTE'), ETIQUETA_VEREDICTO, COLOR_VEREDICTO)}
      <dl>
        <dt>Mejora</dt><dd>{_num(i.get('mejora'))}</dd>
        <dt>IC</dt><dd>{_num(i.get('ic_inferior'))} a {_num(i.get('ic_superior'))}</dd>
        <dt>Umbral</dt><dd>{_num(h.get('umbral_mejora'))}</dd>
        <dt>Dataset</dt><dd><code>{_e(h.get('dataset_id') or (c.get('dataset') or {}).get('id'))}</code></dd>
        <dt>Pruebas fallidas</dt><dd>{_e(', '.join(fallidas)) if fallidas else 'ninguna'}</dd>
      </dl>
      <div class="enlaces">
        <a class="boton" href="corridas/{_e(c['_carpeta'])}.html">Detalle</a>
      </div>
    </article>""")
        bloque_tarjetas = '<div class="tarjetas">' + "".join(tarjetas) + "</div>"
    else:
        bloque_tarjetas = '<p class="vacio">Sin hipótesis evaluadas.</p>'

    # Historial
    if corridas:
        filas_hist = []
        for c in corridas:
            h = c.get("hipotesis", {})
            v = c.get("veredicto", {})
            i = c.get("comparacion", {}).get("intervalo", {})
            filas_hist.append(
                f"<tr><td>{_e(c.get('entorno', {}).get('utc', '')[:19])}</td>"
                f"<td><a href='corridas/{_e(c['_carpeta'])}.html'>{_e(h.get('id'))}</a></td>"
                f"<td>{_badge(v.get('estado', 'PENDIENTE'), ETIQUETA_VEREDICTO, COLOR_VEREDICTO)}</td>"
                f"<td>{_num(i.get('mejora'))}</td>"
                f"<td><code>{_e(c['_carpeta'])}</code></td></tr>"
            )
        tabla_hist = (
            "<table><tr><th>fecha (UTC)</th><th>hipótesis</th><th>veredicto</th>"
            "<th>mejora</th><th>corrida</th></tr>" + "".join(filas_hist) + "</table>"
        )
    else:
        tabla_hist = '<p class="vacio">Sin corridas registradas.</p>'

    cuerpo = f"""
<header class="tope">
  <div class="nav"><a href="pruebas.html">Catálogo de pruebas →</a></div>
  <h1>{_e(titulo)}</h1>
  <p>Evaluación de hipótesis cuantitativas con un protocolo fijo: preregistro,
     calibración separada, datos reservados, baseline convencional, control nulo
     y veredicto explícito. Ningún estado pendiente se presenta como aprobación.</p>
  {kpis}
</header>
<main>
  <h2>Matriz de pruebas</h2>
  {tabla_matriz}

  <h2>Hipótesis</h2>
  {bloque_tarjetas}

  <h2>Historial de corridas</h2>
  {tabla_hist}
</main>
<footer>Panel estático generado por <code>lab panel</code>. Se puede abrir sin
servidor ni conexión. Los informes completos están en cada carpeta de corrida.</footer>
"""
    indice = panel / "index.html"
    (panel / "pruebas.html").write_text(
        _pagina_catalogo(ultimas, panel), encoding="utf-8", newline="\n"
    )
    indice.write_text(_pagina(titulo, cuerpo), encoding="utf-8", newline="\n")
    return indice
