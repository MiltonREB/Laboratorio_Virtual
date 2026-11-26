"""Batería de pruebas del protocolo (T01–T12).

Cada prueba es una función ``ContextoEvaluacion -> ResultadoPrueba``. Ninguna
prueba supone buena fe: si no puede verificar algo, devuelve ``PENDIENTE``
en lugar de ``APROBADO``. Un veredicto global sólo puede ser
``CORROBORADA_PROVISIONAL`` si las doce pruebas están en ``APROBADO`` y las
verificaciones vinculantes lo respaldan.

Estados (v1.1.0): ``APROBADO``, ``PENDIENTE``, ``SENSIBLE``, ``FALLIDO``.
No hay un estado «no aplicable»: el caso vacuo es ``APROBADO`` y se marca.

Orden y sentido de las pruebas
------------------------------
T01 Formalización      ¿está declarado todo lo que el protocolo exige?
T02 Falsabilidad       ¿emite una predicción numérica que podría ser falsa?
T03 Predicción difer.  ¿difiere del baseline por encima de la sensibilidad?
T04 Preregistro        ¿los umbrales y parámetros se congelaron antes?
T05 Calibración        ¿los parámetros libres sólo vieron la calibración?
T06 Fuera de muestra   ¿predice sobre datos que no se usaron para ajustar?
T07 Baseline           ¿supera al modelo convencional de forma significativa?
T08 Estabilidad        ¿la conclusión sobrevive al cambiar la partición?
T09 Reproducibilidad   ¿dos ejecuciones dan exactamente lo mismo?
T10 Incertidumbre      ¿el error observado cabe en el presupuesto declarado?
T11 Control nulo       ¿gana también cuando la verdad es el baseline?
T12 Dominio            ¿la evaluación está dentro del dominio declarado?
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np

from .contrato import Dominio, Hipotesis, Modelo, ResultadoPrueba
from .datos import ConjuntoDatos
from .metricas import Decision, Intervalo
from .preregistro import Verificacion

#: Orden canónico de las pruebas.
ORDEN: tuple[str, ...] = (
    "T01", "T02", "T03", "T04", "T05", "T06",
    "T07", "T08", "T09", "T10", "T11", "T12",
)

TITULOS: dict[str, str] = {
    "T01": "Formalización del contrato",
    "T02": "Falsabilidad de la predicción",
    "T03": "Predicción diferenciadora frente al baseline",
    "T04": "Preregistro de parámetros y umbrales",
    "T05": "Calibración restringida a la muestra de calibración",
    "T06": "Validación fuera de muestra",
    "T07": "Comparación con el baseline convencional",
    "T08": "Estabilidad de la conclusión ante el diseño",
    "T09": "Reproducibilidad numérica",
    "T10": "Presupuesto de incertidumbre",
    "T11": "Control nulo por datos generados con el baseline",
    "T12": "Dominio de validez declarado",
}

#: Pruebas sin las cuales no puede emitirse un veredicto positivo.
#: v1.1.0: las doce son bloqueantes.
BLOQUEANTES: frozenset[str] = frozenset(ORDEN)

#: Factor de tolerancia para decidir que un error "cabe" en el presupuesto.
FACTOR_INCERTIDUMBRE = 3.0
#: Factor de tolerancia del error fuera de muestra frente a su escala.
FACTOR_VALIDACION = 5.0


@dataclass
class ContextoEvaluacion:
    """Todo lo que las pruebas pueden mirar, ya calculado y sin ambigüedad."""

    hipotesis: Hipotesis
    dataset: ConjuntoDatos
    baseline: Modelo
    parametros_declarados: dict[str, float]
    parametros_ajustados: dict[str, float]
    ajuste_usado: bool
    variables_calibracion: dict[str, np.ndarray]
    variables_reservado: dict[str, np.ndarray]
    observado_calibracion: np.ndarray
    observado_reservado: np.ndarray
    pred_hip_calibracion: np.ndarray
    pred_base_calibracion: np.ndarray
    pred_hip_reservado: np.ndarray
    pred_base_reservado: np.ndarray
    errores_calibracion: dict[str, float] = field(default_factory=dict)
    errores_reservado: dict[str, float] = field(default_factory=dict)
    intervalo_reservado: Intervalo | None = None
    decision_baseline: Decision | None = None
    verificacion: Verificacion | None = None
    estabilidad: Mapping[str, object] = field(default_factory=dict)
    control_nulo: Mapping[str, object] = field(default_factory=dict)
    reproducibilidad: Mapping[str, object] = field(default_factory=dict)
    advertencias: list[str] = field(default_factory=list)

    # -- derivados usados por varias pruebas ---------------------------

    @property
    def delta_reservado(self) -> np.ndarray:
        return np.asarray(self.pred_hip_reservado, float) - np.asarray(
            self.pred_base_reservado, float
        )

    @property
    def residuo_reservado(self) -> np.ndarray:
        return np.asarray(self.observado_reservado, float) - np.asarray(
            self.pred_hip_reservado, float
        )

    @property
    def presupuesto_incertidumbre(self) -> float:
        """Presupuesto combinado: incertidumbre declarada ⊕ experimental.

        Si el dataset trae columnas ``u_*``, entran en cuadratura como término
        explícito. Es la diferencia entre «el ajuste deja 0,8 ms» y «el
        instrumento no resuelve mejor de 1,2 ms».
        """
        declarada = float(self.hipotesis.incertidumbre_declarada)
        declarada = declarada if np.isfinite(declarada) and declarada > 0 else None
        return self.dataset.escala_efectiva(
            self.hipotesis.observable_objetivo, declarada
        )

    @property
    def escala_de_validacion(self) -> float:
        presupuesto = self.presupuesto_incertidumbre
        if presupuesto > 0:
            return presupuesto
        base = float(self.errores_reservado.get("baseline", float("nan")))
        return base if np.isfinite(base) and base > 0 else 1.0


# --------------------------------------------------------------------------
# T01–T12
# --------------------------------------------------------------------------


def t01_formalizacion(ctx: ContextoEvaluacion) -> ResultadoPrueba:
    faltas = ctx.hipotesis.problemas_de_contrato()
    if faltas:
        return ResultadoPrueba(
            "T01", TITULOS["T01"], "FALLIDO",
            f"{len(faltas)} elemento(s) del contrato sin declarar",
            {"faltantes": faltas},
        )
    return ResultadoPrueba(
        "T01", TITULOS["T01"], "APROBADO",
        "Enunciado, dominio, unidades, baseline, métrica y umbrales declarados",
        {
            "enunciado": ctx.hipotesis.enunciado,
            "dominio": (ctx.hipotesis.dominio.descripcion if ctx.hipotesis.dominio else None),
            "baseline": ctx.baseline.id,
            "metrica": ctx.hipotesis.metrica,
            "umbral_mejora": ctx.hipotesis.umbral_mejora,
            "umbral_sensibilidad": ctx.hipotesis.umbral_sensibilidad,
        },
    )


def t02_falsabilidad(ctx: ContextoEvaluacion) -> ResultadoPrueba:
    pred = np.asarray(ctx.pred_hip_reservado, float)
    problemas: list[str] = []
    if pred.size == 0:
        problemas.append("predicción vacía")
    if not np.all(np.isfinite(pred)):
        problemas.append("predicción con valores no finitos")
    # Una predicción constante puede ser falsable; su variación entre filas
    # no es condición necesaria para contrastarla con observaciones.
    if not np.isfinite(float(ctx.hipotesis.umbral_mejora or float("nan"))):
        problemas.append("sin umbral de mejora declarado")

    if problemas:
        return ResultadoPrueba(
            "T02", TITULOS["T02"], "FALLIDO",
            "La hipótesis no emite una predicción numérica falsable",
            {"problemas": problemas},
            es_ausencia=True,
        )
    return ResultadoPrueba(
        "T02", TITULOS["T02"], "APROBADO",
        (
            f"Predicción numérica finita en {pred.size} filas; "
            f"el umbral de mejora {ctx.hipotesis.umbral_mejora:g} haría fallar "
            "la hipótesis si no se alcanza"
        ),
        {
            "filas_reservadas": int(pred.size),
            "min": float(pred.min()),
            "max": float(pred.max()),
            "umbral_mejora": ctx.hipotesis.umbral_mejora,
        },
    )


def t03_prediccion_diferenciadora(ctx: ContextoEvaluacion) -> ResultadoPrueba:
    """¿La diferencia con el baseline es distinguible **en la escala de los datos**?

    v1.1.0: el criterio ya no es una tolerancia absoluta. Se exige que |ΔO|
    supere ``factor_diferenciacion`` veces el error del baseline sobre la misma
    muestra reservada, que es la escala real de lo que el modelo alternativo se
    equivoca. Una tolerancia absoluta (p. ej. 10⁻⁴ s) puede cumplirse con una
    diferencia que en la práctica es ruido, o rechazar una diferencia grande en
    otra unidad.
    """
    delta = ctx.delta_reservado
    maximo = float(np.max(np.abs(delta))) if delta.size else 0.0
    rms = float(np.sqrt(np.mean(delta ** 2))) if delta.size else 0.0
    # maximo y rms están en unidades físicas del observable. Si la métrica
    # seleccionada es chi2_reducido, su valor es adimensional y NO puede
    # utilizarse como escala para delta. Recuperamos una escala dimensional
    # desde los residuos de la misma muestra reservada.
    if ctx.hipotesis.metrica == "chi2_reducido":
        residuos_base = np.asarray(ctx.observado_reservado, float) - np.asarray(
            ctx.pred_base_reservado, float
        )
        escala = float(np.sqrt(np.mean(residuos_base ** 2))) if residuos_base.size else float("nan")
    else:
        escala = float(ctx.errores_reservado.get("baseline", float("nan")))
    factor = float(ctx.hipotesis.factor_diferenciacion)
    suelo = ctx.hipotesis.umbral_sensibilidad
    suelo = float(suelo) if suelo is not None else 0.0
    exigido = max(factor * escala, suelo) if np.isfinite(escala) else suelo
    datos = {
        "delta_max_abs": maximo,
        "delta_rms": rms,
        "escala_baseline": escala if np.isfinite(escala) else None,
        "factor_diferenciacion": factor,
        "umbral_sensibilidad_absoluto": suelo or None,
        "exigido": exigido,
        "veces_la_escala": (maximo / escala) if np.isfinite(escala) and escala > 0 else None,
        "unidad": ctx.hipotesis.unidad_observable,
        "texto": ctx.hipotesis.prediccion_diferenciadora,
    }
    if maximo == 0.0:
        return ResultadoPrueba(
            "T03", TITULOS["T03"], "PENDIENTE",
            "La hipótesis predice exactamente lo mismo que el baseline: "
            "no hay predicción diferenciadora que contrastar",
            datos,
            es_ausencia=True,
        )
    if maximo < exigido:
        return ResultadoPrueba(
            "T03", TITULOS["T03"], "PENDIENTE",
            (
                f"|ΔO| máximo {maximo:.4g} {ctx.hipotesis.unidad_observable} no supera "
                f"lo exigido ({exigido:.4g}): {factor:g}× el error del baseline "
                f"({escala:.4g})" if np.isfinite(escala) else
                f"|ΔO| máximo {maximo:.4g} no supera el suelo absoluto {exigido:.4g}"
            ),
            datos,
            es_ausencia=True,
        )
    detalle = (
        f"|ΔO| máximo {maximo:.4g} {ctx.hipotesis.unidad_observable} = "
        f"{maximo / escala:.1f}× el error del baseline ({escala:.4g})"
        if np.isfinite(escala) and escala > 0
        else f"|ΔO| máximo {maximo:.4g} supera el suelo {exigido:.4g}"
    )
    return ResultadoPrueba("T03", TITULOS["T03"], "APROBADO", detalle, datos)


def t04_preregistro(ctx: ContextoEvaluacion) -> ResultadoPrueba:
    """Traduce el estado único del preregistro al estado de la prueba."""
    v = ctx.verificacion
    if v is None:
        return ResultadoPrueba(
            "T04", TITULOS["T04"], "PENDIENTE",
            "No se pudo verificar el preregistro", {"estado_preregistro": None},
        )
    from .preregistro import describir

    mapa = {
        "VALIDO": "APROBADO",
        "ALTERADO": "FALLIDO",
        "AUSENTE": "PENDIENTE",
        "TARDIO": "PENDIENTE",
        "RECIENTE": "PENDIENTE",
        "NO_PUBLICADO": "PENDIENTE",
    }
    datos = v.como_dict()
    if v.estado_preregistro == "ALTERADO":
        datos["cambios"] = ctx.reproducibilidad.get("cambios_firma", [])
    return ResultadoPrueba(
        "T04",
        TITULOS["T04"],
        mapa.get(v.estado_preregistro, "PENDIENTE"),
        describir(v),
        datos,
    )


def t05_calibracion(ctx: ContextoEvaluacion) -> ResultadoPrueba:
    libres = ctx.hipotesis.parametros_libres()
    solape = set(ctx.dataset.calibracion) & set(ctx.dataset.reservado)
    datos = {
        "parametros_libres": [p.nombre for p in libres],
        "valores_declarados": ctx.parametros_declarados,
        "valores_ajustados": ctx.parametros_ajustados,
        "filas_calibracion": len(ctx.dataset.calibracion),
        "filas_reservado": len(ctx.dataset.reservado),
        "solape_particiones": len(solape),
        "ajuste_usado": ctx.ajuste_usado,
        "vacuo": not libres,
    }
    if solape:
        return ResultadoPrueba(
            "T05", TITULOS["T05"], "FALLIDO",
            (
                f"Las particiones de calibración y reservado comparten "
                f"{len(solape)} filas: la validación fuera de muestra está contaminada"
            ),
            datos,
        )
    if not libres:
        return ResultadoPrueba(
            "T05", TITULOS["T05"], "APROBADO",
            "Se cumple de forma vacua: la hipótesis no declara parámetros libres, "
            "así que no hay ajuste que pueda contaminar el reservado",
            datos,
        )
    if not ctx.ajuste_usado:
        return ResultadoPrueba(
            "T05", TITULOS["T05"], "FALLIDO",
            (
                f"Declara {len(libres)} parámetro(s) libre(s) pero no se ajustó "
                "ninguno: los valores usados no tienen respaldo en datos"
            ),
            datos,
        )
    return ResultadoPrueba(
        "T05", TITULOS["T05"], "APROBADO",
        (
            f"{len(libres)} parámetro(s) ajustado(s) sólo con "
            f"{len(ctx.dataset.calibracion)} filas de calibración; "
            f"{len(ctx.dataset.reservado)} filas reservadas intactas"
        ),
        datos,
    )


def t06_fuera_de_muestra(ctx: ContextoEvaluacion) -> ResultadoPrueba:
    error = float(ctx.errores_reservado.get("hipotesis", float("nan")))
    # chi2_reducido es adimensional: su raíz es el RMS de residuos
    # normalizados por sigma. Se compara con un límite en sigmas, nunca
    # con incertidumbres expresadas en metros/segundos.
    es_chi2 = ctx.hipotesis.metrica == "chi2_reducido"
    escala = 1.0 if es_chi2 else ctx.escala_de_validacion
    error_comparable = float(np.sqrt(error)) if es_chi2 and error >= 0 else error
    datos = {
        "error_reservado": error,
        "error_comparable": error_comparable,
        "escala_comparacion": "sigma_normalizada" if es_chi2 else "observable",
        "error_calibracion": _num(ctx.errores_calibracion.get("hipotesis")),
        "escala": escala,
        "factor_admitido": FACTOR_VALIDACION,
        "filas_reservado": int(ctx.observado_reservado.size),
    }
    if not np.isfinite(error):
        return ResultadoPrueba(
            "T06", TITULOS["T06"], "FALLIDO",
            "El error fuera de muestra no es finito: la predicción no es usable",
            datos,
        )
    if error_comparable > FACTOR_VALIDACION * escala:
        return ResultadoPrueba(
            "T06", TITULOS["T06"], "FALLIDO",
            (
                f"El error fuera de muestra ({error:.6g}) supera "
                f"{FACTOR_VALIDACION:g}× la escala admitida ({escala:.6g}): el modelo "
                "no generaliza más allá de los datos con los que se ajustó"
            ),
            datos,
        )
    return ResultadoPrueba(
        "T06", TITULOS["T06"], "APROBADO",
        (
            f"Error fuera de muestra {error:.6g} dentro de {FACTOR_VALIDACION:g}× "
            f"la escala {escala:.6g}"
        ),
        datos,
    )


def t07_baseline(ctx: ContextoEvaluacion) -> ResultadoPrueba:
    """Comparación con el baseline.

    v1.1.0: esta prueba **nunca** devuelve ``FALLIDO``. Que el baseline sea
    significativamente mejor no refuta la hipótesis: dice que este diseño no la
    sostiene. El estado es ``APROBADO`` o ``PENDIENTE``, y el hecho de que el
    intervalo quede bajo cero se registra en ``peor_que_baseline``.
    """
    if ctx.intervalo_reservado is None or ctx.decision_baseline is None:
        return ResultadoPrueba(
            "T07", TITULOS["T07"], "PENDIENTE",
            "No se pudo calcular la comparación con el baseline", {},
        )
    i = ctx.intervalo_reservado
    from .metricas import ratio_errores

    eh = ctx.errores_reservado.get("hipotesis")
    eb = ctx.errores_reservado.get("baseline")
    peor = bool(i.superior < 0.0)
    datos = {
        **i.como_dict(),
        "error_hipotesis": _num(eh),
        "error_baseline": _num(eb),
        "ratio_errores": ratio_errores(float(eh), float(eb)) if eh is not None and eb is not None else None,
        "metrica": ctx.hipotesis.metrica,
        "umbral_mejora": ctx.hipotesis.umbral_mejora,
        "peor_que_baseline": peor,
    }
    if ctx.decision_baseline.estado == "APROBADO":
        return ResultadoPrueba(
            "T07", TITULOS["T07"], "APROBADO", ctx.decision_baseline.motivo, datos
        )
    detalle = ctx.decision_baseline.motivo
    if peor:
        detalle += (
            " El baseline es significativamente mejor: la hipótesis no se sostiene "
            "con estos datos (no se declara refutada, se declara sin apoyo)."
        )
    return ResultadoPrueba("T07", TITULOS["T07"], "PENDIENTE", detalle, datos)


def t08_estabilidad(ctx: ContextoEvaluacion) -> ResultadoPrueba:
    """Estabilidad del signo de la mejora entre particiones alternativas.

    v1.1.0: el único estado de alarma es ``SENSIBLE``. Si la mejora no aparece
    en ninguna partición, el estado es ``PENDIENTE``: no hay evidencia, no un
    fallo demostrado.
    """
    detalle = dict(ctx.estabilidad)
    ensayos = detalle.get("ensayos", [])
    if not ensayos:
        return ResultadoPrueba(
            "T08", TITULOS["T08"], "PENDIENTE",
            "No se ejecutaron particiones alternativas", detalle,
        )
    mejoras = [float(e["mejora"]) for e in ensayos]
    positivas = sum(1 for m in mejoras if m > 0)
    negativas = sum(1 for m in mejoras if m <= 0)
    detalle["positivas"] = positivas
    detalle["negativas"] = negativas
    if negativas == 0:
        return ResultadoPrueba(
            "T08", TITULOS["T08"], "APROBADO",
            f"La mejora conserva el signo en {len(mejoras)} particiones alternativas "
            f"(mínima {min(mejoras):.4f})",
            detalle,
        )
    if positivas == 0:
        return ResultadoPrueba(
            "T08", TITULOS["T08"], "PENDIENTE",
            f"En ninguna de las {len(mejoras)} particiones alternativas la "
            "hipótesis mejora al baseline: no hay evidencia de mejora estable",
            detalle,
        )
    return ResultadoPrueba(
        "T08", TITULOS["T08"], "SENSIBLE",
        (
            f"El signo de la mejora cambia con la partición: {positivas} positivas "
            f"y {negativas} no positivas de {len(mejoras)}. La conclusión depende del "
            "diseño, no sólo de los datos"
        ),
        detalle,
    )


def t09_reproducibilidad(ctx: ContextoEvaluacion) -> ResultadoPrueba:
    r = dict(ctx.reproducibilidad)
    if not r:
        return ResultadoPrueba(
            "T09", TITULOS["T09"], "PENDIENTE",
            "No se ejecutó la comprobación de doble ejecución", {},
        )
    iguales = bool(r.get("prediccion_identica")) and bool(r.get("bootstrap_identico"))
    datos = {
        "sha_prediccion_1": r.get("sha_prediccion_1"),
        "sha_prediccion_2": r.get("sha_prediccion_2"),
        "sha_bootstrap_1": r.get("sha_bootstrap_1"),
        "sha_bootstrap_2": r.get("sha_bootstrap_2"),
        "prediccion_identica": r.get("prediccion_identica"),
        "bootstrap_identico": r.get("bootstrap_identico"),
    }
    if iguales:
        return ResultadoPrueba(
            "T09", TITULOS["T09"], "APROBADO",
            f"Dos ejecuciones producen la misma predicción y el mismo bootstrap "
            f"({str(r.get('sha_prediccion_1'))[:12]}…)",
            datos,
        )
    return ResultadoPrueba(
        "T09", TITULOS["T09"], "FALLIDO",
        "Dos ejecuciones con los mismos parámetros no coinciden: el resultado "
        "no es reproducible bit a bit",
        datos,
    )


def t10_incertidumbre(ctx: ContextoEvaluacion) -> ResultadoPrueba:
    """Presupuesto de incertidumbre: declarado ⊕ experimental.

    v1.1.0 usa las columnas ``u_*`` del dataset como término explícito. «El
    ajuste deja 0,8 ms» y «el instrumento no resuelve mejor de 1,2 ms» son
    afirmaciones distintas, y el presupuesto debe contener las dos.
    """
    declarada = float(ctx.hipotesis.incertidumbre_declarada)
    experimental = ctx.dataset.incertidumbre_media(ctx.hipotesis.observable_objetivo)
    presupuesto = ctx.presupuesto_incertidumbre
    error = float(ctx.errores_reservado.get("hipotesis", float("nan")))
    es_chi2 = ctx.hipotesis.metrica == "chi2_reducido"
    # chi² reducido ya incorpora sigma al calcularse: no volver a dividir
    # por un presupuesto con dimensiones físicas. Su raíz se evalúa como
    # residuo normalizado, con valor esperado cercano a 1.
    if es_chi2:
        presupuesto = 1.0
    datos = {
        "escala_comparacion": "sigma_normalizada" if es_chi2 else "observable",
        "incertidumbre_declarada": None if not np.isfinite(declarada) else declarada,
        "incertidumbre_experimental": experimental,
        "presupuesto_combinado": presupuesto or None,
        "error_observado": _num(error),
        "residuo_rms": float(np.sqrt(np.mean(ctx.residuo_reservado ** 2)))
        if ctx.residuo_reservado.size else None,
    }
    if presupuesto <= 0:
        return ResultadoPrueba(
            "T10", TITULOS["T10"], "PENDIENTE",
            "La hipótesis no declara presupuesto de incertidumbre y el dataset "
            "no trae incertidumbre experimental por fila",
            datos,
        )
    if not np.isfinite(error):
        return ResultadoPrueba(
            "T10", TITULOS["T10"], "FALLIDO",
            "No hay error utilizable para comparar con la incertidumbre declarada",
            datos,
        )
    razon = (float(np.sqrt(error)) if es_chi2 and error >= 0 else error) / presupuesto
    datos["razon_error_sobre_presupuesto"] = razon
    componentes = []
    if datos["incertidumbre_declarada"]:
        componentes.append(f"declarada {datos['incertidumbre_declarada']:.3g}")
    if experimental:
        componentes.append(f"experimental {experimental:.3g}")
    detalle_componentes = " ⊕ ".join(componentes) if componentes else "sin componentes"
    if razon > FACTOR_INCERTIDUMBRE:
        return ResultadoPrueba(
            "T10", TITULOS["T10"], "FALLIDO",
            (
                f"El error observado es {razon:.1f}× el presupuesto "
                f"({error:.6g} vs {presupuesto:.6g}; {detalle_componentes}): "
                "el presupuesto está subestimado"
            ),
            datos,
        )
    if razon < 1.0 / FACTOR_INCERTIDUMBRE:
        return ResultadoPrueba(
            "T10", TITULOS["T10"], "PENDIENTE",
            (
                f"El error observado es {razon:.2f}× el presupuesto "
                f"({detalle_componentes}): el presupuesto parece inflado y no "
                "informa sobre la precisión real"
            ),
            datos,
        )
    return ResultadoPrueba(
        "T10", TITULOS["T10"], "APROBADO",
        (
            f"El error observado es {razon:.2f}× el presupuesto "
            f"({detalle_componentes})"
        ),
        datos,
    )


def t11_control_nulo(ctx: ContextoEvaluacion) -> ResultadoPrueba:
    c = dict(ctx.control_nulo)
    if not c or c.get("error"):
        return ResultadoPrueba(
            "T11", TITULOS["T11"], "PENDIENTE",
            f"No se pudo ejecutar el control nulo: {c.get('error', 'sin datos')}", c,
        )
    mejora = float(c.get("mejora", float("nan")))
    inferior = float(c.get("ic_inferior", float("nan")))
    umbral = float(ctx.hipotesis.umbral_mejora or 0.0)
    datos = {
        **c,
        "umbral_mejora": umbral,
        "descripcion": (
            "Datos sintéticos generados por el baseline con el mismo ruido; una "
            "hipótesis honesta no debe alcanzar su umbral de mejora aquí"
        ),
    }
    if not np.isfinite(mejora):
        return ResultadoPrueba(
            "T11", TITULOS["T11"], "PENDIENTE",
            "El control nulo no produjo una mejora utilizable", datos,
        )
    if mejora >= umbral and np.isfinite(inferior) and inferior > 0:
        return ResultadoPrueba(
            "T11", TITULOS["T11"], "FALLIDO",
            (
                f"Sobre datos generados por el baseline la hipótesis alcanza una "
                f"mejora de {mejora:.4f} (IC inferior {inferior:.4f}) ≥ umbral "
                f"{umbral:.4f}: la ventaja es un artefacto, no una predicción"
            ),
            datos,
        )
    return ResultadoPrueba(
        "T11", TITULOS["T11"], "APROBADO",
        (
            f"Sobre datos del baseline la mejora es {mejora:.4f} "
            f"(umbral exigido {umbral:.4f}): no se gana por artefacto"
        ),
        datos,
    )


def t12_dominio(ctx: ContextoEvaluacion) -> ResultadoPrueba:
    dominio: Dominio | None = ctx.hipotesis.dominio
    if dominio is None:
        return ResultadoPrueba(
            "T12", TITULOS["T12"], "FALLIDO",
            "No hay dominio declarado: no se puede acotar la validez", {},
        )
    combinadas = {
        k: np.concatenate([ctx.variables_calibracion[k], ctx.variables_reservado[k]])
        for k in ctx.variables_calibracion
        if k in ctx.variables_reservado
    }
    fuera = dominio.contiene(combinadas)
    observado = {
        k: {"min": float(np.min(v)) if v.size else None,
            "max": float(np.max(v)) if v.size else None,
            "filas": int(v.size)}
        for k, v in combinadas.items()
    }
    datos = {
        "rango_declarado": {k: list(v) for k, v in dominio.rango.items()},
        "fraccion_fuera": fuera,
        "observado": observado,
        "limitaciones": list(dominio.limitaciones),
    }
    infractoras = {k: f for k, f in fuera.items() if f > 0}
    if infractoras:
        detalle = ", ".join(f"{k}: {f:.1%} de filas" for k, f in infractoras.items())
        return ResultadoPrueba(
            "T12", TITULOS["T12"], "FALLIDO",
            f"La evaluación sale del dominio declarado ({detalle})", datos,
        )
    return ResultadoPrueba(
        "T12", TITULOS["T12"], "APROBADO",
        (
            f"{ctx.observado_calibracion.size} filas de calibración y "
            f"{ctx.observado_reservado.size} reservadas dentro del dominio declarado"
        ),
        datos,
    )


def _num(x: object) -> float | None:
    if x is None:
        return None
    v = float(x)  # type: ignore[arg-type]
    return v if np.isfinite(v) else None


#: Registro de pruebas en el orden canónico.
PRUEBAS = {
    "T01": t01_formalizacion,
    "T02": t02_falsabilidad,
    "T03": t03_prediccion_diferenciadora,
    "T04": t04_preregistro,
    "T05": t05_calibracion,
    "T06": t06_fuera_de_muestra,
    "T07": t07_baseline,
    "T08": t08_estabilidad,
    "T09": t09_reproducibilidad,
    "T10": t10_incertidumbre,
    "T11": t11_control_nulo,
    "T12": t12_dominio,
}


def ejecutar_pruebas(ctx: ContextoEvaluacion) -> list[ResultadoPrueba]:
    """Ejecuta la batería completa y devuelve los resultados en orden."""
    resultados: list[ResultadoPrueba] = []
    for codigo in ORDEN:
        funcion = PRUEBAS[codigo]
        try:
            resultados.append(funcion(ctx))
        except Exception as exc:  # una prueba rota no debe inventar un veredicto
            resultados.append(
                ResultadoPrueba(
                    codigo, TITULOS[codigo], "PENDIENTE",
                    f"La prueba no pudo completarse: {type(exc).__name__}: {exc}",
                    {"excepcion": traceback_formateado()},
                )
            )
    return resultados


def traceback_formateado() -> str:
    import traceback

    return traceback.format_exc(limit=6)
