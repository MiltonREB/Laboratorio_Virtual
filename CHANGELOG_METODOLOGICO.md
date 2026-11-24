# Changelog metodológico

Registro de los cambios del **protocolo**, no del software. Cada entrada dice
qué se cambió, por qué y qué se pierde con el cambio. Los cambios de código sin
consecuencia metodológica no aparecen aquí.

Versión anterior: v1.0.0. Versión actual: **v1.1.0**.

---

## 0.1 — Un solo vocabulario de estados

**Antes.** Seis estados (`APROBADO`, `FALLIDO`, `PENDIENTE`, `NO_APLICABLE`,
`NO_PRESENTADA`, `SENSIBLE_AL_DISENO`) y siete veredictos, con nombres que se
solapaban: el panel decía «Sensible al diseño» y el veredicto
`SENSIBLE_AL_DISENO`; `NO_APLICABLE` se leía a veces como aprobado.

**Ahora.** Cuatro estados: `APROBADO`, `PENDIENTE`, `SENSIBLE`, `FALLIDO`.

- `NO_APLICABLE` desaparece: el caso vacuo (T05 sin parámetros libres) es
  `APROBADO` y se marca `vacuo: true` en la evidencia.
- `NO_PRESENTADA` desaparece como estado: es `PENDIENTE` con `es_ausencia: true`.
  El veredicto sigue distinguiendo «no se presentó» de «falta evidencia».
- `SENSIBLE_AL_DISENO` pasa a llamarse `SENSIBLE`.
- T07 y T08 **nunca** devuelven `FALLIDO`. Se retira el veredicto `REFUTADA`.

**Por qué.** Un experimento no refuta una idea; deja de sostenerla. Llamar
«fallida» a una prueba porque el baseline es mejor mezcla dos cosas: el requisito
estructural incumplido y la ausencia de evidencia. `FALLIDO` queda reservado para
lo primero.

**Qué se pierde.** Menos granularidad en los estados. A cambio, el informe
muestra el detalle en `evidencia` y en `es_ausencia`, y nadie puede confundir un
estado con otro.

## 0.2 — T03 deja de usar una tolerancia absoluta

**Antes.** Se exigía `max|ΔO| > umbral_sensibilidad`, un número absoluto en las
unidades del observable (por ejemplo `10⁻⁴ s`).

**Ahora.** Se exige `max|ΔO| ≥ max(factor_diferenciacion × ε_baseline,
umbral_sensibilidad)`, donde `ε_baseline` es el error del baseline sobre la
muestra reservada y `factor_diferenciacion` es adimensional (por defecto 1.0).

**Por qué.** Una tolerancia absoluta no significa nada por sí sola: depende de la
unidad y de la escala del problema. El error del baseline sí es una escala
interpretable — es lo que el modelo alternativo se equivoca.

**Qué se pierde.** El criterio depende ahora de un cálculo previo (el error del
baseline), así que T03 ya no puede evaluarse sin ejecutar los modelos. A cambio,
«diferenciadora» pasa a querer decir algo.

**Comprobación honesta.** Con el criterio nuevo, la hipótesis del polinomio
**sigue pasando** T03: su `max|ΔO| = 6.2 ms` frente a `ε_baseline = 0.82 ms`
son 7.5 veces la escala. Su rechazo viene de T07 (no mejora) y T08 (signo
inestable). La reformulación no se hizo para que esa hipótesis fallara, sino para
que el umbral fuese interpretable.

## 0.3 — O01 y O04 pasan a ser vinculantes

**Antes.** Las cinco verificaciones eran informativas. Una hipótesis podía
corroborarse sin haber sido comparada con un baseline alternativo ni con datos
externos.

**Ahora.** Sin O01 ejecutada, o con `gana_a_todos = false`, el veredicto máximo es
`PRELIMINAR`. Sin O04 ejecutada, también; si O04 se ejecuta y no supera al
baseline en el holdout, el veredicto es `NO_CORROBORADA`.

**Por qué.** La corrida de `pendulo_amplitud` lo demostró: +0.99 de mejora frente
al baseline lineal, **−0.0004** frente a un modelo de cuarto orden correcto. La
ventaja venía de que el baseline principal estaba incompleto, no de que la
hipótesis aportara algo. Ese hallazgo estaba en una verificación opcional y no
afectaba al veredicto. Ahora sí.

**Qué se pierde.** Más fricción: hay que declarar baselines alternativos y un
holdout. Es deliberado — sin ellos, «corroborada» significaba menos de lo que
parecía.

**Nuevo veredicto.** `PRELIMINAR`: las doce pruebas se cumplen pero falta el
contraste que exige el protocolo. Es un estado honesto y frecuente.

## 0.4 — Separación temporal real en el preregistro

**Antes.** `lab preregistrar` sellaba y el evaluador aceptaba el sello aunque se
hubiera creado un segundo antes. El hash probaba integridad, no anterioridad.

**Ahora.** El sello debe tener una antigüedad mínima (60 s por defecto,
`--separacion-minima`). Con `--exigir-publicacion`, además, debe estar en un
commit de git, que aporta fecha externa verificable. Un sello demasiado joven
produce el estado `RECIENTE` y T04 queda en `PENDIENTE`.

**Por qué.** Publicar el hash en un paso separado, antes de que existan los datos
de la corrida, es la única forma de que el preregistro signifique algo. El hash
solo no basta.

**Qué se pierde.** Comodidad: ya no se puede sellar y ejecutar en el mismo
comando. Y no se resuelve del todo: alguien con acceso a los datos puede mirarlos
antes de sellar. Eso requiere testigos externos (un registro público, un tercero),
que el laboratorio no puede aportar por sí mismo.

## 0.5 — El ratio de errores acompaña siempre a la mejora

**Antes.** El informe decía «mejora +0.9908».

**Ahora.** Dice «mejora +0.9908 (ε_hip/ε_base = 1/109)» en consola, informe,
panel y consolidado.

**Por qué.** «+0.99» se lee como «casi perfecto» cuando en realidad dice «el
baseline es cien veces peor». Son dos afirmaciones distintas y la primera no está
respaldada por el dato.

## 0.6 — Advertencias de viabilidad antes de la corrida

**Antes.** Nada avisaba de que un diseño no podía sostener ninguna conclusión; se
descubría al ver los doce resultados.

**Ahora.** Antes de la batería se calculan seis comprobaciones (V01–V06):
parámetros libres frente a filas de calibración, tamaño del reservado, umbral
dentro del ruido, cobertura del dominio, presupuesto de incertidumbre y estado
del preregistro. **No cambian el veredicto**; se registran y se muestran.

**Por qué.** Ahorran corridas y, sobre todo, ponen delante la razón por la que un
resultado no va a ser interpretable, en lugar de dejar que el lector la deduzca.

**Qué se pierde.** Tres avisos más que leer. Se mitiga marcando severidad.

---

## Extensión para datos reales (misma versión de protocolo)

Preparación de la Fase 1. No cambia el número de pruebas ni el vocabulario, pero
sí dos definiciones:

**T10 — presupuesto combinado.** El presupuesto de incertidumbre pasa a ser
`sqrt(declarada² + experimental²)`, donde la experimental es el RMS de la
columna ``u_T_s`` del dataset. Si la hipótesis no declara nada pero el dataset
trae incertidumbre por fila, T10 **sí** puede evaluarse; antes quedaba en
`PENDIENTE`. Motivo: «el ajuste deja 0,8 ms» y «el instrumento no resuelve mejor
de 1,2 ms» son afirmaciones distintas y el presupuesto debe contener ambas.

**Ajuste del baseline.** El evaluador ajusta ahora también los parámetros libres
del baseline con la misma calibración. Antes el baseline se usaba con sus valores
nominales. Con datos reales eso era insostenible: si la hipótesis estima g y el
baseline la tiene fijada en 9.80665, la ventaja es artificial. La comparación
ahora es entre dos modelos ajustados con los mismos datos.

**Confondo conocido y documentado.** El estimador de g del baseline
(`ajustar_g`) ignora la corrección de amplitud y usa el cuartil inferior de θ0
para reducir el sesgo. Queda un sesgo residual a la baja del orden del 0.3 %, que
infla el error del baseline y favorece levemente a la hipótesis. Está medido en
las pruebas (`test_el_baseline_ajusta_g` comprueba dirección y magnitud) y no se
oculta. Corregirlo exige un ajuste conjunto (g, c2) o un tramo de amplitudes
pequeñas dedicado, que es trabajo de la Fase 1 con datos reales.

**Lo que esto NO es.** El CSV de `pruebas/fixtures/` es sintético. Tiene las
columnas del esquema real para probar la tubería, no para producir evidencia. La
Fase 1 sigue abierta: no hay ninguna medición.

---

## Registro de publicación (cierre de 0.4b)

El preregistro deja de ser un commit local con fecha ajustable:

| Dato | Valor |
|---|---|
| Repositorio | https://github.com/MiltonREB/Laboratorio_Virtual |
| Commit que publica los sellos | `14bf993e5b0c4520d5e20ea3a7716c28bde82d04` |
| Sello de `pendulo_amplitud` | [ver en ese commit](https://github.com/MiltonREB/Laboratorio_Virtual/blob/14bf993e5b0c4520d5e20ea3a7716c28bde82d04/resultados/preregistro/pendulo_amplitud/20261124T192732031946Z.json) |
| Sello de `pendulo_polinomio_alto` | [ver en ese commit](https://github.com/MiltonREB/Laboratorio_Virtual/blob/14bf993e5b0c4520d5e20ea3a7716c28bde82d04/resultados/preregistro/pendulo_polinomio_alto/20261124T192732879391Z.json) |
| `main` publicado al registrar esto | `5dba31a9442402ea161afa5e5433a19a362bc10b` |
| Comprobación | `git merge-base --is-ancestor 14bf993 HEAD` → sí |

El commit del preregistro es **anterior** a cualquier dato de la Fase 1: cuando
se publicó, esa fase no había empezado.

**Verificación pública (2026-11-24).** El repositorio es público. Comprobado
**sin credenciales**, que es como lo vería un revisor:

| Comprobación | Resultado |
|---|---|
| `api.github.com/repos/MiltonREB/Laboratorio_Virtual` | HTTP 200 · `"private": false` |
| Sello de `pendulo_amplitud` en `14bf993` | HTTP 200 (raw, anónimo) |
| `firma_sha256` publicada | `0d700ebfe0394344261133fafb1d7ce00435e293eb60df2794f775e65d3fefa2` |
| Hash que verificó T04 en la corrida | `0d700ebfe039…` — **coincide** |

Con eso **0.4b queda cerrado**: el hash del preregistro es resoluble en una URL
pública, el commit es anterior a cualquier dato de la Fase 1 y cualquiera puede
repetir la comprobación con `python herramientas/verificar_preregistro.py --url …`.

Lo que el sello publicado permite auditar a un tercero, sin pedir permiso a
nadie: que `g` estaba fijada en 9.80665, que `c2` y `c4` partían de 0.0, que el
umbral era 0.1, que el dataset era `pendulo_v1` y que la semilla era 20261124 —
**antes** de que existiera la corrida.

**Lo que el sello no prueba.** Que nadie mirase los datos antes de sellar. Eso
no lo resuelve el software: lo resuelve un registro público con testigos, y es
la razón por la que el sello se publica en un commit con fecha del servidor en
lugar de quedarse en local.

---

## Efecto sobre las corridas de referencia

| Hipótesis | v1.0.0 | v1.1.0 | Motivo |
|---|---|---|---|
| `pendulo_amplitud` | `CORROBORADA_PROVISIONAL` | `PRELIMINAR` | O01: no supera el baseline de cuarto orden |
| `pendulo_polinomio_alto` | `NO_CORROBORADA` | `NO_CORROBORADA` | Sin cambio: T07 y T08 siguen rechazándola |

Que la hipótesis «buena» deje de corroborarse es el resultado correcto. Antes se
estaba premiando una ventaja que dependía de compararse con un baseline
incompleto.

## Lo que este changelog no arregla

1. **Los datos siguen siendo sintéticos.** El laboratorio sigue generando su
   propia verdad. La Fase 1 de la hoja de ruta lo aborda y no se resuelve aquí.
2. **No hay corrección por comparaciones múltiples vinculante.** O05 calcula la
   corrección de Holm pero no cambia el veredicto.
3. **Una corrida por hipótesis no es replicación.** El consolidado avisa si hay
   varias, pero no impide repetir hasta que salga positiva.
4. **`PRELIMINAR` no es un aprobado suave.** No debe citarse como corroboración
   en ningún texto.
