import json
import re
import unittest
from pathlib import Path

from tools import build_criminal_law_api as builder


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "legal-data" / "criminal-law"


def load_code(code_id: str, *, apply_integration: bool = False) -> dict:
    document = json.loads((SOURCE / f"{code_id}.json").read_text(encoding="utf-8"))
    sections = []
    for path in sorted(SOURCE.glob(f"{code_id}-ch*.json")):
        sections.extend(json.loads(path.read_text(encoding="utf-8"))["sections"])
    document["sections"] = sorted(sections, key=lambda item: int(item["number"]))
    return builder.code_payload(document, apply_integration=apply_integration)


def offense_identity(section: dict) -> tuple[str, str, str]:
    heading = re.sub(r"[^a-z0-9]+", " ", section["heading"].lower()).strip()
    return str(section["section"]), heading, str(section.get("offense_class") or "")


class CriminalCodeDeduplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.federal = load_code("federal-criminal-code-2025")
        cls.dc = load_code("dc-criminal-code-federalized", apply_integration=True)

    def test_every_fcc_offense_is_already_represented_by_the_dc_code(self):
        federal = {
            offense_identity(section)
            for section in self.federal["sections"]
            if section["is_offense"] is True
        }
        dc = {
            offense_identity(section)
            for section in self.dc["sections"]
            if section["is_offense"] is True
        }

        self.assertEqual(66, len(federal))
        self.assertEqual(federal, dc)
        self.assertEqual(66, builder.assert_fcc_offenses_are_duplicated(self.federal, self.dc))

    def test_codes_are_not_byte_identical_despite_complete_offense_overlap(self):
        dc_by_section = {section["section"]: section for section in self.dc["sections"]}
        differing_text = [
            section["section"]
            for section in self.federal["sections"]
            if section["section"] in dc_by_section
            and section["text"] != dc_by_section[section["section"]]["text"]
        ]

        self.assertTrue(differing_text)
        self.assertIn("101", differing_text)
        self.assertIn("805", differing_text)

    def test_fcc_source_material_remains_preserved(self):
        self.assertTrue((SOURCE / "federal-criminal-code-2025.json").is_file())
        self.assertEqual(8, len(list(SOURCE.glob("federal-criminal-code-2025-ch*.json"))))


if __name__ == "__main__":
    unittest.main()
