# Informe de evaluación — Péndulo: polinomio de grado 15 en la amplitud

**Hipótesis:** `pendulo_polinomio_alto` v1.0.0  
**Veredicto:** ❌ NO CORROBORADA — `NO_CORROBORADA`  
**Corrida:** `C:\atomo\laboratorio\resultados\pendulo_polinomio_alto_20261124T175746Z`  
**Fecha (UTC):** 2026-11-24T17:57:46.028963+00:00  
**Laboratorio:** v1.0.0

> La hipótesis no superó la comparación con el baseline o no generalizó. No se refuta la idea, pero este diseño no la sostiene.

**Motivo del veredicto:** La hipótesis no demuestra una mejora significativa sobre el baseline (T07): no se puede afirmar que aporte nada nuevo aquí. Además, el signo de la mejora cambia al cambiar la partición (T08): la conclusión depende del diseño.

## 1. Hipótesis contrastada

**Enunciado.** La dependencia del período con la amplitud no sigue una serie truncada, sino una curva suave que un polinomio de grado 15 representa mejor.

**Predicción diferenciadora.** Un polinomio flexible reproduce cualquier estructura fina de la curva T(θ0) que la serie de cuarto orden no captura, incluida la que aparece a amplitudes intermedias.

**Dominio de validez.** Péndulo simple ideal, amplitudes moderadas

| variable | mínimo | máximo |
|---|---|---|
| L_m | 0.4 | 2.5 |
| theta0_rad | 0 | 0.1 |

- Limitación declarada: Polinomio sin base física: no extrapola fuera del rango ajustado.

## 2. Baseline convencional

**`pendulo_lineal`** — Péndulo simple de pequeña amplitud v1.0.0

Supuestos: Amplitud despreciable (θ0 → 0), masa puntual, sin rozamiento, g fija. No depende de θ0.

## 3. Parámetros

| parámetro | valor declarado | unidad | estado | valor ajustado |
|---|---|---|---|---|
| g | 9.80665 | m/s^2 | congelado | — |
| mu | 0.6 | rad | congelado | — |
| s | 0.3 | rad | congelado | — |
| c0 | 0 | 1 | libre | 28853.2 |
| c1 | 0 | 1 | libre | 5832.83 |
| c2 | 0 | 1 | libre | -21794.9 |
| c3 | 0 | 1 | libre | 17375.8 |
| c4 | 0 | 1 | libre | 375.203 |
| c5 | 0 | 1 | libre | -16886.3 |
| c6 | 0 | 1 | libre | 17588.4 |
| c7 | 0 | 1 | libre | -84.219 |
| c8 | 0 | 1 | libre | -18336.4 |
| c9 | 0 | 1 | libre | 12719.9 |
| c10 | 0 | 1 | libre | 14585 |
| c11 | 0 | 1 | libre | -15973 |
| c12 | 0 | 1 | libre | -24417.7 |
| c13 | 0 | 1 | libre | -12111.5 |
| c14 | 0 | 1 | libre | -2754.97 |
| c15 | 0 | 1 | libre | -244.742 |

El ajuste usó 43 filas de calibración. Las 29 filas reservadas no participaron en el ajuste.

## 4. Datos y procedencia

| campo | valor |
|---|---|
| dataset | `pendulo_amplitud_pequena_v1` |
| filas | 72 |
| calibración / reservado | 43 / 29 |
| origen | sintetico |
| generado por | datos/generar_datos.py |
| SHA-256 | `1486b0b5872c28e5e355f04ab3bd7e176913aa6c9ca1dd14e1e2baf51033e623` |
| integridad | verificada |
| descripción | Péndulo simple sintético (72 filas), misma verdad generadora, amplitudes muy pequeñas. La corrección de amplitud vale del orden del ruido, así que un modelo flexible sólo puede ajustar ruido. |

## 5. Comparación con el baseline

| conjunto | error hipótesis | error baseline | métrica |
|---|---|---|---|
| calibración | 8.258104e-04 | 0.00108536 | rmse |
| reservado | 0.00127533 | 8.231526e-04 | rmse |

**Mejora relativa en reservado:** -0.5493 (IC 95 %: -1.336 a 0.09651, 2000 remuestreos).

**Umbral pre-registrado:** 0.1. **Decisión:** `PENDIENTE` — mejora -0.5493 < umbral 0.1000; el IC [-1.3360, 0.0965] no permite rechazar la equivalencia.

**Diferencia máxima con el baseline:** 0.00619995 s (sensibilidad declarada 1.000000e-04 s).

## 6. Matriz de pruebas

| código | prueba | estado | detalle |
|---|---|---|---|
| T01 | Formalización del contrato | `APROBADO` | Enunciado, dominio, unidades, baseline, métrica y umbrales declarados |
| T02 | Falsabilidad de la predicción | `APROBADO` | Predicción numérica finita y variable en 29 filas; el umbral de mejora 0.1 haría fallar la hipótesis si no se alcanza |
| T03 | Predicción diferenciadora frente al baseline | `APROBADO` | ΔO máximo 0.00619995 s supera la sensibilidad declarada 0.0001 |
| T04 | Preregistro de parámetros y umbrales | `APROBADO` | Sello verificado (7201651099dd…), creado 2026-11-24T17:57:45.021303+00:00 |
| T05 | Calibración restringida a la muestra de calibración | `APROBADO` | 16 parámetro(s) ajustado(s) sólo con 43 filas de calibración; 29 filas reservadas intactas |
| T06 | Validación fuera de muestra | `APROBADO` | Error fuera de muestra 0.00127533 dentro de 5× la escala 0.001 |
| T07 | Comparación con el baseline convencional | `PENDIENTE` | mejora -0.5493 < umbral 0.1000; el IC [-1.3360, 0.0965] no permite rechazar la equivalencia |
| T08 | Estabilidad de la conclusión ante el diseño | `SENSIBLE_AL_DISENO` | El signo de la mejora cambia con la partición: 3 positivas y 2 no positivas de 5. La conclusión depende del diseño, no sólo de los datos |
| T09 | Reproducibilidad numérica | `APROBADO` | Dos ejecuciones producen la misma predicción y el mismo bootstrap (03a66bc18840…) |
| T10 | Presupuesto de incertidumbre | `APROBADO` | El error observado es 1.28× la incertidumbre declarada |
| T11 | Control nulo por datos generados con el baseline | `APROBADO` | Sobre datos del baseline la mejora es -2.2906 (umbral exigido 0.1000): no se gana por artefacto |
| T12 | Dominio de validez declarado | `APROBADO` | 43 filas de calibración y 29 reservadas dentro del dominio declarado |

### Verificaciones opcionales

Pruebas que el laboratorio puede ejecutar además de las doce del protocolo. No son vinculantes: amplían el diagnóstico y no cambian el veredicto. «NO_REQUERIDA» significa que su precondición no se cumple en esta hipótesis, no que se haya superado.

| código | verificación | estado | motivo | resultado |
|---|---|---|---|---|
| O01 | Contraste con un baseline alternativo | `NO_REQUERIDA` | La hipótesis no declara baselines alternativos; sólo hay un modelo de referencia contra el que contrastar. |  |
| O02 | Validación por bloques del dominio | `NO_REQUERIDA` | Sólo hay 29 filas reservadas: no alcanzan para 3 bloques de 10 sin que cada bloque sea esencialmente ruido. |  |
| O03 | Sensibilidad al número de remuestreos | `NO_REQUERIDA` | No se pidió con --sensibilidad-bootstrap: recalcular el intervalo con otros tamaños duplica el coste sin cambiar la decisión. |  |
| O04 | Holdout externo | `NO_REQUERIDA` | La hipótesis no declara un dataset de validación independiente; reutilizar el reservado no sería un contraste externo. |  |
| O05 | Corrección por comparaciones múltiples | `NO_REQUERIDA` | Sólo una hipótesis usa este dataset: no hay familia de comparaciones que corregir. |  |

## 7. Estabilidad de la conclusión

Se repitió la comparación con 5 particiones alternativas (40 % reservado cada una).

| partición | semilla | error hipótesis | error baseline | mejora | ¿alcanza el umbral? |
|---|---|---|---|---|---|
| 0 | 20262125 | 0.00128328 | 9.442293e-04 | -0.3591 | no |
| 1 | 20263125 | 8.247721e-04 | 8.116589e-04 | -0.01616 | no |
| 2 | 20264125 | 7.870611e-04 | 9.271566e-04 | 0.1511 | sí |
| 3 | 20265125 | 9.044781e-04 | 9.096588e-04 | 0.005695 | no |
| 4 | 20266125 | 9.591428e-04 | 9.695593e-04 | 0.01074 | no |

Mejora mínima -0.3591, máxima 0.1511, media -0.04154. Alcanza el umbral en 20% de las particiones.

## 8. Control nulo

Se generaron datos sintéticos con el **baseline** como verdad y ruido σ = 0.001 (presupuesto de incertidumbre declarado por la hipótesis; si no consta, el ruido del dataset), y se repitió el procedimiento completo. Una hipótesis que gana aquí está explotando el diseño, no un fenómeno.

| campo | valor |
|---|---|
| mejora sobre datos nulos | -2.291 |
| IC inferior | -5.289 |
| IC superior | -0.1287 |
| umbral exigido | 0.1 |

## 9. Preregistro

| campo | valor |
|---|---|
| existe sello | sí |
| coincide con la firma actual | sí |
| creado durante la evaluación (tardío) | no |
| firma en el sello | 7201651099dd6f7f552f6f8d19539ecd9cece4ff1ab5af649ae969bd307a7978 |
| firma actual | 7201651099dd6f7f552f6f8d19539ecd9cece4ff1ab5af649ae969bd307a7978 |
| creado (UTC) | 2026-11-24T17:57:45.021303+00:00 |

## 10. Reproducibilidad

| comprobación | resultado |
|---|---|
| predicción idéntica en dos ejecuciones | sí |
| bootstrap idéntico con la misma semilla | sí |
| SHA-256 de la predicción | `03a66bc188406501e05d6e40a27d19328305ab8480276c7512d4cc270cf5248c` |

## 11. Qué no demuestra este informe

1. **No demuestra la hipótesis.** Una corroboración provisional es compatible con explicaciones alternativas y con el azar del diseño.
2. **No es replicación independiente.** Los datos y el código se ejecutaron una vez, en un solo entorno.
3. **No valida el baseline como verdad física.** El baseline es el modelo convencional de referencia, con sus propios supuestos.
4. **No extrapola fuera del dominio declarado** en la sección 1.
5. **No convierte un `PENDIENTE` en aprobación.** Un estado pendiente significa falta de evidencia.

## 12. Cómo reproducir esta corrida

```powershell
lab preregistrar --id pendulo_polinomio_alto
lab ejecutar --id pendulo_polinomio_alto
```

| entorno | valor |
|---|---|
| Python | 3.14.0 |
| NumPy | 2.5.4 |
| plataforma | Windows-11-10.0.26300-SP0 |
| archivo de la hipótesis | C:\atomo\laboratorio\hipotesis\pendulo_sobreajuste.py |
| SHA-256 de la hipótesis | `fdfb0c37b71f0a1c68ccf77725cda0cd49f13672b6deb041b2c9da05ab555278` |

