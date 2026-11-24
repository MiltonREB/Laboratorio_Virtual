"""Orquestación de una evaluación completa.

El evaluador no decide nada: calcula el contexto, ejecuta la batería y deja
que :mod:`lab.veredicto` agregue. Toda decisión queda escrita en disco con
los números que la sostienen.
"""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from . import catalogo, metricas, viabilidad
from .contrato import Hipotesis, Modelo, ResultadoPrueba, verificar_salida
from .datos import ConjuntoDatos, ErrorDeDatos, Manifiesto
from .preregistro import Verificacion, diferencias, firmar, sellar, verificar
from .protocolo import ContextoEvaluacion, ejecutar_pruebas
from .registro import Registro
from .veredicto import Veredicto, agregar

#: Versión del protocolo y del paquete.
VERSION_PROTOCOLO = "1.1.0"

#: Separación mínima por defecto entre el sello y la corrida, en segundos.
#: Sellar y evaluar en el mismo instante no acredita anterioridad.
SEPARACION_MINIMA_POR_DEFECTO = 60.0

#: Remuestreos por defecto del bootstrap.
REMUESTREOS_POR_DEFECTO = 2000
#: Particiones alternativas por defecto para T08.
PARTICIONES_POR_DEFECTO = 5

#: Versión del esquema de ``resumen.json``. Se incrementa cuando un campo
#: cambia de significado o desaparece; añadir campos nuevos no obliga.
ESQUEMA_RESUMEN = "1.2"
#: Esquemas que este código sabe leer. 1.1 usaba otro vocabulario de estados,
#: así que no es comparable: se marca en lugar de interpretarse en silencio.
ESQUEMAS_COMPATIBLES: tuple[str, ...] = ("1.2",)


def esquema_compatible(version: object) -> bool:
    """¿Este código puede interpretar un ``resumen.json`` de esa versión?"""
    return str(version) in ESQUEMAS_COMPATIBLES


class ErrorDeEvaluacion(RuntimeError):
    """La hipótesis no se puede evaluar con los datos y el contrato actuales."""


@dataclass
class ResultadoEvaluacion:
    """Todo lo producido por una corrida."""

    hipotesis_id: str
    corrida: Path
    veredicto: Veredicto
    pruebas: list[ResultadoPrueba]
    datos: dict[str, Any] = field(default_factory=dict)

    def como_dict(self) -> dict[str, Any]:
        return dict(self.datos)


# --------------------------------------------------------------------------
# API principal
# --------------------------------------------------------------------------


def evaluar_hipotesis(
    hipotesis: Hipotesis,
    manifiesto: Manifiesto,
    raiz_resultados: str | Path,
    *,
    remuestreos: int = REMUESTREOS_POR_DEFECTO,
    particiones: int = PARTICIONES_POR_DEFECTO,
    guardar: bool = True,
    sellar_si_falta: bool = True,
    sensibilidad_bootstrap: bool = False,
    hipotesis_mismo_dataset: int = 0,
    separacion_minima: float = SEPARACION_MINIMA_POR_DEFECTO,
    exigir_publicacion: bool = False,
) -> ResultadoEvaluacion:
    """Evalúa una hipótesis completa y (por defecto) escribe los artefactos."""
    raiz = Path(raiz_resultados)
    _precondiciones(hipotesis, manifiesto)

    dataset = manifiesto.cargar(hipotesis.dataset_id)
    dataset.exigir_integridad()

    observable = hipotesis.observable_objetivo
    if observable not in dataset.observables:
        raise ErrorDeEvaluacion(
            f"El observable '{observable}' no está en el dataset "
            f"'{dataset.id}' ({', '.join(dataset.observables)})"
        )
    faltantes = [v for v in hipotesis.requiere if v not in dataset.variables]
    if faltantes:
        raise ErrorDeEvaluacion(
            f"Faltan variables requeridas en el dataset: {faltantes}"
        )

    baseline = hipotesis.baseline
    assert baseline is not None  # garantizado por _precondiciones

    # -- preregistro ---------------------------------------------------
    verif = verificar(
        hipotesis,
        raiz,
        separacion_minima=separacion_minima,
        exigir_publicacion=exigir_publicacion,
    )
    advertencias: list[str] = []
    if not verif.existe and sellar_si_falta:
        sellar(hipotesis, raiz, tardio=True)
        verif = verificar(
            hipotesis,
            raiz,
            separacion_minima=separacion_minima,
            exigir_publicacion=exigir_publicacion,
        )
        advertencias.append(
            "No existía sello de preregistro: se creó uno durante la evaluación y "
            "se marca como tardío (T04 no lo aceptará)."
        )
    if verif.existe and verif.estado_preregistro == "RECIENTE":
        advertencias.append(
            "El sello existe pero es más reciente que la separación mínima exigida: "
            "no acredita que los umbrales fueran anteriores a los datos."
        )
    cambios_firma: list[str] = []
    if verif.estado_preregistro == "ALTERADO":
        from .preregistro import ultimo_sello

        previo = ultimo_sello(raiz, hipotesis.id)
        if previo is not None:
            cambios_firma = diferencias(previo.firma, hipotesis.firma_de_parametros())

    # -- datos ---------------------------------------------------------
    vars_cal = dataset.variables_de(dataset.calibracion, hipotesis.requiere)
    vars_res = dataset.variables_de(dataset.reservado, hipotesis.requiere)
    y_cal = dataset.observado(observable, dataset.calibracion)
    y_res = dataset.observado(observable, dataset.reservado)

    sigma = dataset.sigma(observable) if hipotesis.metrica == "chi2_reducido" else None

    # -- ajuste y predicción -------------------------------------------
    parametros_declarados = hipotesis.valores_iniciales()
    parametros_ajustados = dict(hipotesis.ajustar(vars_cal, y_cal, parametros_declarados))
    ajuste_usado = any(
        not np.isclose(
            float(parametros_ajustados.get(p.nombre, np.nan)),
            float(p.valor),
            rtol=0.0,
            atol=1e-15,
        )
        for p in hipotesis.parametros()
        if not p.congelado
    )

    pred_hip_cal = _predecir(hipotesis, vars_cal, parametros_ajustados, observable, y_cal.size, "calibración")
    pred_hip_res = _predecir(hipotesis, vars_res, parametros_ajustados, observable, y_res.size, "reservado")
    pred_base_cal = _predecir(baseline, vars_cal, baseline.valores_iniciales(), observable, y_cal.size, "baseline/calibración")
    pred_base_res = _predecir(baseline, vars_res, baseline.valores_iniciales(), observable, y_res.size, "baseline/reservado")

    # -- errores y comparación -----------------------------------------
    errores_cal = _errores(hipotesis.metrica, y_cal, pred_hip_cal, pred_base_cal, sigma)
    errores_res = _errores(hipotesis.metrica, y_res, pred_hip_res, pred_base_res, sigma)

    intervalo = metricas.bootstrap_mejora(
        y_res,
        pred_hip_res,
        pred_base_res,
        metrica=hipotesis.metrica,
        remuestreos=remuestreos,
        semilla=hipotesis.semilla,
        sigma=sigma,
        devolver_muestras=True,
    )
    umbral = float(hipotesis.umbral_mejora or 0.0)
    decision = metricas.decidir_mejora(intervalo, umbral)

    # -- estabilidad de diseño -----------------------------------------
    estabilidad = _estabilidad(
        hipotesis, dataset, observable, particiones, umbral
    )

    # -- control nulo ---------------------------------------------------
    control = _control_nulo(hipotesis, dataset, observable, remuestreos)

    # -- reproducibilidad ----------------------------------------------
    reproducibilidad = _reproducibilidad(
        hipotesis, vars_res, parametros_ajustados, observable,
        y_res, pred_base_res, remuestreos, sigma,
    )
    reproducibilidad["cambios_firma"] = cambios_firma

    ctx = ContextoEvaluacion(
        hipotesis=hipotesis,
        dataset=dataset,
        baseline=baseline,
        parametros_declarados=parametros_declarados,
        parametros_ajustados=parametros_ajustados,
        ajuste_usado=ajuste_usado,
        variables_calibracion=vars_cal,
        variables_reservado=vars_res,
        observado_calibracion=y_cal,
        observado_reservado=y_res,
        pred_hip_calibracion=pred_hip_cal,
        pred_base_calibracion=pred_base_cal,
        pred_hip_reservado=pred_hip_res,
        pred_base_reservado=pred_base_res,
        errores_calibracion=errores_cal,
        errores_reservado=errores_res,
        intervalo_reservado=intervalo,
        decision_baseline=decision,
        verificacion=verif,
        estabilidad=estabilidad,
        control_nulo=control,
        reproducibilidad=reproducibilidad,
        advertencias=advertencias,
    )

    # -- viabilidad y batería ------------------------------------------
    # Los avisos se calculan antes de ejecutar las pruebas: no cambian el
    # veredicto, pero deben estar disponibles antes de leer los resultados.
    avisos_viabilidad = viabilidad.evaluar(
        hipotesis, dataset, verif, error_baseline=errores_res.get("baseline")
    )

    pruebas = ejecutar_pruebas(ctx)
    verificaciones = catalogo.ejecutar(
        ctx,
        catalogo.OpcionesVerificacion(
            sensibilidad_bootstrap=sensibilidad_bootstrap,
            hipotesis_mismo_dataset=hipotesis_mismo_dataset,
            manifiesto=manifiesto,
        ),
    )
    veredicto = agregar(pruebas, verificaciones)

    corrida = _carpeta_corrida(raiz, hipotesis.id) if guardar else Path()
    datos = _resumen(
        hipotesis=hipotesis,
        dataset=dataset,
        baseline=baseline,
        contexto=ctx,
        pruebas=pruebas,
        veredicto=veredicto,
        intervalo=intervalo,
        decision=decision,
        verif=verif,
        estabilidad=estabilidad,
        control=control,
        reproducibilidad=reproducibilidad,
        parametros_declarados=parametros_declarados,
        parametros_ajustados=parametros_ajustados,
        ajuste_usado=ajuste_usado,
        corrida=corrida,
        advertencias=advertencias,
        remuestreos=remuestreos,
        particiones=particiones,
        verificaciones=verificaciones,
        viabilidad=avisos_viabilidad,
    )

    resultado = ResultadoEvaluacion(hipotesis.id, corrida, veredicto, pruebas, datos)
    if guardar:
        _escribir_artefactos(resultado, ctx, dataset)
    return resultado


# --------------------------------------------------------------------------
# Piezas
# --------------------------------------------------------------------------


def _precondiciones(h: Hipotesis, manifiesto: Manifiesto) -> None:
    problemas: list[str] = []
    if h.baseline is None:
        problemas.append("no declara 'baseline'")
    if not h.dataset_id:
        problemas.append("no declara 'dataset_id'")
    elif not manifiesto.contiene(h.dataset_id):
        problemas.append(
            f"dataset '{h.dataset_id}' no existe en el manifiesto "
            f"({', '.join(manifiesto.ids)})"
        )
    if not h.observable_objetivo:
        problemas.append("no declara 'observable_objetivo'")
    if h.metrica not in metricas.FUNCIONES:
        problemas.append(f"métrica '{h.metrica}' no admitida")
    if problemas:
        raise ErrorDeEvaluacion(
            f"La hipótesis '{h.id}' no se puede evaluar: " + "; ".join(problemas)
        )


def _predecir(
    modelo: Modelo,
    variables: Mapping[str, np.ndarray],
    parametros: Mapping[str, float],
    observable: str,
    filas: int,
    etiqueta: str,
) -> np.ndarray:
    try:
        salida = modelo.predecir(variables, parametros)
    except Exception as exc:
        raise ErrorDeEvaluacion(
            f"El modelo '{modelo.id}' falló al predecir ({etiqueta}): "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    errores = verificar_salida(salida, (observable,), filas)
    if errores:
        raise ErrorDeEvaluacion(
            f"Salida inválida de '{modelo.id}' en {etiqueta}: " + "; ".join(errores)
        )
    return np.asarray(salida[observable], dtype=float)


def _errores(
    metrica: str,
    observado: np.ndarray,
    pred_hip: np.ndarray,
    pred_base: np.ndarray,
    sigma: float | np.ndarray | None,
) -> dict[str, float]:
    return {
        "hipotesis": metricas.aplicar(metrica, pred_hip, observado, sigma),
        "baseline": metricas.aplicar(metrica, pred_base, observado, sigma),
    }


def _estabilidad(
    h: Hipotesis,
    dataset: ConjuntoDatos,
    observable: str,
    particiones: int,
    umbral: float,
) -> dict[str, Any]:
    """Recalcula la comparación con particiones distintas de la declarada."""
    ensayos: list[dict[str, Any]] = []
    for k in range(int(particiones)):
        semilla = int(h.semilla) + 1000 * (k + 1)
        cal, res = dataset.con_particion(semilla, fraccion_reservado=0.4)
        vars_cal = dataset.variables_de(cal, h.requiere)
        vars_res = dataset.variables_de(res, h.requiere)
        y_cal = dataset.observado(observable, cal)
        y_res = dataset.observado(observable, res)
        try:
            params = h.ajustar(vars_cal, y_cal, h.valores_iniciales())
            ph = _predecir(h, vars_res, params, observable, y_res.size, f"estabilidad-{k}")
            assert h.baseline is not None
            pb = _predecir(
                h.baseline, vars_res, h.baseline.valores_iniciales(),
                observable, y_res.size, f"estabilidad-base-{k}",
            )
            eb = metricas.aplicar(h.metrica, pb, y_res)
            eh = metricas.aplicar(h.metrica, ph, y_res)
            mejora = metricas.mejora_relativa(eb, eh)
            ensayos.append(
                {
                    "particion": k,
                    "semilla": semilla,
                    "filas_calibracion": len(cal),
                    "filas_reservado": len(res),
                    "error_hipotesis": eh,
                    "error_baseline": eb,
                    "mejora": mejora,
                    "alcanza_umbral": bool(mejora >= umbral),
                }
            )
        except Exception as exc:
            ensayos.append(
                {
                    "particion": k,
                    "semilla": semilla,
                    "mejora": float("nan"),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    validos = [e for e in ensayos if np.isfinite(e.get("mejora", float("nan")))]
    if not validos:
        return {"ensayos": [], "error": "ninguna partición produjo una mejora finita"}
    mejoras = [float(e["mejora"]) for e in validos]
    return {
        "ensayos": validos,
        "mejora_minima": min(mejoras),
        "mejora_maxima": max(mejoras),
        "mejora_media": float(np.mean(mejoras)),
        "desviacion": float(np.std(mejoras, ddof=1)) if len(mejoras) > 1 else 0.0,
        "fraccion_alcanza_umbral": float(
            np.mean([bool(e["alcanza_umbral"]) for e in validos])
        ),
        "umbral_mejora": umbral,
    }


def _control_nulo(
    h: Hipotesis,
    dataset: ConjuntoDatos,
    observable: str,
    remuestreos: int,
) -> dict[str, Any]:
    """Datos generados por el baseline: la hipótesis no debe ganar aquí."""
    try:
        sigma = float(h.incertidumbre_declarada)
        if not np.isfinite(sigma) or sigma <= 0:
            sigma = float(dataset.ruido.get(observable, 0.0))
        if not np.isfinite(sigma) or sigma <= 0:
            resid = dataset.observado(observable) - _predecir(
                h.baseline, dataset.variables_de(None, h.requiere),
                h.baseline.valores_iniciales(), observable, dataset.filas,
                "control-nulo-base",
            )
            sigma = float(np.std(resid))
        if not np.isfinite(sigma) or sigma <= 0:
            return {"error": "no hay escala de ruido declarada ni residual del baseline"}

        rng = np.random.default_rng(int(h.semilla) * 7919 + 13)
        vars_todas = dataset.variables_de(None, h.requiere)
        base_todas = _predecir(
            h.baseline, vars_todas, h.baseline.valores_iniciales(),
            observable, dataset.filas, "control-nulo-completo",
        )
        y_nulo = base_todas + rng.normal(0.0, sigma, size=base_todas.size)

        cal, res = dataset.calibracion, dataset.reservado
        vars_cal = {k: v[list(cal)] for k, v in vars_todas.items()}
        vars_res = {k: v[list(res)] for k, v in vars_todas.items()}
        y_cal_nulo = y_nulo[list(cal)]
        y_res_nulo = y_nulo[list(res)]
        base_res = base_todas[list(res)]

        params = h.ajustar(vars_cal, y_cal_nulo, h.valores_iniciales())
        pred = _predecir(h, vars_res, params, observable, y_res_nulo.size, "control-nulo-hipotesis")
        eb = metricas.aplicar(h.metrica, base_res, y_res_nulo)
        eh = metricas.aplicar(h.metrica, pred, y_res_nulo)
        intervalo = metricas.bootstrap_mejora(
            y_res_nulo, pred, base_res,
            metrica=h.metrica, remuestreos=remuestreos,
            semilla=int(h.semilla) + 1,
        )
        return {
            "sigma_usado": sigma,
            "mejora": intervalo.mejora,
            "ic_inferior": intervalo.inferior,
            "ic_superior": intervalo.superior,
            "error_baseline": eb,
            "error_hipotesis": eh,
            "filas_calibracion": len(cal),
            "filas_reservado": len(res),
            "exitos_bootstrap": intervalo.exitos,
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _reproducibilidad(
    h: Hipotesis,
    vars_res: Mapping[str, np.ndarray],
    parametros: Mapping[str, float],
    observable: str,
    y_res: np.ndarray,
    pred_base_res: np.ndarray,
    remuestreos: int,
    sigma: float | np.ndarray | None,
) -> dict[str, Any]:
    p1 = _predecir(h, vars_res, parametros, observable, y_res.size, "repro-1")
    p2 = _predecir(h, vars_res, parametros, observable, y_res.size, "repro-2")
    s1 = hashlib.sha256(np.ascontiguousarray(p1, dtype="<f8").tobytes()).hexdigest()
    s2 = hashlib.sha256(np.ascontiguousarray(p2, dtype="<f8").tobytes()).hexdigest()

    def _intervalo():
        i = metricas.bootstrap_mejora(
            y_res, p1, pred_base_res, metrica=h.metrica,
            remuestreos=max(200, min(remuestreos, 500)),
            semilla=h.semilla, sigma=sigma,
        )
        return firmar({"m": i.mejora, "l": i.inferior, "u": i.superior})

    b1, b2 = _intervalo(), _intervalo()
    return {
        "prediccion_identica": bool(s1 == s2),
        "bootstrap_identico": bool(b1 == b2),
        "sha_prediccion_1": s1,
        "sha_prediccion_2": s2,
        "sha_bootstrap_1": b1,
        "sha_bootstrap_2": b2,
        "punto_de_igualdad": bool(np.array_equal(p1, p2)),
    }


# --------------------------------------------------------------------------
# Artefactos
# --------------------------------------------------------------------------


def _carpeta_corrida(raiz: Path, id_: str) -> Path:
    marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = raiz / f"{id_}_{marca}"
    destino = base
    n = 2
    while destino.exists():
        destino = raiz / f"{id_}_{marca}_{n:02d}"
        n += 1
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def _histograma(muestras: Sequence[float], bins: int = 36) -> dict[str, Any]:
    """Histograma compacto de la distribución bootstrap (para graficarla)."""
    valores = [float(v) for v in muestras if np.isfinite(v)]
    if not valores:
        return {"bordes": [], "cuentas": []}
    datos, bordes = np.histogram(np.asarray(valores), bins=bins)
    return {
        "bordes": [float(b) for b in bordes],
        "cuentas": [int(c) for c in datos],
    }


def _entorno(h: Hipotesis) -> dict[str, Any]:
    import inspect

    try:
        archivo = inspect.getfile(type(h))
        sha = hashlib.sha256(Path(archivo).read_bytes()).hexdigest()
    except (OSError, TypeError):
        archivo, sha = None, None
    return {
        "python": sys.version.split()[0],
        "plataforma": platform.platform(),
        "numpy": np.__version__,
        "archivo_hipotesis": archivo,
        "sha256_hipotesis": sha,
        "clase": type(h).__name__,
        "utc": datetime.now(timezone.utc).isoformat(),
    }


def _resumen(**kw: Any) -> dict[str, Any]:
    h: Hipotesis = kw["hipotesis"]
    dataset: ConjuntoDatos = kw["dataset"]
    ctx: ContextoEvaluacion = kw["contexto"]
    veredicto: Veredicto = kw["veredicto"]
    intervalo: metricas.Intervalo = kw["intervalo"]
    decision: metricas.Decision = kw["decision"]
    verif: Verificacion = kw["verif"]
    eh = ctx.errores_reservado.get("hipotesis")
    eb = ctx.errores_reservado.get("baseline")
    ratio = metricas.ratio_errores(float(eh), float(eb)) if (
        eh is not None and eb is not None
    ) else None
    return {
        "schema_version": ESQUEMA_RESUMEN,
        "version_laboratorio": VERSION_PROTOCOLO,
        "version_protocolo": VERSION_PROTOCOLO,
        "hipotesis": {
            "id": h.id,
            "nombre": h.nombre,
            "version": h.version,
            "enunciado": h.enunciado,
            "prediccion_diferenciadora": h.prediccion_diferenciadora,
            "observable_objetivo": h.observable_objetivo,
            "unidad_observable": h.unidad_observable,
            "metrica": h.metrica,
            "umbral_mejora": h.umbral_mejora,
            "umbral_sensibilidad": h.umbral_sensibilidad,
            "incertidumbre_declarada": (
                None if not np.isfinite(h.incertidumbre_declarada)
                else float(h.incertidumbre_declarada)
            ),
            "semilla": h.semilla,
            "dominio": (
                {
                    "descripcion": h.dominio.descripcion,
                    "rango": {k: list(v) for k, v in h.dominio.rango.items()},
                    "limitaciones": list(h.dominio.limitaciones),
                }
                if h.dominio else None
            ),
            "parametros": [p.como_dict() for p in h.parametros()],
            "parametros_declarados": kw["parametros_declarados"],
            "parametros_ajustados": kw["parametros_ajustados"],
            "ajuste_usado": kw["ajuste_usado"],
            "baseline": {
                "id": kw["baseline"].id,
                "nombre": kw["baseline"].nombre,
                "version": kw["baseline"].version,
                "supuestos": kw["baseline"].supuestos,
                "parametros": [p.como_dict() for p in kw["baseline"].parametros()],
            },
        },
        "dataset": dataset.resumen(),
        "comparacion": {
            "intervalo": intervalo.como_dict(),
            "histograma_bootstrap": _histograma(intervalo.muestras),
            "decision": {"estado": decision.estado, "motivo": decision.motivo},
            "error_calibracion": ctx.errores_calibracion,
            "error_reservado": ctx.errores_reservado,
            "ratio_errores": ratio,
            "ratio_errores_texto": metricas.formatear_ratio(ratio),
            "delta_max_abs": float(np.max(np.abs(ctx.delta_reservado)))
            if ctx.delta_reservado.size else None,
        },
        "estabilidad": kw["estabilidad"],
        "control_nulo": kw["control"],
        "reproducibilidad": kw["reproducibilidad"],
        "preregistro": verif.como_dict(),
        "pruebas": [p.como_dict() for p in kw["pruebas"]],
        "verificaciones": [v.como_dict() for v in kw["verificaciones"]],
        "viabilidad": [a.como_dict() for a in kw["viabilidad"]],
        "veredicto": veredicto.como_dict(),
        "advertencias": list(kw["advertencias"]),
        "configuracion": {
            "remuestreos_bootstrap": kw["remuestreos"],
            "particiones_alternativas": kw["particiones"],
        },
        "entorno": _entorno(h),
        "corrida": str(kw["corrida"]),
    }


def _escribir_artefactos(
    resultado: ResultadoEvaluacion, ctx: ContextoEvaluacion, dataset: ConjuntoDatos
) -> None:
    from .informe import informe_markdown

    carpeta = resultado.corrida
    (carpeta / "resumen.json").write_text(
        json.dumps(resultado.datos, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with open(carpeta / "matriz.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["codigo", "titulo", "estado", "detalle"])
        for p in resultado.pruebas:
            w.writerow([p.codigo, p.titulo, p.estado, p.detalle])

    with open(carpeta / "predicciones.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(
            ["fila", "particion", "observado", "prediccion_hipotesis",
             "prediccion_baseline", "residuo_hipotesis", "delta_vs_baseline"]
        )
        for etiqueta, indices, y, ph, pb in (
            ("calibracion", dataset.calibracion, ctx.observado_calibracion,
             ctx.pred_hip_calibracion, ctx.pred_base_calibracion),
            ("reservado", dataset.reservado, ctx.observado_reservado,
             ctx.pred_hip_reservado, ctx.pred_base_reservado),
        ):
            for i, fila in enumerate(indices):
                w.writerow([
                    int(fila), etiqueta, float(y[i]), float(ph[i]), float(pb[i]),
                    float(y[i] - ph[i]), float(ph[i] - pb[i]),
                ])

    (carpeta / "INFORME.md").write_text(
        informe_markdown(resultado), encoding="utf-8", newline="\n"
    )


# --------------------------------------------------------------------------
# Lectura de corridas previas (usada por el panel y por ``lab estado``)
# --------------------------------------------------------------------------


def cargar_corridas(raiz_resultados: str | Path) -> list[dict[str, Any]]:
    """Lee todos los ``resumen.json`` de un directorio de resultados.

    Un archivo con un esquema desconocido no se descarta en silencio: se carga
    y se marca, para que el panel pueda avisar de que esa corrida es de una
    versión distinta y no debe compararse sin cuidado.
    """
    raiz = Path(raiz_resultados)
    corridas: list[dict[str, Any]] = []
    if not raiz.is_dir():
        return corridas
    for archivo in sorted(raiz.glob("*/resumen.json")):
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        datos["_archivo"] = str(archivo)
        datos["_carpeta"] = archivo.parent.name
        datos["_esquema"] = datos.get("schema_version", "sin_declarar")
        datos["_esquema_compatible"] = esquema_compatible(datos["_esquema"])
        corridas.append(datos)
    corridas.sort(key=lambda d: d.get("entorno", {}).get("utc", ""), reverse=True)
    return corridas


def ultima_corrida_por_hipotesis(raiz_resultados: str | Path) -> dict[str, dict[str, Any]]:
    ultimas: dict[str, dict[str, Any]] = {}
    for corrida in cargar_corridas(raiz_resultados):
        id_ = corrida.get("hipotesis", {}).get("id")
        if id_ and id_ not in ultimas:
            ultimas[id_] = corrida
    return ultimas
