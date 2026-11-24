"""Pruebas de la agregación de estados en un veredicto (protocolo v1.1.0)."""

from __future__ import annotations

import unittest

from lab.catalogo import ResultadoVerificacion
from lab.contrato import ResultadoPrueba
from lab.protocolo import ORDEN, TITULOS
from lab.veredicto import (
    DESCRIPCION_VEREDICTO,
    VEREDICTOS,
    VERIFICACIONES_VINCULANTES,
    agregar,
    contar,
    matriz,
)


def bateria(**estados) -> list[ResultadoPrueba]:
    """Doce pruebas, aprobadas salvo las que se indiquen."""
    return [
        ResultadoPrueba(codigo, TITULOS[codigo], estados.get(codigo, "APROBADO"), "detalle")
        for codigo in ORDEN
    ]


def bateria_con_ausencia(**estados) -> list[ResultadoPrueba]:
    pruebas = []
    for codigo in ORDEN:
        estado = estados.get(codigo, "APROBADO")
        pruebas.append(ResultadoPrueba(
            codigo, TITULOS[codigo], estado, "detalle",
            es_ausencia=(codigo in estados.get("_ausencia", ())),
        ))
    return pruebas


def _verificacion(codigo: str, estado: str = "EJECUTADA", **evidencia):
    return ResultadoVerificacion(
        codigo=codigo,
        titulo=codigo,
        estado=estado,
        motivo="motivo de prueba",
        evidencia=evidencia,
        vinculante=codigo in VERIFICACIONES_VINCULANTES,
    )


def verificaciones(
    o01: str = "EJECUTADA",
    o04: str = "EJECUTADA",
    gana_a_todos: bool = True,
    supera_baseline: bool = True,
) -> list[ResultadoVerificacion]:
    return [
        _verificacion("O01", o01, gana_a_todos=gana_a_todos),
        _verificacion("O02"),
        _verificacion("O03", "NO_REQUERIDA"),
        _verificacion("O04", o04, supera_baseline=supera_baseline),
        _verificacion("O05", "NO_REQUERIDA"),
    ]


class TestAgregacion(unittest.TestCase):
    def test_todo_aprobado_y_verificaciones_ok_es_corroborada(self):
        v = agregar(bateria(), verificaciones())
        self.assertEqual(v.estado, "CORROBORADA_PROVISIONAL")
        self.assertTrue(v.es_positivo)

    def test_sin_o01_el_maximo_es_preliminar(self):
        v = agregar(bateria(), verificaciones(o01="NO_REQUERIDA"))
        self.assertEqual(v.estado, "PRELIMINAR")
        self.assertIn("O01", v.motivo)

    def test_sin_o04_el_maximo_es_preliminar(self):
        v = agregar(bateria(), verificaciones(o04="NO_REQUERIDA"))
        self.assertEqual(v.estado, "PRELIMINAR")
        self.assertIn("O04", v.motivo)

    def test_sin_verificaciones_el_maximo_es_preliminar(self):
        self.assertEqual(agregar(bateria()).estado, "PRELIMINAR")

    def test_no_ganar_a_todos_los_baselines_es_preliminar(self):
        v = agregar(bateria(), verificaciones(gana_a_todos=False))
        self.assertEqual(v.estado, "PRELIMINAR")
        self.assertIn("baselines alternativos", v.motivo)

    def test_no_superar_el_holdout_es_no_corroborada(self):
        v = agregar(bateria(), verificaciones(supera_baseline=False))
        self.assertEqual(v.estado, "NO_CORROBORADA")

    def test_ausencia_de_prediccion_es_no_presentada(self):
        pruebas = bateria_con_ausencia(_ausencia=("T03",), T03="PENDIENTE")
        self.assertEqual(agregar(pruebas, verificaciones()).estado, "NO_PRESENTADA")

    def test_t02_no_falsable_es_no_presentada(self):
        pruebas = bateria_con_ausencia(_ausencia=("T02",), T02="FALLIDO")
        self.assertEqual(agregar(pruebas, verificaciones()).estado, "NO_PRESENTADA")

    def test_fuera_de_dominio_manda(self):
        v = agregar(bateria(T12="FALLIDO"), verificaciones())
        self.assertEqual(v.estado, "FUERA_DE_DOMINIO")

    def test_no_generaliza_es_no_corroborada(self):
        self.assertEqual(agregar(bateria(T06="FALLIDO"), verificaciones()).estado,
                         "NO_CORROBORADA")

    def test_sin_mejora_significativa_es_no_corroborada(self):
        v = agregar(bateria(T07="PENDIENTE"), verificaciones())
        self.assertEqual(v.estado, "NO_CORROBORADA")

    def test_sensible_al_diseno(self):
        self.assertEqual(agregar(bateria(T08="SENSIBLE"), verificaciones()).estado,
                         "SENSIBLE")

    def test_preregistro_alterado_impide_corroborar(self):
        v = agregar(bateria(T04="FALLIDO"), verificaciones())
        self.assertEqual(v.estado, "PENDIENTE")
        self.assertIn("preregistro", v.motivo.lower())

    def test_incertidumbre_pendiente_deja_pendiente(self):
        self.assertEqual(agregar(bateria(T10="PENDIENTE"), verificaciones()).estado,
                         "PENDIENTE")

    def test_t05_vacuo_no_bloquea(self):
        pruebas = bateria()
        pruebas[4] = ResultadoPrueba("T05", TITULOS["T05"], "APROBADO", "vacuo",
                                     {"vacuo": True})
        self.assertEqual(agregar(pruebas, verificaciones()).estado,
                         "CORROBORADA_PROVISIONAL")

    def test_no_existe_el_veredicto_refutada(self):
        for estado in VEREDICTOS:
            self.assertNotIn("REFUTAD", estado)
        self.assertNotIn("REFUTADA", DESCRIPCION_VEREDICTO)

    def test_ningun_veredicto_usa_estados_antiguos(self):
        for estado in VEREDICTOS:
            self.assertNotIn("SENSIBLE_AL_DISENO", estado)
            self.assertNotIn("NO_APLICABLE", estado)

    def test_bloqueantes_incumplidas_se_listan(self):
        v = agregar(bateria(T09="FALLIDO", T11="PENDIENTE"), verificaciones())
        self.assertIn("T09", v.bloqueantes)
        self.assertIn("T11", v.bloqueantes)

    def test_conteo_y_matriz(self):
        resultados = bateria(T07="PENDIENTE")
        self.assertEqual(contar(resultados)["PENDIENTE"], 1)
        m = matriz(resultados)
        self.assertEqual(m["T07"], "PENDIENTE")
        self.assertEqual(m["T01"], "APROBADO")

    def test_todos_los_veredictos_tienen_descripcion(self):
        for estado in VEREDICTOS:
            self.assertTrue(DESCRIPCION_VEREDICTO[estado].strip())

    def test_dict_serializable(self):
        d = agregar(bateria(), verificaciones()).como_dict()
        self.assertEqual(d["estado"], "CORROBORADA_PROVISIONAL")
        self.assertIn("matriz", d)
        self.assertIn("conteo_estados", d)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
