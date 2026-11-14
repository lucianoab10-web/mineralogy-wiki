"""Publicar recursos web sin guardarlos en docs, que el espejo de Obsidian regenera."""
from pathlib import Path

from mkdocs.structure.files import File


def on_files(files, config, **kwargs):
    source = Path(config.config_file_path).parent / "site-assets"
    for name in ("mathjax.js", "mobile-tables.js", "mobile-tables.css"):
        uri = f"assets/mineral-wiki/{name}"
        if files.get_file_from_path(uri) is not None:
            raise ValueError(f"La ruta de recursos web ya existe en docs: {uri}")
        files.append(File.generated(config, uri, abs_src_path=str(source / name)))
    return files
