import base64
import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sections_mod = load_module("current_law_sections_sidecar_test", ROOT / "tools" / "apply_current_law_sections.py")
notes_mod = load_module("current_law_notes_sidecar_test", ROOT / "tools" / "apply_current_law_notes.py")
public_laws_mod = load_module("current_public_law_trello_test", ROOT / "tools" / "augment_public_laws_with_current_laws.py")


class CurrentLawSidecarTests(unittest.TestCase):
    def test_section_sidecar_is_merged(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            base = {
                "schema_version": "1.0",
                "chapters": [],
                "existing_chapter_sections": [],
                "section_subsections": [],
                "replacement_notes": [],
            }
            packed = base64.b64encode(gzip.compress(json.dumps(base).encode("utf-8"))).decode("ascii")
            (directory / "current-law-sections.json.gz.b64.part01").write_text(packed, encoding="ascii")
            chapter = {"title": 2, "chapter": "70", "parent_identifier": "/us/usc/t2", "toc_parent_identifier": "/us/usc/t2", "heading": "TEST"}
            for part, section in ((1, "7001"), (2, "7002")):
                extra = {
                    "schema_version": "1.0",
                    "chapters": [{**chapter, "sections": [{"section": section}], "chapter_notes": []}],
                    "existing_chapter_sections": [],
                    "section_subsections": [],
                    "replacement_notes": [],
                }
                (directory / f"current-law-sections.extra.test.part{part}.json").write_text(json.dumps(extra), encoding="utf-8")
            merged = sections_mod.load_manifest(directory)
            self.assertEqual(len(merged["chapters"]), 1)
            self.assertEqual(merged["chapters"][0]["chapter"], "70")
            self.assertEqual([section["section"] for section in merged["chapters"][0]["sections"]], ["7001", "7002"])

    def test_note_sidecar_is_merged(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            primary = directory / "current-law-notes.json"
            primary.write_text(json.dumps({
                "schema_version": "1.0",
                "notes": [{
                    "id": "rp-primary", "title": "2", "section": "1901", "topic": "miscellaneous",
                    "heading": "Primary", "paragraphs": ["Primary manifest paragraph."]
                }]
            }), encoding="utf-8")
            (directory / "current-law-notes.extra.test.json").write_text(json.dumps({
                "schema_version": "1.0",
                "notes": [{
                    "id": "rp-extra", "title": "2", "section": "1901a", "topic": "miscellaneous",
                    "heading": "Extra", "paragraphs": ["Sidecar manifest paragraph."]
                }]
            }), encoding="utf-8")
            merged = notes_mod.load_manifest(primary)
            self.assertEqual([note["id"] for note in merged["notes"]], ["rp-primary", "rp-extra"])

    def test_current_law_can_supply_trello_short_link(self):
        row = {
            "law_id": "PL-042-274",
            "public_law": "42-274",
            "title": "United States Capitol Police Reform and Accountability Act",
            "status": "active",
            "trello_short_link": "DAwGab9j",
            "actions": [],
        }
        law = public_laws_mod.build_current_law(row, {})
        self.assertEqual(law["trello_url"], "https://trello.com/c/DAwGab9j")


if __name__ == "__main__":
    unittest.main()
