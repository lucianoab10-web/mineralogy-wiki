"""Read Table 1 and append its symbols to recognized mineral headings.

ES/EN aliases identify minerals only. Abbreviations always come from the source
Markdown table; missing or ambiguous matches leave the sheet unchanged.
"""
from __future__ import annotations

import html
import importlib.util
import json
import logging
import re
import unicodedata
from pathlib import Path, PurePosixPath
from typing import NamedTuple
from urllib.parse import quote

from mkdocs.exceptions import ConfigurationError
from mkdocs.utils import get_relative_url
from mkdocs.utils.meta import get_data

log = logging.getLogger("mkdocs.hooks.mineral_abbreviations")
_matches = {}
_reference = None
_title = ""


class Entry(NamedTuple):
    symbol: str
    name: str
    status: str


def _plain(value):
    text = html.unescape(re.sub(r"<[^>]*>", "", str(value)))
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    return text.replace("[[", "").replace("]]", "").strip(" *_" + chr(96))


def _key(value):
    text = unicodedata.normalize("NFKD", _plain(value).casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[\s_\-–—]+", " ", text).strip()


def _outside_code(markdown):
    fence = None
    for line in markdown.splitlines():
        marker = re.match(r"^\s*(" + chr(96) + r"{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None:
            yield line


def _table(markdown):
    """Index Symbol / Mineral Name rows, excluding the separate IMA legend."""
    canonical, synonyms = {}, {}
    columns = None
    for line in _outside_code(markdown):
        if not line.lstrip().startswith("|"):
            if columns is not None:
                break
            continue
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if columns is None:
            keys = [_key(cell) for cell in cells]
            if "symbol" in keys and "mineral name" in keys:
                columns = (keys.index("symbol"), keys.index("mineral name"))
                status_column = next((i for i, key in enumerate(keys) if key.startswith("ima status")), None)
            continue
        if len(cells) <= max(columns):
            continue
        symbol, name = cells[columns[0]], _plain(cells[columns[1]])
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", symbol) or not name:
            continue
        status = cells[status_column] if status_column is not None and status_column < len(cells) else ""
        entry = Entry(symbol, name, status)
        # Keep species qualifiers without preceding whitespace: pumpellyite-(Al).
        primary = re.sub(r"\s+\([^)]*\)\s*$", "", name)
        canonical.setdefault(_key(primary), set()).add(entry)
        for alternative in re.findall(r"\s+\(([^)]*)\)", name):
            synonyms.setdefault(_key(alternative), set()).add(entry)
    return canonical, synonyms


def _load_aliases(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigurationError("Las equivalencias de minerales deben ser un objeto JSON.")
    aliases = {}
    for alias, names in raw.items():
        names = [names] if isinstance(names, str) else names
        if not isinstance(names, list) or not names or any(not isinstance(name, str) or not name.strip() for name in names):
            raise ConfigurationError(f"Equivalencia mineral no válida: {alias}")
        targets = tuple(names)
        key = _key(alias)
        if key in aliases and aliases[key] != targets:
            raise ConfigurationError(f"Equivalencia mineral ambigua: {alias}")
        aliases[key] = targets
    return aliases


def _table_entry(name, table):
    canonical, synonyms = table
    key = _key(name)
    # Canonical titanite selects Ttn, not the synonym of the sphene row (Spn).
    entries = canonical.get(key) if key in canonical else synonyms.get(key)
    if not entries or len({entry.symbol for entry in entries}) != 1:
        return None
    return sorted(entries)[0]


def _same_symbols(text, entries):
    return [part.strip().casefold() for part in text.split("/")] == [entry.symbol.casefold() for entry in entries]


def _lookup(name, table, aliases, allow_suffix=True):
    direct = _table_entry(name, table)
    if direct is not None:
        return (direct,)
    targets = aliases.get(_key(name))
    if targets is not None:
        entries = tuple(_table_entry(target, table) for target in targets)
        return entries if all(entry is not None for entry in entries) else None
    if allow_suffix:
        # Accept "Microclina Mc" or "Talco (Tlc)" only if the suffix agrees with
        # that same mineral's row. No fuzzy name or chemical-symbol matching.
        patterns = (
            r"^(.+?)\s+\(([A-Za-z0-9 /]+)\)$",
            r"^(.+?)\s+([A-Za-z][A-Za-z0-9]*(?:\s*/\s*[A-Za-z][A-Za-z0-9]*)*)$",
        )
        for pattern in patterns:
            match = re.fullmatch(pattern, _plain(name))
            if match:
                entries = _lookup(match.group(1), table, aliases, allow_suffix=False)
                if entries and _same_symbols(match.group(2), entries):
                    return entries
    return None


def _resolve(path, body, metadata, table, aliases):
    # Optional English identity supports new or ambiguous sheet filenames.
    if metadata.get("mineral_name_en"):
        names = metadata["mineral_name_en"]
        names = [names] if isinstance(names, str) else names
        if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
            return None
        entries = tuple(_table_entry(name, table) for name in names)
        return entries if entries and all(entry is not None for entry in entries) else None
    names = [PurePosixPath(path).stem]
    if isinstance(metadata.get("title"), str):
        names.append(metadata["title"])
    alternate = metadata.get("aliases") or []
    names.extend([alternate] if isinstance(alternate, str) else alternate if isinstance(alternate, list) else [])
    for line in _outside_code(body):
        heading = re.match(r"^#\s+(.+?)\s*#*\s*$", line)
        if heading:
            names.append(heading.group(1))
            break
    found = {_lookup(name, table, aliases) for name in names if isinstance(name, str)} - {None}
    if len(found) > 1:
        log.warning("Identidad mineral ambigua; no se añade abreviatura: %s", path)
        return None
    return next(iter(found), None)


def on_files(files, config, **kwargs):
    global _reference, _title
    _matches.clear()
    _reference, _title = None, ""
    extra = config.get("extra") or {}
    options = extra.get("mineral_abbreviations") or {}
    source = options.get("source")
    if not source:
        return files
    reference = files.get_file_from_path(source)
    if reference is None or not reference.is_documentation_page() or not reference.inclusion.is_in_nav():
        log.warning("No se encuentra la tabla de abreviaturas: %s", source)
        return files
    body, _ = get_data(reference.content_string)
    table = _table(body)
    if not table[0]:
        log.warning("No se encuentra una tabla Symbol / Mineral Name en %s", source)
        return files
    heading = re.search(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
    _title = _plain(heading.group(1)) if heading else "Table 1"
    _reference = reference
    project = Path(config.config_file_path).parent
    alias_path = project / options.get("aliases", "references/mineral-name-aliases.json")
    aliases = _load_aliases(alias_path)
    spec = importlib.util.spec_from_file_location("abbreviation_sheet_detection", project / "hooks/mineral_navigation.py")
    navigation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(navigation)
    nav = extra.get("mineral_navigation") or {}
    included = set(nav.get("include") or []) | set(nav.get("pending") or [])
    excluded = set(nav.get("references") or []) | set(nav.get("templates") or []) | {source}
    for file in files:
        if not file.is_documentation_page() or not file.inclusion.is_in_nav() or file.src_uri in excluded:
            continue
        if file.src_uri not in included and not navigation._is_mineral_sheet(file.content_string):
            continue
        content, metadata = get_data(file.content_string)
        entries = _resolve(file.src_uri, content, metadata, table, aliases)
        if entries:
            _matches[file.src_uri] = entries
    log.info("Abreviaturas de Table 1: %d fichas con coincidencia.", len(_matches))
    return files


def on_page_content(html_content, page, config, **kwargs):
    entries = _matches.get(page.file.src_uri)
    if not entries or _reference is None:
        return html_content
    page.meta["mineral_abbreviations"] = [entry.symbol for entry in entries]
    heading = re.search(r"(<h1\b[^>]*>)(.*?)(</h1\s*>)", html_content, flags=re.IGNORECASE | re.DOTALL)
    title = _plain(heading.group(2)).rstrip(" ¶") if heading else str(page.title or PurePosixPath(page.file.src_uri).stem)
    existing = re.search(r"(?:\(([^()]*)\)|\s([A-Za-z][A-Za-z0-9]*(?:\s*/\s*[A-Za-z][A-Za-z0-9]*)*))$", title)
    if existing and _same_symbols(existing.group(1) or existing.group(2), entries):
        return html_content
    target = quote(get_relative_url(_reference.url, page.url), safe="/%")
    labels = []
    for entry in entries:
        tooltip = f"{entry.name} · IMA: {entry.status} · {_title}"
        labels.append(f'<a href="{html.escape(target, quote=True)}" title="{html.escape(tooltip, quote=True)}">{html.escape(entry.symbol)}</a>')
    annotation = ' <span class="mineral-abbreviation">(' + " / ".join(labels) + ")</span>"
    if heading:
        inner = heading.group(2)
        permalink = re.search(r'<a\b[^>]*class=["\'][^"\']*\bheaderlink\b', inner, flags=re.IGNORECASE)
        position = permalink.start() if permalink else len(inner)
        replacement = heading.group(1) + inner[:position].rstrip() + annotation + inner[position:] + heading.group(3)
        return html_content[:heading.start()] + replacement + html_content[heading.end():]
    # Existing sheets often start with a table; Material otherwise adds its H1
    # later, in the template. The body and mineral page URL remain unchanged.
    return f"<h1>{html.escape(title)}{annotation}</h1>\n" + html_content
