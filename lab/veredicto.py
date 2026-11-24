"""Agregación de las pruebas en un veredicto único y explícito.

El veredicto nunca promedia estados ni convierte un ``PENDIENTE`` en
aprobación. El orden de las reglas es deliberado: primero se descarta lo que
no es contrastable, luego lo que está fuera de dominio, después lo que
falla, y sólo al final se concede una corroboración **provisional**.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .contrato import ESTADOS_ACEPTABLES, ResultadoPrueba
from .protocolo import BLOQUEANTES, ORDEN

#: Veredictos globales posibles.
VEREDICTOS: tuple[str, ...] = (
    "CORROBORADA_PROVISIONAL",
    "NO_CORROBORADA",
    "REFUTADA",
    "NO_PRESENTADA",
    "SENSIBLE_AL_DISENO",
    "FUERA_DE_DOMINIO",
    "PENDIENTE",
)

#: Texto breve para humanos, apto para un informe.
DESCRIPCION_VEREDICTO: dict[str, str] = {
    "CORROBORADA_PROVISIONAL": (
        "Todas las pruebas bloqueantes se cumplieron sobre datos reservados. "
        "Es corroboración provisional, no demostración: no sustituye replicación "
        "independiente ni excluye explicaciones alternativas."
    ),
    "NO_CORROBORADA": (
        "La hipótesis no superó la comparación con el baseline o no generalizó. "
        "No se refuta la idea, pero este diseño no la sostiene."
    ),
    "REFUTADA": (
        "La hipótesis predice significativamente peor que el baseline sobre los "
        "datos reservados."
    ),
    "NO_PRESENTADA": (
        "No hay predicción diferenciadora contrastable: la hipótesis coincide con "
        "el baseline o su diferencia es menor que la sensibilidad declarada."
    ),
    "SENSIBLE_AL_DISENO": (
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


def agregar(resultados: Sequence[ResultadoPrueba]) -> Veredicto:
    """Aplica las reglas de agregación en orden y devuelve el veredicto."""
    m = matriz(resultados)
    falla = {c for c, e in m.items() if e == "FALLIDO"}
    pendiente = {c for c, e in m.items() if e == "PENDIENTE"}
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
    if "T02" in falla or m.get("T03") == "NO_PRESENTADA":
        detalle = (
            "la predicción no es falsable (T02)" if "T02" in falla
            else "no hay diferencia observable frente al baseline (T03)"
        )
        return salir("NO_PRESENTADA", f"No se presenta predicción contrastable: {detalle}.")

    # 2. Fuera de dominio.
    if "T12" in falla:
        return salir(
            "FUERA_DE_DOMINIO",
            "Las condiciones evaluadas no están dentro del dominio declarado (T12).",
        )

    # 3. No generaliza o el diseño manda.
    if "T06" in falla:
        return salir(
            "NO_CORROBORADA",
            "El modelo no generaliza sobre datos reservados (T06): el error excede "
            "lo admitido y la predicción no es transportable.",
        )
    if "T08" in falla:
        return salir(
            "NO_CORROBORADA",
            "La mejora no aparece en ninguna partición alternativa (T08): el "
            "resultado depende de una única división de los datos.",
        )

    # 4. Comparación con el baseline.
    if "T07" in falla:
        return salir(
            "REFUTADA",
            "Sobre datos reservados el baseline convencional es significativamente "
            "mejor que la hipótesis (T07).",
        )
    if m.get("T07") == "PENDIENTE":
        motivo = (
            "La hipótesis no demuestra una mejora significativa sobre el baseline "
            "(T07): no se puede afirmar que aporte nada nuevo aquí."
        )
        if m.get("T08") == "SENSIBLE_AL_DISENO":
            motivo += (
                " Además, el signo de la mejora cambia al cambiar la partición "
                "(T08): la conclusión depende del diseño."
            )
        return salir("NO_CORROBORADA", motivo)

    # 5. Sensibilidad al diseño.
    if m.get("T08") == "SENSIBLE_AL_DISENO":
        return salir(
            "SENSIBLE_AL_DISENO",
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
        detalle = ", ".join(
            f"{c}={m.get(c)}" for c in bloqueantes_incumplidas
        )
        return salir(
            "PENDIENTE",
            f"Pruebas bloqueantes no superadas: {detalle}.",
        )
    if pendiente:
        return salir(
            "PENDIENTE",
            "Sin fallos, pero quedan pruebas sin evidencia suficiente: "
            + ", ".join(sorted(pendiente)) + ".",
        )

    return salir(
        "CORROBORADA_PROVISIONAL",
        "Se cumplieron todas las pruebas bloqueantes y la conclusión es estable "
        "ante particiones alternativas.",
    )
