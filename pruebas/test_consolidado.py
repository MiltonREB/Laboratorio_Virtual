"""Pruebas del informe consolidado y del versionado de esquema."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import lab
from lab import consolidado, preregistro
from lab.datos import Manifiesto
from lab.evaluador import (
    ESQUEMA_RESUMEN,
    ESQUEMAS_COMPATIBLES,
    cargar_corridas,
    esquema_compatible,
)
from lab.registro import cargar_registro
from pruebas.ayudas import espacio_temporal

RAIZ = Path(lab.__file__).resolve().parent.parent


def _evaluar(id_, destino, remuestreos=200, particiones=1):
    from lab.evaluador import evaluar_hipotesis

    registro = cargar_registro(RAIZ / "hipotesis")
    manifiesto = Manifiesto.desde_directorio(RAIZ / "datos")
    hipotesis = registro.obtener(id_)
    preregistro.sellar(
        hipotesis, destino,
        momento=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    return evaluar_hipotesis(
        hipotesis, manifiesto, destino,
        remuestreos=remuestreos, particiones=particiones,
    )


class TestEsquema(unittest.TestCase):
    def test_version_actual_es_compatible(self):
        self.assertIn(ESQUEMA_RESUMEN, ESQUEMAS_COMPATIBLES)
        self.assertTrue(esquema_compatible(ESQUEMA_RESUMEN))

    def test_version_desconocida_no_es_compatible(self):
        self.assertFalse(esquema_compatible("9.9"))
        self.assertFalse(esquema_compatible(None))

    def test_el_resumen_declara_el_esquema(self):
        destino = espacio_temporal("esquema")
        resultado = _evaluar("pendulo_amplitud", destino)
        datos = json.loads((resultado.corrida / "resumen.json").read_text(encoding="utf-8"))
        self.assertEqual(datos["schema_version"], ESQUEMA_RESUMEN)

    def test_corrida_sin_esquema_se_marca(self):
        destino = espacio_temporal("esquema_viejo")
        carpeta = destino / "antigua_20260101T000000Z"
        carpeta.mkdir(parents=True)
        (carpeta / "resumen.json").write_text(
            json.dumps({"hipotesis": {"id": "antigua"}, "pruebas": []}),
            encoding="utf-8",
        )
        corridas = cargar_corridas(destino)
        self.assertEqual(len(corridas), 1)
        self.assertEqual(corridas[0]["_esquema"], "sin_declarar")
        self.assertFalse(corridas[0]["_esquema_compatible"])


class TestConsolidado(unittest.TestCase):
    def test_sin_corridas_genera_aviso(self):
        destino = espacio_temporal("consolidado_vacio")
        ruta = consolidado.generar_informe(destino)
        self.assertTrue(ruta.is_file())
        texto = ruta.read_text(encoding="utf-8")
        self.assertIn("No hay corridas registradas", texto)

    def test_incluye_veredictos_y_verificaciones(self):
        destino = espacio_temporal("consolidado")
        _evaluar("pendulo_amplitud", destino)
        _evaluar("pendulo_polinomio_alto", destino)

        ruta = consolidado.generar_informe(destino)
        texto = ruta.read_text(encoding="utf-8")
        self.assertIn("PRELIMINAR", texto)
        self.assertIn("NO_CORROBORADA", texto)
        self.assertIn("pendulo_amplitud", texto)
        self.assertIn("Matriz de pruebas", texto)
        self.assertIn("O01", texto)
        self.assertIn("No hay dos hipótesis sobre el mismo dataset", texto)
        self.assertIn("una sola corrida", texto)

    def test_avisa_de_corridas_repetidas(self):
        destino = espacio_temporal("consolidado_repetido")
        _evaluar("pendulo_polinomio_alto", destino)
        _evaluar("pendulo_polinomio_alto", destino)

        ruta = consolidado.generar_informe(destino)
        texto = ruta.read_text(encoding="utf-8")
        self.assertIn("2 corridas registradas", texto)
        self.assertIn("sesgado", texto)

    def test_enlace_a_la_ultima_corrida(self):
        destino = espacio_temporal("consolidado_ultima")
        _evaluar("pendulo_polinomio_alto", destino)
        ruta = consolidado.generar_informe(destino)
        texto = ruta.read_text(encoding="utf-8")
        primera = texto.count("pendulo_polinomio_alto")
        _evaluar("pendulo_polinomio_alto", destino)
        texto2 = consolidado.generar_informe(destino).read_text(encoding="utf-8")
        self.assertGreaterEqual(primera, 1)
        self.assertIn("2 corridas registradas", texto2)

    def test_salida_personalizada(self):
        destino = espacio_temporal("consolidado_salida")
        _evaluar("pendulo_amplitud", destino)
        salida = destino / "sub" / "informe.md"
        ruta = consolidado.generar_informe(destino, salida)
        self.assertEqual(ruta, salida)
        self.assertTrue(salida.is_file())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
