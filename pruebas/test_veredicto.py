"""Pruebas de la agregación de estados en un veredicto."""

from __future__ import annotations

import unittest

from lab.contrato import ResultadoPrueba
from lab.protocolo import ORDEN, TITULOS
from lab.veredicto import DESCRIPCION_VEREDICTO, VEREDICTOS, agregar, contar, matriz


def bateria(**estados) -> list[ResultadoPrueba]:
    """Doce pruebas, aprobadas salvo las que se indiquen."""
    return [
        ResultadoPrueba(codigo, TITULOS[codigo], estados.get(codigo, "APROBADO"), "detalle")
        for codigo in ORDEN
    ]


class TestAgregacion(unittest.TestCase):
    def test_todo_aprobado_es_corroborada(self):
        v = agregar(bateria())
        self.assertEqual(v.estado, "CORROBORADA_PROVISIONAL")
        self.assertTrue(v.es_positivo)

    def test_no_presentada_por_t02(self):
        self.assertEqual(agregar(bateria(T02="FALLIDO")).estado, "NO_PRESENTADA")

    def test_no_presentada_por_t03(self):
        self.assertEqual(agregar(bateria(T03="NO_PRESENTADA")).estado, "NO_PRESENTADA")

    def test_fuera_de_dominio_manda_sobre_lo_demas(self):
        v = agregar(bateria(T12="FALLIDO", T07="APROBADO"))
        self.assertEqual(v.estado, "FUERA_DE_DOMINIO")

    def test_no_generaliza_es_no_corroborada(self):
        self.assertEqual(agregar(bateria(T06="FALLIDO")).estado, "NO_CORROBORADA")

    def test_estabilidad_fallida_es_no_corroborada(self):
        self.assertEqual(agregar(bateria(T08="FALLIDO")).estado, "NO_CORROBORADA")

    def test_peor_que_el_baseline_es_refutada(self):
        self.assertEqual(agregar(bateria(T07="FALLIDO")).estado, "REFUTADA")

    def test_sin_mejora_significativa_es_no_corroborada(self):
        v = agregar(bateria(T07="PENDIENTE"))
        self.assertEqual(v.estado, "NO_CORROBORADA")
        self.assertIn("no demuestra", v.motivo)

    def test_sensible_al_diseno(self):
        self.assertEqual(agregar(bateria(T08="SENSIBLE_AL_DISENO")).estado,
                         "SENSIBLE_AL_DISENO")

    def test_preregistro_alterado_impide_corroborar(self):
        v = agregar(bateria(T04="FALLIDO"))
        self.assertEqual(v.estado, "PENDIENTE")
        self.assertIn("preregistro", v.motivo.lower())

    def test_preregistro_tardio_deja_pendiente(self):
        self.assertEqual(agregar(bateria(T04="PENDIENTE")).estado, "PENDIENTE")

    def test_incertidumbre_pendiente_deja_pendiente(self):
        self.assertEqual(agregar(bateria(T10="PENDIENTE")).estado, "PENDIENTE")

    def test_no_aplicable_no_bloquea(self):
        v = agregar(bateria(T05="NO_APLICABLE"))
        self.assertEqual(v.estado, "CORROBORADA_PROVISIONAL")

    def test_bloqueantes_incumplidas_se_listan(self):
        v = agregar(bateria(T09="FALLIDO", T11="PENDIENTE"))
        self.assertIn("T09", v.bloqueantes)
        self.assertIn("T11", v.bloqueantes)

    def test_conteo_y_matriz(self):
        resultados = bateria(T07="FALLIDO")
        self.assertEqual(contar(resultados)["FALLIDO"], 1)
        m = matriz(resultados)
        self.assertEqual(m["T07"], "FALLIDO")
        self.assertEqual(m["T01"], "APROBADO")

    def test_todos_los_veredictos_tienen_descripcion(self):
        for estado in VEREDICTOS:
            self.assertTrue(DESCRIPCION_VEREDICTO[estado].strip())

    def test_dict_serializable(self):
        d = agregar(bateria()).como_dict()
        self.assertEqual(d["estado"], "CORROBORADA_PROVISIONAL")
        self.assertIn("matriz", d)
        self.assertIn("conteo_estados", d)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
