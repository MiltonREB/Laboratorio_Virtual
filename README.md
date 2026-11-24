# Laboratorio virtual de hipótesis

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
| Hipótesis evaluadas | 2 (una de control positivo, una de control negativo) |
| Pruebas del propio laboratorio | 255 (`python -m unittest discover -s pruebas -t .`) |
| Cobertura del paquete `lab` | 88.7 % (`python herramientas/cobertura.py`) |
| Pruebas del protocolo (por hipótesis) | 12 |
| Verificaciones opcionales | 5 (O01–O05); 3 ejercitadas en la demo |
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
& $py -m lab ejecutar --id pendulo_amplitud
& $py -m lab panel                # panel HTML en panel\index.html
```

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
│   ├── preregistro.py    sello criptográfico de parámetros y umbrales
│   ├── metricas.py       rmse / mae / chi2, bootstrap, reglas de decisión
│   ├── protocolo.py      batería T01–T12
│   ├── catalogo.py       catálogo de pruebas y verificaciones opcionales O01–O05
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
├── pruebas\              255 pruebas del propio laboratorio
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
| T03 | Predicción diferenciadora | La hipótesis coincide con el baseline o su ΔO no es observable |
| T04 | Preregistro | Los umbrales cambiaron después de sellarse, o no hay sello |
| T05 | Calibración | Se ajustó con datos reservados, o se declararon parámetros libres que nunca se ajustaron |
| T06 | Fuera de muestra | El error sobre datos reservados excede 5× la escala admitida |
| T07 | Baseline | No hay mejora significativa sobre el modelo convencional |
| T08 | Estabilidad | El signo de la mejora cambia al cambiar la partición |
| T09 | Reproducibilidad | Dos ejecuciones no dan exactamente lo mismo |
| T10 | Incertidumbre | El error real no cabe en el presupuesto declarado |
| T11 | Control nulo | La hipótesis «gana» sobre datos generados por el baseline |
| T12 | Dominio | Se evaluó fuera del rango declarado |

Los detalles normativos están en [PROTOCOLO.md](PROTOCOLO.md).

## Verificaciones opcionales

Cinco comprobaciones más que **amplían el diagnóstico sin cambiar el veredicto**.
Cada una declara su precondición: si no se cumple, queda registrado el motivo.

| Código | Verificación | Se ejecuta cuando |
|---|---|---|
| O01 | Contraste con baselines alternativos | La hipótesis declara `baselines_alternativos` |
| O02 | Validación por bloques del dominio | Hay ≥ 3 bloques de ≥ 10 filas reservadas |
| O03 | Sensibilidad al número de remuestreos | Se pide con `--sensibilidad-bootstrap` |
| O04 | Holdout externo | La hipótesis declara `dataset_validacion` y existe |
| O05 | Corrección por comparaciones múltiples | Más de una hipótesis usa el dataset |

La demo deja un resultado incómodo y útil. `pendulo_amplitud` gana al baseline
lineal (mejora +0.99) y al de segundo orden (+0.85), pero **no** al modelo de
cuarto orden con coeficientes fijos (mejora −0.0004). Su ventaja frente al
baseline principal procede de incorporar una corrección que ese baseline no
tiene, no de superar a un modelo correcto. Sin O01 eso no se ve.

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
las 255 pruebas, una corrida de demostración completa, la validación del panel
generado y la cobertura mínima.

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
| `CORROBORADA_PROVISIONAL` | Superó todas las pruebas bloqueantes y la conclusión es estable |
| `NO_CORROBORADA` | No generaliza o no demuestra mejora sobre el baseline |
| `REFUTADA` | Predice significativamente peor que el baseline en reservado |
| `NO_PRESENTADA` | No hay predicción diferenciadora que contrastar |
| `SENSIBLE_AL_DISENO` | La conclusión cambia al cambiar la partición de los datos |
| `FUERA_DE_DOMINIO` | La evaluación sale del rango declarado |
| `PENDIENTE` | Falta evidencia; nunca equivale a aprobación |

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
- **El preregistro prueba integridad, no anterioridad.** Registra si el sello se
  creó durante la evaluación y en ese caso no lo acepta.
- **Un veredicto negativo no refuta la idea**, sólo que este diseño no la
  sostiene.
