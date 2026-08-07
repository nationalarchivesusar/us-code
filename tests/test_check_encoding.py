import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "tools" / "check_encoding.py"


def load_module():
    spec = importlib.util.spec_from_file_location("check_encoding_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_encoding_under_test"] = module
    spec.loader.exec_module(module)
    return module


class CheckEncodingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()

    def write_temp(self, text: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        )
        tmp.write(text)
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return Path(tmp.name)

    def test_clean_file_has_no_failures(self):
        path = self.write_temp(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<section>Ordinary text with a genuine question, like this one?</section>\n"
        )
        failures, question_marks = self.mod.scan_file(path)
        self.assertEqual([], failures)
        self.assertEqual(1, question_marks)

    def test_replacement_character_is_a_hard_failure(self):
        path = self.write_temp("<section>Broken � text</section>\n")
        failures, _ = self.mod.scan_file(path)
        self.assertEqual(1, len(failures))
        self.assertIn("replacement character", failures[0])

    def test_mojibake_em_dash_is_a_hard_failure(self):
        mojibake_em_dash = "—".encode("utf-8").decode("latin-1")
        path = self.write_temp(f"<section>Heading{mojibake_em_dash}Body</section>\n")
        failures, _ = self.mod.scan_file(path)
        self.assertEqual(1, len(failures))
        self.assertIn("em dash", failures[0])

    def test_mojibake_curly_quote_is_a_hard_failure(self):
        mojibake_quote = "’".encode("utf-8").decode("latin-1")
        path = self.write_temp(f"<section>President{mojibake_quote}s intention</section>\n")
        failures, _ = self.mod.scan_file(path)
        self.assertEqual(1, len(failures))
        self.assertIn("right single quotation mark", failures[0])

    def test_xml_processing_instructions_are_not_flagged(self):
        path = self.write_temp(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<?xml-stylesheet type="text/css" href="usctitle.css"?>\n'
            "<section>No stray punctuation here.</section>\n"
        )
        failures, question_marks = self.mod.scan_file(path)
        self.assertEqual([], failures)
        self.assertEqual(0, question_marks)

    def test_lfs_pointer_file_is_skipped(self):
        path = self.write_temp(
            "version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 123\n"
        )
        failures, question_marks = self.mod.scan_file(path)
        self.assertEqual([], failures)
        self.assertEqual(0, question_marks)

    def test_main_returns_nonzero_when_a_failure_is_present(self):
        path = self.write_temp("<section>Broken � text</section>\n")
        exit_code = self.mod.main([str(path)])
        self.assertEqual(1, exit_code)

    def test_main_returns_zero_for_clean_input(self):
        path = self.write_temp("<section>All clear, right?</section>\n")
        exit_code = self.mod.main([str(path)])
        self.assertEqual(0, exit_code)


class Title18SentencingRegressionTests(unittest.TestCase):
    """Protect the Roblox catalog from reverting Title 18 to blanket manual sentencing."""

    @classmethod
    def setUpClass(cls):
        path = ROOT / "data" / "api" / "v1" / "criminal-law" / "charges.json"
        if not path.is_file():
            raise unittest.SkipTest("Generated criminal-law API is not present")
        cls.payload = json.loads(path.read_text(encoding="utf-8"))
        cls.title18 = [
            item for item in cls.payload.get("charges", [])
            if item.get("source") == "title18"
        ]

    def test_title18_has_both_automatic_and_manual_entries(self):
        automatic = [
            item for item in self.title18
            if item.get("sentencing_mode") == "automatic_class_rule"
        ]
        manual = [
            item for item in self.title18
            if item.get("sentencing_mode") == "manual_required"
        ]
        self.assertGreater(len(automatic), 0)
        self.assertGreater(len(manual), 0)
        self.assertEqual(len(automatic), self.payload["counts"]["title18_automatic"])
        self.assertEqual(len(manual), self.payload["counts"]["title18_manual"])
        self.assertEqual(len(self.title18), len(automatic) + len(manual))

    def test_automatic_title18_entries_have_class_and_sentence_metadata(self):
        automatic = [
            item for item in self.title18
            if item.get("sentencing_mode") == "automatic_class_rule"
        ]
        for item in automatic:
            with self.subTest(section=item.get("section")):
                self.assertIn(item.get("offense_category"), {"felony", "misdemeanor"})
                self.assertIn(item.get("offense_class"), {"A", "B", "C", "D", "E"})
                self.assertEqual(item.get("classification_status"), "derived_from_title18")
                self.assertIsInstance(item.get("suggested_minutes"), (int, float))
                self.assertGreater(item["suggested_minutes"], 0)
                self.assertIn("18 U.S.C. § 3559", item.get("classification_basis", ""))

    def test_multitier_section_111_remains_manual(self):
        section_111 = next(
            item for item in self.title18 if str(item.get("section")) == "111"
        )
        self.assertEqual(section_111.get("sentencing_mode"), "manual_required")
        self.assertEqual(
            section_111.get("classification_status"),
            "manual_review_required",
        )


if __name__ == "__main__":
    unittest.main()
