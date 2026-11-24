"""Pruebas de los adaptadores de código externo."""

from __future__ import annotations

import sys
import unittest

import numpy as np

from lab.adaptadores import (
    ModeloDesdeFuncion,
    ModeloSubproceso,
    modelo_desde_funcion,
    normalizar_salida,
)
from lab.contrato import Parametro, verificar_salida


class TestNormalizarSalida(unittest.TestCase):
    def test_diccionario(self):
        salida = normalizar_salida({"y": [1.0, 2.0]}, ("y",), 2)
        np.testing.assert_allclose(salida["y"], [1.0, 2.0])

    def test_escalar_se_difunde(self):
        salida = normalizar_salida({"y": 3.0}, ("y",), 3)
        np.testing.assert_allclose(salida["y"], [3.0, 3.0, 3.0])

    def test_escalar_prohibido(self):
        with self.assertRaises(ValueError):
            normalizar_salida({"y": 3.0}, ("y",), 3, permitir_escalar=False)

    def test_secuencia_en_orden_declarado(self):
        salida = normalizar_salida([[1.0, 2.0], [3.0, 4.0]], ("a", "b"), 2)
        np.testing.assert_allclose(salida["a"], [1.0, 2.0])
        np.testing.assert_allclose(salida["b"], [3.0, 4.0])

    def test_arreglo_unico(self):
        salida = normalizar_salida(np.array([1.0, 2.0]), ("y",), 2)
        np.testing.assert_allclose(salida["y"], [1.0, 2.0])

    def test_falta_observable(self):
        with self.assertRaises(ValueError):
            normalizar_salida({"otro": [1.0]}, ("y",), 1)

    def test_forma_incorrecta(self):
        with self.assertRaises(ValueError):
            normalizar_salida({"y": [1.0, 2.0, 3.0]}, ("y",), 2)

    def test_no_finitos(self):
        with self.assertRaises(ValueError):
            normalizar_salida({"y": [1.0, float("nan")]}, ("y",), 2)

    def test_tipo_no_reconocible(self):
        with self.assertRaises(ValueError):
            normalizar_salida("texto", ("y",), 2)


class TestModeloDesdeFuncion(unittest.TestCase):
    def _modelo(self, funcion=None, **kwargs):
        funcion = funcion or (lambda v, p: {"y": 2.0 * np.asarray(v["x"])})
        argumentos = dict(
            id="m1", nombre="Modelo de prueba", funcion=funcion,
            observables=("y",), requiere=("x",),
            parametros=(Parametro("k", 2.0, "1"),),
        )
        argumentos.update(kwargs)
        return ModeloDesdeFuncion(**argumentos)

    def test_predice_y_es_un_modelo(self):
        modelo = self._modelo()
        salida = modelo.predecir({"x": np.array([1.0, 2.0])}, {"k": 2.0})
        np.testing.assert_allclose(salida["y"], [2.0, 4.0])
        self.assertEqual(modelo.parametros()[0].nombre, "k")
        self.assertEqual(verificar_salida(salida, modelo.observables, 2), [])

    def test_atajo(self):
        modelo = modelo_desde_funcion(
            lambda v, p: {"y": np.asarray(v["x"])},
            id="m2", nombre="M2", observables=("y",), requiere=("x",),
        )
        self.assertEqual(modelo.id, "m2")

    def test_rechaza_funcion_no_invocable(self):
        with self.assertRaises(TypeError):
            self._modelo(funcion="no soy invocable")

    def test_rechaza_sin_observables(self):
        with self.assertRaises(ValueError):
            self._modelo(observables=())

    def test_rechaza_sin_variables(self):
        with self.assertRaises(ValueError):
            self._modelo(requiere=())

    def test_rechaza_sin_id(self):
        with self.assertRaises(ValueError):
            self._modelo(id="")

    def test_variable_faltante(self):
        modelo = self._modelo()
        with self.assertRaises(KeyError):
            modelo.predecir({}, {})

    def test_longitudes_inconsistentes(self):
        modelo = self._modelo(
            funcion=lambda v, p: {"y": np.asarray(v["x"])},
            requiere=("x", "z"),
        )
        with self.assertRaises(ValueError):
            modelo.predecir({"x": np.array([1.0, 2.0]), "z": np.array([1.0])}, {})

    def test_propaga_error_de_la_funcion(self):
        def rompe(v, p):
            raise RuntimeError("fallo del legado")

        with self.assertRaises(RuntimeError):
            self._modelo(funcion=rompe).predecir({"x": np.array([1.0])}, {})


CODIGO_ECO = (
    "import json,sys;"
    "d=json.load(sys.stdin);"
    "print(json.dumps({'doble':[2.0*x for x in d['variables']['x']]}))"
)
CODIGO_ROTO = "import sys; sys.exit(3)"
CODIGO_NO_JSON = "print('esto no es json')"


class TestModeloSubproceso(unittest.TestCase):
    def _modelo(self, codigo=CODIGO_ECO, **kwargs):
        argumentos = dict(
            id="sub1", nombre="Subproceso de prueba",
            comando=[sys.executable, "-c", codigo],
            observables=("doble",), requiere=("x",),
        )
        argumentos.update(kwargs)
        return ModeloSubproceso(**argumentos)

    def test_protocolo_json_ida_y_vuelta(self):
        modelo = self._modelo()
        salida = modelo.predecir({"x": np.array([1.0, 2.5])}, {})
        np.testing.assert_allclose(salida["doble"], [2.0, 5.0])

    def test_codigo_de_salida_distinto_de_cero(self):
        with self.assertRaises(RuntimeError) as ctx:
            self._modelo(CODIGO_ROTO).predecir({"x": np.array([1.0])}, {})
        self.assertIn("código 3", str(ctx.exception))

    def test_salida_no_json(self):
        with self.assertRaises(RuntimeError) as ctx:
            self._modelo(CODIGO_NO_JSON).predecir({"x": np.array([1.0])}, {})
        self.assertIn("JSON", str(ctx.exception))

    def test_comando_inexistente(self):
        modelo = self._modelo(comando=["comando_que_no_existe_xyz"])
        with self.assertRaises(RuntimeError):
            modelo.predecir({"x": np.array([1.0])}, {})

    def test_variable_faltante(self):
        with self.assertRaises(KeyError):
            self._modelo().predecir({}, {})

    def test_rechaza_comando_vacio(self):
        with self.assertRaises(ValueError):
            self._modelo(comando=[])

    def test_rechaza_sin_observables(self):
        with self.assertRaises(ValueError):
            self._modelo(observables=())

    def test_rechaza_sin_variables(self):
        with self.assertRaises(ValueError):
            self._modelo(requiere=())

    def test_rechaza_sin_id(self):
        with self.assertRaises(ValueError):
            self._modelo(id="")

    def test_tiempo_limite_excedido(self):
        codigo = "import time; time.sleep(5)"
        modelo = self._modelo(codigo, tiempo_limite=0.4)
        with self.assertRaises(RuntimeError) as ctx:
            modelo.predecir({"x": np.array([1.0])}, {})
        self.assertIn("excedió", str(ctx.exception))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
