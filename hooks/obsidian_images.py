"""
Hook de MkDocs: hace visibles en la wiki web las imágenes de las notas de Obsidian.

El problema
-----------
Las notas insertan imágenes como ![[Pasted image 2026….jpg]] o ![](Pasted image 2026….jpg). Esos archivos viven
en el vault (fuera de `docs_dir`), así que MkDocs no los copia al sitio: el navegador muestra el ícono de
imagen rota con el nombre del archivo como texto alternativo. Además, MkDocs no entiende la sintaxis ![[…]].

Qué hace
--------
Antes de cada build indexa por nombre las imágenes de las carpetas configuradas. En cada página reescribe las
referencias (![[…]], ![](…) y <img src="…">): si la imagen no existe donde se la menciona, la busca por nombre
(sin distinguir mayúsculas), la copia al sitio en assets/obsidian-images/ y apunta la referencia ahí.
No modifica tus notas ni tu repositorio, y no copia imágenes que no se usen. Al final del build deja un resumen
en el registro, con la lista de imágenes que no pudo encontrar.

Instalación (mkdocs.yml)
------------------------
    hooks:
      - hooks/obsidian_images.py

    extra:
      image_dirs:        # opcional: dónde buscar, además de docs_dir y de la carpeta del proyecto
        - C:/Users/Luciano/iCloudDrive/iCloud~md~obsidian/my-notes

También se puede usar la variable de entorno MKDOCS_IMAGE_DIRS (rutas separadas por «;»).
Requiere MkDocs 1.5 o superior (Material 9.5+ ya lo exige).
"""

from __future__ import annotations

import logging
import os
import posixpath
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import quote, unquote

from mkdocs.structure.files import File

log = logging.getLogger("mkdocs.hooks.obsidian_images")

IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".avif"}
SKIP_DIRS = {"node_modules", "site", "__pycache__", "venv", "env"}  # además de toda carpeta que empiece con "."
DEST_DIR = "assets/obsidian-images"

# Estado de un build (se reinicia en on_pre_build).
_index: dict[str, list[Path]] = {}  # nombre en minúsculas -> archivos con ese nombre
_roots: list[Path] = []
_dest_of: dict[str, str] = {}  # archivo origen -> src_uri en el sitio
_taken: dict[str, str] = {}  # src_uri (minúsculas) -> archivo origen (evita colisiones de nombre)
_missing: dict[str, set[str]] = {}  # nombre buscado -> páginas que lo mencionan
_failed: dict[str, str] = {}  # archivo que no se pudo leer -> motivo
_cache: Path | None = None  # carpeta temporal desde donde MkDocs copia las imágenes
_copied = 0

# ![[archivo.png]]  /  ![[archivo.png|300]]  /  ![[archivo.png|alt|300x200]]  (en tablas el «|» viene escapado: \|)
_EMBED = re.compile(r"!\[\[([^\]\n]+?)\]\]")
# ![alt](ruta)  /  ![alt](ruta con espacios.jpg)  /  ![alt](<ruta>)  /  ![alt](ruta "título")
_MDIMG = re.compile(r"!\[([^\]\n]*)\]\(\s*(<[^>\n]+>|[^()\n]*?)\s*(?:\"[^\"\n]*\"\s*)?\)")
# <img ... src="ruta" ...>
_HTMLIMG = re.compile(r"(<img\b[^>]*?\bsrc\s*=\s*)([\"'])(.*?)\2", re.IGNORECASE | re.DOTALL)
# bloques de código: no se tocan
_FENCE = re.compile(r"^(`{3,}|~{3,})[^\n]*\n.*?^\1[ \t]*$", re.MULTILINE | re.DOTALL)
_SIZE = re.compile(r"^(\d+)(?:x(\d+))?$")
_REMOTE = re.compile(r"^(?:[a-z][a-z0-9+.\-]*:|//)", re.IGNORECASE)


# ───────────────────────── Eventos de MkDocs ─────────────────────────


def on_pre_build(config, **kwargs):
    global _index, _roots, _copied, _cache
    _dest_of.clear()
    _taken.clear()
    _missing.clear()
    _failed.clear()
    _cache = None
    _copied = 0
    _roots = _search_roots(config)
    _index = _build_index(_roots, Path(config.site_dir))
    total = sum(len(v) for v in _index.values())
    log.info("obsidian_images: %d imágenes indexadas en %d carpeta(s): %s", total, len(_roots), "; ".join(map(str, _roots)))


def on_page_markdown(markdown, page, config, files, **kwargs):
    if not _index:
        return markdown
    parts: list[str] = []
    last = 0
    for fence in _FENCE.finditer(markdown):  # el texto entre bloques de código sí se procesa
        parts.append(_rewrite(markdown[last : fence.start()], page, config, files))
        parts.append(fence.group(0))
        last = fence.end()
    parts.append(_rewrite(markdown[last:], page, config, files))
    return "".join(parts)


def on_post_build(config, **kwargs):
    global _cache
    if _cache is not None:  # MkDocs ya copió las imágenes al sitio
        shutil.rmtree(_cache, ignore_errors=True)
        _cache = None
    log.info("obsidian_images: %d imagen(es) copiada(s) al sitio (%s/)", _copied, DEST_DIR)
    for src, why in sorted(_failed.items()):
        log.warning("obsidian_images: no se pudo leer «%s» (%s); queda sin cambios en las páginas.", src, why)
    if _missing:
        log.warning("obsidian_images: %d imagen(es) NO encontrada(s) en ninguna carpeta:", len(_missing))
        for name, pages in sorted(_missing.items()):
            log.warning("    · %s   (en: %s)", name, ", ".join(sorted(pages)))
        log.warning("    Carpetas revisadas: %s", "; ".join(map(str, _roots)))
        log.warning("    Si la imagen existe en otra carpeta, agrégala en extra.image_dirs de mkdocs.yml.")


# ───────────────────────── Búsqueda de archivos ─────────────────────────


def _search_roots(config) -> list[Path]:
    project = Path(config.config_file_path).resolve().parent
    candidates: list[tuple[Path, bool]] = [(Path(config.docs_dir), True), (project, True)]
    extra = (config.get("extra") or {}).get("image_dirs") or []
    if isinstance(extra, str):
        extra = [extra]
    candidates += [(Path(os.path.expandvars(os.path.expanduser(str(p)))), False) for p in extra]
    env = os.environ.get("MKDOCS_IMAGE_DIRS", "")
    candidates += [(Path(os.path.expanduser(p.strip())), False) for p in env.split(";") if p.strip()]

    roots: list[Path] = []
    for path, silent in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if not resolved.is_dir():
            if not silent:
                log.warning("obsidian_images: la carpeta de imágenes «%s» no existe; se ignora.", path)
            continue
        if resolved not in roots:
            roots.append(resolved)
    return roots


def _build_index(roots: list[Path], site_dir: Path) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    seen: set[Path] = set()
    try:
        site = site_dir.resolve()
    except OSError:
        site = site_dir
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            here = Path(dirpath)
            dirnames[:] = [
                d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS and (here / d).resolve() != site
            ]
            for name in filenames:
                if os.path.splitext(name)[1].lower() in IMG_EXTS:
                    p = here / name
                    if p not in seen:
                        seen.add(p)
                        index.setdefault(name.lower(), []).append(p)
    return index


def _register(src: Path, files, config) -> str | None:
    """Añade la imagen al sitio (la copia MkDocs al final del build) y devuelve su src_uri.

    Primero la copia a una carpeta temporal: si el archivo no se puede leer (p. ej. un archivo de iCloud que
    aún no se descargó), se avisa y se sigue; una sola imagen defectuosa no debe romper el deploy completo.
    """
    global _copied, _cache
    key = str(src)
    if key in _dest_of:
        return _dest_of[key]
    if key in _failed:
        return None
    name = re.sub(r"\s+", "-", src.name)  # sin espacios: URLs más limpias
    stem, ext = os.path.splitext(name)
    uri, n = f"{DEST_DIR}/{name}", 1
    while uri.lower() in _taken and _taken[uri.lower()] != key:  # mismo nombre en otra carpeta
        n += 1
        uri = f"{DEST_DIR}/{stem}-{n}{ext}"
    if _cache is None:
        _cache = Path(tempfile.mkdtemp(prefix="mkdocs-obsidian-images-"))
    staged = _cache / uri
    try:
        staged.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, staged)
    except OSError as e:
        _failed[key] = str(e)
        return None
    _taken[uri.lower()] = key
    _dest_of[key] = uri
    files.append(File.generated(config, uri, abs_src_path=str(staged)))
    _copied += 1
    return uri


# ───────────────────────── Reescritura de referencias ─────────────────────────


def _locate(target: str, page, config, files) -> str | None:
    """Devuelve el src_uri (relativo a docs_dir) de la imagen que se menciona, o None si no hay que tocarla."""
    clean = unquote(target.strip().strip("<>")).split("#")[0].split("?")[0].strip()
    if not clean or _REMOTE.match(clean):
        return None
    name = posixpath.basename(clean.replace("\\", "/"))
    if os.path.splitext(name)[1].lower() not in IMG_EXTS:
        return None

    # 1) ¿Ya existe como archivo del sitio? (relativa a la página, o a la raíz de docs)
    page_dir = posixpath.dirname(page.file.src_uri)
    clean = clean.replace("\\", "/")
    for cand in (posixpath.join(page_dir, clean), clean.lstrip("/")):
        cand = posixpath.normpath(cand).lstrip("/")
        found = files.get_file_from_path(cand)
        if found is not None and not found.is_documentation_page():
            return cand

    # 2) Buscarla por nombre en las carpetas configuradas.
    hits = _index.get(name.lower())
    if not hits:
        _missing.setdefault(name, set()).add(page.file.src_uri)
        return None
    if len(hits) > 1:
        log.info("obsidian_images: «%s» existe en %d carpetas; se usa %s", name, len(hits), hits[0])
    return _register(hits[0], files, config)


def _source_relative(uri: str, page) -> str:
    """Ruta relativa a la carpeta del .md de origen (MkDocs la traduce a la URL final)."""
    return quote(posixpath.relpath(uri, posixpath.dirname(page.file.src_uri) or "."), safe="/")


def _site_relative(uri: str, page, files) -> str:
    """URL relativa a la página ya generada (para <img> en HTML, que MkDocs no procesa)."""
    target = files.get_file_from_path(uri)
    url = target.url if target is not None else uri
    start = page.url if (not page.url or page.url.endswith("/")) else posixpath.dirname(page.url)
    return quote(posixpath.relpath(url, start or "."), safe="/")


def _rewrite(text: str, page, config, files) -> str:
    use_attr_list = "attr_list" in {str(e).split(".")[-1] for e in config.markdown_extensions}

    def embed(m: re.Match) -> str:
        parts = [p.strip() for p in re.split(r"\\?\|", m.group(1))]
        uri = _locate(parts[0].split("#")[0].split("^")[0], page, config, files)
        if uri is None:
            return m.group(0)
        size = next((_SIZE.match(p) for p in parts[1:] if _SIZE.match(p)), None)
        alt = next((p for p in parts[1:] if p and not _SIZE.match(p)), os.path.splitext(posixpath.basename(parts[0]))[0])
        attrs = ""
        if size and use_attr_list:
            attrs = "{ width=%s%s }" % (size.group(1), f" height={size.group(2)}" if size.group(2) else "")
        return f"![{alt}]({_source_relative(uri, page)}){attrs}"

    def mdimage(m: re.Match) -> str:
        uri = _locate(m.group(2), page, config, files)
        if uri is None:
            return m.group(0)
        return f"![{m.group(1)}]({_source_relative(uri, page)})"

    def htmlimage(m: re.Match) -> str:
        uri = _locate(m.group(3), page, config, files)
        if uri is None:
            return m.group(0)
        return f"{m.group(1)}{m.group(2)}{_site_relative(uri, page, files)}{m.group(2)}"

    text = _EMBED.sub(embed, text)
    text = _MDIMG.sub(mdimage, text)
    return _HTMLIMG.sub(htmlimage, text)
