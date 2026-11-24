# Informe de evaluación — Corrección de amplitud finita del péndulo

**Hipótesis:** `pendulo_amplitud` v1.0.0  
**Veredicto:** ✅ CORROBORADA (provisional) — `CORROBORADA_PROVISIONAL`  
**Corrida:** `C:\atomo\laboratorio\resultados\pendulo_amplitud_20261124T175745Z`  
**Fecha (UTC):** 2026-11-24T17:57:45.836276+00:00  
**Laboratorio:** v1.0.0

> Todas las pruebas bloqueantes se cumplieron sobre datos reservados. Es corroboración provisional, no demostración: no sustituye replicación independiente ni excluye explicaciones alternativas.

**Motivo del veredicto:** Se cumplieron todas las pruebas bloqueantes y la conclusión es estable ante particiones alternativas.

## 1. Hipótesis contrastada

**Enunciado.** A amplitud finita, el período del péndulo simple es mayor que 2π√(L/g) y crece con θ0² y θ0⁴.

**Predicción diferenciadora.** Para θ0 = 1.2 rad el modelo predice un período ≈ 9 % mayor que el baseline de pequeña amplitud; la separación crece cuadráticamente con θ0. El baseline predice separación nula, así que un barrido en amplitud distingue las dos propuestas sin ambigüedad.

**Dominio de validez.** Péndulo simple ideal, amplitudes moderadas, una sola masa

| variable | mínimo | máximo |
|---|---|---|
| L_m | 0.4 | 2.5 |
| theta0_rad | 0 | 1.4 |

- Limitación declarada: Sin rozamiento, sin masa de hilo, sin elasticidad.
- Limitación declarada: Más allá de θ0 ≈ 1.4 rad la serie de cuarto orden deja de ser suficiente.

## 2. Baseline convencional

**`pendulo_lineal`** — Péndulo simple de pequeña amplitud v1.0.0

Supuestos: Amplitud despreciable (θ0 → 0), masa puntual, sin rozamiento, g fija. No depende de θ0.

## 3. Parámetros

| parámetro | valor declarado | unidad | estado | valor ajustado |
|---|---|---|---|---|
| g | 9.80665 | m/s^2 | congelado | — |
| c2 | 0 | rad^-2 | libre | 0.0624705 |
| c4 | 0 | rad^-4 | libre | 0.00359531 |

El ajuste usó 144 filas de calibración. Las 96 filas reservadas no participaron en el ajuste.

## 4. Datos y procedencia

| campo | valor |
|---|---|
| dataset | `pendulo_v1` |
| filas | 240 |
| calibración / reservado | 144 / 96 |
| origen | sintetico |
| generado por | datos/generar_datos.py |
| SHA-256 | `cef7a81feda152e638de81dc176966e8eee0b5d34bb3cf24504f9d11b7864b1b` |
| integridad | verificada |
| descripción | Péndulo simple sintético (240 filas). Control de la maquinaria del laboratorio: la verdad generadora es T = 2π√(L/g)(1+θ²/16+11θ⁴/3072) + ruido gaussiano σ=8e-4 s. No es una medición física. |

## 5. Comparación con el baseline

| conjunto | error hipótesis | error baseline | métrica |
|---|---|---|---|
| calibración | 8.082716e-04 | 0.107478 | rmse |
| reservado | 8.172198e-04 | 0.0891609 | rmse |

**Mejora relativa en reservado:** 0.9908 (IC 95 %: 0.9887 a 0.9925, 2000 remuestreos).

**Umbral pre-registrado:** 0.1. **Decisión:** `APROBADO` — mejora 0.9908 ≥ umbral 0.1000 e IC [0.9887, 0.9925] excluye el cero.

**Diferencia máxima con el baseline:** 0.243358 s (sensibilidad declarada 1.000000e-04 s).

## 6. Matriz de pruebas

| código | prueba | estado | detalle |
|---|---|---|---|
| T01 | Formalización del contrato | `APROBADO` | Enunciado, dominio, unidades, baseline, métrica y umbrales declarados |
| T02 | Falsabilidad de la predicción | `APROBADO` | Predicción numérica finita y variable en 96 filas; el umbral de mejora 0.1 haría fallar la hipótesis si no se alcanza |
| T03 | Predicción diferenciadora frente al baseline | `APROBADO` | ΔO máximo 0.243358 s supera la sensibilidad declarada 0.0001 |
| T04 | Preregistro de parámetros y umbrales | `APROBADO` | Sello verificado (2a1bbdc6b61f…), creado 2026-11-24T17:57:44.572783+00:00 |
| T05 | Calibración restringida a la muestra de calibración | `APROBADO` | 2 parámetro(s) ajustado(s) sólo con 144 filas de calibración; 96 filas reservadas intactas |
| T06 | Validación fuera de muestra | `APROBADO` | Error fuera de muestra 0.00081722 dentro de 5× la escala 0.001 |
| T07 | Comparación con el baseline convencional | `APROBADO` | mejora 0.9908 ≥ umbral 0.1000 e IC [0.9887, 0.9925] excluye el cero |
| T08 | Estabilidad de la conclusión ante el diseño | `APROBADO` | La mejora conserva el signo en 5 particiones alternativas (mínima 0.9909) |
| T09 | Reproducibilidad numérica | `APROBADO` | Dos ejecuciones producen la misma predicción y el mismo bootstrap (9b6543d09bb6…) |
| T10 | Presupuesto de incertidumbre | `APROBADO` | El error observado es 0.82× la incertidumbre declarada |
| T11 | Control nulo por datos generados con el baseline | `APROBADO` | Sobre datos del baseline la mejora es -0.0048 (umbral exigido 0.1000): no se gana por artefacto |
| T12 | Dominio de validez declarado | `APROBADO` | 144 filas de calibración y 96 reservadas dentro del dominio declarado |

### Verificaciones opcionales

Pruebas que el laboratorio puede ejecutar además de las doce del protocolo. No son vinculantes: amplían el diagnóstico y no cambian el veredicto. «NO_REQUERIDA» significa que su precondición no se cumple en esta hipótesis, no que se haya superado.

| código | verificación | estado | motivo | resultado |
|---|---|---|---|---|
| O01 | Contraste con un baseline alternativo | `EJECUTADA` | La hipótesis declara al menos un baseline alternativo. | Mejora frente a cada baseline alternativo: pendulo_segundo_orden +0.847, pendulo_serie_cuarto_orden -0.000. No supera a pendulo_serie_cuarto_orden: frente a ese modelo la hipótesis no aporta nada, y la ventaja observada puede venir del ajuste o de lo incompleto del baseline principal. |
| O02 | Validación por bloques del dominio | `EJECUTADA` | Hay 96 filas reservadas, suficientes para 3 bloques de 10. | La mejora se mantiene en los 3 bloques de 'L_m'. |
| O03 | Sensibilidad al número de remuestreos | `NO_REQUERIDA` | No se pidió con --sensibilidad-bootstrap: recalcular el intervalo con otros tamaños duplica el coste sin cambiar la decisión. |  |
| O04 | Holdout externo | `EJECUTADA` | Dataset de validación independiente: 'pendulo_holdout_v1'. | En el holdout externo (80 filas) la mejora es +0.9806 (error 0.00131574 frente a 0.067948). |
| O05 | Corrección por comparaciones múltiples | `NO_REQUERIDA` | Sólo una hipótesis usa este dataset: no hay familia de comparaciones que corregir. |  |

## 7. Estabilidad de la conclusión

Se repitió la comparación con 5 particiones alternativas (40 % reservado cada una).

| partición | semilla | error hipótesis | error baseline | mejora | ¿alcanza el umbral? |
|---|---|---|---|---|---|
| 0 | 20262124 | 7.790704e-04 | 0.107011 | 0.9927 | sí |
| 1 | 20263124 | 8.233127e-04 | 0.102268 | 0.9919 | sí |
| 2 | 20264124 | 8.016515e-04 | 0.096285 | 0.9917 | sí |
| 3 | 20265124 | 8.216565e-04 | 0.0954076 | 0.9914 | sí |
| 4 | 20266124 | 8.672265e-04 | 0.0951521 | 0.9909 | sí |

Mejora mínima 0.9909, máxima 0.9927, media 0.9917. Alcanza el umbral en 100% de las particiones.

## 8. Control nulo

Se generaron datos sintéticos con el **baseline** como verdad y ruido σ = 0.001 (presupuesto de incertidumbre declarado por la hipótesis; si no consta, el ruido del dataset), y se repitió el procedimiento completo. Una hipótesis que gana aquí está explotando el diseño, no un fenómeno.

| campo | valor |
|---|---|
| mejora sobre datos nulos | -0.004766 |
| IC inferior | -0.03573 |
| IC superior | 0.02666 |
| umbral exigido | 0.1 |

## 9. Preregistro

| campo | valor |
|---|---|
| existe sello | sí |
| coincide con la firma actual | sí |
| creado durante la evaluación (tardío) | no |
| firma en el sello | 2a1bbdc6b61f77de2f181902d61efad2fe44ba140bb996c01e5fb7695e2089d3 |
| firma actual | 2a1bbdc6b61f77de2f181902d61efad2fe44ba140bb996c01e5fb7695e2089d3 |
| creado (UTC) | 2026-11-24T17:57:44.572783+00:00 |

## 10. Reproducibilidad

| comprobación | resultado |
|---|---|
| predicción idéntica en dos ejecuciones | sí |
| bootstrap idéntico con la misma semilla | sí |
| SHA-256 de la predicción | `9b6543d09bb6e8073cec367aa93a621c60d6e2a182c4c27ca73141d5bab59e97` |

## 11. Qué no demuestra este informe

1. **No demuestra la hipótesis.** Una corroboración provisional es compatible con explicaciones alternativas y con el azar del diseño.
2. **No es replicación independiente.** Los datos y el código se ejecutaron una vez, en un solo entorno.
3. **No valida el baseline como verdad física.** El baseline es el modelo convencional de referencia, con sus propios supuestos.
4. **No extrapola fuera del dominio declarado** en la sección 1.
5. **No convierte un `PENDIENTE` en aprobación.** Un estado pendiente significa falta de evidencia.

## 12. Cómo reproducir esta corrida

```powershell
lab preregistrar --id pendulo_amplitud
lab ejecutar --id pendulo_amplitud
```

| entorno | valor |
|---|---|
| Python | 3.14.0 |
| NumPy | 2.5.4 |
| plataforma | Windows-11-10.0.26300-SP0 |
| archivo de la hipótesis | C:\atomo\laboratorio\hipotesis\pendulo_amplitud.py |
| SHA-256 de la hipótesis | `8d6ea4f64e08ae9477ae804fa054fd83779b208644addd7d96af7d46f297735f` |

