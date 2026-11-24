# Cómo contribuir

Gracias por el interés. Este proyecto se toma en serio su propio protocolo, así
que las reglas de contribución son parte del producto, no un trámite.

## Licencia de las contribuciones

Al enviar una contribución aceptas que se distribuya bajo **Apache License 2.0**,
la misma del proyecto (ver [LICENSE](LICENSE)). No se exige firmar nada para
contribuciones ordinarias: el envío de un *pull request* implica esa aceptación.

**Nota sobre el futuro.** Si en algún momento se decide una licencia dual para
una capa enterprise, hará falta un CLA (Contributor License Agreement) para
poder relicenciar. Ese CLA **no existe todavía** y no se pedirá
retroactivamente sin avisar y sin dejar constancia en este archivo. Cualquier
cambio de licencia se anunciará en [CHANGELOG.md](CHANGELOG.md).

## Antes de abrir un pull request

```powershell
python -m unittest discover -s pruebas -t .
python herramientas/cobertura.py --minimo 80
python herramientas/verificar_panel.py      # si tocaste el panel o los gráficos
```

Las tres deben pasar. No se aceptan cambios que bajen la cobertura del 80 %.

## Qué se puede cambiar sin ceremonia

- Correcciones de errores, mejoras de mensajes, documentación, pruebas nuevas.
- Añadir una **prueba** al protocolo: sí, pero ver la sección siguiente.
- Añadir un adaptador para código externo.

## Qué exige discusión previa (RFC)

Las doce pruebas y el veredicto son el núcleo del proyecto. Cambiar **qué se
exige** o **cómo se agrega** un veredicto afecta a resultados ya publicados, así
que requiere:

1. Un *issue* con la etiqueta `rfc`.
2. La justificación metodológica: qué se gana, qué se pierde, qué corridas
   anteriores cambian de veredicto.
3. Una entrada en [CHANGELOG_METODOLOGICO.md](CHANGELOG_METODOLOGICO.md) con
   fecha, motivo y coste del cambio.
4. Actualización de [PROTOCOLO.md](PROTOCOLO.md) y de las pruebas unitarias de
   los estados afectados.

Un cambio de protocolo que no actualiza el changelog metodológico se rechaza,
aunque el código sea correcto.

## Estilo

- Python ≥ 3.10, sin dependencias más allá de NumPy en el núcleo.
- Español en documentación, mensajes y nombres de dominio; inglés sólo en
  identificadores que ya son estándar (`id`, `baseline`, `dataset_id`).
- Nada de acentos en nombres de archivo.
- `unittest`, no `pytest`, para que la suite corra con el intérprete del sistema
  sin instalar nada.

## Qué no se acepta

- Afirmaciones de física nueva sin predicción diferenciadora declarada.
- Resultados retocados: si una corrida da `NO_CORROBORADA`, se publica así.
- Añadir dependencias que impidan ejecutar la suite sin red.
- Cambiar el contenido de un sello de preregistro ya publicado.
