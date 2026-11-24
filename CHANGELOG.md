# Changelog

Cambios del **software y del repositorio**. Los cambios del **protocolo**
(pruebas, umbrales, estados, veredictos) se documentan aparte, con su
justificación y su coste, en
[CHANGELOG_METODOLOGICO.md](CHANGELOG_METODOLOGICO.md).

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Versionado semántico: la versión mayor cambia cuando el protocolo deja de ser
retrocompatible.

## [No publicado] — 2026-11-24

### Cambiado

- **Repositorio renombrado** de `Laboratorio_Virtual` a `lab-hipotesis` para
  alinear el nombre del repositorio con el nombre del paquete distribuible.
  Decisión del usuario. GitHub redirige las URLs anteriores (HTTP 301, y las
  que apuntan a un commit o a un blob siguen resolviendo).
- El commit del preregistro `14bf993` y los sellos SHA-256 de los preregistros
  **no cambian**: el renombrado afecta sólo al localizador, no al contenido.
  Verificado recalculando `0d700ebf…3fefa2` desde el JSON publicado.
- URLs del repositorio actualizadas en `README.md`, `pyproject.toml`
  (`Homepage`, `Repository`, `Issues`) y `CHANGELOG_METODOLOGICO.md`.

### Añadido

- Licencia **Apache 2.0** (`LICENSE`, texto oficial sin modificaciones) y
  `NOTICE` con el titular del copyright.
- Metadatos de licencia en `pyproject.toml` (`license = "Apache-2.0"`,
  `license-files`, clasificador OSI) y campo `readme`.
- `CONTRIBUTING.md` con la cláusula de contribución bajo Apache 2.0, el proceso
  de RFC para cambios de protocolo y la nota sobre un futuro CLA si se
  dual-licencia.
- Sección «Licencia» en `README.md`.

## [1.1.0] — 2026-11-24

### Añadido

- Ingesta de CSV reales (`lab ingestar`, `lab run`) con validación de esquema,
  SHA-256 y partición congelada.
- Presupuesto de incertidumbre combinado (declarada ⊕ experimental) en T10.
- Hipótesis `pendulo_amplitud_real`, con `g` estimada de la calibración.
- Ajuste de los parámetros libres del baseline en el evaluador.
- Advertencias de viabilidad V01–V06 antes de la batería.
- Verificador de preregistros (`herramientas/verificar_preregistro.py`).

### Cambiado

- Protocolo v1.1.0: ver [CHANGELOG_METODOLOGICO.md](CHANGELOG_METODOLOGICO.md).
  Estados reducidos a cuatro, T03 relativa a la escala del baseline, O01 y O04
  vinculantes, separación temporal del preregistro, ratio de errores en todos
  los informes.

## [1.0.0] — 2026-11-24

### Añadido

- Motor del laboratorio: contrato declarativo, preregistro con sello SHA-256,
  doce pruebas de protocolo, cinco verificaciones adicionales.
- Panel HTML estático con un gráfico por prueba y catálogo de pruebas.
- Informe por corrida y informe consolidado.
- Adaptadores para código externo (en proceso y en subproceso).
- Integración continua con verificación de integridad de datos, regeneración
  bit a bit y cobertura mínima.

---

## Qué no está publicado

- **PyPI**: no se ha publicado ningún paquete. El nombre `lab-hipotesis` está
  reservado en `pyproject.toml`, pero subirlo es irreversible en la práctica y
  la v1.0.0 debe incluir la corrida con datos reales de la Fase 1.
- **Zenodo/DOI**: no hay depósito ni DOI. Sin Fase 1 no hay versión citable.
- **Tags**: no se ha creado ninguna etiqueta de versión.
