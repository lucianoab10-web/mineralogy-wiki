"""Agrupa las fichas de minerales sin mover notas ni cambiar sus URL.

Se ejecuta en cada build, tanto local como en GitHub Actions. Las fichas nuevas
se reconocen por la etiqueta ``minerales`` o por sus tablas de propiedades.
Las excepciones y las notas sin completar se declaran en mkdocs.yml.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import PurePosixPath

from mkdocs.exceptions import ConfigurationError
from mkdocs.utils.meta import get_data

log = logging.getLogger("mkdocs.hooks.mineral_navigation")


def _plain(text):
    return "".join(
        char for char in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(char)
    )


def _is_mineral_sheet(content):
    body, metadata = get_data(content)
    tags = metadata.get("tags") or []
    if isinstance(tags, str):
        tags = re.split(r"[\s,]+", tags)
    if any(str(tag).lstrip("#").casefold().split("/")[0] == "minerales" for tag in tags):
        return True

    # Buscar encabezados de tablas reales, fuera de bloques de código.
    # El orden de las columnas varía entre fichas.
    headers = []
    fence = None
    lines = body.splitlines()
    for index, line in enumerate(lines):
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence or "|" not in line or index + 1 >= len(lines):
            continue
        cells = lines[index + 1].strip().strip("|").split("|")
        if len(cells) < 2 or not all(re.fullmatch(r"\s*:?-{3,}:?\s*", cell) for cell in cells):
            continue
        headers.append(_plain(line))

    return any(all(term in header for term in ("color", "raya", "brillo", "dureza", "sistema cristalino")) for header in headers)


def _path_sort(path):
    name = PurePosixPath(path).name
    return (name.casefold() not in {"index.md", "readme.md"}, _plain(path), path)


def _navigation(paths):
    """Conservar las subcarpetas existentes de las notas generales."""
    tree = {}
    for path in sorted(paths, key=_path_sort):
        node = tree
        for folder in PurePosixPath(path).parts[:-1]:
            node = node.setdefault(folder, {})
        node[PurePosixPath(path).name] = path

    def render(node):
        result = []
        for name in sorted(node, key=_path_sort):
            child = node[name]
            result.append({name: render(child)} if isinstance(child, dict) else child)
        return result

    return render(tree)


def on_files(files, config, **kwargs):
    options = (config.get("extra") or {}).get("mineral_navigation") or {}
    pages = {
        file.src_uri: file for file in files
        if file.is_documentation_page() and file.inclusion.is_in_nav()
    }
    assigned = set()

    def configured_paths(key):
        paths = options.get(key) or []
        if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
            raise ConfigurationError(f"extra.mineral_navigation.{key} debe ser una lista de rutas .md.")
        missing = set(paths) - pages.keys()
        if missing:
            # Una eliminación o un cambio de nombre en Obsidian no debe impedir
            # la siguiente publicación. Las fichas etiquetadas se redetectan.
            log.debug("Rutas ausentes en mineral_navigation.%s: %s", key, ", ".join(sorted(missing)))
        duplicates = assigned.intersection(paths)
        if duplicates:
            raise ConfigurationError(f"Rutas repetidas entre grupos de minerales: {', '.join(sorted(duplicates))}")
        assigned.update(paths)
        return set(paths).intersection(pages)

    included = configured_paths("include")
    pending = configured_paths("pending")
    references = configured_paths("references")
    templates = configured_paths("templates")
    sheets = included | {
        path for path, file in pages.items()
        if path not in assigned and _is_mineral_sheet(file.content_string)
    }
    minerals = sheets | pending | references | templates
    if not minerals:
        return files

    children = sorted(sheets, key=_path_sort)
    for title, paths in (("Tablas y guías", references), ("Por completar", pending), ("Plantillas", templates)):
        if paths:
            children.append({title: sorted(paths, key=_path_sort)})

    remaining = set(pages) - minerals
    home = sorted((path for path in remaining if path.casefold() in {"index.md", "readme.md"}), key=_path_sort)
    config["nav"] = home + [{options.get("title", "Fichas de minerales"): children}] + _navigation(remaining - set(home))
    log.info("mineral_navigation: %d fichas; %d páginas en la sección; %d notas generales.", len(sheets), len(minerals), len(remaining))
    return files
