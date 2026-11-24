"""Pruebas de la batería T01–T12: cada estado debe alcanzarse de verdad."""

from __future__ import annotations

import unittest
from unittest import mock

import numpy as np

from lab import protocolo
from lab.contrato import Parametro
from lab.metricas import Decision, Intervalo
from lab.preregistro import Verificacion
from pruebas.ayudas import contexto, hipotesis_con


def _verif(existe=True, coincide=True, tardio=False):
    return Verificacion(
        existe=existe,
        coincide=coincide,
        tardio=tardio,
        firma_en_sello="a" * 64 if existe else None,
        firma_actual="a" * 64 if coincide else "b" * 64,
        ruta="sellos/x.json" if existe else None,
        creado_utc="2026-01-01T00:00:00+00:00" if existe else None,
    )


def _intervalo(mejora=0.5, inferior=0.4, superior=0.6):
    return Intervalo(mejora, inferior, superior, 0.95, 100, 100)


class TestT01Formalizacion(unittest.TestCase):
    def test_aprobado_con_contrato_completo(self):
        self.assertEqual(protocolo.t01_formalizacion(contexto()).estado, "APROBADO")

    def test_fallido_con_contrato_incompleto(self):
        r = protocolo.t01_formalizacion(contexto(hipotesis=hipotesis_con(enunciado="")))
        self.assertEqual(r.estado, "FALLIDO")
        self.assertTrue(r.evidencia["faltantes"])


class TestT02Falsabilidad(unittest.TestCase):
    def test_aprobado_con_prediccion_variable(self):
        self.assertEqual(protocolo.t02_falsabilidad(contexto()).estado, "APROBADO")

    def test_fallido_con_prediccion_constante(self):
        r = protocolo.t02_falsabilidad(contexto(pred_hip=np.full(4, 3.0)))
        self.assertEqual(r.estado, "FALLIDO")

    def test_fallido_con_no_finitos(self):
        with np.errstate(invalid="ignore"):
            r = protocolo.t02_falsabilidad(
                contexto(pred_hip=np.array([1.0, np.nan, 2.0, 3.0]))
            )
        self.assertEqual(r.estado, "FALLIDO")


class TestT03Diferenciadora(unittest.TestCase):
    def test_no_presentada_si_iguala_al_baseline(self):
        base = np.array([1.0, 2.0, 3.0, 4.0])
        r = protocolo.t03_prediccion_diferenciadora(contexto(pred_hip=base, pred_base=base))
        self.assertEqual(r.estado, "NO_PRESENTADA")

    def test_no_presentada_bajo_el_umbral(self):
        base = np.array([1.0, 2.0, 3.0, 4.0])
        r = protocolo.t03_prediccion_diferenciadora(
            contexto(pred_hip=base + 1e-6, pred_base=base)
        )
        self.assertEqual(r.estado, "NO_PRESENTADA")

    def test_aprobado_sobre_el_umbral(self):
        base = np.array([1.0, 2.0, 3.0, 4.0])
        r = protocolo.t03_prediccion_diferenciadora(
            contexto(pred_hip=base + 0.5, pred_base=base)
        )
        self.assertEqual(r.estado, "APROBADO")
        self.assertAlmostEqual(r.evidencia["delta_max_abs"], 0.5)


class TestT04Preregistro(unittest.TestCase):
    def test_pendiente_sin_verificacion(self):
        self.assertEqual(protocolo.t04_preregistro(contexto()).estado, "PENDIENTE")

    def test_pendiente_sin_sello(self):
        r = protocolo.t04_preregistro(contexto(verificacion=_verif(existe=False)))
        self.assertEqual(r.estado, "PENDIENTE")
        self.assertIn("preregistrar", r.detalle)

    def test_fallido_si_no_coincide(self):
        r = protocolo.t04_preregistro(
            contexto(verificacion=_verif(coincide=False))
        )
        self.assertEqual(r.estado, "FALLIDO")

    def test_pendiente_si_es_tardio(self):
        r = protocolo.t04_preregistro(contexto(verificacion=_verif(tardio=True)))
        self.assertEqual(r.estado, "PENDIENTE")

    def test_aprobado_si_verificado(self):
        self.assertEqual(
            protocolo.t04_preregistro(contexto(verificacion=_verif())).estado,
            "APROBADO",
        )


class TestT05Calibracion(unittest.TestCase):
    def test_no_aplicable_sin_parametros_libres(self):
        h = hipotesis_con(PARAMETROS=(Parametro("a", 1.0, "u"),))
        self.assertEqual(protocolo.t05_calibracion(contexto(hipotesis=h)).estado,
                         "NO_APLICABLE")

    def test_aprobado_con_ajuste(self):
        self.assertEqual(protocolo.t05_calibracion(contexto()).estado, "APROBADO")

    def test_fallido_si_no_hay_ajuste(self):
        r = protocolo.t05_calibracion(contexto(ajuste_usado=False))
        self.assertEqual(r.estado, "FALLIDO")

    def test_fallido_si_las_particiones_se_solapan(self):
        from pruebas.ayudas import conjunto_de_prueba

        ctx = contexto()
        malo = conjunto_de_prueba()
        object.__setattr__(malo, "reservado", (0, 1, 2))
        ctx.dataset = malo
        r = protocolo.t05_calibracion(ctx)
        self.assertEqual(r.estado, "FALLIDO")


class TestT06FueraDeMuestra(unittest.TestCase):
    def test_aprobado_con_error_pequeno(self):
        self.assertEqual(protocolo.t06_fuera_de_muestra(contexto()).estado, "APROBADO")

    def test_fallido_con_error_enorme(self):
        r = protocolo.t06_fuera_de_muestra(
            contexto(errores_reservado={"hipotesis": 500.0, "baseline": 0.5})
        )
        self.assertEqual(r.estado, "FALLIDO")

    def test_fallido_con_error_no_finito(self):
        r = protocolo.t06_fuera_de_muestra(
            contexto(errores_reservado={"hipotesis": float("nan"), "baseline": 0.5})
        )
        self.assertEqual(r.estado, "FALLIDO")


class TestT07Baseline(unittest.TestCase):
    def test_sin_intervalo_queda_pendiente(self):
        self.assertEqual(protocolo.t07_baseline(contexto()).estado, "PENDIENTE")

    def test_hereda_la_decision(self):
        ctx = contexto(
            intervalo_reservado=_intervalo(),
            decision_baseline=Decision("APROBADO", "mejora suficiente"),
        )
        r = protocolo.t07_baseline(ctx)
        self.assertEqual(r.estado, "APROBADO")
        self.assertEqual(r.detalle, "mejora suficiente")


class TestT08Estabilidad(unittest.TestCase):
    def test_aprobado_si_todas_positivas(self):
        self.assertEqual(protocolo.t08_estabilidad(contexto()).estado, "APROBADO")

    def test_fallido_si_todas_negativas(self):
        ctx = contexto(estabilidad={"ensayos": [
            {"particion": 0, "mejora": -0.1}, {"particion": 1, "mejora": -0.2}]})
        self.assertEqual(protocolo.t08_estabilidad(ctx).estado, "FALLIDO")

    def test_sensible_si_cambia_el_signo(self):
        ctx = contexto(estabilidad={"ensayos": [
            {"particion": 0, "mejora": 0.3}, {"particion": 1, "mejora": -0.1}]})
        self.assertEqual(protocolo.t08_estabilidad(ctx).estado, "SENSIBLE_AL_DISENO")

    def test_pendiente_sin_ensayos(self):
        self.assertEqual(protocolo.t08_estabilidad(contexto(estabilidad={})).estado,
                         "PENDIENTE")


class TestT09Reproducibilidad(unittest.TestCase):
    def test_aprobado(self):
        self.assertEqual(protocolo.t09_reproducibilidad(contexto()).estado, "APROBADO")

    def test_fallido_si_difiere(self):
        ctx = contexto(reproducibilidad={
            "prediccion_identica": False, "bootstrap_identico": True})
        self.assertEqual(protocolo.t09_reproducibilidad(ctx).estado, "FALLIDO")

    def test_pendiente_sin_datos(self):
        self.assertEqual(protocolo.t09_reproducibilidad(contexto(reproducibilidad={})).estado,
                         "PENDIENTE")


class TestT10Incertidumbre(unittest.TestCase):
    def test_pendiente_sin_declarar(self):
        h = hipotesis_con(incertidumbre_declarada=float("nan"))
        self.assertEqual(protocolo.t10_incertidumbre(contexto(hipotesis=h)).estado,
                         "PENDIENTE")

    def test_fallido_si_subestima(self):
        h = hipotesis_con(incertidumbre_declarada=0.5)
        r = protocolo.t10_incertidumbre(
            contexto(hipotesis=h, errores_reservado={"hipotesis": 20.0, "baseline": 0.5})
        )
        self.assertEqual(r.estado, "FALLIDO")

    def test_pendiente_si_esta_inflada(self):
        h = hipotesis_con(incertidumbre_declarada=0.5)
        r = protocolo.t10_incertidumbre(
            contexto(hipotesis=h, errores_reservado={"hipotesis": 0.001, "baseline": 0.5})
        )
        self.assertEqual(r.estado, "PENDIENTE")

    def test_aprobado_si_es_coherente(self):
        h = hipotesis_con(incertidumbre_declarada=0.5)
        r = protocolo.t10_incertidumbre(
            contexto(hipotesis=h, errores_reservado={"hipotesis": 0.25, "baseline": 0.5})
        )
        self.assertEqual(r.estado, "APROBADO")


class TestT11ControlNulo(unittest.TestCase):
    def test_aprobado_si_no_gana(self):
        self.assertEqual(protocolo.t11_control_nulo(contexto()).estado, "APROBADO")

    def test_fallido_si_gana_sobre_datos_del_baseline(self):
        ctx = contexto(control_nulo={
            "mejora": 0.5, "ic_inferior": 0.4, "ic_superior": 0.6})
        self.assertEqual(protocolo.t11_control_nulo(ctx).estado, "FALLIDO")

    def test_pendiente_si_no_se_ejecuto(self):
        self.assertEqual(protocolo.t11_control_nulo(contexto(control_nulo={})).estado,
                         "PENDIENTE")

    def test_pendiente_si_fallo(self):
        ctx = contexto(control_nulo={"error": "sin ruido"})
        self.assertEqual(protocolo.t11_control_nulo(ctx).estado, "PENDIENTE")


class TestT12Dominio(unittest.TestCase):
    def test_aprobado_dentro(self):
        self.assertEqual(protocolo.t12_dominio(contexto()).estado, "APROBADO")

    def test_fallido_fuera(self):
        h = hipotesis_con()
        from lab.contrato import Dominio

        h.dominio = Dominio("estrecho", {"x": (0.0, 1.0)})
        r = protocolo.t12_dominio(contexto(hipotesis=h))
        self.assertEqual(r.estado, "FALLIDO")

    def test_fallido_sin_dominio(self):
        self.assertEqual(
            protocolo.t12_dominio(contexto(hipotesis=hipotesis_con(dominio=None))).estado,
            "FALLIDO",
        )


class TestBateria(unittest.TestCase):
    def test_ejecuta_las_doce_en_orden(self):
        resultados = protocolo.ejecutar_pruebas(contexto())
        self.assertEqual([r.codigo for r in resultados], list(protocolo.ORDEN))
        self.assertEqual(len(resultados), 12)

    def test_una_prueba_rota_no_aprueba(self):
        def explota(ctx):
            raise RuntimeError("fallo simulado")

        with mock.patch.dict(protocolo.PRUEBAS, {"T03": explota}):
            resultados = protocolo.ejecutar_pruebas(contexto())
        mapa = {r.codigo: r.estado for r in resultados}
        self.assertEqual(mapa["T03"], "PENDIENTE")

    def test_bloqueantes_incluye_las_criticas(self):
        for codigo in ("T01", "T02", "T03", "T04", "T06", "T07", "T09", "T10", "T11", "T12"):
            self.assertIn(codigo, protocolo.BLOQUEANTES)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
