# Informe consolidado del laboratorio

**Generado (UTC):** 2026-11-24 17:57  
**Hipótesis con corrida:** 2  
**Corridas registradas:** 2

## 1. Resumen por hipótesis

| hipótesis | veredicto | mejora | IC 95 % | umbral | error reservado | dataset | corridas |
|---|---|---|---|---|---|---|---|
| `pendulo_amplitud` | **CORROBORADA_PROVISIONAL** | +0.9908 | [+0.9887, +0.9925] | 0.1 | 8.17e-04 | `pendulo_v1` | 1 |
| `pendulo_polinomio_alto` | **NO_CORROBORADA** | -0.5493 | [-1.3360, +0.0965] | 0.1 | 0.001275 | `pendulo_amplitud_pequena_v1` | 1 |

## 2. Matriz de pruebas

| hipótesis | T01 | T02 | T03 | T04 | T05 | T06 | T07 | T08 | T09 | T10 | T11 | T12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `pendulo_amplitud` | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| `pendulo_polinomio_alto` | ok | ok | ok | ok | ok | ok | · | sn | ok | ok | ok | ok |

Leyenda: ok=aprobado, X=fallido, ·=pendiente, —=no aplicable, np=no presentada, sn=sensible al diseño.

## 3. Lo que no se sostiene

### `pendulo_polinomio_alto` — NO_CORROBORADA

La hipótesis no demuestra una mejora significativa sobre el baseline (T07): no se puede afirmar que aporte nada nuevo aquí. Además, el signo de la mejora cambia al cambiar la partición (T08): la conclusión depende del diseño.

_La hipótesis no superó la comparación con el baseline o no generalizó. No se refuta la idea, pero este diseño no la sostiene._


## 4. Verificaciones opcionales ejecutadas

| hipótesis | código | hallazgo | resultado |
|---|---|---|---|
| `pendulo_amplitud` | O01 | NO gana a todos | Mejora frente a cada baseline alternativo: pendulo_segundo_orden +0.847, pendulo_serie_cuarto_orden -0.000. No supera a pendulo_serie_cuarto_orden: frente a ese modelo la hipótesis no aporta nada, y la ventaja observada puede venir del ajuste o de lo incompleto del baseline principal. |
| `pendulo_amplitud` | O02 | CONSISTENTE | La mejora se mantiene en los 3 bloques de 'L_m'. |
| `pendulo_amplitud` | O04 | supera | En el holdout externo (80 filas) la mejora es +0.9806 (error 0.00131574 frente a 0.067948). |

## 5. Avisos de familia y de repetición

- No hay dos hipótesis sobre el mismo dataset, así que no hay familia de comparaciones que corregir en este conjunto.
- Cada hipótesis tiene una sola corrida registrada: no hay selección posterior al resultado.

## 7. Qué no dice este informe

1. No agrega evidencia entre hipótesis: cada veredicto vale por sí solo.
2. No corrige por comparaciones múltiples salvo que O05 se haya ejecutado.
3. No convierte una corroboración provisional en demostración.
4. No sustituye la replicación independiente con datos nuevos.

