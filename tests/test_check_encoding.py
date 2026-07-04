import importlib.util
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


if __name__ == "__main__":
    unittest.main()
