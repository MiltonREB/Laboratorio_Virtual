"""Pruebas de integración: el laboratorio completo sobre los datos reales.

Estas pruebas usan los datasets de ``datos/`` y las hipótesis de
``hipotesis/``. Son lentas comparadas con las unitarias (bootstrap incluido),
así que reducen el número de remuestreos.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import lab
from lab import preregistro
from lab.datos import Manifiesto
from lab.evaluador import (
    cargar_corridas,
    evaluar_hipotesis,
    ultima_corrida_por_hipotesis,
)
from lab.panel import generar_panel
from lab.registro import cargar_registro
from pruebas.ayudas import espacio_temporal

RAIZ = Path(lab.__file__).resolve().parent.parent


class TestRegistroReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registro = cargar_registro(RAIZ / "hipotesis")

    def test_carga_ambas_hipotesis(self):
        self.assertIn("pendulo_amplitud", self.registro)
        self.assertIn("pendulo_polinomio_alto", self.registro)
        self.assertEqual(self.registro.errores, [])

    def test_contratos_completos(self):
        for id_ in self.registro.ids_hipotesis():
            self.assertEqual(self.registro.obtener(id_).problemas_de_contrato(), [],
                             msg=f"{id_} tiene el contrato incompleto")

    def test_baseline_compartido(self):
        a = self.registro.obtener("pendulo_amplitud").baseline
        b = self.registro.obtener("pendulo_polinomio_alto").baseline
        self.assertEqual(a.id, b.id)

    def test_hipotesis_inexistente(self):
        from lab.registro import ErrorDeRegistro

        with self.assertRaises(ErrorDeRegistro):
            self.registro.obtener("no_existe")


class TestManifiestoReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifiesto = Manifiesto.desde_directorio(RAIZ / "datos")

    def test_integridad_de_todos_los_datasets(self):
        informe = self.manifiesto.verificar()
        for id_, datos in informe.items():
            self.assertTrue(datos["ok"], msg=f"{id_}: {datos['error']}")

    def test_particiones_completas(self):
        for id_ in self.manifiesto.ids:
            d = self.manifiesto.cargar(id_)
            if d.es_validacion_externa:
                self.assertEqual((d.calibracion, d.reservado), ((), ()), id_)
                continue
            self.assertEqual(
                sorted((*d.calibracion, *d.reservado)), list(range(d.filas))
            )

    def test_hay_un_dataset_de_validacion_externa(self):
        externos = [
            id_ for id_ in self.manifiesto.ids
            if self.manifiesto.cargar(id_).es_validacion_externa
        ]
        self.assertEqual(externos, ["pendulo_holdout_v1"])


class TestEvaluacionReal(unittest.TestCase):
    def _evaluar(self, id_, remuestreos=300, particiones=2):
        registro = cargar_registro(RAIZ / "hipotesis")
        manifiesto = Manifiesto.desde_directorio(RAIZ / "datos")
        h = registro.obtener(id_)
        tmp = espacio_temporal()
        preregistro.sellar(h, tmp)
        return evaluar_hipotesis(
            h, manifiesto, tmp, remuestreos=remuestreos, particiones=particiones
        ), Path(tmp)

    def test_hipotesis_correcta_queda_corroborada(self):
        resultado, tmp = self._evaluar("pendulo_amplitud")
        self.assertEqual(resultado.veredicto.estado, "CORROBORADA_PROVISIONAL")
        self.assertGreater(resultado.datos["comparacion"]["intervalo"]["mejora"], 0.5)
        self.assertTrue((resultado.corrida / "resumen.json").is_file())
        self.assertTrue((resultado.corrida / "INFORME.md").is_file())
        self.assertTrue((resultado.corrida / "predicciones.csv").is_file())
        self.assertTrue((resultado.corrida / "matriz.csv").is_file())

    def test_sobreajuste_no_queda_corroborado(self):
        resultado, _ = self._evaluar("pendulo_polinomio_alto")
        self.assertNotEqual(resultado.veredicto.estado, "CORROBORADA_PROVISIONAL")
        self.assertLessEqual(resultado.datos["comparacion"]["intervalo"]["mejora"], 0.10)

    def test_coeficientes_recuperados(self):
        resultado, _ = self._evaluar("pendulo_amplitud")
        ajustados = resultado.datos["hipotesis"]["parametros_ajustados"]
        self.assertAlmostEqual(ajustados["c2"], 1.0 / 16.0, places=4)
        self.assertAlmostEqual(ajustados["c4"], 11.0 / 3072.0, places=4)

    def test_sin_preregistro_se_marca_tardio(self):
        registro = cargar_registro(RAIZ / "hipotesis")
        manifiesto = Manifiesto.desde_directorio(RAIZ / "datos")
        h = registro.obtener("pendulo_amplitud")
        tmp = espacio_temporal()
        resultado = evaluar_hipotesis(
            h, manifiesto, tmp, remuestreos=200, particiones=1, guardar=False
        )
        mapa = {p.codigo: p.estado for p in resultado.pruebas}
        self.assertEqual(mapa["T04"], "PENDIENTE")
        self.assertEqual(resultado.veredicto.estado, "PENDIENTE")

    def test_umbral_cambiado_invalida_el_preregistro(self):
        registro = cargar_registro(RAIZ / "hipotesis")
        manifiesto = Manifiesto.desde_directorio(RAIZ / "datos")
        h = registro.obtener("pendulo_amplitud")
        tmp = Path(espacio_temporal())
        preregistro.sellar(h, tmp)
        h.umbral_mejora = 0.99  # cambio posterior al sello
        resultado = evaluar_hipotesis(
            h, manifiesto, tmp, remuestreos=200, particiones=1, guardar=False
        )
        mapa = {p.codigo: p.estado for p in resultado.pruebas}
        self.assertEqual(mapa["T04"], "FALLIDO")
        self.assertEqual(resultado.veredicto.estado, "PENDIENTE")

    def test_hipotesis_sin_dataset_falla_claro(self):
        from lab.evaluador import ErrorDeEvaluacion

        registro = cargar_registro(RAIZ / "hipotesis")
        manifiesto = Manifiesto.desde_directorio(RAIZ / "datos")
        h = registro.obtener("pendulo_amplitud")
        h.dataset_id = "no_existe"
        with self.assertRaises(ErrorDeEvaluacion):
            evaluar_hipotesis(h, manifiesto, espacio_temporal(), guardar=False)


class TestPanelYLectura(unittest.TestCase):
    def test_panel_se_genera_y_lista_la_hipotesis(self):
        tmp = Path(espacio_temporal())
        registro = cargar_registro(RAIZ / "hipotesis")
        manifiesto = Manifiesto.desde_directorio(RAIZ / "datos")
        h = registro.obtener("pendulo_amplitud")
        preregistro.sellar(h, tmp)
        evaluar_hipotesis(h, manifiesto, tmp, remuestreos=200, particiones=1)

        indice = generar_panel(tmp, tmp / "panel")
        self.assertTrue(indice.is_file())
        html = indice.read_text(encoding="utf-8")
        self.assertIn("pendulo_amplitud", html)
        self.assertIn("Corroborada", html)
        paginas = list((tmp / "panel" / "corridas").glob("*.html"))
        self.assertTrue(paginas)

        corrida = paginas[0].read_text(encoding="utf-8")
        self.assertEqual(corrida.count('class="prueba"'), 17)  # 12 T + 5 O
        self.assertIn("Pruebas ejecutadas y sus resultados", corrida)
        self.assertIn("Verificaciones opcionales", corrida)
        self.assertIn("Campos del contrato declarados", corrida)  # gráfico T01

        catalogo = (tmp / "panel" / "pruebas.html").read_text(encoding="utf-8")
        self.assertIn("Catálogo de pruebas", catalogo)
        self.assertIn("O01", catalogo)
        self.assertIn("T12", catalogo)

    def test_verificaciones_registradas(self):
        tmp = espacio_temporal("verificaciones")
        registro = cargar_registro(RAIZ / "hipotesis")
        manifiesto = Manifiesto.desde_directorio(RAIZ / "datos")
        h = registro.obtener("pendulo_amplitud")
        preregistro.sellar(h, tmp)
        resultado = evaluar_hipotesis(h, manifiesto, tmp, remuestreos=200,
                                      particiones=1)
        verificaciones = resultado.datos["verificaciones"]
        self.assertEqual(len(verificaciones), 5)
        codigos = [v["codigo"] for v in verificaciones]
        self.assertEqual(codigos, ["O01", "O02", "O03", "O04", "O05"])
        por_codigo = {v["codigo"]: v for v in verificaciones}
        # La hipótesis declara dos baselines alternativos y un holdout, y su
        # reservado alcanza para tres bloques: O01, O02 y O04 se ejecutan.
        self.assertEqual(por_codigo["O01"]["estado"], "EJECUTADA")
        self.assertEqual(por_codigo["O02"]["estado"], "EJECUTADA")
        self.assertEqual(por_codigo["O04"]["estado"], "EJECUTADA")
        self.assertFalse(por_codigo["O01"]["evidencia"]["gana_a_todos"])
        self.assertTrue(por_codigo["O04"]["evidencia"]["supera_baseline"])

    def test_verificaciones_no_vinculantes_no_cambian_el_veredicto(self):
        tmp = espacio_temporal("no_vinculantes")
        registro = cargar_registro(RAIZ / "hipotesis")
        manifiesto = Manifiesto.desde_directorio(RAIZ / "datos")
        h = registro.obtener("pendulo_amplitud")
        preregistro.sellar(h, tmp)
        resultado = evaluar_hipotesis(h, manifiesto, tmp, remuestreos=200,
                                      particiones=1)
        self.assertEqual(resultado.veredicto.estado, "CORROBORADA_PROVISIONAL")
        # O01 dice que no gana a todos los baselines alternativos y aun así el
        # veredicto no cambia: es informativa, no vinculante.
        o01 = next(v for v in resultado.datos["verificaciones"] if v["codigo"] == "O01")
        self.assertFalse(o01["evidencia"]["gana_a_todos"])

    def test_lectura_de_corridas(self):
        tmp = Path(espacio_temporal())
        registro = cargar_registro(RAIZ / "hipotesis")
        manifiesto = Manifiesto.desde_directorio(RAIZ / "datos")
        h = registro.obtener("pendulo_amplitud")
        preregistro.sellar(h, tmp)
        evaluar_hipotesis(h, manifiesto, tmp, remuestreos=200, particiones=1)
        corridas = cargar_corridas(tmp)
        self.assertEqual(len(corridas), 1)
        ultimas = ultima_corrida_por_hipotesis(tmp)
        self.assertIn("pendulo_amplitud", ultimas)
        self.assertEqual(ultimas["pendulo_amplitud"]["veredicto"]["estado"],
                         "CORROBORADA_PROVISIONAL")

    def test_resumen_json_es_serializable(self):
        tmp = Path(espacio_temporal())
        registro = cargar_registro(RAIZ / "hipotesis")
        manifiesto = Manifiesto.desde_directorio(RAIZ / "datos")
        h = registro.obtener("pendulo_amplitud")
        preregistro.sellar(h, tmp)
        resultado = evaluar_hipotesis(h, manifiesto, tmp, remuestreos=200,
                                      particiones=1)
        texto = (resultado.corrida / "resumen.json").read_text(encoding="utf-8")
        datos = json.loads(texto)
        self.assertEqual(datos["hipotesis"]["id"], "pendulo_amplitud")
        self.assertEqual(len(datos["pruebas"]), 12)
        self.assertEqual(len(datos["verificaciones"]), 5)
        self.assertTrue(datos["comparacion"]["histograma_bootstrap"]["cuentas"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
