"""Gráficos SVG de cada prueba del protocolo.

Un gráfico por prueba, generado a partir de ``resumen.json`` y
``predicciones.csv``. No usa matplotlib ni red: es SVG en línea, para que el
panel siga siendo un archivo que se abre con doble clic.

Cada función devuelve una cadena SVG completa. Si faltan datos, devuelve un
gráfico de sustitución que lo dice: un hueco silencioso se leería como «todo
bien».
"""

from __future__ import annotations

import html
import math
from typing import Any, Mapping, Sequence

FONDO = "#0d1627"
REJILLA = "#1b2942"
EJE = "#33465f"
TEXTO = "#93a4bd"
AZUL = "#38bdf8"
VERDE = "#22c55e"
ROJO = "#ef4444"
AMBAR = "#f59e0b"
VIOLETA = "#a78bfa"
GRIS = "#64748b"

ANCHO_POR_DEFECTO = 340
ALTO_POR_DEFECTO = 190


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------


def _e(valor: Any) -> str:
    return html.escape(str(valor))


def _numero(valor: Any, decimales: int = 3) -> str:
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(v):
        return "—"
    if v == 0:
        return "0"
    if abs(v) < 1e-3 or abs(v) >= 1e5:
        return f"{v:.2e}"
    return f"{v:.{decimales}g}"


def _esc(v: float, lo: float, hi: float, a: float, b: float) -> float:
    if hi == lo:
        return (a + b) / 2.0
    return a + (float(v) - lo) / (hi - lo) * (b - a)


def _lienzo(ancho: int, alto: int, etiqueta: str) -> list[str]:
    return [
        f'<svg viewBox="0 0 {ancho} {alto}" width="100%" '
        f'style="max-width:{ancho}px;height:auto" role="img" '
        f'aria-label="{_e(etiqueta)}">',
        f'<rect x="0" y="0" width="{ancho}" height="{alto}" fill="{FONDO}" rx="8"/>',
    ]


def _texto(x, y, contenido, color=TEXTO, tam=10, ancla="start", peso="400") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" fill="{color}" font-size="{tam}" '
        f'text-anchor="{ancla}" font-weight="{peso}">{_e(contenido)}</text>'
    )


def _sin_datos(ancho: int, alto: int, motivo: str) -> str:
    partes = _lienzo(ancho, alto, f"Sin datos para graficar: {motivo}")
    partes.append(
        _texto(ancho / 2, alto / 2, motivo, GRIS, 11, "middle")
    )
    partes.append("</svg>")
    return "".join(partes)


def _reservadas(predicciones: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [p for p in predicciones if str(p.get("particion")) == "reservado"]


def _rango(valores: Sequence[float], margen: float = 0.08) -> tuple[float, float]:
    """Rango con holgura; nunca degenerado, nunca vacío."""
    limpios = [float(v) for v in valores if math.isfinite(float(v))]
    if not limpios:
        return (0.0, 1.0)
    lo, hi = min(limpios), max(limpios)
    if hi - lo <= 1e-12:
        centro = (hi + lo) / 2.0
        delta = max(abs(centro) * 0.1, 1e-6)
        return (centro - delta, centro + delta)
    extension = (hi - lo) * margen
    return (lo - extension, hi + extension)


def _dentro(valor: float, lo: float, hi: float) -> bool:
    holgura = (hi - lo) * 0.02
    return (lo - holgura) <= valor <= (hi + holgura)


def _ref_horizontal(y: float, x0: float, x1: float, color: str,
                    guion: bool = False, ancho: float = 1.0) -> str:
    trazo = ' stroke-dasharray="4 3"' if guion else ""
    return (f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x1:.1f}" y2="{y:.1f}" '
            f'stroke="{color}" stroke-width="{ancho}"{trazo}/>')


# --------------------------------------------------------------------------
# T01 — formalización
# --------------------------------------------------------------------------


def t01(resumen, predicciones, ancho=ANCHO_POR_DEFECTO, alto=ALTO_POR_DEFECTO) -> str:
    h = resumen.get("hipotesis", {})
    campos = [
        ("enunciado", bool(h.get("enunciado"))),
        ("predicción diferenciadora", bool(h.get("prediccion_diferenciadora"))),
        ("dominio", bool(h.get("dominio"))),
        ("unidad del observable", bool(h.get("unidad_observable"))),
        ("baseline", bool(h.get("baseline"))),
        ("dataset", bool((resumen.get("dataset") or {}).get("id"))),
        ("métrica", bool(h.get("metrica"))),
        ("umbral de mejora", h.get("umbral_mejora") is not None),
        ("umbral de sensibilidad", h.get("umbral_sensibilidad") is not None),
        ("parámetros con unidad", bool(h.get("parametros"))),
    ]
    partes = _lienzo(ancho, alto, "Campos del contrato declarados")
    cumplidos = sum(1 for _, ok in campos if ok)
    partes.append(_texto(12, 20, f"Contrato: {cumplidos}/{len(campos)} campos", TEXTO, 11, "start", "600"))
    y = 34
    hueco = (alto - 46) / len(campos)
    for nombre, ok in campos:
        color = VERDE if ok else ROJO
        partes.append(
            f'<rect x="12" y="{y:.1f}" width="10" height="10" rx="2" fill="{color}"/>'
        )
        partes.append(_texto(28, y + 9, ("✓ " if ok else "✗ ") + nombre,
                             TEXTO if ok else ROJO, 10))
        y += hueco
    partes.append("</svg>")
    return "".join(partes)


# --------------------------------------------------------------------------
# T02 — distribución de la predicción
# --------------------------------------------------------------------------


def _histograma_svg(valores, x0, y0, w, h, color, bins=16) -> list[str]:
    partes: list[str] = []
    if not valores:
        return partes
    lo, hi = min(valores), max(valores)
    if hi == lo:
        hi = lo + 1.0
    cuentas = [0] * bins
    for v in valores:
        k = min(bins - 1, int((v - lo) / (hi - lo) * bins))
        cuentas[k] += 1
    tope = max(cuentas) or 1
    ancho_barra = w / bins
    for i, c in enumerate(cuentas):
        altura = (c / tope) * h
        partes.append(
            f'<rect x="{x0 + i * ancho_barra:.1f}" y="{y0 + h - altura:.1f}" '
            f'width="{max(1.0, ancho_barra - 1):.1f}" height="{altura:.1f}" '
            f'fill="{color}" fill-opacity="0.75"/>'
        )
    return partes


def t02(resumen, predicciones, ancho=ANCHO_POR_DEFECTO, alto=ALTO_POR_DEFECTO) -> str:
    datos = _reservadas(predicciones)
    if not datos:
        return _sin_datos(ancho, alto, "Sin predicciones en la muestra reservada")
    valores = [float(d["hipotesis"]) for d in datos]
    partes = _lienzo(ancho, alto, "Distribución de la predicción")
    partes.append(_texto(12, 18, f"Predicción en {len(valores)} filas reservadas", TEXTO, 10))
    partes.extend(_histograma_svg(valores, 14, 30, ancho - 28, alto - 62, AZUL))
    partes.append(_texto(14, alto - 18, f"mín {_numero(min(valores))}", TEXTO, 9))
    partes.append(_texto(ancho - 14, alto - 18, f"máx {_numero(max(valores))}", TEXTO, 9, "end"))
    partes.append("</svg>")
    return "".join(partes)


# --------------------------------------------------------------------------
# T03 — diferencia frente al baseline
# --------------------------------------------------------------------------


def t03(resumen, predicciones, ancho=ANCHO_POR_DEFECTO, alto=ALTO_POR_DEFECTO) -> str:
    datos = _reservadas(predicciones)
    if not datos:
        return _sin_datos(ancho, alto, "Sin predicciones en la muestra reservada")
    deltas = [float(d["hipotesis"]) - float(d["baseline"]) for d in datos]
    evidencia = _evidencia(resumen, "T03")
    exigido = float(evidencia.get("exigido") or 0.0)
    escala = evidencia.get("escala_baseline")
    lo, hi = _rango(deltas)
    x0, x1 = 14, ancho - 14
    y0, y1 = 26, alto - 32
    partes = _lienzo(ancho, alto, "Diferencia con el baseline por fila")
    partes.append(_texto(12, 18, "ΔO = hipótesis − baseline (por fila)", TEXTO, 10))
    if _dentro(0.0, lo, hi):
        partes.append(_ref_horizontal(_esc(0, lo, hi, y0, y1), x0, x1, EJE))
    banda = _dentro(exigido, lo, hi) or _dentro(-exigido, lo, hi)
    if banda:
        for signo in (-1, 1):
            y = _esc(signo * exigido, lo, hi, y0, y1)
            partes.append(_ref_horizontal(y, x0, x1, AMBAR, guion=True))
    puntos = []
    n = len(deltas)
    for i, d in enumerate(deltas):
        x = x0 + (x1 - x0) * (i / max(1, n - 1))
        y = _esc(d, lo, hi, y0, y1)
        puntos.append(f"{x:.1f},{y:.1f}")
    partes.append(
        f'<polyline points="{" ".join(puntos)}" fill="none" stroke="{AZUL}" '
        'stroke-width="1.3"/>'
    )
    nota = (f"exigido ±{_numero(exigido)}" if banda
            else f"exigido ±{_numero(exigido)} (fuera de escala)")
    if escala is not None:
        nota += f" · error baseline {_numero(escala)}"
    partes.append(_texto(ancho - 14, alto - 12, nota, AMBAR, 9, "end"))
    partes.append("</svg>")
    return "".join(partes)


# --------------------------------------------------------------------------
# T04 — sello de preregistro
# --------------------------------------------------------------------------


def t04(resumen, predicciones, ancho=ANCHO_POR_DEFECTO, alto=ALTO_POR_DEFECTO) -> str:
    pr = resumen.get("preregistro") or {}
    partes = _lienzo(ancho, alto, "Estado del sello de preregistro")
    estado = str(pr.get("estado_preregistro") or "AUSENTE")
    color = {
        "VALIDO": VERDE,
        "ALTERADO": ROJO,
        "AUSENTE": ROJO,
        "TARDIO": AMBAR,
        "RECIENTE": AMBAR,
        "NO_PUBLICADO": AMBAR,
    }.get(estado, GRIS)
    partes.append(
        f'<rect x="14" y="26" width="{ancho - 28}" height="70" rx="10" '
        f'fill="#16233a" stroke="{color}" stroke-width="1.5"/>'
    )
    partes.append(_texto(28, 48, "estado del preregistro", TEXTO, 9))
    partes.append(_texto(28, 70, estado, color, 15, "start", "700"))
    firma = str(pr.get("firma_actual") or "")
    partes.append(_texto(28, 88, firma[:44] or "sin firma", color, 9))
    edad = pr.get("antiguedad_segundos")
    mins = pr.get("separacion_minima") or 0
    filas = [
        ("coincide con la firma actual", estado != "ALTERADO", estado != "ALTERADO"),
        (f"antigüedad ≥ {_numero(mins, 0)} s",
         (isinstance(edad, (int, float)) and edad >= float(mins)),
         bool(pr.get("aceptable")) or estado in ("VALIDO",)),
        ("publicado en git", bool(pr.get("publicado_utc")), bool(pr.get("publicado_utc"))),
    ]
    y = 118
    for etiqueta, ok, bien in filas:
        partes.append(f'<circle cx="20" cy="{y - 4}" r="4" fill="{VERDE if bien else (ROJO if not ok else GRIS)}"/>')
        partes.append(_texto(32, y, etiqueta, TEXTO, 10))
        y += 22
    partes.append("</svg>")
    return "".join(partes)


# --------------------------------------------------------------------------
# T05 — reparto calibración / reservado
# --------------------------------------------------------------------------


def t05(resumen, predicciones, ancho=ANCHO_POR_DEFECTO, alto=ALTO_POR_DEFECTO) -> str:
    ds = resumen.get("dataset") or {}
    cal = int(ds.get("calibracion") or 0)
    res = int(ds.get("reservado") or 0)
    total = cal + res
    partes = _lienzo(ancho, alto, "Reparto entre calibración y reservado")
    if not total:
        return _sin_dibujo(ancho, alto, "Sin dataset cargado")
    ancho_total = ancho - 28
    x = 14
    for valor, color, etiqueta in ((cal, GRIS, "calibración"), (res, VERDE, "reservado")):
        w = ancho_total * valor / total
        partes.append(f'<rect x="{x:.1f}" y="52" width="{max(2.0, w - 2):.1f}" height="34" rx="4" fill="{color}" fill-opacity="0.85"/>')
        if w > 54:
            partes.append(_texto(x + w / 2 - 1, 74, str(valor), FONDO, 12, "middle", "700"))
        x += w
    partes.append(_texto(14, 40, f"{total} filas: {cal} para ajustar, {res} intactas", TEXTO, 10))
    libres = (resumen.get("hipotesis") or {}).get("parametros") or []
    n_libres = sum(1 for p in libres if not p.get("congelado"))
    y = 112
    partes.append(_texto(14, y, f"Parámetros libres ajustados: {n_libres}", TEXTO, 10))
    y += 20
    partes.append(_texto(14, y, "La muestra reservada no participa en ningún ajuste.", GRIS, 9))
    partes.append(_texto(14, y + 18, f"Reservado = {res / total:.0%} del total", GRIS, 9))
    partes.append("</svg>")
    return "".join(partes)


def _sin_dibujo(ancho: int, alto: int, motivo: str) -> str:
    return _sin_datos(ancho, alto, motivo)


# --------------------------------------------------------------------------
# T06 — residuos fuera de muestra
# --------------------------------------------------------------------------


def t06(resumen, predicciones, ancho=ANCHO_POR_DEFECTO, alto=ALTO_POR_DEFECTO) -> str:
    datos = _reservadas(predicciones)
    if not datos:
        return _sin_datos(ancho, alto, "Sin predicciones en la muestra reservada")
    residuos = [float(d["observado"]) - float(d["hipotesis"]) for d in datos]
    evidencia = _evidencia(resumen, "T06")
    escala = float(evidencia.get("escala") or 0.0)
    factor = float(evidencia.get("factor_admitido") or 5.0)
    limite = escala * factor
    lo, hi = _rango(residuos)
    x0, x1 = 14, ancho - 14
    y0, y1 = 26, alto - 34
    partes = _lienzo(ancho, alto, "Residuos de la hipótesis en la muestra reservada")
    if limite > 0 and (_dentro(limite, lo, hi) or _dentro(-limite, lo, hi)):
        alto_banda = _esc(min(limite, hi), lo, hi, y0, y1)
        bajo_banda = _esc(max(-limite, lo), lo, hi, y0, y1)
        partes.append(
            f'<rect x="{x0}" y="{alto_banda:.1f}" width="{x1 - x0}" '
            f'height="{max(1.0, bajo_banda - alto_banda):.1f}" fill="{VERDE}" '
            'fill-opacity="0.12"/>'
        )
        nota = f"banda admitida ±{_numero(limite)}"
    else:
        nota = f"banda admitida ±{_numero(limite)} (fuera de escala)"
    if _dentro(0.0, lo, hi):
        partes.append(_ref_horizontal(_esc(0, lo, hi, y0, y1), x0, x1, EJE))
    puntos = []
    n = len(residuos)
    for i, r in enumerate(residuos):
        x = x0 + (x1 - x0) * (i / max(1, n - 1))
        y = _esc(r, lo, hi, y0, y1)
        puntos.append(f"{x:.1f},{y:.1f}")
    partes.append(f'<polyline points="{" ".join(puntos)}" fill="none" stroke="{VIOLETA}" stroke-width="1.3"/>')
    partes.append(_texto(12, 18, "Residuos (observado − hipótesis)", TEXTO, 10))
    partes.append(_texto(ancho - 14, alto - 12, nota, VERDE, 9, "end"))
    partes.append("</svg>")
    return "".join(partes)


# --------------------------------------------------------------------------
# T07 — distribución bootstrap de la mejora
# --------------------------------------------------------------------------


def t07(resumen, predicciones, ancho=ANCHO_POR_DEFECTO, alto=ALTO_POR_DEFECTO) -> str:
    comp = resumen.get("comparacion") or {}
    hist = comp.get("histograma_bootstrap") or {}
    bordes = [float(b) for b in hist.get("bordes") or []]
    cuentas = [int(c) for c in hist.get("cuentas") or []]
    if not bordes or not cuentas:
        return _sin_datos(ancho, alto, "Sin distribución bootstrap registrada")
    i = comp.get("intervalo") or {}
    umbral = float((resumen.get("hipotesis") or {}).get("umbral_mejora") or 0.0)
    lo, hi = bordes[0], bordes[-1]
    if hi - lo <= 1e-12:
        lo, hi = lo - 0.05, hi + 0.05
    x0, x1 = 14, ancho - 14
    y0, y1 = 30, alto - 34
    tope = max(cuentas) or 1
    partes = _lienzo(ancho, alto, "Distribución bootstrap de la mejora")
    ancho_barra = (x1 - x0) / len(cuentas)
    for k, c in enumerate(cuentas):
        h = (c / tope) * (y1 - y0)
        x = x0 + k * ancho_barra
        partes.append(
            f'<rect x="{x:.1f}" y="{y1 - h:.1f}" width="{max(1.0, ancho_barra - 1):.1f}" '
            f'height="{h:.1f}" fill="{AZUL}" fill-opacity="0.55"/>'
        )
    referencias = [
        (float(i.get("ic_inferior", 0.0)), AMBAR, "IC inf"),
        (float(i.get("ic_superior", 0.0)), AMBAR, "IC sup"),
        (0.0, GRIS, "0"),
        (umbral, VERDE, "umbral"),
    ]
    fuera = []
    for valor, color, etiqueta in referencias:
        if not _dentro(valor, lo, hi):
            fuera.append(f"{etiqueta}={_numero(valor)}")
            continue
        x = _esc(valor, lo, hi, x0, x1)
        guion = "" if etiqueta in ("0", "umbral") else ' stroke-dasharray="4 3"'
        partes.append(
            f'<line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y1}" '
            f'stroke="{color}" stroke-width="1.2"{guion}/>'
        )
        partes.append(_texto(x, y0 - 6, etiqueta, color, 8, "middle"))
    partes.append(_texto(12, alto - 12, f"mejora puntual {_numero(i.get('mejora'))}", TEXTO, 9))
    partes.append(_texto(ancho - 12, alto - 12, f"{i.get('remuestreos')} remuestreos", TEXTO, 9, "end"))
    if fuera:
        partes.append(_texto(ancho - 12, alto - 24,
                             "fuera de escala: " + ", ".join(fuera), GRIS, 8, "end"))
    partes.append("</svg>")
    return "".join(partes)


# --------------------------------------------------------------------------
# T08 — mejora por partición alternativa
# --------------------------------------------------------------------------


def t08(resumen, predicciones, ancho=ANCHO_POR_DEFECTO, alto=ALTO_POR_DEFECTO) -> str:
    est = resumen.get("estabilidad") or {}
    ensayos = [e for e in (est.get("ensayos") or []) if "mejora" in e]
    if not ensayos:
        return _sin_datos(ancho, alto, "Sin particiones alternativas")
    mejoras = [float(e["mejora"]) for e in ensayos]
    umbral = float(est.get("umbral_mejora") or 0.0)
    lo, hi = _rango(mejoras + [0.0])
    x0, x1 = 14, ancho - 14
    y0, y1 = 26, alto - 32
    partes = _lienzo(ancho, alto, "Mejora en particiones alternativas")
    if _dentro(0.0, lo, hi):
        partes.append(_ref_horizontal(_esc(0, lo, hi, y0, y1), x0, x1, EJE))
    umbral_visible = _dentro(umbral, lo, hi)
    if umbral_visible:
        partes.append(_ref_horizontal(_esc(umbral, lo, hi, y0, y1), x0, x1, VERDE, guion=True))
    n = len(mejoras)
    ancho_barra = (x1 - x0) / n
    cero = _esc(0.0, lo, hi, y0, y1)
    for k, m in enumerate(mejoras):
        x = x0 + k * ancho_barra + ancho_barra * 0.2
        y = _esc(m, lo, hi, y0, y1)
        color = VERDE if m > 0 else ROJO
        partes.append(
            f'<rect x="{x:.1f}" y="{min(cero, y):.1f}" width="{ancho_barra * 0.6:.1f}" '
            f'height="{abs(cero - y):.1f}" fill="{color}" fill-opacity="0.8" rx="2"/>'
        )
    etiqueta_umbral = (f"umbral {_numero(umbral)}" if umbral_visible
                       else f"umbral {_numero(umbral)} (fuera de escala)")
    partes.append(_texto(12, 16, f"{n} particiones alternativas", TEXTO, 9))
    partes.append(_texto(ancho - 14, alto - 12,
                         f"media {_numero(est.get('mejora_media'))} · {etiqueta_umbral}",
                         TEXTO, 9, "end"))
    partes.append("</svg>")
    return "".join(partes)


# --------------------------------------------------------------------------
# T09 — reproducibilidad
# --------------------------------------------------------------------------


def t09(resumen, predicciones, ancho=ANCHO_POR_DEFECTO, alto=ALTO_POR_DEFECTO) -> str:
    r = resumen.get("reproducibilidad") or {}
    igual = bool(r.get("prediccion_identica")) and bool(r.get("bootstrap_identico"))
    color = VERDE if igual else ROJO
    partes = _lienzo(ancho, alto, "Reproducibilidad de la predicción")
    s1 = str(r.get("sha_prediccion_1") or "")
    s2 = str(r.get("sha_prediccion_2") or "")
    partes.append(_texto(14, 24, "ejecución 1", TEXTO, 9))
    partes.append(f'<rect x="14" y="30" width="{ancho - 28}" height="26" rx="6" fill="#16233a"/>')
    partes.append(_texto(22, 47, s1[:44] or "—", color, 9))
    partes.append(_texto(14, 82, "ejecución 2", TEXTO, 9))
    partes.append(f'<rect x="14" y="88" width="{ancho - 28}" height="26" rx="6" fill="#16233a"/>')
    partes.append(_texto(22, 105, s2[:44] or "—", color, 9))
    partes.append(
        f'<rect x="14" y="128" width="{ancho - 28}" height="34" rx="8" '
        f'fill="{color}" fill-opacity="0.16" stroke="{color}"/>'
    )
    partes.append(_texto(ancho / 2, 149, "idénticas bit a bit" if igual else "DIFIEREN",
                         color, 11, "middle", "700"))
    partes.append("</svg>")
    return "".join(partes)


# --------------------------------------------------------------------------
# T10 — presupuesto de incertidumbre
# --------------------------------------------------------------------------


def t10(resumen, predicciones, ancho=ANCHO_POR_DEFECTO, alto=ALTO_POR_DEFECTO) -> str:
    evidencia = _evidencia(resumen, "T10")
    razon = evidencia.get("razon_error_sobre_declarada")
    if razon is None:
        return _sin_datos(ancho, alto, "Sin presupuesto de incertidumbre declarado")
    razon = float(razon)
    tope = max(4.0, razon * 1.2)
    x0, x1 = 20, ancho - 20
    partes = _lienzo(ancho, alto, "Error observado frente a la incertidumbre declarada")
    partes.append(_texto(14, 18, "error observado / incertidumbre declarada", TEXTO, 10))
    y = 62
    partes.append(f'<rect x="{x0}" y="{y}" width="{x1 - x0}" height="22" rx="6" fill="#1b2942"/>')
    a = _esc(1 / 3, 0, tope, x0, x1)
    b = _esc(3.0, 0, tope, x0, x1)
    partes.append(f'<rect x="{a:.1f}" y="{y}" width="{b - a:.1f}" height="22" rx="4" fill="{VERDE}" fill-opacity="0.35"/>')
    xm = _esc(min(razon, tope), 0, tope, x0, x1)
    color = VERDE if 1 / 3 <= razon <= 3 else (ROJO if razon > 3 else AMBAR)
    partes.append(f'<line x1="{xm:.1f}" y1="{y - 8}" x2="{xm:.1f}" y2="{y + 30}" stroke="{color}" stroke-width="3"/>')
    partes.append(_texto(x0, y + 48, "0", TEXTO, 9))
    partes.append(_texto(a, y + 48, "1/3", TEXTO, 9, "middle"))
    partes.append(_texto(b, y + 48, "3", TEXTO, 9, "middle"))
    partes.append(_texto(x1, y + 48, f"{tope:.0f}", TEXTO, 9, "end"))
    partes.append(_texto(14, y + 78, f"razón = {razon:.2f}", color, 12, "start", "700"))
    partes.append("</svg>")
    return "".join(partes)


# --------------------------------------------------------------------------
# T11 — control nulo
# --------------------------------------------------------------------------


def t11(resumen, predicciones, ancho=ANCHO_POR_DEFECTO, alto=ALTO_POR_DEFECTO) -> str:
    c = resumen.get("control_nulo") or {}
    if c.get("error") or c.get("mejora") is None:
        return _sin_datos(ancho, alto, "Control nulo no ejecutado")
    mejora = float(c["mejora"])
    inferior = float(c.get("ic_inferior", mejora))
    superior = float(c.get("ic_superior", mejora))
    umbral = float((resumen.get("hipotesis") or {}).get("umbral_mejora") or 0.0)
    lo = min(inferior, 0.0, umbral) * 1.2
    hi = max(superior, umbral, 0.0) * 1.2
    if hi == lo:
        hi = lo + 1.0
    x0, x1 = 20, ancho - 20
    y = 78
    partes = _lienzo(ancho, alto, "Mejora sobre datos generados por el baseline")
    partes.append(_texto(14, 20, "Datos nulos: la verdad es el baseline", TEXTO, 10))
    xm = _esc(mejora, lo, hi, x0, x1)
    xi = _esc(inferior, lo, hi, x0, x1)
    xs = _esc(superior, lo, hi, x0, x1)
    xcero = _esc(0, lo, hi, x0, x1)
    xu = _esc(umbral, lo, hi, x0, x1)
    partes.append(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{EJE}"/>')
    partes.append(f'<line x1="{xcero:.1f}" y1="{y - 10}" x2="{xcero:.1f}" y2="{y + 10}" stroke="{GRIS}"/>')
    partes.append(f'<line x1="{xu:.1f}" y1="{y - 14}" x2="{xu:.1f}" y2="{y + 14}" stroke="{VERDE}" stroke-dasharray="4 3"/>')
    partes.append(f'<line x1="{xi:.1f}" y1="{y}" x2="{xs:.1f}" y2="{y}" stroke="{AMBAR}" stroke-width="3"/>')
    for xv in (xi, xs):
        partes.append(f'<line x1="{xv:.1f}" y1="{y - 6}" x2="{xv:.1f}" y2="{y + 6}" stroke="{AMBAR}" stroke-width="2"/>')
    partes.append(f'<circle cx="{xm:.1f}" cy="{y}" r="5" fill="{AZUL}"/>')
    partes.append(_texto(xu, y + 30, "umbral", VERDE, 8, "middle"))
    partes.append(_texto(14, 130, f"mejora {_numero(mejora)}", TEXTO, 10))
    partes.append(_texto(14, 148, f"IC [{_numero(inferior)}, {_numero(superior)}]", TEXTO, 9))
    partes.append("</svg>")
    return "".join(partes)


# --------------------------------------------------------------------------
# T12 — dominio de validez
# --------------------------------------------------------------------------


def t12(resumen, predicciones, ancho=ANCHO_POR_DEFECTO, alto=ALTO_POR_DEFECTO) -> str:
    evidencia = _evidencia(resumen, "T12")
    rango = evidencia.get("rango_declarado") or {}
    observado = evidencia.get("observado") or {}
    if not rango:
        return _sin_datos(ancho, alto, "Sin dominio declarado")
    partes = _lienzo(ancho, alto, "Cobertura del dominio declarado")
    partes.append(_texto(12, 18, "rango declarado (barra) y valores usados (puntos)", TEXTO, 9))
    x0, x1 = 76, ancho - 16
    y = 42
    filas = list(rango.items())[:4]
    for nombre, (lo, hi) in filas:
        datos = observado.get(nombre) or {}
        omin = datos.get("min")
        omax = datos.get("max")
        partes.append(_texto(12, y + 5, str(nombre), TEXTO, 9))
        partes.append(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{EJE}" stroke-width="2"/>')
        for marca in (lo, hi):
            x = _esc(marca, lo, hi, x0, x1)
            partes.append(f'<line x1="{x:.1f}" y1="{y - 5}" x2="{x:.1f}" y2="{y + 5}" stroke="{GRIS}" stroke-width="2"/>')
        if omin is not None and omax is not None:
            xa = _esc(max(min(omin, hi), lo), lo, hi, x0, x1)
            xb = _esc(min(max(omax, lo), hi), lo, hi, x0, x1)
            partes.append(f'<line x1="{xa:.1f}" y1="{y}" x2="{xb:.1f}" y2="{y}" stroke="{AZUL}" stroke-width="4" stroke-linecap="round"/>')
            partes.append(_texto((xa + xb) / 2, y - 10, f"{_numero(omin)}–{_numero(omax)}", AZUL, 8, "middle"))
        y += 34
    fuera = evidencia.get("fraccion_fuera") or {}
    malas = {k: v for k, v in fuera.items() if v}
    partes.append(_texto(12, alto - 12, "Fuera de rango: " + (", ".join(malas) if malas else "ninguna fila"), VERDE if not malas else ROJO, 9))
    partes.append("</svg>")
    return "".join(partes)


# --------------------------------------------------------------------------
# Despacho
# --------------------------------------------------------------------------


def _evidencia(resumen: Mapping[str, Any], codigo: str) -> Mapping[str, Any]:
    for prueba in resumen.get("pruebas") or []:
        if prueba.get("codigo") == codigo:
            return prueba.get("evidencia") or {}
    return {}


FUNCIONES = {
    "T01": t01, "T02": t02, "T03": t03, "T04": t04,
    "T05": t05, "T06": t06, "T07": t07, "T08": t08,
    "T09": t09, "T10": t10, "T11": t11, "T12": t12,
}


def grafico_prueba(
    codigo: str,
    resumen: Mapping[str, Any],
    predicciones: Sequence[Mapping[str, Any]],
    ancho: int = ANCHO_POR_DEFECTO,
    alto: int = ALTO_POR_DEFECTO,
) -> str:
    """Devuelve el SVG de una prueba; nunca lanza, siempre devuelve algo."""
    funcion = FUNCIONES.get(codigo)
    if funcion is None:
        return _sin_datos(ancho, alto, f"Sin gráfico para {codigo}")
    try:
        return funcion(resumen, predicciones, ancho, alto)
    except Exception as exc:  # un gráfico roto no debe romper el panel
        return _sin_datos(ancho, alto, f"{codigo}: {type(exc).__name__}")


#: Verificaciones opcionales con representación propia (las demás, texto).
def grafico_verificacion(
    codigo: str,
    resumen: Mapping[str, Any],
    ancho: int = ANCHO_POR_DEFECTO,
    alto: int = ALTO_POR_DEFECTO,
) -> str | None:
    """Gráfico para una verificación opcional ejecutada, o None."""
    verificacion = None
    for v in resumen.get("verificaciones") or []:
        if v.get("codigo") == codigo:
            verificacion = v
            break
    if verificacion is None or not verificacion.get("ejecutada"):
        return None
    evidencia = verificacion.get("evidencia") or {}
    if codigo == "O02" and evidencia.get("bloques"):
        return _grafico_bloques(evidencia["bloques"], ancho, alto)
    return None


def _grafico_bloques(bloques, ancho: int, alto: int) -> str:
    mejoras = [float(b["mejora"]) for b in bloques if "mejora" in b]
    if not mejoras:
        return _sin_datos(ancho, alto, "Sin bloques válidos")
    lo = min(mejoras + [0.0])
    hi = max(mejoras + [0.0])
    if hi == lo:
        hi = lo + 1.0
    x0, x1 = 20, ancho - 20
    y0, y1 = 30, alto - 40
    partes = _lienzo(ancho, alto, "Mejora por bloque del dominio")
    cero = _esc(0, lo, hi, y0, y1)
    partes.append(f'<line x1="{x0}" y1="{cero:.1f}" x2="{x1}" y2="{cero:.1f}" stroke="{EJE}"/>')
    n = len(mejoras)
    ancho_barra = (x1 - x0) / n
    for k, m in enumerate(mejoras):
        x = x0 + k * ancho_barra + ancho_barra * 0.22
        y = _esc(m, lo, hi, y0, y1)
        color = VERDE if m > 0 else ROJO
        partes.append(
            f'<rect x="{x:.1f}" y="{min(cero, y):.1f}" width="{ancho_barra * 0.56:.1f}" '
            f'height="{abs(cero - y):.1f}" fill="{color}" fill-opacity="0.8" rx="2"/>'
        )
        partes.append(_texto(x + ancho_barra * 0.28, alto - 24, f"B{k + 1}", TEXTO, 9, "middle"))
    partes.append(_texto(12, 18, "Mejora por tercio del dominio", TEXTO, 10))
    partes.append("</svg>")
    return "".join(partes)
