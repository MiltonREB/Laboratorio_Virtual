"""Catálogo de pruebas: las que siempre corren y las que sólo a veces hacen falta.

El protocolo tiene doce pruebas fijas. Algunas no siempre se pueden o se
deben ejecutar: una hipótesis sin parámetros libres no tiene calibración que
aislar (T05), y una sin datos externos no puede pasar por un holdout (O04).
Este módulo declara esa condición **antes** de mirar el resultado y la deja
escrita con su motivo, para que «no se ejecutó» nunca se lea como «salió bien».

Distingue dos familias:

* ``PRUEBAS_PROTOCOLO`` (T01–T12): vinculantes; forman el veredicto.
* ``VERIFICACIONES_OPCIONALES`` (O01–O05): informativas; amplían el diagnóstico
  y **no** cambian el veredicto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np

from . import metricas


# --------------------------------------------------------------------------
# Metadatos del catálogo
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Definicion:
    """Descripción de una prueba del catálogo."""

    codigo: str
    titulo: str
    proposito: str
    #: Cuándo legítimamente no se ejecuta (texto para el panel).
    no_requerida_cuando: str
    vinculante: bool = True

    def como_dict(self) -> dict[str, Any]:
        return {
            "codigo": self.codigo,
            "titulo": self.titulo,
            "proposito": self.proposito,
            "no_requerida_cuando": self.no_requerida_cuando,
            "vinculante": self.vinculante,
        }


#: Las doce pruebas del protocolo, con la condición que las hace inaplicables.
PRUEBAS_PROTOCOLO: tuple[Definicion, ...] = (
    Definicion(
        "T01", "Formalización del contrato",
        "Comprueba que la hipótesis declare enunciado, dominio, unidades, "
        "baseline, métrica y umbrales.",
        "Nunca: sin metadatos no hay evaluación posible.",
    ),
    Definicion(
        "T02", "Falsabilidad de la predicción",
        "Comprueba que exista una predicción numérica finita y variable que "
        "podría ser falsa.",
        "Nunca: es la condición de posibilidad de todo lo demás.",
    ),
    Definicion(
        "T03", "Predicción diferenciadora",
        "Comprueba que la hipótesis prediga algo distinto del baseline por "
        "encima de la sensibilidad declarada.",
        "Nunca se omite, pero puede quedar en PENDIENTE si ΔO es nulo o no "
        "distinguible: eso también es un resultado.",
    ),
    Definicion(
        "T04", "Preregistro",
        "Verifica el sello SHA-256 de parámetros, umbrales, métrica y semilla.",
        "Nunca, pero sin sello devuelve PENDIENTE en lugar de inventar uno.",
    ),
    Definicion(
        "T05", "Calibración restringida",
        "Comprueba que los parámetros libres se ajusten sólo con la muestra "
        "de calibración.",
        "Cuando la hipótesis no declara parámetros libres: no hay ajuste que "
        "aislar y la prueba se cumple de forma vacua (se marca como tal).",
    ),
    Definicion(
        "T06", "Validación fuera de muestra",
        "Comprueba que el modelo generalice sobre las filas reservadas.",
        "Nunca: reservado vacío o error no finito cuentan como fallo.",
    ),
    Definicion(
        "T07", "Comparación con el baseline",
        "Mide la mejora relativa frente al modelo convencional y exige que el "
        "IC 95 % excluya el cero.",
        "Nunca: es la prueba central del protocolo.",
    ),
    Definicion(
        "T08", "Estabilidad ante el diseño",
        "Repite la comparación con particiones alternativas y detecta si el "
        "signo de la mejora depende de la división de los datos.",
        "Si se piden cero particiones alternativas: no hay con qué medir la "
        "estabilidad y devuelve PENDIENTE.",
    ),
    Definicion(
        "T09", "Reproducibilidad numérica",
        "Ejecuta dos veces la predicción y el bootstrap y compara los bytes.",
        "Nunca.",
    ),
    Definicion(
        "T10", "Presupuesto de incertidumbre",
        "Comprueba que el error observado quepa en la incertidumbre declarada.",
        "Si la hipótesis no declara presupuesto de incertidumbre (NaN): "
        "devuelve PENDIENTE porque no hay contra qué comparar.",
    ),
    Definicion(
        "T11", "Control nulo",
        "Genera datos con el baseline como verdad y comprueba que la hipótesis "
        "no gane por artefacto.",
        "Si no hay escala de ruido declarada ni residual del baseline con el "
        "que sintetizar los datos nulos.",
    ),
    Definicion(
        "T12", "Dominio de validez",
        "Comprueba que todas las filas evaluadas caigan dentro del rango "
        "declarado.",
        "Nunca: sin dominio declarado devuelve FALLIDO.",
    ),
)

#: Verificaciones opcionales: amplían el diagnóstico y no son vinculantes.
VERIFICACIONES_OPCIONALES: tuple[Definicion, ...] = (
    Definicion(
        "O01", "Contraste con un baseline alternativo",
        "Repite la comparación contra cada modelo alternativo declarado por la "
        "hipótesis, para saber si la ventaja depende del baseline elegido. "
        "Vinculante: sin ella el veredicto máximo es PRELIMINAR.",
        "Cuando la hipótesis no declara ``baselines_alternativos``. En ese caso "
        "no hay contraste de robustez y el veredicto máximo es PRELIMINAR.",
        vinculante=True,
    ),
    Definicion(
        "O02", "Validación por bloques del dominio",
        "Parte la muestra reservada en tres bloques de la primera variable y "
        "comprueba que la mejora no se concentre en uno solo.",
        "Cuando no hay al menos 3 bloques de 10 filas reservadas: con menos, "
        "el bloque no es un contraste, es ruido.",
        vinculante=False,
    ),
    Definicion(
        "O03", "Sensibilidad al número de remuestreos",
        "Recalcula el intervalo con 500 y 4000 remuestreos y mide cuánto se "
        "mueve el extremo inferior.",
        "Salvo que se pida con ``--sensibilidad-bootstrap``: duplica el coste "
        "del bootstrap sin cambiar la decisión.",
        vinculante=False,
    ),
    Definicion(
        "O04", "Holdout externo",
        "Repite la comparación sobre un dataset independiente declarado en "
        "``dataset_validacion``. Vinculante: sin ella el veredicto máximo es "
        "PRELIMINAR, y si falla el veredicto es NO_CORROBORADA.",
        "Cuando la hipótesis no declara dataset de validación: reutilizar el "
        "reservado como holdout no sería un contraste externo, y el veredicto "
        "máximo pasa a PRELIMINAR.",
        vinculante=True,
    ),
    Definicion(
        "O05", "Corrección por comparaciones múltiples",
        "Avisa de que varias hipótesis comparten dataset y de que el umbral "
        "debería corregirse por familia de comparaciones.",
        "Cuando sólo una hipótesis usa este dataset: no hay familia que "
        "corregir.",
        vinculante=False,
    ),
)


def definiciones() -> dict[str, Definicion]:
    todas = (*PRUEBAS_PROTOCOLO, *VERIFICACIONES_OPCIONALES)
    return {d.codigo: d for d in todas}


# --------------------------------------------------------------------------
# Opciones de la corrida
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class OpcionesVerificacion:
    """Qué verificaciones opcionales se piden explícitamente."""

    sensibilidad_bootstrap: bool = False
    hipotesis_mismo_dataset: int = 0
    manifiesto: Any = None

    def como_dict(self) -> dict[str, Any]:
        return {
            "sensibilidad_bootstrap": self.sensibilidad_bootstrap,
            "hipotesis_mismo_dataset": self.hipotesis_mismo_dataset,
            "manifiesto_disponible": self.manifiesto is not None,
        }


# --------------------------------------------------------------------------
# Resultado
# --------------------------------------------------------------------------


@dataclass
class ResultadoVerificacion:
    codigo: str
    titulo: str
    estado: str  # "EJECUTADA" | "PENDIENTE" | "NO_REQUERIDA"
    motivo: str
    detalle: str = ""
    evidencia: Mapping[str, Any] = field(default_factory=dict)
    vinculante: bool = False

    @property
    def ejecutada(self) -> bool:
        return self.estado == "EJECUTADA"

    def como_dict(self) -> dict[str, Any]:
        return {
            "codigo": self.codigo,
            "titulo": self.titulo,
            "estado": self.estado,
            "ejecutada": self.ejecutada,
            "vinculante": self.vinculante,
            "motivo": self.motivo,
            "detalle": self.detalle,
            "evidencia": dict(self.evidencia),
        }


# --------------------------------------------------------------------------
# Ejecución
# --------------------------------------------------------------------------


def ejecutar(
    contexto,
    opciones: OpcionesVerificacion | None = None,
) -> list[ResultadoVerificacion]:
    """Ejecuta las verificaciones opcionales cuyas precondiciones se cumplen."""
    op = opciones or OpcionesVerificacion()
    resultados = [
        _o01_baseline_alternativo(contexto),
        _o02_bloques(contexto),
        _o03_bootstrap(contexto, op),
        _o04_holdout(contexto, op),
        _o05_multiples(contexto, op),
    ]
    catalogo = definiciones()
    for resultado in resultados:
        resultado.vinculante = catalogo[resultado.codigo].vinculante
    return resultados


def _no_requerida(codigo: str, motivo: str, detalle: str = "") -> ResultadoVerificacion:
    definicion = definiciones()[codigo]
    return ResultadoVerificacion(
        codigo=codigo,
        titulo=definicion.titulo,
        estado="NO_REQUERIDA",
        motivo=motivo,
        detalle=detalle,
    )


def _o01_baseline_alternativo(contexto) -> ResultadoVerificacion:
    alternativos = tuple(getattr(contexto.hipotesis, "baselines_alternativos", ()) or ())
    if not alternativos:
        return _no_requerida(
            "O01",
            "La hipótesis no declara baselines alternativos; sólo hay un modelo "
            "de referencia contra el que contrastar.",
        )
    resultados = []
    for baseline in alternativos:
        try:
            pred = baseline.predecir(
                contexto.variables_reservado, baseline.valores_iniciales()
            )
            p = np.asarray(pred[contexto.hipotesis.observable_objetivo], dtype=float)
            eb = metricas.aplicar(
                contexto.hipotesis.metrica, p, contexto.observado_reservado
            )
            eh = float(contexto.errores_reservado["hipotesis"])
            resultados.append(
                {
                    "baseline": baseline.id,
                    "error": eb,
                    "mejora": metricas.mejora_relativa(eb, eh),
                }
            )
        except Exception as exc:
            resultados.append({"baseline": baseline.id,
                               "error": f"{type(exc).__name__}: {exc}"})
    validos = [r for r in resultados if isinstance(r.get("error"), float)]
    gana = all(r["mejora"] > 0 for r in validos) if validos else False
    if not validos:
        detalle = "Ningún baseline alternativo produjo una comparación válida."
    else:
        partes = [f"{r['baseline']} {r['mejora']:+.3f}" for r in validos]
        detalle = "Mejora frente a cada baseline alternativo: " + ", ".join(partes) + "."
        pierde = [r["baseline"] for r in validos if r["mejora"] <= 0]
        if pierde:
            detalle += (
                " No supera a " + ", ".join(pierde) + ": frente a ese modelo la "
                "hipótesis no aporta nada, y la ventaja observada puede venir del "
                "ajuste o de lo incompleto del baseline principal."
            )
        else:
            detalle += " Supera a todos los modelos de referencia declarados."
    return ResultadoVerificacion(
        codigo="O01",
        titulo=definiciones()["O01"].titulo,
        estado="EJECUTADA",
        motivo="La hipótesis declara al menos un baseline alternativo.",
        detalle=detalle,
        evidencia={"resultados": resultados, "gana_a_todos": gana},
    )


def _o02_bloques(contexto) -> ResultadoVerificacion:
    variable = contexto.hipotesis.requiere[0] if contexto.hipotesis.requiere else None
    filas = int(contexto.observado_reservado.size)
    if variable is None or variable not in contexto.variables_reservado:
        return _no_requerida(
            "O02", "La hipótesis no declara variables de entrada utilizables."
        )
    if filas < 30:
        return _no_requerida(
            "O02",
            f"Sólo hay {filas} filas reservadas: no alcanzan para 3 bloques de "
            "10 sin que cada bloque sea esencialmente ruido.",
        )
    x = np.asarray(contexto.variables_reservado[variable], dtype=float)
    orden = np.argsort(x)
    tercios = np.array_split(orden, 3)
    if any(t.size < 10 for t in tercios):
        return _no_requerida(
            "O02",
            f"Con {filas} filas reservadas algún tercio queda por debajo de 10 "
            "filas y el bloque no es interpretable.",
        )
    obs = np.asarray(contexto.observado_reservado, dtype=float)
    ph = np.asarray(contexto.pred_hip_reservado, dtype=float)
    pb = np.asarray(contexto.pred_base_reservado, dtype=float)
    bloques = []
    for i, idx in enumerate(tercios, start=1):
        try:
            eh = metricas.aplicar(contexto.hipotesis.metrica, ph[idx], obs[idx])
            eb = metricas.aplicar(contexto.hipotesis.metrica, pb[idx], obs[idx])
            bloques.append(
                {
                    "bloque": i,
                    "filas": int(idx.size),
                    "desde": float(x[idx].min()),
                    "hasta": float(x[idx].max()),
                    "error_hipotesis": eh,
                    "error_baseline": eb,
                    "mejora": metricas.mejora_relativa(eb, eh),
                }
            )
        except Exception as exc:
            bloques.append({"bloque": i, "error": f"{type(exc).__name__}: {exc}"})
    validos = [b for b in bloques if "mejora" in b]
    consistentes = sum(1 for b in validos if b["mejora"] > 0)
    if not validos:
        detalle = "Ningún bloque produjo una comparación válida."
        hallazgo = "SIN_DATOS"
    elif consistentes == len(validos):
        detalle = f"La mejora se mantiene en los {len(validos)} bloques de '{variable}'."
        hallazgo = "CONSISTENTE"
    elif consistentes == 0:
        detalle = f"La mejora desaparece en los {len(validos)} bloques de '{variable}'."
        hallazgo = "NO_REPRODUCE"
    else:
        detalle = (
            f"La mejora aparece en {consistentes} de {len(validos)} bloques de "
            f"'{variable}': depende del tramo del dominio."
        )
        hallazgo = "PARCIAL"
    return ResultadoVerificacion(
        codigo="O02",
        titulo=definiciones()["O02"].titulo,
        estado="EJECUTADA",
        motivo=f"Hay {filas} filas reservadas, suficientes para 3 bloques de 10.",
        detalle=detalle,
        evidencia={"variable": variable, "bloques": bloques, "hallazgo": hallazgo},
    )


def _o03_bootstrap(contexto, opciones: OpcionesVerificacion) -> ResultadoVerificacion:
    if not opciones.sensibilidad_bootstrap:
        return _no_requerida(
            "O03",
            "No se pidió con --sensibilidad-bootstrap: recalcular el intervalo "
            "con otros tamaños duplica el coste sin cambiar la decisión.",
        )
    try:
        a = metricas.bootstrap_mejora(
            contexto.observado_reservado, contexto.pred_hip_reservado,
            contexto.pred_base_reservado, metrica=contexto.hipotesis.metrica,
            remuestreos=500, semilla=contexto.hipotesis.semilla,
        )
        b = metricas.bootstrap_mejora(
            contexto.observado_reservado, contexto.pred_hip_reservado,
            contexto.pred_base_reservado, metrica=contexto.hipotesis.metrica,
            remuestreos=4000, semilla=contexto.hipotesis.semilla,
        )
        deriva = abs(b.inferior - a.inferior)
        return ResultadoVerificacion(
            codigo="O03",
            titulo=definiciones()["O03"].titulo,
            estado="EJECUTADA",
            motivo="Se pidió sensibilidad al bootstrap.",
            detalle=(
                f"IC inferior: {a.inferior:+.4f} con 500 remuestreos y "
                f"{b.inferior:+.4f} con 4000 (deriva {deriva:.4f})."
            ),
            evidencia={
                "ic_inferior_500": a.inferior,
                "ic_inferior_4000": b.inferior,
                "deriva": deriva,
                "estable": bool(deriva < 0.01),
            },
        )
    except Exception as exc:
        return ResultadoVerificacion(
            codigo="O03",
            titulo=definiciones()["O03"].titulo,
            estado="EJECUTADA",
            motivo="Se pidió sensibilidad al bootstrap.",
            detalle=f"No se pudo completar: {type(exc).__name__}: {exc}",
            evidencia={"error": str(exc)},
        )


def _o04_holdout(
    contexto, opciones: OpcionesVerificacion | None = None
) -> ResultadoVerificacion:
    externo = str(getattr(contexto.hipotesis, "dataset_validacion", "") or "")
    if not externo:
        return _no_requerida(
            "O04",
            "La hipótesis no declara un dataset de validación independiente; "
            "reutilizar el reservado no sería un contraste externo.",
        )
    manifiesto = getattr(opciones, "manifiesto", None) if opciones else None
    if manifiesto is None or externo not in getattr(manifiesto, "ids", ()):
        return ResultadoVerificacion(
            codigo="O04",
            titulo=definiciones()["O04"].titulo,
            estado="PENDIENTE",
            motivo=f"La hipótesis declara '{externo}', pero no está en el manifiesto.",
            detalle=(
                "Declarar un holdout que no existe es peor que no declararlo: el "
                "contraste externo no se ejecutó."
            ),
            evidencia={"dataset_validacion": externo, "en_manifiesto": False},
        )
    try:
        h = contexto.hipotesis
        observado_nombre = h.observable_objetivo
        externo_ds = manifiesto.cargar(externo)
        externo_ds.exigir_integridad()
        variables = externo_ds.variables_de(None, h.requiere)
        y = externo_ds.observado(observado_nombre)
        ph = np.asarray(
            h.predecir(variables, contexto.parametros_ajustados)[observado_nombre],
            dtype=float,
        )
        phb = np.asarray(
            h.baseline.predecir(variables, h.baseline.valores_iniciales())[observado_nombre],
            dtype=float,
        )
        eh = metricas.aplicar(h.metrica, ph, y)
        eb = metricas.aplicar(h.metrica, phb, y)
        mejora = metricas.mejora_relativa(eb, eh)
        return ResultadoVerificacion(
            codigo="O04",
            titulo=definiciones()["O04"].titulo,
            estado="EJECUTADA",
            motivo=f"Dataset de validación independiente: '{externo}'.",
            detalle=(
                f"En el holdout externo ({externo_ds.filas} filas) la mejora es "
                f"{mejora:+.4f} (error {eh:.6g} frente a {eb:.6g})."
            ),
            evidencia={
                "dataset_validacion": externo,
                "filas": externo_ds.filas,
                "error_hipotesis": eh,
                "error_baseline": eb,
                "mejora": mejora,
                "supera_baseline": bool(mejora > 0),
            },
        )
    except Exception as exc:
        return ResultadoVerificacion(
            codigo="O04",
            titulo=definiciones()["O04"].titulo,
            estado="PENDIENTE",
            motivo=f"Holdout declarado, pero no se pudo evaluar: {type(exc).__name__}: {exc}",
            evidencia={"dataset_validacion": externo},
        )


def _o05_multiples(contexto, opciones: OpcionesVerificacion) -> ResultadoVerificacion:
    n = int(opciones.hipotesis_mismo_dataset)
    definicion = definiciones()["O05"]
    if n <= 1:
        return _no_requerida(
            "O05",
            "Sólo una hipótesis usa este dataset: no hay familia de "
            "comparaciones que corregir.",
        )
    h = contexto.hipotesis
    alfa_familia = 0.05
    # Umbral de Holm para la comparación más exigente de la familia: α/n.
    nivel_corregido = 1.0 - alfa_familia / n
    try:
        corregido = metricas.bootstrap_mejora(
            contexto.observado_reservado,
            contexto.pred_hip_reservado,
            contexto.pred_base_reservado,
            metrica=h.metrica,
            remuestreos=2000,
            nivel=nivel_corregido,
            semilla=int(h.semilla) + 3,
        )
        umbral = float(h.umbral_mejora or 0.0)
        sobrevive = bool(corregido.inferior > 0.0 and corregido.mejora >= umbral)
        detalle = (
            f"Con α={alfa_familia} repartido entre {n} comparaciones, el IC debe "
            f"calcularse al {nivel_corregido:.1%}: mejora {corregido.mejora:+.4f} "
            f"con IC [{corregido.inferior:+.4f}, {corregido.superior:+.4f}]. "
            + (
                "La conclusión sobrevive a la corrección."
                if sobrevive
                else "La conclusión NO sobrevive: con la familia completa, la "
                     "mejora deja de ser significativa al nivel exigido."
            )
        )
        return ResultadoVerificacion(
            codigo="O05",
            titulo=definicion.titulo,
            estado="EJECUTADA",
            motivo=f"{n} hipótesis comparten el dataset.",
            detalle=detalle,
            evidencia={
                "hipotesis_mismo_dataset": n,
                "alfa_familia": alfa_familia,
                "nivel_corregido": nivel_corregido,
                "mejora": corregido.mejora,
                "ic_inferior_corregido": corregido.inferior,
                "ic_superior_corregido": corregido.superior,
                "sobrevive_correccion": sobrevive,
                "vinculante": False,
            },
        )
    except Exception as exc:
        return ResultadoVerificacion(
            codigo="O05",
            titulo=definicion.titulo,
            estado="PENDIENTE",
            motivo=f"{n} hipótesis comparten el dataset, pero la corrección falló.",
            detalle=f"{type(exc).__name__}: {exc}",
            evidencia={"hipotesis_mismo_dataset": n},
        )
