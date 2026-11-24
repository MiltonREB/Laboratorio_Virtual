"""Informes en Markdown y texto de consola.

El informe está escrito para que un lector pueda intentar refutar la
conclusión: expone los números, el motivo de cada estado y, al final, lo que
el experimento no demuestra.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Sequence

if TYPE_CHECKING:  # pragma: no cover
    from .evaluador import ResultadoEvaluacion


EMBLEMA: dict[str, str] = {
    "CORROBORADA_PROVISIONAL": "✅ CORROBORADA (provisional)",
    "NO_CORROBORADA": "❌ NO CORROBORADA",
    "REFUTADA": "🛑 REFUTADA",
    "NO_PRESENTADA": "⚪ NO PRESENTADA",
    "SENSIBLE_AL_DISENO": "🟠 SENSIBLE AL DISEÑO",
    "FUERA_DE_DOMINIO": "🚫 FUERA DE DOMINIO",
    "PENDIENTE": "⏳ PENDIENTE",
}


def _fmt(x: Any, decimales: int = 6) -> str:
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "sí" if x else "no"
    if isinstance(x, float):
        if x != x:  # NaN
            return "—"
        if x == 0:
            return "0"
        if abs(x) < 1e-3 or abs(x) >= 1e6:
            return f"{x:.{decimales}e}"
        return f"{x:.{decimales}g}"
    return str(x)


def _tabla(cabeceras: Sequence[str], filas: Sequence[Sequence[Any]]) -> str:
    lineas = ["| " + " | ".join(cabeceras) + " |"]
    lineas.append("|" + "|".join(["---"] * len(cabeceras)) + "|")
    for fila in filas:
        lineas.append("| " + " | ".join(_fmt(c) for c in fila) + " |")
    return "\n".join(lineas)


def informe_markdown(resultado: "ResultadoEvaluacion") -> str:
    d = resultado.datos
    h = d["hipotesis"]
    ds = d["dataset"]
    v = d["veredicto"]
    comp = d["comparacion"]
    partes: list[str] = []

    partes.append(f"# Informe de evaluación — {h['nombre']}")
    partes.append("")
    partes.append(f"**Hipótesis:** `{h['id']}` v{h['version']}  ")
    partes.append(f"**Veredicto:** {EMBLEMA.get(v['estado'], v['estado'])} — `{v['estado']}`  ")
    partes.append(f"**Corrida:** `{d['corrida']}`  ")
    partes.append(f"**Fecha (UTC):** {d['entorno']['utc']}  ")
    partes.append(f"**Laboratorio:** v{d['version_laboratorio']}")
    partes.append("")
    partes.append(f"> {v['descripcion']}")
    partes.append("")
    partes.append(f"**Motivo del veredicto:** {v['motivo']}")
    partes.append("")

    if d.get("advertencias"):
        partes.append("## Advertencias de la corrida")
        partes.append("")
        for a in d["advertencias"]:
            partes.append(f"- {a}")
        partes.append("")

    partes.append("## 1. Hipótesis contrastada")
    partes.append("")
    partes.append(f"**Enunciado.** {h['enunciado']}")
    partes.append("")
    partes.append(f"**Predicción diferenciadora.** {h['prediccion_diferenciadora']}")
    partes.append("")
    dominio = h.get("dominio") or {}
    partes.append(f"**Dominio de validez.** {dominio.get('descripcion', '—')}")
    if dominio.get("rango"):
        partes.append("")
        partes.append(
            _tabla(
                ["variable", "mínimo", "máximo"],
                [[k, r[0], r[1]] for k, r in dominio["rango"].items()],
            )
        )
    if dominio.get("limitaciones"):
        partes.append("")
        for lim in dominio["limitaciones"]:
            partes.append(f"- Limitación declarada: {lim}")
    partes.append("")

    partes.append("## 2. Baseline convencional")
    partes.append("")
    b = h["baseline"]
    partes.append(f"**`{b['id']}`** — {b['nombre']} v{b['version']}")
    if b.get("supuestos"):
        partes.append("")
        partes.append(f"Supuestos: {b['supuestos']}")
    partes.append("")

    partes.append("## 3. Parámetros")
    partes.append("")
    filas = []
    for p in h["parametros"]:
        ajustado = h["parametros_ajustados"].get(p["nombre"])
        filas.append([
            p["nombre"], p["valor"], p["unidad"],
            "congelado" if p["congelado"] else "libre",
            ajustado if not p["congelado"] else "—",
        ])
    if filas:
        partes.append(_tabla(
            ["parámetro", "valor declarado", "unidad", "estado", "valor ajustado"],
            filas,
        ))
    else:
        partes.append("La hipótesis no declara parámetros.")
    partes.append("")
    partes.append(
        f"El ajuste usó {ds['calibracion']} filas de calibración. "
        f"Las {ds['reservado']} filas reservadas no participaron en el ajuste."
    )
    partes.append("")

    partes.append("## 4. Datos y procedencia")
    partes.append("")
    partes.append(_tabla(
        ["campo", "valor"],
        [
            ["dataset", f"`{ds['id']}`"],
            ["filas", ds["filas"]],
            ["calibración / reservado", f"{ds['calibracion']} / {ds['reservado']}"],
            ["origen", ds["origen"]],
            ["generado por", ds["generado_por"]],
            ["SHA-256", f"`{ds['sha256']}`"],
            ["integridad", "verificada" if ds["integridad"] else "NO VERIFICADA"],
            ["descripción", ds["descripcion"]],
        ],
    ))
    partes.append("")

    partes.append("## 5. Comparación con el baseline")
    partes.append("")
    partes.append(_tabla(
        ["conjunto", "error hipótesis", "error baseline", "métrica"],
        [
            ["calibración", comp["error_calibracion"].get("hipotesis"),
             comp["error_calibracion"].get("baseline"), h["metrica"]],
            ["reservado", comp["error_reservado"].get("hipotesis"),
             comp["error_reservado"].get("baseline"), h["metrica"]],
        ],
    ))
    partes.append("")
    i = comp["intervalo"]
    partes.append(
        f"**Mejora relativa en reservado:** {_fmt(i['mejora'], 4)} "
        f"(IC {int(i['nivel'] * 100)} %: {_fmt(i['ic_inferior'], 4)} a "
        f"{_fmt(i['ic_superior'], 4)}, {i['remuestreos']} remuestreos)."
    )
    partes.append("")
    partes.append(
        f"**Umbral pre-registrado:** {_fmt(h['umbral_mejora'], 4)}. "
        f"**Decisión:** `{comp['decision']['estado']}` — {comp['decision']['motivo']}."
    )
    partes.append("")
    partes.append(
        f"**Diferencia máxima con el baseline:** {_fmt(comp['delta_max_abs'])} "
        f"{h['unidad_observable']} (sensibilidad declarada "
        f"{_fmt(h['umbral_sensibilidad'])} {h['unidad_observable']})."
    )
    partes.append("")

    partes.append("## 6. Matriz de pruebas")
    partes.append("")
    partes.append(_tabla(
        ["código", "prueba", "estado", "detalle"],
        [[p["codigo"], p["titulo"], f"`{p['estado']}`", p["detalle"]]
         for p in d["pruebas"]],
    ))
    partes.append("")

    verificaciones = d.get("verificaciones") or []
    partes.append("### Verificaciones opcionales")
    partes.append("")
    if verificaciones:
        partes.append(
            "Pruebas que el laboratorio puede ejecutar además de las doce del "
            "protocolo. No son vinculantes: amplían el diagnóstico y no cambian "
            "el veredicto. «NO_REQUERIDA» significa que su precondición no se "
            "cumple en esta hipótesis, no que se haya superado."
        )
        partes.append("")
        partes.append(_tabla(
            ["código", "verificación", "estado", "motivo", "resultado"],
            [
                [v["codigo"], v["titulo"], f"`{v['estado']}`",
                 v.get("motivo", ""), v.get("detalle", "")]
                for v in verificaciones
            ],
        ))
    else:
        partes.append("Esta corrida no registró verificaciones opcionales.")
    partes.append("")

    est = d.get("estabilidad") or {}
    if est.get("ensayos"):
        partes.append("## 7. Estabilidad de la conclusión")
        partes.append("")
        partes.append(
            f"Se repitió la comparación con {len(est['ensayos'])} particiones "
            "alternativas (40 % reservado cada una)."
        )
        partes.append("")
        partes.append(_tabla(
            ["partición", "semilla", "error hipótesis", "error baseline",
             "mejora", "¿alcanza el umbral?"],
            [[e["particion"], e["semilla"], e.get("error_hipotesis"),
              e.get("error_baseline"), _fmt(e.get("mejora"), 4),
              e.get("alcanza_umbral")] for e in est["ensayos"]],
        ))
        partes.append("")
        partes.append(
            f"Mejora mínima {_fmt(est['mejora_minima'], 4)}, máxima "
            f"{_fmt(est['mejora_maxima'], 4)}, media {_fmt(est['mejora_media'], 4)}. "
            f"Alcanza el umbral en {est['fraccion_alcanza_umbral']:.0%} de las particiones."
        )
        partes.append("")
    else:
        partes.append("## 7. Estabilidad de la conclusión")
        partes.append("")
        partes.append("No se ejecutaron particiones alternativas o ninguna fue válida.")
        partes.append("")

    c = d.get("control_nulo") or {}
    partes.append("## 8. Control nulo")
    partes.append("")
    if c.get("error"):
        partes.append(f"No se pudo ejecutar: {c['error']}")
    else:
        partes.append(
            "Se generaron datos sintéticos con el **baseline** como verdad y ruido "
            f"σ = {_fmt(c.get('sigma_usado'))} (presupuesto de incertidumbre "
            "declarado por la hipótesis; si no consta, el ruido del dataset), y se "
            "repitió el procedimiento completo. Una hipótesis que gana aquí está "
            "explotando el diseño, no un fenómeno."
        )
        partes.append("")
        partes.append(_tabla(
            ["campo", "valor"],
            [
                ["mejora sobre datos nulos", _fmt(c.get("mejora"), 4)],
                ["IC inferior", _fmt(c.get("ic_inferior"), 4)],
                ["IC superior", _fmt(c.get("ic_superior"), 4)],
                ["umbral exigido", _fmt(h["umbral_mejora"], 4)],
            ],
        ))
    partes.append("")

    pr = d.get("preregistro") or {}
    partes.append("## 9. Preregistro")
    partes.append("")
    partes.append(_tabla(
        ["campo", "valor"],
        [
            ["existe sello", pr.get("existe")],
            ["coincide con la firma actual", pr.get("coincide")],
            ["creado durante la evaluación (tardío)", pr.get("tardio")],
            ["firma en el sello", pr.get("firma_en_sello")],
            ["firma actual", pr.get("firma_actual")],
            ["creado (UTC)", pr.get("creado_utc")],
        ],
    ))
    partes.append("")

    r = d.get("reproducibilidad") or {}
    partes.append("## 10. Reproducibilidad")
    partes.append("")
    partes.append(_tabla(
        ["comprobación", "resultado"],
        [
            ["predicción idéntica en dos ejecuciones", r.get("prediccion_identica")],
            ["bootstrap idéntico con la misma semilla", r.get("bootstrap_identico")],
            ["SHA-256 de la predicción", f"`{r.get('sha_prediccion_1')}`"],
        ],
    ))
    partes.append("")

    partes.append("## 11. Qué no demuestra este informe")
    partes.append("")
    partes.append(
        "1. **No demuestra la hipótesis.** Una corroboración provisional es "
        "compatible con explicaciones alternativas y con el azar del diseño."
    )
    partes.append(
        "2. **No es replicación independiente.** Los datos y el código se "
        "ejecutaron una vez, en un solo entorno."
    )
    partes.append(
        "3. **No valida el baseline como verdad física.** El baseline es el "
        "modelo convencional de referencia, con sus propios supuestos."
    )
    partes.append(
        "4. **No extrapola fuera del dominio declarado** en la sección 1."
    )
    partes.append(
        "5. **No convierte un `PENDIENTE` en aprobación.** Un estado pendiente "
        "significa falta de evidencia."
    )
    partes.append("")

    partes.append("## 12. Cómo reproducir esta corrida")
    partes.append("")
    partes.append("```powershell")
    partes.append(f"lab preregistrar --id {h['id']}")
    partes.append(f"lab ejecutar --id {h['id']}")
    partes.append("```")
    partes.append("")
    ent = d["entorno"]
    partes.append(_tabla(
        ["entorno", "valor"],
        [
            ["Python", ent["python"]],
            ["NumPy", ent["numpy"]],
            ["plataforma", ent["plataforma"]],
            ["archivo de la hipótesis", ent["archivo_hipotesis"]],
            ["SHA-256 de la hipótesis", f"`{ent['sha256_hipotesis']}`"],
        ],
    ))
    partes.append("")

    return "\n".join(partes) + "\n"


def resumen_consola(resultado: "ResultadoEvaluacion", ancho: int = 78) -> str:
    """Resumen compacto para terminal."""
    d = resultado.datos
    v = d["veredicto"]
    h = d["hipotesis"]
    lineas = ["=" * ancho]
    lineas.append(f"{EMBLEMA.get(v['estado'], v['estado'])}")
    lineas.append(f"Hipótesis: {h['id']} v{h['version']} — {h['nombre']}")
    lineas.append(f"Motivo:    {v['motivo']}")
    lineas.append("-" * ancho)
    for p in d["pruebas"]:
        marca = {
            "APROBADO": "OK  ",
            "FALLIDO": "FALLA",
            "PENDIENTE": "PEND ",
            "NO_APLICABLE": "N/A ",
            "NO_PRESENTADA": "N/P ",
            "SENSIBLE_AL_DISENO": "SENS",
        }.get(p["estado"], "?   ")
        lineas.append(f"  {p['codigo']} {marca} {p['detalle'][:58]}")
    lineas.append("-" * ancho)
    comp = d["comparacion"]
    i = comp["intervalo"]
    lineas.append(
        f"Mejora en reservado: {i['mejora']:+.4f} "
        f"(IC: {i['ic_inferior']:+.4f} a {i['ic_superior']:+.4f})"
    )
    lineas.append(
        f"Error reservado: hipótesis {comp['error_reservado'].get('hipotesis'):.6g} "
        f"vs baseline {comp['error_reservado'].get('baseline'):.6g}"
    )
    lineas.append("=" * ancho)
    return "\n".join(lineas)
