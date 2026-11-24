"""Pruebas de las advertencias de viabilidad (v1.1.0).

Se calculan antes de la batería y no cambian el veredicto: estas pruebas
comprueban que detectan lo que dicen detectar y que no inventan avisos.
"""

from __future__ import annotations

import unittest

import numpy as np

from lab import viabilidad
from lab.contrato import Dominio, Parametro
from lab.preregistro import Verificacion
from pruebas.ayudas import conjunto_de_prueba, hipotesis_con


def _ctx(n=200):
    """Dataset sano: 120 filas de calibración y 80 reservadas."""
    return conjunto_de_prueba(n)


def _codigos(avisos):
    return {a.codigo for a in avisos}


class TestIdentificabilidad(unittest.TestCase):
    def test_sin_avisos_con_pocos_parametros(self):
        h = hipotesis_con(PARAMETROS=(
            Parametro("a", 1.0, "u"),
            Parametro("b", 1.0, "u", congelado=False),
        ))
        avisos = viabilidad.evaluar(h, _ctx())
        self.assertNotIn("V01", _codigos(avisos))

    def test_avisa_con_demasiados_parametros_libres(self):
        libres = tuple(
            Parametro(f"c{k}", 0.0, "1", congelado=False) for k in range(20)
        )
        h = hipotesis_con(PARAMETROS=libres)
        avisos = viabilidad.evaluar(h, _ctx())
        self.assertIn("V01", _codigos(avisos))
        aviso = next(a for a in avisos if a.codigo == "V01")
        self.assertIn("20 parámetros", aviso.mensaje)


class TestReservado(unittest.TestCase):
    def test_avisa_con_reservado_pequeno(self):
        avisos = viabilidad.evaluar(hipotesis_con(), conjunto_de_prueba(40))
        aviso = next(a for a in avisos if a.codigo == "V02")
        self.assertEqual(aviso.severidad, "media")

    def test_severidad_alta_con_menos_de_tres_filas(self):
        avisos = viabilidad.evaluar(hipotesis_con(), conjunto_de_prueba(4))
        aviso = next(a for a in avisos if a.codigo == "V02")
        self.assertEqual(aviso.severidad, "alta")


class TestUmbralEnElRuido(unittest.TestCase):
    """V03 usa el error del baseline como escala, no el ruido."""

    def _con_ruido(self, ruido=1.0):
        dataset = _ctx()
        object.__setattr__(dataset, "ruido", {"y": ruido})
        return dataset

    def test_avisa_si_lo_exigido_cabe_en_el_ruido(self):
        # umbral 0.01 sobre un baseline de error 0.01 exige 1e-4 < ruido 1.0
        h = hipotesis_con(umbral_mejora=0.01)
        avisos = viabilidad.evaluar(h, self._con_ruido(), error_baseline=0.01)
        self.assertIn("V03", _codigos(avisos))

    def test_no_avisa_si_lo_exigido_supera_el_ruido(self):
        h = hipotesis_con(umbral_mejora=0.10)
        avisos = viabilidad.evaluar(h, self._con_ruido(0.01), error_baseline=1.0)
        self.assertNotIn("V03", _codigos(avisos))

    def test_sin_error_del_baseline_no_se_puede_decidir(self):
        h = hipotesis_con(umbral_mejora=0.01)
        avisos = viabilidad.evaluar(h, self._con_ruido())
        self.assertNotIn("V03", _codigos(avisos))


class TestDominio(unittest.TestCase):
    def test_avisa_si_el_dominio_no_cubre_los_datos(self):
        h = hipotesis_con()
        h.dominio = Dominio("estrecho", {"x": (0.0, 1.0)})
        avisos = viabilidad.evaluar(h, _ctx())
        self.assertIn("V04", _codigos(avisos))

    def test_avisa_si_falta_una_variable_del_dominio(self):
        h = hipotesis_con()
        h.dominio = Dominio("otra", {"z": (0.0, 1.0)})
        avisos = viabilidad.evaluar(h, _ctx())
        aviso = next(a for a in avisos if a.codigo == "V04")
        self.assertIn("no tiene", aviso.mensaje)

    def test_sin_dominio_tambien_avisa(self):
        avisos = viabilidad.evaluar(hipotesis_con(dominio=None), _ctx())
        self.assertIn("V04", _codigos(avisos))


class TestIncertidumbre(unittest.TestCase):
    def test_avisa_si_no_hay_presupuesto(self):
        avisos = viabilidad.evaluar(
            hipotesis_con(incertidumbre_declarada=float("nan")), _ctx()
        )
        self.assertIn("V05", _codigos(avisos))

    def test_no_avisa_si_esta_declarado(self):
        avisos = viabilidad.evaluar(hipotesis_con(incertidumbre_declarada=0.1), _ctx())
        self.assertNotIn("V05", _codigos(avisos))


class TestPreregistro(unittest.TestCase):
    def _verif(self, estado):
        return Verificacion(estado_preregistro=estado, firma_actual="a" * 64)

    def test_avisa_de_los_estados_problematicos(self):
        for estado in ("AUSENTE", "RECIENTE", "TARDIO", "ALTERADO", "NO_PUBLICADO"):
            avisos = viabilidad.evaluar(hipotesis_con(), _ctx(), self._verif(estado))
            self.assertIn("V06", _codigos(avisos), estado)

    def test_no_avisa_si_el_sello_es_valido(self):
        avisos = viabilidad.evaluar(hipotesis_con(), _ctx(), self._verif("VALIDO"))
        self.assertNotIn("V06", _codigos(avisos))

    def test_sin_verificacion_no_hay_aviso(self):
        avisos = viabilidad.evaluar(hipotesis_con(), _ctx(), None)
        self.assertNotIn("V06", _codigos(avisos))


class TestFormato(unittest.TestCase):
    def test_cada_aviso_es_serializable(self):
        h = hipotesis_con(umbral_mejora=0.1)
        h.dominio = Dominio("estrecho", {"x": (0.0, 1.0)})
        avisos = viabilidad.evaluar(h, conjunto_de_prueba(40))
        self.assertTrue(avisos)
        for aviso in avisos:
            d = aviso.como_dict()
            self.assertIn(d["severidad"], ("alta", "media", "baja"))
            self.assertTrue(d["mensaje"])
            self.assertTrue(d["codigo"].startswith("V"))

    def test_ningun_aviso_usa_floats_no_serializables(self):
        avisos = viabilidad.evaluar(hipotesis_con(), conjunto_de_prueba(40))
        for aviso in avisos:
            for valor in aviso.como_dict().values():
                self.assertNotIsInstance(valor, np.floating)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
