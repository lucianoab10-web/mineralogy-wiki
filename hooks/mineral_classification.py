"""Read the editable classification table and build mineral navigation.

Only exact normalized identities are used. The Markdown supplies every branch;
this module contains neither mineral assignments nor scientific inference.
"""

from __future__ import annotations

import html
import json
import logging
import re
import unicodedata
from pathlib import Path, PurePosixPath

from mkdocs.exceptions import ConfigurationError
from mkdocs.utils.meta import get_data

log = logging.getLogger("mkdocs.hooks.mineral_classification")
PATH_COLUMNS = ("clase", "subclase", "familia", "subgrupo")
REQUIRED_COLUMNS = ("mineral", "alias") + PATH_COLUMNS


def _plain(value):
    text = html.unescape(re.sub(r"<[^>]*>", "", str(value)))
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    return " ".join(text.replace("[[", "").replace("]]", "").replace(r"\|", "|").strip(" *_` ").split())


def _key(value):
    text = unicodedata.normalize("NFKD", _plain(value).casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[\s_\-–—]+", " ", text).strip()


def _outside_code(markdown):
    fence = None
    for number, line in enumerate(markdown.splitlines(), 1):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not marker.group(2).strip():
                fence = None
            continue
        if fence is None:
            yield number, line


def parse_catalog(markdown):
    """Return identity -> displayed branch tuple, rejecting conflicting rows."""
    catalog = {}
    columns = None
    canonical_paths = {}
    row_count = 0
    for number, line in _outside_code(markdown):
        if not line.lstrip().startswith("|"):
            columns = None
            continue
        row = line.strip()[1:]
        if row.endswith("|") and not row.endswith(r"\|"):
            row = row[:-1]
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", row)]
        headers = [_key(cell) for cell in cells]
        if all(column in headers for column in REQUIRED_COLUMNS):
            if len(headers) != len(set(headers)):
                raise ConfigurationError(f"Clasificacion mineral: columnas repetidas en la linea {number}.")
            columns = {name: headers.index(name) for name in REQUIRED_COLUMNS}
            continue
        if columns is None:
            continue
        if all(re.fullmatch(r"\s*:?-{3,}:?\s*", cell) for cell in cells):
            continue
        if len(cells) <= max(columns.values()):
            raise ConfigurationError(f"Clasificacion mineral: fila incompleta en la linea {number}.")
        mineral = _plain(cells[columns["mineral"]])
        labels = [_plain(cells[columns[name]]) for name in PATH_COLUMNS]
        if not mineral or labels[0] in {"", "-", "–", "—"}:
            raise ConfigurationError(f"Clasificacion mineral: Mineral y Clase son obligatorios (linea {number}).")
        path = tuple(label for label in labels if label not in {"", "-", "–", "—"})
        path_key = tuple(_key(label) for label in path)
        path = canonical_paths.setdefault(path_key, path)
        aliases = [mineral] + cells[columns["alias"]].split(";")
        for alias in aliases:
            identity = _key(alias)
            if not identity or identity in {"-", "–", "—"}:
                continue
            if identity in catalog and catalog[identity] != path:
                raise ConfigurationError(
                    f"Clasificacion mineral contradictoria para '{_plain(alias)}' (linea {number})."
                )
            catalog[identity] = path
        row_count += 1
    if not row_count:
        raise ConfigurationError(
            "No se encontro una tabla de clasificacion con las columnas Mineral, Alias, Clase, Subclase, Familia y Subgrupo."
        )
    return catalog


def load_aliases(path):
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise ConfigurationError(f"No se pueden leer las identidades de minerales: {path}: {error}") from error
    if not isinstance(raw, dict):
        raise ConfigurationError("Las identidades de minerales deben ser un objeto JSON.")
    aliases = {}
    for alias, names in raw.items():
        names = [names] if isinstance(names, str) else names
        if not isinstance(names, list) or not names or any(not isinstance(name, str) or not _key(name) for name in names):
            raise ConfigurationError(f"Identidad mineral no valida: {alias}")
        key = _key(alias)
        targets = tuple(_key(name) for name in names)
        if key in aliases and aliases[key] != targets:
            raise ConfigurationError(f"Identidad mineral contradictoria: {alias}")
        aliases[key] = targets
    return aliases


def _lookup(name, catalog, aliases):
    identity = _key(name)
    if identity in catalog:
        return True, catalog[identity]
    targets = aliases.get(identity)
    if targets is None:
        return False, None
    paths = [catalog.get(target) for target in targets]
    if any(path is None for path in paths) or len(set(paths)) != 1:
        return True, None
    return True, paths[0]


def resolve_sheet(path, content, catalog, aliases):
    """Resolve known identities, with no guessing from formula or tag values."""
    body, metadata = get_data(content)
    candidates = [PurePosixPath(path).stem]
    if isinstance(metadata.get("title"), str):
        candidates.append(metadata["title"])
    alternate = metadata.get("aliases") or []
    if isinstance(alternate, str):
        candidates.append(alternate)
    elif isinstance(alternate, list):
        candidates.extend(name for name in alternate if isinstance(name, str))
    for _, line in _outside_code(body):
        heading = re.match(r"^ {0,3}#\s+(.+?)\s*#*\s*$", line)
        if heading:
            candidates.append(heading.group(1))
            break

    routes = set()
    if "mineral_name_en" in metadata:
        explicit = metadata["mineral_name_en"]
        explicit = [explicit] if isinstance(explicit, str) else explicit
        if not isinstance(explicit, list) or not explicit or any(not isinstance(name, str) or not _key(name) for name in explicit):
            log.warning("Identidad mineral explicita invalida; queda Por clasificar: %s", path)
            return None
        for name in explicit:
            known, route = _lookup(name, catalog, aliases)
            if not known or route is None:
                log.warning("Identidad mineral explicita sin ruta unica; queda Por clasificar: %s", path)
                return None
            routes.add(route)

    for candidate in candidates:
        known, route = _lookup(candidate, catalog, aliases)
        if known:
            if route is None:
                log.warning("Identidad mineral incompleta o ambigua; queda Por clasificar: %s", path)
                return None
            routes.add(route)
    if len(routes) > 1:
        log.warning("Identidades minerales contradictorias; queda Por clasificar: %s", path)
        return None
    return next(iter(routes), None)


def load_reference(files, config, source):
    reference = files.get_file_from_path(source)
    if reference is None or not reference.is_documentation_page() or not reference.inclusion.is_in_nav():
        raise ConfigurationError(f"No se encuentra la tabla de clasificacion mineral: {source}")
    body, _ = get_data(reference.content_string)
    catalog = parse_catalog(body)
    extra = config.get("extra") or {}
    options = extra.get("mineral_abbreviations") or {}
    project = Path(config.config_file_path).parent
    configured_aliases = options.get("aliases")
    alias_path = project / (configured_aliases or "references/mineral-name-aliases.json")
    aliases = load_aliases(alias_path) if configured_aliases or alias_path.exists() else {}
    return catalog, aliases


def classified_navigation(paths, pages, catalog, aliases):
    """Build branches while keeping each original source path exactly once."""
    tree = {"pages": [], "children": {}}
    unknown = []
    for path in sorted(paths, key=lambda value: (_key(value), value)):
        branch = resolve_sheet(path, pages[path].content_string, catalog, aliases)
        if branch is None:
            unknown.append(path)
            continue
        node = tree
        for label in branch:
            node = node["children"].setdefault(label, {"pages": [], "children": {}})
        node["pages"].append(path)

    def render(node):
        result = sorted(node["pages"], key=lambda value: (_key(PurePosixPath(value).stem), value))
        for label in sorted(node["children"], key=lambda value: (_key(value), value)):
            result.append({label: render(node["children"][label])})
        return result

    result = render(tree)
    if unknown:
        result.append({"Por clasificar": unknown})
    return result
