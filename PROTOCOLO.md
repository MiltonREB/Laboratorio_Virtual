# Protocolo del laboratorio de hipótesis (v1.1.0)

Documento normativo. Define qué se exige, cómo se decide y qué no se permite.
El código que lo implementa está en `lab/protocolo.py`, `lab/veredicto.py` y
`lab/viabilidad.py`; si alguna vez discrepan, este documento y el código deben
corregirse juntos.

**Cambios respecto a v1.0.0:** ver
[CHANGELOG_METODOLOGICO.md](CHANGELOG_METODOLOGICO.md).

## 1. Alcance

El protocolo sirve para contrastar **una hipótesis cuantitativa** contra **un
baseline convencional** sobre **un conjunto de datos congelado y particionado**,
y para saber si esa corroboración merece ese nombre o es sólo un resultado
preliminar. No sirve para descubrir hipótesis, ni para elegir la mejor entre
muchas (eso exige corrección por comparaciones múltiples).

## 2. Principios

1. **Nada se decide después de ver los datos.** Métrica, umbral de mejora,
   factor de diferenciación, presupuesto de incertidumbre y semilla se congelan
   por escrito antes de evaluar, y con una separación temporal mínima.
2. **La muestra reservada no se toca.** El ajuste de cualquier parámetro libre
   ocurre sólo con la partición de calibración.
3. **Sin baseline no hay resultado.** Una hipótesis sólo aporta algo si mejora a
   un modelo convencional explícito.
4. **Una mejora sin intervalo no es una mejora.** Se exige que el intervalo de
   confianza del 95 % de la mejora excluya el cero por arriba.
5. **La ventaja tiene que sobrevivir al baseline elegido y al diseño.** Si sólo
   aparece frente a un baseline concreto, o sólo con una partición concreta, no
   se corrobora: se declara preliminar o sensible.
6. **Se distingue «no concluyente» de «falso».** Cuatro estados de prueba; ningún
   veredicto se llama «refutada».
7. **Toda prueba imposible de verificar devuelve `PENDIENTE`.** Nunca se rellena
   un hueco con una aprobación tácita.
8. **El informe publica lo que el experimento no demuestra.**

## 3. Vocabulario

| Término | Definición operativa |
|---|---|
| **Modelo** | Función pura `variables → observables`, con parámetros declarados |
| **Baseline** | Modelo convencional de referencia; no puede ser la propia hipótesis |
| **Baseline alternativo** | Segundo (o tercer) modelo de referencia contra el que también hay que ganar (O01) |
| **Hipótesis** | Modelo + enunciado falsable + dominio + predicción diferenciadora + umbrales |
| **Observable objetivo** | La única magnitud que se compara contra el baseline |
| **Calibración / reservado** | Filas para ajustar / filas que sostienen el veredicto |
| **Umbral de mejora** | Mejora relativa mínima exigida frente al baseline |
| **Factor de diferenciación** | Cuántas veces el error del baseline debe superar \|ΔO\| para considerarlo distinguible |
| **ΔO** | Diferencia entre la predicción de la hipótesis y la del baseline |
| **Holdout externo** | Dataset independiente con el que se comprueba que la mejora no es del diseño (O04) |

## 4. Las doce pruebas

Cuatro estados posibles: `APROBADO`, `PENDIENTE`, `SENSIBLE`, `FALLIDO`.

### T01 — Formalización del contrato

Comprueba que existan `id`, `nombre`, `version`, `enunciado`,
`prediccion_diferenciadora`, `observable_objetivo` con unidad, `observables`,
`requiere`, `dominio` con rango no vacío, `baseline` distinto de la hipótesis,
`dataset_id`, `metrica` admitida, `umbral_mejora` en (0,1) y
`factor_diferenciacion` > 0, y unidad en todos los parámetros.

`umbral_sensibilidad` es **opcional**: si se declara, actúa como suelo absoluto
(por ejemplo, la resolución del instrumento).

### T02 — Falsabilidad

La predicción sobre el reservado debe ser finita, no vacía y no constante. Si no
lo es, `FALLIDO` con la marca de ausencia: no hay nada que contrastar.

### T03 — Predicción diferenciadora (reformulada en v1.1.0)

**Criterio.** Sea `ε_base` el error del baseline sobre la muestra reservada. Se
exige:

```
max|ΔO| ≥ max( factor_diferenciacion × ε_base , umbral_sensibilidad )
```

`factor_diferenciacion` es adimensional y lo declara la hipótesis (por defecto
1.0). Ya no se compara contra una tolerancia absoluta: una tolerancia fija en
segundos puede cumplirse con una diferencia que en la práctica es ruido, o
rechazar una diferencia grande medida en otra unidad.

- `max|ΔO| = 0` → `PENDIENTE` con marca de ausencia.
- Por debajo de lo exigido → `PENDIENTE` con marca de ausencia.
- En otro caso → `APROBADO`, y el informe dice cuántas veces `ε_base` supone.

Ejemplo real del repositorio: en la hipótesis del polinomio, `max|ΔO| = 6.2 ms`
frente a `ε_base = 0.82 ms`; son 7.5 veces la escala, así que **pasa** T03 con
el criterio nuevo. Su rechazo viene de T07 y T08, que es donde corresponde. La
reformulación no está pensada para que esa hipótesis falle, sino para que el
criterio signifique algo.

### T04 — Preregistro

Produce **un solo estado semántico**, `estado_preregistro`:

| Estado | Significado | Estado de la prueba |
|---|---|---|
| `VALIDO` | Sello que coincide, con antigüedad suficiente y publicado si se exige | `APROBADO` |
| `AUSENTE` | No hay sello | `PENDIENTE` |
| `TARDIO` | Sello creado durante la evaluación | `PENDIENTE` |
| `RECIENTE` | Sello más joven que la separación mínima | `PENDIENTE` |
| `NO_PUBLICADO` | Se exigió publicación y el sello no está en un commit | `PENDIENTE` |
| `ALTERADO` | La firma actual no coincide con la sellada | `FALLIDO` |

Separación temporal: `lab ejecutar` exige 60 s por defecto entre el sello y la
corrida (`--separacion-minima`). Con `--exigir-publicacion`, además, el sello
debe estar en un commit de git, que aporta una fecha externa verificable.

### T05 — Calibración

- Particiones solapadas → `FALLIDO`.
- Con parámetros libres y sin ajuste efectivo → `FALLIDO`.
- Sin parámetros libres → `APROBADO` **vacuo**, marcado en la evidencia. Una
  exigencia sobre el conjunto vacío se cumple; el informe lo dice.
- Ajuste sólo con calibración → `APROBADO`.

### T06 — Validación fuera de muestra

El error sobre el reservado debe ser finito y no exceder `5 × escala`, donde la
escala es la incertidumbre declarada o el error del baseline. Es un control de
generalización, no de mérito: eso lo decide T07.

### T07 — Comparación con el baseline

Prueba central. Se calcula la mejora relativa `1 − ε_hip/ε_base` sobre el
reservado y su intervalo percentil del 95 % por bootstrap de filas.

| Condición | Estado |
|---|---|
| mejora ≥ umbral **y** IC inferior > 0 | `APROBADO` |
| cualquier otra | `PENDIENTE` |

**Nunca `FALLIDO`.** Que el baseline sea significativamente mejor no refuta la
hipótesis: dice que este diseño no la sostiene. El hecho se registra en
`peor_que_baseline` y el veredicto lo convierte en `NO_CORROBORADA`.

Cada resultado de T07 incluye el **ratio de errores** `ε_hip/ε_base`, porque la
mejora normalizada sola se malinterpreta: «+0.99» no significa «casi perfecto»,
significa «el baseline es 100 veces peor».

### T08 — Estabilidad de la conclusión

Se repiten particiones alternativas y se recalcula la mejora.

- Todas positivas → `APROBADO`.
- Ninguna positiva → `PENDIENTE` (no hay evidencia de mejora estable).
- Cambia el signo → `SENSIBLE`.

**Nunca `FALLIDO`.**

### T09 — Reproducibilidad numérica

Predicción y bootstrap dos veces con la misma semilla; se comparan los bytes.
Cualquier diferencia → `FALLIDO`.

### T10 — Presupuesto de incertidumbre

Sin presupuesto → `PENDIENTE`. Error > 3 × declarado → `FALLIDO` (subestimado).
Error < declarado / 3 → `PENDIENTE` (inflado). En otro caso → `APROBADO`.

### T11 — Control nulo

Se generan datos con el baseline como verdad y el mismo ruido. Si la hipótesis
alcanza su umbral ahí, su ventaja es un artefacto → `FALLIDO`.

### T12 — Dominio de validez

Todas las filas evaluadas deben caer dentro de `dominio.rango`. Cualquier
variable fuera → `FALLIDO`. No se recorta en silencio.

## 4.1 Verificaciones adicionales

Cinco comprobaciones que se registran con su motivo. **Dos son vinculantes**
(O01 y O04): condicionan el veredicto máximo. Las otras tres son informativas.

| Código | Verificación | Vinculante | Se ejecuta cuando |
|---|---|---|---|
| O01 | Contraste con baselines alternativos | **Sí** | La hipótesis declara `baselines_alternativos` |
| O02 | Validación por bloques del dominio | No | Hay ≥ 3 bloques de ≥ 10 filas reservadas |
| O03 | Sensibilidad al número de remuestreos | No | Se pide con `--sensibilidad-bootstrap` |
| O04 | Holdout externo | **Sí** | Declara `dataset_validacion` y existe en el manifiesto |
| O05 | Corrección por comparaciones múltiples | No | Más de una hipótesis usa el dataset |

Estados de una verificación: `EJECUTADA`, `PENDIENTE`, `NO_REQUERIDA`.
`NO_REQUERIDA` nunca equivale a superada: aparece con su motivo.

**Por qué O01 y O04 son vinculantes.** La corrida de `pendulo_amplitud` lo
mostró: la hipótesis mejoraba +0.99 frente al baseline principal, pero sólo
−0.0004 frente a un modelo correcto de cuarto orden. Ese hallazgo, que rebaja el
veredicto, estaba en una verificación informativa. Ahora una hipótesis que no
supera a todos sus baselines alternativos —o que no tiene holdout externo— no
puede pasar de `PRELIMINAR`.

## 5. Estados

| Estado | Significado |
|---|---|
| `APROBADO` | El criterio se cumplió con evidencia disponible (incluye el caso vacuo, marcado) |
| `PENDIENTE` | Evidencia insuficiente o criterio no alcanzado |
| `SENSIBLE` | La conclusión depende de la partición de los datos |
| `FALLIDO` | Se incumplió un requisito estructural (contrato, calibración, dominio, reproducibilidad) |

Ya no existen `NO_APLICABLE`, `NO_PRESENTADA` ni `SENSIBLE_AL_DISENO` como
estados. El primer caso es un `APROBADO` vacuo; el segundo es un `PENDIENTE` con
la marca `es_ausencia`; el tercero se llama `SENSIBLE`.

## 6. Agregación del veredicto

Reglas en orden; la primera que se cumple decide:

1. Alguna prueba con `es_ausencia` → **`NO_PRESENTADA`**
2. `T12 = FALLIDO` → **`FUERA_DE_DOMINIO`**
3. `T06 = FALLIDO` → **`NO_CORROBORADA`**
4. `T07 ≠ APROBADO` → **`NO_CORROBORADA`**
5. `T08 = SENSIBLE` → **`SENSIBLE`**
6. `T04 = FALLIDO` → **`PENDIENTE`**
7. Alguna bloqueante fuera de `APROBADO` → **`PENDIENTE`**
8. O01 u O04 no ejecutadas → **`PRELIMINAR`**
9. O01 ejecutada y `gana_a_todos = false` → **`PRELIMINAR`**
10. O04 ejecutada y `supera_baseline = false` → **`NO_CORROBORADA`**
11. En otro caso → **`CORROBORADA_PROVISIONAL`**

Las doce pruebas son bloqueantes. El orden no es arbitrario: primero se descarta
lo que no es contrastable, luego lo que está fuera de dominio, después lo que
falla, después lo que depende del diseño, y sólo al final se concede una
corroboración **provisional**, y sólo si las verificaciones vinculantes la
respaldan.

## 7. Viabilidad previa a la corrida

Antes de ejecutar la batería se calculan avisos que **no cambian el veredicto** y
ahorran corridas inútiles:

| Código | Aviso |
|---|---|
| V01 | Demasiados parámetros libres para las filas de calibración (< 10 por parámetro) |
| V02 | Muestra reservada por debajo de 30 filas |
| V03 | El umbral de mejora exige menos que el ruido declarado |
| V04 | El dominio no cubre los datos o declara variables ausentes |
| V05 | No hay presupuesto de incertidumbre |
| V06 | El preregistro no es válido (ausente, reciente, tardío, alterado, sin publicar) |

## 8. Prohibiciones

1. Elegir la tolerancia después de ver el resultado.
2. Reutilizar filas reservadas para ajustar o para elegir el modelo.
3. Extrapolar fuera del dominio declarado y presentarlo como resultado.
4. Declarar `PENDIENTE` como aprobación, o promediar estados.
5. Presentar una mejora normalizada sin el ratio de errores.
6. Sellar y evaluar en el mismo instante y llamarlo preregistro.
7. Publicar el veredicto sin el informe completo.

## 9. Trazabilidad

Cada corrida escribe en `resultados/<hipotesis>_<UTC>/`:

- `resumen.json` — todo el cálculo: parámetros ajustados, intervalo, ratio de
  errores, ensayos de estabilidad, control nulo, verificaciones, avisos de
  viabilidad, estado del preregistro, versión de Python y NumPy, plataforma y
  SHA-256 del archivo de la hipótesis. Declara `schema_version` (1.2).
- `INFORME.md` — informe con matriz de pruebas, verificaciones, viabilidad y
  límites.
- `matriz.csv`, `predicciones.csv` — datos crudos de la decisión.

Los sellos viven en `resultados/preregistro/<hipotesis>/` y no se sobrescriben.

## 10. Extender el protocolo

1. Escribir la función en `lab/protocolo.py` con firma
   `(ContextoEvaluacion) -> ResultadoPrueba`.
2. Añadir su código a `ORDEN` y su título a `TITULOS`.
3. Añadirla a `BLOQUEANTES` si debe impedir la corroboración.
4. Añadir su regla en `lab/veredicto.py`, con motivo explícito.
5. Añadir pruebas unitarias de sus estados posibles, incluido el caso vacuo.

Una prueba que no puede fallar no es una prueba.
