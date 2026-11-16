# Taxonomía de minerales

Esta nota define la clasificación de las fichas. Copia este archivo a la parte publicada de tu vault como `Taxonomia_minerales.md` para editarlo desde Obsidian. La copia del vault tiene prioridad; si todavía no existe, la web utiliza este modelo.

En la sección **Clasificación**, cada viñeta crea un grupo. La sangría crea subgrupos. Después de `:` escribe una o varias etiquetas equivalentes con `#`. Puedes cambiar los nombres visibles, las etiquetas, el orden y la profundidad.

## Clasificación

- Elementos nativos: #elemento-nativo, #elementos-nativos
- Sulfuros y sulfosales
  - Sulfuros: #sulfuro, #sulfuros
  - Sulfosales: #sulfosal, #sulfosales
- Óxidos: #oxido, #oxidos, #óxido, #óxidos
- Hidróxidos y oxihidróxidos: #hidroxido, #hidroxidos, #hidróxido, #hidróxidos, #oxihidroxido, #oxihidroxidos
- Haluros: #haluro, #haluros
- Carbonatos: #carbonato, #carbonatos
- Sulfatos: #sulfato, #sulfatos
- Fosfatos: #fosfato, #fosfatos
- Silicatos: #silicato, #silicatos
  - Nesosilicatos: #nesosilicato, #nesosilicatos
  - Sorosilicatos: #sorosilicato, #sorosilicatos
  - Ciclosilicatos: #ciclosilicato, #ciclosilicatos
  - Inosilicatos: #inosilicato, #inosilicatos
  - Filosilicatos: #filosilicato, #filosilicatos
  - Tectosilicatos: #tectosilicato, #tectosilicatos

## Etiquetas en cada ficha

Ejemplo del panel de propiedades de Talco:

```yaml
---
tags:
  - minerales
  - filosilicato
---
```

También puedes usar una etiqueta anidada de Obsidian, como `minerales/silicatos/filosilicatos`. Si la etiqueta de este contexto es simple (`#filosilicatos`), se compara con el último segmento. Una etiqueta contextual que incluya `/` exige la coincidencia de la ruta completa.

Se aceptan las variantes enumeradas explícitamente y no se adivinan clasificaciones a partir del nombre o la composición. Los acentos se conservan; añade ambas formas como equivalentes si las utilizas. Mayúsculas y `#` inicial no cambian la coincidencia.

La coincidencia de un subgrupo tiene prioridad sobre su grupo superior: `silicatos` + `filosilicatos` produce **Silicatos → Filosilicatos**. Si coinciden dos ramas diferentes, la ficha aparece en **Por revisar**, mostrando ambas clasificaciones. Si no coincide ninguna, permanece en **Sin clasificar**.

Las fichas y sus URL conservan su ubicación. Los cambios se reflejan al publicar las notas y reconstruir la wiki. Las etiquetas locales que todavía no se han publicado no pueden verse en la web.
