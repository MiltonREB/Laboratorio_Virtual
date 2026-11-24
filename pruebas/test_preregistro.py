"""Pruebas del preregistro criptográfico."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lab import preregistro
from pruebas.ayudas import HipotesisDePrueba, espacio_temporal, hipotesis_con


class TestFirma(unittest.TestCase):
    def test_serializacion_canonica_ordena_claves(self):
        a = preregistro.serializar_canonico({"b": 1, "a": 2})
        b = preregistro.serializar_canonico({"a": 2, "b": 1})
        self.assertEqual(a, b)

    def test_firma_es_determinista(self):
        self.assertEqual(
            preregistro.firmar({"x": 1.0}), preregistro.firmar({"x": 1.0})
        )

    def test_firma_cambia_con_el_contenido(self):
        self.assertNotEqual(
            preregistro.firmar({"x": 1.0}), preregistro.firmar({"x": 1.1})
        )


class TestSellado(unittest.TestCase):
    def setUp(self):
        self.raiz = espacio_temporal("sellos")

    def test_sellar_crea_archivo_y_verifica(self):
        h = HipotesisDePrueba()
        sello = preregistro.sellar(h, self.raiz)
        self.assertTrue(sello.ruta.is_file())
        self.assertFalse(sello.tardio)
        v = preregistro.verificar(h, self.raiz)
        self.assertTrue(v.existe)
        self.assertTrue(v.coincide)
        self.assertTrue(v.aceptable)

    def test_cambiar_umbral_invalida_el_sello(self):
        h = HipotesisDePrueba()
        preregistro.sellar(h, self.raiz)
        otra = hipotesis_con(umbral_mejora=0.2)
        v = preregistro.verificar(otra, self.raiz)
        self.assertTrue(v.existe)
        self.assertFalse(v.coincide)
        self.assertFalse(v.aceptable)

    def test_cambiar_parametro_invalida_el_sello(self):
        from lab.contrato import Parametro

        h = HipotesisDePrueba()
        preregistro.sellar(h, self.raiz)
        otra = hipotesis_con(
            PARAMETROS=(Parametro("a", 2.0, "u"), Parametro("b", 1.0, "u", congelado=False))
        )
        self.assertFalse(preregistro.verificar(otra, self.raiz).coincide)

    def test_sello_tardio_no_es_aceptable(self):
        h = HipotesisDePrueba()
        preregistro.sellar(h, self.raiz, tardio=True)
        v = preregistro.verificar(h, self.raiz)
        self.assertTrue(v.coincide)
        self.assertTrue(v.tardio)
        self.assertFalse(v.aceptable)

    def test_sin_sello(self):
        v = preregistro.verificar(HipotesisDePrueba(), self.raiz)
        self.assertFalse(v.existe)
        self.assertFalse(v.aceptable)

    def test_ultimo_sello_gana(self):
        h = HipotesisDePrueba()
        primero = preregistro.sellar(h, self.raiz, tardio=True)
        segundo = preregistro.sellar(h, self.raiz, tardio=False)
        todos = preregistro.sellos(self.raiz, h.id)
        self.assertEqual(len(todos), 2)
        self.assertEqual(preregistro.ultimo_sello(self.raiz, h.id).firma_sha256,
                         segundo.firma_sha256)
        self.assertNotEqual(primero.firma_sha256, "")

    def test_sellos_de_hipotesis_inexistente(self):
        self.assertEqual(preregistro.sellos(self.raiz, "no_existe"), [])
        self.assertIsNone(preregistro.ultimo_sello(self.raiz, "no_existe"))

    def test_diferencias_detecta_cambio_de_parametro(self):
        antes = {"parametros": [{"nombre": "a", "valor": 1.0}], "metrica": "rmse"}
        despues = {"parametros": [{"nombre": "a", "valor": 2.0}], "metrica": "mae"}
        cambios = preregistro.diferencias(antes, despues)
        self.assertTrue(any("parámetro 'a'" in c for c in cambios))
        self.assertTrue(any("metrica" in c for c in cambios))

    def test_diferencias_sin_cambios(self):
        firma = HipotesisDePrueba().firma_de_parametros()
        self.assertEqual(preregistro.diferencias(firma, firma), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
