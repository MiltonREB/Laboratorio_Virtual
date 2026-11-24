"""Prueba el adaptador contra código real: el paquete ``prdu_atomico`` instalado.

No evalúa ninguna hipótesis ni afirma física: comprueba que un modelo heredado
se puede envolver, que respeta el contrato del laboratorio y que reproduce
exactamente la función original.

    python herramientas/prueba_adaptador.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from lab.adaptadores import modelo_desde_funcion  # noqa: E402
from lab.contrato import Parametro, verificar_salida  # noqa: E402


def main() -> int:
    try:
        from prdu_atomico.core import electron_acceleration_from_vcm
    except ImportError as exc:
        print(f"No se pudo importar prdu_atomico: {exc}")
        print("Instala el paquete (pip install -e <ruta v74>) o usa otro módulo.")
        return 2

    modelo = modelo_desde_funcion(
        id="legado_prdu_aceleracion",
        nombre="PRDU v74: aceleración eléctrica a = |q|E/m",
        funcion=lambda variables, parametros: {
            "a_m_s2": electron_acceleration_from_vcm(variables["E_vcm"])
        },
        observables=("a_m_s2",),
        requiere=("E_vcm",),
        version="0.74.0",
        supuestos=(
            "Envoltorio del paquete prdu_atomico instalado. No interpreta "
            "a_electrica como aceleración gravitacional."
        ),
        parametros=(),
    )

    campos = np.array([0.0, 1.0, 10.0, 100.0, 1000.0])
    salida = modelo.predecir({"E_vcm": campos}, {})
    errores = verificar_salida(salida, modelo.observables, campos.size)

    esperado = electron_acceleration_from_vcm(campos)
    identico = np.array_equal(salida["a_m_s2"], esperado)
    determinista = np.array_equal(
        modelo.predecir({"E_vcm": campos}, {})["a_m_s2"], salida["a_m_s2"]
    )

    print(f"modelo:      {modelo.id} v{modelo.version}")
    print(f"observables: {modelo.observables}  variables: {modelo.requiere}")
    print(f"contrato:    {'OK' if not errores else errores}")
    print(f"reproduce la función original: {identico}")
    print(f"determinista: {determinista}")
    print()
    print(f"{'E (V/cm)':>10} {'a (m/s^2)':>16}")
    for campo, valor in zip(campos, salida["a_m_s2"]):
        print(f"{campo:10.1f} {valor:16.6e}")

    # Un adaptador también debe fallar de forma explícita.
    fallo_esperado = False
    try:
        modelo.predecir({"E_vcm": np.array([-1.0])}, {})
    except Exception as exc:
        fallo_esperado = True
        print(f"\nentrada inválida rechazada: {type(exc).__name__}")

    bien = not errores and identico and determinista and fallo_esperado
    print(f"\nresultado: {'OK' if bien else 'REVISAR'}")
    return 0 if bien else 1


if __name__ == "__main__":
    raise SystemExit(main())
