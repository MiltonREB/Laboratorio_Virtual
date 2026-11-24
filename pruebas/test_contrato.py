"""Pruebas del contrato: parámetros, dominio y validación de salidas."""

from __future__ import annotations

import unittest

import numpy as np

from lab.contrato import (
    Dominio,
    Parametro,
    describir_parametros,
    verificar_salida,
)
from pruebas.ayudas import HipotesisDePrueba, hipotesis_con


class TestParametro(unittest.TestCase):
    def test_acepta_valor_finito(self):
        p = Parametro("g", 9.80665, "m/s^2")
        self.assertEqual(p.valor, 9.80665)
        self.assertTrue(p.congelado)

    def test_rechaza_no_finito(self):
        with self.assertRaises(ValueError):
            Parametro("g", float("nan"), "m/s^2")
        with self.assertRaises(ValueError):
            Parametro("g", float("inf"), "m/s^2")

    def test_rechaza_nombre_vacio(self):
        with self.assertRaises(ValueError):
            Parametro("", 1.0, "u")

    def test_convierte_a_dict(self):
        d = Parametro("k", 2, "1", congelado=False).como_dict()
        self.assertEqual(d["nombre"], "k")
        self.assertEqual(d["valor"], 2.0)
        self.assertFalse(d["congelado"])


class TestDominio(unittest.TestCase):
    def test_todo_dentro(self):
        d = Dominio("d", {"x": (0.0, 10.0)})
        fuera = d.contiene({"x": np.array([0.0, 5.0, 10.0])})
        self.assertEqual(fuera["x"], 0.0)

    def test_fraccion_fuera(self):
        d = Dominio("d", {"x": (0.0, 10.0)})
        fuera = d.contiene({"x": np.array([-1.0, 5.0, 20.0, 20.0])})
        self.assertAlmostEqual(fuera["x"], 0.75)

    def test_variable_ausente_cuenta_como_fuera(self):
        d = Dominio("d", {"z": (0.0, 1.0)})
        self.assertEqual(d.contiene({"x": np.array([1.0])})["z"], 1.0)

    def test_vacio_esta_dentro(self):
        d = Dominio("d", {"x": (0.0, 1.0)})
        self.assertEqual(d.contiene({"x": np.array([])})["x"], 0.0)


class TestContratoHipotesis(unittest.TestCase):
    def test_hipotesis_completa_no_tiene_faltas(self):
        self.assertEqual(HipotesisDePrueba().problemas_de_contrato(), [])

    def test_detecta_enunciado_vacio(self):
        faltas = hipotesis_con(enunciado="").problemas_de_contrato()
        self.assertTrue(any("enunciado" in f for f in faltas))

    def test_detecta_metrica_no_admitida(self):
        faltas = hipotesis_con(metrica="r2").problemas_de_contrato()
        self.assertTrue(any("métrica" in f for f in faltas))

    def test_detecta_umbral_fuera_de_rango(self):
        faltas = hipotesis_con(umbral_mejora=1.5).problemas_de_contrato()
        self.assertTrue(any("umbral_mejora" in f for f in faltas))

    def test_detecta_sensibilidad_negativa(self):
        faltas = hipotesis_con(umbral_sensibilidad=-1.0).problemas_de_contrato()
        self.assertTrue(any("umbral_sensibilidad" in f for f in faltas))

    def test_sensibilidad_ausente_o_cero_es_valida(self):
        for valor in (None, 0.0):
            faltas = hipotesis_con(umbral_sensibilidad=valor).problemas_de_contrato()
            self.assertFalse(any("umbral_sensibilidad" in f for f in faltas), valor)

    def test_detecta_factor_de_diferenciacion_invalido(self):
        faltas = hipotesis_con(factor_diferenciacion=0.0).problemas_de_contrato()
        self.assertTrue(any("factor_diferenciacion" in f for f in faltas))

    def test_detecta_parametro_sin_unidad(self):
        h = hipotesis_con()
        h.PARAMETROS = (Parametro("sin_unidad", 1.0, ""),)
        self.assertTrue(any("sin unidad" in f for f in h.problemas_de_contrato()))

    def test_detecta_baseline_igual_a_hipotesis(self):
        h = HipotesisDePrueba()
        h.baseline = h
        self.assertTrue(any("baseline" in f for f in h.problemas_de_contrato()))

    def test_detecta_observable_objetivo_ausente(self):
        faltas = hipotesis_con(observable_objetivo="z").problemas_de_contrato()
        self.assertTrue(any("no está en observables" in f for f in faltas))

    def test_firma_es_estable_entre_instancias(self):
        self.assertEqual(
            HipotesisDePrueba().firma_de_parametros(),
            HipotesisDePrueba().firma_de_parametros(),
        )

    def test_parametros_libres(self):
        libres = [p.nombre for p in HipotesisDePrueba().parametros_libres()]
        self.assertEqual(libres, ["b"])


class TestVerificarSalida(unittest.TestCase):
    def test_salida_correcta(self):
        self.assertEqual(verificar_salida({"y": np.zeros(3)}, ("y",), 3), [])

    def test_detecta_observable_ausente(self):
        errores = verificar_salida({}, ("y",), 3)
        self.assertTrue(any("no devolvió" in e for e in errores))

    def test_detecta_forma_incorrecta(self):
        errores = verificar_salida({"y": np.zeros(2)}, ("y",), 3)
        self.assertTrue(any("forma" in e for e in errores))

    def test_detecta_no_finitos(self):
        errores = verificar_salida({"y": np.array([1.0, np.nan])}, ("y",), 2)
        self.assertTrue(any("no finitos" in e for e in errores))


class TestDescribirParametros(unittest.TestCase):
    def test_vacio(self):
        self.assertEqual(describir_parametros([]), "sin parámetros")

    def test_marca_libres_y_fijos(self):
        texto = describir_parametros(
            [Parametro("a", 1.0, "u"), Parametro("b", 2.0, "u", congelado=False)]
        )
        self.assertIn("fijo", texto)
        self.assertIn("libre", texto)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
