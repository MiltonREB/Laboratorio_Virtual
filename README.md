# Laboratorio virtual de hipótesis

[![estado](https://img.shields.io/badge/protocolo-v1.1.0-blue)](CHANGELOG_METODOLOGICO.md)
[![repositorio](https://img.shields.io/badge/github-lab--hipotesis-181717)](https://github.com/MiltonREB/lab-hipotesis)
[![licencia](https://img.shields.io/badge/licencia-Apache--2.0-blue)](LICENSE)

Un marco para **contrastar hipótesis cuantitativas** de cualquier dominio con un
protocolo fijo: preregistro de parámetros y umbrales, calibración separada,
validación sobre datos reservados, comparación contra un baseline convencional,
control nulo, estabilidad de diseño, reproducibilidad y un veredicto explícito.

El laboratorio no sabe física. Sabe qué exigir.

## Qué es y qué no es

**Es** un banco de pruebas reproducible: cada hipótesis se declara como una clase
con metadatos verificables y se somete siempre a las mismas doce pruebas. Todo
resultado queda en disco con los números que lo sostienen y con la lista de lo que
el experimento **no** demuestra.

**No es** un simulador, ni una fuente de datos, ni una prueba de que una idea sea
cierta. Una hipótesis `CORROBORADA_PROVISIONAL` significa que superó este
protocolo con estos datos, no que sea verdadera.

## Estado actual

| Elemento | Cantidad |
|---|---|
| Protocolo | v1.1.0 ([changelog metodológico](CHANGELOG_METODOLOGICO.md)) |
| Hipótesis evaluadas | 3 (dos sintéticas de control y una preparada para datos medidos) |
| Pruebas del propio laboratorio | 329 (`python -m unittest discover -s pruebas -t .`) |
| Pruebas del protocolo (por hipótesis) | 12, todas bloqueantes |
| Verificaciones adicionales | 5 (O01–O05); O01 y O04 vinculantes |
| Gráficos por corrida | 12 (uno por prueba) + los de verificación ejecutada |
| Datasets congelados con SHA-256 | 3 (dos de ajuste, uno de validación externa) |

Las dos hipótesis incluidas son **demostraciones de la maquinaria**, no física
nueva:

- `pendulo_amplitud` — corrección de amplitud finita del péndulo. Debe salir
  corroborada (y sale).
- `pendulo_polinomio_alto` — polinomio de grado 15 ajustado sobre un diseño sin
  señal suficiente. Debe salir no corroborada (y sale).

Si el laboratorio aprobara la segunda, el laboratorio estaría roto. Por eso están
las dos.

## Inicio rápido

No requiere instalación: basta con ejecutar desde esta carpeta con el Python del
proyecto.

```powershell
$py = 'C:\atomo\.venv\Scripts\python.exe'
cd C:\atomo\laboratorio

& $py -m lab hipotesis listar     # qué hipótesis hay y si su contrato está completo
& $py -m lab datos verificar      # integridad SHA-256 y particiones de cada dataset
& $py -m lab preregistrar --id pendulo_amplitud
& $py -m lab ejecutar --id pendulo_amplitud    # exige 60 s desde el sello
& $py -m lab panel                # panel HTML en panel\index.html
```

El paso de preregistro y el de ejecución están separados a propósito: por defecto
`lab ejecutar` rechaza un sello creado hace menos de 60 segundos
(`--separacion-minima`). Si además quieres anclar el sello a un testigo externo,
haz `git add` + `git commit` del archivo del sello y añade `--exigir-publicacion`.

Después, cualquiera puede comprobar —sin credenciales— que el sello publicado es
el que se usó en la corrida:

```powershell
& $py herramientas\verificar_preregistro.py `
      --sello resultados\preregistro\<hipotesis>\<sello>.json `
      --resumen resultados\<corrida>\resumen.json `
      --url https://raw.githubusercontent.com/<usuario>/<repo>/<commit>/<ruta-al-sello>
```

Compara tres cosas: el hash recalculado del sello, el que la corrida registró y
el de la copia publicada. Los tres tienen que coincidir.

Para evaluar todo de una vez:

```powershell
& $py -m lab ejecutar --todos --panel
```

Para consultar la matriz de estados de la última corrida de cada hipótesis:

```powershell
& $py -m lab estado
```

Para un informe único que compare todas las hipótesis, con avisos de familia y
de corridas repetidas:

```powershell
& $py -m lab consolidado
```

Opcionalmente, para tener el comando `lab` en el entorno:

```powershell
& $py -m pip install -e .
lab estado
```

## Estructura

```
laboratorio\
├── lab\                  motor del laboratorio (no depende del dominio)
│   ├── contrato.py       Modelo, Hipotesis, Dominio, Parametro, estados
│   ├── datos.py          manifiesto, SHA-256, particiones congeladas
│   ├── ingesta.py        registro de CSV reales (esquema, hash, partición)
│   ├── preregistro.py    sello criptográfico de parámetros y umbrales
│   ├── metricas.py       rmse / mae / chi2, bootstrap, reglas de decisión
│   ├── protocolo.py      batería T01–T12
│   ├── catalogo.py       catálogo de pruebas y verificaciones O01–O05
│   ├── viabilidad.py     avisos calculados antes de la corrida
│   ├── graficos.py       un gráfico SVG por prueba
│   ├── veredicto.py      agregación de estados en un veredicto
│   ├── evaluador.py      orquestación, artefactos y esquema de resumen.json
│   ├── adaptadores.py    envuelve código externo (en proceso o subproceso)
│   ├── consolidado.py    informe único que compara todas las hipótesis
│   ├── informe.py        informe Markdown y resumen de consola
│   ├── panel.py          panel HTML estático (portada, catálogo y corridas)
│   └── cli.py            interfaz de línea de comandos
├── hipotesis\            una hipótesis por archivo (se cargan al arrancar)
├── datos\                CSV congelados + manifiesto.json
├── herramientas\         verificación del panel, adaptador y cobertura
├── resultados\           una carpeta por corrida + sellos + consolidado
├── panel\                panel HTML generado (no versionado)
├── pruebas\              326 pruebas del propio laboratorio
│   └── fixtures\         CSV con el esquema real (sintético, sólo para pruebas)
└── .github\workflows\    integración continua
```

## Añadir una hipótesis

```powershell
& $py -m lab nuevo --id mi_idea --nombre "Descripción corta"
```

Eso crea `hipotesis\mi_idea.py` con el esqueleto completo. Después:

1. **Rellena los `TODO`**: baseline, `predecir` y, si hay parámetros libres,
   `ajustar`.
2. **Declara el dataset** en `datos\manifiesto.json`, con su SHA-256 y la
   partición `calibracion` / `reservado`. El laboratorio no divide datos por su
   cuenta.
3. **Comprueba el contrato**: `lab hipotesis listar` debe decir `[lista]`.
4. **Sella los umbrales**: `lab preregistrar --id mi_idea`. A partir de aquí no
   cambies parámetros, umbrales, métrica ni semilla.
5. **Evalúa**: `lab ejecutar --id mi_idea`.

El punto 2 es el que más se subestima. Si no hay datos reservados declarados
antes de mirar los resultados, no hay validación fuera de muestra, y el protocolo
lo dice en lugar de disimularlo.

### El contrato mínimo

```python
class MiIdea(Hipotesis):
    id = "mi_idea"
    observables = ("y",); requiere = ("x",)
    enunciado = "Una frase falsable"
    prediccion_diferenciadora = "Qué predice que el baseline no predice, y dónde se vería"
    dominio = Dominio("dónde vale", rango={"x": (0.0, 1.0)}, limitaciones=())
    observable_objetivo = "y"; unidad_observable = "u"
    baseline = MiBaseline()          # modelo convencional de referencia
    dataset_id = "mi_dataset"
    metrica = "rmse"; umbral_mejora = 0.10; umbral_sensibilidad = 1e-3
    incertidumbre_declarada = 1e-3; semilla = 0
```

`predecir` debe ser una **función pura**: mismos parámetros y variables, mismos
números. `ajustar` recibe sólo la muestra de calibración.

## Las doce pruebas

| Código | Prueba | Qué falla si no se cumple |
|---|---|---|
| T01 | Formalización | Falta un metadato, unidad o dominio |
| T02 | Falsabilidad | La predicción es constante, vacía o no numérica |
| T03 | Predicción diferenciadora | \|ΔO\| no alcanza el error del baseline × factor |
| T04 | Preregistro | Sello ausente, reciente, alterado o sin publicar |
| T05 | Calibración | Se ajustó con datos reservados, o se declararon libres que nunca se ajustaron |
| T06 | Fuera de muestra | El error sobre datos reservados excede 5× la escala admitida |
| T07 | Baseline | No hay mejora significativa sobre el modelo convencional |
| T08 | Estabilidad | El signo de la mejora cambia al cambiar la partición |
| T09 | Reproducibilidad | Dos ejecuciones no dan exactamente lo mismo |
| T10 | Incertidumbre | El error real no cabe en el presupuesto declarado |
| T11 | Control nulo | La hipótesis «gana» sobre datos generados por el baseline |
| T12 | Dominio | Se evaluó fuera del rango declarado |

Cuatro estados: `APROBADO`, `PENDIENTE`, `SENSIBLE`, `FALLIDO`. Ninguna prueba se
llama «refutada» y T07/T08 nunca declaran fracaso: que el baseline sea mejor dice
que este diseño no sostiene la hipótesis, no que la idea sea falsa.

Los detalles normativos están en [PROTOCOLO.md](PROTOCOLO.md).

## Verificaciones adicionales

Cinco comprobaciones más. **Dos son vinculantes** (O01 y O04): condicionan el
veredicto máximo. Las otras tres son informativas.

| Código | Verificación | Vinculante | Se ejecuta cuando |
|---|---|---|---|
| O01 | Contraste con baselines alternativos | **Sí** | La hipótesis declara `baselines_alternativos` |
| O02 | Validación por bloques del dominio | No | Hay ≥ 3 bloques de ≥ 10 filas reservadas |
| O03 | Sensibilidad al número de remuestreos | No | Se pide con `--sensibilidad-bootstrap` |
| O04 | Holdout externo | **Sí** | Declara `dataset_validacion` y existe |
| O05 | Corrección por comparaciones múltiples | No | Más de una hipótesis usa el dataset |

La demo deja un resultado incómodo y útil. `pendulo_amplitud` gana al baseline
lineal (mejora +0.99) y al de segundo orden (+0.85), pero **no** al modelo de
cuarto orden con coeficientes fijos (mejora −0.0004). Su ventaja frente al
baseline principal procede de incorporar una corrección que ese baseline no
tiene, no de superar a un modelo correcto.

Por eso su veredicto es **`PRELIMINAR`**, no `CORROBORADA_PROVISIONAL`: doce
pruebas cumplidas, holdout externo superado, pero no gana a todos los baselines.
Ése es exactamente el tipo de hallazgo que antes quedaba enterrado en una
verificación opcional.

## Advertencias de viabilidad (antes de la corrida)

Antes de ejecutar la batería el laboratorio calcula seis comprobaciones que **no
cambian el veredicto** y ahorran corridas: parámetros libres frente a filas de
calibración, tamaño del reservado, umbral dentro del ruido, cobertura del dominio,
presupuesto de incertidumbre y estado del preregistro. Aparecen en el informe, en
el panel y en la consola.

## Datos reales (preparación de la Fase 1)

El laboratorio acepta un CSV medido, no sólo sus datasets sintéticos. Esquema:

```
L_m, theta0_rad, T_s, u_T_s, u_L_m, u_theta0_rad
```

Las columnas `u_*` son incertidumbres por fila. Si `u_T_s` existe, T10 la usa como
término explícito del presupuesto (`sqrt(declarada² + experimental²)`); si no
existe, lo dice en vez de inventarla.

```powershell
& $py -m lab ingestar --csv mi_medicion.csv --id pendulo_real `
      --procedencia "Laboratorio docente, 2026-11-24, fotopuerta"
& $py -m lab preregistrar --id pendulo_amplitud_real
& $py -m lab ejecutar --id pendulo_amplitud_real
```

`lab ingestar` calcula el SHA-256, comprueba el esquema, fija la partición
calibración/reservado con una semilla registrada y la congela en el manifiesto.
También existe `lab run --csv ... --id ... --hipotesis ...` para hacer ingesta y
evaluación en un paso.

La hipótesis `pendulo_amplitud_real` es la que corresponde a datos medidos:
estima `g` con la calibración (no la fija en 9.80665), declara `c2` y `c4` libres
y exige un baseline alternativo. Su baseline también se ajusta: comparar un
modelo con `g` ajustada contra otro con `g` nominal daría una ventaja artificial.

**Confondo documentado:** el estimador de `g` del baseline ignora la corrección de
amplitud, así que queda un sesgo residual a la baja de ~0.3 % que favorece
levemente a la hipótesis. Está medido en las pruebas y anotado en el changelog.

**Esto no es la Fase 1.** `pruebas/fixtures/pendulo_medido_fixture.csv` es
sintético: tiene el esquema real para probar la tubería, no para producir
evidencia. No hay ninguna medición todavía.

## Adaptadores para código heredado

`lab/adaptadores.py` convierte código existente en un `Modelo` del laboratorio,
que es lo único que el protocolo sabe usar como baseline o como motor:

```python
from lab.adaptadores import modelo_desde_funcion, modelo_desde_subproceso

modelo = modelo_desde_funcion(
    lambda variables, parametros: {"T_s": calcular(variables["L_m"])},
    id="mi_legado", nombre="Mi módulo anterior",
    observables=("T_s",), requiere=("L_m",),
)
```

- **En proceso** (`ModeloDesdeFuncion`): envuelve un `callable`.
- **En subproceso** (`ModeloSubproceso`): habla JSON por tuberías con un
  programa externo. Entrada `{"variables": {...}, "parametros": {...},
  "observables": [...]}`; salida `{"observable": [valores]}`.

Cualquier fallo del código adaptado (código de salida, JSON inválido, tiempo
agotado, forma incorrecta) se convierte en error de evaluación: un modelo roto
no puede parecer un modelo que predice mal.

Prueba contra código real del proyecto anterior:

```powershell
& $py herramientas\prueba_adaptador.py
```

Envuelve `prdu_atomico.core.electron_acceleration_from_vcm` del paquete v74
instalado y comprueba que reproduce la función original bit a bit. **No** evalúa
ninguna hipótesis PRDU ni afirma física: verifica el mecanismo.

## Repositorio, CI y cobertura

El laboratorio es un repositorio git con integración continua
(`.github/workflows/ci.yml`). En cada push, CI ejecuta: integridad de los datos
congelados, regeneración bit a bit de los datasets (`git diff --exit-code`),
las 297 pruebas, una corrida de demostración completa, la validación del panel
generado y la cobertura mínima. La corrida de CI usa `--separacion-minima 0`
porque sólo comprueba la fontanería; el requisito de anterioridad es una
garantía de proceso, no de CI.

La cobertura se mide sin dependencias externas, con el módulo `trace` de la
biblioteca estándar:

```powershell
& $py herramientas\cobertura.py            # informe por módulo
& $py herramientas\cobertura.py --minimo 80 # falla por debajo del umbral
```

## El panel: pruebas, gráficos y catálogo

`panel\index.html` es la portada (matriz de estados, tarjetas de veredicto,
historial). Desde ahí se llega a dos páginas:

**Cada corrida** (`panel\corridas\<hipotesis>_<fecha>.html`) muestra una tarjeta
por prueba con:

- el estado y el motivo concreto del resultado,
- sus números clave,
- **un gráfico propio de esa prueba**, generado con los datos de la corrida:

| Prueba | Qué dibuja |
|---|---|
| T01 | Campos del contrato declarados frente a los exigidos |
| T02 | Distribución de la predicción en la muestra reservada |
| T03 | ΔO fila a fila frente a la sensibilidad declarada |
| T04 | El sello de preregistro y sus tres comprobaciones |
| T05 | Reparto de filas entre calibración y reservado |
| T06 | Residuos fuera de muestra frente a la banda admitida |
| T07 | Distribución bootstrap de la mejora con su IC |
| T08 | Mejora en cada partición alternativa |
| T09 | Las dos ejecuciones y su igualdad bit a bit |
| T10 | Razón error/incertidumbre frente a la banda [1/3, 3] |
| T11 | Mejora sobre datos nulos con su IC |
| T12 | Cobertura del dominio declarado por variable |

Debajo, la sección **«Verificaciones opcionales: ejecutadas y no requeridas»**
lista las cinco verificaciones O01–O05 con su estado y el motivo. «No requerida»
nunca significa «superada»: suele ser una precondición que la hipótesis no
cumple (sin segundo baseline, sin holdout declarado, sin filas suficientes…).

**`panel\pruebas.html`** es el catálogo global: todas las pruebas que el
laboratorio sabe hacer, para qué sirven, **en qué caso legítimo no se ejecutan**
y qué pasó con cada hipótesis en su última corrida.

Para comprobar que el panel generado sigue siendo válido (HTML bien formado,
SVG parseables y sin coordenadas fuera de lienzo):

```powershell
& $py herramientas\verificar_panel.py
```

## Veredictos

| Veredicto | Significado |
|---|---|
| `CORROBORADA_PROVISIONAL` | Doce pruebas cumplidas, supera a todos los baselines declarados, se sostiene en holdout externo y es estable |
| `PRELIMINAR` | Doce pruebas cumplidas, pero falta O01 u O04, o no gana a algún baseline alternativo |
| `NO_CORROBORADA` | No generaliza, no demuestra mejora, o falla el holdout externo |
| `NO_PRESENTADA` | No hay predicción diferenciadora contrastable |
| `SENSIBLE` | La conclusión cambia al cambiar la partición de los datos |
| `FUERA_DE_DOMINIO` | La evaluación sale del rango declarado |
| `PENDIENTE` | Falta evidencia; nunca equivale a aprobación |

`PRELIMINAR` no es un aprobado suave: no debe citarse como corroboración.

## Qué produce cada corrida

En `resultados\<hipotesis>_<fecha>\`:

| Archivo | Contenido |
|---|---|
| `resumen.json` | Todo: hipótesis, baseline, parámetros, errores, bootstrap (con su histograma), estabilidad, control nulo, preregistro, verificaciones opcionales, entorno |
| `INFORME.md` | Informe legible con la matriz de pruebas, las verificaciones opcionales y la sección «qué no demuestra» |
| `matriz.csv` | Los doce estados con su detalle |
| `predicciones.csv` | Fila a fila: observado, predicción de la hipótesis, del baseline, residuos |

Y en `panel\`:

| Archivo | Contenido |
|---|---|
| `index.html` | Portada: matriz de estados, tarjetas de veredicto, historial |
| `pruebas.html` | Catálogo de todas las pruebas y por qué alguna no fue necesaria |
| `corridas\<id>.html` | Una página por corrida, con un gráfico por prueba |

## Sobre el material PRDU de `C:\atomo\archivos`

Este laboratorio se creó **separado** del árbol de versiones PRDU
(v1–v75) y no lo modifica. Es deliberado: el protocolo sólo es útil si puede
aplicarse a cualquier hipótesis, incluida PRDU, sin que el marco herede sus
supuestos.

Cuando quieras contrastar una hipótesis PRDU concreta, el camino es:

1. Formularla como una predicción diferenciadora numérica frente a un baseline
   convencional explícito.
2. Declarar el dataset (puede ser un CSV extraído de un módulo existente) con su
   SHA-256 y su partición reservada.
3. Sellar los umbrales antes de evaluar.

Una hipótesis que no produzca un ΔO mayor que la sensibilidad declarada recibirá
`NO_PRESENTADA`, que es exactamente la información útil: todavía no es
contrastable.

## Limitaciones del laboratorio

- **Un protocolo no convierte datos sintéticos en evidencia física.** Los
  datasets incluidos son controles de la maquinaria.
- **El bootstrap percentil supone que la muestra reservada es representativa.**
  Si el diseño no lo es, el intervalo tampoco.
- **El control nulo usa el baseline como verdad.** Detecta ventajas espurias por
  flexibilidad, no todos los sesgos de selección.
- **El preregistro acredita integridad y separación, no buena fe.** El sello
  detecta cambios posteriores y exige antigüedad mínima y publicación en un
  commit, pero no puede probar que nadie mirase los datos antes de sellar.
- **Un veredicto negativo no refuta la idea**, sólo que este diseño no la
  sostiene.

## Licencia

Código bajo **Apache 2.0**. Las contribuciones se aceptan bajo la misma
licencia: ver [CONTRIBUTING.md](CONTRIBUTING.md). El texto completo está en
[LICENSE](LICENSE) y el titular del copyright en [NOTICE](NOTICE).

Los datos y resultados del repositorio se distribuyen con la misma licencia
salvo que un archivo declare otra cosa. Los valores de referencia externos que
se incorporen en el futuro (CODATA, IUPAC, modelos geodésicos) conservarán su
propia licencia y cita.
