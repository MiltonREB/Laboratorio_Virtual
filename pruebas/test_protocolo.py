"""Pruebas de la batería T01–T12: cada estado debe alcanzarse de verdad.

Protocolo v1.1.0: cuatro estados (APROBADO, PENDIENTE, SENSIBLE, FALLIDO).
T07 y T08 no declaran fracaso; el caso vacuo y la ausencia de predicción se
marcan en la evidencia, no con estados extra.
"""

from __future__ import annotations

import unittest
from unittest import mock

import numpy as np

from lab import protocolo
from lab.contrato import Parametro
from lab.metricas import Decision, Intervalo
from lab.preregistro import Verificacion
from pruebas.ayudas import contexto, hipotesis_con


def _verif(estado: str = "VALIDO", **cambios) -> Verificacion:
    base = dict(
        estado_preregistro=estado,
        firma_actual="a" * 64,
        firma_en_sello=None if estado == "AUSENTE" else (
            "b" * 64 if estado == "ALTERADO" else "a" * 64),
        ruta=None if estado == "AUSENTE" else "sellos/x.json",
        creado_utc=None if estado == "AUSENTE" else "2026-01-01T00:00:00+00:00",
        antiguedad_segundos=None if estado == "AUSENTE" else 3600.0,
        separacion_minima=60.0,
        publicado_utc=None,
    )
    base.update(cambios)
    return Verificacion(**base)


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

    def test_prediccion_constante_falsable_no_es_ausencia(self):
        r = protocolo.t02_falsabilidad(contexto(pred_hip=np.full(4, 3.0)))
        self.assertEqual(r.estado, "APROBADO")
        self.assertFalse(r.es_ausencia)

    def test_fallido_con_no_finitos(self):
        r = protocolo.t02_falsabilidad(
            contexto(pred_hip=np.array([1.0, np.nan, 2.0, 3.0]))
        )
        self.assertEqual(r.estado, "FALLIDO")


class TestT03Diferenciadora(unittest.TestCase):
    """El criterio es relativo a la escala del baseline, no una tolerancia fija."""

    def test_pendiente_si_iguala_al_baseline(self):
        base = np.array([1.0, 2.0, 3.0, 4.0])
        r = protocolo.t03_prediccion_diferenciadora(contexto(pred_hip=base, pred_base=base))
        self.assertEqual(r.estado, "PENDIENTE")
        self.assertTrue(r.es_ausencia)

    def test_pendiente_si_no_supera_la_escala_del_baseline(self):
        base = np.array([1.0, 2.0, 3.0, 4.0])
        r = protocolo.t03_prediccion_diferenciadora(
            contexto(pred_hip=base + 0.01, pred_base=base)
        )
        self.assertEqual(r.estado, "PENDIENTE")
        self.assertTrue(r.es_ausencia)
        self.assertAlmostEqual(r.evidencia["escala_baseline"], 0.5)

    def test_aprobado_al_superar_la_escala(self):
        base = np.array([1.0, 2.0, 3.0, 4.0])
        r = protocolo.t03_prediccion_diferenciadora(
            contexto(pred_hip=base + 0.6, pred_base=base)
        )
        self.assertEqual(r.estado, "APROBADO")
        self.assertAlmostEqual(r.evidencia["veces_la_escala"], 1.2)

    def test_el_factor_declarado_endurece_el_criterio(self):
        base = np.array([1.0, 2.0, 3.0, 4.0])
        flojo = protocolo.t03_prediccion_diferenciadora(
            contexto(pred_hip=base + 0.6, pred_base=base)
        )
        exigente = protocolo.t03_prediccion_diferenciadora(
            contexto(
                hipotesis=hipotesis_con(factor_diferenciacion=2.0),
                pred_hip=base + 0.6, pred_base=base,
            )
        )
        self.assertEqual(flojo.estado, "APROBADO")
        self.assertEqual(exigente.estado, "PENDIENTE")

    def test_el_suelo_absoluto_solo_puede_endurecer(self):
        base = np.array([1.0, 2.0, 3.0, 4.0])
        r = protocolo.t03_prediccion_diferenciadora(
            contexto(
                hipotesis=hipotesis_con(umbral_sensibilidad=0.8),
                pred_hip=base + 0.6, pred_base=base,
            )
        )
        self.assertEqual(r.estado, "PENDIENTE")


class TestT04Preregistro(unittest.TestCase):
    def test_pendiente_sin_verificacion(self):
        self.assertEqual(protocolo.t04_preregistro(contexto()).estado, "PENDIENTE")

    def test_pendiente_sin_sello(self):
        r = protocolo.t04_preregistro(contexto(verificacion=_verif("AUSENTE")))
        self.assertEqual(r.estado, "PENDIENTE")
        self.assertIn("preregistrar", r.detalle)

    def test_fallido_si_la_firma_cambio(self):
        r = protocolo.t04_preregistro(contexto(verificacion=_verif("ALTERADO")))
        self.assertEqual(r.estado, "FALLIDO")

    def test_pendiente_si_es_tardio(self):
        r = protocolo.t04_preregistro(contexto(verificacion=_verif("TARDIO")))
        self.assertEqual(r.estado, "PENDIENTE")

    def test_pendiente_si_es_reciente(self):
        r = protocolo.t04_preregistro(
            contexto(verificacion=_verif("RECIENTE", antiguedad_segundos=2.0))
        )
        self.assertEqual(r.estado, "PENDIENTE")
        self.assertIn("separación", r.detalle)

    def test_pendiente_si_no_esta_publicado(self):
        r = protocolo.t04_preregistro(contexto(verificacion=_verif("NO_PUBLICADO")))
        self.assertEqual(r.estado, "PENDIENTE")

    def test_aprobado_si_verificado(self):
        r = protocolo.t04_preregistro(contexto(verificacion=_verif()))
        self.assertEqual(r.estado, "APROBADO")
        self.assertEqual(r.evidencia["estado_preregistro"], "VALIDO")


class TestT05Calibracion(unittest.TestCase):
    def test_aprobado_vacuo_sin_parametros_libres(self):
        h = hipotesis_con(PARAMETROS=(Parametro("a", 1.0, "u"),))
        r = protocolo.t05_calibracion(contexto(hipotesis=h))
        self.assertEqual(r.estado, "APROBADO")
        self.assertTrue(r.evidencia["vacuo"])

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
        self.assertEqual(protocolo.t05_calibracion(ctx).estado, "FALLIDO")


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

    def test_hereda_la_decision_aprobada(self):
        ctx = contexto(
            intervalo_reservado=_intervalo(),
            decision_baseline=Decision("APROBADO", "mejora suficiente"),
        )
        r = protocolo.t07_baseline(ctx)
        self.assertEqual(r.estado, "APROBADO")
        self.assertEqual(r.detalle, "mejora suficiente")

    def test_nunca_devuelve_fallido_ni_con_el_baseline_mejor(self):
        ctx = contexto(
            intervalo_reservado=_intervalo(-0.5, -0.6, -0.4),
            decision_baseline=Decision("FALLIDO", "el baseline es mejor"),
        )
        r = protocolo.t07_baseline(ctx)
        self.assertEqual(r.estado, "PENDIENTE")
        self.assertTrue(r.evidencia["peor_que_baseline"])

    def test_registra_el_ratio_de_errores(self):
        ctx = contexto(
            intervalo_reservado=_intervalo(),
            decision_baseline=Decision("APROBADO", "ok"),
        )
        r = protocolo.t07_baseline(ctx)
        self.assertAlmostEqual(r.evidencia["ratio_errores"], 0.2)


class TestT08Estabilidad(unittest.TestCase):
    def test_aprobado_si_todas_positivas(self):
        self.assertEqual(protocolo.t08_estabilidad(contexto()).estado, "APROBADO")

    def test_pendiente_si_todas_negativas(self):
        ctx = contexto(estabilidad={"ensayos": [
            {"particion": 0, "mejora": -0.1}, {"particion": 1, "mejora": -0.2}]})
        self.assertEqual(protocolo.t08_estabilidad(ctx).estado, "PENDIENTE")

    def test_sensible_si_cambia_el_signo(self):
        ctx = contexto(estabilidad={"ensayos": [
            {"particion": 0, "mejora": 0.3}, {"particion": 1, "mejora": -0.1}]})
        self.assertEqual(protocolo.t08_estabilidad(ctx).estado, "SENSIBLE")

    def test_nunca_devuelve_fallido(self):
        ctx = contexto(estabilidad={"ensayos": [
            {"particion": 0, "mejora": -0.3}, {"particion": 1, "mejora": 0.1}]})
        self.assertNotEqual(protocolo.t08_estabilidad(ctx).estado, "FALLIDO")

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
        from lab.contrato import Dominio

        h = hipotesis_con()
        h.dominio = Dominio("estrecho", {"x": (0.0, 1.0)})
        self.assertEqual(protocolo.t12_dominio(contexto(hipotesis=h)).estado, "FALLIDO")

    def test_fallido_sin_dominio(self):
        self.assertEqual(
            protocolo.t12_dominio(contexto(hipotesis=hipotesis_con(dominio=None))).estado,
            "FALLIDO",
        )

    def test_evidencia_incluye_rango_observado(self):
        r = protocolo.t12_dominio(contexto())
        self.assertIn("observado", r.evidencia)
        # calibración + reservado del contexto de prueba comparten 4 filas cada uno
        self.assertEqual(r.evidencia["observado"]["x"]["filas"], 8)


class TestBateria(unittest.TestCase):
    def test_ejecuta_las_doce_en_orden(self):
        resultados = protocolo.ejecutar_pruebas(contexto())
        self.assertEqual([r.codigo for r in resultados], list(protocolo.ORDEN))
        self.assertEqual(len(resultados), 12)

    def test_solo_hay_cuatro_estados(self):
        from lab.contrato import ESTADOS

        self.assertEqual(ESTADOS, ("APROBADO", "PENDIENTE", "SENSIBLE", "FALLIDO"))
        for resultado in protocolo.ejecutar_pruebas(contexto()):
            self.assertIn(resultado.estado, ESTADOS)

    def test_una_prueba_rota_no_aprueba(self):
        def explota(ctx):
            raise RuntimeError("fallo simulado")

        with mock.patch.dict(protocolo.PRUEBAS, {"T03": explota}):
            resultados = protocolo.ejecutar_pruebas(contexto())
        mapa = {r.codigo: r.estado for r in resultados}
        self.assertEqual(mapa["T03"], "PENDIENTE")

    def test_las_doce_son_bloqueantes(self):
        self.assertEqual(protocolo.BLOQUEANTES, frozenset(protocolo.ORDEN))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
