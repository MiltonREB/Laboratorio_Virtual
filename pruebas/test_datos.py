"""Pruebas de la capa de datos: integridad, manifiesto y particiones."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from lab.datos import (
    ErrorDeDatos,
    Manifiesto,
    _leer_particion,
    cargar_manifiesto,
    sha256_de_archivo,
)
from pruebas.ayudas import espacio_temporal


def _escribir_dataset(
    carpeta: Path,
    id_: str = "d1",
    filas: int = 10,
    calibracion: list[int] | None = None,
    reservado: list[int] | None = None,
    uso: str | None = None,
) -> Path:
    csv = carpeta / f"{id_}.csv"
    lineas = ["x,y"]
    for i in range(filas):
        lineas.append(f"{i},{2 * i + 1}")
    csv.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    entrada = {
        "id": id_,
        "ruta": f"{id_}.csv",
        "sha256": sha256_de_archivo(csv),
        "descripcion": "sintético de prueba",
        "origen": "sintetico",
        "generado_por": "pruebas",
        "variables": ["x"],
        "observables": ["y"],
        "unidades": {"x": "u", "y": "u"},
        "filas": filas,
        "ruido": {"y": 0.5},
    }
    if uso:
        entrada["uso"] = uso
        if uso == "validacion_externa":
            if calibracion is not None:
                entrada["calibracion"] = calibracion
            if reservado is not None:
                entrada["reservado"] = reservado
        else:
            entrada["calibracion"] = calibracion or []
            entrada["reservado"] = reservado or []
    else:
        entrada["calibracion"] = calibracion if calibracion is not None else list(range(0, filas // 2))
        entrada["reservado"] = reservado if reservado is not None else list(range(filas // 2, filas))

    manifiesto = {"version": 1, "datasets": [entrada]}
    (carpeta / "manifiesto.json").write_text(
        json.dumps(manifiesto), encoding="utf-8"
    )
    return csv


class TestManifiesto(unittest.TestCase):
    def setUp(self):
        self.carpeta = espacio_temporal("manifiesto")

    def test_carga_y_verifica_integridad(self):
        _escribir_dataset(self.carpeta)
        m = cargar_manifiesto(self.carpeta)
        d = m.cargar("d1")
        self.assertTrue(d.integridad)
        self.assertEqual(d.filas, 10)
        self.assertEqual(len(d.calibracion), 5)
        self.assertEqual(len(d.reservado), 5)
        self.assertEqual(d.sigma("y"), 0.5)

    def test_detecta_csv_modificado(self):
        csv = _escribir_dataset(self.carpeta)
        nuevo = ["x,y"] + [f"{i},{3 * i + 7}" for i in range(10)]
        csv.write_text("\n".join(nuevo) + "\n", encoding="utf-8")
        d = cargar_manifiesto(self.carpeta).cargar("d1")
        self.assertFalse(d.integridad)
        with self.assertRaises(ErrorDeDatos):
            d.exigir_integridad()

    def test_csv_truncado_falla_al_cargar(self):
        csv = _escribir_dataset(self.carpeta)
        csv.write_text("x,y\n0,999\n", encoding="utf-8")
        with self.assertRaises(ErrorDeDatos):
            cargar_manifiesto(self.carpeta).cargar("d1")

    def test_verificar_reporta_todos(self):
        _escribir_dataset(self.carpeta)
        informe = cargar_manifiesto(self.carpeta).verificar()
        self.assertTrue(informe["d1"]["ok"])
        self.assertIsNone(informe["d1"]["error"])

    def test_dataset_inexistente_en_manifiesto(self):
        _escribir_dataset(self.carpeta)
        with self.assertRaises(ErrorDeDatos):
            cargar_manifiesto(self.carpeta).cargar("no_existe")

    def test_manifiesto_ausente(self):
        with self.assertRaises(ErrorDeDatos):
            Manifiesto.desde_directorio(self.carpeta)

    def test_csv_inexistente(self):
        _escribir_dataset(self.carpeta)
        (self.carpeta / "d1.csv").unlink()
        with self.assertRaises(ErrorDeDatos):
            cargar_manifiesto(self.carpeta).cargar("d1")

    def test_columna_declarada_ausente(self):
        csv = _escribir_dataset(self.carpeta)
        csv.write_text("x\n1\n2\n", encoding="utf-8")
        entrada = json.loads((self.carpeta / "manifiesto.json").read_text())
        entrada["datasets"][0]["sha256"] = sha256_de_archivo(csv)
        (self.carpeta / "manifiesto.json").write_text(json.dumps(entrada))
        with self.assertRaises(ErrorDeDatos):
            cargar_manifiesto(self.carpeta).cargar("d1")

    def test_filas_declaradas_no_coinciden(self):
        _escribir_dataset(self.carpeta)
        entrada = json.loads((self.carpeta / "manifiesto.json").read_text())
        entrada["datasets"][0]["filas"] = 99
        (self.carpeta / "manifiesto.json").write_text(json.dumps(entrada))
        with self.assertRaises(ErrorDeDatos):
            cargar_manifiesto(self.carpeta).cargar("d1")

    def test_dataset_de_validacion_externa_sin_particiones(self):
        _escribir_dataset(self.carpeta, uso="validacion_externa")
        d = cargar_manifiesto(self.carpeta).cargar("d1")
        self.assertTrue(d.es_validacion_externa)
        self.assertEqual(d.calibracion, ())
        self.assertEqual(d.reservado, ())
        self.assertEqual(d.filas, 10)
        self.assertEqual(d.uso, "validacion_externa")

    def test_validacion_externa_no_debe_declarar_particiones(self):
        _escribir_dataset(self.carpeta, uso="validacion_externa", calibracion=[0, 1])
        with self.assertRaises(ErrorDeDatos):
            cargar_manifiesto(self.carpeta).cargar("d1")

    def test_particiones_solapadas(self):
        _escribir_dataset(self.carpeta, calibracion=[0, 1, 2], reservado=[2, 3, 4])
        with self.assertRaises(ErrorDeDatos):
            cargar_manifiesto(self.carpeta).cargar("d1")

    def test_particiones_incompletas(self):
        _escribir_dataset(self.carpeta, calibracion=[0, 1], reservado=[2, 3])
        with self.assertRaises(ErrorDeDatos):
            cargar_manifiesto(self.carpeta).cargar("d1")

    def test_falta_particion_explicita(self):
        _escribir_dataset(self.carpeta)
        entrada = json.loads((self.carpeta / "manifiesto.json").read_text())
        del entrada["datasets"][0]["reservado"]
        (self.carpeta / "manifiesto.json").write_text(json.dumps(entrada))
        with self.assertRaises(ErrorDeDatos):
            cargar_manifiesto(self.carpeta).cargar("d1")

    def test_indices_fuera_de_rango(self):
        _escribir_dataset(self.carpeta, calibracion=[0, 50], reservado=[1])
        with self.assertRaises(ErrorDeDatos):
            cargar_manifiesto(self.carpeta).cargar("d1")

    def test_csv_con_texto_no_numerico(self):
        _escribir_dataset(self.carpeta)
        csv = self.carpeta / "d1.csv"
        csv.write_text("x,y\n0,uno\n", encoding="utf-8")
        entrada = json.loads((self.carpeta / "manifiesto.json").read_text())
        entrada["datasets"][0]["sha256"] = sha256_de_archivo(csv)
        entrada["datasets"][0]["filas"] = 1
        (self.carpeta / "manifiesto.json").write_text(json.dumps(entrada))
        with self.assertRaises(ErrorDeDatos):
            cargar_manifiesto(self.carpeta).cargar("d1")


class TestConjuntoDatos(unittest.TestCase):
    def setUp(self):
        self.carpeta = espacio_temporal("conjunto")
        _escribir_dataset(self.carpeta, filas=10)
        self.d = cargar_manifiesto(self.carpeta).cargar("d1")

    def test_observado_y_sigma(self):
        np.testing.assert_allclose(self.d.observado("y", [0, 1]), [1.0, 3.0])
        self.assertEqual(self.d.sigma("y"), 0.5)

    def test_observable_no_declarado(self):
        with self.assertRaises(ErrorDeDatos):
            self.d.observado("z")

    def test_columna_inexistente(self):
        with self.assertRaises(ErrorDeDatos):
            self.d.matriz(["no_existe"])

    def test_particion_alternativa_cubre_y_no_solapa(self):
        cal, res = self.d.con_particion(semilla=1)
        self.assertEqual(len(set(cal) & set(res)), 0)
        self.assertEqual(sorted((*cal, *res)), list(range(self.d.filas)))

    def test_particion_es_reproducible(self):
        self.assertEqual(self.d.con_particion(3), self.d.con_particion(3))

    def test_particion_rechaza_fraccion_invalida(self):
        with self.assertRaises(ValueError):
            self.d.con_particion(semilla=1, fraccion_reservado=1.5)

    def test_resumen(self):
        r = self.d.resumen()
        self.assertEqual(r["id"], "d1")
        self.assertEqual(r["filas"], 10)
        self.assertTrue(r["integridad"])


class TestLeerParticion(unittest.TestCase):
    def test_particion_valida(self):
        cal, res = _leer_particion({"calibracion": [0, 1], "reservado": [2]}, 3, "d")
        self.assertEqual(cal, (0, 1))
        self.assertEqual(res, (2,))

    def test_particion_vacia(self):
        with self.assertRaises(ErrorDeDatos):
            _leer_particion({"calibracion": [], "reservado": [2]}, 3, "d")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
