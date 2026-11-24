"""Pruebas de carga de hipótesis: un módulo roto no debe tumbar el laboratorio."""

from __future__ import annotations

import unittest

from lab.registro import ErrorDeRegistro, cargar_registro, modelos_de
from pruebas.ayudas import espacio_temporal

MODELO_VALIDO = '''
from lab.contrato import Hipotesis, Modelo, Parametro


class Base(Modelo):
    id = "base_x"
    nombre = "Base"
    observables = ("y",)
    requiere = ("x",)

    def predecir(self, variables, parametros):
        import numpy as np
        return {"y": np.asarray(variables["x"], dtype=float)}


class Buena(Hipotesis):
    id = "%s"
    nombre = "Buena"
    observables = ("y",)
    requiere = ("x",)
    enunciado = "e"
    prediccion_diferenciadora = "p"
    observable_objetivo = "y"
    unidad_observable = "u"
    baseline = Base()
    dataset_id = "d"
    metrica = "rmse"
    umbral_mejora = 0.1
    umbral_sensibilidad = 0.01

    def predecir(self, variables, parametros):
        import numpy as np
        return {"y": np.asarray(variables["x"], dtype=float)}
'''


class TestCargaRobusta(unittest.TestCase):
    def setUp(self):
        self.raiz = espacio_temporal("registro")
        (self.raiz / "__init__.py").write_text("", encoding="utf-8")

    def _escribir(self, nombre: str, contenido: str):
        archivo = self.raiz / f"{nombre}.py"
        archivo.write_text(contenido, encoding="utf-8")
        return archivo

    def test_carga_una_hipotesis_sin_registrar(self):
        self._escribir("buena", MODELO_VALIDO % "buena")
        registro = cargar_registro(self.raiz)
        self.assertIn("buena", registro)
        self.assertEqual(registro.errores, [])
        self.assertIn("base_x", registro.ids_modelos())

    def test_modulo_roto_no_detiene_al_resto(self):
        self._escribir("rota", "raise RuntimeError('import roto')\n")
        self._escribir("buena", MODELO_VALIDO % "buena")
        registro = cargar_registro(self.raiz)
        self.assertIn("buena", registro)
        self.assertEqual(len(registro.errores), 1)
        self.assertEqual(registro.errores[0].archivo, "rota.py")
        self.assertIn("import roto", registro.errores[0].mensaje)

    def test_id_duplicado_se_reporta(self):
        self._escribir("a", MODELO_VALIDO % "misma")
        self._escribir("b", MODELO_VALIDO % "misma")
        registro = cargar_registro(self.raiz)
        self.assertEqual(registro.ids_hipotesis(), ("misma",))
        self.assertTrue(any("duplicado" in e.mensaje for e in registro.errores))

    def test_modulo_sin_modelos(self):
        self._escribir("vacio", "X = 1\n")
        registro = cargar_registro(self.raiz)
        self.assertEqual(len(registro), 0)
        self.assertTrue(any("no expone" in e.mensaje for e in registro.errores))

    def test_registrar_devuelve_algo_que_no_es_modelo(self):
        self._escribir(
            "malo",
            "def registrar():\n    return [42]\n",
        )
        registro = cargar_registro(self.raiz)
        self.assertTrue(any("no es un Modelo" in e.mensaje for e in registro.errores))

    def test_clase_que_necesita_argumentos(self):
        self._escribir(
            "con_args",
            "from lab.contrato import Modelo\n"
            "class Raro(Modelo):\n"
            "    id = 'raro'\n"
            "    def __init__(self, obligatorio):\n"
            "        self.obligatorio = obligatorio\n"
            "    def predecir(self, variables, parametros):\n"
            "        return {}\n",
        )
        registro = cargar_registro(self.raiz)
        self.assertEqual(len(registro), 0)
        self.assertTrue(any("sin argumentos" in e.mensaje for e in registro.errores))

    def test_modelo_sin_id(self):
        self._escribir(
            "sin_id",
            "from lab.contrato import Modelo\n"
            "class SinId(Modelo):\n"
            "    id = ''\n"
            "    observables = ('y',)\n"
            "    requiere = ('x',)\n"
            "    def predecir(self, variables, parametros):\n"
            "        return {}\n",
        )
        registro = cargar_registro(self.raiz)
        self.assertEqual(len(registro), 0)
        self.assertTrue(any("sin 'id'" in e.mensaje for e in registro.errores))

    def test_directorio_inexistente(self):
        registro = cargar_registro(self.raiz / "no_existe")
        self.assertEqual(len(registro), 0)
        self.assertEqual(len(registro.errores), 1)

    def test_obtener_inexistente_da_mensaje_util(self):
        self._escribir("buena", MODELO_VALIDO % "buena")
        registro = cargar_registro(self.raiz)
        with self.assertRaises(ErrorDeRegistro) as ctx:
            registro.obtener("fantasma")
        self.assertIn("buena", str(ctx.exception))

    def test_modelos_de(self):
        self._escribir("buena", MODELO_VALIDO % "buena")
        registro = cargar_registro(self.raiz)
        self.assertEqual([m.id for m in modelos_de(registro, ["base_x"])], ["base_x"])

    def test_problemas_y_resumen(self):
        contenido = (MODELO_VALIDO % "incompleta").replace(
            'enunciado = "e"', 'enunciado = ""'
        )
        self._escribir("incompleta", contenido)
        registro = cargar_registro(self.raiz)
        problemas = registro.problemas()
        self.assertTrue(any("contrato incompleto" in p for p in problemas))
        resumen = registro.resumen()
        self.assertIn("hipotesis", resumen)
        self.assertIn("modelos", resumen)
        self.assertTrue(resumen["hipotesis"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
