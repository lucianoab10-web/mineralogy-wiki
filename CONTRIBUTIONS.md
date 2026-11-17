# Fotografías de la comunidad

Cada ficha de mineral incorpora un formulario móvil y añade las fotografías aprobadas como filas de su tabla `imagen | nota`. Las filas originales se conservan. La nota y el crédito se muestran como texto, sin interpretar HTML aportado por visitantes.

- **Recepción pública:** https://mineralogy-photo-submissions.knobbyion6.chatgpt.site
- **Revisión privada:** https://mineralogy-photo-review.knobbyion6.chatgpt.site
- **Acceso del revisor:** cuenta de ChatGPT propietaria del panel. El sitio de revisión debe permanecer privado.

La recepción acepta cámara, galería y archivos de imagen. El navegador prepara una copia JPEG de hasta 2400 píxeles por lado, conservando la proporción y normalizando la orientación. No envía el archivo original ni sus metadatos EXIF. Los HEIC/HEIF dependen de la capacidad del navegador para decodificarlos; si no puede, pide una copia JPEG. El servidor verifica tamaño, tipo y cabecera JPEG; ni SVG ni documentos son aceptados.

Los archivos pendientes se guardan en almacenamiento privado, separados del vault. El panel muestra imagen, mineral, nota editable y crédito; **Aprobar y publicar** hace pública esa foto y su nota, y **Rechazar** elimina el archivo. Las operaciones requieren autorización de servidor; ningún secreto se entrega al navegador o al repositorio. Los reintentos del mismo envío no crean copias.

## Integración con MkDocs y Obsidian

`hooks/mineral_contributions.py` reutiliza la detección de minerales de `mineral_navigation.py` y genera `assets/mineral-wiki/contribution-catalog.json`. Las fichas nuevas se incorporan automáticamente. `site-assets/contributions.js` localiza la tabla por sus encabezados y añade cada foto aprobada y su nota en la misma fila. Si una ficha carece de tabla de imágenes, la crea cuando hay una contribución aprobada.

`site-assets/mobile-tables.js` actualiza también las fichas móviles después de añadir las nuevas filas. La aprobación se refleja al abrir o recargar la ficha, sin reconstruir MkDocs. Las contribuciones están en el servicio de fotografías, no en `docs/` ni en las notas originales; el espejo de Obsidian puede regenerar `docs/` sin borrarlas.

Esto no realiza una sincronización inversa al vault local de Obsidian. Incorporar también imágenes a los archivos locales requiere un importador o un flujo de sincronización adicional en el equipo que guarda el vault.

Los orígenes del servicio y del panel se configuran en `extra.photo_contributions` de `mkdocs.yml`. No incluir credenciales en ese archivo. El backend y el panel se conservan en sus repositorios de código de Sites; el almacenamiento duradero utiliza D1 y R2. No compartir el panel de revisión con visitantes.
