"""Pruebas de la interfaz de línea de comandos."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import lab
from lab.cli import main
from pruebas.ayudas import espacio_temporal

RAIZ = Path(lab.__file__).resolve().parent.parent


def correr(argv: list[str]) -> tuple[int, str, str]:
    salida, error = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(error):
        codigo = main(argv)
    return codigo, salida.getvalue(), error.getvalue()


class TestComandosReales(unittest.TestCase):
    def test_hipotesis_listar(self):
        codigo, salida, _ = correr(["hipotesis", "listar"])
        self.assertEqual(codigo, 0)
        self.assertIn("pendulo_amplitud", salida)
        self.assertIn("pendulo_polinomio_alto", salida)

    def test_hipotesis_json(self):
        codigo, salida, _ = correr(["hipotesis", "--json"])
        self.assertEqual(codigo, 0)
        datos = json.loads(salida)
        self.assertEqual(len(datos["hipotesis"]), 3)
        self.assertEqual(datos["errores"], [])

    def test_datos_verificar(self):
        codigo, salida, _ = correr(["datos", "verificar"])
        self.assertEqual(codigo, 0)
        self.assertIn("pendulo_v1", salida)
        self.assertIn("integridad verificada", salida)

    def test_datos_json(self):
        codigo, salida, _ = correr(["datos", "--json"])
        self.assertEqual(codigo, 0)
        datos = json.loads(salida)
        self.assertTrue(all(d["integridad"] for d in datos))

    def test_estado_sin_corridas(self):
        tmp = espacio_temporal("estado")
        codigo, salida, _ = correr(["--raiz", str(tmp), "estado"])
        self.assertEqual(codigo, 0)
        self.assertIn("No hay corridas", salida)

    def test_preregistrar_id_inexistente(self):
        codigo, _, error = correr(["preregistrar", "--id", "no_existe"])
        self.assertEqual(codigo, 2)
        self.assertIn("no registrada", error)

    def test_sin_subcomando_falla(self):
        with self.assertRaises(SystemExit):
            correr([])

    def test_python_m_lab_arranca(self):
        import subprocess

        proceso = subprocess.run(
            [sys.executable, "-m", "lab", "--version"],
            cwd=str(RAIZ), capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proceso.returncode, 0, proceso.stderr)
        self.assertIn("lab 1.1.0", proceso.stdout)

    def test_datos_accion_listar(self):
        codigo, salida, _ = correr(["datos", "listar"])
        self.assertEqual(codigo, 0)
        self.assertIn("Conjuntos de datos", salida)


class TestComandosSobreRaizVacia(unittest.TestCase):
    """Comandos que deben funcionar sin corridas previas."""

    def setUp(self):
        self.raiz = espacio_temporal("cli_vacia")
        for nombre in ("hipotesis", "datos", "resultados"):
            (self.raiz / nombre).mkdir()
        (self.raiz / "hipotesis" / "__init__.py").write_text("", encoding="utf-8")

    def test_estado_json_sin_corridas(self):
        codigo, salida, _ = correr(["--raiz", str(self.raiz), "estado", "--json"])
        self.assertEqual(codigo, 0)
        self.assertIn("No hay corridas", salida)

    def test_panel_de_un_laboratorio_vacio(self):
        codigo, salida, _ = correr(["--raiz", str(self.raiz), "panel"])
        self.assertEqual(codigo, 0)
        indice = self.raiz / "panel" / "index.html"
        self.assertTrue(indice.is_file())
        self.assertIn("panel", salida.lower())

    def test_consolidado_sin_corridas(self):
        codigo, salida, _ = correr(["--raiz", str(self.raiz), "consolidado"])
        self.assertEqual(codigo, 0)
        self.assertTrue((self.raiz / "resultados" / "INFORME_CONSOLIDADO.md").is_file())

    def test_consolidado_con_salida(self):
        destino = self.raiz / "otro" / "informe.md"
        codigo, _, _ = correr(["--raiz", str(self.raiz), "consolidado",
                               "--salida", str(destino)])
        self.assertEqual(codigo, 0)
        self.assertTrue(destino.is_file())


class TestAndamiaje(unittest.TestCase):
    def setUp(self):
        self.raiz = espacio_temporal("cli")
        (self.raiz / "hipotesis").mkdir()
        (self.raiz / "datos").mkdir()
        (self.raiz / "hipotesis" / "__init__.py").write_text("", encoding="utf-8")

    def test_nuevo_crea_archivo_importable(self):
        codigo, salida, _ = correr([
            "--raiz", str(self.raiz), "nuevo",
            "--id", "mi_hipotesis", "--nombre", "Mi hipótesis",
        ])
        self.assertEqual(codigo, 0)
        destino = self.raiz / "hipotesis" / "mi_hipotesis.py"
        self.assertTrue(destino.is_file())
        texto = destino.read_text(encoding="utf-8")
        self.assertIn("class MiHipotesis(Hipotesis)", texto)
        self.assertIn('rango={"x": (0.0, 1.0)}', texto)
        compile(texto, str(destino), "exec")

    def test_nuevo_no_sobrescribe(self):
        correr(["--raiz", str(self.raiz), "nuevo", "--id", "h1",
                "--nombre", "H1"])
        codigo, _, error = correr(["--raiz", str(self.raiz), "nuevo",
                                   "--id", "h1", "--nombre", "H1"])
        self.assertEqual(codigo, 1)
        self.assertIn("Ya existe", error)

    def test_nuevo_rechaza_id_invalido(self):
        codigo, _, error = correr(["--raiz", str(self.raiz), "nuevo",
                                   "--id", "no-valido", "--nombre", "X"])
        self.assertEqual(codigo, 2)
        self.assertIn("no es un identificador", error)

    def test_hipotesis_incompleta_aparece_listada(self):
        correr(["--raiz", str(self.raiz), "nuevo", "--id", "h2", "--nombre", "H2"])
        codigo, salida, _ = correr(["--raiz", str(self.raiz), "hipotesis"])
        self.assertEqual(codigo, 0)
        self.assertIn("h2", salida)
        self.assertIn("TODO_dataset", salida)

    def test_preregistrar_rechaza_contrato_incompleto(self):
        correr(["--raiz", str(self.raiz), "nuevo", "--id", "h3", "--nombre", "H3"])
        archivo = self.raiz / "hipotesis" / "h3.py"
        texto = archivo.read_text(encoding="utf-8").replace(
            'enunciado = "TODO: una frase falsable"', 'enunciado = ""'
        )
        archivo.write_text(texto, encoding="utf-8")
        codigo, _, error = correr(["--raiz", str(self.raiz), "preregistrar",
                                   "--id", "h3"])
        self.assertEqual(codigo, 1)
        self.assertIn("contrato incompleto", error)

    def test_preregistrar_forzado(self):
        correr(["--raiz", str(self.raiz), "nuevo", "--id", "h6", "--nombre", "H6"])
        archivo = self.raiz / "hipotesis" / "h6.py"
        archivo.write_text(
            archivo.read_text(encoding="utf-8").replace(
                'enunciado = "TODO: una frase falsable"', 'enunciado = ""'),
            encoding="utf-8",
        )
        codigo, salida, _ = correr(["--raiz", str(self.raiz), "preregistrar",
                                    "--id", "h6", "--forzar"])
        self.assertEqual(codigo, 0)
        self.assertIn("Sello creado", salida)

    def test_ejecutar_sin_manifiesto_falla_claro(self):
        correr(["--raiz", str(self.raiz), "nuevo", "--id", "h4", "--nombre", "H4"])
        codigo, _, error = correr(["--raiz", str(self.raiz), "ejecutar", "--id", "h4"])
        self.assertEqual(codigo, 2)
        self.assertIn("manifiesto", error)

    def test_ejecutar_con_dataset_inexistente_falla_claro(self):
        from lab.datos import sha256_de_archivo

        correr(["--raiz", str(self.raiz), "nuevo", "--id", "h5", "--nombre", "H5"])
        csv = self.raiz / "datos" / "otro.csv"
        csv.write_text("x,y\n1,2\n2,4\n", encoding="utf-8")
        entrada = {
            "id": "otro",
            "ruta": "otro.csv",
            "sha256": sha256_de_archivo(csv),
            "descripcion": "auxiliar",
            "origen": "sintetico",
            "generado_por": "pruebas",
            "variables": ["x"],
            "observables": ["y"],
            "unidades": {"x": "u", "y": "u"},
            "filas": 2,
            "calibracion": [0],
            "reservado": [1],
        }
        (self.raiz / "datos" / "manifiesto.json").write_text(
            json.dumps({"version": 1, "datasets": [entrada]}), encoding="utf-8"
        )
        codigo, _, error = correr(["--raiz", str(self.raiz), "ejecutar", "--id", "h5"])
        # El dataset declarado por la hipótesis no está: se omite con aviso y,
        # como no se evaluó nada, el código de salida es 2.
        self.assertEqual(codigo, 2)
        self.assertIn("no está declarado", error)
        self.assertIn("TODO_dataset", error)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
