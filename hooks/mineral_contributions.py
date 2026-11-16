"""Add community photos to each mineral's image/note table without editing the vault."""
from __future__ import annotations

import html
import importlib.util
import json
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlsplit

from mkdocs.structure.files import File

_pages: dict[str, str] = {}


def on_files(files, config, **kwargs):
    _pages.clear()
    options = (config.get("extra") or {}).get("photo_contributions") or {}
    api = str(options.get("api_url") or "").rstrip("/")
    if not api:
        return files
    if urlsplit(api).scheme != "https" or urlsplit(api).path not in ("", "/"):
        raise ValueError("photo_contributions.api_url debe ser un origen HTTPS, sin ruta.")
    project = Path(config.config_file_path).parent
    spec = importlib.util.spec_from_file_location("mineral_contribution_detection", project / "hooks/mineral_navigation.py")
    navigation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(navigation)
    nav_options = (config.get("extra") or {}).get("mineral_navigation") or {}
    included = set(nav_options.get("include") or []) | set(nav_options.get("pending") or [])
    excluded = set(nav_options.get("references") or []) | set(nav_options.get("templates") or [])
    minerals = []
    for file in list(files):
        if not file.is_documentation_page() or not file.inclusion.is_in_nav() or file.src_uri in excluded:
            continue
        if file.src_uri not in included and not navigation._is_mineral_sheet(file.content_string):
            continue
        name = PurePosixPath(file.src_uri).stem
        _pages[file.src_uri] = name
        minerals.append({"id": file.src_uri, "name": name, "url": urljoin(config.site_url, file.url)})
    minerals.sort(key=lambda item: item["name"].casefold())
    uri = "assets/mineral-wiki/contribution-catalog.json"
    if files.get_file_from_path(uri) is not None:
        raise ValueError(f"El catálogo generado ya existe en docs: {uri}")
    files.append(File.generated(config, uri, content=json.dumps({"minerals": minerals}, ensure_ascii=False)))
    return files


def on_page_content(html_content, page, config, **kwargs):
    name = _pages.get(page.file.src_uri)
    if name is None:
        return html_content
    options = (config.get("extra") or {}).get("photo_contributions") or {}
    api = str(options.get("api_url") or "").rstrip("/")
    marker = (
        '<div class="mineral-contributions"'
        f' data-mineral-id="{html.escape(page.file.src_uri, quote=True)}"'
        f' data-mineral-name="{html.escape(name, quote=True)}"'
        f' data-api="{html.escape(api, quote=True)}">'
        '<noscript>Activa JavaScript para ver las fotografías de la comunidad y enviar una fotografía.</noscript>'
        '</div>'
    )
    return html_content + "\n" + marker
