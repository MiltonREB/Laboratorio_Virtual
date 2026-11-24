"""Pruebas del catálogo: precondiciones y motivos de las verificaciones."""

from __future__ import annotations

import unittest

from lab import catalogo
from pruebas.ayudas import contexto, hipotesis_con


def _por_codigo(resultados):
    return {r.codigo: r for r in resultados}


class TestDefiniciones(unittest.TestCase):
    def test_doce_pruebas_de_protocolo(self):
        self.assertEqual(len(catalogo.PRUEBAS_PROTOCOLO), 12)
        self.assertEqual(
            [d.codigo for d in catalogo.PRUEBAS_PROTOCOLO],
            [f"T{i:02d}" for i in range(1, 13)],
        )

    def test_cinco_verificaciones_opcionales(self):
        self.assertEqual(len(catalogo.VERIFICACIONES_OPCIONALES), 5)

    def test_o01_y_o04_son_vinculantes(self):
        por_codigo = {d.codigo: d for d in catalogo.VERIFICACIONES_OPCIONALES}
        self.assertTrue(por_codigo["O01"].vinculante)
        self.assertTrue(por_codigo["O04"].vinculante)

    def test_o02_o03_y_o05_no_son_vinculantes(self):
        por_codigo = {d.codigo: d for d in catalogo.VERIFICACIONES_OPCIONALES}
        for codigo in ("O02", "O03", "O05"):
            self.assertFalse(por_codigo[codigo].vinculante, codigo)

    def test_toda_definicion_tiene_proposito_y_condicion(self):
        for definicion in catalogo.definiciones().values():
            self.assertTrue(definicion.proposito.strip(), definicion.codigo)
            self.assertTrue(definicion.no_requerida_cuando.strip(), definicion.codigo)

    def test_codigos_unicos(self):
        codigos = [d.codigo for d in (*catalogo.PRUEBAS_PROTOCOLO,
                                       *catalogo.VERIFICACIONES_OPCIONALES)]
        self.assertEqual(len(codigos), len(set(codigos)))


class TestEjecucion(unittest.TestCase):
    def _contexto_largo(self, n: int = 40):
        import numpy as np

        x = np.arange(n, dtype=float)
        obs = 2.0 * x + 1.0
        return contexto(
            observado=obs,
            pred_hip=obs + 0.01,
            pred_base=obs + 0.5,
        )

    def test_devuelve_las_cinco_verificaciones(self):
        resultados = catalogo.ejecutar(contexto())
        self.assertEqual([r.codigo for r in resultados],
                         ["O01", "O02", "O03", "O04", "O05"])

    def test_por_defecto_casi_todas_no_requeridas(self):
        resultados = _por_codigo(catalogo.ejecutar(contexto()))
        for codigo in ("O01", "O03", "O04", "O05"):
            self.assertEqual(resultados[codigo].estado, "NO_REQUERIDA", codigo)
            self.assertTrue(resultados[codigo].motivo.strip(), codigo)

    def test_o02_se_ejecuta_con_suficientes_filas(self):
        resultados = _por_codigo(catalogo.ejecutar(self._contexto_largo()))
        self.assertEqual(resultados["O02"].estado, "EJECUTADA")
        self.assertIn("bloques", resultados["O02"].detalle)

    def test_o02_no_se_ejecuta_con_pocas_filas(self):
        ctx = contexto()
        ctx.observado_reservado = ctx.observado_reservado[:10]
        ctx.pred_hip_reservado = ctx.pred_hip_reservado[:10]
        ctx.pred_base_reservado = ctx.pred_base_reservado[:10]
        ctx.variables_reservado = {"x": ctx.variables_reservado["x"][:10]}
        resultados = _por_codigo(catalogo.ejecutar(ctx))
        self.assertEqual(resultados["O02"].estado, "NO_REQUERIDA")
        self.assertIn("10", resultados["O02"].motivo)

    def test_o03_solo_con_bandera(self):
        sin = _por_codigo(catalogo.ejecutar(contexto()))
        self.assertEqual(sin["O03"].estado, "NO_REQUERIDA")
        con = _por_codigo(catalogo.ejecutar(
            contexto(),
            catalogo.OpcionesVerificacion(sensibilidad_bootstrap=True),
        ))
        self.assertEqual(con["O03"].estado, "EJECUTADA")
        self.assertIn("deriva", con["O03"].detalle)

    def test_o05_calcula_la_correccion_por_familia(self):
        resultados = _por_codigo(catalogo.ejecutar(
            contexto(),
            catalogo.OpcionesVerificacion(hipotesis_mismo_dataset=3),
        ))
        o05 = resultados["O05"]
        self.assertEqual(o05.estado, "EJECUTADA")
        self.assertIn("3", o05.motivo)
        evidencia = o05.evidencia
        self.assertFalse(evidencia["vinculante"])
        self.assertAlmostEqual(evidencia["nivel_corregido"], 1.0 - 0.05 / 3)
        self.assertIn("sobrevive_correccion", evidencia)
        self.assertIn("IC", o05.detalle)

    def test_o01_se_ejecuta_con_baseline_alternativo(self):
        from pruebas.ayudas import ModeloConstante

        alternativo = ModeloConstante()
        alternativo.id = "alternativo"
        ctx = contexto(hipotesis=hipotesis_con(baselines_alternativos=(alternativo,)))
        resultados = _por_codigo(catalogo.ejecutar(ctx))
        self.assertEqual(resultados["O01"].estado, "EJECUTADA")
        self.assertTrue(resultados["O01"].evidencia["resultados"])

    def test_o04_pendiente_si_declara_dataset_que_no_existe(self):
        ctx = contexto(hipotesis=hipotesis_con(dataset_validacion="fantasma"))
        resultados = _por_codigo(catalogo.ejecutar(ctx))
        self.assertEqual(resultados["O04"].estado, "PENDIENTE")
        self.assertIn("manifiesto", resultados["O04"].motivo)

    def test_resultado_serializable(self):
        for resultado in catalogo.ejecutar(contexto()):
            d = resultado.como_dict()
            self.assertIn("estado", d)
            self.assertIn("motivo", d)
            self.assertEqual(d["ejecutada"], d["estado"] == "EJECUTADA")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
