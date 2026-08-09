import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "tools" / "check_encoding.py"
CLASSIFIER_PATH = ROOT / "tools" / "title18_charge_classifier.py"


def load_module_from(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_module():
    return load_module_from(SCRIPT_PATH, "check_encoding_under_test")


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


class Title18ChargeClassifierTests(unittest.TestCase):
    """Protect common Title 18 drafting styles from false-negative filtering."""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_module_from(
            CLASSIFIER_PATH, "title18_charge_classifier_under_test"
        )

    def detail(self, section: str, heading: str, text: str) -> dict:
        return {
            "section": section,
            "heading": heading,
            "text": text,
            "status": "current",
            "charge_candidate": True,
        }

    def test_known_offense_is_checked_before_heading_filter(self):
        detail = self.detail(
            "113",
            "Assaults within maritime and territorial jurisdiction",
            "Whoever commits an assault shall be fined under this title.",
        )
        self.assertTrue(self.mod.title18_is_positive_charge(detail))

    def test_conditional_penalty_clause_is_a_charge(self):
        detail = self.detail(
            "752",
            "Instigating or assisting escape",
            (
                "Whoever assists an escape shall, if the custody is by virtue "
                "of a felony arrest, be fined under this title or imprisoned."
            ),
        )
        self.assertTrue(self.mod.title18_is_positive_charge(detail))

    def test_intervening_penalty_clause_is_a_charge(self):
        detail = self.detail(
            "1501",
            "Assault on process server",
            (
                "Whoever obstructs an officer shall, except as otherwise "
                "provided by law, be fined under this title or imprisoned."
            ),
        )
        self.assertTrue(self.mod.title18_is_positive_charge(detail))

    def test_conspiracy_formulation_is_a_charge(self):
        detail = self.detail(
            "2384",
            "Seditious conspiracy",
            (
                "If two or more persons conspire to oppose lawful authority, "
                "they shall each be fined under this title or imprisoned."
            ),
        )
        self.assertTrue(self.mod.title18_is_positive_charge(detail))

    def test_split_prohibition_and_penalty_section_is_a_charge(self):
        detail = self.detail(
            "1962",
            "Prohibited activities",
            "It shall be unlawful for any person to engage in the prohibited conduct.",
        )
        self.assertTrue(self.mod.title18_is_positive_charge(detail))

    def test_administrative_heading_remains_noncharge(self):
        detail = self.detail(
            "2518",
            "Procedure for interception of wire, oral, or electronic communications",
            (
                "A person who violates an order shall be fined under this title "
                "or imprisoned."
            ),
        )
        self.assertFalse(self.mod.title18_is_positive_charge(detail))


class Title18SentencingRegressionTests(unittest.TestCase):
    """Protect the Roblox catalog from sentencing and charge-retention regressions."""

    @classmethod
    def setUpClass(cls):
        base = ROOT / "data" / "api" / "v1" / "criminal-law"
        charges_path = base / "charges.json"
        if not charges_path.is_file():
            raise unittest.SkipTest("Generated criminal-law API is not present")
        cls.base = base
        cls.payload = json.loads(charges_path.read_text(encoding="utf-8"))
        cls.manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
        cls.sentencing = json.loads((base / "sentencing.json").read_text(encoding="utf-8"))
        cls.title18 = [
            item for item in cls.payload.get("charges", [])
            if item.get("source") == "title18"
        ]
        cls.title18_by_section = {
            str(item.get("section")): item for item in cls.title18
        }

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
        section_111 = self.title18_by_section["111"]
        self.assertEqual(section_111.get("sentencing_mode"), "manual_required")
        self.assertEqual(
            section_111.get("classification_status"),
            "manual_review_required",
        )

    def test_escape_section_751_remains_bookable_with_body_withheld(self):
        section_751 = self.title18_by_section["751"]
        self.assertEqual(section_751.get("charge_classification"), "known_positive_charge")
        self.assertEqual(section_751.get("sentencing_mode"), "manual_required")
        self.assertTrue(section_751.get("text_withheld"))

        detail = json.loads((self.base / "title18" / "751.json").read_text(encoding="utf-8"))
        self.assertEqual(detail.get("heading"), "Prisoners in custody of institution or officer")
        self.assertTrue(detail.get("text_withheld"))
        self.assertEqual(detail.get("text_display_scope"), "withheld_for_platform_safety")

    def test_representative_legitimate_charges_survive_classifier_audit(self):
        required = {
            "81",    # arson in special maritime/territorial jurisdiction
            "113",   # assault in special maritime/territorial jurisdiction
            "241",   # conspiracy against rights
            "371",   # general conspiracy
            "752",   # instigating/assisting escape
            "956",   # conspiracy to kill/kidnap/maim/injure abroad
            "1001",  # false statements
            "1031",  # major fraud against the United States
            "1113",  # attempt to commit murder/manslaughter
            "1501",  # assault on process server
            "1505",  # obstruction of agency/committee proceedings
            "1751",  # protectee assassination/kidnapping/assault
            "1962",  # prohibited racketeering activities
            "2119",  # motor-vehicle robbery/carjacking
            "2384",  # seditious conspiracy
            "2511",  # unlawful interception/disclosure
        }
        missing = required - set(self.title18_by_section)
        self.assertEqual(set(), missing)

    def test_body_only_secondary_references_are_withheld_not_deleted(self):
        for section in ("1001", "1505"):
            with self.subTest(section=section):
                item = self.title18_by_section[section]
                self.assertTrue(item.get("text_withheld"))
                detail = json.loads(
                    (self.base / "title18" / f"{section}.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertTrue(detail.get("text_withheld"))
                self.assertEqual(
                    detail.get("text_display_scope"),
                    "withheld_for_platform_safety",
                )

    def test_obvious_noncharge_sections_remain_absent(self):
        for section in ("5", "17", "2518"):
            with self.subTest(section=section):
                self.assertNotIn(section, self.title18_by_section)

    def test_secondary_filter_declares_body_withholding_contract(self):
        roblox = self.manifest.get("roblox") or {}
        surface = roblox.get("public_surface") or {}
        self.assertEqual("roblox-safe-charge-only-v5", roblox.get("filter_version"))
        self.assertTrue(surface.get("body_only_secondary_failures_are_withheld"))

    def test_roblox_booking_cap_is_20_without_rewriting_statutory_ceiling(self):
        policy = self.payload.get("sentencing_policy") or {}
        roblox = self.manifest.get("roblox") or {}
        booking = self.sentencing.get("roblox_booking_policy") or {}
        statutory = (self.sentencing.get("rules") or {}).get("multi_charge_max_minutes")

        self.assertEqual(30, statutory)
        self.assertEqual(20, policy.get("multi_charge_max_minutes"))
        self.assertEqual(20, roblox.get("multi_charge_max_minutes"))
        self.assertEqual(20, booking.get("multi_charge_max_minutes"))
        self.assertEqual(30, policy.get("statutory_multi_charge_max_minutes"))
        self.assertEqual(30, roblox.get("statutory_multi_charge_max_minutes"))
        self.assertEqual(30, booking.get("statutory_multi_charge_max_minutes"))


if __name__ == "__main__":
    unittest.main()
