"""Pruebas de la ingesta de CSV reales (Paso 3.1 de la hoja de ruta)."""

from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

from lab import ingesta
from lab.datos import Manifiesto, cargar_manifiesto
from pruebas.ayudas import espacio_temporal

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "pendulo_medido_fixture.csv"


def _csv_minimo(carpeta: Path, filas: int = 30, con_u: bool = True,
                nombre: str = "medido.csv") -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / nombre
    cabecera = ["L_m", "theta0_rad", "T_s"]
    if con_u:
        cabecera += ["u_T_s", "u_L_m", "u_theta0_rad"]
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cabecera)
        for i in range(filas):
            fila = [f"{1.0 + 0.01 * i:.4f}", f"{0.1 + 0.005 * i:.4f}",
                    f"{2.0 + 0.001 * i:.6f}"]
            if con_u:
                fila += ["0.001", "0.001", "0.002"]
            w.writerow(fila)
    return ruta


class TestInspeccion(unittest.TestCase):
    def test_fixture_cumple_el_esquema(self):
        info = ingesta.inspeccionar(FIXTURE)
        self.assertTrue(info.valido)
        self.assertEqual(info.filas, 120)
        self.assertIn("T_s", info.columnas)
        self.assertIn("u_T_s", info.incertidumbres)
        self.assertEqual(info.faltantes, ())

    def test_csv_sin_incertidumbres_avisa(self):
        carpeta = espacio_temporal("sin_u")
        info = ingesta.inspeccionar(_csv_minimo(carpeta, con_u=False))
        self.assertTrue(info.valido)
        self.assertEqual(info.incertidumbres, ())
        self.assertTrue(any("u_T_s" in a for a in info.avisos))

    def test_csv_sin_columna_obligatoria(self):
        carpeta = espacio_temporal("incompleto")
        ruta = carpeta / "malo.csv"
        ruta.write_text("L_m,T_s\n1.0,2.0\n", encoding="utf-8")
        info = ingesta.inspeccionar(ruta)
        self.assertFalse(info.valido)
        self.assertIn("theta0_rad", info.faltantes)

    def test_archivo_inexistente(self):
        with self.assertRaises(ingesta.ErrorDeIngesta):
            ingesta.inspeccionar(Path("no_existe.csv"))


class TestConstruirEntrada(unittest.TestCase):
    def setUp(self):
        self.carpeta = espacio_temporal("entrada")
        self.csv = _csv_minimo(self.carpeta, filas=40)

    def test_particion_completa_y_disyunta(self):
        entrada = ingesta.construir_entrada(self.csv, id_="d", raiz_datos=self.carpeta)
        cal, res = entrada["calibracion"], entrada["reservado"]
        self.assertEqual(sorted(cal + res), list(range(40)))
        self.assertEqual(set(cal) & set(res), set())
        self.assertEqual(len(cal), 24)

    def test_particion_es_reproducible(self):
        a = ingesta.construir_entrada(self.csv, id_="d", raiz_datos=self.carpeta,
                                      semilla=7)
        b = ingesta.construir_entrada(self.csv, id_="d", raiz_datos=self.carpeta,
                                      semilla=7)
        self.assertEqual(a["calibracion"], b["calibracion"])
        self.assertEqual(a["sha256"], b["sha256"])

    def test_semilla_distinta_cambia_la_particion(self):
        a = ingesta.construir_entrada(self.csv, id_="d", raiz_datos=self.carpeta,
                                      semilla=7)
        b = ingesta.construir_entrada(self.csv, id_="d", raiz_datos=self.carpeta,
                                      semilla=8)
        self.assertNotEqual(a["calibracion"], b["calibracion"])

    def test_declara_incertidumbres_y_ruido(self):
        entrada = ingesta.construir_entrada(self.csv, id_="d", raiz_datos=self.carpeta)
        self.assertEqual(entrada["incertidumbres"]["T_s"], "u_T_s")
        self.assertEqual(entrada["origen"], "medido")
        self.assertAlmostEqual(entrada["ruido"]["T_s"], 0.001)

    def test_guarda_la_procedencia(self):
        entrada = ingesta.construir_entrada(
            self.csv, id_="d", raiz_datos=self.carpeta,
            procedencia="Laboratorio docente, 2026-11-24, fotopuerta",
        )
        self.assertIn("fotopuerta", entrada["procedencia"])

    def test_fraccion_invalida(self):
        with self.assertRaises(ValueError):
            ingesta.construir_entrada(self.csv, id_="d", raiz_datos=self.carpeta,
                                      fraccion_calibracion=0.99)

    def test_csv_invalido_no_se_puede_ingestar(self):
        ruta = self.carpeta / "malo.csv"
        ruta.write_text("L_m,T_s\n1,2\n", encoding="utf-8")
        with self.assertRaises(ingesta.ErrorDeIngesta):
            ingesta.construir_entrada(ruta, id_="d", raiz_datos=self.carpeta)


class TestRegistrar(unittest.TestCase):
    def setUp(self):
        self.datos = espacio_temporal("datos")
        self.csv = _csv_minimo(espacio_temporal("origen"), filas=40)

    def test_escribe_manifiesto_y_carga(self):
        entrada = ingesta.registrar(self.csv, self.datos, id_="real_1")
        archivo = self.datos / "manifiesto.json"
        self.assertTrue(archivo.is_file())
        contenido = json.loads(archivo.read_text(encoding="utf-8"))
        self.assertEqual(contenido["datasets"][0]["id"], "real_1")

        manifiesto = Manifiesto.desde_directorio(self.datos)
        conjunto = manifiesto.cargar("real_1")
        self.assertTrue(conjunto.integridad)
        self.assertEqual(conjunto.filas, 40)
        self.assertEqual(conjunto.origen, "medido")
        self.assertIn("T_s", conjunto.incertidumbres)
        self.assertAlmostEqual(conjunto.incertidumbre_media("T_s"), 0.001)
        self.assertEqual(entrada["id"], "real_1")

    def test_no_duplica_ids_sin_reemplazar(self):
        ingesta.registrar(self.csv, self.datos, id_="real_1")
        with self.assertRaises(ingesta.ErrorDeIngesta):
            ingesta.registrar(self.csv, self.datos, id_="real_1")

    def test_reemplazar_actualiza_la_entrada(self):
        ingesta.registrar(self.csv, self.datos, id_="real_1")
        ingesta.registrar(self.csv, self.datos, id_="real_1", reemplazar=True)
        contenido = json.loads(
            (self.datos / "manifiesto.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(contenido["datasets"]), 1)

    def test_dos_datasets_conviven(self):
        ingesta.registrar(self.csv, self.datos, id_="a")
        origen = espacio_temporal("origen2")
        segundo = _csv_minimo(origen, filas=40, nombre="segundo.csv")
        ingesta.registrar(segundo, self.datos, id_="b")
        ids = cargar_manifiesto(self.datos).ids
        self.assertEqual(sorted(ids), ["a", "b"])


class TestEscalaEfectiva(unittest.TestCase):
    def test_combina_declarada_y_experimental_en_cuadratura(self):
        datos = espacio_temporal("escala")
        origen = espacio_temporal("escala_csv")
        ingesta.registrar(_csv_minimo(origen, filas=20), datos, id_="e")
        conjunto = cargar_manifiesto(datos).cargar("e")
        # media de u_T = 0.001, declarada = 0.002 -> sqrt(0.001² + 0.002²)
        self.assertAlmostEqual(conjunto.escala_efectiva("T_s", 0.002),
                               0.0022360679, places=6)
        # sin término declarado queda sólo el experimental
        self.assertAlmostEqual(conjunto.escala_efectiva("T_s", None), 0.001, places=9)
        # un valor negativo no cuenta como presupuesto
        self.assertAlmostEqual(conjunto.escala_efectiva("T_s", -1.0), 0.001, places=9)


class TestColumnas(unittest.TestCase):
    def test_mapea_observables(self):
        mapa = ingesta.columnas_de_incertidumbre(
            ["L_m", "u_T_s", "u_L_m", "u_theta0_rad", "otra"]
        )
        self.assertEqual(mapa["T_s"], "u_T_s")
        self.assertEqual(mapa["L_m"], "u_L_m")
        self.assertNotIn("otra", mapa)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
