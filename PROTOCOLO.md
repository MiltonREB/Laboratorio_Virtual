# Protocolo del laboratorio de hipótesis (v1.0)

Documento normativo. Define qué se exige, cómo se decide y qué no se permite.
El código que lo implementa está en `lab/protocolo.py` y `lab/veredicto.py`; si
alguna vez discrepan, este documento y el código deben corregirse juntos.

## 1. Alcance

El protocolo sirve para contrastar **una hipótesis cuantitativa** contra **un
baseline convencional** sobre **un conjunto de datos congelado y particionado**.
No sirve para descubrir hipótesis, ni para elegir la que mejor se ajusta entre
muchas (eso exige corrección por comparaciones múltiples, que aquí no se aplica).

## 2. Principios

1. **Nada se decide después de ver los datos.** Métrica, umbral de mejora,
   umbral de sensibilidad, presupuesto de incertidumbre y semilla se congelan por
   escrito antes de evaluar. Cambiarlos invalida el preregistro (T04).
2. **La muestra reservada no se toca.** El ajuste de cualquier parámetro libre
   ocurre sólo con la partición de calibración. Las particiones se declaran en el
   manifiesto; el laboratorio no las sortea.
3. **Sin baseline no hay resultado.** Una hipótesis sólo aporta algo si mejora a
   un modelo convencional explícito. Ganar a la nada no cuenta.
4. **Una mejora sin intervalo no es una mejora.** Se exige que el intervalo de
   confianza del 95 % de la mejora excluya el cero por arriba.
5. **Se distingue «no concluyente» de «falso».** `PENDIENTE` no es
   `NO_CORROBORADA`; un fracaso sólo se declara con evidencia.
6. **Toda prueba imposible de verificar devuelve `PENDIENTE`.** Nunca se rellena
   un hueco con una aprobación tácita.
7. **El informe publica lo que el experimento no demuestra.** La sección 11 del
   informe es obligatoria.

## 3. Vocabulario

| Término | Definición operativa |
|---|---|
| **Modelo** | Función pura `variables → observables`, con parámetros declarados |
| **Baseline** | Modelo convencional de referencia; no puede ser la propia hipótesis |
| **Hipótesis** | Modelo + enunciado falsable + dominio + predicción diferenciadora + umbrales |
| **Observable objetivo** | La única magnitud que se compara contra el baseline |
| **Calibración** | Filas usadas para ajustar parámetros libres |
| **Reservado** | Filas que no participan en ningún ajuste y sostienen el veredicto |
| **Umbral de mejora** | Mejora relativa mínima exigida frente al baseline (p. ej. 0.10 = 10 %) |
| **Umbral de sensibilidad** | \|ΔO\| mínimo apreciable; por debajo, la predicción no es distinguible |
| **Presupuesto de incertidumbre** | Error típico declarado para el observable, en su unidad |
| **ΔO** | Diferencia entre la predicción de la hipótesis y la del baseline |

## 4. Las doce pruebas

Cada prueba devuelve uno de seis estados: `APROBADO`, `FALLIDO`, `PENDIENTE`,
`NO_APLICABLE`, `NO_PRESENTADA`, `SENSIBLE_AL_DISENO`.

### T01 — Formalización del contrato

**Comprueba** que existan: `id`, `nombre`, `version`, `enunciado`,
`prediccion_diferenciadora`, `observable_objetivo` con unidad, `observables`,
`requiere`, `dominio` con rango no vacío, `baseline` distinto de la hipótesis,
`dataset_id`, `metrica` admitida, `umbral_mejora` en (0,1), `umbral_sensibilidad`
> 0, y unidad en todos los parámetros.

**Falla** si falta cualquiera. **Corrección**: completar el metadato. No hay
forma de aprobar T01 por defecto.

### T02 — Falsabilidad

**Comprueba** que la predicción sobre la muestra reservada sea finita, no vacía y
no constante. Una predicción constante no distingue ninguna fila y no puede
falsarse con estos datos.

**Falla** si hay `NaN`/`inf`, si el arreglo está vacío o si su rango es cero.

### T03 — Predicción diferenciadora

**Comprueba** que ΔO exista y supere el umbral de sensibilidad declarado.

- ΔO ≡ 0 → `NO_PRESENTADA` («predice lo mismo que el baseline»).
- máx\|ΔO\| < umbral de sensibilidad → `NO_PRESENTADA` («no observable con este
  diseño»).
- En otro caso → `APROBADO`.

`NO_PRESENTADA` no es un fallo moral: es la información de que la idea todavía
no es contrastable con los medios declarados.

### T04 — Preregistro

**Comprueba** la firma SHA-256 de la instantánea `firma_de_parametros()`
(identidad, versión, métrica, umbrales, semilla, observable, dataset y cada
parámetro con su unidad y su estado) contra el último sello.

| Situación | Estado |
|---|---|
| No hay sello | `PENDIENTE` |
| Hay sello y coincide, creado por `lab preregistrar` | `APROBADO` |
| Hay sello y coincide, creado durante la evaluación | `PENDIENTE` (tardío) |
| Hay sello y no coincide | `FALLIDO` |

`FALLIDO` aquí no significa que los datos contradigan la hipótesis: significa que
el resultado **no es interpretable** porque el umbral se movió después.

### T05 — Calibración

- Sin parámetros libres → `NO_APLICABLE` (no hay ajuste que aislar).
- Con parámetros libres pero sin ajuste efectivo → `FALLIDO`.
- Particiones que se solapan → `FALLIDO` (contaminación).
- Ajuste hecho sólo con calibración → `APROBADO`.

### T06 — Validación fuera de muestra

**Comprueba** que el error sobre el reservado sea finito y no exceda
`5 × escala`, donde la escala es la incertidumbre declarada o, si no consta, el
error del baseline en reservado. Es un control de generalización, no de mérito:
un modelo puede generalizar y aun así no superar al baseline (eso lo decide T07).

### T07 — Comparación con el baseline

Es la prueba central. Se calcula la mejora relativa `1 − ε_hip/ε_base` sobre el
reservado y su intervalo percentil del 95 % por bootstrap de filas.

| Condición | Estado |
|---|---|
| mejora ≥ umbral **y** IC inferior > 0 | `APROBADO` |
| IC superior < 0 | `FALLIDO` |
| resto | `PENDIENTE` |

El umbral lo fija la hipótesis, no el laboratorio. Elegirlo después de ver el
resultado es exactamente lo que T04 detecta.

### T08 — Estabilidad de la conclusión

Se repiten `particiones` particiones alternativas (40 % reservado, semillas
derivadas de `semilla`) y se recalcula la mejora en cada una.

- Todas positivas → `APROBADO`.
- Ninguna positiva → `FALLIDO`.
- Cambia el signo → `SENSIBLE_AL_DISENO`.

Esta prueba es la respuesta directa al problema de «cambia el ganador según cómo
partas los datos»: si eso ocurre, el veredicto lo dice en lugar de ocultarlo.

### T09 — Reproducibilidad numérica

Se ejecuta la predicción dos veces y el bootstrap dos veces con la misma semilla.
Se comparan SHA-256 de los bytes (`float64` little-endian).

Cualquier diferencia → `FALLIDO`. Si hay aleatoriedad no sembrada en el modelo o
en el ajuste, aparece aquí.

### T10 — Presupuesto de incertidumbre

- Sin presupuesto declarado → `PENDIENTE`.
- error > 3 × declarado → `FALLIDO` (presupuesto subestimado).
- error < declarado / 3 → `PENDIENTE` (presupuesto inflado; no informa).
- En otro caso → `APROBADO`.

### T11 — Control nulo

Se generan datos sintéticos con el **baseline como verdad** y el mismo ruido, se
repite el procedimiento completo (ajuste en calibración, comparación en
reservado) y se mide la mejora.

- La hipótesis alcanza su umbral con IC inferior > 0 → `FALLIDO`: su ventaja es
  un artefacto de flexibilidad o de fuga de información.
- En otro caso → `APROBADO`.

### T12 — Dominio de validez

Todas las filas evaluadas (calibración y reservado) deben caer dentro de
`dominio.rango`. Cualquier variable fuera → `FALLIDO`.

No se recorta ni se avisa: se rechaza, porque extrapolar en silencio es una de
las formas más comunes de fabricar un resultado positivo.

### 4.1 Verificaciones opcionales (O01–O05)

Además de las doce pruebas, el laboratorio puede ejecutar cinco verificaciones
que **amplían el diagnóstico y no cambian el veredicto**. Existen porque hay
preguntas razonables que no siempre se pueden responder con los datos
disponibles; cuando no se pueden, el motivo queda escrito.

| Código | Verificación | Se ejecuta cuando |
|---|---|---|
| O01 | Contraste con un baseline alternativo | La hipótesis declara `baselines_alternativos` |
| O02 | Validación por bloques del dominio | Hay ≥ 3 bloques de ≥ 10 filas reservadas |
| O03 | Sensibilidad al número de remuestreos | Se pide con `--sensibilidad-bootstrap` |
| O04 | Holdout externo | La hipótesis declara `dataset_validacion` y existe en el manifiesto |
| O05 | Corrección por comparaciones múltiples | Más de una hipótesis usa el mismo dataset |

Estados posibles de una verificación:

| Estado | Significado |
|---|---|
| `EJECUTADA` | Se cumplió la precondición y hay resultado |
| `NO_REQUERIDA` | La precondición no se cumple; se registra el motivo concreto |
| `PENDIENTE` | Se declaró, pero no se pudo ejecutar (p. ej. el dataset no existe) |

**Regla:** `NO_REQUERIDA` nunca equivale a superada. Aparece con su motivo en el
informe, en la página de la corrida y en el catálogo del panel, para que no se
pueda confundir con una prueba pasada.

Cuando O05 se ejecuta, no se limita a avisar: recalcula el intervalo de la
mejora con el nivel corregido por familia (Holm, α/n para la comparación más
exigente) y declara si la conclusión **sobrevive** a la corrección. Sigue sin ser
vinculante, porque cambiar el veredicto a posteriori sería justo lo que el
protocolo prohíbe; lo que hace es poner el número delante.

O01 informa por separado de cada baseline alternativo y dice explícitamente si
la hipótesis **no** supera alguno. Un caso frecuente: ganar al baseline principal
porque ese baseline es incompleto, y empatar con un modelo de referencia mejor.
O04 compara sobre un dataset generado aparte, sin reajustar parámetros.

Un caso típico y deliberado: la hipótesis de control negativo tiene 29 filas
reservadas, así que O02 no se ejecuta porque tres bloques de diez no caben; la
hipótesis de control positivo, con 96, sí la ejecuta y confirma que la mejora se
mantiene en los tres tercios del dominio.

## 5. Estados

| Estado | Significado |
|---|---|
| `APROBADO` | El criterio se cumplió con evidencia disponible |
| `FALLIDO` | El criterio no se cumplió |
| `PENDIENTE` | Evidencia insuficiente o no verificable |
| `NO_APLICABLE` | La prueba no corresponde a esta hipótesis (p. ej. T05 sin parámetros libres) |
| `NO_PRESENTADA` | No hay predicción contrastable (T03) |
| `SENSIBLE_AL_DISENO` | La conclusión depende de la partición (T08) |

`NO_APLICABLE` no es un aprobado disfrazado: se informa como tal y no cuenta como
evidencia a favor.

## 6. Agregación del veredicto

Las reglas se aplican **en este orden** y la primera que se cumple decide:

1. `T02 = FALLIDO` o `T03 = NO_PRESENTADA` → **`NO_PRESENTADA`**
2. `T12 = FALLIDO` → **`FUERA_DE_DOMINIO`**
3. `T06 = FALLIDO` o `T08 = FALLIDO` → **`NO_CORROBORADA`**
4. `T07 = FALLIDO` → **`REFUTADA`**
5. `T07 = PENDIENTE` → **`NO_CORROBORADA`**
6. `T08 = SENSIBLE_AL_DISENO` → **`SENSIBLE_AL_DISENO`**
7. `T04 = FALLIDO` → **`PENDIENTE`** (preregistro alterado)
8. Alguna prueba bloqueante fuera de `APROBADO`/`NO_APLICABLE` → **`PENDIENTE`**
9. Queda alguna prueba en `PENDIENTE` → **`PENDIENTE`**
10. En otro caso → **`CORROBORADA_PROVISIONAL`**

Pruebas bloqueantes: T01, T02, T03, T04, T06, T07, T09, T10, T11, T12.
T05 y T08 no son bloqueantes por sí mismas pero condicionan el resultado (pasos 3
y 6).

El orden no es arbitrario: primero se descarta lo que no es contrastable, luego
lo que está fuera de dominio, después lo que falla, y sólo al final se concede
una corroboración **provisional**.

## 7. Prohibiciones

1. Elegir la tolerancia después de ver el resultado.
2. Reutilizar filas reservadas para ajustar o para elegir el modelo.
3. Extrapolar fuera del dominio declarado y presentarlo como resultado.
4. Declarar `PENDIENTE` como aprobación, o promediar estados.
5. Publicar el veredicto sin el informe completo.
6. Usar la misma muestra para elegir entre varias hipótesis y luego evaluar la
   elegida como si fuera única (fuera del alcance de v1.0).

## 8. Trazabilidad

Cada corrida escribe en `resultados/<hipotesis>_<UTC>/`:

- `resumen.json` — todo el cálculo, incluidos parámetros ajustados, intervalo,
  ensayos de estabilidad, control nulo, verificación de preregistro, versión de
  Python y NumPy, plataforma y SHA-256 del archivo de la hipótesis.
- `INFORME.md` — informe con matriz de pruebas y límites.
- `matriz.csv`, `predicciones.csv` — datos crudos de la decisión.

Los sellos de preregistro viven en `resultados/preregistro/<hipotesis>/` y no se
sobrescriben: cada sello es un archivo nuevo con su marca temporal.

El panel se regenera con `lab panel` y deriva **todo** de esos archivos: la matriz
de estados, una tarjeta con gráfico por prueba, las verificaciones opcionales con
su motivo y el catálogo global. No hay datos embebidos ni cálculo en el navegador,
así que el panel no puede afirmar nada que no esté en `resumen.json`.

Cada `resumen.json` declara `schema_version`. Un archivo con un esquema que este
código no reconoce no se descarta: se carga marcado como incompatible y el
informe consolidado avisa antes de compararlo con los demás.

`lab consolidado` produce un informe único con el resumen por hipótesis, la
matriz de pruebas, lo que no se sostiene, las verificaciones ejecutadas y los
avisos de familia. Incluye un aviso que ningún módulo individual puede dar:
**cuántas corridas registra cada hipótesis**. Reevaluar hasta que salga positiva
es la forma más común de fabricar un resultado, y ahí queda a la vista.

## 9. Extender el protocolo

Para añadir una prueba:

1. Escribir la función en `lab/protocolo.py` con firma
   `(ContextoEvaluacion) -> ResultadoPrueba`.
2. Añadir su código a `ORDEN` y su título a `TITULOS`.
3. Decidir si es bloqueante y, si lo es, añadirla a `BLOQUEANTES`.
4. Añadir la regla de agregación correspondiente en `lab/veredicto.py`, con su
   motivo explícito.
5. Añadir pruebas unitarias de sus tres o cuatro estados posibles.

Una prueba que no puede fallar no es una prueba.
