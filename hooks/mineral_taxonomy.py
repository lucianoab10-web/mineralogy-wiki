"""Read an editable Markdown taxonomy and match Obsidian property tags."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import html
from pathlib import Path, PurePosixPath
import posixpath
import re
import unicodedata
from urllib.parse import quote

from mkdocs.exceptions import ConfigurationError
from mkdocs.utils.meta import get_data

INDEX_URI = "clasificacion-minerales.md"


def normalize_tag(value):
    return unicodedata.normalize("NFC", value.strip().lstrip("#")).casefold()


def property_tags(metadata):
    tags = metadata.get("tags") or []
    if isinstance(tags, str):
        tags = re.split(r"[\s,]+", tags)
    if not isinstance(tags, (list, tuple)):
        return set()
    return {normalize_tag(tag) for tag in tags if isinstance(tag, str) and tag.strip()}


@dataclass(eq=False)
class Group:
    name: str
    tags: tuple[str, ...]
    path: tuple[str, ...]
    line: int
    children: list[Group] = field(default_factory=list)

    @property
    def anchor(self):
        key = "\x00".join(self.path).encode("utf-8")
        return "grupo-" + hashlib.sha256(key).hexdigest()[:12]


@dataclass
class Taxonomy:
    roots: list[Group]
    source: str
    context_uri: str | None = None

    def paths(self):
        def visit(groups, ancestors):
            for group in groups:
                path = ancestors + (group,)
                yield path
                yield from visit(group.children, path)
        return list(visit(self.roots, ()))

    def classify(self, metadata):
        tags = property_tags(metadata)
        terminal_tags = {tag.rsplit("/", 1)[-1] for tag in tags}
        matches = [path for path in self.paths() if any(
            alias in tags or ("/" not in alias and alias in terminal_tags)
            for alias in path[-1].tags
        )]
        # A specific subgroup takes precedence over its tagged ancestors.
        return [path for path in matches if not any(
            len(other) > len(path) and other[:len(path)] == path for other in matches
        )]


def parse_taxonomy(markdown, source="Taxonomia_minerales.md"):
    body, _ = get_data(markdown)
    roots, stack, aliases, labels = [], [], {}, set()
    active = False
    fence = None
    for number, raw in enumerate(body.splitlines(), 1):
        marker = re.match(r"^\s*(`{3,}|~{3,})", raw)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence:
            continue
        heading = re.match(r"^##\s+(.+?)\s*#*\s*$", raw)
        if heading:
            title = "".join(c for c in unicodedata.normalize("NFKD", heading.group(1).casefold()) if not unicodedata.combining(c))
            if active:
                break
            active = title == "clasificacion"
            continue
        if not active:
            continue
        line = raw.expandtabs(4)
        item = re.match(r"^( *)(?:[-*+])\s+(.+?)\s*$", line)
        if not item:
            continue
        indent, text = len(item.group(1)), item.group(2)
        label, _, tag_text = text.partition(":")
        name = label.strip().strip("*` ")
        if not name:
            raise ConfigurationError(f"{source}:{number}: falta el nombre del grupo.")
        tags = tuple(dict.fromkeys(normalize_tag(tag) for tag in re.findall(r"#([\w][\w/-]*)", unicodedata.normalize("NFC", tag_text))))
        if tag_text and not tags:
            raise ConfigurationError(f"{source}:{number}: escribe etiquetas con # después de los dos puntos.")
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack and indent:
            raise ConfigurationError(f"{source}:{number}: un grupo principal debe comenzar sin sangría.")
        if len(stack) >= 12:
            raise ConfigurationError(f"{source}:{number}: demasiados niveles de clasificación.")
        path = (stack[-1][1].path if stack else ()) + (name,)
        if path in labels:
            raise ConfigurationError(f"{source}:{number}: grupo repetido: {' / '.join(path)}.")
        labels.add(path)
        for tag in tags:
            if tag in aliases:
                raise ConfigurationError(f"{source}:{number}: #{tag} ya pertenece a «{aliases[tag]}».")
            aliases[tag] = name
        group = Group(name, tags, path, number)
        (stack[-1][1].children if stack else roots).append(group)
        stack.append((indent, group))
    taxonomy = Taxonomy(roots, source)
    if not roots:
        raise ConfigurationError(f"{source}: añade una lista de grupos bajo el encabezado «## Clasificación».")
    for path in taxonomy.paths():
        if not path[-1].children and not path[-1].tags:
            raise ConfigurationError(f"{source}:{path[-1].line}: el último nivel necesita al menos una etiqueta, por ejemplo #filosilicato.")
    return taxonomy


def load_taxonomy(config, files, context_uri):
    path = PurePosixPath(context_uri)
    if path.is_absolute() or ".." in path.parts or path.suffix.casefold() != ".md":
        raise ConfigurationError("mineral_navigation.taxonomy_file debe ser una ruta Markdown relativa a docs.")
    context = files.get_file_from_path(context_uri)
    if context is not None:
        taxonomy = parse_taxonomy(context.content_string, context_uri)
        taxonomy.context_uri = context_uri
        return taxonomy
    fallback = Path(config.config_file_path).parent / "taxonomy" / path.name
    if not fallback.is_file():
        raise ConfigurationError(f"No se encontró la taxonomía {context_uri} ni {fallback}.")
    return parse_taxonomy(fallback.read_text(encoding="utf-8"), str(fallback))


def sidebar(taxonomy, classifications, paths, sort_key):
    direct, unclassified, ambiguous = {}, [], []
    for uri in sorted(paths, key=sort_key):
        matches = classifications[uri]
        if not matches:
            unclassified.append(uri)
        elif len(matches) > 1:
            ambiguous.append(uri)
        else:
            direct.setdefault(matches[0][-1], []).append(uri)

    def render(group):
        children = [entry for child in group.children for entry in render(child)]
        children += direct.get(group, [])
        return [{group.name: children}] if children else []

    result = [{"Clasificación": INDEX_URI}]
    result += [entry for root in taxonomy.roots for entry in render(root)]
    if unclassified:
        result.append({"Sin clasificar": unclassified})
    if ambiguous:
        result.append({"Por revisar": ambiguous})
    return result


def _md_label(text):
    return re.sub(r"([\\\[\]<>*_`])", r"\\\1", text)


def index_markdown(taxonomy, classifications, sort_key):
    lines = ["# Clasificación de minerales", "", "Explora las fichas por grupo y subgrupo mineralógico.", ""]
    direct = {}
    unclassified, ambiguous = [], []
    for uri in sorted(classifications, key=sort_key):
        matches = classifications[uri]
        if not matches:
            unclassified.append(uri)
        elif len(matches) > 1:
            ambiguous.append(uri)
        else:
            direct.setdefault(matches[0][-1], []).append(uri)

    def sheet_link(uri):
        return f"- [{_md_label(PurePosixPath(uri).stem)}](<{quote(uri, safe='/')}>)"

    for path in taxonomy.paths():
        node = path[-1]
        count = sum(len(uris) for group, uris in direct.items() if group.path[:len(node.path)] == node.path)
        lines += [f'<a id="{node.anchor}"></a>', "", f"{'#' * min(6, len(path) + 1)} {_md_label(node.name)} ({count})", ""]
        lines += [sheet_link(uri) for uri in direct.get(node, [])]
        if not count:
            lines.append("Todavía no hay fichas clasificadas en este grupo.")
        lines.append("")
    for anchor, title, uris in (("sin-clasificar", "Sin clasificar", unclassified), ("por-revisar", "Clasificación por revisar", ambiguous)):
        lines += [f'<a id="{anchor}"></a>', "", f"## {title} ({len(uris)})", ""]
        lines += [sheet_link(uri) for uri in uris] or ["No hay fichas en esta sección."]
        lines.append("")
    return "\n".join(lines)


def classification_html(matches, page, files):
    target = files.get_file_from_path(INDEX_URI)
    start = page.url if not page.url or page.url.endswith("/") else posixpath.dirname(page.url)
    url = quote(posixpath.relpath(target.url, start or "."), safe="/%")
    if not matches:
        links = f'<a href="{url}#sin-clasificar">Sin clasificar</a>'
    else:
        paths = []
        for path in matches:
            paths.append('<span class="mineral-classification__path">' + '<span aria-hidden="true"> › </span>'.join(
                f'<a href="{url}#{node.anchor}">{html.escape(node.name)}</a>' for node in path
            ) + '</span>')
        links = '<span class="mineral-classification__separator"> · </span>'.join(paths)
        if len(matches) > 1:
            links += f' <a href="{url}#por-revisar">Clasificación por revisar</a>'
    return '<div class="mineral-classification" role="navigation" aria-label="Clasificación mineralógica"><span class="mineral-classification__label">Clasificación:</span> ' + links + '</div>\n'
