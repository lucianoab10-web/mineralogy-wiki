# Abreviaturas automáticas en las fichas

En cada publicación, `hooks/mineral_abbreviations.py` consulta la tabla con las
columnas `Symbol` y `Mineral Name` de `docs/abreviaturas minerales (EN).md`.
Las fichas reconocidas muestran el símbolo entre paréntesis tras el nombre:
`Magnetita (Mag)`, `Talco (Tlc)`, `Calcita (Cal)`.

El símbolo procede siempre del Markdown. `mineral-name-aliases.json` contiene
únicamente equivalencias de nombres españoles a nombres ingleses, nunca símbolos.
Una equivalencia puede existir aunque el mineral todavía no figure en la tabla:
en ese caso no se añade ninguna abreviatura. Las coincidencias ambiguas tampoco
se publican. No se usan búsquedas por parecido ni símbolos químicos como sustituto.

Se reconocen el nombre del archivo, el primer título, `title` y `aliases` de
Obsidian. Para una ficha nueva cuyo nombre no se reconozca, se puede añadir una
equivalencia en el JSON o declarar su identidad inglesa en las propiedades:

```yaml
mineral_name_en: talc
```

Las fichas que describen dos especies pueden usar una lista de nombres ingleses.
Ambas especies deben existir en la tabla para mostrar sus dos abreviaturas.

La abreviatura enlaza a la tabla de origen y conserva su nombre inglés y estado
IMA como información emergente. Los nombres ingleses canónicos tienen prioridad
sobre las variantes entre paréntesis: `titanite` utiliza su propia fila, no la
fila distinta `sphene (titanite)`.

El cambio se aplica al HTML generado. No modifica las notas de Obsidian, sus
nombres de archivo, sus enlaces ni el catálogo de contribuciones fotográficas.

## Clasificación automática de las fichas

La tabla `docs/clasificacion minerales.md` define la ruta de navegación de cada
identidad reconocida: Clase → Subclase → Familia → Subgrupo. La copia que se
edita en Obsidian es `compartidos/second-brain/markdowns/clasificacion minerales.md`;
la sincronización habitual la lleva a `docs`, igual que la tabla de abreviaturas.

`hooks/mineral_classification.py` lee la tabla en cada compilación y
`hooks/mineral_navigation.py` construye los grupos sin mover las fichas ni cambiar
sus URL. Las columnas `Tipo`, `Nota` y `Fuentes` documentan el criterio, pero no
añaden niveles al menú. La tabla explica qué ramas son conjuntos de estudio y
qué nombres corresponden a series, grupos o mezclas.

Las identidades se reconocen por nombres y equivalencias exactas. El JSON de
alias identifica nombres españoles e ingleses; las clasificaciones proceden
exclusivamente del Markdown. Si una ficha no se reconoce o sus identidades son
contradictorias, permanece en «Por clasificar». Una fila ambigua en la tabla se
informa como error de configuración. Las notas «Por completar» siguen separadas.

No se asignan clasificaciones a partir de palabras parecidas, fórmulas o etiquetas.
Una fila nueva puede preparar la clasificación de un mineral que todavía no tenga
ficha, como un borato: la tabla no genera páginas minerales vacías.
