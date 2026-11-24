"""Informe consolidado: todas las hipótesis en un solo documento.

El panel responde «¿qué pasó con cada hipótesis?». Este informe responde la
pregunta anterior: «si miro el conjunto, ¿qué puedo afirmar y qué no?».

Incluye un aviso que ningún módulo individual puede dar: cuántas corridas
registra cada hipótesis. Reevaluar hasta que salga positiva es la forma más
común de fabricar un resultado, y aquí queda a la vista.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .evaluador import cargar_corridas, ultima_corrida_por_hipotesis
from .protocolo import ORDEN, TITULOS
from .veredicto import DESCRIPCION_VEREDICTO

SIMBOLO = {
    "APROBADO": "ok",
    "FALLIDO": "X",
    "PENDIENTE": "·",
    "SENSIBLE": "sn",
}


def _fmt(valor: Any, decimales: int = 4) -> str:
    if valor is None:
        return "—"
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    if v != v:
        return "—"
    if v == 0:
        return "0"
    if abs(v) < 1e-3 or abs(v) >= 1e5:
        return f"{v:.2e}"
    return f"{v:+.{decimales}f}" if decimales <= 4 and abs(v) < 100 else f"{v:.{decimales}f}"


def _tabla(cabeceras: Sequence[str], filas: Sequence[Sequence[Any]]) -> str:
    lineas = ["| " + " | ".join(cabeceras) + " |"]
    lineas.append("|" + "|".join(["---"] * len(cabeceras)) + "|")
    for fila in filas:
        lineas.append("| " + " | ".join(str(c).replace("\n", " ") for c in fila) + " |")
    return "\n".join(lineas)


def generar_informe(
    raiz_resultados: str | Path,
    destino: str | Path | None = None,
) -> Path:
    """Escribe el informe consolidado y devuelve su ruta."""
    raiz = Path(raiz_resultados)
    corridas = cargar_corridas(raiz)
    ultimas = ultima_corrida_por_hipotesis(raiz)
    intentos = Counter(
        (c.get("hipotesis") or {}).get("id") for c in corridas
        if (c.get("hipotesis") or {}).get("id")
    )

    partes: list[str] = []
    ahora = datetime.now(timezone.utc)
    partes.append("# Informe consolidado del laboratorio")
    partes.append("")
    partes.append(f"**Generado (UTC):** {ahora:%Y-%m-%d %H:%M}  ")
    partes.append(f"**Hipótesis con corrida:** {len(ultimas)}  ")
    partes.append(f"**Corridas registradas:** {len(corridas)}")
    partes.append("")

    if not ultimas:
        partes.append("No hay corridas registradas. Ejecuta `lab ejecutar --todos`.")
        ruta = Path(destino) if destino else raiz / "INFORME_CONSOLIDADO.md"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text("\n".join(partes) + "\n", encoding="utf-8", newline="\n")
        return ruta

    # -- 1. Resumen por hipótesis --------------------------------------
    filas = []
    for id_, c in sorted(ultimas.items()):
        h = c.get("hipotesis") or {}
        v = c.get("veredicto") or {}
        i = (c.get("comparacion") or {}).get("intervalo") or {}
        ds = c.get("dataset") or {}
        filas.append([
            f"`{id_}`",
            f"**{v.get('estado', '—')}**",
            _fmt(i.get("mejora")),
            f"[{_fmt(i.get('ic_inferior'))}, {_fmt(i.get('ic_superior'))}]",
            (c.get("comparacion") or {}).get("ratio_errores_texto") or "—",
            h.get("umbral_mejora"),
            _fmt((c.get("comparacion") or {}).get("error_reservado", {}).get("hipotesis"), 6),
            f"`{ds.get('id')}`",
            intentos.get(id_, 0),
        ])
    partes.append("## 1. Resumen por hipótesis")
    partes.append("")
    partes.append(_tabla(
        ["hipótesis", "veredicto", "mejora", "IC 95 %", "εhip/εbase", "umbral",
         "error reservado", "dataset", "corridas"],
        filas,
    ))
    partes.append("")

    # -- 2. Matriz de pruebas ------------------------------------------
    filas = []
    for id_, c in sorted(ultimas.items()):
        estados = {p["codigo"]: p["estado"] for p in c.get("pruebas", [])}
        filas.append([f"`{id_}`"] + [SIMBOLO.get(estados.get(cod, "PENDIENTE"), "?")
                                     for cod in ORDEN])
    partes.append("## 2. Matriz de pruebas")
    partes.append("")
    partes.append(_tabla(["hipótesis"] + list(ORDEN), filas))
    partes.append("")
    partes.append(
        "Leyenda: ok=aprobado, X=fallido, ·=pendiente, sn=sensible al diseño."
    )
    partes.append("")

    # -- 3. Lo que no se sostiene --------------------------------------
    negativas = [
        (id_, c) for id_, c in sorted(ultimas.items())
        if (c.get("veredicto") or {}).get("estado") != "CORROBORADA_PROVISIONAL"
    ]
    partes.append("## 3. Lo que no se sostiene")
    partes.append("")
    if not negativas:
        partes.append("Ninguna hipótesis quedó sin corroborar.")
    else:
        for id_, c in negativas:
            v = c.get("veredicto") or {}
            partes.append(f"### `{id_}` — {v.get('estado')}")
            partes.append("")
            partes.append(f"{v.get('motivo', '')}")
            partes.append("")
            partes.append(f"_{DESCRIPCION_VEREDICTO.get(v.get('estado'), '')}_")
            partes.append("")
    partes.append("")

    # -- 4. Verificaciones ejecutadas ----------------------------------
    filas = []
    for id_, c in sorted(ultimas.items()):
        for verif in c.get("verificaciones", []) or []:
            if not verif.get("ejecutada"):
                continue
            hallazgo = ""
            evidencia = verif.get("evidencia") or {}
            if "gana_a_todos" in evidencia:
                hallazgo = "gana a todos" if evidencia["gana_a_todos"] else "NO gana a todos"
            elif "hallazgo" in evidencia:
                hallazgo = str(evidencia["hallazgo"])
            elif "sobrevive_correccion" in evidencia:
                hallazgo = ("sobrevive" if evidencia["sobrevive_correccion"]
                            else "NO sobrevive")
            elif "supera_baseline" in evidencia:
                hallazgo = ("supera" if evidencia["supera_baseline"] else "NO supera")
            filas.append([f"`{id_}`", verif["codigo"], hallazgo,
                          verif.get("detalle", "")])
    partes.append("## 4. Verificaciones opcionales ejecutadas")
    partes.append("")
    if filas:
        partes.append(_tabla(["hipótesis", "código", "hallazgo", "resultado"], filas))
    else:
        partes.append("Ninguna verificación opcional llegó a ejecutarse.")
    partes.append("")

    # -- 5. Avisos de familia ------------------------------------------
    por_dataset: dict[str, list[str]] = {}
    for id_, c in sorted(ultimas.items()):
        ds = (c.get("dataset") or {}).get("id")
        if ds:
            por_dataset.setdefault(ds, []).append(id_)
    compartidos = {k: v for k, v in por_dataset.items() if len(v) > 1}

    partes.append("## 5. Avisos de familia y de repetición")
    partes.append("")
    avisos: list[str] = []
    if compartidos:
        for ds, ids in compartidos.items():
            avisos.append(
                f"- **{len(ids)} hipótesis compiten sobre `{ds}`** ({', '.join(ids)}). "
                "El umbral declarado no está corregido por comparaciones múltiples; "
                "la verificación O05 calcula cuánto cambia el intervalo con la "
                "corrección de Holm."
            )
    else:
        avisos.append(
            "- No hay dos hipótesis sobre el mismo dataset, así que no hay familia "
            "de comparaciones que corregir en este conjunto."
        )
    repetidas = {k: v for k, v in intentos.items() if v > 1}
    if repetidas:
        for id_, n in sorted(repetidas.items()):
            avisos.append(
                f"- `{id_}` tiene **{n} corridas registradas**. La tabla muestra la "
                "última; si se eligió entre ellas por su resultado, el veredicto "
                "está sesgado a favor y hay que tratarlo como exploratorio."
            )
    else:
        avisos.append(
            "- Cada hipótesis tiene una sola corrida registrada: no hay selección "
            "posterior al resultado."
        )
    partes.extend(avisos)
    partes.append("")

    # -- 6. Advertencias de esquema ------------------------------------
    incompatibles = [c for c in corridas if not c.get("_esquema_compatible", True)]
    if incompatibles:
        partes.append("## 6. Corridas con esquema distinto")
        partes.append("")
        partes.append(
            f"{len(incompatibles)} corrida(s) se generaron con un esquema de "
            "`resumen.json` que este código no declara compatible. Se muestran, "
            "pero no deben compararse sin revisar la versión."
        )
        partes.append("")

    # -- 7. Límites ----------------------------------------------------
    partes.append("## 7. Qué no dice este informe")
    partes.append("")
    partes.append(
        "1. No agrega evidencia entre hipótesis: cada veredicto vale por sí solo."
    )
    partes.append(
        "2. No corrige por comparaciones múltiples salvo que O05 se haya ejecutado."
    )
    partes.append(
        "3. No convierte una corroboración provisional en demostración."
    )
    partes.append(
        "4. No sustituye la replicación independiente con datos nuevos."
    )
    partes.append("")

    ruta = Path(destino) if destino else raiz / "INFORME_CONSOLIDADO.md"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(partes) + "\n", encoding="utf-8", newline="\n")
    return ruta
