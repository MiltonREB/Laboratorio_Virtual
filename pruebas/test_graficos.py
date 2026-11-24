"""Pruebas de los gráficos SVG de cada prueba."""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from lab import graficos
from lab.protocolo import ORDEN

RESUMEN_MINIMO = {
    "hipotesis": {
        "enunciado": "x", "prediccion_diferenciadora": "y",
        "dominio": {"rango": {"x": [0, 1]}}, "unidad_observable": "u",
        "baseline": {"id": "b"}, "metrica": "rmse",
        "umbral_mejora": 0.1, "umbral_sensibilidad": 0.01,
        "parametros": [{"nombre": "a", "valor": 1, "congelado": True}],
    },
    "dataset": {"id": "d", "calibracion": 10, "reservado": 6, "filas": 16},
    "comparacion": {
        "intervalo": {"mejora": 0.5, "ic_inferior": 0.4, "ic_superior": 0.6,
                      "remuestreos": 200},
        "histograma_bootstrap": {
            "bordes": [0.3, 0.4, 0.5, 0.6, 0.7],
            "cuentas": [1, 4, 9, 3],
        },
    },
    "estabilidad": {
        "ensayos": [{"particion": 0, "mejora": 0.2}, {"particion": 1, "mejora": -0.1}],
        "umbral_mejora": 0.1,
        "mejora_media": 0.05,
    },
    "control_nulo": {"mejora": -0.01, "ic_inferior": -0.05, "ic_superior": 0.02},
    "reproducibilidad": {
        "prediccion_identica": True, "bootstrap_identico": True,
        "sha_prediccion_1": "a" * 64, "sha_prediccion_2": "a" * 64,
    },
    "preregistro": {"existe": True, "coincide": True, "tardio": False,
                    "firma_actual": "b" * 64},
    "pruebas": [
        {"codigo": "T03", "estado": "APROBADO",
         "evidencia": {"umbral_sensibilidad": 0.01}},
        {"codigo": "T06", "estado": "APROBADO",
         "evidencia": {"escala": 0.1, "factor_admitido": 5.0}},
        {"codigo": "T10", "estado": "APROBADO",
         "evidencia": {"razon_error_sobre_presupuesto": 1.2}},
        {"codigo": "T12", "estado": "APROBADO",
         "evidencia": {"rango_declarado": {"x": [0.0, 10.0]},
                       "observado": {"x": {"min": 1.0, "max": 9.0, "filas": 12}},
                       "fraccion_fuera": {"x": 0.0}}},
    ],
    "verificaciones": [
        {"codigo": "O02", "estado": "EJECUTADA", "ejecutada": True,
         "evidencia": {"bloques": [
             {"bloque": 1, "mejora": 0.3}, {"bloque": 2, "mejora": 0.2},
             {"bloque": 3, "mejora": 0.1}]}},
    ],
}

PREDICCIONES = [
    {"particion": "reservado", "observado": 1.0 + 0.1 * i,
     "hipotesis": 1.02 + 0.1 * i, "baseline": 1.5 + 0.1 * i}
    for i in range(12)
]


class TestGraficos(unittest.TestCase):
    def test_hay_grafico_para_cada_prueba(self):
        self.assertEqual(sorted(graficos.FUNCIONES), sorted(ORDEN))

    def test_cada_grafico_es_svg_valido(self):
        for codigo in ORDEN:
            with self.subTest(codigo=codigo):
                svg = graficos.grafico_prueba(codigo, RESUMEN_MINIMO, PREDICCIONES)
                self.assertTrue(svg.startswith("<svg"), codigo)
                self.assertTrue(svg.endswith("</svg>"), codigo)
                ET.fromstring(svg)  # falla si el XML está mal formado

    def test_resumen_vacio_no_lanza(self):
        for codigo in ORDEN:
            with self.subTest(codigo=codigo):
                svg = graficos.grafico_prueba(codigo, {}, [])
                ET.fromstring(svg)

    def test_resumen_con_nulos_no_lanza(self):
        resumen = {"hipotesis": None, "dataset": None, "comparacion": None,
                   "preregistro": None, "control_nulo": None,
                   "reproducibilidad": None, "estabilidad": None,
                   "pruebas": None, "verificaciones": None}
        for codigo in ORDEN:
            with self.subTest(codigo=codigo):
                svg = graficos.grafico_prueba(codigo, resumen, [])
                ET.fromstring(svg)

    def test_codigo_desconocido_devuelve_aviso(self):
        svg = graficos.grafico_prueba("T99", RESUMEN_MINIMO, PREDICCIONES)
        self.assertIn("Sin gráfico", svg)

    def test_verificacion_ejecutada_tiene_grafico(self):
        svg = graficos.grafico_verificacion("O02", RESUMEN_MINIMO)
        self.assertIsNotNone(svg)
        ET.fromstring(svg)

    def test_verificacion_no_ejecutada_no_tiene_grafico(self):
        self.assertIsNone(graficos.grafico_verificacion("O01", RESUMEN_MINIMO))
        self.assertIsNone(graficos.grafico_verificacion("O05", RESUMEN_MINIMO))


def _coordenadas_fuera(svg: str, ancho: float = 340.0, alto: float = 190.0):
    """Coordenadas que se salen del lienzo (regresión de escala)."""
    raiz = ET.fromstring(svg)
    fuera = []
    for nodo in raiz.iter():
        for clave, limite in (("x", ancho), ("cx", ancho), ("x1", ancho),
                              ("x2", ancho), ("y", alto), ("cy", alto),
                              ("y1", alto), ("y2", alto)):
            valor = nodo.get(clave)
            if valor is None:
                continue
            try:
                v = float(valor)
            except ValueError:
                continue
            if v < -1 or v > limite + 1:
                fuera.append((clave, v))
    return fuera


class TestEscalas(unittest.TestCase):
    """Las líneas de referencia no deben forzar coordenadas absurdas.

    Caso real detectado: una mejora de 0.99 con umbral 0.1 dibujaba el cero a
    x = -42605. El gráfico debe escalar a sus datos y anotar fuera de escala.
    """

    def _resumen_extremo(self):
        resumen = {
            "hipotesis": {"umbral_mejora": 0.1, "umbral_sensibilidad": 1e-4,
                          "metrica": "rmse", "parametros": [],
                          "dominio": {"rango": {"x": [0, 1]}},
                          "unidad_observable": "u", "baseline": {"id": "b"},
                          "enunciado": "e", "prediccion_diferenciadora": "p"},
            "comparacion": {
                "intervalo": {"mejora": 0.9908, "ic_inferior": 0.9887,
                              "ic_superior": 0.9925, "remuestreos": 2000},
                "histograma_bootstrap": {
                    "bordes": [0.985, 0.99, 0.995],
                    "cuentas": [2, 10],
                },
            },
            "estabilidad": {"ensayos": [
                {"particion": 0, "mejora": 0.9908},
                {"particion": 1, "mejora": 0.9910},
            ], "umbral_mejora": 0.1, "mejora_media": 0.9909},
            "pruebas": [
                {"codigo": "T03", "evidencia": {"umbral_sensibilidad": 1e-4}},
                {"codigo": "T06", "evidencia": {"escala": 1e-3,
                                                "factor_admitido": 5.0}},
            ],
        }
        predicciones = [
            {"particion": "reservado", "observado": 2.0,
             "hipotesis": 2.001, "baseline": 1.8}
            for _ in range(10)
        ]
        return resumen, predicciones

    def test_referencias_lejanas_no_rompen_el_lienzo(self):
        resumen, predicciones = self._resumen_extremo()
        for codigo in ("T03", "T06", "T07", "T08"):
            with self.subTest(codigo=codigo):
                svg = graficos.grafico_prueba(codigo, resumen, predicciones)
                self.assertEqual(_coordenadas_fuera(svg), [], codigo)

    def test_avisa_cuando_la_referencia_queda_fuera_de_escala(self):
        resumen, predicciones = self._resumen_extremo()
        svg = graficos.grafico_prueba("T07", resumen, predicciones)
        self.assertIn("fuera de escala", svg)

    def test_banda_asimetrica_no_se_sale_del_lienzo(self):
        """Caso real: ΔO siempre positivo y solo un lado de la banda cabe."""
        resumen = {
            "hipotesis": {"umbral_mejora": 0.1, "factor_diferenciacion": 1.0,
                          "umbral_sensibilidad": None, "unidad_observable": "s"},
            "pruebas": [{"codigo": "T03", "evidencia": {
                "exigido": 0.089, "escala_baseline": 0.089,
                "factor_diferenciacion": 1.0}}],
        }
        predicciones = [
            {"particion": "reservado", "observado": 1.0,
             "hipotesis": 2.0 + 0.01 * i, "baseline": 1.98 + 0.01 * i}
            for i in range(20)
        ]
        svg = graficos.grafico_prueba("T03", resumen, predicciones)
        self.assertEqual(_coordenadas_fuera(svg), [])
        self.assertIn("fuera de escala", svg)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
