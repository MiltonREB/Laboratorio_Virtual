"""Agregación de las pruebas en un veredicto único y explícito.

El veredicto nunca promedia estados ni convierte un ``PENDIENTE`` en
aprobación. El orden de las reglas es deliberado: primero se descarta lo que
no es contrastable, luego lo que está fuera de dominio, después lo que falla,
después lo que depende del diseño, y sólo al final se concede una corroboración
**provisional**… y sólo si las verificaciones vinculantes la respaldan.

Vocabulario (v1.1.0)
--------------------
Cuatro estados de prueba: ``APROBADO``, ``PENDIENTE``, ``SENSIBLE``,
``FALLIDO``. Siete veredictos, ninguno llamado «refutada»: un experimento no
refuta una idea, sólo deja de sostenerla.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .contrato import ESTADOS_ACEPTABLES, ResultadoPrueba
from .protocolo import BLOQUEANTES, ORDEN

#: Veredictos globales posibles.
VEREDICTOS: tuple[str, ...] = (
    "CORROBORADA_PROVISIONAL",
    "PRELIMINAR",
    "NO_CORROBORADA",
    "NO_PRESENTADA",
    "SENSIBLE",
    "FUERA_DE_DOMINIO",
    "PENDIENTE",
)

#: Verificaciones que condicionan el veredicto máximo (v1.1.0).
VERIFICACIONES_VINCULANTES: tuple[str, ...] = ("O01", "O04")

#: Texto breve para humanos, apto para un informe.
DESCRIPCION_VEREDICTO: dict[str, str] = {
    "CORROBORADA_PROVISIONAL": (
        "Las doce pruebas se cumplieron, las verificaciones vinculantes la "
        "respaldan y la conclusión es estable. Sigue siendo provisional: no "
        "sustituye replicación independiente ni excluye explicaciones alternativas."
    ),
    "PRELIMINAR": (
        "Las doce pruebas se cumplieron, pero falta el contraste que exige el "
        "protocolo para corroborar: un baseline alternativo al que superar o un "
        "holdout externo. El resultado es indicativo, no corroborado."
    ),
    "NO_CORROBORADA": (
        "La hipótesis no superó la comparación con el baseline o no generalizó. "
        "No se refuta la idea, pero este diseño no la sostiene."
    ),
    "NO_PRESENTADA": (
        "No hay predicción diferenciadora contrastable: la hipótesis coincide con "
        "el baseline o su diferencia no es distinguible en la escala de los datos."
    ),
    "SENSIBLE": (
        "La conclusión cambia al cambiar la partición de los datos. Antes de "
        "afirmar nada hay que fijar el diseño y repetir con datos nuevos."
    ),
    "FUERA_DE_DOMINIO": (
        "La evaluación sale del dominio de validez declarado; el resultado no "
        "aplica a las condiciones ensayadas."
    ),
    "PENDIENTE": (
        "Falta evidencia para emitir un veredicto: alguna prueba bloqueante no se "
        "cumplió o no pudo ejecutarse."
    ),
}


@dataclass(frozen=True)
class Veredicto:
    estado: str
    motivo: str
    bloqueantes: tuple[str, ...]
    conteo: Mapping[str, int]
    matriz: Mapping[str, str]

    @property
    def descripcion(self) -> str:
        return DESCRIPCION_VEREDICTO.get(self.estado, "")

    @property
    def es_positivo(self) -> bool:
        return self.estado == "CORROBORADA_PROVISIONAL"

    def como_dict(self) -> dict[str, object]:
        return {
            "estado": self.estado,
            "motivo": self.motivo,
            "descripcion": self.descripcion,
            "bloqueantes_incumplidas": list(self.bloqueantes),
            "conteo_estados": dict(self.conteo),
            "matriz": dict(self.matriz),
        }


def matriz(resultados: Sequence[ResultadoPrueba]) -> dict[str, str]:
    return {r.codigo: r.estado for r in resultados}


def contar(resultados: Sequence[ResultadoPrueba]) -> dict[str, int]:
    conteo: dict[str, int] = {}
    for r in resultados:
        conteo[r.estado] = conteo.get(r.estado, 0) + 1
    return conteo


def _verificaciones_por_codigo(
    verificaciones: Sequence[object] | None,
) -> dict[str, object]:
    salida: dict[str, object] = {}
    for v in verificaciones or []:
        codigo = getattr(v, "codigo", None) or (
            v.get("codigo") if isinstance(v, Mapping) else None
        )
        if codigo:
            salida[str(codigo)] = v
    return salida


def _leer(v: object, campo: str, defecto=None):
    if isinstance(v, Mapping):
        return v.get(campo, defecto)
    return getattr(v, campo, defecto)


def agregar(
    resultados: Sequence[ResultadoPrueba],
    verificaciones: Sequence[object] | None = None,
) -> Veredicto:
    """Aplica las reglas de agregación en orden y devuelve el veredicto."""
    m = matriz(resultados)
    falla = {c for c, e in m.items() if e == "FALLIDO"}
    pendiente = {c for c, e in m.items() if e == "PENDIENTE"}
    ausencia = {r.codigo for r in resultados if r.es_ausencia}
    bloqueantes_incumplidas = tuple(
        c for c in ORDEN if c in BLOQUEANTES and m.get(c) not in ESTADOS_ACEPTABLES
    )

    def salir(estado: str, motivo: str) -> Veredicto:
        return Veredicto(
            estado=estado,
            motivo=motivo,
            bloqueantes=bloqueantes_incumplidas,
            conteo=contar(resultados),
            matriz=m,
        )

    # 1. Sin predicción contrastable no hay nada que evaluar.
    if ausencia:
        detalle = ", ".join(sorted(ausencia))
        return salir(
            "NO_PRESENTADA",
            f"No se presenta predicción contrastable: la prueba {detalle} no "
            "encontró una diferencia distinguible frente al baseline.",
        )

    # 2. Fuera de dominio.
    if "T12" in falla:
        return salir(
            "FUERA_DE_DOMINIO",
            "Las condiciones evaluadas no están dentro del dominio declarado (T12).",
        )

    # 3. No generaliza.
    if "T06" in falla:
        return salir(
            "NO_CORROBORADA",
            "El modelo no generaliza sobre datos reservados (T06): el error excede "
            "lo admitido y la predicción no es transportable.",
        )

    # 4. La comparación con el baseline.
    if m.get("T07") != "APROBADO":
        detalle = next(
            (r.detalle for r in resultados if r.codigo == "T07"),
            "sin mejora significativa",
        )
        return salir("NO_CORROBORADA", f"{detalle}")

    # 5. Sensibilidad al diseño.
    if m.get("T08") == "SENSIBLE":
        return salir(
            "SENSIBLE",
            "El signo de la mejora cambia al cambiar la partición (T08): hay que "
            "fijar el diseño y repetir antes de concluir.",
        )

    # 6. Veredicto condicionado por la validez del preregistro.
    if "T04" in falla:
        return salir(
            "PENDIENTE",
            "El preregistro no coincide con la firma actual (T04): los umbrales o "
            "parámetros cambiaron después de sellarse. Repite el preregistro y la "
            "corrida para que el resultado sea interpretable.",
        )

    # 7. Cualquier otra bloqueante no cumplida impide la corroboración.
    if bloqueantes_incumplidas:
        detalle = ", ".join(f"{c}={m.get(c)}" for c in bloqueantes_incumplidas)
        return salir("PENDIENTE", f"Pruebas bloqueantes no superadas: {detalle}.")
    if pendiente:
        return salir(
            "PENDIENTE",
            "Sin fallos, pero quedan pruebas sin evidencia suficiente: "
            + ", ".join(sorted(pendiente)) + ".",
        )

    # 8. Las verificaciones vinculantes deciden entre corroborar y quedarse corto.
    vinculantes = _verificaciones_por_codigo(verificaciones)
    faltantes: list[str] = []
    for codigo in VERIFICACIONES_VINCULANTES:
        v = vinculantes.get(codigo)
        if v is None or _leer(v, "estado") != "EJECUTADA":
            faltantes.append(codigo)
    if faltantes:
        motivos = []
        for codigo in faltantes:
            v = vinculantes.get(codigo)
            motivos.append(f"{codigo}: {_leer(v, 'motivo', 'no ejecutada')}")
        return salir(
            "PRELIMINAR",
            "Se cumplieron las doce pruebas, pero falta contraste vinculante — "
            + "; ".join(motivos) + ". El máximo alcanzable es preliminar.",
        )

    o01 = vinculantes["O01"]
    if not (_leer(o01, "evidencia", {}) or {}).get("gana_a_todos", False):
        return salir(
            "PRELIMINAR",
            "La hipótesis no supera a todos los baselines alternativos (O01): su "
            "ventaja depende del baseline elegido. El máximo alcanzable es preliminar.",
        )

    o04 = vinculantes["O04"]
    if not (_leer(o04, "evidencia", {}) or {}).get("supera_baseline", False):
        return salir(
            "NO_CORROBORADA",
            "Sobre el holdout externo la hipótesis no supera al baseline (O04): no "
            "generaliza fuera del diseño con el que se ajustó.",
        )

    return salir(
        "CORROBORADA_PROVISIONAL",
        "Las doce pruebas se cumplieron, la mejora supera a todos los baselines "
        "declarados, se sostiene en un holdout externo y es estable ante "
        "particiones alternativas.",
    )
