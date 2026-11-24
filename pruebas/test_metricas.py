"""Pruebas de métricas, bootstrap y reglas de decisión."""

from __future__ import annotations

import unittest

import numpy as np

from lab.metricas import (
    Intervalo,
    aplicar,
    bootstrap_mejora,
    chi2_reducido,
    decidir_mejora,
    mae,
    mejora_relativa,
    rmse,
)


class TestErrores(unittest.TestCase):
    def test_rmse_conocido(self):
        self.assertAlmostEqual(rmse(np.array([1.0, 2.0]), np.array([1.0, 4.0])),
                               np.sqrt(2.0))

    def test_mae_conocido(self):
        self.assertAlmostEqual(mae(np.array([1.0, 2.0]), np.array([1.0, 4.0])), 1.0)

    def test_chi2_con_sigma(self):
        self.assertAlmostEqual(
            chi2_reducido(np.array([2.0]), np.array([1.0]), 1.0), 1.0
        )

    def test_chi2_rechaza_sigma_invalida(self):
        with self.assertRaises(ValueError):
            chi2_reducido(np.array([1.0]), np.array([1.0]), 0.0)

    def test_formas_incompatibles(self):
        with self.assertRaises(ValueError):
            rmse(np.array([1.0]), np.array([1.0, 2.0]))

    def test_conjunto_vacio(self):
        with self.assertRaises(ValueError):
            rmse(np.array([]), np.array([]))

    def test_aplicar_metrica_desconocida(self):
        with self.assertRaises(KeyError):
            aplicar("mse", np.array([1.0]), np.array([1.0]))

    def test_aplicar_chi2_usa_sigma_por_defecto(self):
        self.assertAlmostEqual(
            aplicar("chi2_reducido", np.array([2.0]), np.array([1.0])), 1.0
        )


class TestMejoraRelativa(unittest.TestCase):
    def test_mejora_positiva(self):
        self.assertAlmostEqual(mejora_relativa(1.0, 0.5), 0.5)

    def test_mejora_negativa(self):
        self.assertAlmostEqual(mejora_relativa(0.5, 1.0), -1.0)

    def test_baseline_degenerado(self):
        with self.assertRaises(ValueError):
            mejora_relativa(0.0, 0.5)


class TestBootstrap(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(0)
        self.obs = rng.normal(0.0, 1.0, size=200)
        self.bueno = self.obs + rng.normal(0.0, 0.1, size=200)
        self.malo = self.obs + rng.normal(0.0, 2.0, size=200)

    def test_hipotesis_mejor_da_ic_positivo(self):
        i = bootstrap_mejora(self.obs, self.bueno, self.malo, remuestreos=300, semilla=1)
        self.assertGreater(i.mejora, 0)
        self.assertGreater(i.inferior, 0)
        self.assertTrue(i.excluye_cero_positivo)

    def test_reproducible_con_la_misma_semilla(self):
        a = bootstrap_mejora(self.obs, self.bueno, self.malo, remuestreos=200, semilla=5)
        b = bootstrap_mejora(self.obs, self.bueno, self.malo, remuestreos=200, semilla=5)
        self.assertEqual((a.mejora, a.inferior, a.superior),
                         (b.mejora, b.inferior, b.superior))

    def test_semilla_distinta_cambia_el_intervalo(self):
        a = bootstrap_mejora(self.obs, self.bueno, self.malo, remuestreos=200, semilla=5)
        b = bootstrap_mejora(self.obs, self.bueno, self.malo, remuestreos=200, semilla=6)
        self.assertNotEqual(a.inferior, b.inferior)

    def test_formas_incompatibles(self):
        with self.assertRaises(ValueError):
            bootstrap_mejora(self.obs, self.bueno[:-1], self.malo)

    def test_pocas_filas(self):
        with self.assertRaises(ValueError):
            bootstrap_mejora(np.array([1.0, 2.0]), np.array([1.0, 2.0]),
                             np.array([1.0, 2.0]))

    def test_remuestreos_insuficientes(self):
        with self.assertRaises(ValueError):
            bootstrap_mejora(self.obs, self.bueno, self.malo, remuestreos=10)

    def test_puede_devolver_muestras_para_graficar(self):
        i = bootstrap_mejora(self.obs, self.bueno, self.malo, remuestreos=300,
                             semilla=1, devolver_muestras=True)
        self.assertTrue(i.muestras)
        self.assertLessEqual(len(i.muestras), 800)
        self.assertLessEqual(min(i.muestras), i.mejora + 1e-9)
        self.assertGreaterEqual(max(i.muestras), i.mejora - 1e-9)

    def test_sin_pedirlo_no_guarda_muestras(self):
        i = bootstrap_mejora(self.obs, self.bueno, self.malo, remuestreos=200)
        self.assertEqual(i.muestras, ())


class TestDecision(unittest.TestCase):
    def test_aprobado(self):
        d = decidir_mejora(Intervalo(0.5, 0.4, 0.6, 0.95, 100, 100), 0.1)
        self.assertEqual(d.estado, "APROBADO")

    def test_fallido_cuando_el_ic_queda_bajo_cero(self):
        d = decidir_mejora(Intervalo(-0.5, -0.6, -0.4, 0.95, 100, 100), 0.1)
        self.assertEqual(d.estado, "FALLIDO")

    def test_pendiente_por_ic_que_incluye_cero(self):
        d = decidir_mejora(Intervalo(0.5, -0.1, 0.6, 0.95, 100, 100), 0.1)
        self.assertEqual(d.estado, "PENDIENTE")

    def test_pendiente_por_umbral_no_alcanzado(self):
        d = decidir_mejora(Intervalo(0.02, 0.01, 0.03, 0.95, 100, 100), 0.1)
        self.assertEqual(d.estado, "PENDIENTE")

    def test_mejora_negativa_sin_significancia_no_es_fallo(self):
        d = decidir_mejora(Intervalo(-0.05, -0.2, 0.1, 0.95, 100, 100), 0.1)
        self.assertEqual(d.estado, "PENDIENTE")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
