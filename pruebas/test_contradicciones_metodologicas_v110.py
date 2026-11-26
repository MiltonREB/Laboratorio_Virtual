"""Regresiones RED/GREEN sobre funciones REALES, commit cf030202.

No ejecuta duplicados simplificados: importa los módulos originales lab.*.
El test compara la misma señal física en m y cm: chi2 es adimensional.
"""
import unittest
import numpy as np

from pruebas.ayudas import contexto, hipotesis_con
from lab.protocolo import (
    t02_falsabilidad, t03_prediccion_diferenciadora,
    t06_fuera_de_muestra, t10_incertidumbre, ORDEN, TITULOS,
)
from lab.contrato import ResultadoPrueba
from lab.veredicto import agregar


class TestRegresionesMetodologicas(unittest.TestCase):
    def test_f01_prediccion_constante_falsable(self):
        r = t02_falsabilidad(contexto(pred_hip=np.full(4, 9.81)))
        self.assertEqual(r.estado, "APROBADO", r.detalle)
        self.assertFalse(r.es_ausencia)

    def test_x01_t03_invariante_de_unidades_si_metrica_chi2(self):
        def evaluar(escala):
            base = np.zeros(4)
            hip = np.full(4, 0.2 * escala)
            obs = np.full(4, 0.6 * escala)
            c = contexto(
                hipotesis=hipotesis_con(metrica="chi2_reducido", umbral_sensibilidad=0.0),
                observado=obs, pred_hip=hip, pred_base=base,
                errores_reservado={"hipotesis": 0.5, "baseline": 1.0},
            )
            return t03_prediccion_diferenciadora(c)
        a, b = evaluar(1.0), evaluar(100.0)
        self.assertEqual(a.estado, b.estado, (a.evidencia, b.evidencia))

    def test_x01_t06_invariante_de_unidades_si_metrica_chi2(self):
        def evaluar(u):
            c = contexto(
                hipotesis=hipotesis_con(metrica="chi2_reducido", incertidumbre_declarada=u),
                errores_reservado={"hipotesis": 4.0, "baseline": 1.0},
            )
            return t06_fuera_de_muestra(c)
        a, b = evaluar(0.1), evaluar(10.0)
        self.assertEqual(a.estado, b.estado, (a.evidencia, b.evidencia))
        self.assertEqual(a.estado, "APROBADO")

    def test_f06_t10_invariante_de_unidades_si_metrica_chi2(self):
        def evaluar(u):
            c = contexto(
                hipotesis=hipotesis_con(metrica="chi2_reducido", incertidumbre_declarada=u),
                errores_reservado={"hipotesis": 4.0, "baseline": 1.0},
            )
            return t10_incertidumbre(c)
        a, b = evaluar(0.1), evaluar(10.0)
        self.assertEqual(a.estado, b.estado, (a.evidencia, b.evidencia))
        self.assertEqual(a.estado, "APROBADO")

    def test_f12_preregistro_alterado_debe_impedir_veredicto_sobre_datos(self):
        pruebas = [
            ResultadoPrueba(
                codigo, TITULOS[codigo],
                "FALLIDO" if codigo == "T04"
                else ("PENDIENTE" if codigo == "T07" else "APROBADO"),
                "prueba de auditoria",
            )
            for codigo in ORDEN
        ]
        self.assertEqual(agregar(pruebas).estado, "PENDIENTE")

    def test_control_t02_no_finito_sigue_fallando(self):
        r = t02_falsabilidad(contexto(pred_hip=np.array([1.0, np.nan, 2.0, 3.0])))
        self.assertEqual(r.estado, "FALLIDO")

    def test_control_t03_identidad_sigue_pendiente(self):
        v = np.array([1.0, 2.0, 3.0, 4.0])
        c = contexto(pred_hip=v, pred_base=v)
        self.assertEqual(t03_prediccion_diferenciadora(c).estado, "PENDIENTE")

    def test_control_t06_chi2_extremo_sigue_fallando(self):
        c = contexto(
            hipotesis=hipotesis_con(metrica="chi2_reducido"),
            errores_reservado={"hipotesis": 100.0, "baseline": 1.0},
        )
        self.assertEqual(t06_fuera_de_muestra(c).estado, "FALLIDO")

    def test_control_t10_chi2_extremo_sigue_fallando(self):
        c = contexto(
            hipotesis=hipotesis_con(metrica="chi2_reducido"),
            errores_reservado={"hipotesis": 100.0, "baseline": 1.0},
        )
        self.assertEqual(t10_incertidumbre(c).estado, "FALLIDO")

    def test_control_t07_pendiente_con_preregistro_valido(self):
        pruebas = [
            ResultadoPrueba(codigo, TITULOS[codigo],
                "PENDIENTE" if codigo == "T07" else "APROBADO", "control")
            for codigo in ORDEN
        ]
        self.assertEqual(agregar(pruebas).estado, "NO_CORROBORADA")


if __name__ == "__main__":
    unittest.main()
