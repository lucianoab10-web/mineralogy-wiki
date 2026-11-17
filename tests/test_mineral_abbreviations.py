import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml
from mkdocs.commands.build import build
from mkdocs.config import load_config

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("abbreviations_under_test", ROOT / "hooks/mineral_abbreviations.py")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)
SOURCE = "abreviaturas minerales (EN).md"


class MineralAbbreviations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "docs" / SOURCE).read_text(encoding="utf-8")
        cls.table = hook._table(cls.source)
        cls.aliases = hook._load_aliases(ROOT / "references/mineral-name-aliases.json")

    def setUp(self):
        hook._matches.clear()
        hook._reference = SimpleNamespace(url=SOURCE[:-3] + "/")
        hook._title = "Table 1. Updated list of abbreviations"

    def symbols(self, name, table=None):
        entries = hook._lookup(name, table or self.table, self.aliases)
        return tuple(entry.symbol for entry in entries) if entries else None

    def page(self, name, url=None):
        return SimpleNamespace(file=SimpleNamespace(src_uri=name + ".md"), title=name, url=url or name + "/", meta={})

    def test_spanish_names_accents_groups_and_english_names(self):
        expected = {"Magnetita": ("Mag",), "Talco": ("Tlc",), "Calcita": ("Cal",), "Granate": ("Grt",), "CIRCÓN": ("Zrn",), "Cianita": ("Ky",), "Kyonita-Distena-Cianita": ("Ky",), "magnetite": ("Mag",), "Anfíboles Amp": ("Amp",)}
        for name, symbols in expected.items():
            with self.subTest(name=name):
                self.assertEqual(self.symbols(name), symbols)

    def test_absent_rows_do_not_invent_symbols_or_match_substrings(self):
        for name in ["Oro", "Cobre", "Platino", "Turquesa", "Piroxenos Px", "Magnetismo", "Granitico", "Cal"]:
            with self.subTest(name=name):
                self.assertIsNone(self.symbols(name))

    def test_table_changes_are_authoritative(self):
        updated = self.source.replace("| Tlc | talc | G |", "| Tlc2 | talc | G |")
        self.assertNotEqual(updated, self.source)
        self.assertEqual(self.symbols("Talco", hook._table(updated)), ("Tlc2",))

    def test_canonical_names_take_priority_over_parenthesized_synonyms(self):
        self.assertEqual(self.symbols("Titanita"), ("Ttn",))
        self.assertEqual(self.symbols("sphene"), ("Spn",))
        self.assertEqual(self.symbols("baryte"), ("Brt",))
        self.assertEqual(self.symbols("pumpellyite-(Al)"), ("Pmp",))
        self.assertIsNone(self.symbols("Approved"))

    def test_ambiguous_rows_and_conflicting_sheet_identities_are_rejected(self):
        table = hook._table("| Symbol | Mineral Name |\n| --- | --- |\n| T1 | talc |\n| T2 | talc |\n")
        self.assertIsNone(self.symbols("Talco", table))
        with self.assertLogs(hook.log, level="WARNING"):
            self.assertIsNone(hook._resolve("Talco.md", "", {"title": "Magnetita"}, self.table, self.aliases))

    def test_parser_skips_code_and_reads_reordered_columns(self):
        fake = "~~~md\n| Symbol | Mineral Name |\n| --- | --- |\n| Wrong | talc |\n~~~\n"
        real = "| Mineral Name | IMA status | Symbol |\n| --- | --- | --- |\n| talc | G | Tlc |\n\n| IMA status | Meaning |\n| --- | --- |\n| A | Approved |\n"
        table = hook._table(fake + real)
        self.assertEqual(hook._table_entry("talc", table), hook.Entry("Tlc", "talc", "G"))
        self.assertIsNone(hook._table_entry("Approved", table))

    def test_metadata_aliases_and_explicit_english_identity(self):
        self.assertEqual(hook._resolve("Muestra.md", "", {"aliases": ["Talco", "talc"]}, self.table, self.aliases)[0].symbol, "Tlc")
        self.assertEqual(hook._resolve("Muestra.md", "", {"mineral_name_en": "talc"}, self.table, self.aliases)[0].symbol, "Tlc")
        self.assertIsNone(hook._resolve("Muestra.md", "", {"mineral_name_en": "unknown"}, self.table, self.aliases))
        fence = "~~~md\n# Magnetita\n~~~\n# Talco\n"
        self.assertEqual(hook._resolve("Muestra.md", fence, {}, self.table, self.aliases)[0].symbol, "Tlc")

    def test_combined_sheet_requires_every_species_to_exist(self):
        name = "Tenantina - Tetrahidrita"
        self.assertEqual(self.symbols(name), ("Tnt", "Ttr"))
        changed = self.source.replace("| Ttr | tetrahedrite | A |", "")
        self.assertIsNone(self.symbols(name, hook._table(changed)))

    def test_heading_preserves_markup_permalink_body_and_nested_links(self):
        page = self.page("Talco", "subcarpeta/Talco/")
        hook._matches[page.file.src_uri] = hook._lookup("Talco", self.table, self.aliases)
        original = '<h1 id="talco"><em>Talco</em><a class="headerlink" href="#talco">¶</a></h1><table><tr><td>Nota</td></tr></table>'
        result = hook.on_page_content(original, page, None)
        self.assertIn('<h1 id="talco"><em>Talco</em> <span', result)
        self.assertIn('</span><a class="headerlink" href="#talco">¶</a></h1>', result)
        self.assertIn('href="../../abreviaturas%20minerales%20%28EN%29/"', result)
        self.assertTrue(result.endswith('<table><tr><td>Nota</td></tr></table>'))
        self.assertEqual(page.meta["mineral_abbreviations"], ["Tlc"])
        self.assertEqual(hook.on_page_content(result, page, None), result)

    def test_table_first_sheets_get_one_heading_and_existing_symbols_are_not_duplicated(self):
        page = self.page("Magnetita")
        hook._matches[page.file.src_uri] = hook._lookup("Magnetita", self.table, self.aliases)
        original = "<table><tr><td>Datos</td></tr></table>"
        result = hook.on_page_content(original, page, None)
        self.assertTrue(result.startswith("<h1>Magnetita "))
        self.assertEqual(result.count("<h1>"), 1)
        self.assertTrue(result.endswith(original))
        existing = '<h1>Magnetita (Mag)</h1>' + original
        self.assertEqual(hook.on_page_content(existing, page, None), existing)
        self.assertEqual(hook.on_page_content(original, self.page("Oro"), None), original)

    def test_missing_reference_clears_previous_build_state(self):
        hook._matches["Talco.md"] = hook._lookup("Talco", self.table, self.aliases)
        with self.assertLogs(hook.log, level="WARNING"):
            hook.on_files(SimpleNamespace(get_file_from_path=lambda path: None), {"extra": {"mineral_abbreviations": {"source": SOURCE}}})
        self.assertFalse(hook._matches)
        self.assertIsNone(hook._reference)

    def test_full_material_build_updates_symbols_and_preserves_source_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "hooks").mkdir()
            (root / "docs/subcarpeta").mkdir(parents=True)
            for name in ["mineral_navigation.py", "mineral_abbreviations.py"]:
                shutil.copyfile(ROOT / "hooks" / name, root / "hooks" / name)
            (root / "docs" / SOURCE).write_text(self.source, encoding="utf-8")
            documents = {
                "Magnetita.md": "---\ntags: [minerales]\n---\n| imagen | nota |\n| --- | --- |\n| Foto | Nota |\n",
                "subcarpeta/Talco.md": "---\ntags: [minerales]\n---\n# Talco\n\nContenido.\n",
                "Oro.md": "---\ntags: [minerales]\n---\n# Oro\n",
                "Guia.md": "# Talco\n\nNota general sin etiqueta mineral.\n",
                "baseminerales.md": "---\ntags: [minerales]\n---\n# Talco\n",
            }
            for name, text in documents.items():
                (root / "docs" / name).write_text(text, encoding="utf-8")
            config_data = {
                "site_name": "Minerals", "site_url": "https://example.com/wiki/", "theme": {"name": "material"},
                "docs_dir": "docs", "site_dir": "site", "plugins": [], "markdown_extensions": ["tables"],
                "hooks": ["hooks/mineral_navigation.py", "hooks/mineral_abbreviations.py"],
                "extra": {"mineral_abbreviations": {"source": SOURCE, "aliases": str(ROOT / "references/mineral-name-aliases.json")},
                          "mineral_navigation": {"references": [SOURCE], "templates": ["baseminerales.md"]}},
            }
            config_path = root / "mkdocs.yml"
            config_path.write_text(yaml.safe_dump(config_data, allow_unicode=True), encoding="utf-8")
            before = {file: file.read_bytes() for file in (root / "docs").rglob("*.md")}
            build(load_config(str(config_path), strict=True))
            for file, data in before.items():
                self.assertEqual(file.read_bytes(), data)
            mag = (root / "site/Magnetita/index.html").read_text(encoding="utf-8")
            talc = (root / "site/subcarpeta/Talco/index.html").read_text(encoding="utf-8")
            self.assertIn('class="mineral-abbreviation"', mag)
            self.assertIn('>Mag</a>)</span>', mag)
            self.assertIn('>Tlc</a>)</span>', talc)
            for name in ["Oro", "Guia", "baseminerales", SOURCE[:-3]]:
                self.assertNotIn('class="mineral-abbreviation"', (root / "site" / name / "index.html").read_text(encoding="utf-8"))
            source = root / "docs" / SOURCE
            source.write_text(self.source.replace("| Tlc | talc | G |", "| Tlc2 | talc | G |"), encoding="utf-8")
            build(load_config(str(config_path), strict=True))
            self.assertIn('>Tlc2</a>)</span>', (root / "site/subcarpeta/Talco/index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
