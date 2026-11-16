from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

from mkdocs.commands.build import build
from mkdocs.config import load_config
from mkdocs.exceptions import ConfigurationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hooks"))
from mineral_taxonomy import parse_taxonomy, property_tags

TREE = """# Taxonomía
## Clasificación
- Óxidos: #oxido, #óxido
- Silicatos: #silicato, #silicatos
  - Filosilicatos: #filosilicato, #filosilicatos
  - Inosilicatos: #inosilicato
## Ejemplos
- Esto no se debe leer: #otro
"""


class TagMatchingTests(unittest.TestCase):
    def setUp(self):
        self.tree = parse_taxonomy(TREE)

    def names(self, tags):
        return [[node.name for node in path] for path in self.tree.classify({"tags": tags})]

    def test_terminal_tag_matches_and_specific_subgroup_wins(self):
        self.assertEqual(self.names(["minerales", "silicatos", "minerales/silicatos/filosilicatos"]), [["Silicatos", "Filosilicatos"]])
        self.assertEqual(self.names(["#FILOSILICATO"]), [["Silicatos", "Filosilicatos"]])

    def test_exact_full_paths_and_unrelated_tags(self):
        tree = parse_taxonomy("## Clasificación\n- Silicatos\n  - Hojas: #grupo/filosilicato\n")
        self.assertFalse(tree.classify({"tags": ["filosilicato"]}))
        self.assertTrue(tree.classify({"tags": ["grupo/filosilicato"]}))
        self.assertFalse(self.names(["resuelto", "metamorficos-lista", "filosilicatos-extra"]))
        self.assertFalse(self.names(["filosilicato/no-es-la-hoja"]))

    def test_explicit_aliases_case_unicode_and_string_properties(self):
        self.assertEqual(self.names(["O\u0301XIDO"]), [["Óxidos"]])
        self.assertEqual(self.names("minerales, #filosilicato"), [["Silicatos", "Filosilicatos"]])
        self.assertEqual(property_tags({"tags": None}), set())

    def test_conflicting_leaves_are_preserved_for_review(self):
        self.assertEqual(self.names(["oxido", "filosilicato"]), [["Óxidos"], ["Silicatos", "Filosilicatos"]])

    def test_deep_tree_and_markdown_example_fences(self):
        tree = parse_taxonomy("## Clasificación\n- Silicatos\n  - Inosilicatos\n    - Cadenas dobles: #cadena-doble\n\n```md\n- No cuenta: #otro\n```\n")
        matches = tree.classify({"tags": ["cadena-doble"]})
        self.assertEqual([n.name for n in matches[0]], ["Silicatos", "Inosilicatos", "Cadenas dobles"])
        self.assertFalse(tree.classify({"tags": ["otro"]}))

    def test_invalid_taxonomies_fail_with_actionable_errors(self):
        for text in ["## Clasificación\n- Silicatos\n", "## Clasificación\n- A: #uno\n- B: #uno\n", "# Sin sección\n- A: #uno\n"]:
            with self.subTest(text=text), self.assertRaises(ConfigurationError):
                parse_taxonomy(text)


class BuildIntegrationTests(unittest.TestCase):
    def test_vault_context_controls_sidebar_classification_and_preserves_uploads_and_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "hooks").mkdir()
            (root / "taxonomy").mkdir()
            for name in ("mineral_navigation.py", "mineral_taxonomy.py", "mineral_contributions.py"):
                shutil.copy(ROOT / "hooks" / name, root / "hooks" / name)
            (root / "taxonomy/Taxonomia_minerales.md").write_text(TREE)
            (root / "docs/Taxonomia_minerales.md").write_text(TREE.replace("Filosilicatos:", "Hojas:"))
            talc = "---\ntags: [minerales, silicatos, minerales/silicatos/filosilicatos]\n---\n\n| imagen | nota |\n| --- | --- |\n| ![Talc](https://example.org/talc.jpg) | Nota original |\n"
            (root / "docs/Talco.md").write_text(talc)
            (root / "docs/Magnetita.md").write_text("---\ntags: [minerales, oxido]\n---\nContenido")
            (root / "docs/SinGrupo.md").write_text("---\ntags: [minerales]\n---\nContenido")
            (root / "docs/Revisar.md").write_text("---\ntags: [minerales, oxido, filosilicato]\n---\nContenido")
            (root / "docs/General.md").write_text("---\ntags: [filosilicato]\n---\nUna nota temática general.")
            (root / "docs/Pendiente.md").write_text("Contenido pendiente.")
            (root / "mkdocs.yml").write_text("""site_name: Prueba
site_url: https://example.org/wiki/
theme:
  name: material
markdown_extensions: [tables]
hooks:
  - hooks/mineral_navigation.py
  - hooks/mineral_contributions.py
extra:
  mineral_navigation:
    title: Fichas de minerales
    taxonomy_file: Taxonomia_minerales.md
    pending: [Pendiente.md]
  photo_contributions:
    api_url: https://photos.example.org
""")
            config = load_config(config_file=str(root / "mkdocs.yml"))
            build(config)
            navigation = config["nav"][0]["Fichas de minerales"]
            self.assertIn({"Silicatos": [{"Hojas": ["Talco.md"]}]}, navigation)
            self.assertIn({"Óxidos": ["Magnetita.md"]}, navigation)
            self.assertIn({"Sin clasificar": ["SinGrupo.md"]}, navigation)
            self.assertIn({"Por revisar": ["Revisar.md"]}, navigation)
            self.assertIn({"Por completar": ["Pendiente.md"]}, navigation)
            rendered = (root / "site/Talco/index.html").read_text()
            self.assertIn('aria-label="Clasificación mineralógica"', rendered)
            self.assertIn('data-mineral-id="Talco.md"', rendered)
            self.assertIn("Nota original", rendered)
            self.assertIn("Hojas", rendered)
            self.assertIn("../clasificacion-minerales/#grupo-", rendered)
            self.assertEqual((root / "docs/Talco.md").read_text(), talc)
            overview = (root / "site/clasificacion-minerales/index.html").read_text()
            self.assertIn("Hojas (1)", overview)
            self.assertIn("../Talco/", overview)
            catalogue = json.loads((root / "site/assets/mineral-wiki/contribution-catalog.json").read_text())
            ids = {item["id"] for item in catalogue["minerals"]}
            self.assertEqual(ids, {"Talco.md", "Magnetita.md", "SinGrupo.md", "Revisar.md", "Pendiente.md"})
            general = (root / "site/General/index.html").read_text()
            self.assertNotIn('aria-label="Clasificación mineralógica"', general)


if __name__ == "__main__":
    unittest.main()
