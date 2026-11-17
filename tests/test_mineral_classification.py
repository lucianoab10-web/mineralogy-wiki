import importlib.util
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml
from mkdocs.commands.build import build
from mkdocs.config import load_config
from mkdocs.exceptions import ConfigurationError

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "clasificacion minerales.md"


def load_hook(name):
    spec = importlib.util.spec_from_file_location("taxonomy_test_" + name, ROOT / "hooks" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


classifier = load_hook("mineral_classification")
navigation = load_hook("mineral_navigation")
HEADERS = ["Mineral", "Alias", "Clase", "Subclase", "Familia", "Subgrupo", "Tipo", "Nota", "Fuentes"]
ROWS = [
    ["plagioclase", "Plagioclasa", "Silicatos", "Tectosilicatos", "Feldespatos", "Plagioclasas", "Serie", "", ""],
    ["albite", "Albita", "Silicatos", "Tectosilicatos", "Feldespatos", "Plagioclasas", "Especie", "", ""],
    ["anorthite", "Anortita", "Silicatos", "Tectosilicatos", "Feldespatos", "Plagioclasas", "Especie", "", ""],
    ["microcline", "Microclina; Microclina Mc", "Silicatos", "Tectosilicatos", "Feldespatos", "Alcalinos", "Especie", "", ""],
    ["talc", "Talco", "Silicatos", "Filosilicatos", "", "", "Especie", "", ""],
    ["magnetite", "Magnetita", "Óxidos e hidróxidos", "Óxidos", "Espinelas", "", "Especie", "", ""],
    ["borax", "Bórax", "Boratos", "", "", "", "Especie", "", ""],
    ["tennantite", "Tennantita", "Sulfuros y sulfosales", "Sulfosales", "Grupo de la tetraedrita", "", "Serie", "", ""],
    ["tetrahedrite", "Tetraedrita", "Sulfuros y sulfosales", "Sulfosales", "Grupo de la tetraedrita", "", "Serie", "", ""],
]


def table(rows=ROWS, headers=HEADERS):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] + ["| " + " | ".join(row) + " |" for row in rows])


class File:
    def __init__(self, path, content):
        self.src_uri = path
        self.content_string = content
        self.inclusion = SimpleNamespace(is_in_nav=lambda: True)

    def is_documentation_page(self):
        return self.src_uri.endswith(".md")


class Files(list):
    def get_file_from_path(self, path):
        return next((file for file in self if file.src_uri == path), None)


class Config(dict):
    pass


def leaves(tree):
    result = []
    if isinstance(tree, str):
        result.append(tree)
    elif isinstance(tree, dict):
        for item in tree.values():
            result.extend(leaves(item))
    else:
        for item in tree:
            result.extend(leaves(item))
    return result


class MineralClassification(unittest.TestCase):
    def setUp(self):
        self.catalog = classifier.parse_catalog(table())
        self.aliases = {"tenantina tetrahidrita": ("tennantite", "tetrahedrite")}

    def route(self, name, content="", aliases=None, catalog=None):
        return classifier.resolve_sheet(name, content, catalog or self.catalog, aliases or self.aliases)

    def test_plagioclase_has_four_real_branches_and_preserves_species_endmembers(self):
        expected = ("Silicatos", "Tectosilicatos", "Feldespatos", "Plagioclasas")
        for name in ["Plagioclasa.md", "Albita.md", "Anortita.md", "nested/PLAGIOCLASA.md"]:
            with self.subTest(name=name):
                self.assertEqual(self.route(name), expected)

    def test_table_can_be_reordered_padded_and_contains_human_only_columns(self):
        indices = [6, 8, 3, 1, 0, 7, 5, 2, 4]
        reordered = table([[row[index] for index in indices] for row in ROWS], [HEADERS[index] for index in indices])
        padded = "\n".join("|" + "|".join(cell.ljust(28) for cell in line.strip("|").split("|")) + "|" for line in reordered.splitlines())
        self.assertEqual(classifier.parse_catalog(reordered), self.catalog)
        self.assertEqual(classifier.parse_catalog(padded), self.catalog)

    def test_compact_rows_keep_empty_trailing_columns(self):
        compact = "\n".join("|" + "|".join(cell.strip() for cell in line.strip()[1:-1].split("|")) + "|" for line in table().splitlines())
        self.assertEqual(classifier.parse_catalog(compact), self.catalog)

    def test_source_table_edits_change_the_route_without_a_code_change(self):
        changed = table().replace("| Filosilicatos |", "| Nueva rama editable |")
        self.assertEqual(self.route("Talco.md", catalog=classifier.parse_catalog(changed)), ("Silicatos", "Nueva rama editable"))
        self.assertEqual(self.route("Talco.md"), ("Silicatos", "Filosilicatos"))

    def test_future_borate_sheet_uses_the_markdown_row(self):
        self.assertEqual(self.route("Bórax.md"), ("Boratos",))

    def test_empty_levels_and_dash_placeholders_do_not_create_fake_branches(self):
        rows = [["halite", "Halita", "Halogenuros", "-", "—", "", "Especie", "", ""]]
        self.assertEqual(self.route("Halita.md", catalog=classifier.parse_catalog(table(rows))), ("Halogenuros",))

    def test_table_fences_and_other_unrelated_tables_do_not_assign_anything(self):
        fake = table([["talc", "Talco", "Clase incorrecta", "", "", "", "", "", ""]])
        source = "~~~markdown\n" + fake + "\n~~~\n\n| Mineral | Otra columna |\n| --- | --- |\n| talc | falso |\n\n" + table()
        self.assertEqual(classifier.parse_catalog(source), self.catalog)
        with self.assertRaises(ConfigurationError):
            classifier.parse_catalog("```markdown\n" + table() + "\n```\n")

    def test_fence_text_is_not_a_closing_fence(self):
        fake = "```md\n```not-a-close\n" + table() + "\n```\n"
        with self.assertRaises(ConfigurationError):
            classifier.parse_catalog(fake)

    def test_contradictory_aliases_and_canonical_identities_are_configuration_errors(self):
        conflicts = [
            ROWS + [["other", "Talco", "Otra clase", "", "", "", "", "", ""]],
            ROWS + [["talc", "", "Otra clase", "", "", "", "", "", ""]],
        ]
        for rows in conflicts:
            with self.subTest(rows=rows[-1]), self.assertRaises(ConfigurationError):
                classifier.parse_catalog(table(rows))

    def test_a_repeated_alias_for_the_same_route_is_not_ambiguous(self):
        rows = ROWS + [["plagioclase duplicate", "PLAGIOCLASA", "silicatos", "tectosilicatos", "feldespatos", "plagioclasas", "", "", ""]]
        self.assertEqual(self.route("Plagioclasa.md", catalog=classifier.parse_catalog(table(rows))), self.route("Plagioclasa.md"))

    def test_empty_class_and_missing_table_are_errors(self):
        for source in ["", "# Solo un texto\n", table([["unknown", "", "", "", "", "", "", "", ""]])]:
            with self.subTest(source=source), self.assertRaises(ConfigurationError):
                classifier.parse_catalog(source)

    def test_no_formula_tag_substring_or_unverified_suffix_inference(self):
        content = "---\ntags: [minerales, sulfuros]\n---\nCuFeS2"
        for name in ["Calcopitia.md", "Nueva muestra.md", "Talco desconocido.md", "Talco Tlc.md", "Magnetismo.md"]:
            with self.subTest(name=name):
                self.assertIsNone(self.route(name, content))
        self.assertEqual(self.route("Microclina Mc.md"), self.route("Microclina.md"), "An explicitly listed suffix is allowed")

    def test_exact_title_aliases_and_first_h1_outside_code_are_supported(self):
        contents = [
            "---\ntitle: Talco\n---\n",
            "---\naliases: [Talco, talc]\n---\n",
            "~~~md\n# Magnetita\n~~~\n# Talco\n",
        ]
        for content in contents:
            with self.subTest(content=content):
                self.assertEqual(self.route("Muestra.md", content), self.route("Talco.md"))

    def test_conflicting_known_filename_title_alias_or_h1_remains_unclassified(self):
        for content in ["---\ntitle: Magnetita\n---\n", "---\naliases: [Magnetita]\n---\n", "# Magnetita\n"]:
            with self.subTest(content=content), self.assertLogs(classifier.log, level="WARNING"):
                self.assertIsNone(self.route("Talco.md", content))

    def test_explicit_names_require_every_identity_and_cannot_hide_a_known_conflict(self):
        self.assertEqual(self.route("Muestra.md", "---\nmineral_name_en: [albite, anorthite]\n---\n"), self.route("Plagioclasa.md"))
        for name, explicit in [("Talco.md", "magnetite"), ("Muestra.md", "[talc, unknown]"), ("Muestra.md", "[talc, magnetite]"), ("Muestra.md", "[]")]:
            with self.subTest(name=name, explicit=explicit), self.assertLogs(classifier.log, level="WARNING"):
                self.assertIsNone(self.route(name, "---\nmineral_name_en: " + explicit + "\n---\n"))

    def test_combined_alias_requires_every_member_and_the_same_complete_route(self):
        self.assertEqual(self.route("Tenantina - Tetrahidrita.md"), self.route("Tennantita.md"))
        changed = classifier.parse_catalog(table([row for row in ROWS if row[0] != "tetrahedrite"]))
        with self.assertLogs(classifier.log, level="WARNING"):
            self.assertIsNone(self.route("Tenantina - Tetrahidrita.md", catalog=changed))
        changed = classifier.parse_catalog(table([row[:3] + ["Otra rama"] + row[4:] if row[0] == "tetrahedrite" else row for row in ROWS]))
        with self.assertLogs(classifier.log, level="WARNING"):
            self.assertIsNone(self.route("Tenantina - Tetrahidrita.md", catalog=changed))

    def test_json_aliases_only_identify_existing_catalog_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "aliases.json"
            source.write_text(json.dumps({"Mi muestra": "talc", "Inexistente": "not in catalog"}), encoding="utf-8")
            aliases = classifier.load_aliases(source)
            self.assertEqual(self.route("Mi muestra.md", aliases=aliases), self.route("Talco.md"))
            with self.assertLogs(classifier.log, level="WARNING"):
                self.assertIsNone(self.route("Inexistente.md", aliases=aliases))
            source.write_text(json.dumps({"Alias": "talc", "ÁLIAS": "magnetite"}), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                classifier.load_aliases(source)

    def config(self, root, **options):
        result = Config(extra={"mineral_navigation": options})
        result.config_file_path = str(Path(root) / "mkdocs.yml")
        return result

    def files(self):
        return Files([
            File("index.md", "# Inicio"), File(SOURCE, table()),
            File("Plagioclasa.md", "---\ntags: [minerales]\n---\n# Plagioclasa"),
            File("nested/Albita.md", "---\ntags: [minerales]\n---\n# Albita"),
            File("Calcopitia.md", "---\ntags: [minerales, sulfuros]\n---\n"),
            File("Muestra nueva.md", "---\ntags: [minerales]\n---\nCuFeS2"),
            File("Talco dudoso.md", "---\ntags: [minerales]\n---\n"),
            File("Microclina Mc.md", ""), File("plantilla.md", "---\ntags: [minerales]\n---\n# Talco"),
            File("notes/General.md", "# Nota general"),
        ])

    def test_navigation_keeps_every_original_path_once_and_pending_references_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            files = self.files()
            before = [(file.src_uri, file.content_string) for file in files]
            config = self.config(directory, classification=SOURCE, references=[SOURCE], pending=["Microclina Mc.md"], templates=["plantilla.md"])
            self.assertIs(navigation.on_files(files, config), files)
            children = config["nav"][1]["Fichas de minerales"]
            self.assertIn({"Silicatos": [{"Tectosilicatos": [{"Feldespatos": [{"Plagioclasas": ["nested/Albita.md", "Plagioclasa.md"]}]}]}]}, children)
            self.assertIn({"Por clasificar": ["Calcopitia.md", "Muestra nueva.md", "Talco dudoso.md"]}, children)
            self.assertIn({"Tablas y guías": [SOURCE]}, children)
            self.assertIn({"Por completar": [{"Silicatos": [{"Tectosilicatos": [{"Feldespatos": [{"Alcalinos": ["Microclina Mc.md"]}]}]}]}]}, children)
            self.assertIn({"Plantillas": ["plantilla.md"]}, children)
            self.assertEqual(sorted(leaves(config["nav"])), sorted(file.src_uri for file in files))
            self.assertEqual(len(leaves(config["nav"])), len(set(leaves(config["nav"]))))
            self.assertEqual([(file.src_uri, file.content_string) for file in files], before)

    def test_missing_option_preserves_legacy_flat_navigation_without_loading_classifier(self):
        with tempfile.TemporaryDirectory() as directory:
            files = self.files()
            config = self.config(directory, references=[SOURCE], pending=["Microclina Mc.md"], templates=["plantilla.md"])
            navigation.on_files(files, config)
            children = config["nav"][1]["Fichas de minerales"]
            self.assertIn("Plagioclasa.md", children)
            self.assertIn("nested/Albita.md", children)
            self.assertNotIn("Por clasificar", str(children))
            self.assertIn({"Por completar": ["Microclina Mc.md"]}, children)

    def test_enabled_missing_or_empty_reference_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            for source in ["", "absent.md"]:
                with self.subTest(source=source), self.assertRaises(ConfigurationError):
                    navigation.on_files(self.files(), self.config(directory, classification=source))
            with self.assertRaises(ConfigurationError):
                navigation.on_files(Files([File(SOURCE, "# Vacio")]), self.config(directory, classification=SOURCE))

    def test_material_build_uses_table_changes_without_moving_or_editing_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "hooks").mkdir()
            (root / "docs").mkdir()
            for name in ["mineral_navigation.py", "mineral_classification.py"]:
                shutil.copyfile(ROOT / "hooks" / name, root / "hooks" / name)
            mineral = "---\ntags: [minerales]\n---\n# Plagioclasa\n\nTexto original.\n"
            (root / "docs/Plagioclasa.md").write_text(mineral, encoding="utf-8")
            (root / "docs/index.md").write_text("# Inicio", encoding="utf-8")
            (root / "docs" / SOURCE).write_text(table(), encoding="utf-8")
            config_data = {
                "site_name": "Minerales", "site_url": "https://example.com/wiki/", "theme": {"name": "material"},
                "docs_dir": "docs", "site_dir": "site", "plugins": [], "markdown_extensions": ["tables"],
                "hooks": ["hooks/mineral_navigation.py"],
                "extra": {"mineral_navigation": {"classification": SOURCE, "references": [SOURCE]}},
            }
            config_path = root / "mkdocs.yml"
            config_path.write_text(yaml.safe_dump(config_data, allow_unicode=True), encoding="utf-8")
            before = (root / "docs/Plagioclasa.md").read_bytes()
            build(load_config(str(config_path)))
            output = root / "site/Plagioclasa/index.html"
            self.assertTrue(output.exists())
            first = output.read_text(encoding="utf-8")
            self.assertIn("Feldespatos", first)
            self.assertIn("Plagioclasas", first)
            self.assertIn("Texto original.", first)
            self.assertEqual((root / "docs/Plagioclasa.md").read_bytes(), before)
            (root / "docs" / SOURCE).write_text(table().replace("Plagioclasas", "Serie editable"), encoding="utf-8")
            build(load_config(str(config_path)))
            second = output.read_text(encoding="utf-8")
            self.assertIn("Serie editable", second)
            self.assertTrue(output.exists())
            self.assertEqual((root / "docs/Plagioclasa.md").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
