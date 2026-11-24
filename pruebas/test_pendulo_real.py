"""Paso 3.4: el pipeline completo sobre un CSV con el esquema real.

El CSV es sintético (``pruebas/fixtures/``), pero tiene las columnas que tendrá
la medición real: ``u_T_s`` incluida. Lo que se prueba aquí es que el
laboratorio **no falla de esquema** y que usa de verdad la incertidumbre
experimental y la g estimada.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lab import preregistro, viabilidad
from lab.contrato import ESTADOS
from lab.datos import Manifiesto
from lab.evaluador import evaluar_hipotesis
from lab.ingesta import registrar
from lab.registro import cargar_registro
from lab.veredicto import VEREDICTOS
from pruebas.ayudas import espacio_temporal

RAIZ = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "pendulo_medido_fixture.csv"
G_USADA = 9.7923


class TestAjusteDeG(unittest.TestCase):
    def test_recupera_la_gravedad_de_los_datos(self):
        import numpy as np
        from hipotesis.pendulo_real import ajustar_g

        rng = np.random.default_rng(1)
        L = rng.uniform(0.6, 1.8, size=200)
        T = 2.0 * np.pi * np.sqrt(L / 9.75) + rng.normal(0, 1e-4, size=200)
        self.assertAlmostEqual(ajustar_g(L, T), 9.75, places=2)

    def test_rechaza_datos_no_utilizables(self):
        import numpy as np
        from hipotesis.pendulo_real import ajustar_g

        with self.assertRaises(ValueError):
            ajustar_g(np.zeros(5), np.ones(5))


class TestPipelineConDatosMedidos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.datos = espacio_temporal("datos_reales")
        registrar(FIXTURE, cls.datos, id_="pendulo_real",
                  procedencia="fixture sintético con esquema real")
        cls.manifiesto = Manifiesto.desde_directorio(cls.datos)
        cls.registro = cargar_registro(RAIZ / "hipotesis")

    def _evaluar(self, remuestreos=300, particiones=2):
        resultado_datos = espacio_temporal("resultados_reales")
        h = self.registro.obtener("pendulo_amplitud_real")
        preregistro.sellar(
            h, resultado_datos,
            momento=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        return evaluar_hipotesis(
            h, self.manifiesto, resultado_datos,
            remuestreos=remuestreos, particiones=particiones,
        )

    def test_las_doce_pruebas_se_ejecutan_sin_excepcion(self):
        resultado = self._evaluar()
        self.assertEqual(len(resultado.pruebas), 12)
        self.assertEqual([p.codigo for p in resultado.pruebas],
                         ["T01", "T02", "T03", "T04", "T05", "T06",
                          "T07", "T08", "T09", "T10", "T11", "T12"])
        for prueba in resultado.pruebas:
            self.assertIn(prueba.estado, ESTADOS, prueba.codigo)

    def test_el_veredicto_pertenece_al_vocabulario(self):
        resultado = self._evaluar()
        self.assertIn(resultado.veredicto.estado, VEREDICTOS)

    def test_el_dataset_expone_incertidumbre_experimental(self):
        conjunto = self.manifiesto.cargar("pendulo_real")
        self.assertIn("T_s", conjunto.incertidumbres)
        media = conjunto.incertidumbre_media("T_s")
        self.assertIsNotNone(media)
        self.assertGreater(media, 0)
        self.assertLess(media, 0.01)

    def test_el_baseline_ajusta_g(self):
        resultado = self._evaluar()
        baseline = resultado.datos["hipotesis"]["baseline"]
        self.assertTrue(baseline["ajustado"])
        g = baseline["parametros_ajustados"]["g"]
        # El estimador usa el cuartil inferior de amplitud porque ignora la
        # corrección: queda un sesgo residual a la baja del orden del 0.3 %.
        # Se acepta como confondo conocido, no se ajusta la tolerancia al
        # resultado: el sesgo favorece levemente a la hipótesis.
        self.assertLess(g, G_USADA)
        self.assertLess(abs(g - G_USADA), 0.05)

    def test_t10_usa_el_presupuesto_experimental(self):
        resultado = self._evaluar()
        t10 = next(p for p in resultado.datos["pruebas"] if p["codigo"] == "T10")
        self.assertIsNotNone(t10["evidencia"]["presupuesto_combinado"])
        self.assertGreater(t10["evidencia"]["presupuesto_combinado"], 0)
        self.assertIsNotNone(t10["evidencia"]["incertidumbre_experimental"])

    def test_viabilidad_no_avisa_si_el_dataset_trae_incertidumbre(self):
        """Aunque no se declare un número, la experimental cubre el presupuesto."""
        h = self.registro.obtener("pendulo_amplitud_real")
        avisos = viabilidad.evaluar(h, self.manifiesto.cargar("pendulo_real"))
        self.assertNotIn("V05", {a.codigo for a in avisos})

    def test_el_informe_y_el_resumen_se_escriben(self):
        resultado = self._evaluar()
        for nombre in ("resumen.json", "INFORME.md", "matriz.csv", "predicciones.csv"):
            self.assertTrue((resultado.corrida / nombre).is_file(), nombre)

    def test_no_se_puede_evaluar_sin_el_dataset_registrado(self):
        from lab.evaluador import ErrorDeEvaluacion

        h = self.registro.obtener("pendulo_amplitud_real")
        with self.assertRaises(ErrorDeEvaluacion):
            evaluar_hipotesis(
                h, Manifiesto.desde_directorio(RAIZ / "datos"),
                espacio_temporal("sin_dataset"), guardar=False,
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
