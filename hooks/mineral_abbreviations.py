"""Link mineral sheets to the abbreviation reference mirrored from Obsidian."""
from __future__ import annotations

import html
import importlib.util
import logging
import re
from pathlib import Path
from urllib.parse import quote

from mkdocs.utils import get_relative_url
from mkdocs.utils.meta import get_data

log = logging.getLogger("mkdocs.hooks.mineral_abbreviations")
_sheets = set()
_reference = None
_title = ""


def on_files(files, config, **kwargs):
    global _reference, _title
    _sheets.clear()
    _reference, _title = None, ""
    extra = config.get("extra") or {}
    source = (extra.get("mineral_abbreviations") or {}).get("source")
    if not source:
        return files
    reference = files.get_file_from_path(source)
    if reference is None or not reference.is_documentation_page() or not reference.inclusion.is_in_nav():
        log.warning("No se encuentra la referencia de abreviaturas: %s", source)
        return files

    body, metadata = get_data(reference.content_string)
    heading = re.search(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
    _title = str(metadata.get("title") or (heading.group(1) if heading else "Tabla de abreviaturas"))
    _reference = reference

    project = Path(config.config_file_path).parent
    spec = importlib.util.spec_from_file_location("abbreviation_sheet_detection", project / "hooks/mineral_navigation.py")
    navigation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(navigation)
    options = extra.get("mineral_navigation") or {}
    included = set(options.get("include") or []) | set(options.get("pending") or [])
    excluded = set(options.get("references") or []) | set(options.get("templates") or []) | {source}
    for file in files:
        if not file.is_documentation_page() or not file.inclusion.is_in_nav() or file.src_uri in excluded:
            continue
        if file.src_uri in included or navigation._is_mineral_sheet(file.content_string):
            _sheets.add(file.src_uri)
    return files


def on_page_content(html_content, page, config, **kwargs):
    if _reference is None or page.file.src_uri not in _sheets:
        return html_content
    target = quote(get_relative_url(_reference.url, page.url), safe="/%")
    panel = (
        '<details class="mineral-abbreviations">'
        '<summary>Abreviaturas de minerales (EN)</summary>'
        '<p>Consulta los símbolos, los nombres en inglés y la leyenda del estado IMA en '
        f'<a href="{html.escape(target, quote=True)}">{html.escape(_title)}</a>.</p>'
        '</details>'
    )
    heading_end = re.search(r"</h1\s*>", html_content, flags=re.IGNORECASE)
    position = heading_end.end() if heading_end else 0
    return html_content[:position] + "\n" + panel + "\n" + html_content[position:]
