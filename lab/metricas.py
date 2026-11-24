"""Métricas de error, mejora relativa y decisión estadística.

Regla del laboratorio: el umbral de decisión se declara antes de mirar los
datos, y una mejora sólo cuenta si su intervalo de confianza excluye el cero.
Una tolerancia elegida después de ver el resultado no es evidencia.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

import numpy as np


# --------------------------------------------------------------------------
# Errores
# --------------------------------------------------------------------------


def rmse(predicho: np.ndarray, observado: np.ndarray) -> float:
    p = np.asarray(predicho, dtype=float)
    o = np.asarray(observado, dtype=float)
    if p.shape != o.shape:
        raise ValueError(f"Formas incompatibles: {p.shape} vs {o.shape}")
    if p.size == 0:
        raise ValueError("Conjunto vacío")
    return float(np.sqrt(np.mean((p - o) ** 2)))


def mae(predicho: np.ndarray, observado: np.ndarray) -> float:
    p = np.asarray(predicho, dtype=float)
    o = np.asarray(observado, dtype=float)
    if p.shape != o.shape:
        raise ValueError(f"Formas incompatibles: {p.shape} vs {o.shape}")
    if p.size == 0:
        raise ValueError("Conjunto vacío")
    return float(np.mean(np.abs(p - o)))


def chi2_reducido(predicho: np.ndarray, observado: np.ndarray, sigma: float | np.ndarray) -> float:
    """χ²/dof con dof = n (no se descuentan parámetros ajustados).

    Se documenta así a propósito: el laboratorio no maquilla los grados de
    libertad, y el informe declara cuántos parámetros libres había.
    """
    p = np.asarray(predicho, dtype=float)
    o = np.asarray(observado, dtype=float)
    s = np.asarray(sigma, dtype=float)
    if np.any(s <= 0) or not np.all(np.isfinite(s)):
        raise ValueError("sigma debe ser positiva y finita")
    if p.size == 0:
        raise ValueError("Conjunto vacío")
    return float(np.mean(((p - o) / s) ** 2))


FUNCIONES: dict[str, Callable[..., float]] = {
    "rmse": rmse,
    "mae": mae,
    "chi2_reducido": chi2_reducido,
}

#: En qué dirección un valor menor es mejor.
DIRECCION_MENOR_ES_MEJOR: dict[str, bool] = {k: True for k in FUNCIONES}


def aplicar(metrica: str, predicho: np.ndarray, observado: np.ndarray,
            sigma: float | np.ndarray | None = None) -> float:
    """Evalúa la métrica pedida, resolviendo ``sigma`` si hace falta."""
    if metrica not in FUNCIONES:
        raise KeyError(f"Métrica desconocida '{metrica}' (usa {', '.join(FUNCIONES)})")
    if metrica == "chi2_reducido":
        s = 1.0 if sigma is None else sigma
        return chi2_reducido(predicho, observado, s)
    return FUNCIONES[metrica](predicho, observado)


def mejora_relativa(error_baseline: float, error_hipotesis: float) -> float:
    """1 − ε_hip/ε_base. Positiva = la hipótesis reduce el error."""
    if not np.isfinite(error_baseline) or error_baseline <= 0:
        raise ValueError(
            f"El baseline debe tener error finito y positivo (es {error_baseline!r}); "
            "sin él, la mejora relativa no está definida"
        )
    return float(1.0 - (error_hipotesis / error_baseline))


def ratio_errores(error_hipotesis: float, error_baseline: float) -> float | None:
    """ε_hip / ε_base. Acompaña a la mejora porque ésta sola se malinterpreta."""
    if not np.isfinite(error_baseline) or error_baseline <= 0:
        return None
    return float(error_hipotesis / error_baseline)


def formatear_ratio(ratio: float | None) -> str:
    """'1/109' cuando el ratio es pequeño y positivo; si no, decimal."""
    if ratio is None or not np.isfinite(ratio):
        return "—"
    if ratio <= 0:
        return f"{ratio:.3g}"
    if ratio < 0.5:
        return f"1/{1.0 / ratio:.0f}"
    return f"{ratio:.3g}"


# --------------------------------------------------------------------------
# Bootstrap
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Intervalo:
    """Resultado de un bootstrap de la mejora relativa."""

    mejora: float
    inferior: float
    superior: float
    nivel: float
    remuestreos: int
    exitos: int
    #: Submuestra de la distribución bootstrap, útil para graficarla.
    muestras: tuple[float, ...] = ()

    @property
    def excluye_cero(self) -> bool:
        return self.inferior > 0.0 or self.superior < 0.0

    @property
    def excluye_cero_positivo(self) -> bool:
        return self.inferior > 0.0

    def como_dict(self) -> dict[str, object]:
        return {
            "mejora": self.mejora,
            "ic_inferior": self.inferior,
            "ic_superior": self.superior,
            "nivel": self.nivel,
            "remuestreos": self.remuestreos,
            "exitos": self.exitos,
            "excluye_cero": self.excluye_cero,
        }


def bootstrap_mejora(
    observado: np.ndarray,
    predicho_hipotesis: np.ndarray,
    predicho_baseline: np.ndarray,
    metrica: str = "rmse",
    remuestreos: int = 2000,
    nivel: float = 0.95,
    semilla: int = 0,
    sigma: float | np.ndarray | None = None,
    devolver_muestras: bool = False,
    max_muestras: int = 800,
) -> Intervalo:
    """Intervalo de confianza percentil de la mejora relativa.

    Remuestrea filas de la muestra reservada (pares observado/predicción) y
    recalcula la mejora en cada remuestreo. Los remuestreos que producen un
    baseline degenerado (error nulo) se descartan y se cuentan.
    """
    o = np.asarray(observado, dtype=float)
    h = np.asarray(predicho_hipotesis, dtype=float)
    b = np.asarray(predicho_baseline, dtype=float)
    if not (o.shape == h.shape == b.shape):
        raise ValueError(f"Formas incompatibles: {o.shape}, {h.shape}, {b.shape}")
    if o.size < 3:
        raise ValueError("Se requieren al menos 3 filas para remuestrear")
    if remuestreos < 100:
        raise ValueError("remuestreos debe ser >= 100")

    e_hip = aplicar(metrica, h, o, sigma)
    e_base = aplicar(metrica, b, o, sigma)
    punto = mejora_relativa(e_base, e_hip)

    rng = np.random.default_rng(int(semilla))
    valores = np.empty(int(remuestreos), dtype=float)
    exitos = 0
    n = o.size
    for k in range(int(remuestreos)):
        idx = rng.integers(0, n, size=n)
        eb = aplicar(metrica, b[idx], o[idx], _sigma_idx(sigma, idx))
        eh = aplicar(metrica, h[idx], o[idx], _sigma_idx(sigma, idx))
        if eb <= 0 or not np.isfinite(eb) or not np.isfinite(eh):
            continue
        valores[exitos] = 1.0 - eh / eb
        exitos += 1
    if exitos < 0.5 * int(remuestreos):
        raise ValueError(
            f"Sólo {exitos}/{remuestreos} remuestreos fueron utilizables; "
            "el dataset es demasiado degenerado para este bootstrap"
        )
    alfa = (1.0 - float(nivel)) / 2.0
    inferior = float(np.quantile(valores[:exitos], alfa))
    superior = float(np.quantile(valores[:exitos], 1.0 - alfa))
    muestras: tuple[float, ...] = ()
    if devolver_muestras:
        paso = max(1, exitos // max(1, int(max_muestras)))
        muestras = tuple(float(v) for v in valores[:exitos:paso])
    return Intervalo(punto, inferior, superior, float(nivel), int(remuestreos),
                     exitos, muestras)


def _sigma_idx(sigma, idx):
    if sigma is None:
        return None
    s = np.asarray(sigma, dtype=float)
    return s[idx] if s.ndim else s


# --------------------------------------------------------------------------
# Reglas de decisión
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Decision:
    estado: str
    motivo: str


def decidir_mejora(intervalo: Intervalo, umbral: float) -> Decision:
    """Regla pre-registrada para la prueba contra el baseline.

    APROBADO  : mejora puntual ≥ umbral y el IC 95 % excluye el cero por arriba.
    FALLIDO   : el IC excluye el cero por abajo (la hipótesis es
                significativamente peor que el baseline).
    PENDIENTE : cualquier otra situación (mejora no significativa o
                insuficiente). No se declara fracaso sin evidencia.
    """
    if intervalo.excluye_cero_positivo and intervalo.mejora >= umbral:
        return Decision(
            "APROBADO",
            f"mejora {intervalo.mejora:.4f} ≥ umbral {umbral:.4f} e IC "
            f"[{intervalo.inferior:.4f}, {intervalo.superior:.4f}] excluye el cero",
        )
    if intervalo.superior < 0.0:
        return Decision(
            "FALLIDO",
            f"el IC de la mejora [{intervalo.inferior:.4f}, {intervalo.superior:.4f}] "
            "queda por debajo del cero: el baseline es significativamente mejor",
        )
    if intervalo.mejora >= umbral:
        return Decision(
            "PENDIENTE",
            f"mejora puntual {intervalo.mejora:.4f} ≥ umbral {umbral:.4f}, pero el IC "
            f"[{intervalo.inferior:.4f}, {intervalo.superior:.4f}] incluye el cero",
        )
    return Decision(
        "PENDIENTE",
        f"mejora {intervalo.mejora:.4f} < umbral {umbral:.4f}; el IC "
        f"[{intervalo.inferior:.4f}, {intervalo.superior:.4f}] no permite rechazar "
        "la equivalencia",
    )
